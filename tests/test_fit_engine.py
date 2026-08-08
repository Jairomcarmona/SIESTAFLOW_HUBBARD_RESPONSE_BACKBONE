import pytest
import numpy as np

from siestaflow_hubbard.domain.cardinals import Cardinals
from siestaflow_hubbard.domain.alpha_grid import AlphaGrid
from siestaflow_hubbard.synthetic_backend.population_generator import (
    OccupationRecord,
    generate_populations,
)
from siestaflow_hubbard.synthetic_backend.fit_engine import (
    FitEngine,
    assemble_slope_matrix,
    RegressionRecord,
)
from siestaflow_hubbard.synthetic_backend.recovery import recover_U
from siestaflow_hubbard.domain.matrix_pipeline import invert_chi


def create_test_cardinals(A_2x4, alpha_values):
    grid = AlphaGrid(
        alpha_values_ev=alpha_values,
        K_p=len(alpha_values),
        symmetric_pairs=True,
        k_negative=2,
        k_zero=1,
        k_positive=2,
    )
    alpha_grids = {"P0": grid, "P1": grid}
    return Cardinals(P=2, O=4, N=2, alpha_grids=alpha_grids, A=A_2x4)


def test_fit_slopes_noiseless(A_2x4, R_BARE_C1, ALPHA_SYMMETRIC, INTERCEPTS):
    cardinals = create_test_cardinals(A_2x4, ALPHA_SYMMETRIC)
    bare_records, _ = generate_populations(
        R_bare_true=R_BARE_C1,
        R_screened_true=R_BARE_C1,
        cardinals=cardinals,
        intercepts=INTERCEPTS,
    )

    engine = FitEngine()
    regression_records = engine.fit_slopes(bare_records, cardinals, response_mode="BARE")
    assert len(regression_records) == 4 * 2

    for rec in regression_records:
        o = rec.observable_index
        p = rec.channel_index
        expected_slope = R_BARE_C1[o, p]
        assert np.isclose(rec.slope, expected_slope, atol=1e-10)
        assert np.isclose(rec.intercept, INTERCEPTS[o], atol=1e-10)
        assert rec.r_squared == pytest.approx(1.0, abs=1e-10)
        assert rec.n_points == 5


def test_assemble_slope_matrix(A_2x4, R_BARE_C1, ALPHA_SYMMETRIC, INTERCEPTS):
    cardinals = create_test_cardinals(A_2x4, ALPHA_SYMMETRIC)
    bare_records, _ = generate_populations(
        R_bare_true=R_BARE_C1,
        R_screened_true=R_BARE_C1,
        cardinals=cardinals,
        intercepts=INTERCEPTS,
    )

    engine = FitEngine()
    regression_records = engine.fit_slopes(bare_records, cardinals, response_mode="BARE")
    R_assembled = assemble_slope_matrix(regression_records, cardinals)

    assert R_assembled.shape == (4, 2)
    np.testing.assert_allclose(R_assembled, R_BARE_C1, atol=1e-10)


def test_fit_slopes_requires_minimum_points(A_2x4, ALPHA_SYMMETRIC):
    cardinals = create_test_cardinals(A_2x4, ALPHA_SYMMETRIC)
    insufficient_records = [
        OccupationRecord(
            response_mode="BARE",
            channel_index=0,
            alpha_ev=0.0,
            observable_index=0,
            occupation=2.5,
        )
    ]
    engine = FitEngine()
    with pytest.raises(ValueError):
        engine.fit_slopes(insufficient_records, cardinals, response_mode="BARE")


def test_roundtrip_noiseless_U_recovery(
    A_2x4, R_BARE_C1, R_SCR_C1, U_TRUE_C1, ALPHA_SYMMETRIC, INTERCEPTS
):
    cardinals = create_test_cardinals(A_2x4, ALPHA_SYMMETRIC)
    bare_records, screened_records = generate_populations(
        R_bare_true=R_BARE_C1,
        R_screened_true=R_SCR_C1,
        cardinals=cardinals,
        intercepts=INTERCEPTS,
    )

    engine = FitEngine()
    reg_bare = engine.fit_slopes(bare_records, cardinals, response_mode="BARE")
    reg_scr = engine.fit_slopes(screened_records, cardinals, response_mode="SCREENED")

    R_bare_fit = assemble_slope_matrix(reg_bare, cardinals)
    R_scr_fit = assemble_slope_matrix(reg_scr, cardinals)

    chi0 = A_2x4 @ R_bare_fit
    chi = A_2x4 @ R_scr_fit
    U_calc = invert_chi(chi0) - invert_chi(chi)

    np.testing.assert_allclose(U_calc, U_TRUE_C1, atol=1e-10)

    U_recovered = recover_U(R_bare_fit, R_scr_fit, cardinals)
    np.testing.assert_allclose(U_recovered, U_TRUE_C1, atol=1e-10)

def test_weighted_fit_strategy():
    from siestaflow_hubbard.synthetic_backend.fit_strategies import WeightedFitterStrategy
    
    # create some noisy data with alpha values
    alpha_vals = np.array([-0.2, -0.1, 0.0, 0.1, 0.2])
    true_m, true_c = 2.0, 5.0
    occupations = true_m * alpha_vals + true_c
    
    # add noise that is larger at larger alpha
    noise = np.array([0.05, 0.01, 0.0, -0.01, -0.05])
    occupations += noise
    
    fitter = WeightedFitterStrategy()
    m, c, diag = fitter.fit(alpha_vals, occupations)
    
    # Test that slope and intercept are close to truth (weights help reduce impact of noise at ends)
    assert np.isclose(c, 5.0, atol=1e-7)
    
    # Test diagnostics calculation
    assert "slope_std_err" in diag
    assert "design_condition_number" in diag
    assert "asymmetry" in diag
    assert "r_squared" in diag
    
    # Ensure standard error is computed
    assert not np.isnan(diag["slope_std_err"])
    assert diag["slope_std_err"] > 0
    assert diag["r_squared"] > 0.9
