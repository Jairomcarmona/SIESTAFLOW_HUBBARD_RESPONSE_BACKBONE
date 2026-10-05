"""D3 shared estimators, deterministic barriers, model bounds and D4 U gates."""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
from hashlib import sha256
from random import Random
from typing import cast

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from hubbardflow.domain.fdebq_matrix import LABEL, column_influences, full_budget_box, qualify_matrices
from hubbardflow.domain.fdebq_models import (
    CalibrationProtocol,
    ColumnEvidence,
    FdebqRoundsError,
    RoundDecision,
    RoundReason,
    RoundRequest,
    RoundStatus,
    ScfCandidateEstimate,
)
from hubbardflow.domain.fdebq_rounds import decide_round, production_column_plan, seed_requests, select_column
from hubbardflow.domain.response_error_budget import (
    BoundKind,
    ElementSeries,
    NoiseModel,
    PointObservation,
    element_report,
)
from hubbardflow.domain.response_protocol import EstimatorKind, EstimatorSpec
from hubbardflow.domain.symmetry_reduction import ResponseMode
from hubbardflow.domain.u_certification import certify_u_matrices

GRID = (0.005, 0.01, 0.02, 0.04)
LATTICE = GRID + (0.08,)


def protocol(*, tau: float = 0.1, rounds: int = 8, validation: bool = True) -> CalibrationProtocol:
    synthetic_digest = sha256(b"synthetic-known-model-validation-only").hexdigest()
    return CalibrationProtocol(
        "test-v1", LATTICE, GRID, GRID, rounds, 1.0, tau, "L0", synthetic_digest if validation else None
    )


def series(
    j: str,
    mode: ResponseMode,
    i: str,
    *,
    chi: float,
    k: float = 0.0,
    b1: float = 0.0,
    width: float = 0.000001,
    grid: tuple[float, ...] = GRID,
) -> ElementSeries:
    points = []
    for magnitude in grid:
        for sign in (-1, 1):
            a = Fraction(str(magnitude)) * sign
            value = Fraction(str(chi)) * a + Fraction(str(k)) * a * abs(a) + Fraction(str(b1)) * a**3
            points.append(PointObservation(float(a), float(value), width))
    return ElementSeries(j, mode, i, 0.0, width, tuple(points))


def columns(
    *, scf: bool, state: bool = True, width: float = 0.000001, grid: tuple[float, ...] = GRID
) -> tuple[ColumnEvidence, ...]:
    result = []
    for j in ("s0", "s1"):
        for mode in ResponseMode:
            rows = tuple(
                series(j, mode, i, chi=-2.0 if mode is ResponseMode.BARE else -1.0, width=width, grid=grid)
                if i == j
                else series(j, mode, i, chi=0.0, width=width, grid=grid)
                for i in ("s0", "s1")
            )
            estimates: list[ScfCandidateEstimate] = []
            if scf:
                for row in rows:
                    report = element_report(row, NoiseModel(), protocol_estimator=None, kappa=1.0)
                    estimates.extend(
                        ScfCandidateEstimate(
                            row.site_observed, c.estimator, width, BoundKind.ESTIMATE, True, True
                        )
                        for c in report.candidates
                    )
            result.append(ColumnEvidence(j, mode, rows, (), tuple(estimates), state))
    return tuple(result)


def decide(data: tuple[ColumnEvidence, ...], p: CalibrationProtocol) -> RoundDecision:
    requests = seed_requests(("s0", "s1"), p)
    return decide_round(data, p, requested=requests, terminal=requests)


def test_tau_required_protocol_digest_mapping_and_four_scales() -> None:
    p = protocol()
    assert CalibrationProtocol.from_mapping(p.to_mapping()) == p
    assert replace(p, tau_u_ev=0.2).digest != p.digest
    assert replace(p, max_rounds=9).digest != p.digest
    for seed in ((0.005, 0.01, 0.02), (0.005, 0.01, 0.02, 0.02001)):
        with pytest.raises(FdebqRoundsError):
            replace(p, seed_bare_ev=seed)
    raw = p.to_mapping()
    del raw["tau_u_ev"]
    with pytest.raises(ValueError):
        CalibrationProtocol.from_mapping(raw)


