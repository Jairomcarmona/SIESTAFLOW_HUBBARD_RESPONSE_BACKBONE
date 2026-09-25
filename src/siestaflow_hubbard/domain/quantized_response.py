"""Deterministic uncertainty propagation for printed linear-response data.

SIESTA occupation summaries and printed projector matrices may have different
decimal precision.  This module carries the source observable's rounding
interval through a centered linear fit and a directly inverted response
matrix.  It does not assign a statistical confidence level to print rounding.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class CenteredLinearFit:
    intercept: np.ndarray
    slope: np.ndarray
    residuals: np.ndarray
    slope_half_width: np.ndarray
    coefficients: np.ndarray


def fit_centered_linear_response(
    alpha_ev: np.ndarray,
    observations: np.ndarray,
    observation_half_width: np.ndarray,
) -> CenteredLinearFit:
    """Fit intercept+slope*alpha and propagate independent print intervals.

    ``observations`` and ``observation_half_width`` are shaped ``(n, channels)``
    (one-dimensional vectors are accepted).  For OLS slope coefficients
    ``c_i``, bounded output rounding propagates as ``sum(abs(c_i)*h_i)``.
    """
    x = np.asarray(alpha_ev, dtype=float)
    y = np.asarray(observations, dtype=float)
    h = np.asarray(observation_half_width, dtype=float)
    if y.ndim == 1:
        y = y[:, None]
    if h.ndim == 1:
        h = h[:, None]
    if x.ndim != 1 or y.ndim != 2 or h.shape not in ((len(x), 1), y.shape):
        raise ValueError("alpha, observations, and rounding intervals have incompatible shapes")
    if y.shape[0] != len(x) or y.shape[1] == 0:
        raise ValueError("observations must have one row per alpha and at least one channel")
    if h.shape[1] == 1 and y.shape[1] != 1:
        h = np.broadcast_to(h, y.shape)
    if (not np.all(np.isfinite(x)) or not np.all(np.isfinite(y))
            or not np.all(np.isfinite(h)) or np.any(h < 0.0)):
        raise ValueError("response observations and rounding intervals must be finite; intervals nonnegative")
    centered = x - float(np.mean(x))
    denominator = float(centered @ centered)
    if denominator <= 0.0:
        raise ValueError("at least two distinct alpha values are required")
    coefficients = centered / denominator
    slope = coefficients @ y
    intercept = np.mean(y, axis=0) - float(np.mean(x)) * slope
    residuals = y - (intercept[None, :] + x[:, None] * slope[None, :])
    bound = np.abs(coefficients) @ h
    return CenteredLinearFit(intercept, slope, residuals, bound, coefficients)


def inverse_rounding_bound(matrix: np.ndarray, component_half_width: np.ndarray) -> dict[str, object]:
    """Bound inverse perturbation for a matrix with componentwise intervals.

    The matrix and interval are symmetrized as in the response analysis.  A
    finite bound is returned only when every perturbation inside the interval
    leaves the matrix invertible (beta < 1).
    """
    raw = np.asarray(matrix, dtype=float)
    widths = np.asarray(component_half_width, dtype=float)
    if raw.ndim != 2 or raw.shape[0] != raw.shape[1] or widths.shape != raw.shape:
        raise ValueError("response matrix and component intervals must be equally sized square matrices")
    if not np.all(np.isfinite(raw)) or not np.all(np.isfinite(widths)) or np.any(widths < 0.0):
        raise ValueError("response matrix and component intervals must be finite; intervals nonnegative")
    symmetric = (raw + raw.T) / 2.0
    delta = (widths + widths.T) / 2.0
    rank = int(np.linalg.matrix_rank(symmetric))
    condition = float(np.linalg.cond(symmetric))
    if rank != len(symmetric):
        return {"robustly_invertible": False, "rank": rank, "condition_number": condition,
                "beta": float("inf"), "inverse_error_bound": None, "matrix": symmetric, "inverse": None}
    inverse = np.linalg.inv(symmetric)
    inverse_norm = float(np.linalg.norm(inverse, 2))
    delta_norm = float(np.linalg.norm(delta, 2))
    beta = inverse_norm * delta_norm
    robust = beta < 1.0
    error = inverse_norm**2 * delta_norm / (1.0 - beta) if robust else None
    return {"robustly_invertible": robust, "rank": rank, "condition_number": condition,
            "beta": beta, "inverse_error_bound": error, "matrix": symmetric, "inverse": inverse}


def hubbard_u_interval(
    chi0: np.ndarray,
    chi: np.ndarray,
    chi0_half_width: np.ndarray,
    chi_half_width: np.ndarray,
) -> dict[str, object]:
    """Return the point U and conservative interval from two response matrices."""
    bare = inverse_rounding_bound(chi0, chi0_half_width)
    screened = inverse_rounding_bound(chi, chi_half_width)
    robust = bool(bare["robustly_invertible"] and screened["robustly_invertible"])
    if not robust:
        return {"robustly_invertible": False, "chi0": bare, "chi": screened,
                "u_eV_point": None, "u_eV_interval": None, "u_by_site_eV": None}
    u_by_site = np.diag(bare["inverse"] - screened["inverse"])
    point = float(np.mean(u_by_site))
    half_width = float(bare["inverse_error_bound"] + screened["inverse_error_bound"])
    return {"robustly_invertible": True, "chi0": bare, "chi": screened,
            "u_eV_point": point, "u_eV_interval": [point - half_width, point + half_width],
            "u_by_site_eV": u_by_site}
