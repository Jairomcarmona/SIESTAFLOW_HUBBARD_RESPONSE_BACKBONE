"""D1/D2 ground truth, conservative fallbacks and archived reference goldens."""

from __future__ import annotations

import json
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from typing import cast

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from hubbardflow.domain.coverage import (
    CoverageError,
    CoverageQualification,
    CoverageReason,
    CoverageReferenceEvidence,
    CoverageStatus,
    CoverageStrategy,
    UserCoveragePolicy,
    qualify_coverage,
)
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
    EquivalenceBands,
    SymmetryAtom,
    SymmetryModel,
    coverage_policy_v1,
)
from hubbardflow.domain.symmetry_operations import CandidateOperations, candidate_operations
from hubbardflow.siesta_backend.coverage_reference import build_coverage_reference_evidence
from hubbardflow.siesta_backend.fdf_model import DftuRecord
from tools.hubbardflow_plan_diagnose import CoverageDiagnostic, diagnose

ROOT = Path(__file__).resolve().parents[2]
DIGEST = sha256(b"declared synthetic reference").hexdigest()
USER = UserCoveragePolicy("test-user-policy-v1", True, ())
RECORD = DftuRecord("X", "1", 1, 0, 0, 0, 2, 0.2, (), "X 1\n1 0\n0 0\n2 0.2")


def _golden_contract(report: CoverageDiagnostic) -> dict[str, object]:
    full = report.to_mapping()
    golden = {
        key: full[key]
        for key in (
            "schema",
            "diagnostic_only",
            "input_file_sha256",
            "output_sha256",
            "inventory",
            "reference_status",
            "strategy",
            "reasons",
            "would_reduce_to",
        )
    }
    assert report.qualification is not None
    ref = report.qualification.reference.to_mapping()
    golden["reference_admission"] = {
        key: ref[key]
        for key in (
            "input_file_sha256",
            "echoed_input_sha256",
            "input_output_consistent",
            "nonpolarized_verified",
            "perturbation_detected",
            "status",
            "parent_dm_sha256",
        )
    }
    return golden


def _toy(
    count: int, *, antiferromagnet: bool = False, nonpolarized: bool = False
) -> tuple[CorrelatedSubspaceInventory, CoverageReferenceEvidence, SymmetryModel]:
    moments = tuple(
        0.0 if nonpolarized else 0.8 * (-1 if antiferromagnet and i % 2 else 1) for i in range(count)
    )
    model = SymmetryModel(
        DIGEST,
        ((1.0, 0, 0), (0, 2.0, 0), (0, 0, 3.0)),
        tuple(SymmetryAtom(i, (i / count, 0, 0), DIGEST, True) for i in range(count)),
        2,
        True,
        False,
        True,
        True,
    )
    inventory = CorrelatedSubspaceInventory(
        tuple(CorrelatedSubspace(f"s{i}", i, "X", 1, RECORD, DIGEST) for i in range(count)),
        DIGEST,
        InventoryStatus.OK,
        (),
        DIGEST,
    )
    state = ReferenceStateEvidence(
        DIGEST,
        DIGEST,
        True,
        True,
        () if nonpolarized else tuple(MomentEvidence(i, moment, 5e-7) for i, moment in enumerate(moments)),
        (count, count, count),
        ((1, 0, 0, 0.0), (0, 1, 0, 0.0), (0, 0, 1, 0.0)),
        OccupationSpectraStatus.AVAILABLE,
        tuple(
            SubspaceOccupationEvidence(
                f"s{i}",
                i,
                (OccupationSpectrum("up", ((1 + m) / 2,), ((5e-7,),)),)
                if nonpolarized
                else (
                    OccupationSpectrum("up", ((1 + m) / 2,), ((5e-7,),)),
                    OccupationSpectrum("down", ((1 - m) / 2,), ((5e-7,),)),
                ),
            )
            for i, m in enumerate(moments)
        ),
        EvidenceStatus.ADMISSIBLE,
        (),
    )
    return (
        inventory,
        CoverageReferenceEvidence(
            state, DIGEST, DIGEST, True, nonpolarized, False, EvidenceStatus.ADMISSIBLE, DIGEST
        ),
        model,
    )


