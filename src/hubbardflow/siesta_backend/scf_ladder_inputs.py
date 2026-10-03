"""Read-only binding of SCF ladder metadata to authoritative SIESTA inputs.

The existing FDF model supplies projector/site syntax; the audited BARE
profile supplies its mode contract. An explicit screened SCF contract is
required for SCREENED preparation. Output convergence still needs validation
after the user's run and cannot be established from an input file.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction
from hashlib import sha256
from pathlib import Path
from typing import cast

from hubbardflow.domain.response_budget_models import _Record
from hubbardflow.domain.scf_ladder_models import ScfLadderError, ScfLevel, ScfReason, ScfStatus
from hubbardflow.domain.symmetry_reduction import ResponseMode
from hubbardflow.domain.validation import require_fdf_representable_ev, require_int, require_sha256
from hubbardflow.execution.campaign_v2 import resolve_fdf_includes

from .fdf_labels import canonical_fdf_label
from .fdf_model import _directive_rows, _one, parse_effective_fdf
from .reference_state_evidence import build_reference_state_evidence
from .siesta542_bare_profile import Siesta542PotentialShiftHamiltonianProfile


@dataclass(frozen=True)
class LadderInputBinding:
    site_id: str
    mode: ResponseMode
    alpha_ev: float
    atom_index: int
    effective_fdf_sha256: str
    effective_text: str

    def __post_init__(self) -> None:
        try:
            if not isinstance(self.site_id, str) or not self.site_id or self.site_id != self.site_id.strip():
                raise ScfLadderError("site_id must be a nonempty literal DFTU label")
            if not isinstance(self.mode, ResponseMode):
                raise ScfLadderError("mode must be a ResponseMode")
            require_fdf_representable_ev(self.alpha_ev, "alpha_ev")
            require_int(self.atom_index, "atom_index", minimum=0)
            require_sha256(self.effective_fdf_sha256, "effective_fdf_sha256")
            if not isinstance(self.effective_text, str) or not self.effective_text.strip():
                raise ScfLadderError("effective_text must retain the nonempty exact FDF text")
        except ValueError as exc:
            raise ScfLadderError(str(exc)) from exc

    def to_mapping(self) -> dict[str, object]:
        return {
            "site_id": self.site_id,
            "mode": self.mode.value,
            "alpha_ev": self.alpha_ev,
            "atom_index": self.atom_index,
            "effective_fdf_sha256": self.effective_fdf_sha256,
            "effective_text": self.effective_text,
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> LadderInputBinding:
        if set(payload) != {
            "site_id",
            "mode",
            "alpha_ev",
            "atom_index",
            "effective_fdf_sha256",
            "effective_text",
        }:
            raise ScfLadderError("LadderInputBinding mapping must contain exactly its declared fields")
        try:
            return cls(
                cast(str, payload["site_id"]),
                ResponseMode(cast(str, payload["mode"])),
                cast(float, payload["alpha_ev"]),
                cast(int, payload["atom_index"]),
                cast(str, payload["effective_fdf_sha256"]),
                cast(str, payload["effective_text"]),
            )
        except ValueError as exc:
            raise ScfLadderError(str(exc)) from exc


def _reject_file_dm_init(effective_text: str) -> None:
    """Reject unsafe restart directives before parsing can mask the safety error."""
    for raw_line in effective_text.splitlines():
        directive = raw_line.partition("#")[0].split(maxsplit=1)
        if directive and canonical_fdf_label(directive[0]) == "filedminit":
            raise ScfLadderError("File.DM.Init is prohibited; supply DM.UseSaveDM true")


def bind_ladder_input(source: Path, site_id: str, mode: ResponseMode, alpha_ev: float) -> LadderInputBinding:
    """Reject mismatched/ambiguous input identities before any file is written.

    Exactly one supported projector has the nonzero declared alpha and zero
    second-channel shift; every other correlated projector is unshifted. Site
    IDs name the literal DFTU label, which must identify exactly one atom.
    No approximate alpha comparison or inferred mode is permitted.
    """
    try:
        require_fdf_representable_ev(alpha_ev, "alpha_ev")
        if alpha_ev == 0:
            raise ScfLadderError("zero perturbations are not SCF ladder inputs")
        effective, _ = resolve_fdf_includes(source)
        _reject_file_dm_init(effective)
        # Validate the whole input after rejecting the unsafe restart route.
        model = parse_effective_fdf(source)
        if model.dftu_method != 2 or model.dftu_potential_shift is not True:
            raise ScfLadderError("input must explicitly establish method-2 DFTU.PotentialShift")
        target = [r for r in model.dftu_records if r.label == site_id]
        atoms = [atom for atom in model.atoms if atom.species_label == site_id]
        if len(target) != 1 or len(atoms) != 1:
            raise ScfLadderError("target DFTU label must identify exactly one projector and atom")
        for record in model.dftu_records:
            require_fdf_representable_ev(record.u_ref_ev, "DFTU.Proj potential shift")
            if record.projector_header_value != "1" or record.j_ref_ev != 0:
                raise ScfLadderError("unsupported projector multiplicity or nonzero second-channel shift")
            expected = alpha_ev if record.label == site_id else 0.0
            shift_fields = record.canonical_text.splitlines()[2].split()
            exact_shift = Fraction(shift_fields[0].replace("D", "e").replace("d", "e"))
            exact_second_channel = Fraction(shift_fields[1].replace("D", "e").replace("d", "e"))
            if exact_shift != Fraction(str(expected)) or exact_second_channel:
                raise ScfLadderError("DFTU.Proj label/alpha does not match the ladder request")
        text = model.effective_text
        profile = Siesta542PotentialShiftHamiltonianProfile()
        if mode is ResponseMode.BARE:
            profile.validate_fdf(text)
        elif mode is ResponseMode.SCREENED:
            for key in ("DFTU.FirstIteration", "DM.UseSaveDM", "SCF.MustConverge"):
                value = _one(text, key)
                if value is None or value.casefold() not in {"true", "t"}:
                    raise ScfLadderError(f"SCREENED input must explicitly declare {key} true")
            mix = _one(text, "SCF.Mix")
            if mix is None or mix.casefold() != profile.required_fdf_values["SCF.Mix"]:
                raise ScfLadderError("SCREENED input must explicitly establish the supported SCF.Mix")
            iterations = _one(text, "MaxSCFIterations")
            if iterations is None:
                raise ScfLadderError("SCREENED input must explicitly declare MaxSCFIterations")
            count = require_int(int(iterations), "MaxSCFIterations", minimum=1)
            if count == int(profile.required_fdf_values["MaxSCFIterations"]):
                raise ScfLadderError("SCREENED input cannot use the BARE one-diagonalization limit")
        else:
            raise ScfLadderError("unsupported response mode")
        return LadderInputBinding(
            site_id, mode, alpha_ev, atoms[0].atom_index, model.effective_fdf_sha256, text
        )
    except (ValueError, OSError) as exc:
        raise ScfLadderError(f"NOT_ESTABLISHED: source FDF ladder identity cannot be bound: {exc}") from exc


@dataclass(frozen=True)
class LadderMaterializedInput(_Record):
    level_id: str
    dm_tolerance: float
    h_tolerance_ev: float
    effective_source_fdf_sha256: str
    materialized_fdf_sha256: str
    effective_text: str
    effective_criteria: tuple[tuple[str, str | None], ...]

    def __post_init__(self) -> None:
        # _Record's identifier strings exclude trailing whitespace; effective
        # FDF text is instead an exact multiline artifact, including its newline.
        level = ScfLevel(self.level_id, self.dm_tolerance, self.h_tolerance_ev)
        level.require_echo_representable()
        require_sha256(self.effective_source_fdf_sha256, "effective_source_fdf_sha256")
        require_sha256(self.materialized_fdf_sha256, "materialized_fdf_sha256")
        if not isinstance(self.effective_text, str) or not self.effective_text.strip():
            raise ScfLadderError("materialized FDF text must be nonempty")
        if sha256(self.effective_text.encode()).hexdigest() != self.materialized_fdf_sha256:
            raise ScfLadderError("materialized FDF digest does not match its exact text")
        if not isinstance(self.effective_criteria, tuple) or any(
            not isinstance(pair, tuple)
            or len(pair) != 2
            or not isinstance(pair[0], str)
            or not pair[0].strip()
            or (pair[1] is not None and (not isinstance(pair[1], str) or not pair[1].strip()))
            for pair in self.effective_criteria
        ):
            raise ScfLadderError("effective_criteria must retain explicit label/value pairs")

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> LadderMaterializedInput:
        if set(payload) != {
            "level_id",
            "dm_tolerance",
            "h_tolerance_ev",
            "effective_source_fdf_sha256",
            "materialized_fdf_sha256",
            "effective_text",
            "effective_criteria",
        }:
            raise ScfLadderError("materialized input mapping must contain exactly its declared fields")
        pairs = payload["effective_criteria"]
        if not isinstance(pairs, (tuple, list)) or any(not isinstance(pair, (tuple, list)) for pair in pairs):
            raise ScfLadderError("effective_criteria must be label/value pairs")
        return cls(
            cast(str, payload["level_id"]),
            cast(float, payload["dm_tolerance"]),
            cast(float, payload["h_tolerance_ev"]),
            cast(str, payload["effective_source_fdf_sha256"]),
            cast(str, payload["materialized_fdf_sha256"]),
            cast(str, payload["effective_text"]),
            cast(tuple[tuple[str, str | None], ...], tuple(tuple(pair) for pair in pairs)),
        )


def _materialize_tolerances(text: str, level: ScfLevel) -> LadderMaterializedInput:
    level.require_echo_representable()
    assert level.h_tolerance_ev is not None
    removed = {"dmtolerance", "scfdmtolerance", "scfhtolerance"}
    lines: list[str] = []
    active = False
    for line in text.splitlines():
        body = line.partition("#")[0].strip()
        if re.match(r"%block\s", body, re.IGNORECASE):
            active = True
        elif re.match(r"%endblock(?:\s|$)", body, re.IGNORECASE):
            active = False
        fields = body.split(maxsplit=1)
        if not active and fields and canonical_fdf_label(fields[0]) in removed:
            continue
        lines.append(line)
    materialized = "\n".join(lines).rstrip() + (
        f"\nSCF.DM.Tolerance {level.dm_tolerance:.6f}\nSCF.H.Tolerance {level.h_tolerance_ev:.6f} eV\n"
    )
    recorded: dict[str, str | None] = {
        label: value
        for label, value in _directive_rows(materialized)
        if canonical_fdf_label(label) in {"scfdmconverge", "scfhconverge", "maxscfiterations"}
        or canonical_fdf_label(label).startswith(("scfedm", "scffreee"))
        or "harris" in canonical_fdf_label(label)
    }
    # An undeclared criterion is absent evidence, never an inferred SIESTA
    # default. Retain that absence explicitly alongside the declared values.
    for label in ("SCF.DM.Converge", "SCF.H.Converge", "MaxSCFIterations"):
        if not any(canonical_fdf_label(key) == canonical_fdf_label(label) for key in recorded):
            recorded[label] = None
    for group, matches in (
        ("SCF.EDM.*", lambda key: key.startswith("scfedm")),
        ("SCF.FreeE.*", lambda key: key.startswith("scffreee")),
        ("Harris", lambda key: "harris" in key),
    ):
        if not any(matches(canonical_fdf_label(key)) for key in recorded):
            recorded[group] = None
    criteria = tuple(sorted(recorded.items()))
    return LadderMaterializedInput(
        level.level_id,
        level.dm_tolerance,
        level.h_tolerance_ev,
        sha256(text.encode()).hexdigest(),
        sha256(materialized.encode()).hexdigest(),
        materialized,
        criteria,
    )


def materialize_ladder_input(
    source: Path, site_id: str, mode: ResponseMode, alpha_ev: float, level: ScfLevel
) -> LadderMaterializedInput:
    """Harden only declared DM/H tolerances; BARE retains one diagonalization."""
    binding = bind_ladder_input(source, site_id, mode, alpha_ev)
    return _materialize_tolerances(binding.effective_text, level)


def materialize_ladder_reference(reference_fdf: Path, level: ScfLevel) -> LadderMaterializedInput:
    """Prepare the independent zero-shift reference whose output DM defines one level.

    The reference is not an alpha-zero noise replica. No SCF result is inferred
    here: its normal completion and positive convergence evidence are checked
    after the user runs it.
    """
    effective, _ = resolve_fdf_includes(reference_fdf)
    _reject_file_dm_init(effective)
    model = parse_effective_fdf(reference_fdf)
    if model.dftu_potential_shift is True and any(
        r.u_ref_ev != 0 or r.j_ref_ev != 0 for r in model.dftu_records
    ):
        raise ScfLadderError("level reference must have no DFTU potential shift")
    result = _materialize_tolerances(model.effective_text, level)
    # Explicitly preserve zero-shift reference semantics rather than relying on
    # a SIESTA default for this flag.
    lines: list[str] = []
    active = False
    for line in result.effective_text.splitlines():
        body = line.partition("#")[0].strip()
        if re.match(r"%block\s", body, re.IGNORECASE):
            active = True
        elif re.match(r"%endblock(?:\s|$)", body, re.IGNORECASE):
            active = False
        fields = body.split(maxsplit=1)
        if not active and fields and canonical_fdf_label(fields[0]) == "dftupotentialshift":
            continue
        lines.append(line)
    text = "\n".join(lines).rstrip() + "\nDFTU.PotentialShift false\n"
    return LadderMaterializedInput(
        result.level_id,
        result.dm_tolerance,
        result.h_tolerance_ev,
        result.effective_source_fdf_sha256,
        sha256(text.encode()).hexdigest(),
        text,
        result.effective_criteria,
    )


@dataclass(frozen=True)
class LadderOutputValidation(_Record):
    status: ScfStatus
    reason_codes: tuple[ScfReason, ...]
    output_sha256: str


def validate_ladder_output(
    output: Path, level: ScfLevel, *, reference_fdf: Path | None = None
) -> LadderOutputValidation:
    """Prove six-decimal level echoes and both criteria, including for BARE.

    Positive convergence is required only for the parent reference, never for
    a fixed-Hxc BARE population. The existing reference evidence parser supplies
    this proof; absence of a failure marker alone cannot establish convergence.
    """
    level.require_echo_representable()
    assert level.h_tolerance_ev is not None
    raw = output.read_bytes()
    text = raw.decode("utf-8", errors="replace")
    reasons: list[ScfReason] = []
    for label, value, unit in (
        ("DM tolerance for SCF", level.dm_tolerance, ""),
        ("Hamiltonian tolerance for SCF", level.h_tolerance_ev, r"\s+eV"),
    ):
        tokens = re.findall(
            rf"^\s*redata:\s*{label}\s*=\s*(\d+\.\d{{6}}){unit}\s*$",
            text,
            re.IGNORECASE | re.MULTILINE,
        )
        if len(tokens) != 1 or Decimal(tokens[0]) != Decimal(str(value)):
            reasons.append(ScfReason.SCF_LEVEL_NOT_APPLIED)
    for label in ("DM", "H"):
        tokens = re.findall(
            rf"^\s*redata:\s*Require {label} convergence for SCF\s*=\s*(T|F)\s*$",
            text,
            re.IGNORECASE | re.MULTILINE,
        )
        if len(tokens) != 1 or tokens[0].upper() != "T":
            reasons.append(ScfReason.SCF_CRITERIA_NOT_ACTIVE)
    if reference_fdf is not None:
        evidence = build_reference_state_evidence(reference_fdf, output, ())
        if not evidence.normal_completion_verified or not evidence.scf_converged:
            reasons.append(ScfReason.LEVEL_REFERENCE_NOT_CONVERGED)
    unique = tuple(sorted(set(reasons), key=lambda reason: reason.value))
    return LadderOutputValidation(
        ScfStatus.NOT_ESTABLISHED if unique else ScfStatus.ESTABLISHED, unique, sha256(raw).hexdigest()
    )
