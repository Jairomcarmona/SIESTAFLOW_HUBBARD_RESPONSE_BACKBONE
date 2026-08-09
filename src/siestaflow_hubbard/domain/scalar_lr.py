"""
scalar_lr.py – reusable scalar linear-response functions.

These functions are not tied to MnO. MnO is only the validation fixture.
All quantities in eV unless noted.

Design principles:
- No hardcoded scientific acceptance thresholds.
- If a NumericalLinearityPolicy is supplied, it gates the verdict.
- If no policy is supplied, all diagnostics are reported and scientific_verdict
  is set to DIAGNOSTICS_ONLY (no threshold-based classification is applied).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence, Optional
import numpy as np


# ─────────────────────────────────────────────
# POLICY (optional)
# ─────────────────────────────────────────────

@dataclass
class NumericalLinearityPolicy:
    """
    Explicit, caller-supplied thresholds for scientific classification.
    If this is not provided, no automatic STABLE/WINDOW_DEPENDENT/INVALID
    verdict is assigned — only diagnostics are reported.

    All fields are optional. Unset fields are ignored.
    """
    min_r2_bare: Optional[float] = None
    min_r2_screened: Optional[float] = None
    max_asymmetry_001: Optional[float] = None
    max_asymmetry_002: Optional[float] = None
    max_u_rel_diff: Optional[float] = None
    max_chi0_rel_diff: Optional[float] = None
    max_chi_rel_diff: Optional[float] = None


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
    # one-sided slopes (finite difference from alpha=0)
    left_slope_001: float = float("nan")   # (n(0) - n(-0.01)) / 0.01
    right_slope_001: float = float("nan")  # (n(+0.01) - n(0))  / 0.01
    left_slope_002: float = float("nan")   # (n(0) - n(-0.02)) / 0.02
    right_slope_002: float = float("nan")  # (n(+0.02) - n(0))  / 0.02
    asymmetry_001: float = float("nan")    # |right - left| / (|right| + |left|)
    asymmetry_002: float = float("nan")
    # symmetric central-difference slope
    central_slope_001: float = float("nan")  # (n(+0.01) - n(-0.01)) / 0.02
    central_slope_002: float = float("nan")  # (n(+0.02) - n(-0.02)) / 0.04


@dataclass
class ScalarResponseResult:
    """Complete scalar LR result for one (projector, site) pair."""
    # Fits
    bare_full: LinearFit
    bare_inner: LinearFit        # inner 3-point window
    screened_full: LinearFit
    screened_inner: LinearFit

    # Response functions from OLS fits
    chi0_full: float
    chi0_inner: float
    chi_full: float
    chi_inner: float

    # Symmetric central-difference estimates
    chi0_central_001: float
    chi0_central_002: float
    chi_central_001: float
    chi_central_002: float

    # U values (eV)
    U_full: float
    U_inner: float
    U_central_001: float
    U_central_002: float
    U_abs_diff: float      # |U_full - U_inner|
    U_rel_diff: float      # U_abs_diff / |U_full|

    # Diagnostics
    n_ref_spread: float          # max - min of n_ref across alpha
    restart_drift: float         # n0(0) - n_ref(0)   [diagnostic only]
    screened_alpha0_drift: float # n(0)  - n_ref(0)   [diagnostic only]
    chi0_rel_diff: float         # |chi0_full - chi0_inner| / |chi0_full|
    chi_rel_diff: float

    # Verdict
    scientific_verdict: str   # STABLE | WINDOW_DEPENDENT | INVALID | DIAGNOSTICS_ONLY

    # Raw table
    points: list[ResponsePoint] = field(default_factory=list)


# ─────────────────────────────────────────────
# CORE MATHEMATICAL FUNCTIONS
# ─────────────────────────────────────────────

def fit_response(alpha: Sequence[float], occupations: Sequence[float]) -> LinearFit:
    """
    Fit n(alpha) = intercept + slope * alpha using OLS.
    alpha and occupations must have the same length (>= 2).
    Computes one-sided and symmetric central-difference diagnostics
    when alpha=0, ±0.01, ±0.02 are present.
    """
    a = np.asarray(alpha, dtype=float)
    n = np.asarray(occupations, dtype=float)
    if len(a) < 2:
        raise ValueError("fit_response requires at least 2 points")

    X = np.column_stack([np.ones_like(a), a])
    coeffs, _, _, _ = np.linalg.lstsq(X, n, rcond=None)
    intercept, slope = float(coeffs[0]), float(coeffs[1])

    n_pred = intercept + slope * a
    residuals = list(n - n_pred)
    max_abs_residual = float(np.max(np.abs(n - n_pred)))

    ss_res = float(np.sum((n - n_pred) ** 2))
    ss_tot = float(np.sum((n - np.mean(n)) ** 2))
    r_squared = 1.0 - ss_res / ss_tot if ss_tot > 1e-30 else float("nan")

    # Build lookup: alpha_value -> occupation_value
    alpha_to_n: dict[float, float] = {}
    for ai, ni in zip(a.tolist(), n.tolist()):
        alpha_to_n[round(ai, 6)] = ni

    def get(av: float):
        return alpha_to_n.get(round(av, 6), None)

    n0 = get(0.0)
    nm01 = get(-0.01)
    np01 = get(+0.01)
    nm02 = get(-0.02)
    np02 = get(+0.02)

    # One-sided slopes from alpha=0
    left_slope_001 = (n0 - nm01) / 0.01 if (n0 is not None and nm01 is not None) else float("nan")
    right_slope_001 = (np01 - n0) / 0.01 if (n0 is not None and np01 is not None) else float("nan")
    left_slope_002 = (n0 - nm02) / 0.02 if (n0 is not None and nm02 is not None) else float("nan")
    right_slope_002 = (np02 - n0) / 0.02 if (n0 is not None and np02 is not None) else float("nan")

    def asymmetry(left: float, right: float) -> float:
        denom = abs(left) + abs(right)
        return abs(right - left) / denom if denom > 1e-30 else float("nan")

    asym_001 = asymmetry(left_slope_001, right_slope_001)
    asym_002 = asymmetry(left_slope_002, right_slope_002)

    # Symmetric central-difference slopes
    central_001 = (np01 - nm01) / 0.02 if (np01 is not None and nm01 is not None) else float("nan")
    central_002 = (np02 - nm02) / 0.04 if (np02 is not None and nm02 is not None) else float("nan")

    return LinearFit(
        slope=slope,
        intercept=intercept,
        r_squared=r_squared,
        residuals=residuals,
        max_abs_residual=max_abs_residual,
        n_points=len(a),
        left_slope_001=left_slope_001,
        right_slope_001=right_slope_001,
        left_slope_002=left_slope_002,
        right_slope_002=right_slope_002,
        asymmetry_001=asym_001,
        asymmetry_002=asym_002,
        central_slope_001=central_001,
        central_slope_002=central_002,
    )


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


def _apply_policy_verdict(
    result: "ScalarResponseResult",
    policy: NumericalLinearityPolicy,
) -> str:
    """
    Apply caller-supplied policy thresholds to assign a verdict.
    Returns STABLE, WINDOW_DEPENDENT, or INVALID.
    """
    invalid = False
    window_dep = False

    bf = result.bare_full
    sf = result.screened_full

    if policy.min_r2_bare is not None and not np.isnan(bf.r_squared):
        if bf.r_squared < policy.min_r2_bare:
            invalid = True

    if policy.min_r2_screened is not None and not np.isnan(sf.r_squared):
        if sf.r_squared < policy.min_r2_screened:
            invalid = True

    if policy.max_asymmetry_001 is not None:
        for asym in [bf.asymmetry_001, sf.asymmetry_001]:
            if not np.isnan(asym) and asym > policy.max_asymmetry_001:
                window_dep = True

    if policy.max_asymmetry_002 is not None:
        for asym in [bf.asymmetry_002, sf.asymmetry_002]:
            if not np.isnan(asym) and asym > policy.max_asymmetry_002:
                window_dep = True

    if policy.max_u_rel_diff is not None:
        if result.U_rel_diff > policy.max_u_rel_diff:
            window_dep = True

    if policy.max_chi0_rel_diff is not None:
        if result.chi0_rel_diff > policy.max_chi0_rel_diff:
            window_dep = True

    if policy.max_chi_rel_diff is not None:
        if result.chi_rel_diff > policy.max_chi_rel_diff:
            window_dep = True

    if invalid:
        return "INVALID"
    if window_dep:
        return "WINDOW_DEPENDENT"
    return "STABLE"


def analyze_scalar_response_campaign(
    points: list[ResponsePoint],
    policy: Optional[NumericalLinearityPolicy] = None,
) -> ScalarResponseResult:
    """
    Run the complete scalar LR analysis on a list of ResponsePoint objects.

    Parameters
    ----------
    points : list[ResponsePoint]
        Five-point grid or subset. alpha=0 may be included.
    policy : NumericalLinearityPolicy, optional
        If supplied, gates scientific_verdict using the provided thresholds.
        If None, scientific_verdict = 'DIAGNOSTICS_ONLY'.

    Returns
    -------
    ScalarResponseResult
    """
    pts = sorted(points, key=lambda p: p.alpha)

    alphas = np.array([p.alpha for p in pts])
    n_refs = np.array([p.n_ref for p in pts])
    n0s = np.array([p.n0 for p in pts])
    ns = np.array([p.n for p in pts])

    # Full fits
    bare_full = fit_response(alphas, n0s)
    screened_full = fit_response(alphas, ns)

    # Inner 3-point fits (|alpha| <= 0.011)
    inner_mask = np.array([abs(a) <= 0.011 for a in alphas])
    if inner_mask.sum() < 2:
        raise ValueError("Inner window has fewer than 2 points")
    bare_inner = fit_response(alphas[inner_mask], n0s[inner_mask])
    screened_inner = fit_response(alphas[inner_mask], ns[inner_mask])

    chi0_full = bare_full.slope
    chi0_inner = bare_inner.slope
    chi_full = screened_full.slope
    chi_inner = screened_inner.slope

    # Symmetric central-difference estimates
    chi0_central_001 = bare_full.central_slope_001
    chi0_central_002 = bare_full.central_slope_002
    chi_central_001 = screened_full.central_slope_001
    chi_central_002 = screened_full.central_slope_002

    # Relative differences
    chi0_rel_diff = abs(chi0_full - chi0_inner) / (abs(chi0_full) + 1e-30)
    chi_rel_diff = abs(chi_full - chi_inner) / (abs(chi_full) + 1e-30)

    # U from OLS fits
    if abs(chi0_full) < 1e-10:
        raise ZeroDivisionError(f"chi0_full is effectively zero: {chi0_full}")
    if abs(chi_full) < 1e-10:
        raise ZeroDivisionError(f"chi_full is effectively zero: {chi_full}")

    U_full = compute_scalar_u(chi0_full, chi_full)
    U_inner = compute_scalar_u(chi0_inner, chi_inner)
    U_abs_diff = abs(U_full - U_inner)
    U_rel_diff = U_abs_diff / (abs(U_full) + 1e-30)

    # U from symmetric central differences
    U_central_001 = (
        compute_scalar_u(chi0_central_001, chi_central_001)
        if (not np.isnan(chi0_central_001) and not np.isnan(chi_central_001)
            and abs(chi0_central_001) > 1e-10 and abs(chi_central_001) > 1e-10)
        else float("nan")
    )
    U_central_002 = (
        compute_scalar_u(chi0_central_002, chi_central_002)
        if (not np.isnan(chi0_central_002) and not np.isnan(chi_central_002)
            and abs(chi0_central_002) > 1e-10 and abs(chi_central_002) > 1e-10)
        else float("nan")
    )

    # Alpha=0 diagnostics
    n_ref_spread = float(np.max(n_refs) - np.min(n_refs))
    zero_mask = np.isclose(alphas, 0.0, atol=1e-9)
    if zero_mask.any():
        idx0 = int(np.where(zero_mask)[0][0])
        restart_drift = float(n0s[idx0] - n_refs[idx0])
        screened_alpha0_drift = float(ns[idx0] - n_refs[idx0])
    else:
        restart_drift = float("nan")
        screened_alpha0_drift = float("nan")

    # Partial result (verdict filled below)
    result = ScalarResponseResult(
        bare_full=bare_full,
        bare_inner=bare_inner,
        screened_full=screened_full,
        screened_inner=screened_inner,
        chi0_full=chi0_full,
        chi0_inner=chi0_inner,
        chi_full=chi_full,
        chi_inner=chi_inner,
        chi0_central_001=chi0_central_001,
        chi0_central_002=chi0_central_002,
        chi_central_001=chi_central_001,
        chi_central_002=chi_central_002,
        U_full=U_full,
        U_inner=U_inner,
        U_central_001=U_central_001,
        U_central_002=U_central_002,
        U_abs_diff=U_abs_diff,
        U_rel_diff=U_rel_diff,
        n_ref_spread=n_ref_spread,
        restart_drift=restart_drift,
        screened_alpha0_drift=screened_alpha0_drift,
        chi0_rel_diff=chi0_rel_diff,
        chi_rel_diff=chi_rel_diff,
        scientific_verdict="DIAGNOSTICS_ONLY",
        points=pts,
    )

    # Apply policy if provided
    if policy is not None:
        result.scientific_verdict = _apply_policy_verdict(result, policy)

    return result
