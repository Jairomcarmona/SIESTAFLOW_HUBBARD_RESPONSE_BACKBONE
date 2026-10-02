"""F1–F8 synthetic counterexamples, permutation properties and archived geometry."""

from __future__ import annotations

import ast
import json
from collections.abc import Callable
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from typing import Protocol, cast

import numpy as np
import numpy.typing as npt
import pytest
from hypothesis import given
from hypothesis import strategies as st

from hubbardflow.domain.state_evidence import (
    EvidenceStatus,
    MomentEvidence,
    OccupationSpectraStatus,
    OccupationSpectrum,
    ReferenceStateEvidence,
    SubspaceOccupationEvidence,
)
from hubbardflow.domain.subspace_inventory import (
    CorrelatedSubspace,
    CorrelatedSubspaceInventory,
    InventoryStatus,
)
from hubbardflow.domain.symmetry_operation_models import (
    IDENTITY,
    Commensurability,
    ConditionStatus,
    CoveragePolicy,
    EquivalenceBands,
    ExactnessClass,
    Operation,
    ShadowPolicy,
    SymmetryAtom,
    SymmetryModel,
    SymmetryOperationsError,
    SymmetryReason,
    bind_symmetry_model,
    coverage_policy_v1,
)
from hubbardflow.domain.symmetry_operations import (
    candidate_operations,
    classify,
    close_under_composition,
    orbits,
)
from hubbardflow.siesta_backend.fdf_model import DftuRecord, parse_effective_fdf, species_identity

ROOT = Path(__file__).resolve().parents[2]
FDF_DIGEST = sha256(b"synthetic effective FDF").hexdigest()
IDENTITY_DIGEST = sha256(b"one declared semantic species").hexdigest()
RECORD = DftuRecord("X", "1", 1, 0, 0, 0, 2, 0.2, (), "X 1\n1 0\n0 0\n2 0.2")


def _ring(
    moments: tuple[float, ...],
) -> tuple[SymmetryModel, CorrelatedSubspaceInventory, ReferenceStateEvidence]:
    count = len(moments)
    model = SymmetryModel(
        FDF_DIGEST,
        ((1.0, 0, 0), (0, 2.0, 0), (0, 0, 3.0)),
        tuple(SymmetryAtom(i, (i / count, 0, 0), IDENTITY_DIGEST, True) for i in range(count)),
        2,
        True,
        False,
        True,
        True,
    )
    subspaces = tuple(CorrelatedSubspace(f"s{i}", i, "X", 1, RECORD, IDENTITY_DIGEST) for i in range(count))
    inventory = CorrelatedSubspaceInventory(subspaces, FDF_DIGEST, InventoryStatus.OK, (), FDF_DIGEST)
    state = ReferenceStateEvidence(
        FDF_DIGEST,
        FDF_DIGEST,
        True,
        True,
        tuple(MomentEvidence(i, moment, 5e-7) for i, moment in enumerate(moments)),
        (count, count, count),
        ((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0)),
        OccupationSpectraStatus.AVAILABLE,
        tuple(
            SubspaceOccupationEvidence(
                f"s{i}",
                i,
                (
                    OccupationSpectrum("up", ((1 + moment) / 2,), ((5e-7,),)),
                    OccupationSpectrum("down", ((1 - moment) / 2,), ((5e-7,),)),
                ),
            )
            for i, moment in enumerate(moments)
        ),
        EvidenceStatus.ADMISSIBLE,
        (),
    )
    return model, inventory, state


def _translation(model: SymmetryModel, step: int, flip: bool = False) -> Operation:
    count = len(model.atoms)
    return Operation(
        IDENTITY,
        (step / count, 0, 0),
        -1 if flip else 1,
        tuple((i + step) % count for i in range(count)),
        tuple((i + step) % count for i in range(count)),
        model,
    )


def _condition(result: object, name: str) -> ConditionStatus:
    from hubbardflow.domain.symmetry_operations import OperationClassification

    assert isinstance(result, OperationClassification)
    return next(item.status for item in result.conditions if item.condition == name)


