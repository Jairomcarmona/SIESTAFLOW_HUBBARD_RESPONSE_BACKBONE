"""D5 known contraction, print intervals, envelopes and TASK2 integration."""

from __future__ import annotations

import json
from dataclasses import replace
from fractions import Fraction
from random import Random

import pytest
from hypothesis import given
from hypothesis import strategies as st

from hubbardflow.domain.fdebq_matrix import qualify_matrices
from hubbardflow.domain.fdebq_models import ColumnEvidence, RoundReason, RoundStatus
from hubbardflow.domain.fdebq_rounds import decide_round, seed_requests, select_column
from hubbardflow.domain.response_budget_models import BoundKind, ElementSeries, PointObservation
from hubbardflow.domain.response_error_budget import printed_response_budget
from hubbardflow.domain.response_protocol import EstimatorKind, EstimatorSpec
from hubbardflow.domain.scf_budget_adapter import scf_element_report, scf_response_estimate
from hubbardflow.domain.scf_ladder import estimate_ladder
from hubbardflow.domain.scf_ladder_models import (
    LadderEvidence,
    ScfEnvelope,
    ScfLadderError,
    ScfLadderProtocol,
    ScfLevel,
    ScfStatus,
)
from hubbardflow.domain.symmetry_reduction import ResponseMode
from tests.unit.test_fdebq_rounds import GRID, columns
from tests.unit.test_fdebq_rounds import protocol as calibration_protocol


def policy() -> ScfLadderProtocol:
    return ScfLadderProtocol(
        "synthetic-v1", True, (ScfLevel("L0", 1e-3), ScfLevel("L1", 1e-5), ScfLevel("L2", 1e-7)), 2.0, 0.8
    )


def ladder(
    *,
    abs_error: float = 0.001,
    rel_error: float = 0.01,
    rho: float = 0.2,
    width: float = 0.00000001,
    chi: float = -1.0,
    grid: tuple[float, ...] = (0.01, 0.08),
) -> tuple[LadderEvidence, ...]:
    rows = []
    for level in range(3):
        points = []
        for a in grid:
            af = Fraction(str(a))
            error = Fraction(str(abs_error)) + Fraction(str(rel_error)) * abs(Fraction(str(chi)) * af)
            for sign in (-1, 1):
                n = sign * (Fraction(str(chi)) * af + error * Fraction(str(rho)) ** level / 2)
                points.append(PointObservation(sign * a, float(n), width))
        rows.append(
            LadderEvidence(
                f"L{level}", ElementSeries("j", ResponseMode.SCREENED, "i", 0.0, width, tuple(points))
            )
        )
    return tuple(rows)


def test_exact_d5_print_radii_and_mapping() -> None:
    p = policy()
    e = estimate_ladder(ladder(abs_error=0.01, rel_error=0.0, width=0.000001), p)
    a = e.amplitudes[0]
    assert a.eta1_plus_e == pytest.approx(0.008004)
    assert a.eta1_minus_e == pytest.approx(0.007996)
    assert a.eta2_plus_e == pytest.approx(0.001604)
    assert a.eta2_minus_e == pytest.approx(0.001596)
    assert a.rho_hat == pytest.approx(0.001604 / 0.007996)
    assert a.delta_estimate_e == pytest.approx(p.theta * a.eta1_plus_e / (1 - a.rho_hat))
    assert e.kind is BoundKind.ESTIMATE and e.status is ScfStatus.ESTABLISHED
    assert ScfEnvelope.from_mapping(json.loads(json.dumps(e.to_mapping()))) == e
    assert ScfLadderProtocol.from_mapping(p.to_mapping()) == p
    assert replace(p, theta=3.0).digest != p.digest
    assert replace(p, rho_max=0.7).digest != p.digest


@pytest.mark.parametrize("width", (0.0, 0.00001))
def test_zero_differences_use_declared_rho_and_cap_review(width: float) -> None:
    e = estimate_ladder(ladder(abs_error=0.0, rel_error=0.0, width=width), policy())
    assert e.status is ScfStatus.SCF_UNDER_RESOLVED and not e.qualified
    for a in e.amplitudes:
        assert a.rho_hat == policy().rho_max
        assert a.delta_estimate_e == pytest.approx(policy().theta * 4 * width / (1 - policy().rho_max))


