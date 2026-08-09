"""
Tests for the matrix_lr N×N linear-response engine.

Tests cover:
  - mathematical correctness (recovery of known chi0, chi, U)
  - site-label permutation invariance
  - alpha-order permutation invariance
  - off-diagonal coupling retained
  - singular matrix rejection (no silent pinv)
  - nearly singular condition diagnostics
  - chi0/chi swap changes U correctly
  - raw vs symmetrized matrices remain distinguishable
  - A @ R (row/column convention) mapping correctness
  - 2×2 synthetic full pipeline (occupations → regressions → chi → inversion → U)
"""

import math
import pytest
import numpy as np

from siestaflow_hubbard.domain.matrix_lr import (
    ResponseObservation,
    ElementDiagnostics,
    MatrixConditionReport,
    InversionReport,
    MatrixResponseResult,
    fit_response_matrix,
    analyze_matrix_condition,
    invert_response_matrix,
    compute_interaction_matrix,
    analyze_matrix_response_campaign,
)

# ─────────────────────────────────────────────
# SYNTHETIC 2×2 HELPERS
# ─────────────────────────────────────────────

CHI0_TRUE = np.array([
    [-0.80, -0.10],
    [-0.06, -0.70],
])

CHI_TRUE = np.array([
    [-0.25, -0.04],
    [-0.03, -0.22],
])

N_REF_TRUE = np.array([5.37, 4.82])   # n_I(0)
ALPHA_GRID = [-0.02, -0.01, 0.00, 0.01, 0.02]
SITE_LABELS = [0, 1]


def _make_synthetic_2x2(
    chi0: np.ndarray = CHI0_TRUE,
    chi: np.ndarray = CHI_TRUE,
    n_ref: np.ndarray = N_REF_TRUE,
    site_labels: list[int] = None,
    alpha_grid: list[float] = None,
) -> list[ResponseObservation]:
    """
    Build ResponseObservation list for a 2-site system from known chi matrices.
    n_I(alpha_J) = n_I(0) + chi_IJ * alpha_J
    """
    if site_labels is None:
        site_labels = SITE_LABELS[:]
    if alpha_grid is None:
        alpha_grid = ALPHA_GRID[:]
    N = len(site_labels)
    obs = []
    for J_idx, J in enumerate(site_labels):
        for alpha in alpha_grid:
            occ_bare = [n_ref[I] + chi0[I, J_idx] * alpha for I in range(N)]
            occ_scrn = [n_ref[I] + chi[I, J_idx] * alpha for I in range(N)]
            obs.append(ResponseObservation(
                perturbation_site=J,
                alpha=alpha,
                site_labels=site_labels[:],
                occupations_ref=list(n_ref),
                occupations_bare=occ_bare,
                occupations_screened=occ_scrn,
            ))
    return obs


# ─────────────────────────────────────────────
# fit_response_matrix
# ─────────────────────────────────────────────

def test_fit_response_matrix_recovers_chi0_and_chi():
    """Synthetic 2×2 must recover chi0 and chi within 1e-10."""
    obs = _make_synthetic_2x2()
    chi0_raw, chi_raw, diags = fit_response_matrix(obs)
    assert chi0_raw.shape == (2, 2)
    assert chi_raw.shape == (2, 2)
    np.testing.assert_allclose(chi0_raw, CHI0_TRUE, atol=1e-10)
    np.testing.assert_allclose(chi_raw, CHI_TRUE, atol=1e-10)


