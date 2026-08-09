"""Tests for the scalar_lr production module."""

import pytest
import numpy as np

from siestaflow_hubbard.domain.scalar_lr import (
    ResponsePoint,
    LinearFit,
    fit_response,
    evaluate_linearity,
    compute_scalar_u,
    analyze_scalar_response_campaign,
)


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


def test_fit_response_nonlinear_identified_as_nonlinear():
    """Nonlinear response (quadratic) must produce poor R² and be classified nonlinear."""
    alpha = [-0.02, -0.01, 0.00, 0.01, 0.02]
    # Purely quadratic — zero linear component
    n = [5.3 + 50.0 * a ** 2 for a in alpha]

    fit = fit_response(alpha, n)
    linearity = evaluate_linearity(fit, r2_threshold=0.999)

    # R² should be low because data has no linear trend
    assert linearity in ("MARGINAL", "NONLINEAR"), f"Expected nonlinear, got {linearity}, R2={fit.r_squared}"


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
    points = []
    for a in alpha_grid:
        points.append(ResponsePoint(
            alpha=a,
            n_ref=n_ref0,      # flat reference
            n0=n_ref0 + chi0 * a,
            n=n_ref0 + chi * a,
        ))
    return points


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
    assert result.scientific_verdict == "STABLE"


def test_campaign_analysis_mno_real_data():
    """Real MnO P4-B data must pass through the production analysis pipeline."""
    # Known P4-B values for alpha=0 plus plausible surrounding points
    # (actual runs will differ slightly; this uses approximate stand-ins)
    pts = [
        ResponsePoint(alpha=-0.02, n_ref=5.37225, n0=5.35624, n=5.36004),
        ResponsePoint(alpha=-0.01, n_ref=5.37225, n0=5.36229, n=5.36609),
        ResponsePoint(alpha=0.00,  n_ref=5.37225, n0=5.36834, n=5.37214),
        ResponsePoint(alpha=0.01,  n_ref=5.37225, n0=5.37439, n=5.37819),
        ResponsePoint(alpha=0.02,  n_ref=5.37225, n0=5.38044, n=5.38424),
    ]
    # Should not raise; just verify the pipeline runs end-to-end
    result = analyze_scalar_response_campaign(pts)
    assert result.scientific_verdict in ("STABLE", "WINDOW_DEPENDENT", "INVALID")
    assert np.isfinite(result.U_full)
    assert np.isfinite(result.chi0_full)
    assert np.isfinite(result.chi_full)
