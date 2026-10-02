"""Independent checks of the exact symmetric slope functional."""

from fractions import Fraction

import numpy as np
import pytest

from hubbardflow.domain.response_budget_models import ResponseBudgetError
from hubbardflow.domain.response_budget_moments import (
    EstimatorMoments,
    divided_difference_coefficients,
    estimator_moments,
)
from hubbardflow.domain.response_protocol import EstimatorKind, EstimatorSpec


@pytest.mark.parametrize(
    "kind,degree,grid",
    [
        (EstimatorKind.CENTRAL, None, (0.02,)),
        (EstimatorKind.RICHARDSON_2, None, (0.02, 0.04)),
        (EstimatorKind.LINEAR_LSQ, None, (0.02, 0.04, 0.06)),
        (EstimatorKind.POLYNOMIAL_LSQ, 1, (0.02, 0.04, 0.06)),
        (EstimatorKind.POLYNOMIAL_LSQ, 2, (0.02, 0.04, 0.06)),
        (EstimatorKind.POLYNOMIAL_LSQ, 3, (0.02, 0.04, 0.06)),
    ],
)
def test_exact_weights_match_declared_estimator(
    kind: EstimatorKind, degree: int | None, grid: tuple[float, ...]
) -> None:
    spec = EstimatorSpec(kind, degree, grid)
    exact = estimator_moments(spec)
    weights = dict(spec.weights())
    for a, weight in zip(exact.amplitudes_ev, exact.weights, strict=True):
        assert float(weight) == pytest.approx(2 * float(a) * weights[float(a)], abs=1e-14)
    assert sum(exact.weights) == 1
    assert EstimatorMoments.from_mapping(exact.to_mapping()) == exact
    assert exact.principal(2) == exact.moments[exact.j0 - 1]
    with pytest.raises(ResponseBudgetError):
        exact.principal(3)


def test_divided_difference_coefficients_exact_polynomial_reproduction() -> None:
    for nodes in ((Fraction(1), Fraction(3)), (Fraction(1), Fraction(3), Fraction(9))):
        coefficients = divided_difference_coefficients(nodes)
        assert sum(coefficients) == 0
        assert sum(w * x ** (len(nodes) - 1) for w, x in zip(coefficients, nodes, strict=True)) == 1
        radius = sum((abs(w) * Fraction("0.1") for w in coefficients), Fraction())
        for signs in np.ndindex(*(2,) * len(nodes)):
            delta = sum(
                (
                    w * Fraction("0.1") * (-1 if sign else 1)
                    for w, sign in zip(coefficients, signs, strict=True)
                ),
                Fraction(),
            )
            assert abs(delta) <= radius