def test_named_profile_exact_values_digest_and_round_trip() -> None:
    profile = coverage_policy_v1()
    assert profile.geometry == EquivalenceBands(1e-5, 1e-3)
    assert profile.magnetic_print_multipliers == EquivalenceBands(10, 1000)
    assert profile.spectral_print_multipliers == EquivalenceBands(10, 1000)
    assert profile.magnetic_half_width_floor_e == 5e-7
    assert not profile.allow_spin_flip and not profile.allow_rotations
    assert profile.shadow is ShadowPolicy.MANDATORY
    assert CoveragePolicy.from_mapping(json.loads(json.dumps(profile.to_mapping()))) == profile
    assert replace(profile, allow_spin_flip=True).digest != profile.digest
    model, _, _ = _ring((0.8, -0.8, 0.8, -0.8))
    op = _translation(model, 1, True)
    assert Operation.from_mapping(json.loads(json.dumps(op.to_mapping()))) == op


@pytest.mark.parametrize(
    "x,status",
    [(1e-5, ConditionStatus.EQUAL), (1e-4, ConditionStatus.AMBIGUOUS), (1e-3, ConditionStatus.DIFFERENT)],
)
def test_declared_geometry_boundaries(x: float, status: ConditionStatus) -> None:
    assert coverage_policy_v1().geometry.classify(x) is status


@pytest.mark.parametrize("count", [4, 6])
def test_afm_ring_global_spin_flip_and_same_sublattice_translation(count: int) -> None:
    model, inventory, state = _ring(tuple(0.82 * (-1) ** i for i in range(count)))
    policy = replace(coverage_policy_v1(), allow_spin_flip=True)
    assert classify(_translation(model, 1, True), inventory, state, policy).accepted
    assert classify(_translation(model, 2), inventory, state, policy).accepted
    assert not classify(_translation(model, 1), inventory, state, policy).accepted
    assert not classify(_translation(model, 1, True), inventory, state, coverage_policy_v1()).accepted


@pytest.mark.parametrize("count", [4, 6])
def test_equal_magnitude_different_environment_negative_and_true_translation_positive(count: int) -> None:
    model, inventory, state = _ring(tuple(0.81 * (-1) ** i for i in range(count)))
    other = sha256(b"site energy 0.8: different Hamiltonian").hexdigest()
    model = replace(
        model,
        atoms=tuple(
            replace(atom, identity_digest=other if atom.atom_index % 2 else IDENTITY_DIGEST)
            for atom in model.atoms
        ),
    )
    inventory = replace(
        inventory,
        subspaces=tuple(
            replace(item, identity_digest=other if item.atom_index % 2 else IDENTITY_DIGEST)
            for item in inventory.subspaces
        ),
    )
    policy = replace(coverage_policy_v1(), allow_spin_flip=True)
    wrong = classify(_translation(model, 1, True), inventory, state, policy)
    assert not wrong.accepted and _condition(wrong, "F2") is ConditionStatus.DIFFERENT
    assert classify(_translation(model, 2), inventory, state, policy).accepted


def test_fm_ring_and_spontaneously_broken_symmetric_ring() -> None:
    model, inventory, state = _ring((0.8,) * 4)
    assert classify(_translation(model, 1), inventory, state, coverage_policy_v1()).accepted
    model, inventory, state = _ring((0.86, 0.86, -0.73) * 2)
    for eps in (False, True):
        result = classify(
            _translation(model, 1, eps), inventory, state, replace(coverage_policy_v1(), allow_spin_flip=True)
        )
        assert not result.accepted and _condition(result, "F5") is ConditionStatus.DIFFERENT


