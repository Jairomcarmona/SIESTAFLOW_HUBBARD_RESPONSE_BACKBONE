import pytest
import numpy as np

from siestaflow_hubbard.domain.cardinals import Cardinals
from siestaflow_hubbard.domain.alpha_grid import AlphaGrid
from siestaflow_hubbard.synthetic_backend.population_generator import generate_populations, OccupationRecord
from siestaflow_hubbard.synthetic_backend.noise_injection import NoiseParams


@pytest.fixture
def dummy_cardinals(ALPHA_SYMMETRIC, A_2x4):
    grid = AlphaGrid(
        alpha_values_ev=ALPHA_SYMMETRIC,
        K_p=5,
        symmetric_pairs=True,
        k_negative=2,
        k_zero=1,
        k_positive=2,
    )
    alpha_grids = {"P0": grid, "P1": grid}
    return Cardinals(P=2, O=4, N=2, alpha_grids=alpha_grids, A=A_2x4)


def test_generate_noiseless_count(R_BARE_C1, R_SCR_C1, dummy_cardinals, INTERCEPTS):
    bare_records, screened_records = generate_populations(
        R_bare_true=R_BARE_C1,
        R_screened_true=R_SCR_C1,
        cardinals=dummy_cardinals,
        intercepts=INTERCEPTS,
        noise_params=None,
    )
    # Verify count: P=2, O=4, K_p=5 each -> O*sum(K_p) = 4*10 = 40
    assert len(bare_records) == 40
    assert len(screened_records) == 40
    assert dummy_cardinals.total_records_per_mode == 40


def test_generate_noiseless_values(R_BARE_C1, R_SCR_C1, dummy_cardinals, INTERCEPTS):
    bare_records, screened_records = generate_populations(
        R_bare_true=R_BARE_C1,
        R_screened_true=R_SCR_C1,
        cardinals=dummy_cardinals,
        intercepts=INTERCEPTS,
        noise_params=None,
    )

    # For alpha=0.0, all occupations should equal intercepts[o]
    for rec in bare_records + screened_records:
        if rec.alpha_ev == 0.0:
            assert rec.occupation == INTERCEPTS[rec.observable_index]

    # For alpha=0.10, channel 0, observable 0: occupation = 2.5 + (-0.50)*0.10 = 2.45
    ch0_obs0_alpha010 = [
        rec for rec in bare_records
        if rec.channel_index == 0 and rec.observable_index == 0 and rec.alpha_ev == 0.10
    ]
    assert len(ch0_obs0_alpha010) == 1
    assert pytest.approx(ch0_obs0_alpha010[0].occupation) == 2.45


def test_generate_with_noise_reproducible(R_BARE_C1, R_SCR_C1, dummy_cardinals, INTERCEPTS):
    noise_params = NoiseParams(sigma=0.001, seed=42)

    bare1, screened1 = generate_populations(
        R_bare_true=R_BARE_C1,
        R_screened_true=R_SCR_C1,
        cardinals=dummy_cardinals,
        intercepts=INTERCEPTS,
        noise_params=noise_params,
    )

    bare2, screened2 = generate_populations(
        R_bare_true=R_BARE_C1,
        R_screened_true=R_SCR_C1,
        cardinals=dummy_cardinals,
        intercepts=INTERCEPTS,
        noise_params=noise_params,
    )

    assert len(bare1) == len(bare2)
    assert len(screened1) == len(screened2)

    for r1, r2 in zip(bare1, bare2):
        assert r1.occupation == r2.occupation
        assert r1.alpha_ev == r2.alpha_ev
        assert r1.channel_index == r2.channel_index
        assert r1.observable_index == r2.observable_index

    for r1, r2 in zip(screened1, screened2):
        assert r1.occupation == r2.occupation
        assert r1.alpha_ev == r2.alpha_ev
        assert r1.channel_index == r2.channel_index
        assert r1.observable_index == r2.observable_index


def test_generate_no_noise_exact_intercept(R_BARE_C1, R_SCR_C1, dummy_cardinals, INTERCEPTS):
    bare_records, screened_records = generate_populations(
        R_bare_true=R_BARE_C1,
        R_screened_true=R_SCR_C1,
        cardinals=dummy_cardinals,
        intercepts=INTERCEPTS,
        noise_params=NoiseParams(sigma=0.0, seed=None),
    )

    for rec in bare_records + screened_records:
        if rec.alpha_ev == 0:
            assert rec.occupation == INTERCEPTS[rec.observable_index]