def test_known_translation_orbit_is_candidate_with_shadow_and_never_proven() -> None:
    inventory, evidence, model = _toy(4)
    q = qualify_coverage(inventory, evidence, model, coverage_policy_v1(), USER)
    assert q.would_reduce_to == 1
    assert q.strategy is CoverageStrategy.PARTIALLY_REDUCED
    assert q.computed_columns == ("s0", "s1")
    assert q.classes[0].status is CoverageStatus.CANDIDATE_PENDING_SHADOW
    assert q.classes[0].members == ("s0", "s1", "s2", "s3")
    for member, operation_id in q.classes[0].ops_rep_to_member:
        assert q.operations[operation_id].accepted
        assert q.operations[operation_id].operation.correlated_permutation[0] == int(member[1:])


@pytest.mark.parametrize("count", [1, 2])
def test_d2_no_saving_includes_singletons_and_two_member_orbits(count: int) -> None:
    inventory, evidence, model = _toy(count)
    q = qualify_coverage(inventory, evidence, model, coverage_policy_v1(), USER)
    assert q.would_reduce_to == 1
    assert q.strategy is CoverageStrategy.ALL_SUBSPACES
    assert q.computed_columns == tuple(f"s{i}" for i in range(count))
    assert CoverageReason.NO_SAVING in q.reasons
    assert not q.classes[0].reduced


def test_mno16_toy_off_two_candidates_on_one_candidate_with_compulsory_shadow() -> None:
    inventory, evidence, model = _toy(16, antiferromagnet=True)
    off = qualify_coverage(inventory, evidence, model, coverage_policy_v1(), USER)
    on = qualify_coverage(
        inventory, evidence, model, replace(coverage_policy_v1(), allow_spin_flip=True), USER
    )
    assert off.would_reduce_to == 2 and len(off.computed_columns) == 4
    assert on.would_reduce_to == 1 and on.computed_columns == ("s0", "s1")
    assert all(c.status is CoverageStatus.CANDIDATE_PENDING_SHADOW for c in off.classes + on.classes)
    assert off.digest != on.digest


def test_coo2_toy_spin_flip_candidate_has_no_run_savings() -> None:
    inventory, evidence, model = _toy(2, antiferromagnet=True)
    q = qualify_coverage(
        inventory, evidence, model, replace(coverage_policy_v1(), allow_spin_flip=True), USER
    )
    assert q.would_reduce_to == 1
    assert q.strategy is CoverageStrategy.ALL_SUBSPACES
    assert q.classes[0].reasons == (CoverageReason.NO_SAVING,)


def test_nonpolarized_translation_toy_does_not_fabricate_moments() -> None:
    inventory, evidence, model = _toy(4, nonpolarized=True)
    q = qualify_coverage(inventory, evidence, model, coverage_policy_v1(), USER)
    assert q.would_reduce_to == 1 and len(q.computed_columns) == 2
    assert not q.reference.state.moments_by_atom
    assert all(c.conditions[4].status.value == "NOT_APPLICABLE" for c in q.operations)


def test_verified_nonpolarized_coverage_omits_spin_flip_candidates_for_either_flag() -> None:
    inventory, evidence, model = _toy(4, nonpolarized=True)
    off = qualify_coverage(inventory, evidence, model, coverage_policy_v1(), USER)
    on = qualify_coverage(
        inventory, evidence, model, replace(coverage_policy_v1(), allow_spin_flip=True), USER
    )
    assert all(result.operation.eps == 1 for result in off.operations)
    assert all(result.operation.eps == 1 for result in on.operations)
    assert tuple(item.members for item in off.classes) == tuple(item.members for item in on.classes)
    assert tuple(item.status for item in off.classes) == tuple(item.status for item in on.classes)


@pytest.mark.parametrize("allow_rotations", [False, True])
def test_continuum_only_translation_is_rejected_for_production_policy(allow_rotations: bool) -> None:
    inventory, evidence, model = _toy(4)
    missing_mesh = replace(evidence.state, mesh_divisions=None)
    evidence = replace(evidence, state=missing_mesh)
    policy = replace(coverage_policy_v1(), allow_rotations=allow_rotations)
    q = qualify_coverage(inventory, evidence, model, policy, USER)
    assert q.classes[0].status is CoverageStatus.REJECTED_EXPANDED
    assert q.classes[0].reasons == (CoverageReason.FEATURE_VALIDATION_NOT_ESTABLISHED,)
    assert all(
        q.operations[operation_id].operation.exactness_class.value == "EXACT_IN_CONTINUUM_ONLY"
        for _, operation_id in q.classes[0].ops_rep_to_member
    )


