"""Synthetic truth, strict order, exact moments, and frozen diagnostic checks."""

from __future__ import annotations

import json
from dataclasses import replace
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from hubbardflow.domain.response_budget_moments import estimator_moments
from hubbardflow.domain.response_error_budget import (
    BoundKind,
    BudgetReason,
    CandidateBudget,
    ElementBudgetReport,
    ElementSeries,
    NoiseModel,
    OddEvenDecomposition,
    OrderStatus,
    PointObservation,
    QualificationCap,
    ResponseBudgetError,
    candidate_budgets,
    decompose,
    element_report,
    reciprocity,
    u_influence,
    verify_order,
)
from hubbardflow.domain.response_protocol import EstimatorKind, EstimatorSpec
from hubbardflow.domain.symmetry_reduction import ResponseMode

V6 = (0.02, 0.04, 0.06)
GEOMETRIC = (0.005, 0.01, 0.02, 0.04, 0.08)


def series(
    *,
    grid: tuple[float, ...] = V6,
    chi: str = "-1",
    b1: str = "0",
    b2: str = "0",
    k: str = "0",
    even: tuple[str, str, str] = ("0", "0", "0"),
    width: float = 0.0,
    rounded: bool = False,
    offset: float = 0.0,
) -> ElementSeries:
    points = []
    for magnitude in grid:
        for sign in (-1, 1):
            a = sign * Fraction(str(magnitude))
            occupation = (
                Fraction(chi) * a
                + Fraction(b1) * a**3
                + Fraction(b2) * a**5
                + Fraction(k) * a * abs(a)
                + Fraction(even[0])
                + Fraction(even[1]) * a**2
                + Fraction(even[2]) * a**4
            )
            value = float(occupation)
            if rounded:
                value = round(value, 6)
            points.append(PointObservation(float(a), value, width))
    return ElementSeries("J", ResponseMode.BARE, "I", offset, width, tuple(points))


def report(data: ElementSeries, spec: EstimatorSpec | None = None) -> ElementBudgetReport:
    return element_report(data, NoiseModel(), protocol_estimator=spec, kappa=1.0)


def protocol(kind: EstimatorKind, grid: tuple[float, ...] = V6) -> EstimatorSpec:
    return EstimatorSpec(kind, 3 if kind is EstimatorKind.POLYNOMIAL_LSQ else None, grid)


def candidates(result: ElementBudgetReport, kind: EstimatorKind) -> list[CandidateBudget]:
    return [value for value in result.candidates if value.estimator.kind is kind]


def test_exact_v6_moments_and_j0() -> None:
    linear = estimator_moments(protocol(EstimatorKind.LINEAR_LSQ))
    cubic = estimator_moments(protocol(EstimatorKind.POLYNOMIAL_LSQ))
    rich = estimator_moments(EstimatorSpec(EstimatorKind.RICHARDSON_2, None, V6[:2]))
    assert linear.j0 == 1 and linear.moments[0] == Fraction(7, 2500)
    assert cubic.j0 == rich.j0 == 2
    assert cubic.moments[0] == rich.moments[0] == 0
    assert cubic.weights == (Fraction(29, 63), Fraction(67, 63), Fraction(-33, 63))
    assert cubic.moments[1] == Fraction(-131, 32_812_500)
    assert rich.moments[1] == -(Fraction("0.02") ** 2) * Fraction("0.04") ** 2
    # Cancellation remains exact even when the first surviving moment is tiny.
    tiny = estimator_moments(protocol(EstimatorKind.POLYNOMIAL_LSQ, (0.0001, 0.0002, 0.0003)))
    assert tiny.moments[0] == 0 and tiny.moments[1] != 0 and tiny.j0 == 2