@given(st.sampled_from([float("nan"), float("inf"), float("-inf"), True]))
def test_nonfinite_protocol_rejected(value: float | bool) -> None:
    with pytest.raises(ValueError):
        replace(protocol(), tau_u_ev=value)
    with pytest.raises(ValueError):
        replace(protocol(), candidate_lattice_ev=(value,) + LATTICE)


def test_column_minimax_differs_from_per_row_diagnostic_and_uses_one_functional() -> None:
    p = protocol()
    data = columns(scf=True)[0]
    first, second = (
        EstimatorSpec(EstimatorKind.CENTRAL, None, (GRID[0],)),
        EstimatorSpec(EstimatorKind.CENTRAL, None, (GRID[1],)),
    )
    estimates = []
    for estimate in data.scf_estimates:
        radius = 10.0
        if estimate.estimator == first:
            radius = 0.0 if estimate.site_observed == "s0" else 0.2
        elif estimate.estimator == second:
            radius = 0.1
        estimates.append(replace(estimate, radius_e_per_ev=radius))
    chosen = select_column(replace(data, scf_estimates=tuple(estimates)), p)
    assert chosen.estimator == second
    assert all(e.candidate.estimator == second for e in chosen.elements)
    plan = production_column_plan(chosen, p)
    assert plan is not None and plan.estimator == second
    assert plan.amplitudes_ev == second.amplitudes_ev
    assert any(best is not None and best.estimator != second for _, best in chosen.diagnostic_best)


def test_tie_break_amplitude_then_family_then_full_grid() -> None:
    data = columns(scf=False, width=0.0)[0]
    chosen = select_column(data, protocol())
    assert chosen.estimator == EstimatorSpec(EstimatorKind.CENTRAL, None, (GRID[0],))
    estimates = tuple(
        ScfCandidateEstimate(
            row.site_observed,
            c.estimator,
            0.0,
            BoundKind.ESTIMATE,
            max(c.estimator.amplitudes_ev) == GRID[1],
            True,
        )
        for row in data.series
        for c in element_report(row, NoiseModel(), protocol_estimator=None, kappa=1.0).candidates
    )
    chosen = select_column(replace(data, scf_estimates=estimates), protocol())
    assert chosen.estimator == EstimatorSpec(EstimatorKind.CENTRAL, None, (GRID[1],))
    # Unlike the zero-drift test above, both families are admissible here.
    rows = tuple(series("s0", ResponseMode.BARE, i, chi=0.0, b1=1.0, width=0.0) for i in ("s0", "s1"))
    estimates = tuple(
        ScfCandidateEstimate(
            row.site_observed,
            c.estimator,
            0.0001 if c.estimator.kind is EstimatorKind.RICHARDSON_2 else 0.0,
            BoundKind.ESTIMATE,
            max(c.estimator.amplitudes_ev) == GRID[1],
            True,
        )
        for row in rows
        for c in element_report(row, NoiseModel(), protocol_estimator=None, kappa=1.0).candidates
    )
    evidence = ColumnEvidence("s0", ResponseMode.BARE, rows, (), estimates, True)
    chosen = select_column(evidence, protocol())
    assert chosen.estimator == EstimatorSpec(EstimatorKind.CENTRAL, None, (GRID[1],))


def test_underresolved_scf_estimate_caps_review_even_with_a_radius() -> None:
    data = tuple(
        replace(c, scf_estimates=tuple(replace(e, qualified=False) for e in c.scf_estimates))
        for c in columns(scf=True)
    )
    result = decide(data, protocol())
    assert result.qualification.status is RoundStatus.REVIEW
    assert RoundReason.SCF_ESTIMATE_MISSING in result.qualification.reasons
    assert all(e.scf_estimate_e_per_ev is not None for c in result.qualification.columns for e in c.elements)