@pytest.mark.parametrize(
    "trigger,expected",
    [
        ("disabled", CoverageReason.DISABLED_OR_FIXED),
        ("missing", CoverageReason.EVIDENCE_INCOMPLETE),
        ("shift", CoverageReason.EVIDENCE_INCOMPLETE),
        ("binding", CoverageReason.EVIDENCE_BINDING_MISMATCH),
        ("identity", CoverageReason.SPECIES_IDENTITY_NOT_ESTABLISHED),
        ("syntax", CoverageReason.UNSUPPORTED_SYNTAX),
        ("ambiguous", CoverageReason.AMBIGUOUS_OPERATION),
    ],
)
def test_h_fallbacks_fail_closed(trigger: str, expected: CoverageReason) -> None:
    inventory, evidence, model = _toy(4)
    user = USER
    if trigger == "disabled":
        user = replace(USER, enabled=False)
    elif trigger == "missing":
        evidence = replace(
            evidence,
            state=replace(
                evidence.state,
                occupation_spectra_status=OccupationSpectraStatus.NOT_AVAILABLE,
                occupation_spectra_by_subspace=(),
            ),
        )
    elif trigger == "shift":
        evidence = replace(evidence, perturbation_detected=True)
    elif trigger == "binding":
        inventory = replace(inventory, effective_fdf_sha256="0" * 64)
    elif trigger == "identity":
        model = replace(model, atoms=tuple(replace(a, identity_digest=None) for a in model.atoms))
    elif trigger == "syntax":
        inventory = replace(inventory, status=InventoryStatus.NOT_SUPPORTED)
    elif trigger == "ambiguous":
        evidence = replace(
            evidence,
            state=replace(
                evidence.state,
                moments_by_atom=(MomentEvidence(0, 0.80002, 5e-7), *evidence.state.moments_by_atom[1:]),
            ),
        )
    q = qualify_coverage(inventory, evidence, model, coverage_policy_v1(), user)
    if trigger == "binding":
        original_inventory, original_evidence, original_model = _toy(4)
        original = qualify_coverage(
            original_inventory, original_evidence, original_model, coverage_policy_v1(), user
        )
        assert q.strategy is original.strategy
        assert q.classes == original.classes
        assert CoverageReason.EVIDENCE_BINDING_MISMATCH not in q.reasons
        assert any(w.field == "reference.input_fdf_sha256" for w in q.traceability_warnings)
    else:
        assert q.strategy is CoverageStrategy.ALL_SUBSPACES
        assert expected in q.reasons
    assert q.computed_columns == (
        original.computed_columns if trigger == "binding" else ("s0", "s1", "s2", "s3")
    )


def test_nonclosed_candidate_group_is_dropped_whole(monkeypatch: pytest.MonkeyPatch) -> None:
    inventory, evidence, model = _toy(4)

    def incomplete_group(model: SymmetryModel, bands: EquivalenceBands) -> CandidateOperations:
        search = candidate_operations(model, bands)
        return CandidateOperations(
            tuple(
                op
                for op in search.operations
                if op.rotation_int == IDENTITY
                and op.eps == 1
                and op.translation_frac in ((0, 0, 0), (0.25, 0, 0))
            ),
            search.reasons,
        )

    monkeypatch.setattr("hubbardflow.domain.coverage.candidate_operations", incomplete_group)
    q = qualify_coverage(inventory, evidence, model, coverage_policy_v1(), USER)
    assert q.strategy is CoverageStrategy.ALL_SUBSPACES
    assert CoverageReason.GROUP_NOT_CLOSED in q.reasons
    assert q.computed_columns == ("s0", "s1", "s2", "s3")


def test_missing_identity_operation_expands_without_invented_maps() -> None:
    inventory, evidence, model = _toy(4)
    # TASK 9 F3 must reject an incomplete projector semantic record, even for I.
    bad_record = replace(RECORD, lambda_values=cast(tuple[float, ...], None))
    inventory = replace(
        inventory, subspaces=tuple(replace(s, dftu_record=bad_record) for s in inventory.subspaces)
    )
    q = qualify_coverage(inventory, evidence, model, coverage_policy_v1(), USER)
    assert q.strategy is CoverageStrategy.ALL_SUBSPACES
    assert CoverageReason.IDENTITY_OPERATION_NOT_ESTABLISHED in q.reasons
    assert all(not c.ops_rep_to_member for c in q.classes)


