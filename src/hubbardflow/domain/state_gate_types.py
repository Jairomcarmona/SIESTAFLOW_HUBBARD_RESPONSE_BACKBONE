"""Typed input records consumed by the pure I.5 state policy.

The SIESTA adapter preserves printed decimals here without making the domain
depend on backend code or creating a cycle through the public gate API.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum


class StateGateError(ValueError):
    """Invalid or incomplete input to I.5 state consistency evidence."""


@dataclass(frozen=True)
class StateGatePoint:
    """A validated or rejected signed-alpha observation in one column/mode."""

    alpha_ev: float
    node_validated: bool
    state: PointState | None

    def __post_init__(self) -> None:
        if not math.isfinite(self.alpha_ev) or self.alpha_ev == 0:
            raise StateGateError("point alpha_ev must be finite and non-zero")


class BandEvidenceStatus(str, Enum):
    """Whether a point has a parsed band spectrum for the G4 check."""

    AVAILABLE = "AVAILABLE"
    NOT_AVAILABLE = "NOT_AVAILABLE"


@dataclass(frozen=True)
class PrintedBandEnergy:
    """One printed eigenvalue and its distance from that run's Fermi level."""

    kpoint: int
    spin: int
    energy_ev: float
    energy_token: str
    distance_to_fermi_ev: float
    print_quantum_ev: float

    def __post_init__(self) -> None:
        if self.kpoint < 1 or self.spin < 1:
            raise StateGateError("kpoint and spin indices must be positive")
        for name, value in (
            ("energy_ev", self.energy_ev),
            ("distance_to_fermi_ev", self.distance_to_fermi_ev),
            ("print_quantum_ev", self.print_quantum_ev),
        ):
            if not math.isfinite(value):
                raise StateGateError(f"{name} must be finite")
        if self.print_quantum_ev <= 0 or self.distance_to_fermi_ev < 0:
            raise StateGateError("band print quantum must be positive and distance non-negative")
        if not self.energy_token.strip():
            raise StateGateError("printed band energy token must be non-empty")

    def to_mapping(self) -> dict[str, int | float | str]:
        return {
            "kpoint": self.kpoint,
            "spin": self.spin,
            "energy_ev": self.energy_ev,
            "energy_token": self.energy_token,
            "distance_to_fermi_ev": self.distance_to_fermi_ev,
            "print_quantum_ev": self.print_quantum_ev,
        }

    @classmethod
    def from_mapping(cls, value: object) -> PrintedBandEnergy:
        if not isinstance(value, dict):
            raise StateGateError("printed band energy must be an object")
        try:
            return cls(
                kpoint=int(value["kpoint"]),
                spin=int(value["spin"]),
                energy_ev=float(value["energy_ev"]),
                energy_token=str(value["energy_token"]),
                distance_to_fermi_ev=float(value["distance_to_fermi_ev"]),
                print_quantum_ev=float(value["print_quantum_ev"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise StateGateError(f"invalid printed band energy: {exc}") from exc


@dataclass(frozen=True)
class AtomPointState:
    """Printed spin matrices and final Mulliken moment for one correlated atom."""

    atom_index: int
    matrix_up: tuple[tuple[str, ...], ...]
    matrix_down: tuple[tuple[str, ...], ...]
    matrix_print_quantum_e: float
    sz_e: float
    sz_half_width_e: float

    def __post_init__(self) -> None:
        if self.atom_index < 1:
            raise StateGateError("atom_index must be positive")
        if not self.matrix_up or len(self.matrix_up) != len(self.matrix_down):
            raise StateGateError("spin matrices must be non-empty and have equal dimensions")
        size = len(self.matrix_up)
        if any(len(row) != size for row in self.matrix_up + self.matrix_down):
            raise StateGateError("spin matrices must be square")
        if any(not token.strip() for row in self.matrix_up + self.matrix_down for token in row):
            raise StateGateError("matrix decimal strings must be non-empty")
        for name, value in (
            ("matrix_print_quantum_e", self.matrix_print_quantum_e),
            ("sz_e", self.sz_e),
            ("sz_half_width_e", self.sz_half_width_e),
        ):
            if not math.isfinite(value):
                raise StateGateError(f"{name} must be finite")
        if self.matrix_print_quantum_e <= 0 or self.sz_half_width_e <= 0:
            raise StateGateError("print quantum and moment half-width must be positive")

    def to_mapping(self) -> dict[str, object]:
        return {
            "atom_index": self.atom_index,
            "matrix_up": [list(row) for row in self.matrix_up],
            "matrix_down": [list(row) for row in self.matrix_down],
            "matrix_print_quantum_e": self.matrix_print_quantum_e,
            "sz_e": self.sz_e,
            "sz_half_width_e": self.sz_half_width_e,
        }

    @classmethod
    def from_mapping(cls, value: object) -> AtomPointState:
        if not isinstance(value, dict):
            raise StateGateError("atom point state must be an object")
        try:
            return cls(
                atom_index=int(value["atom_index"]),
                matrix_up=tuple(tuple(str(item) for item in row) for row in value["matrix_up"]),
                matrix_down=tuple(tuple(str(item) for item in row) for row in value["matrix_down"]),
                matrix_print_quantum_e=float(value["matrix_print_quantum_e"]),
                sz_e=float(value["sz_e"]),
                sz_half_width_e=float(value["sz_half_width_e"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise StateGateError(f"invalid atom point state: {exc}") from exc


@dataclass(frozen=True)
class PointState:
    """All printed state evidence from one reference or perturbed SIESTA run."""

    atoms: tuple[AtomPointState, ...]
    fermi_energy_ev: float
    fermi_energy_token: str
    fermi_print_quantum_ev: float
    fermi_stdout_energy_ev: float
    fermi_stdout_token: str
    fermi_stdout_half_width_ev: float
    band_evidence_status: BandEvidenceStatus
    band_energies: tuple[PrintedBandEnergy, ...] = ()

    def __post_init__(self) -> None:
        if not self.atoms:
            raise StateGateError("point state requires at least one correlated atom")
        indices = tuple(atom.atom_index for atom in self.atoms)
        if indices != tuple(sorted(set(indices))):
            raise StateGateError("point state atom indices must be unique and sorted")
        for name, value in (
            ("fermi_energy_ev", self.fermi_energy_ev),
            ("fermi_print_quantum_ev", self.fermi_print_quantum_ev),
            ("fermi_stdout_energy_ev", self.fermi_stdout_energy_ev),
            ("fermi_stdout_half_width_ev", self.fermi_stdout_half_width_ev),
        ):
            if not math.isfinite(value):
                raise StateGateError(f"{name} must be finite")
        if self.fermi_print_quantum_ev <= 0 or self.fermi_stdout_half_width_ev <= 0:
            raise StateGateError("Fermi print quantum and stdout half-width must be positive")
        if not self.fermi_energy_token.strip() or not self.fermi_stdout_token.strip():
            raise StateGateError("Fermi energy tokens must be non-empty")
        if self.band_evidence_status is BandEvidenceStatus.AVAILABLE and not self.band_energies:
            raise StateGateError("available band evidence requires eigenvalues")
        if self.band_evidence_status is BandEvidenceStatus.NOT_AVAILABLE and self.band_energies:
            raise StateGateError("unavailable band evidence cannot contain eigenvalues")

    def to_mapping(self) -> dict[str, object]:
        return {
            "atoms": [atom.to_mapping() for atom in self.atoms],
            "fermi_energy_ev": self.fermi_energy_ev,
            "fermi_energy_token": self.fermi_energy_token,
            "fermi_print_quantum_ev": self.fermi_print_quantum_ev,
            "fermi_stdout_energy_ev": self.fermi_stdout_energy_ev,
            "fermi_stdout_token": self.fermi_stdout_token,
            "fermi_stdout_half_width_ev": self.fermi_stdout_half_width_ev,
            "band_evidence_status": self.band_evidence_status.value,
            "band_energies": [energy.to_mapping() for energy in self.band_energies],
        }

    @classmethod
    def from_mapping(cls, value: object) -> PointState:
        if not isinstance(value, dict):
            raise StateGateError("point state must be an object")
        try:
            raw_atoms = value["atoms"]
            raw_bands = value["band_energies"]
            if not isinstance(raw_atoms, list) or not isinstance(raw_bands, list):
                raise TypeError("atoms and band_energies must be arrays")
            return cls(
                atoms=tuple(AtomPointState.from_mapping(atom) for atom in raw_atoms),
                fermi_energy_ev=float(value["fermi_energy_ev"]),
                fermi_energy_token=str(value["fermi_energy_token"]),
                fermi_print_quantum_ev=float(value["fermi_print_quantum_ev"]),
                fermi_stdout_energy_ev=float(value["fermi_stdout_energy_ev"]),
                fermi_stdout_token=str(value["fermi_stdout_token"]),
                fermi_stdout_half_width_ev=float(value["fermi_stdout_half_width_ev"]),
                band_evidence_status=BandEvidenceStatus(value["band_evidence_status"]),
                band_energies=tuple(PrintedBandEnergy.from_mapping(item) for item in raw_bands),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise StateGateError(f"invalid point state: {exc}") from exc
