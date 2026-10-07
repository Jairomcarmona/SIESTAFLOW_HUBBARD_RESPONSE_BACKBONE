"""Response symmetry candidates and the fail-closed F1–F8 evidence classifier.

Spin flip is a global scalar collinear transformation, never an axial-vector
rotation. Geometry and species evidence include ligands. These operations only
propose coverage: they do not authorize omission of a mandatory shadow.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from fractions import Fraction
from itertools import permutations, product
from typing import cast

import numpy as np

from .state_evidence import ReferenceStateEvidence, spectrum_difference
from .subspace_inventory import CorrelatedSubspaceInventory
from .symmetry_geometry import _k_invariant, _lattice_compatible
from .symmetry_groups import close_under_composition, orbits
from .symmetry_operation_models import (
    IDENTITY,
    Commensurability,
    ConditionStatus,
    CoveragePolicy,
    EquivalenceBands,
    Operation,
    Rotation,
    SymmetryModel,
    SymmetryOperationsError,
    SymmetryReason,
    Vector,
)
from .validation import ValidationError, require_finite, require_int, require_nonnegative_finite

__all__ = ["candidate_operations", "classify", "close_under_composition", "orbits"]


@dataclass(frozen=True)
class CandidateOperations:
    operations: tuple[Operation, ...]
    reasons: tuple[SymmetryReason, ...]


def candidate_operations(model: SymmetryModel, geometry_band: EquivalenceBands) -> CandidateOperations:
    """Search internal signed-axis candidates and exact decimal translations.

    Matching uses the upper fractional band, so near symmetries survive as
    candidates and are subsequently labelled AMBIGUOUS. Multiple matches never
    establish a permutation. Species preservation is tested separately in F2.
    """
    atoms = sorted(model.atoms, key=lambda atom: atom.atom_index)
    positions = np.asarray([atom.coordinates_fractional for atom in atoms]) % 1
    anchor = min(range(len(atoms)), key=lambda i: tuple(positions[i]))
    spatial: set[tuple[Rotation, Vector]] = set()
    for order in permutations(range(3)):
        for signs in product((-1, 1), repeat=3):
            rotation = tuple(tuple(signs[i] * int(order[i] == j) for j in range(3)) for i in range(3))
            if _lattice_compatible(rotation, model):
                rotated_anchor = positions[anchor] @ np.asarray(rotation).T
                for position in positions:
                    translation = cast(
                        Vector, tuple(float(value) for value in (position - rotated_anchor) % 1)
                    )
                    spatial.add((rotation, translation))
    reasons: set[SymmetryReason] = set()
    correlated = [atom.atom_index for atom in atoms if atom.correlated]
    operations: list[Operation] = []
    exact_rows: dict[tuple[str, str, str], tuple[Vector, tuple[int, ...]]] = {}
    if all(atom.rational_coordinates is not None for atom in atoms):
        coordinates = {atom.atom_index: atom.rational_coordinates for atom in atoms}
        # Keep every atom index per normalized coordinate so duplicate positions
        # remain ambiguous exactly as in the former full scan.
        exact_coordinate_index: dict[tuple[Fraction, ...], list[int]] = {}
        checked_translations: set[tuple[str, str, str]] = set()
        for atom in atoms:
            coordinate = coordinates[atom.atom_index]
            assert coordinate is not None
            exact_coordinate_index.setdefault(tuple(value % 1 for value in coordinate), []).append(
                atom.atom_index
            )
        for anchor_atom in atoms:
            for target_atom in atoms:
                translation_rational = tuple(
                    (target - source) % 1
                    for source, target in zip(
                        coordinates[anchor_atom.atom_index] or (),
                        coordinates[target_atom.atom_index] or (),
                        strict=True,
                    )
                )
                rational_key = cast(tuple[str, str, str], tuple(str(value) for value in translation_rational))
                # Many atom pairs generate the same exact translation. Its map
                # depends only on that vector, so evaluate each vector once.
                if rational_key in checked_translations:
                    continue
                checked_translations.add(rational_key)
                mapping: list[int] = []
                for source_atom in atoms:
                    translated = tuple(
                        (value + delta) % 1
                        for value, delta in zip(
                            coordinates[source_atom.atom_index] or (), translation_rational, strict=True
                        )
                    )
                    matches = exact_coordinate_index.get(translated, [])
                    if len(matches) != 1:
                        mapping = []
                        break
                    mapping.append(matches[0])
                if not mapping or len(set(mapping)) != len(atoms):
                    continue
                atom_map = dict(zip((atom.atom_index for atom in atoms), mapping, strict=True))
                if {atom_map[index] for index in correlated} != set(correlated):
                    continue
                exact_rows[rational_key] = (
                    cast(Vector, tuple(float(value) for value in translation_rational)),
                    tuple(mapping),
                )
    exact_mappings = {mapping for _, mapping in exact_rows.values()}
    for rotation, translation in sorted(spatial):
        mapped = positions @ np.asarray(rotation).T + translation
        float_mapping: list[int] = []
        for point in mapped:
            delta = point - positions
            residuals = np.max(np.abs(delta - np.rint(delta)), axis=1)
            matches = [i for i, residual in enumerate(residuals) if residual <= geometry_band.tau_neq]
            if len(matches) != 1:
                if len(matches) > 1:
                    reasons.add(SymmetryReason.GEOMETRIC_MAPPING_AMBIGUOUS)
                break
            float_mapping.append(atoms[matches[0]].atom_index)
        if len(float_mapping) != len(atoms) or len(set(float_mapping)) != len(atoms):
            continue
        if rotation == IDENTITY and tuple(float_mapping) in exact_mappings:
            continue
        atom_map = dict(zip((atom.atom_index for atom in atoms), float_mapping, strict=True))
        if {atom_map[i] for i in correlated} != set(correlated):
            continue
        corr_map = tuple(correlated.index(atom_map[i]) for i in correlated)
        operations.extend(
            Operation(rotation, translation, eps, tuple(float_mapping), corr_map, model) for eps in (1, -1)
        )
    for rational, (translation, exact_mapping) in sorted(exact_rows.items(), key=lambda row: row[1][0]):
        atom_map = dict(zip((atom.atom_index for atom in atoms), exact_mapping, strict=True))
        corr_map = tuple(correlated.index(atom_map[index]) for index in correlated)
        operations.extend(
            Operation(IDENTITY, translation, eps, exact_mapping, corr_map, model, rational) for eps in (1, -1)
        )
    return CandidateOperations(tuple(operations), tuple(sorted(reasons, key=lambda reason: reason.value)))


@dataclass(frozen=True)
class ConditionResult:
    condition: str
    status: ConditionStatus
    measured_value: float | None
    tau_eq: float | None
    tau_neq: float | None
    pair_measurements: tuple[tuple[int, int, float, float, float], ...] = ()
    ambiguous_pairs: tuple[tuple[int, int], ...] = ()


@dataclass(frozen=True)
class OperationClassification:
    operation: Operation
    conditions: tuple[ConditionResult, ...]
    commensurability: Commensurability
    reasons: tuple[SymmetryReason, ...]

    @property
    def accepted(self) -> bool:
        """Eligible candidate only; this never constitutes a PROVEN coverage class.

        F7 spectra alone cannot see changed eigenvectors with equal eigenvalues.
        Mandatory response shadows remain necessary to confirm reconstruction.
        """
        return not self.reasons and all(
            item.status in (ConditionStatus.EQUAL, ConditionStatus.NOT_APPLICABLE)
            or (item.condition == "F8" and self.operation.rotation_int == IDENTITY)
            for item in self.conditions
        )

    def to_mapping(self) -> dict[str, object]:
        return {
            "operation": self.operation.to_mapping(),
            "conditions": [{**asdict(item), "status": item.status.value} for item in self.conditions],
            "commensurability": self.commensurability.value,
            "reasons": [reason.value for reason in self.reasons],
            "accepted": self.accepted,
        }


def _record_key(record: object) -> tuple[object, ...]:
    return tuple(
        getattr(record, key, None)
        for key in ("n", "l", "rc_bohr", "omega", "lambda_values", "u_ref_ev", "j_ref_ev")
    )


def _classify(
    op: Operation,
    inventory: CorrelatedSubspaceInventory,
    state: ReferenceStateEvidence,
    policy: CoveragePolicy,
) -> OperationClassification:
    """Test F1–F8, preserving measurements and the declared pairwise bands."""
    atoms = sorted(op.model.atoms, key=lambda atom: atom.atom_index)
    atom_by_index = {atom.atom_index: atom for atom in atoms}
    mapping = dict(zip((atom.atom_index for atom in atoms), op.atom_permutation, strict=True))
    ordered = sorted(inventory.subspaces, key=lambda item: item.atom_index)
    if len({item.atom_index for item in ordered}) != len(ordered):
        raise SymmetryOperationsError("duplicate correlated atom records are not supported")
    if len({item.site_id for item in ordered}) != len(ordered):
        raise SymmetryOperationsError("duplicate correlated site identifiers")
    if {item.atom_index for item in ordered} != {atom.atom_index for atom in atoms if atom.correlated}:
        raise SymmetryOperationsError("inventory must cover exactly all model-correlated atoms")
    if len({item.atom_index for item in state.moments_by_atom}) != len(state.moments_by_atom):
        raise SymmetryOperationsError("duplicate moment records")
    if len({item.atom_index for item in state.occupation_spectra_by_subspace}) != len(
        state.occupation_spectra_by_subspace
    ):
        raise SymmetryOperationsError("duplicate occupation records")
    reasons = []
    if any(item.identity_digest != atom_by_index[item.atom_index].identity_digest for item in ordered):
        reasons.append(SymmetryReason.EVIDENCE_BINDING_MISMATCH)
    if not state.normal_completion_verified or not state.scf_converged:
        reasons.append(SymmetryReason.REFERENCE_NOT_ADMISSIBLE)
    if op.eps == -1 and not policy.allow_spin_flip:
        reasons.append(SymmetryReason.SPIN_FLIP_DISABLED)
    if op.rotation_int != IDENTITY and not policy.allow_rotations:
        reasons.append(SymmetryReason.ROTATIONS_DISABLED)
    results = []

    def measured(name: str, value: float | None, bands: EquivalenceBands) -> None:
        status = ConditionStatus.AMBIGUOUS if value is None else bands.classify(value)
        results.append(ConditionResult(name, status, value, bands.tau_eq, bands.tau_neq))

    def exact(name: str, equal: bool | None, applicable: bool = True) -> None:
        status = (
            ConditionStatus.NOT_APPLICABLE
            if not applicable
            else ConditionStatus.AMBIGUOUS
            if equal is None
            else ConditionStatus.EQUAL
            if equal
            else ConditionStatus.DIFFERENT
        )
        results.append(ConditionResult(name, status, None if equal is None else float(not equal), None, None))

    residual = 0.0
    for atom in atoms:
        delta = (
            np.asarray(atom.coordinates_fractional) @ np.asarray(op.rotation_int).T
            + op.translation_frac
            - np.asarray(atom_by_index[mapping[atom.atom_index]].coordinates_fractional)
        )
        residual = max(residual, float(np.max(np.abs(delta - np.rint(delta)))))
    if op.rational_mapping_exact:
        residual = 0.0
    measured("F1", residual, policy.geometry)
    # Unimodularity alone does not make an integer matrix a spatial isometry.
    # Recheck candidates received directly or deserialized, independently of
    # the geometric search (a shear can leave a special atom position fixed).
    if not _lattice_compatible(op.rotation_int, op.model):
        results[-1] = ConditionResult(
            "F1", ConditionStatus.DIFFERENT, residual, policy.geometry.tau_eq, policy.geometry.tau_neq
        )
        reasons.append(SymmetryReason.LATTICE_INCOMPATIBLE)
    identities = [
        (atom.identity_digest, atom_by_index[mapping[atom.atom_index]].identity_digest) for atom in atoms
    ]
    exact(
        "F2",
        None if any(a is None or b is None for a, b in identities) else all(a == b for a, b in identities),
    )
    valid_mapping = len(op.correlated_permutation) == len(ordered) and all(
        mapping[source.atom_index] == ordered[op.correlated_permutation[i]].atom_index
        for i, source in enumerate(ordered)
    )
    exact(
        "F3",
        valid_mapping
        and all(
            _record_key(source.dftu_record) == _record_key(ordered[op.correlated_permutation[i]].dftu_record)
            and all(value is not None for value in _record_key(source.dftu_record))
            for i, source in enumerate(ordered)
        ),
    )
    exact(
        "F4",
        op.model.dftu_method == 2 and _k_invariant(op.rotation_int, state.k_mesh),
        op.rotation_int != IDENTITY,
    )
    moments = {item.atom_index: item for item in state.moments_by_atom}
    magnetic = []
    for atom in atoms:
        a, b = moments.get(atom.atom_index), moments.get(mapping[atom.atom_index])
        if a is None or b is None:
            break
        for value in (a.moment_e, b.moment_e):
            require_finite(value, "moment_e")
        for value in (a.half_width_e, b.half_width_e):
            require_nonnegative_finite(value, "moment_half_width_e")
        width = max(a.half_width_e, b.half_width_e, policy.magnetic_half_width_floor_e)
        magnetic.append(
            (
                atom.atom_index,
                mapping[atom.atom_index],
                abs(b.moment_e - op.eps * a.moment_e),
                width * policy.magnetic_print_multipliers.tau_eq,
                width * policy.magnetic_print_multipliers.tau_neq,
            )
        )

    def pair_result(
        name: str,
        pairs: list[tuple[int, int, float, float, float]],
        count: int,
        ambiguous_pairs: tuple[tuple[int, int], ...] = (),
    ) -> None:
        statuses = [
            EquivalenceBands(eq, neq).classify(value)
            if neq
            else (ConditionStatus.EQUAL if value == 0 else ConditionStatus.DIFFERENT)
            for _, _, value, eq, neq in pairs
        ]
        status = (
            ConditionStatus.AMBIGUOUS
            if len(pairs) != count
            else ConditionStatus.DIFFERENT
            if ConditionStatus.DIFFERENT in statuses
            else ConditionStatus.AMBIGUOUS
            if ConditionStatus.AMBIGUOUS in statuses
            else ConditionStatus.EQUAL
        )
        results.append(
            ConditionResult(
                name,
                status,
                max((pair[2] for pair in pairs), default=None),
                None,
                None,
                tuple(pairs),
                ambiguous_pairs,
            )
        )

    pair_result("F5", magnetic, len(atoms))
    exact(
        "F6",
        op.model.collinear
        and not op.model.spin_orbit
        and op.model.spin_independent_perturbation
        and op.model.scalar_spin_summed_observable,
        op.eps == -1,
    )
    if not op.model.collinear or op.model.spin_orbit:
        reasons.append(SymmetryReason.REFERENCE_NOT_ADMISSIBLE)
    spectra = {item.atom_index: item for item in state.occupation_spectra_by_subspace}
    spectral = []
    heterogeneous_pairs = []
    for subspace in ordered:
        spec_a, spec_b = spectra.get(subspace.atom_index), spectra.get(mapping[subspace.atom_index])
        if spec_a is None or spec_b is None:
            break
        for item in (spec_a, spec_b):
            channels = [spectrum.spin for spectrum in item.spectra]
            if len(set(channels)) != len(channels) or set(channels) not in ({"up"}, {"up", "down"}):
                raise SymmetryOperationsError("occupation evidence requires unique up or up/down channels")
            for spectrum in item.spectra:
                size = 2 * subspace.dftu_record.l + 1
                if (
                    len(spectrum.eigenvalues_e) != size
                    or len(spectrum.matrix_half_widths_e) != size
                    or any(len(row) != size for row in spectrum.matrix_half_widths_e)
                ):
                    raise SymmetryOperationsError(
                        "occupation matrix dimensions must match the complete l shell"
                    )
        difference = spectrum_difference(spec_a, spec_b, op.eps == -1)
        widths = [
            value
            for item in (spec_a, spec_b)
            for spectrum in item.spectra
            for row in spectrum.matrix_half_widths_e
            for value in row
        ]
        for value in widths:
            require_nonnegative_finite(value, "matrix_half_width_e")
        for item in (spec_a, spec_b):
            for spectrum in item.spectra:
                for value in spectrum.eigenvalues_e:
                    require_finite(value, "eigenvalue_e")
        if difference is None or not widths:
            break
        # The declared profile has no aggregation rule for heterogeneous entry
        # radii in a spectral comparison. Ambiguity costs compute and never
        # creates an equivalence; uniform radii need no aggregation assumption.
        if len(set(widths)) != 1:
            heterogeneous_pairs.append((subspace.atom_index, mapping[subspace.atom_index]))
            reasons.append(SymmetryReason.SPECTRAL_PRECISION_HETEROGENEOUS)
            continue
        width = widths[0]
        spectral.append(
            (
                subspace.atom_index,
                mapping[subspace.atom_index],
                difference,
                width * policy.spectral_print_multipliers.tau_eq,
                width * policy.spectral_print_multipliers.tau_neq,
            )
        )
    pair_result("F7", spectral, len(ordered), tuple(heterogeneous_pairs))
    mesh = state.mesh_divisions
    commensurability = Commensurability.NOT_ESTABLISHED
    if mesh is not None:
        for value in mesh:
            require_int(value, "mesh division", minimum=1)
        commensurability = (
            Commensurability.COMMENSURATE
            if all(
                (Fraction(value) * n).denominator == 1
                for value, n in zip(
                    op.translation_rational
                    if op.translation_rational is not None
                    else tuple(str(t) for t in op.translation_frac),
                    mesh,
                    strict=True,
                )
            )
            else Commensurability.INCOMMENSURATE
        )
    # F8 records the numerical class; incommensurability does not exclude a
    # translation candidate. Missing effective mesh evidence remains recorded
    # as ambiguous and is likewise not an eligibility gate for translations.
    exact("F8", None if mesh is None else True)
    return OperationClassification(
        op, tuple(results), commensurability, tuple(sorted(set(reasons), key=lambda x: x.value))
    )


def classify(
    op: Operation,
    inventory: CorrelatedSubspaceInventory,
    state: ReferenceStateEvidence,
    policy: CoveragePolicy,
) -> OperationClassification:
    """Classify a candidate, rejecting invalid numeric evidence with local errors."""
    try:
        operation = replace(op, model=replace(op.model, mesh_divisions=state.mesh_divisions))
        return _classify(operation, inventory, state, policy)
    except ValidationError as exc:
        raise SymmetryOperationsError(str(exc)) from exc
