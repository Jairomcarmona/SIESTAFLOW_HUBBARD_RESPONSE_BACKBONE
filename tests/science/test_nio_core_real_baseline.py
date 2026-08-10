import json
from pathlib import Path

import numpy as np

from production_benchmarks.lr_arithmetic import build_chi_matrix_3point, compute_U_matrix


BASELINE = json.loads(
    (Path(__file__).parents[1] / "fixtures" / "nio_core_real_baseline_783533.json").read_text()
)


def _observations():
    result = {}
    for key, values in BASELINE["observations"].items():
        j, alpha, mode = key.strip("()").split(", ")
        result[(int(j), float(alpha), mode)] = values
    return result


def test_real_yoltla_783533_baseline_uses_direct_production_inversion(monkeypatch):
    def forbidden_pinv(*args, **kwargs):
        raise AssertionError("pseudoinverse is forbidden for the scientific baseline")

    monkeypatch.setattr(np.linalg, "pinv", forbidden_pinv)
    observations = _observations()
    chi0 = build_chi_matrix_3point(observations, 2, 0.01, "BARE")
    chi = build_chi_matrix_3point(observations, 2, 0.01, "SCREENED")
    result = compute_U_matrix(chi0, chi)

    np.testing.assert_allclose(chi0, BASELINE["chi0"], rtol=0, atol=1e-12)
    np.testing.assert_allclose(chi, BASELINE["chi"], rtol=0, atol=1e-12)
    assert result["chi0_rank"] == BASELINE["rank_chi0"]
    assert result["chi_rank"] == BASELINE["rank_chi"]
    np.testing.assert_allclose(result["U"], BASELINE["U"], rtol=0, atol=1e-9)