def test_user_equivalences_only_restrict_and_never_add() -> None:
    inventory, evidence, model = _toy(4, antiferromagnet=True)
    q = qualify_coverage(
        inventory,
        evidence,
        model,
        coverage_policy_v1(),
        replace(USER, declared_classes=(("s0", "s1", "s2", "s3"),)),
    )
    assert q.would_reduce_to == 2
    assert q.strategy is CoverageStrategy.ALL_SUBSPACES  # two members + shadow: no saving
    q = qualify_coverage(
        inventory, evidence, model, coverage_policy_v1(), replace(USER, declared_classes=(("s0", "s1"),))
    )
    assert q.would_reduce_to == 4
    with pytest.raises(CoverageError, match="absent"):
        qualify_coverage(
            inventory, evidence, model, coverage_policy_v1(), replace(USER, declared_classes=(("unknown",),))
        )


@settings(max_examples=12, deadline=None)
@given(st.permutations(tuple(range(4))))
def test_property_input_order_and_json_roundtrip(order: list[int]) -> None:
    inventory, evidence, model = _toy(4)
    first = qualify_coverage(inventory, evidence, model, coverage_policy_v1(), USER)
    second = qualify_coverage(
        replace(inventory, subspaces=tuple(inventory.subspaces[i] for i in order)),
        evidence,
        replace(model, atoms=tuple(model.atoms[i] for i in order)),
        coverage_policy_v1(),
        USER,
    )
    assert first.digest == second.digest
    loaded = cast(dict[str, object], json.loads(json.dumps(first.to_mapping())))
    assert CoverageQualification.from_mapping(loaded) == first


@given(st.sampled_from((float("nan"), float("inf"), -float("inf"))))
def test_property_nonfinite_even_in_fallback_evidence_is_rejected(bad: float) -> None:
    inventory, evidence, model = _toy(4)
    evidence = replace(
        evidence,
        state=replace(
            evidence.state,
            moments_by_atom=(MomentEvidence(0, bad, 5e-7), *evidence.state.moments_by_atom[1:]),
        ),
    )
    with pytest.raises(CoverageError):
        qualify_coverage(inventory, evidence, model, coverage_policy_v1(), replace(USER, enabled=False))


@pytest.mark.parametrize("system", ["CoO", "NiO", "FeO", "Cu3N"])
def test_archived_single_output_golden_negative_d1(system: str) -> None:
    folder = ROOT / "examples/tmo_campaigns"
    report = diagnose(
        folder / f"{system}_ref.fdf",
        folder / f"{system}_ref.out",
        (folder,),
        USER,
        allow_spin_flip=False,
        allow_rotations=False,
    )
    assert report.qualification is not None
    assert report.qualification.reference.status is EvidenceStatus.REFERENCE_NOT_ADMISSIBLE
    assert report.qualification.strategy is CoverageStrategy.ALL_SUBSPACES
    assert CoverageReason.EVIDENCE_INCOMPLETE in report.qualification.reasons
    assert (
        report.json_text()
        == diagnose(
            folder / f"{system}_ref.fdf",
            folder / f"{system}_ref.out",
            (folder,),
            USER,
            allow_spin_flip=False,
            allow_rotations=False,
        ).json_text()
    )
    if system == "Cu3N":
        assert report.qualification.reference.nonpolarized_verified
        assert report.qualification.reference.perturbation_detected
        assert not report.qualification.reference.input_output_consistent


@pytest.mark.parametrize("system", ["CoO", "NiO", "FeO", "Cu3N", "MnO"])
def test_versioned_golden_contract_and_full_report_determinism(system: str) -> None:
    if system == "MnO":
        folder = (
            ROOT
            / "campaigns/mno_afmii_strict_lr_v3r2/results/response-matrix-foreground-recovery-v4/00_REFERENCE"
        )
        fdf, output = folder / "siesta.fdf", folder / "siesta.out"
    else:
        folder = ROOT / "examples/tmo_campaigns"
        fdf, output = folder / f"{system}_ref.fdf", folder / f"{system}_ref.out"
    user = UserCoveragePolicy("coverage-user-policy-v1", True, ())
    report = diagnose(fdf, output, (folder,), user, allow_spin_flip=False, allow_rotations=False)
    expected = json.loads((ROOT / f"docs/fdebq/task10_reports/{system}.json").read_text(encoding="utf-8"))
    # JSON normalizes tuples to arrays and enum values to strings.
    assert json.loads(json.dumps(_golden_contract(report))) == expected
    repeated = diagnose(fdf, output, (folder,), user, allow_spin_flip=False, allow_rotations=False)
    assert report.json_text().encode() == repeated.json_text().encode()
    assert report.markdown_text().encode() == repeated.markdown_text().encode()
    assert CoverageDiagnostic.from_mapping(json.loads(report.json_text())) == report


