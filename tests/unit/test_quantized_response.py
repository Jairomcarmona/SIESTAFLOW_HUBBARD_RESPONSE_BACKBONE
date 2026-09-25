import numpy as np
import pytest

from siestaflow_hubbard.domain.quantized_response import (
    fit_centered_linear_response,
    hubbard_u_interval,
    inverse_rounding_bound,
)


def test_linear_fit_propagates_each_print_interval_through_ols_weights():
    alpha = np.array([-1.0, 0.0, 1.0])
    y = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 8.0]])
    half_width = np.array([[0.1, 0.2], [0.2, 0.1], [0.3, 0.4]])
    fit = fit_centered_linear_response(alpha, y, half_width)
    assert fit.slope == pytest.approx([2.0, 3.0])
    assert fit.slope_half_width == pytest.approx([0.2, 0.3])
    assert fit.residuals.shape == y.shape


def test_inverse_rounding_bound_fails_closed_when_interval_can_cross_singularity():
    matrix = np.eye(2)
    too_wide = np.full((2, 2), 0.6)
    result = inverse_rounding_bound(matrix, too_wide)
    assert result["robustly_invertible"] is False
    assert result["inverse_error_bound"] is None


def test_u_interval_combines_direct_inverse_error_bounds():
    chi0 = np.diag([1.0, 2.0])
    chi = np.diag([0.5, 1.0])
    widths = np.full((2, 2), 1e-8)
    result = hubbard_u_interval(chi0, chi, widths, widths)
    assert result["robustly_invertible"] is True
    assert result["u_eV_point"] == pytest.approx(-0.75)
    low, high = result["u_eV_interval"]
    assert low < -0.75 < high
