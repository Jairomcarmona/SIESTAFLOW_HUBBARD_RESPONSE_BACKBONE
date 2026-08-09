"""
scalar_lr.py – reusable scalar linear-response functions.

These functions are *not* tied to MnO. MnO is only the validation fixture.
All quantities in eV unless noted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence, Optional, Tuple
import numpy as np


# ─────────────────────────────────────────────
# DATA STRUCTURES
# ─────────────────────────────────────────────

@dataclass
class ResponsePoint:
    """One alpha point in the response campaign."""
    alpha: float           # perturbation strength (eV)
    n_ref: float           # population at SCF iter 1 (reference)
    n0: float              # BARE occupation after 2 SCF steps
    n: float               # SCREENED occupation (converged)
    # provenance
    bare_fdf_sha256: str = ""
    bare_out_sha256: str = ""
    screened_fdf_sha256: str = ""
    screened_out_sha256: str = ""
    parent_dm_sha256: str = ""
    projector_fingerprint: str = ""


@dataclass
class LinearFit:
    """Result of a 1-D linear regression n = intercept + slope * alpha."""
    slope: float
    intercept: float
    r_squared: float
    residuals: list[float] = field(default_factory=list)
    max_abs_residual: float = 0.0
    n_points: int = 0
    left_slope: float = float("nan")   # finite-diff slope for negative half
    right_slope: float = float("nan")  # finite-diff slope for positive half
    asymmetry: float = float("nan")    # |right - left| / (|right| + |left|)
    asymmetry_001: float = float("nan")
    asymmetry_002: float = float("nan")


@dataclass
class ScalarResponseResult:
    """Complete scalar LR result for one (projector, site) pair."""
    # Fits
    bare_full: LinearFit
    bare_inner: LinearFit        # inner 3-point window
    screened_full: LinearFit
    screened_inner: LinearFit

    # Response functions
    chi0_full: float
    chi0_inner: float
    chi_full: float
    chi_inner: float

    # U values (eV)
    U_full: float
    U_inner: float
    U_abs_diff: float
    U_rel_diff: float

    # Diagnostics
    n_ref_spread: float          # max - min of n_ref across alpha
    restart_drift: float         # n0(0) - n_ref(0)
    screened_alpha0_drift: float # n(0)  - n_ref(0)
    chi0_rel_diff: float
    chi_rel_diff: float

    # Verdict
    scientific_verdict: str      # STABLE | WINDOW_DEPENDENT | INVALID

    # Raw table
    points: list[ResponsePoint] = field(default_factory=list)


# ─────────────────────────────────────────────
# CORE MATHEMATICAL FUNCTIONS
# ─────────────────────────────────────────────

def fit_response(alpha: Sequence[float], occupations: Sequence[float]) -> LinearFit:
    """
    Fit n(alpha) = intercept + slope * alpha using OLS.
    alpha and occupations must have the same length (>= 2).
    """
    a = np.asarray(alpha, dtype=float)
    n = np.asarray(occupations, dtype=float)
    if len(a) < 2:
        raise ValueError("fit_response requires at least 2 points")

    # Build design matrix [1  alpha]
    X = np.column_stack([np.ones_like(a), a])
    coeffs, residuals_sq, rank, sv = np.linalg.lstsq(X, n, rcond=None)
    intercept, slope = float(coeffs[0]), float(coeffs[1])

    n_pred = intercept + slope * a
    residuals = list(n - n_pred)
    max_abs_residual = float(np.max(np.abs(n - n_pred)))

    ss_res = float(np.sum((n - n_pred) ** 2))
    ss_tot = float(np.sum((n - np.mean(n)) ** 2))
    r_squared = 1.0 - ss_res / ss_tot if ss_tot > 1e-30 else float("nan")

    # Asymmetry diagnostics (only on full 5-point grid)
    left_slope = right_slope = asymmetry = float("nan")
    asymmetry_001 = asymmetry_002 = float("nan")

    # inner-point finite differences if zero is present
    a_sorted = sorted(zip(a, n), key=lambda x: x[0])
    a_vals = [x[0] for x in a_sorted]
    n_vals = [x[1] for x in a_sorted]

    if 0.0 in a_vals:
        idx0 = a_vals.index(0.0)
        n0_val = n_vals[idx0]

        # ±0.01 asymmetry
        if -0.01 in a_vals and 0.01 in a_vals:
            idx_m = a_vals.index(-0.01)
            idx_p = a_vals.index(0.01)
            left_slope_001 = (n0_val - n_vals[idx_m]) / 0.01
            right_slope_001 = (n_vals[idx_p] - n0_val) / 0.01
            denom = abs(right_slope_001) + abs(left_slope_001)
            asymmetry_001 = (
                abs(right_slope_001 - left_slope_001) / denom
                if denom > 1e-30 else float("nan")
            )
            left_slope = left_slope_001
            right_slope = right_slope_001
            denom2 = abs(right_slope) + abs(left_slope)
            asymmetry = abs(right_slope - left_slope) / denom2 if denom2 > 1e-30 else float("nan")

        # ±0.02 asymmetry
        if -0.02 in a_vals and 0.02 in a_vals:
            idx_m2 = a_vals.index(-0.02)
            idx_p2 = a_vals.index(0.02)
            left_slope_002 = (n0_val - n_vals[idx_m2]) / 0.02
            right_slope_002 = (n_vals[idx_p2] - n0_val) / 0.02
            denom2 = abs(right_slope_002) + abs(left_slope_002)
            asymmetry_002 = (
                abs(right_slope_002 - left_slope_002) / denom2
                if denom2 > 1e-30 else float("nan")
            )

    return LinearFit(
        slope=slope,
        intercept=intercept,
        r_squared=r_squared,
        residuals=residuals,
        max_abs_residual=max_abs_residual,
        n_points=len(a),
        left_slope=left_slope,
        right_slope=right_slope,
        asymmetry=asymmetry,
        asymmetry_001=asymmetry_001,
        asymmetry_002=asymmetry_002,
    )


def evaluate_linearity(fit: LinearFit, r2_threshold: float = 0.999) -> str:
    """
    Return a linearity label based on fit quality diagnostics.
    Returns one of: 'LINEAR', 'MARGINAL', 'NONLINEAR'
    """
    if np.isnan(fit.r_squared):
        return "NONLINEAR"
    if fit.r_squared >= r2_threshold:
        # Check asymmetry if available
        if not np.isnan(fit.asymmetry_001) and fit.asymmetry_001 > 0.05:
            return "MARGINAL"
        return "LINEAR"
    elif fit.r_squared >= 0.99:
        return "MARGINAL"
    else:
        return "NONLINEAR"


def compute_scalar_u(chi0: float, chi: float) -> float:
    """
    U = 1/chi0 - 1/chi  (eV).
    Raises ZeroDivisionError if chi0 or chi is zero.
    """
    if chi0 == 0.0:
        raise ZeroDivisionError("chi0 is zero – cannot compute U")
    if chi == 0.0:
        raise ZeroDivisionError("chi is zero – cannot compute U")
    return 1.0 / chi0 - 1.0 / chi


def analyze_scalar_response_campaign(
    points: list[ResponsePoint],
    alpha0_n_ref: Optional[float] = None,
    alpha0_n0: Optional[float] = None,
    alpha0_n: Optional[float] = None,
) -> ScalarResponseResult:
    """
    Run the complete scalar LR analysis on a list of ResponsePoint objects.

    Parameters
    ----------
    points : list[ResponsePoint]
        Must contain the five-point grid (at minimum). alpha=0 can be included.
    alpha0_n_ref, alpha0_n0, alpha0_n : floats
        Optional explicit overrides for alpha=0 observables (from P4-B).
        If alpha=0 is already in `points`, these are ignored.

    Returns
    -------
    ScalarResponseResult
    """
    # Sort by alpha
    pts = sorted(points, key=lambda p: p.alpha)

    alphas = np.array([p.alpha for p in pts])
    n_refs = np.array([p.n_ref for p in pts])
    n0s = np.array([p.n0 for p in pts])
    ns = np.array([p.n for p in pts])

    # Full 5-point fits
    bare_full = fit_response(alphas, n0s)
    screened_full = fit_response(alphas, ns)

    # Inner 3-point fits (alpha in {-0.01, 0.00, +0.01})
    inner_mask = np.array([abs(a) <= 0.011 for a in alphas])
    if inner_mask.sum() < 2:
        raise ValueError("Inner window has fewer than 2 points")
    bare_inner = fit_response(alphas[inner_mask], n0s[inner_mask])
    screened_inner = fit_response(alphas[inner_mask], ns[inner_mask])

    chi0_full = bare_full.slope
    chi0_inner = bare_inner.slope
    chi_full = screened_full.slope
    chi_inner = screened_inner.slope

    # Relative differences
    chi0_rel_diff = (
        abs(chi0_full - chi0_inner) / (abs(chi0_full) + 1e-30)
    )
    chi_rel_diff = (
        abs(chi_full - chi_inner) / (abs(chi_full) + 1e-30)
    )

    # Validate chi0 and chi are nonzero before computing U
    if abs(chi0_full) < 1e-10:
        raise ZeroDivisionError(f"chi0_full is effectively zero: {chi0_full}")
    if abs(chi_full) < 1e-10:
        raise ZeroDivisionError(f"chi_full is effectively zero: {chi_full}")

    U_full = compute_scalar_u(chi0_full, chi_full)
    U_inner = compute_scalar_u(chi0_inner, chi_inner)
    U_abs_diff = abs(U_full - U_inner)
    U_rel_diff = U_abs_diff / (abs(U_full) + 1e-30)

    # Diagnostics
    n_ref_spread = float(np.max(n_refs) - np.min(n_refs))

    # alpha=0 diagnostics
    zero_mask = np.isclose(alphas, 0.0, atol=1e-9)
    if zero_mask.any():
        idx0 = int(np.where(zero_mask)[0][0])
        restart_drift = float(n0s[idx0] - n_refs[idx0])
        screened_alpha0_drift = float(ns[idx0] - n_refs[idx0])
    elif alpha0_n0 is not None and alpha0_n_ref is not None:
        restart_drift = float(alpha0_n0 - alpha0_n_ref)
        screened_alpha0_drift = float(alpha0_n - alpha0_n_ref) if alpha0_n is not None else float("nan")
    else:
        restart_drift = float("nan")
        screened_alpha0_drift = float("nan")

    # Scientific verdict
    bare_linearity = evaluate_linearity(bare_full)
    screened_linearity = evaluate_linearity(screened_full)

    U_stable = (U_rel_diff < 0.10)  # < 10% window sensitivity
    chi0_stable = (chi0_rel_diff < 0.05)
    chi_stable = (chi_rel_diff < 0.05)

    if (
        bare_linearity == "LINEAR"
        and screened_linearity == "LINEAR"
        and U_stable
        and chi0_stable
        and chi_stable
    ):
        verdict = "STABLE"
    elif bare_linearity == "NONLINEAR" or screened_linearity == "NONLINEAR":
        verdict = "INVALID"
    else:
        verdict = "WINDOW_DEPENDENT"

    return ScalarResponseResult(
        bare_full=bare_full,
        bare_inner=bare_inner,
        screened_full=screened_full,
        screened_inner=screened_inner,
        chi0_full=chi0_full,
        chi0_inner=chi0_inner,
        chi_full=chi_full,
        chi_inner=chi_inner,
        U_full=U_full,
        U_inner=U_inner,
        U_abs_diff=U_abs_diff,
        U_rel_diff=U_rel_diff,
        n_ref_spread=n_ref_spread,
        restart_drift=restart_drift,
        screened_alpha0_drift=screened_alpha0_drift,
        chi0_rel_diff=chi0_rel_diff,
        chi_rel_diff=chi_rel_diff,
        scientific_verdict=verdict,
        points=pts,
    )