@pytest.mark.parametrize(
    "folder",
    [
        "validation_observables_v6/coo/pbe_lru",
        "validation_observables_v6/mno/lru_central",
        "FEO_SCF_DIAGNOSTIC_EXPORT_20261001/feo_pbe/seedDM_converged",
    ],
)
def test_frozen_outputs_negative_golden_read_only(folder: str) -> None:
    path = ROOT / folder
    report = diagnose(
        path / "input.fdf", path / "siesta.out", (path,), USER, allow_spin_flip=False, allow_rotations=False
    )
    assert report.qualification is not None
    assert report.qualification.reference.status is EvidenceStatus.REFERENCE_NOT_ADMISSIBLE
    assert report.qualification.strategy is CoverageStrategy.ALL_SUBSPACES
    assert CoverageReason.EVIDENCE_INCOMPLETE in report.qualification.reasons


def test_mno_single_unperturbed_reference_has_both_required_observables() -> None:
    path = (
        ROOT
        / "campaigns/mno_afmii_strict_lr_v3r2/results/response-matrix-foreground-recovery-v4/00_REFERENCE"
    )
    evidence = build_coverage_reference_evidence(path / "siesta.fdf", path / "siesta.out", ())
    assert evidence.status is EvidenceStatus.ADMISSIBLE
    assert evidence.input_output_consistent and not evidence.perturbation_detected
    assert len(evidence.state.moments_by_atom) == 32
    assert len(evidence.state.occupation_spectra_by_subspace) == 16
    report = diagnose(
        path / "siesta.fdf", path / "siesta.out", (path,), USER, allow_spin_flip=False, allow_rotations=False
    )
    assert report.qualification is not None
    assert report.qualification.strategy is CoverageStrategy.ALL_SUBSPACES
    assert CoverageReason.SPECIES_IDENTITY_NOT_ESTABLISHED in report.qualification.reasons


def test_backend_truncated_or_cross_bound_output_cannot_be_reference(tmp_path: Path) -> None:
    path = ROOT / "examples/tmo_campaigns"
    output = tmp_path / "siesta.out"
    output.write_text(
        (path / "Cu3N_ref.out").read_text(encoding="utf-8").split("Job completed")[0], encoding="utf-8"
    )
    evidence = build_coverage_reference_evidence(path / "Cu3N_ref.fdf", output, ())
    assert evidence.status is EvidenceStatus.REFERENCE_NOT_ADMISSIBLE
    assert not evidence.state.normal_completion_verified


def test_incomplete_last_mulliken_table_does_not_reuse_earlier_table(tmp_path: Path) -> None:
    folder = (
        ROOT
        / "campaigns/mno_afmii_strict_lr_v3r2/results/response-matrix-foreground-recovery-v4/00_REFERENCE"
    )
    text = (folder / "siesta.out").read_text(encoding="utf-8")
    text += "\nMulliken Atomic Populations:\nAtom # charge valence Sz [e] Species\n1 1.0 1.0 0.8 MnLR00\n--------\nsiesta: normal completion\n"
    output = tmp_path / "incomplete-final-table.out"
    output.write_text(text, encoding="utf-8")
    evidence = build_coverage_reference_evidence(folder / "siesta.fdf", output, ())
    assert evidence.state.normal_completion_verified
    assert evidence.status is EvidenceStatus.REFERENCE_NOT_ADMISSIBLE


