"""Exact estimator moments for the R0/R1/R2 truncation diagnostics.

Decimal FDF amplitudes are rational numbers. Keeping the slope functional in
that arithmetic makes cancellation and the first surviving moment exact,
including for the cubic least-squares protocol; no numerical zero test is used.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from hubbardflow.domain.response_budget_models import ResponseBudgetError, _Record
from hubbardflow.domain.response_protocol import EstimatorKind, EstimatorSpec


@dataclass(frozen=True)
class EstimatorMoments(_Record):
    """Slope-space weights and the first nonzero moment in ``t = a²``."""

    amplitudes_ev: tuple[Fraction, ...]
    weights: tuple[Fraction, ...]
    j0: int
    moments: tuple[Fraction, ...]

    def __post_init__(self) -> None:
        super().__post_init__()
        if not self.amplitudes_ev or len(self.weights) != len(self.amplitudes_ev) or sum(self.weights) != 1:
            raise ResponseBudgetError("slope weights must match amplitudes and sum exactly to one")
        if (
            self.j0 < 1
            or self.j0 > len(self.moments)
            or any(self.moments[: self.j0 - 1])
            or self.moments[self.j0 - 1] == 0
        ):
            raise ResponseBudgetError("j0 must be the exact first nonzero moment")

    def principal(self, p_used: int) -> Fraction:
        """Use R0's conservative variable a when order two is unverified."""
        if p_used == 1:
            return sum((w * a for w, a in zip(self.weights, self.amplitudes_ev, strict=True)), Fraction())
        if p_used == 2:
            return self.moments[self.j0 - 1]
        raise ResponseBudgetError("p_used must be one or two under R0")


def estimator_moments(estimator: EstimatorSpec) -> EstimatorMoments:
    """Derive exact weights from the symmetric estimator's odd design block.

    The degree-one/two fit has only the a column in that block. The cubic
    normal equations have columns a and a³; their exact two-by-two inverse
    supplies the slope functional without a pseudoinverse or regularization.
    """
    a = tuple(Fraction(str(value)) for value in estimator.amplitudes_ev)
    t = tuple(value**2 for value in a)
    weights: tuple[Fraction, ...]
    if estimator.kind is EstimatorKind.CENTRAL:
        weights = (Fraction(1),)
    elif estimator.kind is EstimatorKind.RICHARDSON_2:
        weights = (t[1] / (t[1] - t[0]), -t[0] / (t[1] - t[0]))
    elif estimator.kind is EstimatorKind.LINEAR_LSQ or estimator.polynomial_degree in (1, 2):
        weights = tuple(value / sum(t) for value in t)
    else:
        s1, s2, s3 = (sum(value**j for value in t) for j in (1, 2, 3))
        weights = tuple(value * (s3 - s2 * value) / (s1 * s3 - s2**2) for value in t)
    moments = tuple(
        sum((w * value**j for w, value in zip(weights, t, strict=True)), Fraction())
        for j in range(1, len(a) + 1)
    )
    j0 = next(j for j, value in enumerate(moments, 1) if value != 0)
    return EstimatorMoments(a, weights, j0, moments)


def divided_difference_coefficients(nodes: tuple[Fraction, ...]) -> tuple[Fraction, ...]:
    """Coefficients of the highest divided difference on distinct nodes."""
    return tuple(
        Fraction(1) / _product(tuple(x - y for j, y in enumerate(nodes) if j != i))
        for i, x in enumerate(nodes)
    )


def _product(values: tuple[Fraction, ...]) -> Fraction:
    result = Fraction(1)
    for value in values:
        result *= value
    return result
