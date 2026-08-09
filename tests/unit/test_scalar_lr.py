"""Tests for the scalar_lr production module.

Priorities:
  - mathematical correctness of fit_response and compute_scalar_u
  - policy-gated verdict correctness
  - real MnO data (actual measurements from P4-C)
"""

import pytest
import math
import numpy as np

from siestaflow_hubbard.domain.scalar_lr import (
    ResponsePoint,
    LinearFit,
    NumericalLinearityPolicy,
    fit_response,
    compute_scalar_u,
    analyze_scalar_response_campaign,
)

# ─────────────────────────────────────────────
# REAL MnO DATASET (P4-C measurements)
# ─────────────────────────────────────────────
MNO_ALPHA  = [-0.02, -0.01,  0.00,  0.01,  0.02]
MNO_N_REF  = [5.372250, 5.372250, 5.372250, 5.372250, 5.372250]
MNO_N0     = [5.528550, 5.443350, 5.368340, 5.302770, 5.245810]
MNO_N_SCRN = [5.374180, 5.373200, 5.372140, 5.371130, 5.370070]

def _mno_points():
    return [
        ResponsePoint(alpha=a, n_ref=r, n0=b, n=s)
        for a, r, b, s in zip(MNO_ALPHA, MNO_N_REF, MNO_N0, MNO_N_SCRN)
    ]


# ─────────────────────────────────────────────
# fit_response tests
# ─────────────────────────────────────────────

def test_fit_response_exact_linear_data():
    """Exact synthetic linear data must recover exact chi."""
    chi_true = 0.5
    intercept_true = 5.37
    alpha = [-0.02, -0.01, 0.00, 0.01, 0.02]
    n = [intercept_true + chi_true * a for a in alpha]

    fit = fit_response(alpha, n)
    assert abs(fit.slope - chi_true) < 1e-10, f"slope={fit.slope}, expected {chi_true}"
    assert abs(fit.intercept - intercept_true) < 1e-10, f"intercept={fit.intercept}"
    assert fit.r_squared > 0.9999999


def test_fit_response_known_chi0_chi_gives_correct_u():
    """Synthetic known chi0 and chi must give exactly correct U."""
    chi0_true = 0.60
    chi_true = 0.75
    U_true = 1.0 / chi0_true - 1.0 / chi_true

    alpha = [-0.02, -0.01, 0.00, 0.01, 0.02]
    n0 = [5.37 + chi0_true * a for a in alpha]
    ns = [5.37 + chi_true * a for a in alpha]

    fit0 = fit_response(alpha, n0)
    fit = fit_response(alpha, ns)

    U_computed = compute_scalar_u(fit0.slope, fit.slope)
    assert abs(U_computed - U_true) < 1e-10, f"U={U_computed}, expected {U_true}"


def test_fit_response_alpha_permutation_invariant():
    """Alpha input permutation must produce the same fitted response."""
    chi = 0.45
    alpha = [-0.02, -0.01, 0.00, 0.01, 0.02]
    n = [5.3 + chi * a for a in alpha]

    alpha_shuffled = [0.01, -0.02, 0.00, 0.02, -0.01]
    n_shuffled = [5.3 + chi * a for a in alpha_shuffled]

    fit1 = fit_response(alpha, n)
    fit2 = fit_response(alpha_shuffled, n_shuffled)

    assert abs(fit1.slope - fit2.slope) < 1e-12
    assert abs(fit1.intercept - fit2.intercept) < 1e-12


def test_fit_response_nonlinear_data_poor_r2():
    """Purely quadratic data must produce R² much less than 1."""
    alpha = [-0.02, -0.01, 0.00, 0.01, 0.02]
    # purely quadratic — no linear component
    n = [5.3 + 500.0 * a ** 2 for a in alpha]

    fit = fit_response(alpha, n)
    assert fit.r_squared < 0.5, f"Expected poor R2 for quadratic data, got {fit.r_squared}"


def test_fit_response_central_slopes_exact_linear():
    """For exact linear data, central-difference slopes must equal the OLS slope."""
    chi = 0.6
    alpha = [-0.02, -0.01, 0.00, 0.01, 0.02]
    n = [5.37 + chi * a for a in alpha]

    fit = fit_response(alpha, n)
    assert abs(fit.central_slope_001 - chi) < 1e-10
    assert abs(fit.central_slope_002 - chi) < 1e-10


def test_compute_scalar_u_zero_chi0_rejected():
    """Zero chi0 must raise ZeroDivisionError."""
    with pytest.raises(ZeroDivisionError):
        compute_scalar_u(0.0, 0.5)


def test_compute_scalar_u_zero_chi_rejected():
    """Zero chi must raise ZeroDivisionError."""
    with pytest.raises(ZeroDivisionError):
        compute_scalar_u(0.5, 0.0)


# ─────────────────────────────────────────────
# analyze_scalar_response_campaign tests
# ─────────────────────────────────────────────

def _make_synthetic_points(chi0: float, chi: float, n_ref0: float = 5.37):
    """Build a synthetic 5-point ResponsePoint list."""
    alpha_grid = [-0.02, -0.01, 0.00, 0.01, 0.02]
    return [
        ResponsePoint(alpha=a, n_ref=n_ref0, n0=n_ref0 + chi0 * a, n=n_ref0 + chi * a)
        for a in alpha_grid
    ]


