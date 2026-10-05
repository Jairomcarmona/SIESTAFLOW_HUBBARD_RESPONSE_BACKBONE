"""Verified elementwise inverse perturbation bounds for printed occupations.

All proof arithmetic is rational. A floating inverse is only a preconditioner:
its exact residual enters the bound, so neither a first-order approximation nor
an unverified floating inverse can establish invertibility.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from fractions import Fraction
from typing import Any

import numpy as np

from .u_certification import CertificationError, Interval, exact_slope_weights
from .validation import ValidationError, require_finite, require_nonnegative_finite


class ElementwiseRoundingError(ValueError):
    """The supplied matrix box cannot support a verified print bound."""


class InverseBoundStatus(str, Enum):
    BOUNDED = "BOUNDED"
    NOT_ESTABLISHED = "NOT_ESTABLISHED"


class InverseBoundReason(str, Enum):
    NOMINAL_MATRIX_SINGULAR = "nominal_matrix_singular"
    PRINT_BOX_CONTRACTION_NOT_PROVEN = "print_box_contraction_not_proven"


def _number(value: float, label: str) -> Fraction:
    try:
        return Fraction.from_float(require_finite(value, label))
    except ValidationError as exc:
        raise ElementwiseRoundingError(str(exc)) from exc


def _upper(value: Fraction) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ElementwiseRoundingError("verified endpoint cannot be represented as finite float")
    if Fraction.from_float(result) < value:
        result = math.nextafter(result, math.inf)
    if not math.isfinite(result):
        raise ElementwiseRoundingError("outward-rounded endpoint cannot be represented as finite float")
    return result


def _lower(value: Fraction) -> float:
    return -_upper(-value)


def fitted_print_interval(
    alpha_ev: Sequence[float], occupation_e: Sequence[float], half_width_e: Sequence[float], *, degree: int
) -> Interval:
    """Enclose exact OLS c1, including round-to-nearest input conversion.

    Alpha values define the fixed estimator grid. Occupation centers may have
    been converted from printed decimals to binary64, and widths may have been
    converted from exact decimal quantization. Both conversions are enclosed;
    no statistical uncertainty or SCF error is inferred.

    For a total assembled from multiple binary conversions, half_width_e must
    also enclose the error of that aggregation against the exact lexical sum.
    The campaign occupation adapter supplies that error explicitly. The extra
    half-ULP cell here only encloses a single round-to-nearest conversion.
    """
    if len(alpha_ev) != len(occupation_e) or len(alpha_ev) != len(half_width_e):
        raise ElementwiseRoundingError("alpha, occupation and half-width lengths must agree")
    try:
        weights = exact_slope_weights([str(_number(x, "alpha_ev")) for x in alpha_ev], degree)
    except CertificationError as exc:
        raise ElementwiseRoundingError(str(exc)) from exc
    center = Fraction(0)
    radius = Fraction(0)
    for weight, raw_center, raw_width in zip(weights, occupation_e, half_width_e):
        try:
            value = require_finite(raw_center, "occupation_e")
            width = require_nonnegative_finite(raw_width, "half_width_e")
        except ValidationError as exc:
            raise ElementwiseRoundingError(str(exc)) from exc
        exact_center = Fraction.from_float(value)
        # This encloses an original decimal that rounded to the supplied float.
        adjacent = (math.nextafter(value, -math.inf), math.nextafter(value, math.inf))
        if not all(math.isfinite(x) for x in adjacent):
            raise ElementwiseRoundingError("occupation conversion interval is not finite")
        conversion = max(abs(_number(x, "adjacent occupation") - exact_center) for x in adjacent) / 2
        exact_width = max(Fraction.from_float(width), Fraction(str(width)))
        center += weight * exact_center
        radius += abs(weight) * (exact_width + conversion)
    return Interval(center - radius, center + radius)


def _multiply(a: Sequence[Sequence[Fraction]], b: Sequence[Sequence[Fraction]]) -> list[list[Fraction]]:
    columns = tuple(zip(*b))
    return [[sum((x * y for x, y in zip(row, column)), Fraction(0)) for column in columns] for row in a]


@dataclass(frozen=True)
class ElementwiseInverseBound:
    """Inverse diagonal enclosure and independent rigorous norm cross-check."""

    status: InverseBoundStatus
    diagonal_intervals: tuple[Interval, ...]
    first_order_diagonal_eV: tuple[Fraction, ...]
    remainder_diagonal_eV: tuple[Fraction, ...]
    contraction: Fraction | None
    uniform_cross_check_eV: Fraction | None
    reason: InverseBoundReason | None = None

    def __post_init__(self) -> None:
        size = len(self.diagonal_intervals)
        if self.status == InverseBoundStatus.BOUNDED and (
            not size
            or len(self.first_order_diagonal_eV) != size
            or len(self.remainder_diagonal_eV) != size
            or self.contraction is None
            or not 0 <= self.contraction < 1
            or self.uniform_cross_check_eV is None
            or self.uniform_cross_check_eV < 0
        ):
            raise ElementwiseRoundingError(
                "bounded inverse requires complete intervals and contraction proof"
            )
        if any(x < 0 for x in (*self.first_order_diagonal_eV, *self.remainder_diagonal_eV)):
            raise ElementwiseRoundingError("inverse error components must be nonnegative")

    def to_mapping(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "diagonal_intervals_eV": [[_lower(x.lo), _upper(x.hi)] for x in self.diagonal_intervals],
            "first_order_diagonal_eV": [_upper(x) for x in self.first_order_diagonal_eV],
            "remainder_diagonal_eV": [_upper(x) for x in self.remainder_diagonal_eV],
            "verified_contraction_upper": None if self.contraction is None else _upper(self.contraction),
            "verified_contraction_exact": None if self.contraction is None else str(self.contraction),
            "uniform_interval_cross_check_eV": (
                None if self.uniform_cross_check_eV is None else _upper(self.uniform_cross_check_eV)
            ),
            "reason": None if self.reason is None else self.reason.value,
            "proof": "exact rational residual and elementwise Neumann majorant with infinite-tail enclosure",
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ElementwiseInverseBound:
        intervals = tuple(
            Interval(_number(x[0], "lower"), _number(x[1], "upper")) for x in value["diagonal_intervals_eV"]
        )
        return cls(
            InverseBoundStatus(value["status"]),
            intervals,
            tuple(_number(x, "first order") for x in value["first_order_diagonal_eV"]),
            tuple(_number(x, "remainder") for x in value["remainder_diagonal_eV"]),
            None
            if value["verified_contraction_exact"] is None
            else Fraction(value["verified_contraction_exact"]),
            None
            if value["uniform_interval_cross_check_eV"] is None
            else _number(value["uniform_interval_cross_check_eV"], "cross check"),
            None if value.get("reason") is None else InverseBoundReason(value["reason"]),
        )


def bound_inverse_diagonal(box: Sequence[Sequence[Interval]]) -> ElementwiseInverseBound:
    """Bound every inverse in a matrix box without regularization.

    For a rational preconditioner R, K=|I-RM|+|R|H majorizes the
    inverse iteration over M+E, |E|<=H. If q=max row sum(K)<1, the
    diagonal error is bounded by K|R| plus its infinite Neumann tail.
    The tail at (i,j) is <= row_sum(K)[i] * max_k(K|R|)[k,j]/(1-q).
    This remains rigorous for asymmetric matrices and accounts for R's defect.
    """
    size = len(box)
    if not size or any(len(row) != size for row in box):
        raise ElementwiseRoundingError("matrix box must be nonempty and square")
    center = [[(x.lo + x.hi) / 2 for x in row] for row in box]
    widths = [[(x.hi - x.lo) / 2 for x in row] for row in box]
    nominal = np.asarray([[float(x) for x in row] for row in center])
    if not np.all(np.isfinite(nominal)):
        raise ElementwiseRoundingError("matrix center must be finite")
    try:
        floating_inverse = np.linalg.inv(nominal)
    except np.linalg.LinAlgError:
        return ElementwiseInverseBound(
            InverseBoundStatus.NOT_ESTABLISHED,
            (),
            (),
            (),
            None,
            None,
            InverseBoundReason.NOMINAL_MATRIX_SINGULAR,
        )
    r = [[_number(float(x), "inverse preconditioner") for x in row] for row in floating_inverse]
    absolute_r = [[abs(x) for x in row] for row in r]
    product = _multiply(r, center)
    defect = [[abs(Fraction(i == j) - product[i][j]) for j in range(size)] for i in range(size)]
    propagated = _multiply(absolute_r, widths)
    k = [[defect[i][j] + propagated[i][j] for j in range(size)] for i in range(size)]
    row_sums = [sum(row, Fraction(0)) for row in k]
    q = max(row_sums)
    if q >= 1:
        return ElementwiseInverseBound(
            InverseBoundStatus.NOT_ESTABLISHED,
            (),
            (),
            (),
            q,
            None,
            InverseBoundReason.PRINT_BOX_CONTRACTION_NOT_PROVEN,
        )
    leading = _multiply(k, absolute_r)
    print_leading = _multiply(propagated, absolute_r)
    max_by_column = [max(column) for column in zip(*leading)]
    tail = [row_sums[i] * max_by_column[i] / (1 - q) for i in range(size)]
    # A second exact proof uses the induced infinity norm, independently of
    # the per-element leading term. It bounds every entry of the same series.
    uniform = max(sum(row, Fraction(0)) for row in leading) / (1 - q)
    radii = [leading[i][i] + tail[i] for i in range(size)]
    if any(radius > uniform for radius in radii):
        # Both proofs are valid; their intersection is also an enclosure.
        radii = [min(radius, uniform) for radius in radii]
    return ElementwiseInverseBound(
        InverseBoundStatus.BOUNDED,
        tuple(Interval(r[i][i] - radii[i], r[i][i] + radii[i]) for i in range(size)),
        tuple(print_leading[i][i] for i in range(size)),
        tuple(radii[i] - print_leading[i][i] for i in range(size)),
        q,
        uniform,
    )


@dataclass(frozen=True)
class ElementwiseUBound:
    """Print enclosure centered on the reported floating U diagonal."""

    half_width_eV: tuple[Fraction, ...]
    intervals_eV: tuple[Interval, ...]

    def __post_init__(self) -> None:
        if not self.half_width_eV or len(self.half_width_eV) != len(self.intervals_eV):
            raise ElementwiseRoundingError("U bound requires one interval and width per site")
        if any(x < 0 for x in self.half_width_eV):
            raise ElementwiseRoundingError("U half-widths must be nonnegative")

    def to_mapping(self) -> dict[str, Any]:
        return {
            "half_width_eV": [_upper(x) for x in self.half_width_eV],
            "intervals_eV": [[_lower(x.lo), _upper(x.hi)] for x in self.intervals_eV],
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ElementwiseUBound:
        return cls(
            tuple(_number(x, "half width") for x in value["half_width_eV"]),
            tuple(Interval(_number(x[0], "lower"), _number(x[1], "upper")) for x in value["intervals_eV"]),
        )


def bound_u_diagonal(
    bare: ElementwiseInverseBound, screened: ElementwiseInverseBound, reported_u_eV: Sequence[float]
) -> ElementwiseUBound:
    """Subtract inverse intervals, preserving fit/inversion float displacement."""
    if bare.status != InverseBoundStatus.BOUNDED or screened.status != InverseBoundStatus.BOUNDED:
        raise ElementwiseRoundingError("both inverse bounds must be established")
    if len(bare.diagonal_intervals) != len(screened.diagonal_intervals) or len(reported_u_eV) != len(
        bare.diagonal_intervals
    ):
        raise ElementwiseRoundingError("inverse bounds and reported U must have equal lengths")
    radii: list[Fraction] = []
    intervals: list[Interval] = []
    for a, b, point in zip(bare.diagonal_intervals, screened.diagonal_intervals, reported_u_eV):
        enclosure = Interval(a.lo - b.hi, a.hi - b.lo)
        center = _number(point, "reported_u_eV")
        radius = max(abs(enclosure.lo - center), abs(enclosure.hi - center))
        radii.append(radius)
        intervals.append(Interval(center - radius, center + radius))
    return ElementwiseUBound(tuple(radii), tuple(intervals))