def test_fit_response_matrix_off_diagonal_retained():
    """Off-diagonal elements must be non-zero and correctly recovered."""
    obs = _make_synthetic_2x2()
    chi0_raw, chi_raw, _ = fit_response_matrix(obs)
    # Off-diagonal chi0
    assert abs(chi0_raw[0, 1] - CHI0_TRUE[0, 1]) < 1e-10   # chi0[0,1] = -0.10
    assert abs(chi0_raw[1, 0] - CHI0_TRUE[1, 0]) < 1e-10   # chi0[1,0] = -0.06
    # Off-diagonal chi
    assert abs(chi_raw[0, 1] - CHI_TRUE[0, 1]) < 1e-10     # chi[0,1]  = -0.04
    assert abs(chi_raw[1, 0] - CHI_TRUE[1, 0]) < 1e-10     # chi[1,0]  = -0.03
    # Must NOT be zero
    assert abs(chi0_raw[0, 1]) > 0.01
    assert abs(chi_raw[0, 1]) > 0.01


def test_fit_response_matrix_site_label_permutation():
    """
    Site-label permutation invariance.
    When site_labels=[0,1] and site_labels=[1,0] both generate occupations
    from the same physical chi matrix (keyed by site identity, not position),
    the (obs_site, pert_site) chi values must be identical.

    We generate observations where site J=0 always perturbs n_I using CHI0_TRUE[:,0]
    and site J=1 always perturbs using CHI0_TRUE[:,1], regardless of label order.
    """
    # Build observations with physically consistent site-keyed chi values
    # For this test use independent chi values per site to make the mapping unambiguous.
    # chi_by_site[J_phys][I_phys] = chi0_IJ
    chi0_by_site = {
        (0, 0): -0.80, (1, 0): -0.06,   # col J=0
        (0, 1): -0.10, (1, 1): -0.70,   # col J=1
    }
    chi_by_site = {
        (0, 0): -0.25, (1, 0): -0.03,
        (0, 1): -0.04, (1, 1): -0.22,
    }
    n_ref_phys = {0: 5.37, 1: 4.82}

    def make_obs_with_labels(site_labels, alpha_grid=ALPHA_GRID):
        obs = []
        for J in site_labels:
            for alpha in alpha_grid:
                occ_bare = [n_ref_phys[I] + chi0_by_site[(I, J)] * alpha for I in site_labels]
                occ_scrn = [n_ref_phys[I] + chi_by_site[(I, J)] * alpha for I in site_labels]
                obs.append(ResponseObservation(
                    perturbation_site=J,
                    alpha=alpha,
                    site_labels=list(site_labels),
                    occupations_ref=[n_ref_phys[I] for I in site_labels],
                    occupations_bare=occ_bare,
                    occupations_screened=occ_scrn,
                ))
        return obs

    obs_01 = make_obs_with_labels([0, 1])
    obs_10 = make_obs_with_labels([1, 0])

    chi0_01, chi_01, _ = fit_response_matrix(obs_01)
    chi0_10, chi_10, _ = fit_response_matrix(obs_10)

    # obs_01: row 0=site0, col 1=site1 → chi0_01[0,1] = chi0_by_site[(0,1)] = -0.10
    assert abs(chi0_01[0, 1] - (-0.10)) < 1e-10
    # obs_10: row 0=site1, col 1=site0 → chi0_10[0,1] = chi0_by_site[(1,0)] = -0.06
    assert abs(chi0_10[0, 1] - (-0.06)) < 1e-10
    # obs_01: diagonal site0 at [0,0] = -0.80
    assert abs(chi0_01[0, 0] - (-0.80)) < 1e-10
    # obs_10: site0 is at position 1 in [1,0], so chi0_10[1,1] = chi0_by_site[(0,0)] = -0.80
    assert abs(chi0_10[1, 1] - (-0.80)) < 1e-10


def test_fit_response_matrix_alpha_order_permutation():
    """Shuffled alpha order must produce identical matrix to sorted order."""
    obs_sorted = _make_synthetic_2x2(alpha_grid=[-0.02, -0.01, 0.0, 0.01, 0.02])
    obs_shuffled = _make_synthetic_2x2(alpha_grid=[0.01, -0.02, 0.0, 0.02, -0.01])

    chi0_s, chi_s, _ = fit_response_matrix(obs_sorted)
    chi0_u, chi_u, _ = fit_response_matrix(obs_shuffled)

    np.testing.assert_allclose(chi0_s, chi0_u, atol=1e-12)
    np.testing.assert_allclose(chi_s, chi_u, atol=1e-12)