@pytest.mark.parametrize(
    "negative",
    [
        "ferrimagnet",
        "orbital_order",
        "basis",
        "geometry",
        "ligand_geometry",
        "ligand_moment",
        "ligand_identity",
        "soc",
        "noncollinear",
        "projector",
        "missing_spectra",
        "missing_moments",
        "digest",
        "truncated",
    ],
)
@pytest.mark.parametrize("flags_on", [False, True])
def test_zero_false_acceptances(negative: str, flags_on: bool) -> None:
    model, inventory, state = _ring((0.8, -0.8, 0.8, -0.8))
    policy = replace(coverage_policy_v1(), allow_spin_flip=flags_on, allow_rotations=flags_on)
    if negative == "ferrimagnet":
        state = replace(
            state,
            moments_by_atom=tuple(
                replace(x, moment_e=-0.7) if x.atom_index % 2 else x for x in state.moments_by_atom
            ),
        )
    elif negative == "orbital_order":
        item = state.occupation_spectra_by_subspace[1]
        changed = replace(item, spectra=(replace(item.spectra[0], eigenvalues_e=(0.4,)), item.spectra[1]))
        state = replace(
            state,
            occupation_spectra_by_subspace=(
                state.occupation_spectra_by_subspace[0],
                changed,
                *state.occupation_spectra_by_subspace[2:],
            ),
        )
    elif negative == "basis":
        model = replace(
            model,
            atoms=tuple(
                replace(x, identity_digest=sha256(b"different PAO.Basis under same label").hexdigest())
                if x.atom_index == 1
                else x
                for x in model.atoms
            ),
        )
    elif negative == "geometry":
        model = replace(
            model,
            atoms=tuple(
                replace(x, coordinates_fractional=(0.2501, 0, 0)) if x.atom_index == 1 else x
                for x in model.atoms
            ),
        )
    elif negative.startswith("ligand"):
        ligand_atoms = tuple(SymmetryAtom(i + 4, (i / 4, 0.25, 0), IDENTITY_DIGEST, False) for i in range(4))
        model = replace(model, atoms=model.atoms + ligand_atoms)
        state = replace(
            state,
            moments_by_atom=state.moments_by_atom + tuple(MomentEvidence(i + 4, 0, 5e-7) for i in range(4)),
        )
        if negative == "ligand_geometry":
            model = replace(
                model,
                atoms=tuple(
                    replace(x, coordinates_fractional=(0.2501, 0.25, 0)) if x.atom_index == 5 else x
                    for x in model.atoms
                ),
            )
        elif negative == "ligand_moment":
            state = replace(
                state,
                moments_by_atom=tuple(
                    replace(x, moment_e=0.2) if x.atom_index == 5 else x for x in state.moments_by_atom
                ),
            )
        else:
            model = replace(
                model,
                atoms=tuple(
                    replace(x, identity_digest=sha256(b"different ligand basis").hexdigest())
                    if x.atom_index == 5
                    else x
                    for x in model.atoms
                ),
            )
    elif negative == "soc":
        model = replace(model, spin_orbit=True)
    elif negative == "noncollinear":
        model = replace(model, collinear=False)
    elif negative == "projector":
        inventory = replace(
            inventory,
            subspaces=tuple(
                replace(x, dftu_record=replace(RECORD, rc_bohr=3)) if x.atom_index == 1 else x
                for x in inventory.subspaces
            ),
        )
    elif negative == "missing_spectra":
        state = replace(
            state,
            occupation_spectra_status=OccupationSpectraStatus.NOT_AVAILABLE,
            occupation_spectra_by_subspace=(),
        )
    elif negative == "missing_moments":
        state = replace(state, moments_by_atom=state.moments_by_atom[:-1])
    elif negative == "digest":
        state = replace(state, input_fdf_sha256=IDENTITY_DIGEST)
    else:
        state = replace(state, normal_completion_verified=False)
    count = len(inventory.subspaces)
    mapping = tuple((i + 1) % 4 for i in range(4))
    if negative.startswith("ligand"):
        mapping += tuple(4 + (i + 1) % 4 for i in range(4))
    op = Operation(IDENTITY, (0.25, 0, 0), -1, mapping, tuple((i + 1) % count for i in range(count)), model)
    result = classify(op, inventory, state, policy)
    assert not result.accepted
    if negative in {"geometry", "ligand_geometry"}:
        assert _condition(result, "F1") is ConditionStatus.AMBIGUOUS