def test_linear_protocol_cubic_truth_and_order_two() -> None:
    result = report(series(b1="2"), protocol(EstimatorKind.LINEAR_LSQ))
    assert verify_order(result.decomposition) == (OrderStatus.VERIFIED_2,)
    central = candidates(result, EstimatorKind.CENTRAL)
    assert [value.moment_ratio for value in central[:2]] == [Fraction(4), Fraction(9, 4)]
    assert all(value.p_used == 2 for value in central)
    linear = result.candidates[-1]
    assert linear.admissible and linear.truncation_e_per_ev > 0
    assert linear.truncation_e_per_ev == float(Fraction("0.0028") * 2)
    assert abs(linear.estimate_e_per_ev + 1) <= linear.total_e_per_ev + 1e-15
    for kind in (EstimatorKind.RICHARDSON_2, EstimatorKind.POLYNOMIAL_LSQ):
        spec = EstimatorSpec(
            kind,
            3 if kind is EstimatorKind.POLYNOMIAL_LSQ else None,
            V6 if kind is EstimatorKind.POLYNOMIAL_LSQ else V6[:2],
        )
        assert estimator_moments(spec).moments[0] == 0


def test_richardson_v6_q_nine_and_formula_noise() -> None:
    # The known b2 term is below the print interval in the strict order test.
    data = series(b1="10", b2="1", width=5e-7)
    result = report(data)
    rich = candidates(result, EstimatorKind.RICHARDSON_2)[0]
    neighbour = candidates(result, EstimatorKind.RICHARDSON_2)[1]
    assert rich.order_status is OrderStatus.VERIFIED_2
    assert rich.moment_ratio == 9
    true_bias = abs(float(estimator_moments(rich.estimator).moments[1]))
    assert abs(abs(rich.estimate_e_per_ev + 1) - true_bias) <= 1e-15
    formula = (
        abs(rich.estimate_e_per_ev - neighbour.estimate_e_per_ev)
        + rich.noise_e_per_ev
        + neighbour.noise_e_per_ev
    ) / 8
    assert rich.truncation_e_per_ev == pytest.approx(formula, abs=1e-15)
    assert true_bias <= rich.truncation_e_per_ev


def test_geometric_richardson_regression() -> None:
    result = report(series(grid=GEOMETRIC, b1="1"))
    for value in candidates(result, EstimatorKind.RICHARDSON_2)[:-1]:
        assert value.moment_ratio == Fraction(2) ** 4
        assert value.truncation_e_per_ev == 0


def test_nonanalytic_zero_noise_order_one_and_exact_bias() -> None:
    result = report(series(k="0.8"), protocol(EstimatorKind.POLYNOMIAL_LSQ))
    assert verify_order(result.decomposition) == (OrderStatus.VERIFIED_1,)
    central = candidates(result, EstimatorKind.CENTRAL)
    assert [value.moment_ratio for value in central[:2]] == [Fraction(2), Fraction(3, 2)]
    for value, amplitude in zip(central[:2], V6[:2], strict=True):
        assert value.admissible and value.p_used == 1
        assert value.truncation_e_per_ev == float(Fraction(str(amplitude)) * Fraction("0.8"))
        assert BudgetReason.ORDER_1_VERIFIED in value.reasons
    for value in result.candidates:
        if value.j0 >= 2:
            assert not value.admissible
            assert BudgetReason.ORDER_NOT_VERIFIED_FOR_ESTIMATOR in value.reasons


def test_preasymptotic_mixes_are_unresolved_but_opposite_sign_is_inconsistent() -> None:
    for data in (series(b1="1", k="1"), series(b1="1", b2="-50"), series(b1="1", b2="1000")):
        result = report(data, protocol(EstimatorKind.POLYNOMIAL_LSQ))
        assert verify_order(result.decomposition) == (OrderStatus.UNRESOLVED,)
        assert result.best is not None and result.best.admissible
        assert result.best.p_used == 1

    opposite_sign = report(series(b1="1", k="-0.08"), protocol(EstimatorKind.POLYNOMIAL_LSQ))
    assert verify_order(opposite_sign.decomposition) == (OrderStatus.INCONSISTENT,)
    assert opposite_sign.best is None
    assert all(
        not value.admissible and BudgetReason.ORDER_INCONSISTENT in value.reasons
        for value in opposite_sign.candidates
    )

    below_rho1 = report(series(b1="1", k="-2"), protocol(EstimatorKind.POLYNOMIAL_LSQ))
    assert verify_order(below_rho1.decomposition) == (OrderStatus.INCONSISTENT,)