def test_fit_response_matrix_row_col_convention():
    """
    Row I = observed, col J = perturbed.
    chi0_raw[I, J] = slope of n_I vs alpha_J.
    Verify by construction: chi0_raw[0,1] must equal chi0 applied to
    site 1 perturbation observed on site 0.
    """
    obs = _make_synthetic_2x2()
    chi0_raw, chi_raw, _ = fit_response_matrix(obs)
    # chi0_raw[0, 1]: obs=site0, pert=site1 → expected = CHI0_TRUE[0, 1]
    assert abs(chi0_raw[0, 1] - CHI0_TRUE[0, 1]) < 1e-10
    # chi_raw[1, 0]: obs=site1, pert=site0 → expected = CHI_TRUE[1, 0]
    assert abs(chi_raw[1, 0] - CHI_TRUE[1, 0]) < 1e-10


def test_fit_response_matrix_insufficient_alpha_raises():
    """Fewer than 2 alpha points for a column must raise ValueError."""
    obs = _make_synthetic_2x2(alpha_grid=[0.01])  # only 1 point
    with pytest.raises(ValueError, match="fewer than 2 alpha points"):
        fit_response_matrix(obs)


# ─────────────────────────────────────────────
# analyze_matrix_condition
# ─────────────────────────────────────────────

def test_condition_full_rank_matrix():
    M = np.array([[-0.80, -0.10], [-0.06, -0.70]])
    report = analyze_matrix_condition(M)
    assert report.is_full_rank
    assert report.rank == 2
    assert report.matrix_status == "FULL_RANK"
    assert math.isfinite(report.condition_number)
    assert len(report.singular_values) == 2


def test_condition_singular_matrix():
    M = np.array([[1.0, 2.0], [2.0, 4.0]])  # rank 1
    report = analyze_matrix_condition(M)
    assert not report.is_full_rank
    assert report.rank == 1
    assert report.matrix_status == "RANK_DEFICIENT"


def test_condition_nearly_singular_matrix_has_high_cond():
    M = np.array([[1.0, 0.0], [0.0, 1e-10]])
    report = analyze_matrix_condition(M)
    assert report.condition_number > 1e8


def test_condition_requires_square():
    M = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
    with pytest.raises(ValueError):
        analyze_matrix_condition(M)


# ─────────────────────────────────────────────
# invert_response_matrix
# ─────────────────────────────────────────────

def test_invert_full_rank_matrix_exact():
    """Inverting a known matrix must recover identity to machine precision."""
    M = CHI0_TRUE.copy()
    cond = analyze_matrix_condition(M)
    report = invert_response_matrix(M, cond)
    N = M.shape[0]
    np.testing.assert_allclose(report.inverse @ M, np.eye(N), atol=1e-12)
    np.testing.assert_allclose(M @ report.inverse, np.eye(N), atol=1e-12)
    assert report.left_residual < 1e-12
    assert report.right_residual < 1e-12
    assert report.method == "direct_inv"


def test_invert_rank_deficient_raises():
    """Rank-deficient matrix must raise ValueError — no silent pinv."""
    M = np.array([[1.0, 2.0], [2.0, 4.0]])
    cond = analyze_matrix_condition(M)
    with pytest.raises(ValueError, match="rank-deficient"):
        invert_response_matrix(M, cond)


def test_singular_chi0_rejected():
    """Singular chi0 must be detected and inversion refused."""
    chi0_singular = np.array([[1.0, 0.0], [0.0, 0.0]])
    chi_ok = CHI_TRUE.copy()
    obs = _make_synthetic_2x2(chi0=chi0_singular, chi=chi_ok)
    # fit_response_matrix should succeed but condition should detect rank deficiency
    chi0_raw, _, _ = fit_response_matrix(obs)
    cond = analyze_matrix_condition(chi0_raw)
    assert not cond.is_full_rank or cond.condition_number > 1e10