def test_pairwise_print_bands_prevent_one_coarse_atom_from_hiding_another() -> None:
    model, inventory, state = _ring((0.8,) * 4)
    state = replace(
        state,
        moments_by_atom=(
            MomentEvidence(0, 0.8, 0.1),
            MomentEvidence(1, 0.8, 0.1),
            MomentEvidence(2, 0.8, 5e-7),
            MomentEvidence(3, 0.801, 5e-7),
        ),
    )
    op = Operation(IDENTITY, (0, 0, 0), 1, (1, 0, 3, 2), (1, 0, 3, 2), model)
    assert _condition(classify(op, inventory, state, coverage_policy_v1()), "F5") is ConditionStatus.DIFFERENT


def test_heterogeneous_matrix_entry_half_widths_make_spectral_pair_ambiguous() -> None:
    model, inventory, state = _ring((0.8,) * 4)
    first = state.occupation_spectra_by_subspace[0]
    changed = replace(
        first, spectra=(replace(first.spectra[0], matrix_half_widths_e=((0.1,),)), first.spectra[1])
    )
    state = replace(
        state, occupation_spectra_by_subspace=(changed, *state.occupation_spectra_by_subspace[1:])
    )
    result = classify(_translation(model, 1), inventory, state, coverage_policy_v1())
    assert not result.accepted
    f7 = next(item for item in result.conditions if item.condition == "F7")
    assert f7.status is ConditionStatus.AMBIGUOUS
    assert f7.ambiguous_pairs == ((0, 1), (3, 0))
    assert SymmetryReason.SPECTRAL_PRECISION_HETEROGENEOUS in result.reasons


def test_uniform_entry_half_widths_use_exact_declared_spectral_multipliers() -> None:
    model, inventory, state = _ring((0.8,) * 4)
    result = classify(_translation(model, 1), inventory, state, coverage_policy_v1())
    assert result.accepted
    f7 = next(item for item in result.conditions if item.condition == "F7")
    assert not f7.ambiguous_pairs
    assert all(eq == 10 * 5e-7 and neq == 1000 * 5e-7 for _, _, _, eq, neq in f7.pair_measurements)


def test_f8_records_incommensurate_translation_without_excluding_candidate() -> None:
    model, inventory, state = _ring((0.8,) * 4)
    state = replace(state, mesh_divisions=(3, 3, 3))
    result = classify(_translation(model, 1), inventory, state, coverage_policy_v1())
    assert result.accepted
    assert result.commensurability is Commensurability.INCOMMENSURATE
    assert result.operation.exactness_class is ExactnessClass.EXACT_TRANSLATION


def test_f8_missing_mesh_is_recorded_without_excluding_translation_candidate() -> None:
    model, inventory, state = _ring((0.8,) * 4)
    result = classify(
        _translation(model, 1), inventory, replace(state, mesh_divisions=None), coverage_policy_v1()
    )
    assert result.accepted
    assert result.commensurability is Commensurability.NOT_ESTABLISHED
    assert _condition(result, "F8") is ConditionStatus.AMBIGUOUS


def test_subset_inventory_cannot_classify_full_model_as_response_equivalence() -> None:
    model, inventory, state = _ring((0.8,) * 4)
    reduced = replace(inventory, subspaces=inventory.subspaces[:2])
    op = replace(_translation(model, 0), correlated_permutation=(0, 1))
    with pytest.raises(SymmetryOperationsError, match="all model-correlated"):
        classify(op, reduced, state, coverage_policy_v1())


def test_nondiagonal_supercell_rows_define_reciprocal_generators_as_inverse_columns() -> None:
    model, inventory, state = _ring((0.0,))
    model = replace(model, lattice_vectors_angstrom=((1.0, 0, 0), (0, 1.0, 0), (0, 0, 1.0)))
    swap_xy = ((0, 1, 0), (1, 0, 0), (0, 0, 1))
    op = Operation(swap_xy, (0, 0, 0), 1, (0,), (0,), model)
    # K @ k is integer at Gamma and (1/2,0,0); the swapped (0,1/2,0)
    # is absent from this grid even though the atom at the origin is fixed.
    state = replace(state, k_mesh=((2, 1, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0)))
    result = classify(op, inventory, state, replace(coverage_policy_v1(), allow_rotations=True))
    assert not result.accepted
    assert _condition(result, "F4") is ConditionStatus.DIFFERENT


