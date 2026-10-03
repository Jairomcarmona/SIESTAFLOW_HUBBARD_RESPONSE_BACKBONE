"""Pure phase-one FD-EBQ diagnostics, with the authorized I.3 errata.

Printed radii are BOUNDs. R0 verifies the dominant order conservatively;
R1/R2 provide conditional ESTIMATEs of truncation, not rigorous tail bounds.
There is no campaign qualification or execution decision in this module.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from fractions import Fraction
from itertools import pairwise

import numpy as np
from numpy.typing import NDArray

from hubbardflow.domain.response_budget_models import (
    BoundKind,
    BudgetReason,
    CandidateBudget,
    ElementBudgetReport,
    ElementSeries,
    NoiseModel,
    OddEvenDecomposition,
    OrderStatus,
    PointObservation,
    PrintedResponseBudget,
    QualificationCap,
    ReciprocityResidual,
    ResponseBudgetError,
    _derived_finite,
)
from hubbardflow.domain.response_budget_moments import (
    EstimatorMoments,
    divided_difference_coefficients,
    estimator_moments,
)
from hubbardflow.domain.response_protocol import EstimatorKind, EstimatorSpec
from hubbardflow.domain.validation import ValidationError, require_positive_finite

# Re-export the immutable public records from the small model module.
__all__ = [
    "BoundKind",
    "BudgetReason",
    "CandidateBudget",
    "ElementBudgetReport",
    "ElementSeries",
    "NoiseModel",
    "OddEvenDecomposition",
    "OrderStatus",
    "PointObservation",
    "PrintedResponseBudget",
    "QualificationCap",
    "ReciprocityResidual",
    "ResponseBudgetError",
    "candidate_budgets",
    "decompose",
    "element_report",
    "printed_response_budget",
    "reciprocity",
    "u_influence",
    "verify_order",
]


def decompose(series: ElementSeries, noise: NoiseModel) -> OddEvenDecomposition:
    """Separate parity without allowing an even/reference shift into slopes.

    Decimal-token rationals preserve exact strict-interval order tests. Phase
    one deliberately rejects SCF components rather than treating them as known.
    """
    if not isinstance(series, ElementSeries) or not isinstance(noise, NoiseModel):
        raise ResponseBudgetError("decompose requires an ElementSeries and a NoiseModel")
    points = {Fraction(str(point.alpha_ev)): point for point in series.points}
    amplitudes = tuple(sorted(alpha for alpha in points if alpha > 0))
    odd, slopes, radii, even = [], [], [], []
    for a in amplitudes:
        plus, minus = points[a], points[-a]
        np_, nm = Fraction(str(plus.occupation_e)), Fraction(str(minus.occupation_e))
        difference = (np_ - nm) / 2
        odd.append(_derived_finite(difference, "odd_e"))
        slopes.append(difference / a)
        radii.append((Fraction(str(plus.half_width_e)) + Fraction(str(minus.half_width_e))) / (2 * a))
        even.append(_derived_finite((np_ + nm) / 2 - Fraction(str(series.reference_occupation_e)), "even_e"))
    even_fit = None
    if len(amplitudes) >= 3:
        # Scale by the largest a² to keep the diagnostic even fit well scaled.
        t = np.asarray([_derived_finite(a**2, "amplitudes_ev_squared") for a in amplitudes])
        scaled = t / t[-1]
        design = np.column_stack((np.ones(len(t)), scaled, scaled**2))
        coeffs, _, rank, _ = np.linalg.lstsq(design, np.asarray(even), rcond=None)
        if rank != 3:
            raise ResponseBudgetError("even-part fit is rank deficient")
        even_fit = (
            _derived_finite(float(coeffs[0]), "even_fit.delta0_e"),
            _derived_finite(float(coeffs[1] / t[-1]), "even_fit.c2"),
            _derived_finite(float(coeffs[2] / t[-1] ** 2), "even_fit.c4"),
        )
    return OddEvenDecomposition(
        tuple(_derived_finite(a, "amplitudes_ev") for a in amplitudes),
        tuple(odd),
        tuple(_derived_finite(s, "slopes_e_per_ev") for s in slopes),
        tuple(_derived_finite(n, "slope_noise_e_per_ev") for n in radii),
        tuple(even),
        even_fit,
        tuple(slopes),
        tuple(radii),
    )


def verify_order(dec: OddEvenDecomposition) -> tuple[OrderStatus, ...]:
    """Apply R0 while treating higher-order shifts as pre-asymptotic evidence.

    A same-sign ratio below rho_1 contradicts every analytic order p >= 1.
    Other ratios that do not uniquely identify p=1 or p=2 remain unresolved;
    higher-order terms can shift precise finite-amplitude data away from either
    leading-order ratio without making the response inconsistent.
    """
    a = tuple(Fraction(str(value)) for value in dec.amplitudes_ev)
    s, nu = dec.slope_fractions, dec.noise_fractions
    result = []
    for k in range(len(a) - 2):
        d0, d1 = s[k + 1] - s[k], s[k + 2] - s[k + 1]
        n0, n1 = nu[k] + nu[k + 1], nu[k + 1] + nu[k + 2]
        if abs(d0) <= n0 or abs(d1) <= n1:
            result.append(OrderStatus.UNRESOLVED)
        elif d0 * d1 < 0:
            result.append(OrderStatus.INCONSISTENT)
        else:
            lo, hi = (abs(d1) - n1) / (abs(d0) + n0), (abs(d1) + n1) / (abs(d0) - n0)
            rho1, rho2 = ((a[k + 2] ** p - a[k + 1] ** p) / (a[k + 1] ** p - a[k] ** p) for p in (1, 2))
            contains1, contains2 = lo <= rho1 <= hi, lo <= rho2 <= hi
            result.append(
                OrderStatus.UNRESOLVED
                if contains1 and contains2
                else OrderStatus.VERIFIED_1
                if contains1
                else OrderStatus.VERIFIED_2
                if contains2
                else OrderStatus.INCONSISTENT
                if hi < rho1
                else OrderStatus.UNRESOLVED
            )
    return tuple(result)


def _family_order(orders: Sequence[OrderStatus]) -> OrderStatus:
    priority = (
        OrderStatus.VERIFIED_2,
        OrderStatus.VERIFIED_1,
        OrderStatus.UNRESOLVED,
        OrderStatus.INCONSISTENT,
    )
    if any(not isinstance(status, OrderStatus) for status in orders):
        raise ResponseBudgetError("orders must contain OrderStatus values")
    return max(orders, key=priority.index) if orders else OrderStatus.UNRESOLVED


def _value_noise(dec: OddEvenDecomposition, moments: EstimatorMoments) -> tuple[Fraction, Fraction]:
    indexes = {Fraction(str(a)): i for i, a in enumerate(dec.amplitudes_ev)}
    if any(a not in indexes for a in moments.amplitudes_ev):
        raise ResponseBudgetError("protocol estimator uses an amplitude absent from the element series")
    value = sum(
        (
            w * dec.slope_fractions[indexes[a]]
            for w, a in zip(moments.weights, moments.amplitudes_ev, strict=True)
        ),
        Fraction(),
    )
    radius = sum(
        (
            abs(w) * dec.noise_fractions[indexes[a]]
            for w, a in zip(moments.weights, moments.amplitudes_ev, strict=True)
        ),
        Fraction(),
    )
    return value, radius


def _tail(dec: OddEvenDecomposition, moments: EstimatorMoments, p_used: int) -> Fraction:
    """R2 maximum over all consecutive divided-difference windows."""
    degree = moments.j0 if p_used == 2 else 1
    nodes = tuple(Fraction(str(a)) ** p_used for a in dec.amplitudes_ev)
    bounds = []
    for start in range(len(nodes) - degree):
        weights = divided_difference_coefficients(nodes[start : start + degree + 1])
        value = sum(
            (w * s for w, s in zip(weights, dec.slope_fractions[start : start + degree + 1], strict=True)),
            Fraction(),
        )
        radius = sum(
            (
                abs(w) * n
                for w, n in zip(weights, dec.noise_fractions[start : start + degree + 1], strict=True)
            ),
            Fraction(),
        )
        bounds.append(abs(value) + radius)
    if not bounds:
        raise ResponseBudgetError("truncation requires enough amplitudes for its divided difference")
    return abs(moments.principal(p_used)) * max(bounds)


def printed_response_budget(series: ElementSeries, estimator: EstimatorSpec) -> PrintedResponseBudget:
    """Apply the declared column functional with TASK 2's additive print radius.

    A single amplitude is sufficient: shadows compare the same finite-amplitude
    estimator, so this gate neither selects an estimator nor invents a tail or
    an SCF floor. TASK 17 must supply its ESTIMATE separately.
    """
    dec = decompose(series, NoiseModel(0.0, 0.0, BoundKind.BOUND))
    value, radius = _value_noise(dec, estimator_moments(estimator))
    return PrintedResponseBudget(
        _derived_finite(value, "estimate_e_per_ev"),
        _derived_finite(radius, "print_bound_e_per_ev"),
        BoundKind.BOUND,
    )


def _candidate(
    dec: OddEvenDecomposition, spec: EstimatorSpec, status: OrderStatus, neighbour: EstimatorSpec | None
) -> CandidateBudget:
    moments = estimator_moments(spec)
    value, radius = _value_noise(dec, moments)
    p_used = 2 if status is OrderStatus.VERIFIED_2 else 1
    reasons = []
    if status is OrderStatus.INCONSISTENT:
        reasons.append(BudgetReason.ORDER_INCONSISTENT)
    elif status is OrderStatus.VERIFIED_1:
        reasons.append(BudgetReason.ORDER_1_VERIFIED)
    elif status is OrderStatus.UNRESOLVED:
        reasons.append(BudgetReason.ORDER_UNRESOLVED_CONSERVATIVE_P1)
    excluded = status is OrderStatus.INCONSISTENT
    if moments.j0 >= 2 and status is not OrderStatus.VERIFIED_2:
        reasons.append(BudgetReason.ORDER_NOT_VERIFIED_FOR_ESTIMATOR)
        excluded = True
    tau, ratio = Fraction(), None
    if not excluded:
        if neighbour is not None:
            next_moments = estimator_moments(neighbour)
            current, next_ = moments.principal(p_used), next_moments.principal(p_used)
            if moments.j0 == next_moments.j0 and current * next_ > 0:
                ratio = next_ / current
                if ratio <= 1:
                    reasons.append(BudgetReason.MOMENT_RATIO_NOT_INCREASING)
                    excluded = True
                else:
                    next_value, next_radius = _value_noise(dec, next_moments)
                    tau = (abs(value - next_value) + radius + next_radius) / (ratio - 1)
            else:
                tau = _tail(dec, moments, p_used)
        else:
            tau = _tail(dec, moments, p_used)
            if moments.j0 >= 2 and len(dec.amplitudes_ev) < moments.j0 + 2:
                reasons.append(BudgetReason.TAIL_UNRESOLVED)
                excluded = True
    return CandidateBudget(
        spec,
        _derived_finite(value, "candidate.estimate_e_per_ev"),
        _derived_finite(radius, "candidate.noise_e_per_ev"),
        _derived_finite(tau, "candidate.truncation_e_per_ev"),
        status,
        not excluded,
        tuple(reasons),
        p_used,
        moments.j0,
        moments.moments,
        ratio,
    )


def candidate_budgets(
    dec: OddEvenDecomposition,
    orders: Sequence[OrderStatus],
    *,
    protocol_estimator: EstimatorSpec | None,
    kappa: float,
) -> tuple[CandidateBudget, ...]:
    """Closed candidate family and R0/R1/R2 budgets with neighbour falsation.

    The family order is the most conservative drift-pair status. The last
    candidate of a family uses R2. Protocol candidates always use R2. A tail
    diagnostic remains visible; no global qualification is produced.
    """
    try:
        factor = require_positive_finite(kappa, "kappa")
    except ValidationError as exc:
        raise ResponseBudgetError(str(exc)) from exc
    expected = verify_order(dec)
    if len(dec.amplitudes_ev) < 2:
        raise ResponseBudgetError("truncation diagnostics require at least two distinct amplitudes")
    if tuple(orders) != expected:
        raise ResponseBudgetError("orders must match verify_order for this decomposition")
    status = _family_order(orders)
    central = tuple(EstimatorSpec(EstimatorKind.CENTRAL, None, (a,)) for a in dec.amplitudes_ev)
    richardson = tuple(
        EstimatorSpec(EstimatorKind.RICHARDSON_2, None, dec.amplitudes_ev[k : k + 2])
        for k in range(len(dec.amplitudes_ev) - 1)
    )
    result = []
    for family in (central, richardson):
        budgets = [
            _candidate(dec, spec, status, family[k + 1] if k + 1 < len(family) else None)
            for k, spec in enumerate(family)
        ]
        for k, candidate in enumerate(budgets):
            if candidate.admissible and any(
                abs(candidate.estimate_e_per_ev - budgets[j].estimate_e_per_ev)
                > factor * (candidate.total_e_per_ev + budgets[j].total_e_per_ev)
                for j in (k - 1, k + 1)
                if 0 <= j < len(budgets) and budgets[j].admissible
            ):
                candidate = replace(
                    candidate,
                    admissible=False,
                    reasons=candidate.reasons + (BudgetReason.NEIGHBOUR_INCONSISTENT,),
                )
            result.append(candidate)
    if protocol_estimator is not None:
        if not isinstance(protocol_estimator, EstimatorSpec):
            raise ResponseBudgetError("protocol_estimator must be an EstimatorSpec or None")
        result.append(_candidate(dec, protocol_estimator, status, None))
    return tuple(result)


def element_report(
    series: ElementSeries, noise: NoiseModel, *, protocol_estimator: EstimatorSpec | None, kappa: float
) -> ElementBudgetReport:
    """Select the smallest conditional budget for diagnostic reporting only.

    Ties use maximum amplitude, then CENTRAL/RICHARDSON/POLYNOMIAL/LINEAR
    family order, then the complete amplitude tuple and polynomial degree.
    """
    dec = decompose(series, noise)
    drifts = tuple(s1 - s0 for s0, s1 in pairwise(dec.slope_fractions))
    ratios = tuple(_derived_finite(d1 / d0, "drift_ratios") if d0 else None for d0, d1 in pairwise(drifts))
    candidates = candidate_budgets(dec, verify_order(dec), protocol_estimator=protocol_estimator, kappa=kappa)
    families = tuple(EstimatorKind)
    admissible = [candidate for candidate in candidates if candidate.admissible]
    tail_fallback = not admissible
    eligible = admissible or [
        candidate for candidate in candidates if BudgetReason.TAIL_UNRESOLVED in candidate.reasons
    ]
    best = (
        min(
            eligible,
            key=lambda c: (
                c.total_e_per_ev,
                max(c.estimator.amplitudes_ev),
                families.index(c.estimator.kind),
                c.estimator.amplitudes_ev,
                c.estimator.polynomial_degree or 0,
            ),
        )
        if eligible
        else None
    )
    return ElementBudgetReport(
        (series.site_perturbed, series.mode, series.site_observed),
        dec,
        ratios,
        candidates,
        best,
        QualificationCap.REVIEW if tail_fallback and best is not None else None,
        (BudgetReason.TAIL_UNRESOLVED,) if tail_fallback and best is not None else (),
    )


def reciprocity(reports: Sequence[ElementBudgetReport], *, kappa: float) -> tuple[ReciprocityResidual, ...]:
    """Report reciprocal best-estimator residuals; missing/unusable pairs emit none."""
    try:
        factor = require_positive_finite(kappa, "kappa")
    except ValidationError as exc:
        raise ResponseBudgetError(str(exc)) from exc
    by_key = {report.series_key: report for report in reports}
    if len(by_key) != len(reports):
        raise ResponseBudgetError("reciprocity reports must have distinct series keys")
    result = []
    for (j, mode, i), report in sorted(by_key.items(), key=lambda item: item[0]):
        partner = by_key.get((i, mode, j))
        if j >= i or partner is None or report.best is None or partner.best is None:
            continue
        residual = abs(report.best.estimate_e_per_ev - partner.best.estimate_e_per_ev)
        allowed = factor * (report.best.total_e_per_ev + partner.best.total_e_per_ev)
        result.append(ReciprocityResidual((j, i), mode, residual, allowed, residual <= allowed))
    return tuple(result)


def u_influence(
    chi0: NDArray[np.float64], chi: NDArray[np.float64]
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Return derivatives with shape (K,I,J); never compute or report U.

    Direct inversion is mandatory. Singular matrices are rejected explicitly;
    no pseudoinverse, symmetrization, or regularization is available here.
    """
    for matrix in (chi0, chi):
        if (
            not isinstance(matrix, np.ndarray)
            or matrix.ndim != 2
            or not matrix.shape[0]
            or matrix.shape[0] != matrix.shape[1]
            or matrix.dtype.kind not in "fi"
            or not np.all(np.isfinite(matrix))
        ):
            raise ResponseBudgetError("influence requires finite real, nonempty square matrices")
    if chi0.shape != chi.shape:
        raise ResponseBudgetError("chi0 and chi must have the same shape")
    try:
        inverse0, inverse = np.linalg.inv(chi0), np.linalg.inv(chi)
    except np.linalg.LinAlgError as exc:
        raise ResponseBudgetError("influence requires nonsingular matrices under direct inversion") from exc
    first = -np.einsum("ki,jk->kij", inverse0, inverse0)
    second = np.einsum("ki,jk->kij", inverse, inverse)
    if not np.all(np.isfinite(first)) or not np.all(np.isfinite(second)):
        raise ResponseBudgetError("influence overflows finite floating-point output")
    return first, second