def test_underresolved_nonzero_and_noncontractive_ladder() -> None:
    e = estimate_ladder(ladder(abs_error=0.000001, rel_error=0.0, width=0.00001), policy())
    assert e.status is ScfStatus.SCF_UNDER_RESOLVED
    failed = estimate_ladder(ladder(rho=0.9), policy())
    assert failed.status is ScfStatus.NOISE_FLOOR_NOT_ESTABLISHED
    assert failed.eps_abs_e is None and failed.eps_rel is None
    assert all(a.delta_estimate_e is None for a in failed.amplitudes)


def test_envelope_absolute_relative_and_response_radius() -> None:
    data = ladder(chi=1.0, width=0.0)
    envelope = estimate_ladder(data, policy())
    assert envelope.eps_abs_e is not None and envelope.eps_abs_e > 0
    assert envelope.eps_rel is not None and envelope.eps_rel > 0
    for amplitude in (0.01, 0.08):
        spec = EstimatorSpec(EstimatorKind.CENTRAL, None, (amplitude,))
        estimate = scf_response_estimate(data[0].series, spec, envelope)
        point = next(p for p in data[0].series.points if p.alpha_ev == amplitude)
        expected = (envelope.eps_abs_e + envelope.eps_rel * abs(point.occupation_e)) / amplitude
        assert estimate.radius_e_per_ev == pytest.approx(expected)
        assert estimate.kind is BoundKind.ESTIMATE
    assert envelope.covers((0.01, 0.04, 0.08))
    for a in (0.005, 0.1):
        assert not envelope.covers((a,))
        with pytest.raises(ScfLadderError, match="SCF_ENVELOPE_NOT_COVERED"):
            scf_response_estimate(data[0].series, EstimatorSpec(EstimatorKind.CENTRAL, None, (a,)), envelope)


def test_nonincreasing_response_magnitudes_are_all_absolute() -> None:
    data = ladder(chi=0.0, rel_error=0.0, width=0.0)
    envelope = estimate_ladder(data, policy())
    assert envelope.eps_rel == 0.0
    assert envelope.eps_abs_e == pytest.approx(0.001)


@given(st.permutations((0, 1, 2)))
def test_arrival_order_invariance(order: list[int]) -> None:
    data = ladder()
    shuffled = tuple(
        replace(data[i], series=replace(data[i].series, points=tuple(reversed(data[i].series.points))))
        for i in order
    )
    assert estimate_ladder(
        shuffled, replace(policy(), levels=tuple(reversed(policy().levels)))
    ) == estimate_ladder(data, policy())


@given(st.sampled_from([float("nan"), float("inf"), float("-inf"), True]))
def test_nonfinite_rejected(value: float | bool) -> None:
    with pytest.raises(ScfLadderError):
        replace(policy(), theta=value)
    raw = policy().to_mapping()
    raw["rho_max"] = value
    with pytest.raises(ScfLadderError):
        ScfLadderProtocol.from_mapping(raw)


def test_invalid_protocol_disabled_missing_levels_and_no_zero_replicas() -> None:
    for change in ({"theta": 0.0}, {"rho_max": 1.0}, {"rho_max": -0.1}, {"levels": policy().levels[:2]}):
        with pytest.raises(ScfLadderError):
            replace(policy(), **change)
    with pytest.raises(ScfLadderError, match="DISABLED"):
        estimate_ladder(ladder(), replace(policy(), enabled=False))
    with pytest.raises(ScfLadderError):
        estimate_ladder(ladder()[:2], policy())
    with pytest.raises(ValueError):
        PointObservation(0.0, 0.0, 0.0)