def test_nonorthogonal_fractional_rotation_uses_inverse_transpose_on_kpoints() -> None:
    model, inventory, state = _ring((0.0,))
    model = replace(
        model,
        lattice_vectors_angstrom=((1.0, 1.0, 0), (0, 1.0, 0), (0, 0, 1.0)),
    )
    rotation = ((1, 1, 0), (-1, -1, 1), (1, 0, 0))
    op = Operation(rotation, (0, 0, 0), 1, (0,), (0,), model)
    policy = replace(coverage_policy_v1(), allow_rotations=True)
    assert _condition(classify(op, inventory, state, policy), "F1") is ConditionStatus.EQUAL
    # The operation is a nonorthogonal integer representation of a cubic
    # rotation. A one-axis-only mesh must fail F4 under reciprocal R^{-T}.
    state = replace(state, k_mesh=((2, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0)))
    result = classify(op, inventory, state, replace(coverage_policy_v1(), allow_rotations=True))
    assert _condition(result, "F4") is ConditionStatus.DIFFERENT


def test_rotations_require_method_two_invariant_effective_kmesh_and_explicit_flag() -> None:
    model, inventory, state = _ring((0.8,) * 4)
    reflection = ((-1, 0, 0), (0, 1, 0), (0, 0, 1))
    op = Operation(reflection, (0, 0, 0), 1, (0, 3, 2, 1), (0, 3, 2, 1), model)
    on = replace(coverage_policy_v1(), allow_rotations=True)
    assert classify(op, inventory, state, on).accepted
    assert not classify(op, inventory, state, coverage_policy_v1()).accepted
    assert not classify(replace(op, model=replace(model, dftu_method=1)), inventory, state, on).accepted
    assert not classify(op, inventory, replace(state, k_mesh=None), on).accepted
    # A cyclic cubic-axis rotation cannot preserve a 2x3x4 mesh.
    cubic = replace(model, lattice_vectors_angstrom=((1.0, 0, 0), (0, 1.0, 0), (0, 0, 1.0)))
    swap = ((1, 0, 0), (0, 0, 1), (0, 1, 0))
    rotated = Operation(swap, (0, 0, 0), 1, (0, 1, 2, 3), (0, 1, 2, 3), cubic)
    mesh = ((2, 0, 0, 0), (0, 3, 0, 0), (0, 0, 4, 0))
    assert (
        _condition(classify(rotated, inventory, replace(state, k_mesh=mesh), on), "F4")
        is ConditionStatus.DIFFERENT
    )


def test_unimodular_shear_cannot_pass_as_lattice_symmetry_on_fixed_atom_and_unit_kmesh() -> None:
    model, inventory, state = _ring((0.0,))
    model = replace(model, lattice_vectors_angstrom=((1.0, 0, 0), (0, 1.0, 0), (0, 0, 1.0)))
    shear = ((1, 1, 0), (0, 1, 0), (0, 0, 1))
    op = Operation(shear, (0, 0, 0), 1, (0,), (0,), model)
    result = classify(op, inventory, state, replace(coverage_policy_v1(), allow_rotations=True))
    # The atom is fixed and all electronic evidence is equal; the metric test
    # must independently exclude this non-isometric GL(3,Z) transformation.
    assert not result.accepted
    assert _condition(result, "F1") is ConditionStatus.DIFFERENT
    assert SymmetryReason.LATTICE_INCOMPATIBLE in result.reasons
    assert all(
        item.status in (ConditionStatus.EQUAL, ConditionStatus.NOT_APPLICABLE)
        for item in result.conditions
        if item.condition != "F1"
    )


class _LegacyOperation(Protocol):
    @property
    def permutation(self) -> tuple[int, ...]: ...
    @property
    def rotation(self) -> tuple[tuple[int, ...], ...]: ...


class _LegacyCertificate(Protocol):
    @property
    def crystal_operations(self) -> tuple[_LegacyOperation, ...]: ...