def test_unresolved_drift_and_overlap_use_conservative_order() -> None:
    for data in (series(b1="0.0001", width=5e-7), series(b1="1", width=0.0001)):
        result = report(data)
        assert verify_order(result.decomposition) == (OrderStatus.UNRESOLVED,)
        assert result.best is not None and result.best.admissible
        assert result.best.p_used == 1
        assert BudgetReason.ORDER_UNRESOLVED_CONSERVATIVE_P1 in result.best.reasons


def test_r2_tail_unresolved_only_for_cancelling_estimators() -> None:
    result = report(series(b1="1"), protocol(EstimatorKind.POLYNOMIAL_LSQ))
    cubic = result.candidates[-1]
    assert cubic.j0 == 2 and not cubic.admissible
    assert BudgetReason.TAIL_UNRESOLVED in cubic.reasons
    assert cubic.truncation_kind is BoundKind.ESTIMATE
    assert cubic.noise_kind is BoundKind.BOUND
    assert all(
        BudgetReason.TAIL_UNRESOLVED not in value.reasons
        for value in candidates(result, EstimatorKind.CENTRAL)
    )


def test_tail_candidate_cannot_worsen_existing_eligible_selection() -> None:
    data = series(b1="1")
    baseline = report(data)
    augmented = report(data, protocol(EstimatorKind.POLYNOMIAL_LSQ))
    assert BudgetReason.TAIL_UNRESOLVED in augmented.candidates[-1].reasons
    assert augmented.best == baseline.best
    assert augmented.qualification_cap is baseline.qualification_cap is None
    assert augmented.reasons == baseline.reasons == ()


def test_tail_only_fallback_selects_best_and_caps_at_review(monkeypatch: pytest.MonkeyPatch) -> None:
    import hubbardflow.domain.response_error_budget as module

    data = series(b1="1")
    original = report(data, protocol(EstimatorKind.POLYNOMIAL_LSQ))
    tail = original.candidates[-1]
    assert BudgetReason.TAIL_UNRESOLVED in tail.reasons
    worse_tail = replace(tail, truncation_e_per_ev=tail.truncation_e_per_ev + 1)

    def only_tail(*args: object, **kwargs: object) -> tuple[CandidateBudget, ...]:
        return (worse_tail, tail)

    monkeypatch.setattr(module, "candidate_budgets", only_tail)
    result = report(data)
    assert result.best == tail
    assert result.qualification_cap is QualificationCap.REVIEW
    assert result.reasons == (BudgetReason.TAIL_UNRESOLVED,)
    assert ElementBudgetReport.from_mapping(result.to_mapping()) == result


@given(st.permutations(tuple(range(6))))
def test_point_order_invariance(order: list[int]) -> None:
    data = series(b1="2", width=5e-7)
    permuted = replace(data, points=tuple(data.points[index] for index in order))
    assert report(permuted, protocol(EstimatorKind.POLYNOMIAL_LSQ)) == report(
        data, protocol(EstimatorKind.POLYNOMIAL_LSQ)
    )