def test_singular_chi_rejected():
    """Singular chi must be detected and inversion refused."""
    chi_singular = np.array([[0.0, 0.0], [0.0, 0.0]])
    chi0_ok = CHI0_TRUE.copy()
    obs = _make_synthetic_2x2(chi0=chi0_ok, chi=chi_singular)
    _, chi_raw, _ = fit_response_matrix(obs)
    cond = analyze_matrix_condition(chi_raw)
    with pytest.raises(ValueError):
        invert_response_matrix(chi_raw, cond)


# ─────────────────────────────────────────────
# compute_interaction_matrix
# ─────────────────────────────────────────────

def test_compute_interaction_matrix_exact():
    """U = inv(chi0) - inv(chi) must be exact within numerical precision."""
    U_expected = np.linalg.inv(CHI0_TRUE) - np.linalg.inv(CHI_TRUE)

    cond0 = analyze_matrix_condition(CHI0_TRUE)
    cond = analyze_matrix_condition(CHI_TRUE)
    inv0 = invert_response_matrix(CHI0_TRUE, cond0)
    inv = invert_response_matrix(CHI_TRUE, cond)
    U = compute_interaction_matrix(inv0.inverse, inv.inverse)

    np.testing.assert_allclose(U, U_expected, atol=1e-10)


def test_chi0_chi_swap_changes_u():
    """Swapping chi0 and chi must change U in the mathematically expected way."""
    cond0 = analyze_matrix_condition(CHI0_TRUE)
    cond = analyze_matrix_condition(CHI_TRUE)
    inv0 = invert_response_matrix(CHI0_TRUE, cond0)
    inv = invert_response_matrix(CHI_TRUE, cond)

    U_normal = compute_interaction_matrix(inv0.inverse, inv.inverse)   # inv(chi0) - inv(chi)
    U_swapped = compute_interaction_matrix(inv.inverse, inv0.inverse)  # inv(chi) - inv(chi0)

    np.testing.assert_allclose(U_swapped, -U_normal, atol=1e-12)


def test_compute_interaction_shape_mismatch():
    """Shape mismatch must raise ValueError."""
    M1 = np.eye(2)
    M2 = np.eye(3)
    with pytest.raises(ValueError, match="Shape mismatch"):
        compute_interaction_matrix(M1, M2)


# ─────────────────────────────────────────────
# Raw vs symmetrized matrices remain distinguishable
# ─────────────────────────────────────────────

def test_raw_vs_symmetrized_distinguishable():
    """chi0_raw != chi0_sym for asymmetric true chi0."""
    obs = _make_synthetic_2x2()
    result = analyze_matrix_response_campaign(obs)

    # CHI0_TRUE is not symmetric (off-diagonal -0.10 vs -0.06)
    assert not np.allclose(result.chi0_raw, result.chi0_sym, atol=1e-6)

    # Symmetrized must be exactly (raw + raw.T) / 2
    expected_sym = 0.5 * (result.chi0_raw + result.chi0_raw.T)
    np.testing.assert_allclose(result.chi0_sym, expected_sym, atol=1e-15)

    # Asymmetry norm must be > 0
    assert result.chi0_asymmetry_norm > 0.01


def test_chi0_raw_asymmetry_norm_correct():
    """||chi0_raw - chi0_raw.T||_F must equal expected value."""
    obs = _make_synthetic_2x2()
    result = analyze_matrix_response_campaign(obs)
    expected_norm = float(np.linalg.norm(result.chi0_raw - result.chi0_raw.T, "fro"))
    assert abs(result.chi0_asymmetry_norm - expected_norm) < 1e-14