def test_candidate_must_be_admissible_in_every_row_and_scf_envelope() -> None:
    data = columns(scf=True)[0]
    rejected = replace(
        data,
        scf_estimates=tuple(
            replace(e, admissible=False) if e.site_observed == "s1" else e for e in data.scf_estimates
        ),
    )
    assert select_column(rejected, protocol()).estimator is None
    partial = replace(data, scf_estimates=tuple(e for e in data.scf_estimates if e.site_observed == "s0"))
    assert select_column(partial, protocol()).estimator is None


def test_barrier_shuffled_arrival_waits_then_identical_decision_and_roundtrip() -> None:
    p = protocol()
    data = columns(scf=True)
    req = seed_requests(("s0", "s1"), p)
    waiting = decide_round(data, p, requested=req, terminal=req[:-1])
    assert waiting.qualification.status is RoundStatus.WAITING
    assert waiting.qualification.columns == ()
    ready = decide_round(
        tuple(reversed(data)), p, requested=tuple(reversed(req)), terminal=tuple(reversed(req))
    )
    assert ready == decide(data, p)
    assert ready.qualification.status is RoundStatus.QUALIFIED
    assert RoundDecision.from_mapping(ready.to_mapping()) == ready
    assert ready.qualification.label == LABEL


@given(st.permutations(tuple(range(4))))
def test_input_order_invariance(order: list[int]) -> None:
    data = columns(scf=True)
    assert decide(tuple(data[i] for i in order), protocol()) == decide(data, protocol())


def test_missing_scf_or_state_never_above_review_and_bad_evidence_fails() -> None:
    for data, reason in (
        (columns(scf=False), RoundReason.SCF_ESTIMATE_MISSING),
        (columns(scf=True, state=False), RoundReason.SCIENTIFIC_STATE_NOT_ESTABLISHED),
    ):
        result = decide(data, protocol())
        assert result.qualification.status is RoundStatus.REVIEW
        assert reason in result.qualification.reasons
    unvalidated = decide(columns(scf=True), protocol(validation=False))
    assert unvalidated.qualification.status is RoundStatus.REVIEW
    assert RoundReason.VALIDATION_NOT_ESTABLISHED in unvalidated.qualification.reasons
    with pytest.raises(FdebqRoundsError, match="same amplitudes"):
        replace(
            columns(scf=False)[0],
            series=(
                columns(scf=False)[0].series[0],
                replace(
                    columns(scf=False)[0].series[1],
                    points=tuple(
                        p for p in columns(scf=False)[0].series[1].points if abs(p.alpha_ev) != GRID[-1]
                    ),
                ),
            ),
        )
    with pytest.raises(FdebqRoundsError, match="terminal request lacks"):
        decide(columns(scf=False, grid=GRID[:-1]), protocol())


def test_no_common_candidate_requests_next_scale_then_not_established() -> None:
    p = protocol()
    data = columns(scf=True)
    bad = replace(data[0], scf_estimates=tuple(replace(e, admissible=False) for e in data[0].scf_estimates))
    result = decide((bad,) + data[1:], p)
    assert result.qualification.status is RoundStatus.CONTINUE
    assert result.next_requests == (
        RoundRequest("s0", ResponseMode.BARE, -0.08),
        RoundRequest("s0", ResponseMode.BARE, 0.08),
    )
    assert RoundReason.NO_COMMON_ESTIMATOR in result.qualification.reasons
    exhausted = replace(p, candidate_lattice_ev=GRID)
    result = decide((bad,) + data[1:], exhausted)
    assert result.qualification.status is RoundStatus.NOT_ESTABLISHED
    assert RoundReason.LATTICE_EXHAUSTED in result.qualification.reasons
    result = decide((bad,) + data[1:], replace(p, max_rounds=1))
    assert result.qualification.status is RoundStatus.REVIEW
    assert RoundReason.MAX_ROUNDS in result.qualification.reasons


def test_monotone_failed_scale_excludes_all_larger_scales() -> None:
    data = columns(scf=False)[0]
    failed = replace(data, failed_amplitudes_ev=(0.02,))
    assert select_column(failed, protocol()).estimator is None
    all_data = columns(scf=False)
    result = decide((failed,) + all_data[1:], protocol())
    assert result.qualification.status is RoundStatus.NOT_ESTABLISHED
    assert not result.next_requests  # 0.08 is excluded, not requested.