@given(st.integers(-10, 10), st.integers(-10, 10), st.integers(-10, 10), st.integers(-10, 10))
def test_even_function_and_reference_invariance(c0: int, c2: int, c4: int, offset: int) -> None:
    baseline = report(series(b1="2", width=5e-7), protocol(EstimatorKind.POLYNOMIAL_LSQ))
    shifted = report(
        series(b1="2", even=(str(c0), str(c2), str(c4)), offset=float(offset), width=5e-7),
        protocol(EstimatorKind.POLYNOMIAL_LSQ),
    )
    assert shifted.decomposition.slopes_e_per_ev == pytest.approx(
        baseline.decomposition.slopes_e_per_ev, abs=1e-12
    )
    for actual, expected in zip(shifted.candidates, baseline.candidates, strict=True):
        assert actual.estimate_e_per_ev == pytest.approx(expected.estimate_e_per_ev, abs=1e-12)
        assert actual.truncation_e_per_ev == pytest.approx(expected.truncation_e_per_ev, abs=1e-12)


@given(st.sampled_from([float("nan"), float("inf"), float("-inf"), True, False]))
def test_invalid_numbers_rejected(value: float | bool) -> None:
    for key in ("alpha_ev", "occupation_e", "half_width_e"):
        payload: dict[str, object] = {"alpha_ev": 0.02, "occupation_e": 7.0, "half_width_e": 5e-7}
        payload[key] = value
        with pytest.raises(ResponseBudgetError):
            PointObservation.from_mapping(payload)
    with pytest.raises(ResponseBudgetError):
        element_report(series(), NoiseModel(), protocol_estimator=None, kappa=value)


def test_invalid_pairs_noise_and_serialization() -> None:
    data = series(b1="2", width=5e-7)
    for points in (
        data.points[:-1],
        data.points + (data.points[0],),
        (),
        (PointObservation(-0.01, 7.0, 0.0), PointObservation(0.02, 7.0, 0.0)),
    ):
        with pytest.raises(ResponseBudgetError):
            replace(data, points=points)
    with pytest.raises(ResponseBudgetError):
        NoiseModel(eps_abs_e=1e-6)
    with pytest.raises(ResponseBudgetError):
        PointObservation(0.00001, 7.0, 0.0)
    result = report(data, protocol(EstimatorKind.POLYNOMIAL_LSQ))
    assert ElementSeries.from_mapping(json.loads(json.dumps(data.to_mapping()))) == data
    assert ElementBudgetReport.from_mapping(json.loads(json.dumps(result.to_mapping()))) == result
    bad = result.to_mapping()
    bad["extra"] = 1
    with pytest.raises(ResponseBudgetError):
        ElementBudgetReport.from_mapping(bad)
    with pytest.raises(ResponseBudgetError):
        candidate_budgets(result.decomposition, (), protocol_estimator=None, kappa=1.0)


@pytest.mark.parametrize("field", ["slopes_e_per_ev", "slope_noise_e_per_ev", "even_e"])
def test_finite_inputs_with_unrepresentable_derived_values_fail_closed(field: str) -> None:
    occupation_minus = -1e308 if field == "slopes_e_per_ev" else 1e308
    width = 1e308 if field == "slope_noise_e_per_ev" else 0.0
    reference = -1e308 if field == "even_e" else 0.0
    data = ElementSeries(
        "J",
        ResponseMode.BARE,
        "I",
        reference,
        0.0,
        (PointObservation(-0.0001, occupation_minus, width), PointObservation(0.0001, 1e308, width)),
    )
    with pytest.raises(ResponseBudgetError, match=f"derived {field}.*finite float"):
        decompose(data, NoiseModel())


def test_finite_slopes_with_unrepresentable_candidate_truncation_fail_closed() -> None:
    points = []
    for magnitude, slope in zip(V6, (Fraction("-1e308"), Fraction(0), Fraction("1e308")), strict=True):
        for sign in (-1, 1):
            alpha = sign * Fraction(str(magnitude))
            points.append(PointObservation(float(alpha), float(slope * alpha), 0.0))
    data = ElementSeries("J", ResponseMode.BARE, "I", 0.0, 0.0, tuple(points))
    dec = decompose(data, NoiseModel())
    assert dec.slopes_e_per_ev == (-1e308, 0.0, 1e308)
    with pytest.raises(ResponseBudgetError, match="derived candidate.truncation_e_per_ev.*finite float"):
        candidate_budgets(dec, verify_order(dec), protocol_estimator=None, kappa=1.0)


