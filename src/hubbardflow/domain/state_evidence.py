"""Pure records and comparisons for a reference state's magnetic and orbital evidence.

Occupation spectra are compared only after the backend has tied printed matrices
to a completed reference output. A missing spectrum stays explicit so F7 cannot
turn absent data into an equivalence claim.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class CorrelatedSubspaceLike(Protocol):
    """Minimum inventory fields needed to bind state evidence to a site."""

    @property
    def site_id(self) -> str: ...

    @property
    def atom_index(self) -> int: ...


class EvidenceStatus(str, Enum):
    ADMISSIBLE = "ADMISSIBLE"
    REFERENCE_NOT_ADMISSIBLE = "REFERENCE_NOT_ADMISSIBLE"


class OccupationSpectraStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    NOT_AVAILABLE = "NOT_AVAILABLE"


class StateEvidenceReason(str, Enum):
    NORMAL_COMPLETION_MISSING = "NORMAL_COMPLETION_MISSING"
    SCF_NOT_CONVERGED = "SCF_NOT_CONVERGED"
    MOMENTS_MISSING = "MOMENTS_MISSING"
    INIT_MESH_MISSING = "INIT_MESH_MISSING"
    K_MESH_MISSING = "K_MESH_MISSING"
    OCCUPATION_SPECTRA_NOT_AVAILABLE = "OCCUPATION_SPECTRA_NOT_AVAILABLE"
    OCCUPATION_SPECTRA_INCOMPLETE = "OCCUPATION_SPECTRA_INCOMPLETE"


@dataclass(frozen=True)
class MomentEvidence:
    atom_index: int
    moment_e: float
    half_width_e: float


@dataclass(frozen=True)
class OccupationSpectrum:
    """Sorted eigenvalues and per-entry print radii for one local spin matrix."""

    spin: str
    eigenvalues_e: tuple[float, ...]
    matrix_half_widths_e: tuple[tuple[float, ...], ...]


@dataclass(frozen=True)
class SubspaceOccupationEvidence:
    site_id: str
    atom_index: int
    spectra: tuple[OccupationSpectrum, ...]


@dataclass(frozen=True)
class ReferenceStateEvidence:
    input_fdf_sha256: str
    siesta_output_sha256: str
    normal_completion_verified: bool
    scf_converged: bool
    moments_by_atom: tuple[MomentEvidence, ...]
    mesh_divisions: tuple[int, int, int] | None
    k_mesh: tuple[tuple[int, int, int, float], ...] | None
    occupation_spectra_status: OccupationSpectraStatus
    occupation_spectra_by_subspace: tuple[SubspaceOccupationEvidence, ...]
    status: EvidenceStatus
    reason_codes: tuple[StateEvidenceReason, ...]


def spectrum_difference(
    a: SubspaceOccupationEvidence,
    b: SubspaceOccupationEvidence,
    flip: bool,
) -> float | None:
    """Return the largest absolute spectral difference, or ``None`` if absent.

    A global spin flip swaps the up/down spectra. Spin channels must have the
    same names and dimensions after that swap; incomplete evidence is not equal.
    """
    first = {spectrum.spin: spectrum.eigenvalues_e for spectrum in a.spectra}
    second = {spectrum.spin: spectrum.eigenvalues_e for spectrum in b.spectra}
    if not first or not second:
        return None
    if flip:
        second = {
            "up" if spin == "down" else "down" if spin == "up" else spin: values
            for spin, values in second.items()
        }
    if set(first) != set(second):
        return None
    differences: list[float] = []
    for spin in sorted(first):
        left, right = first[spin], second[spin]
        if len(left) != len(right):
            return None
        differences.extend(abs(x - y) for x, y in zip(left, right, strict=True))
    return max(differences, default=0.0)