def test_column_influence_uses_absolute_inverse_products_and_next_highest() -> None:
    bare = np.array([[-2.0, 0.2], [0.1, -3.0]])
    screened = np.array([[-1.0, 0.1], [0.1, -2.0]])
    b0 = np.array([[0.01, 0.2], [0.02, 0.3]])
    b = np.array([[0.1, 0.02], [0.2, 0.03]])
    actual = column_influences(bare, screened, b0, b)
    for values, matrix, budget in zip(actual, (bare, screened), (b0, b), strict=True):
        inverse = np.linalg.inv(matrix)
        expected = tuple(
            max(sum(abs(inverse[k, i] * inverse[j, k]) * budget[i, j] for i in range(2)) for k in range(2))
            for j in range(2)
        )
        assert values == pytest.approx(expected)
    data = list(columns(scf=True, width=0.0001))
    data[-1] = replace(
        data[-1], scf_estimates=tuple(replace(e, radius_e_per_ev=0.01) for e in data[-1].scf_estimates)
    )
    result = decide(tuple(data), protocol(tau=0.000001))
    assert result.qualification.status is RoundStatus.CONTINUE
    assert {r.site_id for r in result.next_requests} == {"s1"}
    assert {r.mode for r in result.next_requests} == {ResponseMode.SCREENED}


def test_full_elementwise_box_calls_existing_routines_and_covers_truth() -> None:
    bare, screened = ((-2.0, 0.1), (0.2, -3.0)), ((-1.0, 0.2), (0.1, -2.0))
    b0 = ((Fraction("0.01"), Fraction("0.02")), (Fraction("0.03"), Fraction("0.04")))
    b = ((Fraction("0.02"), Fraction("0.01")), (Fraction("0.04"), Fraction("0.03")))
    box0, box = full_budget_box(bare, b0), full_budget_box(screened, b)
    assert box0[1][0].hi - box0[1][0].lo == 2 * b0[1][0]
    expected = certify_u_matrices(box0, box)
    result = qualify_matrices(bare, screened, b0, b, tau_u_ev=0.2)
    assert result.passed and result.half_width_u_ev == tuple(
        float(Fraction(v)) for v in cast(list[str], expected["half_width_by_site"])
    )
    assert not qualify_matrices(bare, screened, b0, b, tau_u_ev=0.000001).passed
    # Actual U is evaluated only in this synthetic ground-truth check.
    truth = np.diag(np.linalg.inv(np.array(bare)) - np.linalg.inv(np.array(screened)))
    intervals = cast(list[dict[str, str]], expected["u_interval_by_site"])
    for value, interval in zip(truth, intervals, strict=True):
        assert float(Fraction(interval["lower"])) <= value <= float(Fraction(interval["upper"]))


def test_strict_beta_gate_and_singular_direct_inversion_error() -> None:
    matrix = ((1.0, 0.0), (0.0, 1.0))
    exact_one = ((Fraction(1), Fraction(0)), (Fraction(0), Fraction(0)))
    zero = ((Fraction(0), Fraction(0)), (Fraction(0), Fraction(0)))
    result = qualify_matrices(matrix, matrix, exact_one, zero, tau_u_ev=100.0)
    assert result.beta0 == 1 and not result.passed
    assert result.reasons == (RoundReason.MATRIX_NOT_RESOLVED,)
    with pytest.raises(FdebqRoundsError, match="nonsingular"):
        qualify_matrices(((1.0, 1.0), (1.0, 1.0)), matrix, zero, zero, tau_u_ev=1.0)


def test_no_condition_number_or_u_stability_inputs_enter_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    import inspect

    baseline = decide(columns(scf=True), protocol())

    def forbidden(*args: object, **kwargs: object) -> float:
        raise AssertionError("condition number must never select calibrated experiments")

    monkeypatch.setattr(np.linalg, "cond", forbidden)
    assert decide(columns(scf=True), protocol()) == baseline
    assert set(inspect.signature(decide_round).parameters) == {"columns", "protocol", "requested", "terminal"}
    assert set(inspect.signature(select_column).parameters) == {"evidence", "protocol"}
    # Changing the U-space tolerance does not change the column functional.
    assert select_column(columns(scf=True)[0], protocol(tau=1.0)) == select_column(
        columns(scf=True)[0], protocol(tau=0.001)
    )