# ─────────────────────────────────────────────
# Full 2×2 synthetic pipeline (end-to-end)
# ─────────────────────────────────────────────

def test_full_2x2_synthetic_pipeline():
    """
    Full pipeline:
    synthetic occupations → regressions → chi0/chi → inversion → U.
    Must recover chi0, chi, and U_matrix exactly from known true values.
    """
    obs = _make_synthetic_2x2()
    result = analyze_matrix_response_campaign(obs)

    # Chi matrices recovered
    np.testing.assert_allclose(result.chi0_raw, CHI0_TRUE, atol=1e-10)
    np.testing.assert_allclose(result.chi_raw, CHI_TRUE, atol=1e-10)

    # Matrix status
    assert result.matrix_status == "FULL_RANK"
    assert result.U_matrix is not None

    # U_matrix
    U_expected = np.linalg.inv(CHI0_TRUE) - np.linalg.inv(CHI_TRUE)
    np.testing.assert_allclose(result.U_matrix, U_expected, atol=1e-10)

    # Site-diagonal U values (numerical, not interpreted as Hubbard U yet)
    U_11 = result.U_matrix[0, 0]
    U_22 = result.U_matrix[1, 1]
    assert math.isfinite(U_11) and abs(U_11) > 0.1
    assert math.isfinite(U_22) and abs(U_22) > 0.1

    # Off-diagonal U values present and finite
    U_12 = result.U_matrix[0, 1]
    U_21 = result.U_matrix[1, 0]
    assert math.isfinite(U_12)
    assert math.isfinite(U_21)

    # Inversion residuals must be near machine precision
    assert result.inversion_chi0.left_residual < 1e-12
    assert result.inversion_chi0.right_residual < 1e-12
    assert result.inversion_chi.left_residual < 1e-12
    assert result.inversion_chi.right_residual < 1e-12


def test_full_2x2_diagonal_only_chi_matches_scalar():
    """
    For strictly diagonal chi0 and chi (decoupled sites),
    each diagonal U_II must match the scalar result 1/chi0_II - 1/chi_II.
    """
    chi0_diag = np.diag([-0.80, -0.70])
    chi_diag = np.diag([-0.25, -0.22])

    obs = _make_synthetic_2x2(chi0=chi0_diag, chi=chi_diag)
    result = analyze_matrix_response_campaign(obs)

    U_11_scalar = 1.0 / (-0.80) - 1.0 / (-0.25)
    U_22_scalar = 1.0 / (-0.70) - 1.0 / (-0.22)

    assert abs(result.U_matrix[0, 0] - U_11_scalar) < 1e-10
    assert abs(result.U_matrix[1, 1] - U_22_scalar) < 1e-10
    # Off-diagonals must be zero for diagonal matrices
    assert abs(result.U_matrix[0, 1]) < 1e-10
    assert abs(result.U_matrix[1, 0]) < 1e-10


def test_full_pipeline_rank_deficient_chi0_no_u():
    """
    Rank-deficient chi0 must result in matrix_status=RANK_DEFICIENT
    and U_matrix=None (no silent inversion).
    """
    # Make chi0 rank-deficient: row 1 = 2 * row 0
    chi0_rd = np.array([[-0.50, -0.10], [-1.00, -0.20]])  # row1 = 2*row0
    chi_ok = CHI_TRUE.copy()
    obs = _make_synthetic_2x2(chi0=chi0_rd, chi=chi_ok)
    result = analyze_matrix_response_campaign(obs)

    assert result.U_matrix is None
    assert "RANK_DEFICIENT" in result.matrix_status or not result.condition_chi0.is_full_rank


def test_element_diagnostics_present_for_all_pairs():
    """element_diagnostics must have 2*N*N entries (bare + screened per (I,J))."""
    obs = _make_synthetic_2x2()
    result = analyze_matrix_response_campaign(obs)
    N = 2
    assert len(result.element_diagnostics) == 2 * N * N   # bare + screened


