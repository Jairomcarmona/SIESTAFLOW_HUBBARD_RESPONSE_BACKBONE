"""Safe, site-specific SIESTA FDF materialization from a generic LR plan.

Unlike the legacy generic FDF builder, this module never replaces an entire
``DFTU.Proj`` block.  It preserves every correlated-site definition and
changes only the declared target potential shift plus the BARE/SCREENED
controls.  This is required for a symmetry plan to remain scientifically tied
to the audited reference FDF.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from siestaflow_hubbard.domain.symmetry_reduction import PerturbationSpec, ResponseMode
from .backend_admission import BackendAdmission
from .backend_admission_plugin import _is_campaign_contract_admission
from .siesta542_bare_profile import Siesta542PotentialShiftHamiltonianProfile


class ResponseMaterializationError(ValueError):
    """An input cannot safely become a SIESTA LR response calculation."""


@dataclass(frozen=True)
class MaterializedResponse:
    run_id: str
    target_site_id: str
    mode: ResponseMode
    alpha_ev: float
    content: str


def _split_block(lines: list[str]) -> tuple[int, int]:
    starts = [index for index, line in enumerate(lines) if line.strip().lower() == "%block dftu.proj"]
    ends = [index for index, line in enumerate(lines) if line.strip().lower() == "%endblock dftu.proj"]
    if len(starts) != 1 or len(ends) != 1 or ends[0] <= starts[0]:
        raise ResponseMaterializationError("exactly one complete DFTU.Proj block is required")
    return starts[0], ends[0]


def _replace_key(content: str, key: str, value: str) -> str:
    pattern = re.compile(rf"^\s*{re.escape(key)}\b.*$", re.IGNORECASE | re.MULTILINE)
    replacement = f"{key} {value}"
    return pattern.sub(replacement, content, count=1) if pattern.search(content) else content.rstrip() + f"\n{replacement}\n"


def _require_scalar(content: str, key: str, allowed: set[str]) -> None:
    match = re.search(rf"^\s*{re.escape(key)}\s+([^\s#]+)", content, re.IGNORECASE | re.MULTILINE)
    if not match or match.group(1).lower() not in allowed:
        raise ResponseMaterializationError(f"reference FDF lacks required {key} contract")


def _rewrite_projector_shifts(content: str, target_site_id: str, alpha_ev: float) -> str:
    lines = content.splitlines()
    start, end = _split_block(lines)
    body = lines[start + 1:end]
    if len(body) % 4:
        raise ResponseMaterializationError("DFTU.Proj must use four-line site records")
    found_target = False
    rewritten: list[str] = []
    for offset in range(0, len(body), 4):
        header, shell, _shift, radial = body[offset:offset + 4]
        fields = header.split()
        shell_fields = shell.split()
        if len(fields) != 2 or fields[1] != "1" or len(shell_fields) != 2:
            raise ResponseMaterializationError("unsupported or ambiguous DFTU.Proj site record")
        try:
            int(shell_fields[0]); int(shell_fields[1])
            float(radial.split()[0]); float(radial.split()[1])
        except (ValueError, IndexError) as exc:
            raise ResponseMaterializationError("non-numeric DFTU.Proj site record") from exc
        site_id = fields[0]
        shift = alpha_ev if site_id == target_site_id else 0.0
        found_target |= site_id == target_site_id
        rewritten.extend((header, shell, f"  {shift:+.4f} 0.0000", radial))
    if not found_target:
        raise ResponseMaterializationError(f"target Hubbard site absent from DFTU.Proj: {target_site_id}")
    return "\n".join([*lines[:start + 1], *rewritten, *lines[end:]]) + "\n"


def materialize_response_fdf(
    reference_fdf: str | Path,
    spec: PerturbationSpec,
    *,
    bare_profile: Siesta542PotentialShiftHamiltonianProfile | None = None,
    admission: BackendAdmission | None = None,
) -> MaterializedResponse:
    """Render one response FDF while preserving all unperturbed projectors.

    The audited reference must already declare SIESTA method-2 projectors and
    potential shifting.  The function does not create pseudopotentials, copy
    a DM, execute SIESTA, or select an occupation event.
    """
    if spec.mode is ResponseMode.BARE:
        if bare_profile is None or not isinstance(admission, BackendAdmission):
            raise ResponseMaterializationError(
                "BARE materialization requires an admitted SIESTA 5.4.2 profile"
            )
        if not _is_campaign_contract_admission(admission):
            raise ResponseMaterializationError("BARE materialization requires campaign-contract admission")
        if admission.scientific_profile.key != (bare_profile.profile_id, bare_profile.profile_version):
            raise ResponseMaterializationError("BARE profile differs from the admitted scientific profile")
    content = Path(reference_fdf).read_text(encoding="utf-8")
    _require_scalar(content, "DFTU.ProjectorGenerationMethod", {"2"})
    _require_scalar(content, "DFTU.PotentialShift", {"true", "t"})
    content = _rewrite_projector_shifts(content, spec.site_id, spec.alpha_ev)
    content = _replace_key(content, "SystemLabel", spec.run_id)
    content = _replace_key(content, "DFTU.FirstIteration", "true")
    content = _replace_key(content, "DM.UseSaveDM", "true")
    if spec.mode is ResponseMode.BARE:
        controls: dict[str, str] = {}
    elif spec.mode is ResponseMode.SCREENED:
        controls = {
            "MaxSCFIterations": "300",
            "SCF.MustConverge": "T",
            "SCF.Mix": "Hamiltonian",
            "SCF.Mixer.Method": "Pulay",
            "SCF.Mixer.Weight": "0.05",
            "SCF.Mixer.History": "8",
            "SCF.DM.Converge": "T",
            "SCF.H.Converge": "T",
            "SCF.DM.Tolerance": "1.0e-5",
            "SCF.H.Tolerance": "1.0e-4 eV",
        }
    else:  # pragma: no cover - protects future enum extension.
        raise ResponseMaterializationError(f"unsupported response mode: {spec.mode}")
    for key, value in controls.items():
        content = _replace_key(content, key, value)
    if spec.mode is ResponseMode.BARE:
        assert bare_profile is not None
        content = bare_profile.materialize(content)
    return MaterializedResponse(spec.run_id, spec.site_id, spec.mode, spec.alpha_ev, content)


def write_materialized_response(reference_fdf: str | Path, spec: PerturbationSpec,
                                destination: str | Path, *,
                                bare_profile: Siesta542PotentialShiftHamiltonianProfile | None = None,
                                admission: BackendAdmission | None = None) -> MaterializedResponse:
    rendered = materialize_response_fdf(
        reference_fdf, spec, bare_profile=bare_profile, admission=admission,
    )
    Path(destination).write_text(rendered.content, encoding="utf-8", newline="\n")
    return rendered