def test_campaign_analysis_recovers_exact_u():
    """Complete campaign pipeline must recover exact U from synthetic data."""
    chi0_true = 0.60
    chi_true = 0.80
    U_true = 1.0 / chi0_true - 1.0 / chi_true

    pts = _make_synthetic_points(chi0_true, chi_true)
    result = analyze_scalar_response_campaign(pts)

    assert abs(result.chi0_full - chi0_true) < 1e-10
    assert abs(result.chi_full - chi_true) < 1e-10
    assert abs(result.U_full - U_true) < 1e-10


def test_campaign_no_policy_returns_diagnostics_only():
    """Without a policy, scientific_verdict must be DIAGNOSTICS_ONLY."""
    pts = _make_synthetic_points(0.6, 0.8)
    result = analyze_scalar_response_campaign(pts, policy=None)
    assert result.scientific_verdict == "DIAGNOSTICS_ONLY"


def test_campaign_policy_stable_on_linear_data():
    """Exact linear data with any reasonable policy must return STABLE."""
    pts = _make_synthetic_points(0.6, 0.8)
    policy = NumericalLinearityPolicy(min_r2_bare=0.999, min_r2_screened=0.999, max_u_rel_diff=0.10)
    result = analyze_scalar_response_campaign(pts, policy=policy)
    assert result.scientific_verdict == "STABLE"


def test_campaign_policy_invalid_on_nonlinear_data():
    """Nonlinear BARE data with strict R² policy must return INVALID."""
    alpha_grid = [-0.02, -0.01, 0.00, 0.01, 0.02]
    # Strong quadratic + tiny linear component so chi0_full is nonzero but R² is poor
    pts = [
        ResponsePoint(alpha=a, n_ref=5.37, n0=5.37 + 0.01 * a + 500.0 * a ** 2, n=5.37 + 0.5 * a)
        for a in alpha_grid
    ]
    policy = NumericalLinearityPolicy(min_r2_bare=0.999)
    result = analyze_scalar_response_campaign(pts, policy=policy)
    assert result.scientific_verdict == "INVALID"


def test_campaign_central_slopes_exact_linear():
    """For exact linear data, central-difference U must equal OLS U."""
    chi0 = 0.60
    chi = 0.80
    U_true = 1.0 / chi0 - 1.0 / chi

    pts = _make_synthetic_points(chi0, chi)
    result = analyze_scalar_response_campaign(pts)

    assert abs(result.chi0_central_001 - chi0) < 1e-10
    assert abs(result.chi0_central_002 - chi0) < 1e-10
    assert abs(result.chi_central_001 - chi) < 1e-10
    assert abs(result.chi_central_002 - chi) < 1e-10
    assert abs(result.U_central_001 - U_true) < 1e-10
    assert abs(result.U_central_002 - U_true) < 1e-10


# ─────────────────────────────────────────────
# Real MnO data tests (actual P4-C measurements)
# ─────────────────────────────────────────────

def test_campaign_mno_real_data_chi0_full():
    """Real MnO data must reproduce chi0_full = -7.0606 within 0.001."""
    result = analyze_scalar_response_campaign(_mno_points())
    assert abs(result.chi0_full - (-7.060600)) < 0.001, f"chi0_full={result.chi0_full}"


def test_campaign_mno_real_data_chi0_inner():
    """Real MnO data must reproduce chi0_inner = -7.0290 within 0.001."""
    result = analyze_scalar_response_campaign(_mno_points())
    assert abs(result.chi0_inner - (-7.029000)) < 0.001, f"chi0_inner={result.chi0_inner}"


def test_campaign_mno_real_data_chi_full():
    """Real MnO data must reproduce chi_full = -0.1029 within 0.001."""
    result = analyze_scalar_response_campaign(_mno_points())
    assert abs(result.chi_full - (-0.102900)) < 0.001, f"chi_full={result.chi_full}"


def test_campaign_mno_real_data_chi_inner():
    """Real MnO data must reproduce chi_inner = -0.1035 within 0.001."""
    result = analyze_scalar_response_campaign(_mno_points())
    assert abs(result.chi_inner - (-0.103500)) < 0.001, f"chi_inner={result.chi_inner}"


def test_campaign_mno_real_data_u_full():
    """Real MnO data must reproduce U_full = 9.5765 eV within 0.01 eV."""
    result = analyze_scalar_response_campaign(_mno_points())
    assert abs(result.U_full - 9.5765) < 0.01, f"U_full={result.U_full}"


def test_campaign_mno_real_data_u_inner():
    """Real MnO data must reproduce U_inner = 9.5196 eV within 0.01 eV."""
    result = analyze_scalar_response_campaign(_mno_points())
    assert abs(result.U_inner - 9.5196) < 0.01, f"U_inner={result.U_inner}"


def test_campaign_mno_real_data_central_diagnostics():
    """Real MnO data: central-difference diagnostics must be finite and physically reasonable."""
    result = analyze_scalar_response_campaign(_mno_points())
    assert math.isfinite(result.chi0_central_001)
    assert math.isfinite(result.chi0_central_002)
    assert math.isfinite(result.chi_central_001)
    assert math.isfinite(result.chi_central_002)
    assert math.isfinite(result.U_central_001)
    assert math.isfinite(result.U_central_002)
    # chi0 is large negative (bare response dominates)
    assert result.chi0_central_001 < -1.0
    # chi is small negative (screened response)
    assert result.chi_central_001 < 0.0
    # U is positive and in the range 5-15 eV
    assert 5.0 < result.U_central_001 < 15.0