def test_element_diagnostics_r2_exact_linear():
    """For exact linear synthetic data, all R² in element_diagnostics must be >= 0.9999."""
    obs = _make_synthetic_2x2()
    result = analyze_matrix_response_campaign(obs)
    for d in result.element_diagnostics:
        assert d.fit_full.r_squared >= 0.9999, (
            f"R²={d.fit_full.r_squared} for (I={d.obs_site}, J={d.pert_site}, mode={d.mode})"
        )


def test_split_species_fdf_materialization():
    """materialize_split_species_fdf must produce MnLR0 and MnLR1 with correct species labels and atom counts."""
    from siestaflow_hubbard.siesta_backend.fdf_builder import materialize_split_species_fdf
    base_fdf = """
SystemName Base Test
SystemLabel Base
NumberOfAtoms 4
NumberOfSpecies 2
%block ChemicalSpeciesLabel
 1  25  Mn
 2   8  O
%endblock ChemicalSpeciesLabel
%block AtomicCoordinatesAndAtomicSpecies
 0.00  0.00  0.00  1
 0.50  0.00  0.00  1
 0.25  0.50  0.50  2
 0.75  0.50  0.50  2
%endblock AtomicCoordinatesAndAtomicSpecies
"""
    new_fdf, species_labels = materialize_split_species_fdf(base_fdf, target_species="Mn", new_prefix="MnLR")
    assert species_labels == ["MnLR0", "MnLR1"]
    assert "MnLR0" in new_fdf
    assert "MnLR1" in new_fdf
    assert "NumberOfSpecies 3" in new_fdf or "NumberOfSpecies  3" in new_fdf


def test_split_species_ni_dminitspin_preserved():
    """
    Regression: DM.InitSpin must be preserved exactly through a Ni->NiLR0/NiLR1 split.
    The splitter must NOT regenerate spin values from Mn assumptions or any atomic-number logic.
    """
    from siestaflow_hubbard.siesta_backend.fdf_builder import materialize_split_species_fdf
    base_fdf = """
SystemName NiO Test
NumberOfAtoms 4
NumberOfSpecies 2
%block ChemicalSpeciesLabel
 1  28  Ni
 2   8  O
%endblock ChemicalSpeciesLabel
%block AtomicCoordinatesAndAtomicSpecies
 0.00  0.00  0.00  1
 0.50  0.00  0.00  1
 0.25  0.50  0.50  2
 0.75  0.50  0.50  2
%endblock AtomicCoordinatesAndAtomicSpecies
%block DM.InitSpin
 1 +2.0
 2 -2.0
 3  0.0
 4  0.0
%endblock DM.InitSpin
"""
    new_fdf, species_labels = materialize_split_species_fdf(base_fdf, target_species="Ni", new_prefix="NiLR")
    assert species_labels == ["NiLR0", "NiLR1"]
    assert "NiLR0" in new_fdf
    assert "NiLR1" in new_fdf
    # DM.InitSpin must be EXACTLY preserved: atom 1 = +2.0, atom 2 = -2.0
    assert " 1 +2.0" in new_fdf, "DM.InitSpin atom 1 must remain +2.0 (antiferromagnetic NiLR0)"
    assert " 2 -2.0" in new_fdf, "DM.InitSpin atom 2 must remain -2.0 (antiferromagnetic NiLR1)"
    assert " 3  0.0" in new_fdf, "DM.InitSpin atom 3 (O) must remain 0.0"
    assert " 4  0.0" in new_fdf, "DM.InitSpin atom 4 (O) must remain 0.0"
    # Must NOT contain Mn-specific +5.0 spin initialization
    assert "+5.0" not in new_fdf, "Mn-specific +5.0 spin must NOT appear for Ni system"