def test_translation_geometric_core_agrees_with_unchanged_legacy_detector() -> None:
    import symmetry_reduction_proposal

    model, _, _ = _ring((0.8,) * 4)
    detect = cast(Callable[..., _LegacyCertificate], symmetry_reduction_proposal.detect_symmetry)
    certificate = detect(
        model.lattice_vectors_angstrom,
        [a.coordinates_fractional for a in model.atoms],
        [1] * 4,
        ["X"] * 4,
        [(0, 0, 0.8)] * 4,
        [{"complete_l_shell": False}] * 4,
        [{"rotationally_invariant": False}] * 4,
        geometric_tolerance=coverage_policy_v1().geometry.tau_eq,
        magnetic_tolerance=coverage_policy_v1().magnetic_half_width_floor_e,
    )
    legacy = {op.permutation for op in certificate.crystal_operations if op.rotation == IDENTITY}
    new = {
        op.atom_permutation
        for op in candidate_operations(model, coverage_policy_v1().geometry).operations
        if op.rotation_int == IDENTITY
    }
    assert new == legacy


@given(st.integers(min_value=2, max_value=12))
def test_group_closure_orbit_partition_and_deterministic_representative(count: int) -> None:
    model, inventory, _ = _ring((0.8,) * count)
    ops = tuple(_translation(model, step) for step in range(count))
    group = close_under_composition(ops)
    assert not group.reasons
    assert close_under_composition(tuple(reversed(ops))) == group
    partition = orbits(group, inventory)
    assert partition.orbits[0].members == tuple(f"s{i}" for i in range(count))
    assert partition.orbits[0].representative == "s0" and partition.orbits[0].shadow == "s1"
    assert orbits(group, replace(inventory, subspaces=tuple(reversed(inventory.subspaces)))) == partition


@given(st.permutations(tuple(range(4))))
def test_candidate_determinism_under_reordering_atom_records(order: list[int]) -> None:
    model, _, _ = _ring((0.8,) * 4)
    first = candidate_operations(model, coverage_policy_v1().geometry)
    second = candidate_operations(
        replace(model, atoms=tuple(model.atoms[i] for i in order)), coverage_policy_v1().geometry
    )
    assert [(op.rotation_int, op.translation_frac, op.atom_permutation) for op in first.operations] == [
        (op.rotation_int, op.translation_frac, op.atom_permutation) for op in second.operations
    ]
    assert first == second
    assert [op.to_mapping() for op in first.operations] == [op.to_mapping() for op in second.operations]


def test_nonclosure_drops_whole_set_and_empty_group_gives_singletons() -> None:
    model, inventory, _ = _ring((0.8,) * 4)
    group = close_under_composition((_translation(model, 0), _translation(model, 1)))
    assert group.operations == () and group.reasons == (SymmetryReason.GROUP_NOT_CLOSED,)
    assert len(orbits(group, inventory).orbits) == 4


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_rejected_at_all_numeric_boundaries(bad: float) -> None:
    model, inventory, state = _ring((0.8,) * 4)
    with pytest.raises(SymmetryOperationsError):
        EquivalenceBands(bad, 1)
    with pytest.raises(SymmetryOperationsError):
        replace(model.atoms[0], coordinates_fractional=(bad, 0, 0))
    with pytest.raises(SymmetryOperationsError):
        replace(_translation(model, 1), translation_frac=(bad, 0, 0))
    with pytest.raises(ValueError):
        classify(
            _translation(model, 1),
            inventory,
            replace(state, moments_by_atom=(MomentEvidence(0, bad, 5e-7), *state.moments_by_atom[1:])),
            coverage_policy_v1(),
        )


@given(st.sampled_from([float("nan"), float("inf"), -float("inf")]))
def test_property_nonfinite_spectral_evidence_cannot_be_accepted(bad: float) -> None:
    model, inventory, state = _ring((0.8,) * 4)
    entry = state.occupation_spectra_by_subspace[0]
    invalid = replace(entry, spectra=(replace(entry.spectra[0], eigenvalues_e=(bad,)), entry.spectra[1]))
    with pytest.raises(SymmetryOperationsError):
        classify(
            _translation(model, 1),
            inventory,
            replace(
                state, occupation_spectra_by_subspace=(invalid, *state.occupation_spectra_by_subspace[1:])
            ),
            coverage_policy_v1(),
        )


