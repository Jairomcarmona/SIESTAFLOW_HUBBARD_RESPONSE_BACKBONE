"""Full elementwise model boxes evaluated by the unchanged U interval routines.

The interval evaluation is conditional on TASK2 truncation and TASK17 SCF
models. First-order influences rank refinement requests only, never acceptance.
"""

from __future__ import annotations

from collections.abc import Sequence
from fractions import Fraction
from typing import cast

import numpy as np
from numpy.typing import NDArray

from .fdebq_models import ConditionalMatrixQualification, FdebqRoundsError, RoundReason
from .response_error_budget import u_influence
from .u_certification import CertificationError, Interval, certify_u_matrices
from .validation import require_finite, require_positive_finite

LABEL = "calificación condicional al modelo de error"


def full_budget_box(
    centers_e_per_ev: Sequence[Sequence[float]], radii_e_per_ev: Sequence[Sequence[Fraction]]
) -> tuple[tuple[Interval, ...], ...]:
    """Each IJ entry receives its own additive print+truncation+SCF radius."""
    n = len(centers_e_per_ev)
    if (
        n < 2
        or len(radii_e_per_ev) != n
        or any(len(row) != n for matrix in (centers_e_per_ev, radii_e_per_ev) for row in matrix)
    ):
        raise FdebqRoundsError("full budget box requires same-size square matrices with at least two sites")
    out = []
    for values, radii in zip(centers_e_per_ev, radii_e_per_ev, strict=True):
        row = []
        for value, radius in zip(values, radii, strict=True):
            try:
                center = Fraction(str(require_finite(value, "matrix center")))
                if not isinstance(radius, Fraction) or radius < 0:
                    raise FdebqRoundsError("elementwise radii must be nonnegative Fractions")
                require_finite(radius, "matrix radius")
                row.append(Interval.around(center, radius))
            except ValueError as exc:
                raise FdebqRoundsError(str(exc)) from exc
        out.append(tuple(row))
    return tuple(out)


def qualify_matrices(
    chi0_e_per_ev: Sequence[Sequence[float]],
    chi_e_per_ev: Sequence[Sequence[float]],
    budget0_e_per_ev: Sequence[Sequence[Fraction]],
    budget_e_per_ev: Sequence[Sequence[Fraction]],
    *,
    tau_u_ev: float,
) -> ConditionalMatrixQualification:
    """D4 requires both strict spectral beta gates and the full U box gate.

    No U value or condition number enters estimator/amplitude selection. A
    singular midpoint is an actionable direct-inversion error, never a fallback.
    """
    try:
        tau = Fraction(str(require_positive_finite(tau_u_ev, "tau_u_ev")))
        box0 = full_budget_box(chi0_e_per_ev, budget0_e_per_ev)
        box = full_budget_box(chi_e_per_ev, budget_e_per_ev)
        if len(box0) != len(box):
            raise FdebqRoundsError("BARE and SCREENED matrix sizes disagree")
        matrix0, matrix = np.asarray(chi0_e_per_ev, dtype=float), np.asarray(chi_e_per_ev, dtype=float)
        inverse0, inverse = np.linalg.inv(matrix0), np.linalg.inv(matrix)
        beta0 = require_finite(
            float(np.linalg.norm(inverse0, 2) * np.linalg.norm(np.asarray(budget0_e_per_ev, dtype=float), 2)),
            "beta0",
        )
        beta = require_finite(
            float(np.linalg.norm(inverse, 2) * np.linalg.norm(np.asarray(budget_e_per_ev, dtype=float), 2)),
            "beta",
        )
    except (ValueError, np.linalg.LinAlgError) as exc:
        raise FdebqRoundsError(
            f"matrix qualification requires finite nonsingular direct inverses: {exc}"
        ) from exc
    if beta0 >= 1 or beta >= 1:
        return ConditionalMatrixQualification(
            beta0, beta, (), False, (RoundReason.MATRIX_NOT_RESOLVED,), LABEL
        )
    try:
        evaluation = certify_u_matrices(box0, box)
    except CertificationError as exc:
        if str(exc) == "INCONSISTENT_CERTIFIERS":
            raise FdebqRoundsError(str(exc)) from exc
        return ConditionalMatrixQualification(
            beta0, beta, (), False, (RoundReason.MATRIX_NOT_RESOLVED,), LABEL
        )
    raw = evaluation.get("half_width_by_site")
    if raw is None:
        return ConditionalMatrixQualification(
            beta0, beta, (), False, (RoundReason.MATRIX_NOT_RESOLVED,), LABEL
        )
    radii = tuple(Fraction(value) for value in cast(Sequence[str], raw))
    passed = all(radius <= tau for radius in radii)
    return ConditionalMatrixQualification(
        beta0,
        beta,
        tuple(require_finite(r, "U half width") for r in radii),
        passed,
        () if passed else (RoundReason.REQUIREMENT_NOT_MET,),
        LABEL,
    )


def column_influences(
    chi0_e_per_ev: NDArray[np.float64],
    chi_e_per_ev: NDArray[np.float64],
    budget0_e_per_ev: NDArray[np.float64],
    budget_e_per_ev: NDArray[np.float64],
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Max over K of each column's sum over I, separately for both modes.

    Scores use |A_KI A_JK| B0_IJ and |inverse(chi)_KI inverse(chi)_JK| B_IJ.
    These are derivatives of the model at the estimated matrices, not U.
    """
    try:
        bare, screened = u_influence(chi0_e_per_ev, chi_e_per_ev)
        for budget in (budget0_e_per_ev, budget_e_per_ev):
            if budget.shape != chi0_e_per_ev.shape or not np.all(np.isfinite(budget)) or np.any(budget < 0):
                raise FdebqRoundsError("influence budgets require finite nonnegative matrix radii")
        result = []
        for weights, budget in ((bare, budget0_e_per_ev), (screened, budget_e_per_ev)):
            scores = np.max(np.sum(np.abs(weights) * budget[None, :, :], axis=1), axis=0)
            result.append(tuple(require_finite(float(v), "column influence") for v in scores))
        return result[0], result[1]
    except ValueError as exc:
        raise FdebqRoundsError(str(exc)) from exc
