import numpy as np
import pytest

from siestaflow_hubbard.domain.adaptive_alpha import (
    AdaptiveAlphaPolicy,
    AlphaPlanError,
    authorize_alpha_window,
)
from siestaflow_hubbard.domain.alpha_selection import AlphaSelectionPolicy


def _linear_observations():
    alpha = np.array([-0.2, -0.1, -0.05, 0.0, 0.05, 0.1, 0.2])
    occupations = 5.0 - 0.3 * alpha[:, None]
    moments = np.zeros((7, 1, 3))
    moments[:, 0, 2] = 3.0
    return alpha, occupations, moments


def test_adaptive_alpha_authorizes_only_a_common_stable_window():
    alpha, occupations, moments = _linear_observations()
    policy = AdaptiveAlphaPolicy(0.1, AlphaSelectionPolicy(occupation_noise=1e-8))
    report = authorize_alpha_window(policy, alpha, occupations, moments)
    assert report["decision"]["status"] == "proposed"
    assert report["levels_ev"] == [-0.2, -0.1, -0.05, 0.0, 0.05, 0.1, 0.2]


def test_adaptive_alpha_blocks_a_magnetic_branch_change():
    alpha, occupations, moments = _linear_observations()
    moments[0, 0, 2] = 4.0
    policy = AdaptiveAlphaPolicy(0.1, AlphaSelectionPolicy(occupation_noise=1e-8))
    with pytest.raises(AlphaPlanError, match="no common"):
        authorize_alpha_window(policy, alpha, occupations, moments)
