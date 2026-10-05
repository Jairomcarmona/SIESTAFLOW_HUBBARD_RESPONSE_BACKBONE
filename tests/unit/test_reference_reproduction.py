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
    ParentReproduction,
    ReferenceReproduction,
    ReferenceReproductionError,
    ReproductionReason,
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


def test_identical_printed_state_accepts_different_dm_bytes() -> None:
    evidence = reference_reproduction_evidence(
        output(), output(), FIRST, SECOND, ParentReproduction.PRINT_EQUIVALENT
    )
    assert evidence.equivalent
    assert evidence.planning_parent_dm_sha256 != evidence.campaign_parent_dm_sha256
    assert evidence.max_occupation_difference_e == 0.0
    assert evidence.max_fermi_difference_ev == 0.0
    assert evidence.occupation_comparison_quanta_e == (1e-5,)
    assert evidence.fermi_comparison_quantum_ev == 1e-5
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
    assert evidence.equivalent is (abs(quanta) <= 1)
    assert evidence.max_occupation_difference_e == float(Decimal(abs(quanta)) * Decimal("0.00001"))
    if abs(quanta) >= 2:
        assert evidence.reason is ReproductionReason.PARENT_STATE_NOT_EQUIVALENT
        assert "atom 1 spin up element (1,2)" in evidence.detail
        assert "quantum 0.00001" in evidence.detail


@pytest.mark.parametrize("fermi, equivalent", [("1.00001", True), ("1.00002", False), ("0.99998", False)])
def test_fermi_quantum_boundary(fermi: str, equivalent: bool) -> None:
    evidence = reference_reproduction_evidence(
        output(), output(fermi=fermi), FIRST, SECOND, ParentReproduction.PRINT_EQUIVALENT
    )
    assert evidence.equivalent is equivalent
    if not equivalent:
        assert "Fermi: difference" in evidence.detail


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
    assert evidence.reason is ReproductionReason.PARENT_STATE_NOT_EQUIVALENT
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
def test_bitwise_retains_legacy_dm_comparison(matches: bool) -> None:
    evidence = reference_reproduction_evidence(
        "",
        "",
        FIRST,
        FIRST if matches else SECOND,
        ParentReproduction.BITWISE,
    )
    assert evidence.equivalent is matches
    assert evidence.reason is (
        ReproductionReason.EQUIVALENT if matches else ReproductionReason.PARENT_DM_NOT_REPRODUCED
    )


def test_frozen_mno_printed_reference_regression() -> None:
    text = (
        ROOT
        / "campaigns/mno_afmii_strict_lr_v3r2/results/response-matrix-foreground-recovery-v4/00_REFERENCE/siesta.out"
    ).read_text(encoding="utf-8")
    result = reference_reproduction_evidence(text, text, FIRST, SECOND, ParentReproduction.PRINT_EQUIVALENT)
    assert result.equivalent


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
