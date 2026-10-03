"""Frozen response-operation contracts and the declared coverage-policy-v1 profile."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from enum import Enum
from fractions import Fraction
from hashlib import sha256
from typing import Literal, Protocol, cast

import numpy as np

from .validation import (
    ValidationError,
    require_finite,
    require_int,
    require_nonnegative_finite,
    require_positive_finite,
    require_sha256,
)

Rotation = tuple[tuple[int, ...], ...]
Vector = tuple[float, float, float]
IDENTITY: Rotation = ((1, 0, 0), (0, 1, 0), (0, 0, 1))


class SymmetryOperationsError(ValueError):
    """Invalid symmetry inputs cannot establish response equivalence."""


class ConditionStatus(str, Enum):
    EQUAL = "EQUAL"
    DIFFERENT = "DIFFERENT"
    AMBIGUOUS = "AMBIGUOUS"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ExactnessClass(str, Enum):
    EXACT_TRANSLATION = "EXACT_TRANSLATION"
    EXACT_IN_CONTINUUM_ONLY = "EXACT_IN_CONTINUUM_ONLY"


class Commensurability(str, Enum):
    COMMENSURATE = "COMMENSURATE"
    INCOMMENSURATE = "INCOMMENSURATE"
    NOT_ESTABLISHED = "NOT_ESTABLISHED"


class SymmetryReason(str, Enum):
    SPGLIB_NOT_AVAILABLE = "SPGLIB_NOT_AVAILABLE"
    SPGLIB_SEARCH_FAILED = "SPGLIB_SEARCH_FAILED"
    GEOMETRIC_MAPPING_AMBIGUOUS = "GEOMETRIC_MAPPING_AMBIGUOUS"
    GROUP_NOT_CLOSED = "GROUP_NOT_CLOSED"
    SPIN_FLIP_DISABLED = "SPIN_FLIP_DISABLED"
    ROTATIONS_DISABLED = "ROTATIONS_DISABLED"
    REFERENCE_NOT_ADMISSIBLE = "REFERENCE_NOT_ADMISSIBLE"
    EVIDENCE_BINDING_MISMATCH = "EVIDENCE_BINDING_MISMATCH"
    LATTICE_INCOMPATIBLE = "LATTICE_INCOMPATIBLE"
    SPECTRAL_PRECISION_HETEROGENEOUS = "SPECTRAL_PRECISION_HETEROGENEOUS"


class ShadowPolicy(str, Enum):
    MANDATORY = "MANDATORY"


def _digest(payload: Mapping[str, object]) -> str:
    return sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


@dataclass(frozen=True)
class EquivalenceBands:
    tau_eq: float
    tau_neq: float

    def __post_init__(self) -> None:
        try:
            require_nonnegative_finite(self.tau_eq, "tau_eq")
            require_positive_finite(self.tau_neq, "tau_neq")
        except ValidationError as exc:
            raise SymmetryOperationsError(str(exc)) from exc
        if self.tau_eq >= self.tau_neq:
            raise SymmetryOperationsError("tau_eq must be less than tau_neq")

    def to_mapping(self) -> dict[str, object]:
        return {"tau_eq": self.tau_eq, "tau_neq": self.tau_neq}

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> EquivalenceBands:
        return cls(require_finite(value["tau_eq"], "tau_eq"), require_finite(value["tau_neq"], "tau_neq"))

    def classify(self, value: float) -> ConditionStatus:
        require_nonnegative_finite(value, "difference")
        if value <= self.tau_eq:
            return ConditionStatus.EQUAL
        return ConditionStatus.DIFFERENT if value >= self.tau_neq else ConditionStatus.AMBIGUOUS


@dataclass(frozen=True)
class CoveragePolicy:
    version: str
    geometry: EquivalenceBands
    magnetic_print_multipliers: EquivalenceBands
    spectral_print_multipliers: EquivalenceBands
    magnetic_half_width_floor_e: float
    allow_spin_flip: bool
    allow_rotations: bool
    shadow: ShadowPolicy

    def __post_init__(self) -> None:
        if not self.version or not isinstance(self.shadow, ShadowPolicy):
            raise SymmetryOperationsError("policy version and explicit shadow policy are required")
        if type(self.allow_spin_flip) is not bool or type(self.allow_rotations) is not bool:
            raise SymmetryOperationsError("strategy flags must be booleans")
        try:
            require_positive_finite(self.magnetic_half_width_floor_e, "magnetic_half_width_floor_e")
        except ValidationError as exc:
            raise SymmetryOperationsError(str(exc)) from exc

    def to_mapping(self) -> dict[str, object]:
        return {
            "version": self.version,
            "geometry": self.geometry.to_mapping(),
            "magnetic_print_multipliers": self.magnetic_print_multipliers.to_mapping(),
            "spectral_print_multipliers": self.spectral_print_multipliers.to_mapping(),
            "magnetic_half_width_floor_e": self.magnetic_half_width_floor_e,
            "allow_spin_flip": self.allow_spin_flip,
            "allow_rotations": self.allow_rotations,
            "shadow": self.shadow.value,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> CoveragePolicy:
        if not isinstance(value["version"], str) or not isinstance(value["shadow"], str):
            raise SymmetryOperationsError("version and shadow must be strings")
        bands = []
        for name in ("geometry", "magnetic_print_multipliers", "spectral_print_multipliers"):
            entry = value[name]
            if not isinstance(entry, Mapping):
                raise SymmetryOperationsError(f"{name} must be a mapping")
            bands.append(EquivalenceBands.from_mapping(entry))
        if type(value["allow_spin_flip"]) is not bool or type(value["allow_rotations"]) is not bool:
            raise SymmetryOperationsError("strategy flags must be booleans")
        return cls(
            value["version"],
            bands[0],
            bands[1],
            bands[2],
            require_finite(value["magnetic_half_width_floor_e"], "magnetic_half_width_floor_e"),
            value["allow_spin_flip"],
            value["allow_rotations"],
            ShadowPolicy(value["shadow"]),
        )

    @property
    def digest(self) -> str:
        return _digest(self.to_mapping())


def coverage_policy_v1() -> CoveragePolicy:
    """The declared TASK 9 profile; every value and flag enters its digest."""
    return CoveragePolicy(
        "coverage-policy-v1",
        EquivalenceBands(1e-5, 1e-3),
        EquivalenceBands(10, 1000),
        EquivalenceBands(10, 1000),
        5e-7,
        False,
        False,
        ShadowPolicy.MANDATORY,
    )


@dataclass(frozen=True)
class SymmetryAtom:
    atom_index: int
    coordinates_fractional: Vector
    identity_digest: str | None
    correlated: bool
    fractional_coordinates_rational: tuple[str, str, str] | None = None
    rational_coordinates_available: bool = True

    def __post_init__(self) -> None:
        try:
            require_int(self.atom_index, "atom_index", minimum=0)
            if len(self.coordinates_fractional) != 3:
                raise SymmetryOperationsError("fractional coordinates require three components")
            for coordinate in self.coordinates_fractional:
                require_finite(coordinate, "fractional coordinate")
            if type(self.rational_coordinates_available) is not bool:
                raise SymmetryOperationsError("rational coordinate availability must be boolean")
            if self.fractional_coordinates_rational is not None:
                if len(self.fractional_coordinates_rational) != 3:
                    raise SymmetryOperationsError("rational fractional coordinates require three components")
                for rational_coordinate in self.fractional_coordinates_rational:
                    Fraction(rational_coordinate)
            if self.identity_digest is not None:
                require_sha256(self.identity_digest, "identity_digest")
        except ValidationError as exc:
            raise SymmetryOperationsError(str(exc)) from exc

    @property
    def rational_coordinates(self) -> tuple[Fraction, Fraction, Fraction] | None:
        if not self.rational_coordinates_available:
            return None
        if self.fractional_coordinates_rational is None:
            values = tuple(Fraction(str(value)) for value in self.coordinates_fractional)
        else:
            values = tuple(Fraction(value) for value in self.fractional_coordinates_rational)
            if tuple(float(value) for value in values) != self.coordinates_fractional:
                return None
        return cast(tuple[Fraction, Fraction, Fraction], values)


@dataclass(frozen=True)
class SymmetryModel:
    """Pure geometry snapshot, including species evidence for unobserved ligands."""

    effective_fdf_sha256: str
    lattice_vectors_angstrom: tuple[tuple[float, ...], ...]
    atoms: tuple[SymmetryAtom, ...]
    dftu_method: int | None
    collinear: bool
    spin_orbit: bool
    spin_independent_perturbation: bool
    scalar_spin_summed_observable: bool
    mesh_divisions: tuple[int, int, int] | None = None

    def __post_init__(self) -> None:
        try:
            require_sha256(self.effective_fdf_sha256, "effective_fdf_sha256")
            if self.mesh_divisions is not None:
                if len(self.mesh_divisions) != 3:
                    raise SymmetryOperationsError("mesh_divisions must have three positive values")
                for mesh_division in self.mesh_divisions:
                    require_int(mesh_division, "mesh division", minimum=1)
            for row in self.lattice_vectors_angstrom:
                for lattice_component in row:
                    require_finite(lattice_component, "lattice vector")
        except ValidationError as exc:
            raise SymmetryOperationsError(str(exc)) from exc
        lattice = np.asarray(self.lattice_vectors_angstrom)
        if lattice.shape != (3, 3) or np.linalg.det(lattice) == 0:
            raise SymmetryOperationsError("lattice must be an invertible 3 by 3 matrix")
        if not self.atoms or len({atom.atom_index for atom in self.atoms}) != len(self.atoms):
            raise SymmetryOperationsError("atoms must be nonempty with unique atom_index values")
        object.__setattr__(self, "atoms", tuple(sorted(self.atoms, key=lambda atom: atom.atom_index)))
        if any(
            type(flag) is not bool
            for flag in (
                self.collinear,
                self.spin_orbit,
                self.spin_independent_perturbation,
                self.scalar_spin_summed_observable,
            )
        ):
            raise SymmetryOperationsError("model spin and observable flags must be booleans")


class _Atom(Protocol):
    @property
    def atom_index(self) -> int: ...
    @property
    def coordinates_fractional(self) -> Vector: ...
    @property
    def species_label(self) -> str: ...
    @property
    def coordinates_fractional_rational(self) -> tuple[str, str, str] | None: ...


class _Record(Protocol):
    @property
    def label(self) -> str: ...


class _Model(Protocol):
    @property
    def effective_fdf_sha256(self) -> str: ...
    @property
    def lattice_vectors_angstrom(self) -> tuple[tuple[float, float, float], ...]: ...
    @property
    def atoms(self) -> tuple[_Atom, ...]: ...
    @property
    def dftu_records(self) -> tuple[_Record, ...]: ...
    @property
    def dftu_method(self) -> int | None: ...
    @property
    def dftu_potential_shift(self) -> bool | None: ...
    @property
    def noncollinear(self) -> bool: ...
    @property
    def spin_orbit(self) -> bool: ...


class _Identity(Protocol):
    @property
    def digest(self) -> str: ...
    @property
    def status(self) -> object: ...


def bind_symmetry_model(model: _Model, identities: Mapping[str, _Identity]) -> SymmetryModel:
    """Bind already parsed FDF and semantic identities without file access.

    The current backend observable is explicitly the spin-summed shell trace;
    PotentialShift identifies its spin-independent perturbation contract.
    """
    labels = {record.label for record in model.dftu_records}
    atoms = []
    for atom in sorted(model.atoms, key=lambda entry: entry.atom_index):
        identity = identities.get(atom.species_label)
        digest = (
            identity.digest
            if identity is not None and getattr(identity.status, "value", identity.status) == "ESTABLISHED"
            else None
        )
        atoms.append(
            SymmetryAtom(
                atom.atom_index,
                cast(Vector, tuple(float(Fraction(value)) for value in atom.coordinates_fractional_rational))
                if atom.coordinates_fractional_rational is not None
                else atom.coordinates_fractional,
                digest,
                atom.species_label in labels,
                atom.coordinates_fractional_rational,
                atom.coordinates_fractional_rational is not None,
            )
        )
    return SymmetryModel(
        model.effective_fdf_sha256,
        model.lattice_vectors_angstrom,
        tuple(atoms),
        model.dftu_method,
        not model.noncollinear,
        model.spin_orbit,
        model.dftu_potential_shift is True,
        True,
    )


@dataclass(frozen=True)
class Operation:
    rotation_int: Rotation
    translation_frac: Vector
    eps: Literal[1, -1]
    atom_permutation: tuple[int, ...]
    correlated_permutation: tuple[int, ...]
    model: SymmetryModel
    translation_rational: tuple[str, str, str] | None = None

    def __post_init__(self) -> None:
        if self.eps not in (1, -1) or type(self.eps) is not int:
            raise SymmetryOperationsError("eps must be +1 or -1 (one global spin flip)")
        if len(self.rotation_int) != 3 or any(len(row) != 3 for row in self.rotation_int):
            raise SymmetryOperationsError("rotation_int must have shape 3 by 3")
        try:
            for row in self.rotation_int:
                for value in row:
                    require_int(value, "rotation entry", minimum=-abs(value))
            if len(self.translation_frac) != 3:
                raise SymmetryOperationsError("translation_frac must have three components")
            for component in self.translation_frac:
                require_finite(component, "translation_frac")
            if self.translation_rational is not None:
                if len(self.translation_rational) != 3:
                    raise SymmetryOperationsError("rational translation requires three components")
                for value in self.translation_rational:
                    Fraction(value)
        except (TypeError, ValidationError) as exc:
            raise SymmetryOperationsError(str(exc)) from exc
        r = self.rotation_int
        determinant = (
            r[0][0] * (r[1][1] * r[2][2] - r[1][2] * r[2][1])
            - r[0][1] * (r[1][0] * r[2][2] - r[1][2] * r[2][0])
            + r[0][2] * (r[1][0] * r[2][1] - r[1][1] * r[2][0])
        )
        if determinant not in (-1, 1):
            raise SymmetryOperationsError("rotation_int must be an integer unimodular matrix")
        indices = sorted(atom.atom_index for atom in self.model.atoms)
        try:
            for index in (*self.atom_permutation, *self.correlated_permutation):
                require_int(index, "permutation index", minimum=0)
        except ValidationError as exc:
            raise SymmetryOperationsError(str(exc)) from exc
        if sorted(self.atom_permutation) != indices:
            raise SymmetryOperationsError("atom_permutation must be a bijection of all atom indices")
        if sorted(self.correlated_permutation) != list(range(len(self.correlated_permutation))):
            raise SymmetryOperationsError("correlated_permutation must be a bijection")

    @property
    def rational_mapping_exact(self) -> bool:
        if self.rotation_int != IDENTITY or any(
            atom.rational_coordinates is None for atom in self.model.atoms
        ):
            return False
        atoms = {atom.atom_index: atom for atom in self.model.atoms}
        translation = tuple(
            Fraction(value)
            for value in (
                self.translation_rational
                if self.translation_rational is not None
                else tuple(str(value) for value in self.translation_frac)
            )
        )
        for source, target_index in zip(self.model.atoms, self.atom_permutation, strict=True):
            source_coordinates = source.rational_coordinates
            target = atoms[target_index].rational_coordinates
            if source_coordinates is None or target is None:
                return False
            translated = tuple((source_coordinates[axis] + translation[axis]) % 1 for axis in range(3))
            if tuple(value % 1 for value in target) != translated:
                return False
        return True

    @property
    def exactness_class(self) -> ExactnessClass:
        mesh = self.model.mesh_divisions
        if self.eps != 1 or mesh is None or not self.rational_mapping_exact:
            return ExactnessClass.EXACT_IN_CONTINUUM_ONLY
        translation = tuple(
            Fraction(value)
            for value in (
                self.translation_rational
                if self.translation_rational is not None
                else tuple(str(value) for value in self.translation_frac)
            )
        )
        for component, size in zip(translation, mesh, strict=True):
            if (component * size).denominator != 1:
                return ExactnessClass.EXACT_IN_CONTINUUM_ONLY
        return ExactnessClass.EXACT_TRANSLATION

    def to_mapping(self) -> dict[str, object]:
        return {**asdict(self), "exactness_class": self.exactness_class.value}

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> Operation:
        # Explicit reconstruction keeps JSON arrays from escaping as mutable fields.
        model = cast(Mapping[str, object], value["model"])
        atoms = tuple(
            SymmetryAtom(
                cast(int, item["atom_index"]),
                cast(Vector, tuple(cast(Sequence[float], item["coordinates_fractional"]))),
                cast(str | None, item["identity_digest"]),
                cast(bool, item["correlated"]),
                None
                if item.get("fractional_coordinates_rational") is None
                else cast(
                    tuple[str, str, str],
                    tuple(cast(Sequence[str], item["fractional_coordinates_rational"])),
                ),
                cast(bool, item.get("rational_coordinates_available", True)),
            )
            for item in cast(Sequence[Mapping[str, object]], model["atoms"])
        )
        snapshot = SymmetryModel(
            cast(str, model["effective_fdf_sha256"]),
            tuple(tuple(row) for row in cast(Sequence[Sequence[float]], model["lattice_vectors_angstrom"])),
            atoms,
            cast(int | None, model["dftu_method"]),
            cast(bool, model["collinear"]),
            cast(bool, model["spin_orbit"]),
            cast(bool, model["spin_independent_perturbation"]),
            cast(bool, model["scalar_spin_summed_observable"]),
            None
            if model.get("mesh_divisions") is None
            else cast(tuple[int, int, int], tuple(cast(Sequence[int], model["mesh_divisions"]))),
        )
        return cls(
            tuple(tuple(row) for row in cast(Sequence[Sequence[int]], value["rotation_int"])),
            cast(Vector, tuple(cast(Sequence[float], value["translation_frac"]))),
            cast(Literal[1, -1], value["eps"]),
            tuple(cast(Sequence[int], value["atom_permutation"])),
            tuple(cast(Sequence[int], value["correlated_permutation"])),
            snapshot,
            None
            if value.get("translation_rational") is None
            else cast(tuple[str, str, str], tuple(cast(Sequence[str], value["translation_rational"]))),
        )
