"""D16 known printed states, inclusive quantum boundaries and fail-closed inputs."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from hashlib import sha256
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from hubbardflow.domain.reference_reproduction import (
    FermiEquivalence,
    OccupationEquivalence,
    ParentReproduction,
    ReferenceReproduction,
    ReferenceReproductionError,
    ReproductionReason,
    ReproductionWarning,
    ToleranceSource,
    compare_reference_states,
)
from hubbardflow.execution.reference_reproduction_step import check_reference_reproduction
from hubbardflow.siesta_backend.event_parser import parse_hubbard_population_events
from hubbardflow.siesta_backend.point_state_evidence import build_point_state
from hubbardflow.siesta_backend.reference_reproduction_evidence import reference_reproduction_evidence

ROOT = Path(__file__).resolve().parents[2]
FIRST = sha256(b"planning DM bytes").hexdigest()
SECOND = sha256(b"campaign DM different bytes").hexdigest()


def output(*, off_diagonal: float = 0.0, fermi: str = "1.00000", polarized: bool = True) -> str:
    rows = []
    for i in range(1, 6):
        for j in range(1, 6):
            value = 0.5 if i == j else off_diagonal if {i, j} == {1, 2} else 0.0
            rows.append(f"{i} {j} {value:.5f}" + (f" {value:.5f}" if polarized else ""))
    return "\n".join(
        [
            "SCF Convergence by density criterion",
            "Using DM_out to compute the final energy and forces",
            "hubbard_term: recalculating local occupations 14",
            "hubbard_term: projector occupations",
            "hubbard_term: atom, species: 1 1",
            *rows,
            "Occupations: 2.50000 2.50000 5.00000" if polarized else "Occupations: 2.50000 2.50000",
            "hubbard_term: recalculating Hamiltonian",
            f"siesta: Fermi = {fermi}",
            "Mulliken Atomic Populations:",
            "Atom # Q [e] Qval [e] Sz [e] Species",
            "1 5.00000 5.00000 0.00000 Mn",
            "------------------------------------",
            "Job completed",
            "siesta: normal completion",
        ]
    )


def test_identical_printed_state_and_different_dm_bytes_are_recorded() -> None:
    evidence = reference_reproduction_evidence(
        output(), output(), FIRST, SECOND, ParentReproduction.PRINT_EQUIVALENT
    )
    assert not evidence.equivalent
    assert evidence.reason is ReproductionReason.EQUIVALENCE_NOT_ASSESSED
    assert evidence.planning_parent_dm_sha256 != evidence.campaign_parent_dm_sha256
    assert evidence.max_occupation_difference_e == 0.0
    assert evidence.max_fermi_difference_ev == 0.0
    assert evidence.occupation_comparison_quanta_e == (1e-5,)
    assert evidence.fermi_comparison_quantum_ev == 1e-5
    assert evidence.fermi_tolerance_ev is None
    assert ReferenceReproduction.from_mapping(evidence.to_mapping()) == evidence


@given(st.integers(min_value=-5, max_value=5))
def test_exact_quantum_boundary(quanta: int) -> None:
    evidence = reference_reproduction_evidence(
        output(),
        output(off_diagonal=quanta * 1e-5),
        FIRST,
        SECOND,
        ParentReproduction.PRINT_EQUIVALENT,
    )
    assert evidence.reason is ReproductionReason.EQUIVALENCE_NOT_ASSESSED
    assert evidence.max_occupation_difference_e == float(Decimal(abs(quanta)) * Decimal("0.00001"))


@pytest.mark.parametrize("fermi", ["1.00001", "1.00002", "0.99998"])
def test_fermi_outside_print_bounds_is_recorded_but_unassessed(fermi: str) -> None:
    evidence = reference_reproduction_evidence(
        output(), output(fermi=fermi), FIRST, SECOND, ParentReproduction.PRINT_EQUIVALENT
    )
    assert not evidence.equivalent
    assert evidence.reason is ReproductionReason.EQUIVALENCE_NOT_ASSESSED
    assert evidence.max_fermi_difference_ev is not None


def test_two_occupation_quanta_reject_parent_even_when_fermi_tolerance_is_unassessed() -> None:
    evidence = reference_reproduction_evidence(
        output(),
        output(off_diagonal=2e-5),
        FIRST,
        SECOND,
        ParentReproduction.PRINT_EQUIVALENT,
        scf_dm_tolerance=1e-5,
        tolerance_factor=1.0,
    )
    assert evidence.reason is ReproductionReason.PARENT_STATE_NOT_EQUIVALENT
    assert evidence.rejects_reduction
    assert evidence.occupation_tolerance_e == 1e-5
    assert "atom 1 spin up element (1,2)" in evidence.detail
    assert "difference 0.00002 e > tolerance 1e-05 e" in evidence.detail
    assert evidence.fermi_tolerance_ev is None


@pytest.mark.parametrize("digest", [FIRST, SECOND, None, "malformed"])
def test_numeric_noise_below_declared_occupation_tolerance_never_rejects_by_digest(
    digest: str | None,
) -> None:
    evidence = reference_reproduction_evidence(
        output(),
        output(off_diagonal=1e-5),
        FIRST,
        digest,
        ParentReproduction.PRINT_EQUIVALENT,
        scf_dm_tolerance=1e-5,
        tolerance_factor=2.0,
    )
    assert not evidence.rejects_reduction
    assert evidence.reason is ReproductionReason.EQUIVALENT
    assert evidence.occupation_equivalence is OccupationEquivalence.EQUIVALENT
    assert evidence.fermi_equivalence is FermiEquivalence.RECORDED_NOT_ASSESSED
    assert evidence.occupation_tolerance_e == 2e-5
    assert evidence.max_occupation_difference_e == 1e-5


def test_archived_mno_real_occupation_difference_rejects_without_fermi_tolerance() -> None:
    text = (
        ROOT
        / "campaigns/mno_afmii_strict_lr_v3r2/results/response-matrix-foreground-recovery-v4/00_REFERENCE/siesta.out"
    ).read_text(encoding="utf-8")
    state = build_point_state(parse_hubbard_population_events(text)[-1], text)
    atom = state.atoms[0]
    row = (
        atom.matrix_up[0][0],
        str(Decimal(atom.matrix_up[0][1]) + Decimal("0.00005")),
        *atom.matrix_up[0][2:],
    )
    changed = replace(state, atoms=(replace(atom, matrix_up=(row, *atom.matrix_up[1:])), *state.atoms[1:]))
    evidence = compare_reference_states(state, changed, FIRST, SECOND, 1e-5, 1.0)
    assert evidence.reason is ReproductionReason.PARENT_STATE_NOT_EQUIVALENT
    assert evidence.rejects_reduction
    assert "element (1,2)" in evidence.detail
    assert evidence.fermi_tolerance_ev is None


@pytest.mark.parametrize(
    "bad",
    [
        "not a SIESTA output",
        output(polarized=False),
        output().replace("Job completed", "interrupted"),
        output().replace("SCF Convergence by density criterion", "SCF_NOT_CONV"),
        output().replace("Using DM_out to compute the final energy and forces", "intermediate DM"),
        output() + "\nMPI_Abort",
        output().replace("siesta: Fermi = 1.00000", "siesta: Fermi = NaN"),
    ],
)
def test_unparseable_or_unconverged_reference_fails_closed_even_when_dm_matches(bad: str) -> None:
    evidence = reference_reproduction_evidence(
        output(), bad, FIRST, FIRST, ParentReproduction.PRINT_EQUIVALENT
    )
    assert not evidence.equivalent
    assert evidence.reason is ReproductionReason.EQUIVALENCE_NOT_ASSESSED
    assert "campaign reference state unparseable or invalid" in evidence.detail


def test_species_or_projector_identity_mismatch_fails_closed() -> None:
    evidence = reference_reproduction_evidence(
        output(),
        output().replace("atom, species: 1 1", "atom, species: 1 2"),
        FIRST,
        SECOND,
        ParentReproduction.PRINT_EQUIVALENT,
    )
    assert not evidence.equivalent
    assert "atom/projector identities differ" in evidence.detail


def test_identically_truncated_population_must_match_complete_inventory() -> None:
    evidence = reference_reproduction_evidence(
        output(),
        output(),
        FIRST,
        SECOND,
        ParentReproduction.PRINT_EQUIVALENT,
        expected_projectors=((1, 5), (2, 5)),
    )
    assert not evidence.equivalent
    assert "atom/projector inventory incomplete" in evidence.detail


@pytest.mark.parametrize("matches", [False, True])
def test_record_only_never_decides_from_dm_hash(matches: bool) -> None:
    evidence = reference_reproduction_evidence(
        "",
        "",
        FIRST,
        FIRST if matches else SECOND,
        ParentReproduction.RECORD_ONLY,
    )
    assert not evidence.equivalent
    assert evidence.reason is ReproductionReason.EQUIVALENCE_NOT_ASSESSED
    assert evidence.planning_parent_dm_sha256 == FIRST
    assert evidence.campaign_parent_dm_sha256 == (FIRST if matches else SECOND)


def test_frozen_mno_printed_reference_regression() -> None:
    text = (
        ROOT
        / "campaigns/mno_afmii_strict_lr_v3r2/results/response-matrix-foreground-recovery-v4/00_REFERENCE/siesta.out"
    ).read_text(encoding="utf-8")
    result = reference_reproduction_evidence(text, text, FIRST, SECOND, ParentReproduction.PRINT_EQUIVALENT)
    assert not result.equivalent
    assert result.reason is ReproductionReason.EQUIVALENCE_NOT_ASSESSED
    assert result.max_occupation_difference_e == 0.0


@pytest.mark.parametrize("token", ["NaN", "Infinity", "-Infinity"])
def test_domain_rejects_nonfinite_matrix_tokens(token: str) -> None:
    state = build_point_state(parse_hubbard_population_events(output())[-1], output())
    atom = state.atoms[0]
    matrix = ((token, *atom.matrix_up[0][1:]), *atom.matrix_up[1:])
    broken = replace(state, atoms=(replace(atom, matrix_up=matrix),))
    with pytest.raises(ReferenceReproductionError):
        compare_reference_states(state, broken, FIRST, SECOND)


def test_unreadable_output_records_both_digest_identities(tmp_path: Path) -> None:
    dm = tmp_path / "observed.DM"
    dm.write_bytes(b"campaign DM different bytes")
    evidence = check_reference_reproduction(
        tmp_path / "missing.out", tmp_path / "missing2.out", FIRST, dm, ParentReproduction.PRINT_EQUIVALENT
    )
    assert evidence.campaign_parent_dm_sha256 == SECOND
    assert not evidence.equivalent
    assert "reference output unreadable" in evidence.detail


def test_heterogeneous_token_precision_cannot_hide_a_precise_element_difference() -> None:
    state = build_point_state(parse_hubbard_population_events(output())[-1], output())
    atom = state.atoms[0]
    coarse = ("0.5", *atom.matrix_up[0][1:])
    planning = replace(state, atoms=(replace(atom, matrix_up=(coarse, *atom.matrix_up[1:])),))
    changed_row = (coarse[0], "0.00002", *coarse[2:])
    campaign = replace(state, atoms=(replace(atom, matrix_up=(changed_row, *atom.matrix_up[1:])),))
    evidence = compare_reference_states(planning, campaign, FIRST, SECOND, 1e-5, 1.0)
    assert evidence.reason is ReproductionReason.PARENT_STATE_NOT_EQUIVALENT
    assert evidence.affected_atom_indices == (1,)
    assert evidence.occupation_comparison_quanta_e == (1e-5, 0.1)
    assert evidence.occupation_tolerances_e == (1e-5, 0.1)
    assert "element (1,2)" in evidence.detail
    assert "tolerance 1e-05" in evidence.detail


def test_all_atoms_with_physical_differences_are_retained() -> None:
    state = build_point_state(parse_hubbard_population_events(output())[-1], output())
    atom = state.atoms[0]
    second = replace(atom, atom_index=2)
    planning = replace(state, atoms=(atom, second))
    changed_row = ("0.50003", *atom.matrix_up[0][1:])
    changed_matrix = (changed_row, *atom.matrix_up[1:])
    campaign = replace(
        state, atoms=(replace(atom, matrix_up=changed_matrix), replace(second, matrix_up=changed_matrix))
    )
    evidence = compare_reference_states(planning, campaign, FIRST, SECOND, 1e-5, 1.0)
    assert evidence.affected_atom_indices == (1, 2)
    assert "atom 1" in evidence.detail and "atom 2" in evidence.detail
    assert ReferenceReproduction.from_mapping(evidence.to_mapping()) == evidence


def test_report_renders_effective_tolerances_and_fermi_assessment() -> None:
    from hubbardflow.reporting.lr_u_report import reference_reproduction_report_lines

    evidence = reference_reproduction_evidence(
        output(),
        output(off_diagonal=1e-5),
        FIRST,
        SECOND,
        ParentReproduction.PRINT_EQUIVALENT,
        scf_dm_tolerance=1e-5,
        tolerance_factor=2.0,
    )
    report = "\n".join(reference_reproduction_report_lines(evidence.to_mapping()))
    assert FIRST in report and SECOND in report
    assert "Maximum occupation difference (e): 1e-05" in report
    assert "Occupation tolerances used (e): [2e-05]" in report
    assert "Declared SCF.DM.Tolerance: 1e-05; policy factor: 2" in report
    assert "Fermi assessment: RECORDED_NOT_ASSESSED" in report
    assert "Criterion: `PRINT_EQUIVALENT`" in report


def test_record_only_preserves_real_occupation_rejection_and_scope() -> None:
    evidence = reference_reproduction_evidence(
        output(),
        output(off_diagonal=2e-5),
        FIRST,
        SECOND,
        ParentReproduction.RECORD_ONLY,
        scf_dm_tolerance=1e-5,
        tolerance_factor=1.0,
    )
    assert evidence.reason is ReproductionReason.PARENT_STATE_NOT_EQUIVALENT
    assert evidence.rejects_reduction
    assert evidence.affected_atom_indices == (1,)
    assert "difference 0.00002 e > tolerance 1e-05 e" in evidence.detail
    assert evidence.planning_parent_dm_sha256 == FIRST
    assert evidence.campaign_parent_dm_sha256 == SECOND


def test_record_only_preserves_incomplete_domain_identity_rejection() -> None:
    state = build_point_state(parse_hubbard_population_events(output())[-1], output())
    campaign = replace(state, atoms=(replace(state.atoms[0], atom_index=2),))
    evidence = compare_reference_states(
        state, campaign, FIRST, SECOND, 1e-5, 1.0, ParentReproduction.RECORD_ONLY
    )
    assert evidence.reason is ReproductionReason.PARENT_IDENTITY_NOT_ESTABLISHED
    assert evidence.rejects_reduction
    assert evidence.all_reduced_classes_affected
    assert "atom indices differ" in evidence.detail


def test_record_only_preserves_incomplete_parsed_projector_identity_rejection() -> None:
    evidence = reference_reproduction_evidence(
        output(),
        output(),
        FIRST,
        SECOND,
        ParentReproduction.RECORD_ONLY,
        expected_projectors=((1, 5), (2, 5)),
        scf_dm_tolerance=1e-5,
        tolerance_factor=1.0,
    )
    assert evidence.reason is ReproductionReason.PARENT_IDENTITY_NOT_ESTABLISHED
    assert evidence.rejects_reduction
    assert evidence.all_reduced_classes_affected


@pytest.mark.parametrize("difference", [0.0, 1e-5])
def test_record_only_different_dm_bytes_and_noise_below_tol_do_not_reject(difference: float) -> None:
    evidence = reference_reproduction_evidence(
        output(),
        output(off_diagonal=difference),
        FIRST,
        SECOND,
        ParentReproduction.RECORD_ONLY,
        scf_dm_tolerance=1e-5,
        tolerance_factor=2.0,
    )
    assert evidence.reason is ReproductionReason.EQUIVALENCE_NOT_ASSESSED
    assert not evidence.rejects_reduction
    assert evidence.max_occupation_difference_e == difference
    assert evidence.occupation_tolerance_e == 2e-5
    assert evidence.planning_parent_dm_sha256 != evidence.campaign_parent_dm_sha256


def test_record_only_without_fermi_tolerance_records_fermi_without_rejecting() -> None:
    evidence = reference_reproduction_evidence(
        output(),
        output(fermi="1.90000"),
        FIRST,
        SECOND,
        ParentReproduction.RECORD_ONLY,
        scf_dm_tolerance=1e-5,
        tolerance_factor=1.0,
    )

    assert evidence.reason is ReproductionReason.EQUIVALENCE_NOT_ASSESSED
    assert evidence.occupation_equivalence is OccupationEquivalence.NOT_ASSESSED
    assert evidence.max_occupation_difference_e == 0.0
    assert evidence.occupation_tolerance_e == 1e-5
    assert evidence.fermi_equivalence is FermiEquivalence.RECORDED_NOT_ASSESSED
    assert evidence.max_fermi_difference_ev == 0.9
    assert evidence.fermi_tolerance_ev is None
    assert not evidence.rejects_reduction


@pytest.mark.parametrize("fermi", ["1.00000", "1.90000"])
def test_no_declared_fermi_tolerance_does_not_change_occupation_verdict(fermi: str) -> None:
    evidence = reference_reproduction_evidence(
        output(),
        output(fermi=fermi),
        FIRST,
        SECOND,
        ParentReproduction.PRINT_EQUIVALENT,
        scf_dm_tolerance=1e-5,
        tolerance_factor=1.0,
    )
    assert evidence.equivalent
    assert evidence.occupation_equivalence is OccupationEquivalence.EQUIVALENT
    assert evidence.fermi_equivalence is FermiEquivalence.RECORDED_NOT_ASSESSED
    assert evidence.max_fermi_difference_ev == float(abs(Decimal(fermi) - Decimal("1.00000")))
    assert evidence.fermi_print_half_widths_ev == (5e-6, 5e-6)
    assert evidence.fermi_tolerance_ev is None
    assert evidence.planning_parent_dm_sha256 != evidence.campaign_parent_dm_sha256
    assert ReferenceReproduction.from_mapping(evidence.to_mapping()) == evidence


@pytest.mark.parametrize("fermi,tolerance", [("1.00002", 2e-5), ("1.00001", 2e-5)])
def test_declared_fermi_tolerance_inclusive_boundary_passes(fermi: str, tolerance: float) -> None:
    evidence = reference_reproduction_evidence(
        output(),
        output(fermi=fermi),
        FIRST,
        SECOND,
        ParentReproduction.PRINT_EQUIVALENT,
        scf_dm_tolerance=1e-5,
        tolerance_factor=1.0,
        tol_fermi_ev=tolerance,
        fermi_tolerance_source=ToleranceSource.CONFIG,
    )
    assert evidence.equivalent
    assert evidence.fermi_equivalence is FermiEquivalence.EQUIVALENT
    assert evidence.fermi_tolerance_ev == tolerance
    assert evidence.declared_fermi_tolerance_ev == tolerance
    assert evidence.fermi_tolerance_source is ToleranceSource.CONFIG
    assert not evidence.warnings
    assert ReferenceReproduction.from_mapping(evidence.to_mapping()) == evidence


def test_declared_fermi_tolerance_exceeded_has_own_reason_and_parent_scope() -> None:
    evidence = reference_reproduction_evidence(
        output(),
        output(fermi="1.00003"),
        FIRST,
        SECOND,
        ParentReproduction.PRINT_EQUIVALENT,
        scf_dm_tolerance=1e-5,
        tolerance_factor=1.0,
        tol_fermi_ev=2e-5,
        fermi_tolerance_source=ToleranceSource.CLI,
    )
    assert evidence.reason is ReproductionReason.PARENT_FERMI_NOT_EQUIVALENT
    assert evidence.rejects_reduction
    assert evidence.occupation_equivalence is OccupationEquivalence.EQUIVALENT
    assert evidence.fermi_equivalence is FermiEquivalence.NOT_EQUIVALENT
    assert evidence.all_reduced_classes_affected  # Every class using this one parent.
    assert evidence.affected_atom_indices == ()
    assert "Fermi difference 0.00003 eV > tolerance 0.00002 eV" in evidence.detail
    assert ReferenceReproduction.from_mapping(evidence.to_mapping()) == evidence


def test_declared_fermi_tolerance_below_combined_print_width_warns_and_uses_width() -> None:
    evidence = reference_reproduction_evidence(
        output(),
        output(fermi="1.00001"),
        FIRST,
        SECOND,
        ParentReproduction.PRINT_EQUIVALENT,
        scf_dm_tolerance=1e-5,
        tolerance_factor=1.0,
        tol_fermi_ev=1e-6,
    )
    assert evidence.equivalent
    assert evidence.fermi_equivalence is FermiEquivalence.EQUIVALENT
    assert evidence.fermi_tolerance_ev == 1e-5
    assert evidence.declared_fermi_tolerance_ev == 1e-6
    assert evidence.warnings == (ReproductionWarning.FERMI_TOLERANCE_BELOW_PRINT_HALF_WIDTH,)
    assert ReferenceReproduction.from_mapping(evidence.to_mapping()) == evidence
    from hubbardflow.reporting.lr_u_report import reference_reproduction_report_lines

    report = "\n".join(reference_reproduction_report_lines(evidence.to_mapping()))
    assert "FERMI_TOLERANCE_BELOW_PRINT_HALF_WIDTH" in report
    assert "tolerance used (eV): 1e-05; declared (eV): 1e-06" in report


@pytest.mark.parametrize(
    "fermi,reason",
    [
        ("1.00001", ReproductionReason.EQUIVALENCE_NOT_ASSESSED),
        ("1.00003", ReproductionReason.PARENT_FERMI_NOT_EQUIVALENT),
    ],
)
def test_record_only_preserves_declared_fermi_failure_without_granting_equivalence(
    fermi: str,
    reason: ReproductionReason,
) -> None:
    evidence = reference_reproduction_evidence(
        output(),
        output(fermi=fermi),
        FIRST,
        SECOND,
        ParentReproduction.RECORD_ONLY,
        scf_dm_tolerance=1e-5,
        tolerance_factor=1.0,
        tol_fermi_ev=2e-5,
    )
    assert evidence.reason is reason
    assert not evidence.equivalent
    assert evidence.occupation_equivalence is OccupationEquivalence.NOT_ASSESSED
    assert evidence.fermi_equivalence is (
        FermiEquivalence.NOT_EQUIVALENT
        if reason is ReproductionReason.PARENT_FERMI_NOT_EQUIVALENT
        else FermiEquivalence.RECORDED_NOT_ASSESSED
    )


def test_fermi_and_occupation_failures_are_separate() -> None:
    evidence = reference_reproduction_evidence(
        output(),
        output(off_diagonal=3e-5, fermi="1.00003"),
        FIRST,
        SECOND,
        ParentReproduction.PRINT_EQUIVALENT,
        scf_dm_tolerance=1e-5,
        tolerance_factor=1.0,
        tol_fermi_ev=2e-5,
    )
    assert evidence.reason is ReproductionReason.PARENT_STATE_NOT_EQUIVALENT
    assert evidence.occupation_equivalence is OccupationEquivalence.NOT_EQUIVALENT
    assert evidence.fermi_equivalence is FermiEquivalence.NOT_EQUIVALENT
    assert evidence.max_occupation_difference_e == evidence.max_fermi_difference_ev == 3e-5


def test_archived_mno_occupation_equivalence_does_not_require_fermi_tolerance() -> None:
    text = (
        ROOT
        / "campaigns/mno_afmii_strict_lr_v3r2/results/response-matrix-foreground-recovery-v4/00_REFERENCE/siesta.out"
    ).read_text(encoding="utf-8")
    evidence = reference_reproduction_evidence(
        text,
        text,
        FIRST,
        SECOND,
        ParentReproduction.PRINT_EQUIVALENT,
        scf_dm_tolerance=1e-5,
        tolerance_factor=1.0,
    )
    assert evidence.equivalent
    assert evidence.occupation_equivalence is OccupationEquivalence.EQUIVALENT
    assert evidence.fermi_equivalence is FermiEquivalence.RECORDED_NOT_ASSESSED


@pytest.mark.parametrize("value", [True, -1.0, float("nan"), float("inf")])
def test_domain_rejects_invalid_declared_fermi_tolerance(value: object) -> None:
    state = build_point_state(parse_hubbard_population_events(output())[-1], output())
    with pytest.raises(ValueError):
        compare_reference_states(state, state, FIRST, SECOND, tol_fermi_ev=value)  # type: ignore[arg-type]
