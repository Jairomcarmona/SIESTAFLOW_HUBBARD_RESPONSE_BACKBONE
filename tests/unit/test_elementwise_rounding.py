"""Truth coverage and adversarial checks of the exact elementwise print bound."""

import json
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from hubbardflow.domain.elementwise_rounding import (
    ElementwiseInverseBound,
    ElementwiseRoundingError,
    InverseBoundStatus,
    bound_inverse_diagonal,
    bound_u_diagonal,
    fitted_print_interval,
)
from hubbardflow.domain.lr_analysis_v2 import LRAnalysisPolicy, analyze_verified_lr
from hubbardflow.domain.matrix_lr import ResponseObservation
from hubbardflow.domain.u_certification import Interval, inverse
from hubbardflow.execution.observation_assembly import ObservationAssembler
from hubbardflow.siesta_backend.event_parser import parse_hubbard_population_events
from hubbardflow.siesta_backend.occupation_precision import read_printed_occupation_precision


def _box(matrix: np.ndarray, half_width: float) -> list[list[Interval]]:
    return [[Interval.around(Fraction(str(x)), Fraction(str(half_width))) for x in row] for row in matrix]


def test_exact_synthetic_ground_truth_with_cubic_and_print_rounding() -> None:
    alphas = [-0.15, -0.1, -0.05, 0.05, 0.1, 0.15]
    true = Fraction(-4, 5)
    exact = [Fraction(5) + true * Fraction(str(a)) + Fraction(2) * Fraction(str(a)) ** 3 for a in alphas]
    rounded = [round(float(x), 5) for x in exact]
    enclosure = fitted_print_interval(alphas, rounded, [5e-6] * len(alphas), degree=3)
    assert enclosure.contains(true)


def test_two_rounded_tokens_keep_lexical_extrema_in_the_campaign_print_box() -> None:
    output = """hubbard_term: recalculating local occupations 1
  hubbard_term: atom, species: 1 1
    1 1 1.00001 2.00003
    Occupations: 1.00001 2.00003
"""
    event = parse_hubbard_population_events(output)[0]
    printed = read_printed_occupation_precision(output, event)[1]
    lexical_total = Fraction("1.00001") + Fraction("2.00003")
    lexical_half_width = Fraction(printed.half_width_exact)
    lexical_lower_slope = (lexical_total - lexical_half_width) / 2
    # This reproduces the audit counterexample: half a ULP of the summed
    # center cannot enclose separately rounded tokens followed by summation.
    old = fitted_print_interval([-1.0, 1.0], [0.0, printed.total], [0.0, printed.half_width], degree=1)
    assert old.lo > lexical_lower_slope
    widths = ObservationAssembler.event_trace_half_widths(
        output, event, [{"atom_index": 1}], minimum_decimal_places=None
    )
    assert widths is not None
    corrected = fitted_print_interval([-1.0, 1.0], [0.0, printed.total], [0.0, widths[0]], degree=1)
    assert corrected.contains(lexical_lower_slope)
    assert corrected.contains((lexical_total + lexical_half_width) / 2)


def test_contraction_below_one_survives_json_mapping_round_trip() -> None:
    q = Fraction(18014398509481983, 18014398509481984)
    bound = bound_inverse_diagonal([[Interval(1 - q, 1 + q)]])
    assert bound.status == InverseBoundStatus.BOUNDED
    assert bound.contraction == q
    serialized = json.loads(json.dumps(bound.to_mapping(), allow_nan=False))
    assert serialized["verified_contraction_upper"] == 1.0
    assert serialized["verified_contraction_exact"] == str(q)
    restored = ElementwiseInverseBound.from_mapping(serialized)
    assert restored.status == InverseBoundStatus.BOUNDED
    assert restored.contraction == q


@given(st.fractions(min_value=Fraction(-1, 1000), max_value=Fraction(1, 1000)))
def test_elementwise_bound_covers_rational_truth_and_full_nonlinear_remainder(delta: Fraction) -> None:
    center = np.array([[-0.8, -0.1], [-0.06, -0.7]])
    box = _box(center, 0.001)
    bound = bound_inverse_diagonal(box)
    assert bound.status == InverseBoundStatus.BOUNDED
    perturbed = [[(x.lo + x.hi) / 2 + delta for x in row] for row in box]
    truth = inverse(perturbed)
    assert all(enclosure.contains(truth[i][i]) for i, enclosure in enumerate(bound.diagonal_intervals))
    assert all(x >= 0 for x in bound.remainder_diagonal_eV)
    assert bound.uniform_cross_check_eV is not None