def test_finite_slopes_with_unrepresentable_drift_ratio_fail_closed() -> None:
    points = []
    for magnitude, slope in zip(V6, (Fraction(0), Fraction("1e-300"), Fraction("1e308")), strict=True):
        for sign in (-1, 1):
            alpha = sign * Fraction(str(magnitude))
            points.append(PointObservation(float(alpha), float(slope * alpha), 0.0))
    data = ElementSeries("J", ResponseMode.BARE, "I", 0.0, 0.0, tuple(points))
    assert decompose(data, NoiseModel()).slopes_e_per_ev == (0.0, 1e-300, 1e308)
    with pytest.raises(ResponseBudgetError, match="derived drift_ratios.*finite float"):
        report(data)


@pytest.mark.parametrize("field", ["slope_fractions", "noise_fractions"])
def test_decomposition_mapping_with_unrepresentable_exact_fraction_fails_closed(field: str) -> None:
    payload = decompose(series(), NoiseModel()).to_mapping()
    payload[field] = [
        {"numerator": 10**1000, "denominator": 1},
        {"numerator": 0, "denominator": 1},
        {"numerator": 0, "denominator": 1},
    ]
    with pytest.raises(ResponseBudgetError, match=f"derived decomposition.{field}.*finite float"):
        OddEvenDecomposition.from_mapping(payload)


@pytest.mark.parametrize("case", ["bare", "screened", "nonanalytic"])
def test_seeded_400_trial_coverage(case: str) -> None:
    rng = np.random.default_rng(7)
    covered = accepted = 0
    grid = (0.0025, 0.005, 0.01, 0.02) if case == "bare" else GEOMETRIC
    for _ in range(400):
        # Appendix 2 parameter sets; uniformly distributed print error remains
        # within the independently declared half-step for each observation.
        data = (
            series(grid=grid, chi="-1.355", b1="9.4", b2="-60", even=("7", "0.35", "-7.8"), width=5e-7)
            if case == "bare"
            else series(grid=grid, chi="-0.117", b1="0.03", width=5e-7)
            if case == "screened"
            else series(grid=grid, chi="-0.5", k="0.8", width=5e-7)
        )
        # Randomize only the common print phase, then actually quantize to six
        # decimals. Every point's rounding error remains at most 5e-7 e.
        phase = float(rng.uniform(-0.5, 0.5))
        points = tuple(
            replace(point, occupation_e=round(point.occupation_e + phase, 6)) for point in data.points
        )
        result = report(replace(data, points=points))
        if case == "nonanalytic":
            assert OrderStatus.VERIFIED_2 not in verify_order(result.decomposition)
        if result.best is None:
            continue
        truth = {"bare": -1.355, "screened": -0.117, "nonanalytic": -0.5}[case]
        accepted += 1
        covered += abs(result.best.estimate_e_per_ev - truth) <= result.best.total_e_per_ev
    assert accepted == 400
    assert covered / accepted >= 0.99


def test_analytic_random_cubic_quintic_v6_coverage() -> None:
    rng = np.random.default_rng(20261002)
    covered = accepted = 0
    for _ in range(400):
        chi = float(rng.uniform(-1.5, -0.5))
        b1 = float(rng.choice((-1, 1))) * float(rng.uniform(1.0, 8.0))
        b2 = float(rng.choice((-1, 1))) * float(rng.uniform(0.1, 30.0))
        data = series(chi=str(chi), b1=str(b1), b2=str(b2), width=5e-7)
        points = tuple(
            replace(
                point,
                occupation_e=point.occupation_e + float(rng.uniform(-5e-7, 5e-7)),
            )
            for point in data.points
        )
        result = report(replace(data, points=points))
        assert result.best is not None and result.best.admissible
        accepted += 1
        covered += abs(result.best.estimate_e_per_ev - chi) <= result.best.total_e_per_ev
    assert accepted == 400
    assert covered / accepted >= 0.99