def test_reciprocity_falsification_caps_review_without_symmetrizing() -> None:
    data = list(columns(scf=True))
    row = series("s0", ResponseMode.BARE, "s1", chi=0.001)
    data[0] = replace(data[0], series=(data[0].series[0], row))
    result = decide(tuple(data), protocol())
    assert result.qualification.status is RoundStatus.REVIEW
    assert RoundReason.BUDGET_FALSIFIED in result.qualification.reasons
    assert result.qualification.columns[0].elements[1].candidate.estimate_e_per_ev == 0.001


def test_cancelling_mixed_scales_are_unresolved_instead_of_qualified() -> None:
    row = series("s0", ResponseMode.BARE, "s0", chi=-1.0, k=-0.08, b1=1.0, width=0.0)
    selection = select_column(ColumnEvidence("s0", ResponseMode.BARE, (row,), (), (), True), protocol())
    assert selection.estimator is None


@given(st.integers(2, 5), st.integers(0, 10))
def test_verified_larger_matrix_boxes_cover_known_perturbations(n: int, integer_radius: int) -> None:
    center0 = np.diag(np.arange(2, n + 2, dtype=float))
    center = center0 + np.eye(n)
    radius = Fraction(integer_radius, 10000)
    radii = tuple(tuple(radius if i == j else Fraction() for j in range(n)) for i in range(n))
    evaluation = qualify_matrices(center0.tolist(), center.tolist(), radii, radii, tau_u_ev=1.0)
    assert evaluation.passed
    box0, box = full_budget_box(center0.tolist(), radii), full_budget_box(center.tolist(), radii)
    result = certify_u_matrices(box0, box)
    intervals = cast(list[dict[str, str]], result["u_interval_by_site"])
    truth = tuple(
        1 / (Fraction(str(center0[i, i])) + radius) - 1 / (Fraction(str(center[i, i])) - radius)
        for i in range(n)
    )
    for actual, interval in zip(truth, intervals, strict=True):
        assert Fraction(interval["lower"]) <= actual <= Fraction(interval["upper"])


@pytest.mark.parametrize("regime", ("analytic", "nonanalytic", "mixed"))
def test_400_random_ground_truth_cases_per_regime(regime: str) -> None:
    rng = Random(8016)
    for _ in range(400):
        chi = -rng.uniform(0.1, 4.0)
        coefficient = rng.uniform(0.1, 2.0)
        k = coefficient if regime in ("nonanalytic", "mixed") else 0.0
        b1 = coefficient if regime in ("analytic", "mixed") else 0.0
        width = rng.uniform(1e-10, 1e-9)
        row = series("s0", ResponseMode.BARE, "s0", chi=chi, k=k, b1=b1, width=width)
        row = replace(
            row,
            points=tuple(
                replace(p, occupation_e=p.occupation_e + rng.uniform(-width, width)) for p in row.points
            ),
        )
        evidence = ColumnEvidence("s0", ResponseMode.BARE, (row,), (), (), True)
        selected = select_column(evidence, protocol())
        assert selected.estimator is not None
        element = selected.elements[0]
        candidate = element.candidate
        assert abs(candidate.estimate_e_per_ev - chi) <= candidate.total_e_per_ev


@pytest.mark.parametrize("digest", [None, "", "malformed"])
def test_round_evidence_digest_is_optional_without_changing_qualification(digest):
    from hubbardflow.domain.fdebq_models import CalibrationQualification

    original = decide(columns(scf=True), protocol()).qualification
    raw = original.to_mapping()
    if digest is None:
        raw.pop("evidence_sha256")
    else:
        raw["evidence_sha256"] = digest
    restored = CalibrationQualification.from_mapping(raw)
    assert restored.status is original.status
    assert restored.columns == original.columns
    assert restored.matrix == original.matrix
    assert restored.reasons == original.reasons