def test_order_invariance_of_exact_cubic_fit() -> None:
    alpha = [-0.15, -0.1, -0.05, 0.05, 0.1, 0.15]
    values = [5 - 0.8 * x + 2 * x**3 for x in alpha]
    widths = [1e-5, 2e-5, 3e-5, 4e-5, 5e-5, 6e-5]
    a = fitted_print_interval(alpha, values, widths, degree=3)
    b = fitted_print_interval(alpha[::-1], values[::-1], widths[::-1], degree=3)
    assert a == b


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_input_is_rejected(value: float) -> None:
    with pytest.raises(ElementwiseRoundingError, match="finite"):
        fitted_print_interval([-0.1, 0.1], [value, 5.0], [1e-5, 1e-5], degree=1)


def test_singular_and_box_containing_singularity_do_not_claim_bound() -> None:
    singular = bound_inverse_diagonal(_box(np.ones((2, 2)), 0.0))
    assert singular.status == InverseBoundStatus.NOT_ESTABLISHED
    unsafe = bound_inverse_diagonal(_box(np.eye(2), 1.0))
    assert unsafe.status == InverseBoundStatus.NOT_ESTABLISHED
    assert unsafe.diagonal_intervals == ()


def test_36_site_translation_reconstructed_response_has_elementwise_bounds() -> None:
    # One representative column of each ring determines the full 36x36
    # circulant response. This tests the full reconstructed inversion basis.
    size = 36
    first = np.zeros(size)
    first[0], first[1], first[-1] = -0.8, -0.02, -0.02
    bare = np.column_stack([np.roll(first, i) for i in range(size)])
    screened = bare * 0.35
    bound0 = bound_inverse_diagonal(_box(bare, 2e-5))
    bound = bound_inverse_diagonal(_box(screened, 2e-5))
    point = np.diag(np.linalg.inv(bare) - np.linalg.inv(screened))
    result = bound_u_diagonal(bound0, bound, point)
    assert len(result.half_width_eV) == size
    assert max(map(float, result.half_width_eV)) < float(
        bound0.uniform_cross_check_eV + bound.uniform_cross_check_eV
    )
    assert max(map(float, result.half_width_eV)) > 0


def test_monte_carlo_occupation_rounding_is_covered_by_v3_primary_bound() -> None:
    rng = np.random.default_rng(2401)
    bare = np.array([[-0.8, -0.02, -0.01], [-0.03, -0.7, -0.02], [-0.01, -0.02, -0.75]])
    screened = bare * 0.35
    alphas = [-0.15, -0.1, -0.05, 0.05, 0.1, 0.15]
    observations = [
        ResponseObservation(
            j, a, [0, 1, 2], [5.0] * 3, (5.0 + bare[:, j] * a).tolist(), (5.0 + screened[:, j] * a).tolist()
        )
        for j in range(3)
        for a in alphas
    ]
    widths = {
        (x.perturbation_site, x.alpha, mode): [5e-6] * 3
        for x in observations
        for mode in ("bare", "screened")
    }
    policy = LRAnalysisPolicy(estimator="polynomial")
    report = analyze_verified_lr(
        observations, policy, trace_half_widths_electron=widths, occupation_source="siesta_occupations_total"
    )
    bounds = report["printing_rounding_bounds"]
    nominal = np.asarray(report["primary"]["U_matrix_eV"])
    allowed = np.array([bounds["U_scalar_half_width_by_site_eV"][str(i)] for i in range(3)])
    assert bounds["legacy_uniform_norm_bound"]["maximum_U_scalar_half_width_eV"] > max(allowed)
    observed_max = np.zeros(3)
    for _ in range(100):
        varied = [
            ResponseObservation(
                x.perturbation_site,
                x.alpha,
                x.site_labels,
                x.occupations_ref,
                (np.asarray(x.occupations_bare) + rng.uniform(-5e-6, 5e-6, 3)).tolist(),
                (np.asarray(x.occupations_screened) + rng.uniform(-5e-6, 5e-6, 3)).tolist(),
            )
            for x in observations
        ]
        sample = analyze_verified_lr(varied, policy)
        observed_max = np.maximum(
            observed_max, abs(np.diag(np.asarray(sample["primary"]["U_matrix_eV"]) - nominal))
        )
    assert np.all(observed_max <= allowed)


def test_frozen_nio_matrices_are_read_only_regression_for_verified_box() -> None:
    fixture = Path(__file__).parents[1] / "fixtures/replay_nio_p5/replay_analysis.v3.json"
    archived = json.loads(fixture.read_text())
    widths = archived["printing_rounding_bounds"]
    result = bound_inverse_diagonal(
        [
            [
                Interval.around(Fraction(str(value)), Fraction(str(width)))
                for value, width in zip(row, row_widths)
            ]
            for row, row_widths in zip(
                archived["primary"]["matrix_used_chi0"], widths["chi0_slope_half_width_eV_inv"]
            )
        ]
    )
    assert result.status == InverseBoundStatus.BOUNDED
