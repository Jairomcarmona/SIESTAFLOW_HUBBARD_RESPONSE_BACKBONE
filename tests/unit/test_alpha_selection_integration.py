import numpy as np
import pytest

from siestaflow_hubbard.domain.alpha_selection import AlphaSelectionPolicy, select_common_alpha_window


def _linear_data(scale=1.0):
    alphas = np.array([-0.2, -0.1, -0.05, 0.0, 0.05, 0.1, 0.2])
    slopes = np.array([-0.25, -0.15]) * scale
    occupations = 4.0 + alphas[:, None] * slopes
    moments = np.zeros((7, 2, 3))
    moments[:, :, 2] = np.array([2.0, -2.0])
    return alphas, occupations, moments


def test_common_linear_window_is_accepted_and_order_independent():
    alphas, occupations, moments = _linear_data()
    policy = AlphaSelectionPolicy(occupation_noise=1e-7)
    forward = select_common_alpha_window(alphas, occupations, moments, 0.1, policy)
    reverse = select_common_alpha_window(alphas[::-1], occupations[::-1], moments[::-1], 0.1, policy)
    assert forward["status"] == reverse["status"] == "proposed"
    assert forward["recommended_alpha_ev"] == reverse["recommended_alpha_ev"] == 0.2


def test_curvature_or_magnetic_branch_change_is_not_accepted():
    alphas, occupations, moments = _linear_data()
    occupations = occupations + (alphas**2)[:, None] * np.array([4.0, 3.0])
    rejected = select_common_alpha_window(alphas, occupations, moments, 0.1, AlphaSelectionPolicy(1e-7))
    assert rejected["status"] == "rejected"
    moments[0, 0, 2] += 0.5
    rejected_magnetic = select_common_alpha_window(alphas, _linear_data()[1], moments, 0.1, AlphaSelectionPolicy(1e-7))
    assert rejected_magnetic["status"] == "rejected"


def test_override_is_recorded_but_cannot_bypass_rejection():
    alphas, occupations, moments = _linear_data()
    report = select_common_alpha_window(
        alphas,
        occupations,
        moments,
        0.1,
        AlphaSelectionPolicy(1e-7),
        override={"alpha_ev": 0.1, "actor": "reviewer", "reason": "narrower window"},
    )
    assert report["status"] == "proposed"
    assert report["override"]["applied"] is True
    with pytest.raises(ValueError, match="seven"):
        select_common_alpha_window(alphas[:-1], occupations[:-1], moments[:-1], 0.1, AlphaSelectionPolicy(1e-7))