def test_duplicates_and_incomplete_channel_matrices_fail_closed() -> None:
    model, inventory, state = _ring((0.8,) * 4)
    op = _translation(model, 1)
    with pytest.raises(SymmetryOperationsError, match="bijection"):
        replace(op, atom_permutation=(0, 0, 2, 3))
    with pytest.raises(SymmetryOperationsError, match="duplicate moment"):
        classify(
            op,
            inventory,
            replace(state, moments_by_atom=state.moments_by_atom + state.moments_by_atom[:1]),
            coverage_policy_v1(),
        )
    entry = state.occupation_spectra_by_subspace[0]
    malformed = replace(entry, spectra=(entry.spectra[0], entry.spectra[0]))
    with pytest.raises(SymmetryOperationsError, match="unique up"):
        classify(
            op,
            inventory,
            replace(
                state, occupation_spectra_by_subspace=(malformed, *state.occupation_spectra_by_subspace[1:])
            ),
            coverage_policy_v1(),
        )
    malformed = replace(
        entry, spectra=(replace(entry.spectra[0], eigenvalues_e=(0.1, 0.2)), entry.spectra[1])
    )
    with pytest.raises(SymmetryOperationsError, match="dimensions"):
        classify(
            op,
            inventory,
            replace(
                state, occupation_spectra_by_subspace=(malformed, *state.occupation_spectra_by_subspace[1:])
            ),
            coverage_policy_v1(),
        )


def test_archived_fdf_geometry_binding_includes_ligands_and_missing_identity_stays_explicit() -> None:
    path = ROOT / "examples/tmo_campaigns/CoO_ref.fdf"
    source = parse_effective_fdf(path)
    model = bind_symmetry_model(source, species_identity(source, (path.parent,)))
    assert len(model.atoms) == source.number_of_atoms
    assert any(not atom.correlated for atom in model.atoms)
    assert model.effective_fdf_sha256 == source.effective_fdf_sha256
    assert any(atom.identity_digest is None for atom in model.atoms)
    candidates = candidate_operations(model, coverage_policy_v1().geometry)
    assert all(len(op.atom_permutation) == source.number_of_atoms for op in candidates.operations)


class _RingChi(Protocol):
    def __call__(
        self,
        eps: npt.NDArray[np.float64],
        U: float,
        t: float,
        Ne: int,
        kT: float,
        seed_m: npt.NDArray[np.float64],
    ) -> tuple[
        tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]],
        npt.NDArray[np.float64],
        npt.NDArray[np.float64],
    ]: ...


def test_reference_mean_field_ring_response_law_and_hidden_environment_counterexample() -> None:
    # Load only reference definitions; do not execute its top-level print/campaign.
    tree = ast.parse((ROOT / "docs/fdebq/reference/toy_symmetry_ring.py").read_text(encoding="utf-8"))
    definitions = ast.Module(
        body=[node for node in tree.body if isinstance(node, (ast.Import, ast.FunctionDef))], type_ignores=[]
    )
    namespace: dict[str, object] = {}
    exec(compile(definitions, "toy_symmetry_ring.py", "exec"), namespace)  # noqa: S102 -- trusted frozen reference definitions
    chi = cast(_RingChi, namespace["chi"])
    permutation = np.eye(4)[[3, 0, 1, 2]]
    for energies, should_hold in [(np.zeros(4), True), (np.array([0.0, 0.8, 0.0, 0.8]), False)]:
        _, bare, screened = chi(energies, 4.0, 1.0, 4, 0.05, np.array([1.0, -1.0, 1.0, -1.0]))
        for matrix in (bare, screened):
            residual = float(np.max(np.abs(permutation @ matrix @ permutation.T - matrix)))
            assert (residual <= coverage_policy_v1().geometry.tau_eq) is should_hold