def test_known_truth_covered_in_400_absolute_relative_and_mixed_regimes() -> None:
    rng = Random(1705)
    for regime in ("absolute", "relative", "mixed"):
        for _ in range(400):
            abs_error = rng.uniform(0.00001, 0.0001) if regime != "relative" else 0.0
            rel_error = rng.uniform(0.001, 0.01) if regime != "absolute" else 0.0
            chi = rng.uniform(0.5, 2.0)
            data = ladder(abs_error=abs_error, rel_error=rel_error, chi=chi, rho=rng.uniform(0.1, 0.5))
            data = tuple(
                replace(
                    item,
                    series=replace(
                        item.series,
                        points=tuple(
                            replace(
                                point,
                                occupation_e=point.occupation_e
                                + rng.uniform(-point.half_width_e, point.half_width_e),
                            )
                            for point in item.series.points
                        ),
                    ),
                )
                for item in data
            )
            envelope = estimate_ladder(data, policy())
            assert envelope.qualified
            for a in (0.01, 0.08):
                spec = EstimatorSpec(EstimatorKind.CENTRAL, None, (a,))
                scf = scf_response_estimate(data[0].series, spec, envelope)
                printed = printed_response_budget(data[0].series, spec)
                assert (
                    abs(printed.estimate_e_per_ev - chi) <= printed.print_bound_e_per_ev + scf.radius_e_per_ev
                )


def measured_columns(*, underresolved: bool = False, bad_rho: bool = False) -> tuple[ColumnEvidence, ...]:
    result = []
    for column in columns(scf=False):
        envelopes = []
        for row in column.series:
            endpoint = replace(
                row, points=tuple(p for p in row.points if abs(p.alpha_ev) in (GRID[0], GRID[-1]))
            )
            evidence = []
            for level in range(3):
                rho = 0.9 if bad_rho else 0.2
                shift = 0.0 if underresolved else 0.0001 * (1 - rho**level)
                evidence.append(
                    LadderEvidence(
                        f"L{level}",
                        replace(
                            endpoint,
                            points=tuple(
                                replace(
                                    p,
                                    occupation_e=p.occupation_e
                                    - (shift / 2 if p.alpha_ev > 0 else -shift / 2),
                                )
                                for p in endpoint.points
                            ),
                        ),
                    )
                )
            envelopes.append(estimate_ladder(evidence, policy()))
        result.append(replace(column, scf_envelopes=tuple(envelopes)))
    return tuple(result)


def test_task16_uses_full_model_and_keeps_missing_state_validation_review() -> None:
    data = measured_columns()
    p = calibration_protocol()
    requests = seed_requests(("s0", "s1"), p)
    result = decide_round(data, p, requested=requests, terminal=requests)
    assert result.qualification.status is RoundStatus.QUALIFIED
    first = data[0]
    adapted = scf_element_report(
        first.series[0], first.scf_envelopes[0], protocol_estimator=None, kappa=p.kappa
    )
    for candidate in adapted.report.candidates:
        assert candidate.noise_kind is BoundKind.BOUND
        assert (
            candidate.noise_e_per_ev
            == printed_response_budget(first.series[0], candidate.estimator).print_bound_e_per_ev
        )
        assert candidate.truncation_kind is BoundKind.ESTIMATE
    assert all(e.kind is BoundKind.ESTIMATE for e in adapted.estimates)
    for changed, protocol in (
        (tuple(replace(c, state_gate_established=False) for c in data), p),
        (data, replace(p, t0_t4_result_sha256=None)),
        (measured_columns(underresolved=True), p),
        (measured_columns(bad_rho=True), p),
    ):
        decision = decide_round(changed, protocol, requested=requests, terminal=requests)
        assert decision.qualification.status is RoundStatus.REVIEW
    under = decide_round(measured_columns(underresolved=True), p, requested=requests, terminal=requests)
    assert RoundReason.SCF_UNDER_RESOLVED in under.qualification.reasons
    failed = decide_round(measured_columns(bad_rho=True), p, requested=requests, terminal=requests)
    assert RoundReason.NOISE_FLOOR_NOT_ESTABLISHED in failed.qualification.reasons
    assert type(data[0]).from_mapping(data[0].to_mapping()) == data[0]