def test_reciprocity_sorted_and_duplicate_rejection() -> None:
    base = series(width=5e-7)
    first = report(replace(base, site_perturbed="A", site_observed="B"))
    second = report(replace(base, site_perturbed="B", site_observed="A"))
    assert reciprocity((second, first), kappa=1.0) == reciprocity((first, second), kappa=1.0)
    residual = reciprocity((first, second), kappa=1.0)[0]
    assert residual.residual_e_per_ev == 0 and residual.consistent
    with pytest.raises(ResponseBudgetError):
        reciprocity((first, first), kappa=1.0)


def test_influence_direct_inversion_signs_and_invalid_matrices() -> None:
    matrix = np.array([[2.0, 1.0], [0.0, 3.0]])
    bare, screened = u_influence(matrix, matrix)
    inverse = np.linalg.inv(matrix)
    for k in range(2):
        np.testing.assert_array_equal(screened[k], np.outer(inverse[k], inverse[:, k]))
    np.testing.assert_array_equal(bare, -screened)
    for invalid in (np.zeros((2, 2)), np.array([[np.nan]]), np.array([[True]]), np.ones((2, 3))):
        with pytest.raises(ResponseBudgetError):
            u_influence(invalid, invalid)


def test_frozen_coo_regression() -> None:
    path = Path(__file__).resolve().parents[2] / (
        "results/stage-ub-v6-observables/coo-u-b-campaigns/stageubv6-coo-a0/lr_u_analysis.v3.json"
    )
    if not path.exists():
        pytest.skip(f"frozen CoO fixture is missing: {path}")
    rows = json.loads(path.read_text(encoding="utf-8"))["response_observation_dataset"]["rows"]

    def frozen(j: int, i: int, mode: ResponseMode) -> ElementSeries:
        points = []
        ref = ref_width = 0.0
        for row in rows:
            if row["perturbed_site_index"] != j:
                continue
            observed = next(item for item in row["observed_sites"] if item["observed_site_index"] == i)
            key = mode.value.lower()
            points.append(
                PointObservation(
                    row["alpha_eV"],
                    observed["occupations_electron"][key],
                    observed["occupation_half_widths_electron"][key],
                )
            )
            ref = observed["occupations_electron"]["reference"]
            ref_width = observed["occupation_half_widths_electron"]["reference"]
        return ElementSeries(str(j), mode, str(i), ref, ref_width, tuple(points))

    bare = report(frozen(0, 0, ResponseMode.BARE))
    # User-authorized full precision from immutable tokens; Appendix numbers
    # were rounded for display. Preserve the prescribed 1e-9 comparison.
    assert bare.decomposition.slopes_e_per_ev == pytest.approx(
        (-1.351575, -1.3402375, -1.3215916666666667), abs=1e-9, rel=0
    )
    assert bare.drift_ratios[0] == pytest.approx(1.645, abs=0.001)
    bare_cross = report(frozen(0, 1, ResponseMode.BARE))
    assert bare_cross.drift_ratios[0] == pytest.approx(1.638, abs=0.001)
    for value in (bare, bare_cross):
        assert verify_order(value.decomposition) == (OrderStatus.UNRESOLVED,)
        assert value.best is not None and value.best.admissible
        assert value.best.p_used == 1
    assert bare.decomposition.even_fit is not None
    assert bare.decomposition.even_fit[0] == pytest.approx(1.92e-5, abs=1e-8)
    cross = [report(frozen(j, i, ResponseMode.SCREENED)) for j, i in ((0, 1), (1, 0))]
    c0, c1 = (candidates(value, EstimatorKind.CENTRAL)[0] for value in cross)
    assert abs(c0.estimate_e_per_ev - c1.estimate_e_per_ev) <= c0.noise_e_per_ev + c1.noise_e_per_ev
    assert c0.estimate_e_per_ev == c1.estimate_e_per_ev