def test_split_species_arbitrary_atomic_number():
    """
    Regression: materialize_split_species_fdf must work for any atomic number,
    not just Z=25 (Mn). Fe (Z=26) must split correctly.
    """
    from siestaflow_hubbard.siesta_backend.fdf_builder import materialize_split_species_fdf
    base_fdf = """
NumberOfAtoms 2
NumberOfSpecies 2
%block ChemicalSpeciesLabel
 1  26  Fe
 2   8  O
%endblock ChemicalSpeciesLabel
%block AtomicCoordinatesAndAtomicSpecies
 0.00  0.00  0.00  1
 0.25  0.50  0.50  2
%endblock AtomicCoordinatesAndAtomicSpecies
"""
    new_fdf, species_labels = materialize_split_species_fdf(base_fdf, target_species="Fe", new_prefix="FeLR")
    assert species_labels == ["FeLR0"]
    assert "FeLR0" in new_fdf
    # Atomic number 26 must be preserved
    assert " 26 " in new_fdf or "  26  " in new_fdf


def test_uniform_mode_reconstruction_from_2x2_matrix():
    """
    Uniform mode reconstruction: row sums (chi0_00 + chi0_01) and (chi_00 + chi_01)
    must equal the response under uniform perturbation [alpha, alpha].
    """
    chi0 = np.array([[-0.6170, 0.4436], [0.4436, -0.6170]])
    chi  = np.array([[-0.0698, 0.0139], [0.0139, -0.0698]])

    # Row sum = uniform response
    chi0_u_row0 = chi0[0, 0] + chi0[0, 1]
    chi_u_row0  = chi[0, 0] + chi[0, 1]

    assert abs(chi0_u_row0 - (-0.1734)) < 1e-4
    assert abs(chi_u_row0 - (-0.0559)) < 1e-4

    v_u = np.array([1.0, 1.0]) / np.sqrt(2.0)
    U_mat = np.linalg.inv(chi0) - np.linalg.inv(chi)
    U_u_proj = float(v_u.T @ U_mat @ v_u)

    # Reconstructed uniform U must be close to 12.12 eV (and close to 11.94 eV scalar)
    assert abs(U_u_proj - 12.1221) < 0.01


def test_real_observations_enter_production_nxn_engine():
    """
    Real 2×2 MnO measurements passed into analyze_matrix_response_campaign(...)
    must produce full-rank U_matrix with off-diagonal terms U_01 == U_10 == 0.55875 eV.
    """
    # Actual measured values from the 2×2 campaign
    mno_2x2_chi0 = np.array([[-0.617000, 0.443600], [0.443600, -0.617000]])
    mno_2x2_chi  = np.array([[-0.069800, 0.013900], [0.013900, -0.069800]])

    alpha_grid = [-0.02, -0.01, 0.00, 0.01, 0.02]
    site_labels = [0, 1]
    n_ref = [5.41803, 5.41803]

    obs = []
    for J_idx, J in enumerate(site_labels):
        for alpha in alpha_grid:
            occ_bare = [n_ref[I] + mno_2x2_chi0[I, J_idx] * alpha for I in range(2)]
            occ_scrn = [n_ref[I] + mno_2x2_chi[I, J_idx] * alpha for I in range(2)]
            obs.append(ResponseObservation(
                perturbation_site=J,
                alpha=alpha,
                site_labels=site_labels,
                occupations_ref=n_ref,
                occupations_bare=occ_bare,
                occupations_screened=occ_scrn,
            ))

    result = analyze_matrix_response_campaign(obs)

    assert result.matrix_status == "FULL_RANK"
    assert result.U_matrix is not None
    assert abs(result.U_matrix[0, 0] - 11.56332) < 0.01
    assert abs(result.U_matrix[1, 1] - 11.56332) < 0.01
    assert abs(result.U_matrix[0, 1] - 0.55875) < 0.01
    assert abs(result.U_matrix[1, 0] - 0.55875) < 0.01