@pytest.mark.parametrize("control", ["ferrimagnet", "orbital", "ligand", "soc", "noncollinear"])
@pytest.mark.parametrize("flags", [False, True])
def test_negative_controls_have_zero_false_reductions(control: str, flags: bool) -> None:
    inventory, evidence, model = _toy(4, antiferromagnet=True)
    if control == "ferrimagnet":
        evidence = replace(
            evidence,
            state=replace(
                evidence.state,
                moments_by_atom=tuple(
                    MomentEvidence(i, m, 5e-7) for i, m in enumerate((0.8, -0.4, 0.6, -0.2))
                ),
            ),
        )
    elif control == "orbital":
        evidence = replace(
            evidence,
            state=replace(
                evidence.state,
                occupation_spectra_by_subspace=tuple(
                    replace(
                        row,
                        spectra=tuple(
                            replace(spectrum, eigenvalues_e=(spectrum.eigenvalues_e[0] + 0.01 * i,))
                            for spectrum in row.spectra
                        ),
                    )
                    for i, row in enumerate(evidence.state.occupation_spectra_by_subspace)
                ),
            ),
        )
    elif control == "ligand":
        # Different semantic identity even though all labels and |m| coincide.
        model = replace(
            model,
            atoms=tuple(
                replace(a, identity_digest=sha256(str(a.atom_index).encode()).hexdigest())
                for a in model.atoms
            ),
        )
        inventory = replace(
            inventory,
            subspaces=tuple(
                replace(s, identity_digest=model.atoms[s.atom_index].identity_digest or "")
                for s in inventory.subspaces
            ),
        )
    elif control == "soc":
        model = replace(model, spin_orbit=True)
    else:
        model = replace(model, collinear=False)
    q = qualify_coverage(
        inventory,
        evidence,
        model,
        replace(coverage_policy_v1(), allow_spin_flip=flags, allow_rotations=flags),
        USER,
    )
    assert q.strategy is CoverageStrategy.ALL_SUBSPACES
    assert q.computed_columns == ("s0", "s1", "s2", "s3")


def test_nonpolarized_backend_admission_requires_single_zero_shift_echo(tmp_path: Path) -> None:
    fdf_text = """NumberOfAtoms 1
NumberOfSpecies 1
%block ChemicalSpeciesLabel
1 1 X
%endblock ChemicalSpeciesLabel
LatticeConstant 1.0 Ang
%block LatticeVectors
1.0 0.0 0.0
0.0 1.0 0.0
0.0 0.0 1.0
%endblock LatticeVectors
AtomicCoordinatesFormat Fractional
%block AtomicCoordinatesAndAtomicSpecies
0.0 0.0 0.0 1
%endblock AtomicCoordinatesAndAtomicSpecies
Spin non-polarized
DFTU.PotentialShift true
%block DFTU.Proj
X 1
1 0
0.0 0.0
2.0 0.2
%endblock DFTU.Proj
"""
    fdf, output = tmp_path / "siesta.fdf", tmp_path / "siesta.out"
    fdf.write_text(fdf_text, encoding="utf-8")
    out_text = (
        "******** Dump of input data file ********\n"
        + fdf_text
        + "******** End of input data file ********\n"
        "redata: Spin configuration = none\n"
        "redata: Number of spin components = 1\n"
        "redata: Time-Reversal Symmetry = T\n"
        "SCF Convergence by density criterion\n"
        "hubbard_term: recalculating local occupations 1\n"
        "hubbard_term: atom, species: 1 1\n"
        "1 1 0.500000\n"
        "hubbard_term: Total projector shell\n"
        "Occupations: 0.500000 0.500000\n"
        "hubbard_term: maximum change in local occup. 0.000000\n"
        "siesta: normal completion\n"
    )
    output.write_text(out_text, encoding="utf-8")
    evidence = build_coverage_reference_evidence(fdf, output, ())
    assert evidence.status is EvidenceStatus.ADMISSIBLE
    assert evidence.nonpolarized_verified and not evidence.state.moments_by_atom
    output.write_text(out_text.replace("0.0 0.0\n2.0 0.2", "0.1 0.0\n2.0 0.2"), encoding="utf-8")
    evidence = build_coverage_reference_evidence(fdf, output, ())
    assert evidence.status is EvidenceStatus.REFERENCE_NOT_ADMISSIBLE
    assert evidence.perturbation_detected and not evidence.input_output_consistent


def test_unknown_syntax_reports_explicit_all_subspaces(tmp_path: Path) -> None:
    fdf = tmp_path / "invalid.fdf"
    fdf.write_text("NumberOfAtoms 2\n", encoding="utf-8")
    output = tmp_path / "siesta.out"
    output.write_text("siesta: normal completion\n", encoding="utf-8")
    report = diagnose(fdf, output, (), USER, allow_spin_flip=False, allow_rotations=False)
    assert report.to_mapping()["strategy"] == "ALL_SUBSPACES"
    assert report.to_mapping()["reasons"] == ["UNSUPPORTED_SYNTAX"]
