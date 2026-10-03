"""Read-only binding of SCF ladder metadata to authoritative SIESTA inputs.

The existing FDF model supplies projector/site syntax; the audited BARE
profile supplies its mode contract. An explicit screened SCF contract is
required for SCREENED preparation. Output convergence still needs validation
after the user's run and cannot be established from an input file.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import cast

from hubbardflow.domain.scf_ladder_models import ScfLadderError
from hubbardflow.domain.symmetry_reduction import ResponseMode
from hubbardflow.domain.validation import require_fdf_representable_ev, require_int, require_sha256
from hubbardflow.execution.campaign_v2 import resolve_fdf_includes
from hubbardflow.siesta_backend.fdf_labels import canonical_fdf_label

from .fdf_model import _one, parse_effective_fdf
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
        for raw_line in effective.splitlines():
            directive = raw_line.partition("#")[0].split(maxsplit=1)
            if directive and canonical_fdf_label(directive[0]) == "filedminit":
                raise ScfLadderError("File.DM.Init is prohibited; supply DM.UseSaveDM true")
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