def test_tampered_envelope_and_uncovered_order_tail_rejected() -> None:
    data = ladder()
    envelope = estimate_ladder(data, policy())
    with pytest.raises(ScfLadderError, match="does not match"):
        scf_response_estimate(
            data[0].series,
            EstimatorSpec(EstimatorKind.CENTRAL, None, (0.01,)),
            replace(envelope, eps_abs_e=0.0),
        )
    extended = replace(
        data[0].series,
        points=data[0].series.points + (PointObservation(-0.1, -0.1, 0.0), PointObservation(0.1, 0.1, 0.0)),
    )
    with pytest.raises(ScfLadderError, match="SCF_ENVELOPE_NOT_COVERED"):
        scf_element_report(extended, envelope, protocol_estimator=None, kappa=1.0)


def test_interior_amplitude_is_covered_and_relative_component_is_alpha_independent() -> None:
    all_data = ladder(abs_error=0.0, chi=1.0, rel_error=0.01, width=0.0, grid=(0.01, 0.02, 0.04, 0.08))
    endpoints = tuple(
        replace(
            item,
            series=replace(
                item.series,
                points=tuple(point for point in item.series.points if abs(point.alpha_ev) in (0.01, 0.08)),
            ),
        )
        for item in all_data
    )
    envelope = estimate_ladder(endpoints, policy())
    estimates = tuple(
        scf_response_estimate(all_data[0].series, EstimatorSpec(EstimatorKind.CENTRAL, None, (a,)), envelope)
        for a in (0.01, 0.02, 0.04, 0.08)
    )
    assert all(e.radius_e_per_ev == pytest.approx(estimates[0].radius_e_per_ev) for e in estimates)
    adapted = scf_element_report(all_data[0].series, envelope, protocol_estimator=None, kappa=1.0)
    assert adapted.report.candidates


def test_task16_uncovered_tail_returns_review() -> None:
    data = measured_columns()
    outside = tuple(
        replace(
            column,
            series=tuple(
                replace(
                    row,
                    points=row.points
                    + (PointObservation(-0.08, -0.08, 0.000001), PointObservation(0.08, 0.08, 0.000001)),
                )
                for row in column.series
            ),
        )
        for column in data
    )
    p = calibration_protocol()
    requests = seed_requests(("s0", "s1"), p)
    result = decide_round(outside, p, requested=requests, terminal=requests)
    assert result.qualification.status is RoundStatus.REVIEW
    assert RoundReason.SCF_ENVELOPE_NOT_COVERED in result.qualification.reasons


@pytest.mark.parametrize("exhausted", (False, True))
def test_underresolved_review_is_unconditional_when_matrix_fails_and_refinement_or_exhaustion(
    exhausted: bool,
) -> None:
    data = measured_columns(underresolved=True)
    p = calibration_protocol(tau=1e-12)
    if exhausted:
        p = replace(p, candidate_lattice_ev=GRID)
    # These same diagonal responses and nonzero print/SCF radii fail D4's
    # declared tiny requirement. D5(b) must still return REVIEW, including
    # when another amplitude exists or the lattice has been exhausted.
    sites = ("s0", "s1")
    centers = {mode: [[0.0] * 2 for _ in sites] for mode in ResponseMode}
    budgets = {mode: [[Fraction()] * 2 for _ in sites] for mode in ResponseMode}
    for column in data:
        selected = select_column(column, p)
        for element in selected.elements:
            i, j = sites.index(element.site_observed), sites.index(selected.site_id)
            centers[column.mode][i][j] = element.candidate.estimate_e_per_ev
            assert element.scf_estimate_e_per_ev is not None
            budgets[column.mode][i][j] = sum(
                (
                    Fraction(str(value))
                    for value in (
                        element.candidate.noise_e_per_ev,
                        element.candidate.truncation_e_per_ev,
                        element.scf_estimate_e_per_ev,
                    )
                ),
                Fraction(),
            )
    matrix = qualify_matrices(
        centers[ResponseMode.BARE],
        centers[ResponseMode.SCREENED],
        budgets[ResponseMode.BARE],
        budgets[ResponseMode.SCREENED],
        tau_u_ev=p.tau_u_ev,
    )
    assert not matrix.passed
    requests = seed_requests(("s0", "s1"), p)
    result = decide_round(data, p, requested=requests, terminal=requests)
    assert result.qualification.status is RoundStatus.REVIEW
    assert RoundReason.SCF_UNDER_RESOLVED in result.qualification.reasons
    assert not result.next_requests
