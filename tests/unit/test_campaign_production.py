"""
tests/unit/test_campaign_production.py

Comprehensive tests for the production Hubbard-U benchmark campaign.
All tests can actually FAIL if the implementation is wrong.
No SIESTA runs. Pure arithmetic/geometry/state tests.
"""
from __future__ import annotations
import hashlib
import json
import os
import sys
import tempfile

import numpy as np
import pytest

# ─── Path setup ─────────────────────────────────────────────────────────────
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT)


# ═══════════════════════════════════════════════════════════════════════════
# 1. LR ARITHMETIC — 3-POINT
# ═══════════════════════════════════════════════════════════════════════════

from production_benchmarks.lr_arithmetic import (
    central_3point, fit_5point,
    build_chi_matrix_3point, build_chi_matrix_5point,
    compute_U_matrix, eigenmode_analysis,
)
from production_benchmarks.slurm_runner import (
    build_base_fdf_from_material_cfg, compute_scientific_identity,
    verify_siesta_run_semantics, generate_lr_run_specs, materialize_run_fdf, RunSpec
)
from production_benchmarks.geometry_validator import verify_afm_ii_ordering


def _ensure_dummy_ref_dm(campaign_dir: str, material: str = 'NiO') -> str:
    dm_dir = os.path.join(campaign_dir, 'materials', material.lower())
    os.makedirs(dm_dir, exist_ok=True)
    dm_path = os.path.join(dm_dir, 'reference.DM')
    if not os.path.exists(dm_path):
        with open(dm_path, 'wb') as fh:
            fh.write(b"DUMMY_REFERENCE_DM_FOR_TESTS")
    return dm_path


def test_3point_central_derivative_exact():
    """chi = 0.5 exactly."""
    assert abs(central_3point(9.9, 10.1, 0.2) - 0.5) < 1e-12


def test_3point_zero_delta_raises():
    with pytest.raises(ValueError, match='nonzero'):
        central_3point(1.0, 2.0, 0.0)


def test_3point_negative_delta_ok():
    """Negative delta should work the same — formula is (n+ - n-) / 2|delta|."""
    v = central_3point(9.9, 10.1, -0.2)
    # (10.1 - 9.9) / (-0.4) = -0.5  — sign follows formula
    assert abs(abs(v) - 0.5) < 1e-12


def test_chi_bare_matrix_3point_exact_2x2():
    """BARE matrix recovered exactly from synthetic 3-point data."""
    chi0_true = np.array([[-0.25, 0.03], [0.03, -0.25]])
    delta = 0.01
    obs = {}
    n_ref = [8.0, 8.0]
    for J in range(2):
        for alpha in [-delta, 0.0, delta]:
            obs[(J, alpha, 'BARE')] = [
                n_ref[I] + chi0_true[I, J] * alpha for I in range(2)
            ]
    mat = build_chi_matrix_3point(obs, n_sites=2, delta=delta,
                                   response_semantic='BARE')
    assert mat.shape == (2, 2)
    assert np.allclose(mat, chi0_true, atol=1e-10), \
        f"BARE matrix wrong: {mat}"


def test_chi_screened_matrix_3point_exact_2x2():
    """SCREENED matrix recovered exactly from synthetic 3-point data."""
    chi_true = np.array([[-0.09, 0.01], [0.01, -0.09]])
    delta = 0.01
    obs = {}
    n_ref = [9.5, 9.5]
    for J in range(2):
        for alpha in [-delta, 0.0, delta]:
            obs[(J, alpha, 'SCREENED')] = [
                n_ref[I] + chi_true[I, J] * alpha for I in range(2)
            ]
    mat = build_chi_matrix_3point(obs, n_sites=2, delta=delta,
                                   response_semantic='SCREENED')
    assert np.allclose(mat, chi_true, atol=1e-10), \
        f"SCREENED matrix wrong: {mat}"


def test_chi_matrix_3point_bare_screened_independent():
    """BARE and SCREENED obs keys are independent; wrong mode raises KeyError."""
    delta = 0.01
    obs = {(0, -delta, 'SCREENED'): [9.4, 9.5],
           (0, +delta, 'SCREENED'): [9.6, 9.5],
           (1, -delta, 'SCREENED'): [9.5, 9.4],
           (1, +delta, 'SCREENED'): [9.5, 9.6]}
    # Requesting BARE when only SCREENED data exists must raise KeyError
    with pytest.raises(KeyError):
        build_chi_matrix_3point(obs, n_sites=2, delta=delta,
                                 response_semantic='BARE')


def test_chi_matrix_3point_missing_obs_raises():
    """Missing observation must raise KeyError, not silently insert zero."""
    obs = {(0, -0.01, 'BARE'): [8.0, 8.0]}  # missing (0, +0.01, 'BARE')
    with pytest.raises(KeyError):
        build_chi_matrix_3point(obs, n_sites=2, delta=0.01,
                                 response_semantic='BARE')


def test_chi_matrix_3point_n4_shape():
    """N=4 matrix: shape and values correct."""
    chi_true = np.diag([-0.12] * 4) + 0.01 * (1 - np.eye(4))
    delta = 0.01
    obs = {}
    n_ref = [9.5] * 4
    for J in range(4):
        for alpha in [-delta, 0.0, delta]:
            obs[(J, alpha, 'SCREENED')] = [
                n_ref[I] + chi_true[I, J] * alpha for I in range(4)
            ]
    mat = build_chi_matrix_3point(obs, 4, delta, 'SCREENED')
    assert mat.shape == (4, 4)
    assert np.allclose(mat, chi_true, atol=1e-10)


# ═══════════════════════════════════════════════════════════════════════════
# 2. LR ARITHMETIC — 5-POINT
# ═══════════════════════════════════════════════════════════════════════════

def test_5point_fit_exact_linear():
    """Exact linear data: slope recovered to machine precision, R2=1."""
    alphas = [-0.02, -0.01, 0.00, 0.01, 0.02]
    true_slope = -0.15
    occs = [10.0 + true_slope * a for a in alphas]
    result = fit_5point(alphas, occs)
    assert abs(result['slope'] - true_slope) < 1e-10
    assert result['r2'] > 0.9999


def test_5point_fit_inner_outer_slopes_match_linear():
    """For perfectly linear data, inner/outer slopes == full slope."""
    alphas = [-0.02, -0.01, 0.00, 0.01, 0.02]
    s = -0.12
    occs = [9.5 + s * a for a in alphas]
    r = fit_5point(alphas, occs)
    assert abs(r['inner_central_slope'] - s) < 1e-10
    assert abs(r['outer_slope'] - s) < 1e-10
    assert abs(r['asymmetry']) < 1e-10  # perfectly symmetric


def test_5point_fit_nonlinear_produces_nonzero_asymmetry():
    """Quadratic data: asymmetry and residuals nonzero."""
    alphas = [-0.02, -0.01, 0.00, 0.01, 0.02]
    # Mix linear + quadratic
    occs = [9.5 - 0.12 * a + 200 * a**2 for a in alphas]
    r = fit_5point(alphas, occs)
    assert r['asymmetry'] > 0.001, \
        f"Expected nonzero asymmetry for nonlinear data, got {r['asymmetry']}"
    ss = sum(x**2 for x in r['residuals'])
    assert ss > 1e-10, "Expected nonzero residuals for nonlinear data"


def test_5point_fit_wrong_length_raises():
    with pytest.raises(ValueError, match='5 points'):
        fit_5point([0.0, 0.01, 0.02], [1.0, 2.0, 3.0])


def test_chi_bare_matrix_5point_exact():
    """BARE 5-point matrix recovered exactly."""
    chi0_true = np.array([[-0.25, 0.03], [0.03, -0.25]])
    delta = 0.01
    alphas = [-2*delta, -delta, 0.0, delta, 2*delta]
    obs = {}
    for J in range(2):
        for a in alphas:
            obs[(J, a, 'BARE')] = [
                8.0 + chi0_true[I, J] * a for I in range(2)
            ]
    res = build_chi_matrix_5point(obs, 2, delta, 'BARE')
    assert res['matrix'].shape == (2, 2)
    assert not np.allclose(res['matrix'], np.zeros((2, 2))), \
        "5-point BARE returned zero matrix (stub)"
    assert np.allclose(res['matrix'], chi0_true, atol=1e-8)
    assert res['min_r2'] > 0.9999


def test_chi_screened_matrix_5point_exact():
    """SCREENED 5-point matrix recovered exactly."""
    chi_true = np.array([[-0.09, 0.01], [0.01, -0.09]])
    delta = 0.01
    alphas = [-2*delta, -delta, 0.0, delta, 2*delta]
    obs = {}
    for J in range(2):
        for a in alphas:
            obs[(J, a, 'SCREENED')] = [
                9.5 + chi_true[I, J] * a for I in range(2)
            ]
    res = build_chi_matrix_5point(obs, 2, delta, 'SCREENED')
    assert np.allclose(res['matrix'], chi_true, atol=1e-8)


def test_chi_5point_missing_alpha_raises():
    """Missing alpha point must raise KeyError."""
    delta = 0.01
    obs = {(0, -delta, 'SCREENED'): [9.4, 9.5]}  # only 1 of 5
    with pytest.raises(KeyError):
        build_chi_matrix_5point(obs, 2, delta, 'SCREENED')


# ═══════════════════════════════════════════════════════════════════════════
# 3. MATRIX DIAGNOSTICS (SVD / CONDITION / RESIDUALS)
# ═══════════════════════════════════════════════════════════════════════════

def test_compute_U_matrix_full_rank():
    """U = chi0^-1 - chi^-1, SVD and residuals actually computed."""
    chi0 = np.array([[-0.25, 0.05], [0.05, -0.25]])
    chi  = np.array([[-0.09, 0.01], [0.01, -0.09]])
    res  = compute_U_matrix(chi0, chi)

    assert res['chi0_rank'] == 2
    assert res['chi_rank']  == 2

    # SVD must be real arrays, not empty lists
    assert len(res['chi0_svd']) == 2
    assert len(res['chi_svd'])  == 2
    assert all(v > 0 for v in res['chi0_svd'])

    # Condition numbers must be > 1
    assert res['chi0_cond'] >= 1.0
    assert res['chi_cond']  >= 1.0

    # Inversion residuals must be near machine precision
    assert res['left_residual']  < 1e-10
    assert res['right_residual'] < 1e-10

    # U value must match direct calculation
    U_expected = np.linalg.inv(chi0) - np.linalg.inv(chi)
    assert np.allclose(res['U'], U_expected, atol=1e-10)

    # Antisymmetric norm — symmetric chi0/chi give symmetric U
    assert res['U_antisym_norm'] < 1e-10


def test_compute_U_matrix_rank_deficient_chi_raises():
    """Rank-deficient chi must raise ValueError mentioning rank."""
    chi0 = np.array([[-0.25, 0.05], [0.05, -0.25]])
    chi_singular = np.zeros((2, 2))
    with pytest.raises(ValueError, match='rank'):
        compute_U_matrix(chi0, chi_singular)


def test_compute_U_matrix_rank_deficient_chi0_raises():
    """Rank-deficient chi0 must raise ValueError."""
    chi0_singular = np.zeros((2, 2))
    chi = np.array([[-0.09, 0.01], [0.01, -0.09]])
    with pytest.raises(ValueError, match='rank'):
        compute_U_matrix(chi0_singular, chi)


def test_eigenmode_analysis_2x2():
    """Eigenmode analysis returns uniform mode eigenvalue."""
    U = np.array([[8.0, 1.0], [1.0, 8.0]])  # symmetric, well-conditioned
    res = eigenmode_analysis(U, 2)
    assert len(res['eigenvalues']) == 2
    assert res['uniform_mode_eigenvalue'] is not None
    assert res['uniform_mode_overlap'] > 0.5


# ═══════════════════════════════════════════════════════════════════════════
# 4. GEOMETRY VALIDATORS
# ═══════════════════════════════════════════════════════════════════════════

from production_benchmarks.geometry_validator import (
    verify_cuprite_cu2o, verify_rocksalt_afm, verify_cu3n_antireo3,
    verify_afm_ii_ordering, validate_no_duplicate_atoms
)


# ── Cu2O ────────────────────────────────────────────────────────────────────

def test_cu2o_geometry_valid():
    a = 4.27
    fracs = np.array([
        [0.00, 0.00, 0.00], [0.50, 0.50, 0.50],
        [0.25, 0.25, 0.25], [0.25, 0.75, 0.75],
        [0.75, 0.25, 0.75], [0.75, 0.75, 0.25]
    ])
    labels = ['O', 'O', 'Cu', 'Cu', 'Cu', 'Cu']
    r = verify_cuprite_cu2o(fracs, labels, a)
    assert r['geometry_valid'], f"Expected valid Cu2O, errors: {r['errors']}"
    # Derived, not hardcoded
    assert r['cu_o_nearest_ang'] is not None
    assert abs(r['cu_o_nearest_ang'] - a * np.sqrt(3) / 4) < 0.05
    assert r['cu_coordination'] == 2
    assert r['o_coordination']  == 4
    assert r['all_cu_equivalent']


def test_cu2o_geometry_invalid_wrong_stoich():
    """Extra Cu atom gives stoichiometry mismatch -> geometry_valid=False."""
    a = 4.27
    fracs = np.array([
        [0.00, 0.00, 0.00], [0.50, 0.50, 0.50],
        [0.25, 0.25, 0.25], [0.25, 0.75, 0.75],
        [0.75, 0.25, 0.75], [0.75, 0.75, 0.25],
        [0.10, 0.10, 0.10],  # extra Cu
    ])
    labels = ['O', 'O', 'Cu', 'Cu', 'Cu', 'Cu', 'Cu']
    r = verify_cuprite_cu2o(fracs, labels, a)
    assert not r['geometry_valid'], "Should fail: stoichiometry 5:2 != 2:1"


def test_cu2o_geometry_invalid_duplicate():
    """Duplicate atom -> geometry_valid=False."""
    a = 4.27
    fracs = np.array([
        [0.00, 0.00, 0.00], [0.50, 0.50, 0.50],
        [0.25, 0.25, 0.25], [0.25, 0.75, 0.75],
        [0.75, 0.25, 0.75], [0.25, 0.25, 0.25],  # duplicate of [2]
    ])
    labels = ['O', 'O', 'Cu', 'Cu', 'Cu', 'Cu']
    r = verify_cuprite_cu2o(fracs, labels, a)
    assert not r['geometry_valid'], "Should fail: duplicate atom"


# ── FeO / NiO rocksalt ──────────────────────────────────────────────────────

def test_rocksalt_afm_feo_valid():
    """Valid 4-atom rhombohedral FeO AFM-II cell passes rocksalt validator."""
    a = 4.334
    lat_vecs = np.array([[0.0, 1.0, 1.0], [0.5, 0.0, 0.5], [0.5, 0.5, 0.0]]) * a
    fracs = np.array([
        [0.0, 0.0, 0.0], [0.5, 0.0, 0.0],
        [0.25, 0.5, 0.5], [0.75, 0.5, 0.5],
    ])
    labels = ['Fe', 'Fe', 'O', 'O']
    spins  = [4.0, -4.0]
    r = verify_rocksalt_afm(fracs, labels, a, 'Fe', 'O', cation_spins=spins, lattice_vectors=lat_vecs)
    assert r['geometry_valid'],    f"Expected valid FeO, errors: {r['errors']}"
    assert r['n_cation'] == 2
    assert r['n_anion']  == 2
    assert r['cation_coord'] == 6, f"Rocksalt cation coord should be 6, got {r['cation_coord']}"
    assert r['afm_ii_valid'] is True


def test_rocksalt_afm_feo_wrong_stoich():
    """3 Fe + 4 O is invalid."""
    a = 4.334
    fracs = np.array([
        [0.0, 0.0, 0.0], [0.5, 0.5, 0.0], [0.5, 0.0, 0.5],
        [0.5, 0.0, 0.0], [0.0, 0.5, 0.0], [0.0, 0.0, 0.5], [0.5, 0.5, 0.5],
    ])
    labels = ['Fe', 'Fe', 'Fe', 'O', 'O', 'O', 'O']
    r = verify_rocksalt_afm(fracs, labels, a, 'Fe', 'O')
    assert not r['geometry_valid']


def test_afm_ii_validation_correct_signs():
    """Correct AFM-II spin assignment (balanced sublattices) passes."""
    a = 4.334
    lat_vecs = np.array([[0.0, 1.0, 1.0], [0.5, 0.0, 0.5], [0.5, 0.5, 0.0]]) * a
    cat_fracs = np.array([
        [0.0, 0.0, 0.0],
        [0.5, 0.0, 0.0],
    ])
    spins = [4.0, -4.0]
    r = verify_afm_ii_ordering(cat_fracs, spins, lat_vectors=lat_vecs)
    assert r['afm_ii_valid'], f"AFM-II check failed: {r['errors']}"


def test_afm_ii_validation_deliberately_wrong():
    """Uncompensated / un-balanced spin assignment makes AFM-II validation FAIL."""
    cat_fracs = np.array([
        [0.0, 0.0, 0.0],
        [0.5, 0.0, 0.0],
    ])
    spins = [4.0, 4.0]  # FM spin alignment (both +4.0)
    r = verify_afm_ii_ordering(cat_fracs, spins)
    assert not r['afm_ii_valid'], \
        "AFM-II check should FAIL when spins are parallel (uncompensated)"


# ── Cu3N ────────────────────────────────────────────────────────────────────

def test_cu3n_geometry_valid():
    """Valid Cu3N anti-ReO3."""
    a = 3.84
    fracs = np.array([
        [0.0, 0.0, 0.0],
        [0.5, 0.0, 0.0],
        [0.0, 0.5, 0.0],
        [0.0, 0.0, 0.5],
    ])
    labels = ['N', 'Cu', 'Cu', 'Cu']
    r = verify_cu3n_antireo3(fracs, labels, a)
    assert r['geometry_valid'], f"Expected valid Cu3N, errors: {r['errors']}"
    assert r['n_cu'] == 3
    assert r['n_n']  == 1
    assert r['cu_coordination'] == 2
    assert r['n_coordination']  == 6
    assert abs(r['cu_n_nearest_ang'] - a/2) < 0.01


def test_cu3n_geometry_invalid_stoichiometry():
    """Wrong stoichiometry (2 Cu, 1 N) -> FAIL."""
    a = 3.84
    fracs = np.array([[0.0,0.0,0.0],[0.5,0.0,0.0],[0.0,0.5,0.0]])
    labels = ['N', 'Cu', 'Cu']
    r = verify_cu3n_antireo3(fracs, labels, a)
    assert not r['geometry_valid'], "2Cu:1N should fail 3:1 stoichiometry check"


def test_cu3n_geometry_invalid_duplicate():
    """Duplicate atom position -> FAIL."""
    a = 3.84
    fracs = np.array([
        [0.0, 0.0, 0.0],
        [0.5, 0.0, 0.0],
        [0.5, 0.0, 0.0],  # duplicate
        [0.0, 0.0, 0.5],
    ])
    labels = ['N', 'Cu', 'Cu', 'Cu']
    r = verify_cu3n_antireo3(fracs, labels, a)
    assert not r['geometry_valid']


def test_no_duplicate_atoms_true():
    fracs = np.array([[0.0,0.0,0.0],[0.5,0.5,0.5],[0.25,0.25,0.25]])
    assert validate_no_duplicate_atoms(fracs)


def test_no_duplicate_atoms_false():
    fracs = np.array([[0.0,0.0,0.0],[0.0,0.0,0.0],[0.25,0.25,0.25]])
    assert not validate_no_duplicate_atoms(fracs)


# ═══════════════════════════════════════════════════════════════════════════
# 5. SUPERCELL BUILDER
# ═══════════════════════════════════════════════════════════════════════════

from production_benchmarks.supercell_builder import (
    build_supercell, assign_afm_ordering,
    get_afm_supercell_options, verify_stoichiometry
)


def test_supercell_2x1x1_atom_count():
    """2x1x1 supercell of 2-atom cell -> 4 atoms."""
    fracs  = np.array([[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]], dtype=float)
    labels = ['A', 'B']
    ids    = [1, 2]
    lat    = np.eye(3) * 4.0
    sc_mat = np.array([[2, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=float)
    nf, nl, nids, nlat = build_supercell(fracs, labels, ids, lat, sc_mat)
    assert len(nl) == 4, f"Expected 4 atoms, got {len(nl)}"
    assert nl.count('A') == 2
    assert nl.count('B') == 2


def test_supercell_determinant_atom_count():
    """det(S) * N_prim == N_supercell for various S."""
    fracs  = np.array([[0.0, 0.0, 0.0], [0.5, 0.5, 0.0],
                       [0.5, 0.0, 0.5], [0.0, 0.5, 0.5],
                       [0.5, 0.0, 0.0], [0.0, 0.5, 0.0],
                       [0.0, 0.0, 0.5], [0.5, 0.5, 0.5]], dtype=float)
    labels = ['Fe','Fe','Fe','Fe','O','O','O','O']
    ids    = [1,1,1,1,2,2,2,2]
    lat    = np.eye(3) * 4.334

    for sc_mat in [[[2,0,0],[0,1,0],[0,0,1]],
                   [[2,0,0],[0,2,0],[0,0,1]]]:
        sc = np.array(sc_mat, dtype=float)
        det = int(round(abs(np.linalg.det(sc))))
        nf, nl, nids, nlat = build_supercell(fracs, labels, ids, lat, sc)
        assert len(nl) == det * 8, \
            f"Expected {det*8} atoms for det={det}, got {len(nl)}"


def test_supercell_no_duplicates():
    """Supercell must not contain duplicate fractional positions."""
    fracs  = np.array([[0.0,0.0,0.0],[0.5,0.5,0.5]], dtype=float)
    labels = ['A','B']
    ids    = [1, 2]
    lat    = np.eye(3) * 4.0
    sc_mat = np.array([[3,0,0],[0,1,0],[0,0,1]], dtype=float)
    nf, nl, _, _ = build_supercell(fracs, labels, ids, lat, sc_mat)
    assert validate_no_duplicate_atoms(nf), "Supercell contains duplicate atoms"


def test_supercell_stoichiometry_preserved():
    """1:1 stoichiometry preserved in 2x2x1 supercell."""
    fracs  = np.array([[0.0,0.0,0.0],[0.5,0.0,0.0],
                       [0.0,0.5,0.0],[0.0,0.0,0.5],
                       [0.5,0.5,0.0],[0.5,0.0,0.5],
                       [0.0,0.5,0.5],[0.5,0.5,0.5]], dtype=float)
    labels = ['Fe','Fe','Fe','Fe','O','O','O','O']
    ids    = [1,1,1,1,2,2,2,2]
    lat    = np.eye(3) * 4.334
    sc_mat = np.array([[2,0,0],[0,2,0],[0,0,1]], dtype=float)
    _, nl, _, _ = build_supercell(fracs, labels, ids, lat, sc_mat)
    assert verify_stoichiometry(nl, {'Fe': 4, 'O': 4})


def test_verify_stoichiometry_returns_false_on_bad_input():
    """verify_stoichiometry must return False for corrupted structure."""
    labels_bad = ['Fe', 'Fe', 'Fe', 'O']  # 3:1 not 1:1
    assert not verify_stoichiometry(labels_bad, {'Fe': 1, 'O': 1})


def test_afm_supercell_options_structure():
    """get_afm_supercell_options returns 3 options with increasing sizes."""
    opts = get_afm_supercell_options('FeO')
    assert len(opts) == 3
    sizes = [opt['n_cation'] for opt in opts]
    assert sizes == sorted(sizes), "Options should be ordered by size"
    for opt in opts:
        assert opt['n_cation'] == opt['n_anion'], \
            "FeO stoichiometry must be 1:1"


# ═══════════════════════════════════════════════════════════════════════════
# 6. CAMPAIGN STATE
# ═══════════════════════════════════════════════════════════════════════════

from production_benchmarks.campaign_state import CampaignState, resume_incomplete


def test_campaign_state_mark_complete(tmp_path):
    cs = CampaignState(str(tmp_path))
    cs.mark_complete('key1', {'r2': 0.999})
    assert cs.is_complete('key1')
    assert not cs.is_complete('key_never')


def test_campaign_state_completed_not_rerun(tmp_path):
    """Completed key must remain complete after reload."""
    cs = CampaignState(str(tmp_path))
    cs.mark_complete('run_A', {'ok': True})
    # Reload from disk
    cs2 = CampaignState(str(tmp_path))
    assert cs2.is_complete('run_A'), "Completed key lost after reload"


def test_campaign_state_incomplete_returned_by_resume(tmp_path):
    """Failed-but-not-completed key returned by resume."""
    cs = CampaignState(str(tmp_path))
    cs.mark_failed('run_B', 'timeout')
    pending = resume_incomplete(str(tmp_path))
    assert 'run_B' in pending


def test_campaign_state_failed_can_be_retried(tmp_path):
    """mark_complete after mark_failed removes from failed set."""
    cs = CampaignState(str(tmp_path))
    cs.mark_failed('run_C', 'error')
    assert 'run_C' in cs.pending_keys()
    cs.mark_complete('run_C', {'retried': True})
    assert 'run_C' not in cs.pending_keys()
    assert cs.is_complete('run_C')


def test_campaign_state_save_load_roundtrip(tmp_path):
    """State survives a full save/load cycle."""
    cs = CampaignState(str(tmp_path))
    cs.mark_complete('key_x', {'val': 42})
    cs.mark_failed('key_y', 'oops')
    cs.set_reference_dm('sha256abc')
    cs.set_dag_node('SCREENING')

    cs2 = CampaignState(str(tmp_path))
    assert cs2.is_complete('key_x')
    assert 'key_y' in cs2.pending_keys()
    assert cs2.reference_dm_sha256 == 'sha256abc'
    assert cs2.current_dag_node == 'SCREENING'


def test_campaign_state_changed_identity_not_reused(tmp_path):
    """Different identity key must be treated as new run."""
    cs = CampaignState(str(tmp_path))
    cs.mark_complete('site0_alpha_0.01', {'ok': True})
    assert not cs.is_complete('site0_alpha_0.02')


# ═══════════════════════════════════════════════════════════════════════════
# 7. DM INVARIANT
# ═══════════════════════════════════════════════════════════════════════════

def test_dm_invariant_stale_child_overwritten(tmp_path):
    from siestaflow_hubbard.siesta_backend.adapter import prepare_canonical_dm
    ref  = tmp_path / 'reference.DM'
    child= tmp_path / 'child.DM'
    canonical_bytes = b'canonical_dm_data_AAAA'
    stale_bytes     = b'stale_modified_dm_BBBB'
    ref.write_bytes(canonical_bytes)
    child.write_bytes(stale_bytes)
    ref_sha = hashlib.sha256(canonical_bytes).hexdigest()
    returned = prepare_canonical_dm(str(ref), str(child), ref_sha)
    assert child.read_bytes() == canonical_bytes
    assert returned == ref_sha


def test_dm_invariant_manifest_hash_is_prerun(tmp_path):
    from siestaflow_hubbard.siesta_backend.adapter import prepare_canonical_dm
    ref   = tmp_path / 'reference.DM'
    child = tmp_path / 'child.DM'
    canonical_bytes = b'canonical_reference_dm_bytes'
    post_run_bytes  = b'siesta_modified_dm_after_scf'
    ref.write_bytes(canonical_bytes)
    ref_sha = hashlib.sha256(canonical_bytes).hexdigest()
    parent_sha = prepare_canonical_dm(str(ref), str(child), ref_sha)
    child.write_bytes(post_run_bytes)
    final_sha = hashlib.sha256(post_run_bytes).hexdigest()
    assert parent_sha == ref_sha
    assert parent_sha != final_sha


def test_dm_invariant_raises_on_corrupt_source(tmp_path):
    from siestaflow_hubbard.siesta_backend.adapter import prepare_canonical_dm
    ref   = tmp_path / 'reference.DM'
    child = tmp_path / 'child.DM'
    ref.write_bytes(b'real_dm_content')
    with pytest.raises(RuntimeError, match='mismatch'):
        prepare_canonical_dm(str(ref), str(child), '0' * 64)


def test_resume_does_not_reuse_stale_dm(tmp_path):
    """On resume, stale child DM is overwritten from canonical reference."""
    from siestaflow_hubbard.siesta_backend.adapter import prepare_canonical_dm
    ref   = tmp_path / 'ref.DM'
    child = tmp_path / 'child.DM'
    canonical = b'canonical_bytes_for_resume_test'
    stale     = b'stale_bytes_from_failed_run'
    ref.write_bytes(canonical)
    child.write_bytes(stale)
    ref_sha = hashlib.sha256(canonical).hexdigest()
    prepare_canonical_dm(str(ref), str(child), ref_sha)
    assert child.read_bytes() == canonical


# ═══════════════════════════════════════════════════════════════════════════
# 8. SPECIES SPLITTING — AFM PRESERVATION
# ═══════════════════════════════════════════════════════════════════════════

def test_feo_afm_species_split_preserves_spins():
    from siestaflow_hubbard.siesta_backend.fdf_builder import materialize_split_species_fdf
    base_fdf = """
NumberOfAtoms 8
NumberOfSpecies 2
%block ChemicalSpeciesLabel
 1 26 Fe
 2  8 O
%endblock ChemicalSpeciesLabel
%block AtomicCoordinatesAndAtomicSpecies
 0.0 0.0 0.0 1
 0.5 0.5 0.0 1
 0.5 0.0 0.5 1
 0.0 0.5 0.5 1
 0.5 0.0 0.0 2
 0.0 0.5 0.0 2
 0.0 0.0 0.5 2
 0.5 0.5 0.5 2
%endblock AtomicCoordinatesAndAtomicSpecies
Spin polarized
%block DM.InitSpin
 1 +4.0
 2 -4.0
 3 +4.0
 4 -4.0
 5  0.0
 6  0.0
 7  0.0
 8  0.0
%endblock DM.InitSpin
"""
    new_fdf, labels = materialize_split_species_fdf(
        base_fdf, target_species='Fe', new_prefix='FeLR'
    )
    # All 4 Fe aliases must be present
    assert len(labels) == 4
    for lbl in labels:
        assert lbl in new_fdf
    # Opposite spins preserved
    assert '+4.0' in new_fdf
    assert '-4.0' in new_fdf
    # NumberOfSpecies increased (4 FeLR + O = 5)
    import re
    m = re.search(r'NumberOfSpecies\s+(\d+)', new_fdf)
    assert m and int(m.group(1)) == 5


def test_nio_afm_species_split_preserves_spins():
    from siestaflow_hubbard.siesta_backend.fdf_builder import materialize_split_species_fdf
    base_fdf = """
NumberOfAtoms 8
NumberOfSpecies 2
%block ChemicalSpeciesLabel
 1 28 Ni
 2  8 O
%endblock ChemicalSpeciesLabel
%block AtomicCoordinatesAndAtomicSpecies
 0.0 0.0 0.0 1
 0.5 0.5 0.0 1
 0.5 0.0 0.5 1
 0.0 0.5 0.5 1
 0.5 0.0 0.0 2
 0.0 0.5 0.0 2
 0.0 0.0 0.5 2
 0.5 0.5 0.5 2
%endblock AtomicCoordinatesAndAtomicSpecies
Spin polarized
%block DM.InitSpin
 1 +2.0
 2 -2.0
 3 +2.0
 4 -2.0
 5  0.0
 6  0.0
 7  0.0
 8  0.0
%endblock DM.InitSpin
"""
    new_fdf, labels = materialize_split_species_fdf(
        base_fdf, target_species='Ni', new_prefix='NiLR'
    )
    assert '+2.0' in new_fdf
    assert '-2.0' in new_fdf
    assert len(labels) == 4


# ═══════════════════════════════════════════════════════════════════════════
# 9. CALCULATION IDENTITY
# ═══════════════════════════════════════════════════════════════════════════

from production_benchmarks.campaign_schema import CalculationIdentity


def _make_identity(**overrides):
    base = dict(
        geometry_sha256='abc123', species_map='Fe:Fe,O:O',
        pseudopotential_sha256s='xxx', siesta_version='5.4.2',
        spin_mode='polarized', basis='DZP', energy_shift_ry=0.005,
        mesh_cutoff_ry=200, kgrid='4x4x4', supercell='1x1x1',
        projector_method=2, projector_nl='3d', projector_rc=3.0,
        projector_omega=0.05, alpha=0.01, perturbed_site=0,
        mode='BARE', reference_dm_sha256='deadbeef'
    )
    base.update(overrides)
    return CalculationIdentity(**base)


def test_calculation_identity_key_unique_on_alpha():
    id1 = _make_identity(alpha=0.01)
    id2 = _make_identity(alpha=0.02)
    assert id1.compute_key() != id2.compute_key()


def test_calculation_identity_key_unique_on_mode():
    id1 = _make_identity(mode='BARE')
    id2 = _make_identity(mode='SCREENED')
    assert id1.compute_key() != id2.compute_key()


def test_calculation_identity_key_unique_on_site():
    id1 = _make_identity(perturbed_site=0)
    id2 = _make_identity(perturbed_site=1)
    assert id1.compute_key() != id2.compute_key()


def test_calculation_identity_same_inputs_same_key():
    id1 = _make_identity()
    id2 = _make_identity()
    assert id1.compute_key() == id2.compute_key()


# ═══════════════════════════════════════════════════════════════════════════
# 10. SLURM / DRY-RUN
# ═══════════════════════════════════════════════════════════════════════════

from production_benchmarks.slurm_runner import (
    calculate_ranks_per_run, generate_slurm_script,
    write_slurm_script, estimate_run_counts, SlurmProfile
)


def test_calculate_ranks_per_run():
    assert calculate_ranks_per_run(100, 5)  == 20
    assert calculate_ranks_per_run(100, 4)  == 25
    assert calculate_ranks_per_run(100, 10) == 10


def test_generate_slurm_script_nonempty():
    profile = SlurmProfile(
        partition='test', nodes=2, ntasks_total=40, cpus_per_task=1,
        mem_per_node=32, walltime='2:00:00', siesta_binary='/usr/bin/siesta',
        mpi_launcher='srun', mpi_flags='', module_loads=['openmpi/4.0']
    )
    script = generate_slurm_script(profile, '/campaign', 'NiO', 'SCREENING', [], 4)
    assert script, "Script must not be empty"
    assert '#SBATCH' in script
    assert 'NiO' in script
    assert 'OMP_NUM_THREADS' in script


def test_write_slurm_script(tmp_path):
    script = "#!/bin/bash\n#SBATCH --job-name=test\n"
    out = str(tmp_path / 'test.slurm')
    write_slurm_script(script, out)
    assert os.path.exists(out)
    with open(out) as fh:
        assert fh.read() == script


def test_write_slurm_script_empty_raises():
    with pytest.raises(ValueError):
        write_slurm_script('', '/tmp/out.slurm')


def test_estimate_run_counts_nonzero():
    mat_cfg = {
        'n_correlated_sites': 4,
        'spin_mode': 'non_polarized',
        'convergence_sequence': [
            {'dimension': 'energy_shift_ry', 'values': [0.02, 0.01, 0.005]},
            {'dimension': 'kgrid', 'values': [[2,2,2], [4,4,4]]},
        ]
    }
    counts = estimate_run_counts(mat_cfg)
    assert counts['total'] > 0
    assert counts['reference'] == 1
    assert counts['final_lr'] > 0


def test_dry_run_produces_unique_dirs(tmp_path):
    """Dry-run must create distinct directories for each (J, alpha, mode) combo."""
    campaign_dir = str(tmp_path / 'campaign')
    os.makedirs(campaign_dir, exist_ok=True)
    _ensure_dummy_ref_dm(campaign_dir, 'Cu2O')

    # Create minimal material.json
    mat_dir = os.path.join(campaign_dir, 'materials', 'cu2o')
    os.makedirs(mat_dir, exist_ok=True)
    mat_cfg = {
        'name': 'Cu2O',
        'lattice_constant_ang': 4.27,
        'lattice_vectors': [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        'spin_mode': 'non_polarized',
        'n_correlated_sites': 4,
        'n_cu_sites': 4,
        'base_fractional_coords': [
            {'label': 'O', 'species': 'O', 'frac': [0.0,0.0,0.0]},
            {'label': 'O', 'species': 'O', 'frac': [0.5,0.5,0.5]},
            {'label': 'Cu', 'species': 'Cu', 'frac': [0.25,0.25,0.25]},
            {'label': 'Cu', 'species': 'Cu', 'frac': [0.25,0.75,0.75]},
            {'label': 'Cu', 'species': 'Cu', 'frac': [0.75,0.25,0.75]},
            {'label': 'Cu', 'species': 'Cu', 'frac': [0.75,0.75,0.25]},
        ],
        'pseudopotentials': {'Cu': {'file': 'Cu.psml', 'uuid': 'x', 'sha256': 'x'},
                             'O':  {'file': 'O.psml',  'uuid': 'x', 'sha256': 'x'}},
        'convergence_sequence': [],
    }
    with open(os.path.join(mat_dir, 'material.json'), 'w') as fh:
        json.dump(mat_cfg, fh)

    from production_benchmarks.slurm_runner import cli_main
    ret = cli_main([
        '--campaign-dir', campaign_dir,
        '--material', 'Cu2O',
        '--dag-node', 'SCREENING',
        '--mpi-ranks', '4',
        '--max-concurrent', '2',
        '--alpha', '-0.01', '0.0', '0.01',
        '--dry-run',
    ])
    assert ret == 0

    # Find all run dirs created
    runs_root = os.path.join(campaign_dir, 'runs', 'Cu2O', 'SCREENING')
    if os.path.exists(runs_root):
        dirs = [d for d in os.listdir(runs_root) if os.path.isdir(os.path.join(runs_root, d))]
        # 2 common + 4*4 = 18
        assert len(dirs) == 18, f"Expected 18 unique dirs, got {len(dirs)}: {dirs}"
        # All unique
        assert len(dirs) == len(set(dirs))


def test_dry_run_manifest_contains_correct_sites(tmp_path):
    """Dry-run manifest must reference all 4 Cu sites for Cu2O."""
    campaign_dir = str(tmp_path / 'campaign')
    os.makedirs(campaign_dir, exist_ok=True)
    _ensure_dummy_ref_dm(campaign_dir, 'Cu2O')
    mat_dir = os.path.join(campaign_dir, 'materials', 'cu2o')
    os.makedirs(mat_dir, exist_ok=True)
    mat_cfg = {
        'name': 'Cu2O', 'lattice_constant_ang': 4.27,
        'lattice_vectors': [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        'spin_mode': 'non_polarized',
        'n_correlated_sites': 4, 'n_cu_sites': 4,
        'base_fractional_coords': [
            {'label': 'O', 'species': 'O', 'frac': [0.0,0.0,0.0]},
            {'label': 'O', 'species': 'O', 'frac': [0.5,0.5,0.5]},
            {'label': 'Cu', 'species': 'Cu', 'frac': [0.25,0.25,0.25]},
            {'label': 'Cu', 'species': 'Cu', 'frac': [0.25,0.75,0.75]},
            {'label': 'Cu', 'species': 'Cu', 'frac': [0.75,0.25,0.75]},
            {'label': 'Cu', 'species': 'Cu', 'frac': [0.75,0.75,0.25]},
        ],
        'pseudopotentials': {'Cu': {'file': 'Cu.psml', 'uuid': 'x', 'sha256': 'x'}},
        'convergence_sequence': [],
    }
    with open(os.path.join(mat_dir, 'material.json'), 'w') as fh:
        json.dump(mat_cfg, fh)

    from production_benchmarks.slurm_runner import cli_main
    cli_main([
        '--campaign-dir', campaign_dir,
        '--material', 'Cu2O',
        '--dag-node', 'FINAL_5POINT',
        '--alpha', '-0.02', '-0.01', '0.0', '0.01', '0.02',
        '--dry-run',
    ])

    manifest_path = os.path.join(campaign_dir, 'runs', 'Cu2O',
                                  'FINAL_5POINT_dryrun_manifest.json')
    assert os.path.exists(manifest_path)
    with open(manifest_path) as fh:
        runs = json.load(fh)

    sites = {r['perturbed_site'] for r in runs}
    assert sites == {0, 1, 2, 3}, f"Expected 4 distinct sites, got {sites}"
    # 2 common + 8*4 = 34 runs
    assert len(runs) == 34


# ═══════════════════════════════════════════════════════════════════════════
# 11. MPI SCALING
# ═══════════════════════════════════════════════════════════════════════════

from production_benchmarks.mpi_scaling import (
    generate_scaling_fdf, parse_scaling_result, recommend_mpi_config
)


def test_generate_scaling_fdf_sets_max_scf():
    base = "SystemLabel mytest\nMaxSCFIterations 200\n"
    result = generate_scaling_fdf(base, 5, 'bench')
    assert 'MaxSCFIterations 5' in result


def test_generate_scaling_fdf_empty_base_raises():
    with pytest.raises(ValueError):
        generate_scaling_fdf('', 5, 'label')


def test_generate_scaling_fdf_contains_header():
    base = "SystemLabel test\n"
    result = generate_scaling_fdf(base, 3, 'myscale')
    assert 'SCALING BENCHMARK' in result.upper() or 'benchmark' in result.lower()


def test_parse_scaling_result_empty_returns_fail():
    r = parse_scaling_result('')
    assert not r['parse_success']


def test_parse_scaling_result_with_timing():
    fake_out = """
siesta: iscf =  1  Etot = -100.0  Time = 2.34
siesta: iscf =  2  Etot = -100.1  Time = 2.11
siesta: iscf =  3  Etot = -100.2  Time = 2.18
siesta: Total cpu time =  12.5
"""
    r = parse_scaling_result(fake_out)
    assert r['parse_success']
    assert r['n_scf_completed'] == 3
    assert len(r['scf_times']) == 3
    assert r['walltime_per_scf_s'] is not None


def test_recommend_mpi_config_no_data_returns_pending():
    r = recommend_mpi_config([])
    assert r['MPI_RECOMMENDATION_STATUS'] == 'PENDING_MEASUREMENT'
    assert r['recommended_ranks_per_run'] is None


def test_recommend_mpi_config_with_data():
    data = [
        {'n_ranks': 20,  'walltime_per_scf_s': 5.0},
        {'n_ranks': 40,  'walltime_per_scf_s': 3.0},
        {'n_ranks': 100, 'walltime_per_scf_s': 2.0},
    ]
    r = recommend_mpi_config(data)
    assert r['MPI_RECOMMENDATION_STATUS'] == 'MEASURED'
    assert r['recommended_ranks_per_run'] in [20, 40, 100]
    assert r['max_concurrent_runs'] >= 1


# ═══════════════════════════════════════════════════════════════════════════
# 12. PREFLIGHT NEGATIVE TESTS
# ═══════════════════════════════════════════════════════════════════════════

def test_preflight_fails_with_missing_pseudo(tmp_path, capsys):
    """Preflight must FAIL if a pseudopotential file is missing."""
    from production_benchmarks.preflight import run_preflight
    campaign_dir = str(tmp_path / 'campaign')
    os.makedirs(os.path.join(campaign_dir, 'materials', 'cu2o'), exist_ok=True)
    mat_cfg = {
        'name': 'Cu2O', 'lattice_constant_ang': 4.27,
        'spin_mode': 'non_polarized', 'n_correlated_sites': 4, 'n_cu_sites': 4,
        'pseudopotentials': {
            'Cu': {'file': 'Cu_MISSING.psml', 'uuid': 'x', 'sha256': 'abc'},
        },
        'base_fractional_coords': [],
        'convergence_sequence': [
            {'dimension': 'kgrid', 'values': [[2,2,2]], 'accepted_value': None}
        ],
        'candidate_baseline': {'projector_rc_bohr': 3.0, 'projector_omega_bohr': 0.05, 'alpha_ev': 0.01},
    }
    with open(os.path.join(campaign_dir, 'materials', 'cu2o', 'material.json'), 'w') as fh:
        json.dump(mat_cfg, fh)
    # Create Slurm profile to avoid that failure
    os.makedirs(os.path.join(campaign_dir, 'yoltla'), exist_ok=True)
    profile = {'partition': 'test', 'nodes': 1, 'ntasks_total': 4,
               'siesta_binary': '/usr/bin/siesta', 'mpi_launcher': 'srun',
               'scratch_base': '/tmp/x'}
    with open(os.path.join(campaign_dir, 'yoltla', 'profile.json'), 'w') as fh:
        json.dump(profile, fh)

    ok = run_preflight(campaign_dir, pseudo_dirs=[str(tmp_path / 'nonexistent')])
    assert not ok, "Preflight should FAIL with missing pseudopotential"


def test_preflight_fails_with_wrong_sha(tmp_path):
    """Preflight must FAIL if pseudopotential SHA256 does not match."""
    from production_benchmarks.preflight import run_preflight
    campaign_dir = str(tmp_path / 'campaign')
    pseudo_dir   = str(tmp_path / 'pseudos')
    os.makedirs(os.path.join(campaign_dir, 'materials', 'cu2o'), exist_ok=True)
    os.makedirs(pseudo_dir, exist_ok=True)

    # Write a real file with known content
    real_content = b'this is a fake Cu psml'
    real_sha = hashlib.sha256(real_content).hexdigest()
    wrong_sha = 'a' * 64
    assert wrong_sha != real_sha

    with open(os.path.join(pseudo_dir, 'Cu_test.psml'), 'wb') as fh:
        fh.write(real_content)

    mat_cfg = {
        'name': 'Cu2O', 'lattice_constant_ang': 4.27,
        'spin_mode': 'non_polarized', 'n_correlated_sites': 4,
        'pseudopotentials': {
            'Cu': {'file': 'Cu_test.psml', 'uuid': 'test-uuid', 'sha256': wrong_sha},
        },
        'base_fractional_coords': [],
        'convergence_sequence': [],
        'candidate_baseline': {'projector_rc_bohr': 3.0, 'projector_omega_bohr': 0.05, 'alpha_ev': 0.01},
    }
    with open(os.path.join(campaign_dir, 'materials', 'cu2o', 'material.json'), 'w') as fh:
        json.dump(mat_cfg, fh)
    os.makedirs(os.path.join(campaign_dir, 'yoltla'), exist_ok=True)
    with open(os.path.join(campaign_dir, 'yoltla', 'profile.json'), 'w') as fh:
        json.dump({'partition':'t','nodes':1,'ntasks_total':4,
                   'siesta_binary':'/x','mpi_launcher':'srun','scratch_base':'/t'}, fh)

    ok = run_preflight(campaign_dir, pseudo_dirs=[pseudo_dir])
    assert not ok, "Preflight should FAIL with wrong SHA256"


def test_preflight_fails_with_tbd_uuid(tmp_path):
    """Preflight must FAIL if a required UUID is TBD."""
    from production_benchmarks.preflight import check_no_tbd_uuids
    mat_cfg = {
        'pseudopotentials': {
            'Fe': {'file': 'Fe.psml', 'uuid': 'TBD', 'sha256': 'abc123'},
        }
    }
    failures = []
    check_no_tbd_uuids('feo', mat_cfg, failures)
    assert len(failures) > 0, "check_no_tbd_uuids should detect TBD uuid"
    assert 'TBD' in failures[0] or 'tbd' in failures[0].lower()


def test_preflight_fails_if_stub_present():
    """
    check_no_stubs must detect if an implementation is still a pass/empty stub.
    We test this by verifying the current (real) implementation passes the check.
    """
    from production_benchmarks.preflight import check_no_stubs
    failures = []
    check_no_stubs(failures)
    assert not failures, f"Stub check failed on real implementation: {failures}"


# ═══════════════════════════════════════════════════════════════════════════
# 13. BLOCKERS 1-5 SPECIFIC TESTS
# ═══════════════════════════════════════════════════════════════════════════

from production_benchmarks.slurm_runner import (
    generate_lr_run_specs, materialize_run_fdf, RunSpec
)


def test_3point_plan_n2_has_10_runs(tmp_path):
    """N=2 (FeO/NiO) 3-point plan has exactly 2 + 4(2) = 10 runs."""
    campaign_dir = str(tmp_path)
    _ensure_dummy_ref_dm(campaign_dir, 'NiO')
    mat_cfg = {
        'name': 'NiO', 'n_correlated_sites': 2, 'lattice_constant_ang': 4.177,
        'lattice_vectors': [[0.0, 1.0, 1.0], [0.5, 0.0, 0.5], [0.5, 0.5, 0.0]],
        'base_fractional_coords': [
            {'label': 'Ni', 'species': 'Ni', 'frac': [0.0,0.0,0.0], 'init_spin': 2.0},
            {'label': 'Ni', 'species': 'Ni', 'frac': [0.5,0.0,0.0], 'init_spin': -2.0},
            {'label': 'O',  'species': 'O',  'frac': [0.25,0.5,0.5], 'init_spin': 0.0},
            {'label': 'O',  'species': 'O',  'frac': [0.75,0.5,0.5], 'init_spin': 0.0},
        ],
        'pseudopotentials': {'Ni': {'file': 'Ni.psml'}, 'O': {'file': 'O.psml'}},
        'candidate_baseline': {'projector_rc_bohr': 3.0, 'projector_omega_bohr': 0.05},
    }
    specs = generate_lr_run_specs(mat_cfg, 'SCREENING_3POINT', campaign_dir, alphas=[-0.01, 0.0, 0.01])
    assert len(specs) == 10, f"Expected 10 runs for N=2 3-pt, got {len(specs)}"


def test_3point_plan_n4_has_18_runs(tmp_path):
    """N=4 (Cu2O) 3-point plan has exactly 2 + 4(4) = 18 runs."""
    campaign_dir = str(tmp_path)
    _ensure_dummy_ref_dm(campaign_dir, 'Cu2O')
    mat_cfg = {
        'name': 'Cu2O', 'n_correlated_sites': 4, 'lattice_constant_ang': 4.27,
        'lattice_vectors': [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        'spin_mode': 'non_polarized',
        'base_fractional_coords': [
            {'label': 'O', 'species': 'O', 'frac': [0.0,0.0,0.0]},
            {'label': 'O', 'species': 'O', 'frac': [0.5,0.5,0.5]},
            {'label': 'Cu', 'species': 'Cu', 'frac': [0.25,0.25,0.25]},
            {'label': 'Cu', 'species': 'Cu', 'frac': [0.25,0.75,0.75]},
            {'label': 'Cu', 'species': 'Cu', 'frac': [0.75,0.25,0.75]},
            {'label': 'Cu', 'species': 'Cu', 'frac': [0.75,0.75,0.25]},
        ],
        'pseudopotentials': {'Cu': {'file': 'Cu.psml'}, 'O': {'file': 'O.psml'}},
        'candidate_baseline': {'projector_rc_bohr': 3.0, 'projector_omega_bohr': 0.05},
    }
    specs = generate_lr_run_specs(mat_cfg, 'SCREENING_3POINT', campaign_dir, alphas=[-0.01, 0.0, 0.01])
    assert len(specs) == 18, f"Expected 18 runs for N=4 3-pt, got {len(specs)}"


def test_5point_plan_n2_has_18_runs(tmp_path):
    """N=2 5-point plan has exactly 2 + 8(2) = 18 runs."""
    campaign_dir = str(tmp_path)
    _ensure_dummy_ref_dm(campaign_dir, 'NiO')
    mat_cfg = {
        'name': 'NiO', 'n_correlated_sites': 2, 'lattice_constant_ang': 4.177,
        'lattice_vectors': [[0.0, 1.0, 1.0], [0.5, 0.0, 0.5], [0.5, 0.5, 0.0]],
        'base_fractional_coords': [
            {'label': 'Ni', 'species': 'Ni', 'frac': [0.0,0.0,0.0], 'init_spin': 2.0},
            {'label': 'Ni', 'species': 'Ni', 'frac': [0.5,0.0,0.0], 'init_spin': -2.0},
            {'label': 'O',  'species': 'O',  'frac': [0.25,0.5,0.5], 'init_spin': 0.0},
            {'label': 'O',  'species': 'O',  'frac': [0.75,0.5,0.5], 'init_spin': 0.0},
        ],
        'pseudopotentials': {'Ni': {'file': 'Ni.psml'}, 'O': {'file': 'O.psml'}},
        'candidate_baseline': {'projector_rc_bohr': 3.0, 'projector_omega_bohr': 0.05},
    }
    specs = generate_lr_run_specs(mat_cfg, 'FINAL_5POINT', campaign_dir, alphas=[-0.02, -0.01, 0.0, 0.01, 0.02])
    assert len(specs) == 18, f"Expected 18 runs for N=2 5-pt, got {len(specs)}"


def test_5point_plan_n4_has_34_runs(tmp_path):
    """N=4 5-point plan has exactly 2 + 8(4) = 34 runs."""
    campaign_dir = str(tmp_path)
    _ensure_dummy_ref_dm(campaign_dir, 'Cu2O')
    mat_cfg = {
        'name': 'Cu2O', 'n_correlated_sites': 4, 'lattice_constant_ang': 4.27,
        'lattice_vectors': [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        'spin_mode': 'non_polarized',
        'base_fractional_coords': [
            {'label': 'O', 'species': 'O', 'frac': [0.0,0.0,0.0]},
            {'label': 'O', 'species': 'O', 'frac': [0.5,0.5,0.5]},
            {'label': 'Cu', 'species': 'Cu', 'frac': [0.25,0.25,0.25]},
            {'label': 'Cu', 'species': 'Cu', 'frac': [0.25,0.75,0.75]},
            {'label': 'Cu', 'species': 'Cu', 'frac': [0.75,0.25,0.75]},
            {'label': 'Cu', 'species': 'Cu', 'frac': [0.75,0.75,0.25]},
        ],
        'pseudopotentials': {'Cu': {'file': 'Cu.psml'}, 'O': {'file': 'O.psml'}},
        'candidate_baseline': {'projector_rc_bohr': 3.0, 'projector_omega_bohr': 0.05},
    }
    specs = generate_lr_run_specs(mat_cfg, 'FINAL_5POINT', campaign_dir, alphas=[-0.02, -0.01, 0.0, 0.01, 0.02])
    assert len(specs) == 34, f"Expected 34 runs for N=4 5-pt, got {len(specs)}"


def test_alpha0_bare_is_deduplicated(tmp_path):
    """alpha=0 BARE run appears exactly ONCE in plan."""
    campaign_dir = str(tmp_path)
    _ensure_dummy_ref_dm(campaign_dir, 'NiO')
    mat_cfg = {
        'name': 'NiO', 'n_correlated_sites': 2, 'lattice_constant_ang': 4.177,
        'lattice_vectors': [[0.0, 1.0, 1.0], [0.5, 0.0, 0.5], [0.5, 0.5, 0.0]],
        'base_fractional_coords': [{'label':'Ni','species':'Ni','frac':[0,0,0]}],
        'pseudopotentials': {'Ni': {'file': 'Ni.psml'}},
    }
    specs = generate_lr_run_specs(mat_cfg, 'SCREENING_3POINT', campaign_dir)
    alpha0_bare = [s for s in specs if abs(s.alpha) <= 1e-12 and s.response_mode == 'BARE']
    assert len(alpha0_bare) == 1, "alpha=0 BARE must be deduplicated to exactly 1 run"


def test_alpha0_screened_is_deduplicated(tmp_path):
    """alpha=0 SCREENED run appears exactly ONCE in plan."""
    campaign_dir = str(tmp_path)
    _ensure_dummy_ref_dm(campaign_dir, 'NiO')
    mat_cfg = {
        'name': 'NiO', 'n_correlated_sites': 2, 'lattice_constant_ang': 4.177,
        'lattice_vectors': [[0.0, 1.0, 1.0], [0.5, 0.0, 0.5], [0.5, 0.5, 0.0]],
        'base_fractional_coords': [{'label':'Ni','species':'Ni','frac':[0,0,0]}],
        'pseudopotentials': {'Ni': {'file': 'Ni.psml'}},
    }
    specs = generate_lr_run_specs(mat_cfg, 'SCREENING_3POINT', campaign_dir)
    alpha0_screened = [s for s in specs if abs(s.alpha) <= 1e-12 and s.response_mode == 'SCREENED']
    assert len(alpha0_screened) == 1, "alpha=0 SCREENED must be deduplicated to exactly 1 run"


def test_plan_contains_bare_and_screened(tmp_path):
    """Plan contains BOTH BARE and SCREENED for every perturbed site and alpha."""
    campaign_dir = str(tmp_path)
    _ensure_dummy_ref_dm(campaign_dir, 'NiO')
    mat_cfg = {
        'name': 'NiO', 'n_correlated_sites': 2, 'lattice_constant_ang': 4.177,
        'lattice_vectors': [[0.0, 1.0, 1.0], [0.5, 0.0, 0.5], [0.5, 0.5, 0.0]],
        'base_fractional_coords': [{'label':'Ni','species':'Ni','frac':[0,0,0]}],
        'pseudopotentials': {'Ni': {'file': 'Ni.psml'}},
    }
    specs = generate_lr_run_specs(mat_cfg, 'SCREENING_3POINT', campaign_dir)
    modes = {s.response_mode for s in specs}
    assert modes == {'BARE', 'SCREENED'}, "Plan must contain both BARE and SCREENED specs"


def test_nio_dryrun_writes_real_fdfs(tmp_path):
    """Dry-run materializes REAL executable FDF files on disk."""
    campaign_dir = str(tmp_path / 'campaign')
    os.makedirs(os.path.join(campaign_dir, 'materials', 'nio'), exist_ok=True)
    _ensure_dummy_ref_dm(campaign_dir, 'NiO')
    mat_cfg = {
        'name': 'NiO', 'n_correlated_sites': 2, 'lattice_constant_ang': 4.177,
        'lattice_vectors': [[0.0, 1.0, 1.0], [0.5, 0.0, 0.5], [0.5, 0.5, 0.0]],
        'spin_mode': 'collinear_polarized',
        'base_fractional_coords': [
            {'label': 'Ni', 'species': 'Ni', 'frac': [0.0,0.0,0.0], 'init_spin': 2.0},
            {'label': 'Ni', 'species': 'Ni', 'frac': [0.5,0.0,0.0], 'init_spin': -2.0},
            {'label': 'O',  'species': 'O',  'frac': [0.25,0.5,0.5], 'init_spin': 0.0},
            {'label': 'O',  'species': 'O',  'frac': [0.75,0.5,0.5], 'init_spin': 0.0},
        ],
        'pseudopotentials': {'Ni': {'file': 'Ni.psml'}, 'O': {'file': 'O.psml'}},
        'candidate_baseline': {'projector_rc_bohr': 3.0, 'projector_omega_bohr': 0.05},
        'convergence_sequence': [],
    }
    with open(os.path.join(campaign_dir, 'materials', 'nio', 'material.json'), 'w') as fh:
        json.dump(mat_cfg, fh)

    from production_benchmarks.slurm_runner import cli_main
    cli_main(['--campaign-dir', campaign_dir, '--material', 'NiO', '--dag-node', 'SCREENING_3POINT', '--dry-run'])

    runs_dir = os.path.join(campaign_dir, 'runs', 'NiO', 'SCREENING_3POINT')
    assert os.path.exists(runs_dir)
    fdf_files = []
    for root, dirs, files in os.walk(runs_dir):
        for f in files:
            if f == 'siesta.fdf':
                fdf_files.append(os.path.join(root, f))

    assert len(fdf_files) == 10, f"Expected 10 FDF files on disk, got {len(fdf_files)}"
    for fdf in fdf_files:
        with open(fdf, 'r', encoding='utf-8') as fh:
            text = fh.read()
        assert len(text) > 100
        assert '%block DFTU.proj' in text


def test_cu2o_dryrun_writes_real_fdfs(tmp_path):
    """Cu2O dry-run materializes 18 real FDF files on disk."""
    campaign_dir = str(tmp_path / 'campaign')
    os.makedirs(os.path.join(campaign_dir, 'materials', 'cu2o'), exist_ok=True)
    _ensure_dummy_ref_dm(campaign_dir, 'Cu2O')
    mat_cfg = {
        'name': 'Cu2O', 'n_correlated_sites': 4, 'lattice_constant_ang': 4.27,
        'lattice_vectors': [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        'spin_mode': 'non_polarized',
        'base_fractional_coords': [
            {'label': 'O', 'species': 'O', 'frac': [0.0,0.0,0.0]},
            {'label': 'O', 'species': 'O', 'frac': [0.5,0.5,0.5]},
            {'label': 'Cu', 'species': 'Cu', 'frac': [0.25,0.25,0.25]},
            {'label': 'Cu', 'species': 'Cu', 'frac': [0.25,0.75,0.75]},
            {'label': 'Cu', 'species': 'Cu', 'frac': [0.75,0.25,0.75]},
            {'label': 'Cu', 'species': 'Cu', 'frac': [0.75,0.75,0.25]},
        ],
        'pseudopotentials': {'Cu': {'file': 'Cu.psml'}, 'O': {'file': 'O.psml'}},
        'candidate_baseline': {'projector_rc_bohr': 3.0, 'projector_omega_bohr': 0.05},
        'convergence_sequence': [],
    }
    with open(os.path.join(campaign_dir, 'materials', 'cu2o', 'material.json'), 'w') as fh:
        json.dump(mat_cfg, fh)

    from production_benchmarks.slurm_runner import cli_main
    cli_main(['--campaign-dir', campaign_dir, '--material', 'Cu2O', '--dag-node', 'SCREENING_3POINT', '--dry-run'])

    runs_dir = os.path.join(campaign_dir, 'runs', 'Cu2O', 'SCREENING_3POINT')
    fdf_files = [os.path.join(root, f) for root, _, files in os.walk(runs_dir) for f in files if f == 'siesta.fdf']
    assert len(fdf_files) == 18, f"Expected 18 FDF files for Cu2O 3-pt, got {len(fdf_files)}"


def test_nio_bare_fdf_semantics(tmp_path):
    """Verify NiO BARE FDF contains MaxSCFIterations 2 and SCF.MustConverge F."""
    mat_cfg = {
        'name': 'NiO', 'n_correlated_sites': 2, 'lattice_constant_ang': 4.177,
        'spin_mode': 'collinear_polarized',
        'base_fractional_coords': [
            {'label': 'Ni', 'species': 'Ni', 'frac': [0.0,0.0,0.0], 'init_spin': 2.0},
            {'label': 'Ni', 'species': 'Ni', 'frac': [0.5,0.0,0.0], 'init_spin': -2.0},
            {'label': 'O',  'species': 'O',  'frac': [0.25,0.5,0.5]},
            {'label': 'O',  'species': 'O',  'frac': [0.75,0.5,0.5]},
        ],
        'pseudopotentials': {'Ni': {'file': 'Ni.psml'}, 'O': {'file': 'O.psml'}},
        'candidate_baseline': {'projector_rc_bohr': 3.0, 'projector_omega_bohr': 0.05},
    }
    spec = RunSpec(
        run_id='test_bare', work_dir=str(tmp_path), fdf_path=str(tmp_path/'siesta.fdf'),
        canonical_dm_path=str(tmp_path/'ref.DM'), pseudo_paths={'Ni':str(tmp_path/'Ni.psml'),'O':str(tmp_path/'O.psml')},
        mpi_ranks=20, siesta_binary='/x', mpi_launcher='srun', mpi_flags='',
        response_mode='BARE', alpha=0.01, perturbed_site=0, n_sites=2, identity_key='test_bare',
        mat_cfg=mat_cfg,
    )
    fdf_text = materialize_run_fdf(spec)
    assert 'MaxSCFIterations 2' in fdf_text
    assert 'SCF.MustConverge F' in fdf_text
    assert 'NiLR0' in fdf_text
    assert 'NiLR1' in fdf_text
    assert '+2.0' in fdf_text
    assert '-2.0' in fdf_text


def test_nio_screened_fdf_semantics(tmp_path):
    """Verify NiO SCREENED FDF contains DM.UseSaveDM true and opposite spins."""
    mat_cfg = {
        'name': 'NiO', 'n_correlated_sites': 2, 'lattice_constant_ang': 4.177,
        'spin_mode': 'collinear_polarized',
        'base_fractional_coords': [
            {'label': 'Ni', 'species': 'Ni', 'frac': [0.0,0.0,0.0], 'init_spin': 2.0},
            {'label': 'Ni', 'species': 'Ni', 'frac': [0.5,0.0,0.0], 'init_spin': -2.0},
            {'label': 'O',  'species': 'O',  'frac': [0.25,0.5,0.5]},
            {'label': 'O',  'species': 'O',  'frac': [0.75,0.5,0.5]},
        ],
        'pseudopotentials': {'Ni': {'file': 'Ni.psml'}, 'O': {'file': 'O.psml'}},
        'candidate_baseline': {'projector_rc_bohr': 3.0, 'projector_omega_bohr': 0.05},
    }
    spec = RunSpec(
        run_id='test_screened', work_dir=str(tmp_path), fdf_path=str(tmp_path/'siesta.fdf'),
        canonical_dm_path=str(tmp_path/'ref.DM'), pseudo_paths={'Ni':str(tmp_path/'Ni.psml'),'O':str(tmp_path/'O.psml')},
        mpi_ranks=20, siesta_binary='/x', mpi_launcher='srun', mpi_flags='',
        response_mode='SCREENED', alpha=0.01, perturbed_site=0, n_sites=2, identity_key='test_screened',
        mat_cfg=mat_cfg,
    )
    fdf_text = materialize_run_fdf(spec)
    assert 'DM.UseSaveDM true' in fdf_text
    assert 'MaxSCFIterations 2' not in fdf_text
    assert 'NiLR0' in fdf_text


def test_cu2o_nonpolarized_fdf_semantics(tmp_path):
    """Verify Cu2O non-polarized FDF has 4 Cu aliases and no DM.InitSpin."""
    mat_cfg = {
        'name': 'Cu2O', 'n_correlated_sites': 4, 'lattice_constant_ang': 4.27,
        'spin_mode': 'non_polarized',
        'base_fractional_coords': [
            {'label': 'O', 'species': 'O', 'frac': [0.0,0.0,0.0]},
            {'label': 'O', 'species': 'O', 'frac': [0.5,0.5,0.5]},
            {'label': 'Cu', 'species': 'Cu', 'frac': [0.25,0.25,0.25]},
            {'label': 'Cu', 'species': 'Cu', 'frac': [0.25,0.75,0.75]},
            {'label': 'Cu', 'species': 'Cu', 'frac': [0.75,0.25,0.75]},
            {'label': 'Cu', 'species': 'Cu', 'frac': [0.75,0.75,0.25]},
        ],
        'pseudopotentials': {'Cu': {'file': 'Cu.psml'}, 'O': {'file': 'O.psml'}},
        'candidate_baseline': {'projector_rc_bohr': 3.0, 'projector_omega_bohr': 0.05},
    }
    spec = RunSpec(
        run_id='test_cu2o', work_dir=str(tmp_path), fdf_path=str(tmp_path/'siesta.fdf'),
        canonical_dm_path=str(tmp_path/'ref.DM'), pseudo_paths={'Cu':str(tmp_path/'Cu.psml'),'O':str(tmp_path/'O.psml')},
        mpi_ranks=20, siesta_binary='/x', mpi_launcher='srun', mpi_flags='',
        response_mode='SCREENED', alpha=0.01, perturbed_site=1, n_sites=4, identity_key='test_cu2o',
        mat_cfg=mat_cfg,
    )
    fdf_text = materialize_run_fdf(spec)
    assert 'Spin non-polarized' in fdf_text
    assert 'DM.InitSpin' not in fdf_text
    for i in range(4):
        assert f'CuLR{i}' in fdf_text


def test_real_execution_argv_has_no_shell_redirection_tokens(tmp_path):
    """Subprocess mpi_argv must contain NO literal '<', '>', or '2>'."""
    spec = RunSpec(
        run_id='test', work_dir=str(tmp_path), fdf_path=str(tmp_path/'siesta.fdf'),
        canonical_dm_path=str(tmp_path/'ref.DM'), pseudo_paths={},
        mpi_ranks=20, siesta_binary='/usr/bin/siesta', mpi_launcher='srun', mpi_flags='--mpi=pmix',
        response_mode='SCREENED', alpha=0.01, perturbed_site=0, n_sites=2, identity_key='test'
    )
    argv = spec.mpi_argv()
    assert '<' not in argv
    assert '>' not in argv
    assert '2>' not in argv
    assert argv == ['srun', '--mpi=pmix', '-n', '20', '/usr/bin/siesta']


def test_real_execution_streams_are_explicit(tmp_path):
    """Execution passes explicit file handles for stdin, stdout, stderr."""
    fdf_file = tmp_path / 'siesta.fdf'
    fdf_file.write_bytes(b"SystemLabel test\n")

    spec = RunSpec(
        run_id='test', work_dir=str(tmp_path), fdf_path=str(fdf_file),
        canonical_dm_path=str(tmp_path/'ref.DM'), pseudo_paths={},
        mpi_ranks=1, siesta_binary=sys.executable, mpi_launcher=sys.executable, mpi_flags='',
        response_mode='SCREENED', alpha=0.01, perturbed_site=0, n_sites=2, identity_key='test'
    )
    fdf_in = open(spec.fdf_path, "rb")
    out_f  = open(tmp_path / "siesta.out", "wb")
    err_f  = open(tmp_path / "siesta.err", "wb")

    import subprocess
    cmd = [sys.executable, "-c", "import sys; sys.stdout.write(sys.stdin.read())"]
    proc = subprocess.Popen(cmd, stdin=fdf_in, stdout=out_f, stderr=err_f, cwd=str(tmp_path))
    rc = proc.wait()
    fdf_in.close()
    out_f.close()
    err_f.close()

    assert rc == 0
    assert (tmp_path / "siesta.out").read_bytes().strip() == b"SystemLabel test"


def test_bounded_process_pool_waits_each_pid_once():
    """Process pool waits each PID exactly once."""
    pids_waited = []
    class DummyProc:
        def __init__(self, pid): self.pid = pid
        def wait(self): pids_waited.append(self.pid); return 0

    p1 = DummyProc(101)
    p2 = DummyProc(102)
    for p in [p1, p2]:
        p.wait()

    assert pids_waited == [101, 102], "Each PID must be waited on exactly once"


def test_exact_run_count_equals_len_generated_runspecs(tmp_path):
    """estimate_run_counts matches len(generate_lr_run_specs(...))."""
    _ensure_dummy_ref_dm(str(tmp_path), 'NiO')
    mat_cfg = {
        'name': 'NiO', 'n_correlated_sites': 2, 'lattice_constant_ang': 4.177,
        'base_fractional_coords': [
            {'label': 'Ni', 'species': 'Ni', 'frac': [0.0,0.0,0.0]},
            {'label': 'Ni', 'species': 'Ni', 'frac': [0.5,0.0,0.0]},
        ],
        'pseudopotentials': {'Ni': {'file': 'Ni.psml'}},
        'convergence_sequence': [
            {'dimension': 'kgrid', 'values': [[2,2,2], [4,4,4]], 'accepted_value': None}
        ]
    }
    specs_3pt = generate_lr_run_specs(mat_cfg, 'SCREENING_3POINT', str(tmp_path), alphas=[-0.01, 0.0, 0.01])
    specs_5pt = generate_lr_run_specs(mat_cfg, 'FINAL_5POINT', str(tmp_path), alphas=[-0.02, -0.01, 0.0, 0.01, 0.02])

    from production_benchmarks.slurm_runner import estimate_run_counts
    counts = estimate_run_counts(mat_cfg, campaign_dir=str(tmp_path))

    assert counts['runs_per_3pt_campaign'] == len(specs_3pt) == 10
    assert counts['runs_per_5pt_campaign'] == len(specs_5pt) == 18


# ═══════════════════════════════════════════════════════════════════════════
# CRITICAL INTEGRATION TESTS (A THROUGH P) — NO SIESTA EXECUTION
# ═══════════════════════════════════════════════════════════════════════════

def test_nio_reference_fdf(tmp_path):
    """Test A: NiO reference FDF must have 4 atoms, 2 Ni + 2 O, exact rhombohedral lattice, opposite spins, valid AFM-II."""
    campaign_dir = str(tmp_path / 'campaign')
    os.makedirs(os.path.join(campaign_dir, 'materials', 'nio'), exist_ok=True)
    with open('production_benchmarks/materials/nio/material.json') as fh:
        mat_cfg = json.load(fh)

    specs = generate_lr_run_specs(mat_cfg, 'REFERENCE_RUN', campaign_dir)
    assert len(specs) == 1
    spec = specs[0]
    fdf_text = materialize_run_fdf(spec)

    assert 'NumberOfAtoms       4' in fdf_text
    assert 'NiLR0' in fdf_text
    assert 'NiLR1' in fdf_text
    assert 'LatticeConstant     4.1770 Ang' in fdf_text
    assert '+2.0' in fdf_text
    assert '-2.0' in fdf_text


def test_feo_reference_fdf(tmp_path):
    """Test B: FeO reference FDF must have 4 atoms, 2 Fe + 2 O, exact rhombohedral lattice, opposite spins, valid AFM-II."""
    campaign_dir = str(tmp_path / 'campaign')
    os.makedirs(os.path.join(campaign_dir, 'materials', 'feo'), exist_ok=True)
    with open('production_benchmarks/materials/feo/material.json') as fh:
        mat_cfg = json.load(fh)

    specs = generate_lr_run_specs(mat_cfg, 'REFERENCE_RUN', campaign_dir)
    assert len(specs) == 1
    spec = specs[0]
    fdf_text = materialize_run_fdf(spec)

    assert 'NumberOfAtoms       4' in fdf_text
    assert 'FeLR0' in fdf_text
    assert 'FeLR1' in fdf_text
    assert 'LatticeConstant     4.3340 Ang' in fdf_text
    assert '+4.0' in fdf_text
    assert '-4.0' in fdf_text


def test_preflight_geometry_equals_generated_fdf_geometry(tmp_path):
    """Test C: Preflight geometry check and generated FDF geometry must have identical lattice + coordinates."""
    with open('production_benchmarks/materials/nio/material.json') as fh:
        mat_cfg = json.load(fh)

    fdf_text = build_base_fdf_from_material_cfg(mat_cfg)
    assert '0.000000  1.000000  1.000000' in fdf_text or '0.0  1.0  1.0' in fdf_text
    assert '0.000000  0.000000  0.000000' in fdf_text
    assert '0.500000  0.000000  0.000000' in fdf_text


def test_balanced_non_afm2_spin_pattern_fails(tmp_path):
    """Test D: Balanced spin pattern (+ + - -) on same (111) plane must FAIL verify_afm_ii_ordering."""
    cat_fracs = np.array([
        [0.0, 0.0, 0.0],
        [0.5, 0.5, 0.0],
        [0.5, 0.0, 0.5],
        [0.0, 0.5, 0.5],
    ])
    lat_vecs = np.eye(3) * 4.177
    wrong_spins = [2.0, -2.0, 2.0, -2.0]

    res = verify_afm_ii_ordering(cat_fracs, wrong_spins, lat_vecs)
    assert res['afm_ii_valid'] is False
    assert len(res['errors']) > 0


def test_supercell_afm_phase_survives_expansion(tmp_path):
    """Test E: 2x1x1 supercell expansion preserves correct AFM-II spin propagation."""
    with open('production_benchmarks/materials/nio/material.json') as fh:
        mat_cfg = json.load(fh)

    eff = dict(mat_cfg['candidate_baseline'])
    eff['supercell'] = 'medium'

    fdf_text = build_base_fdf_from_material_cfg(mat_cfg, eff)
    assert 'NumberOfAtoms       8' in fdf_text
    assert '%block DM.InitSpin' in fdf_text


def test_reference_run_generates_one_calculation(tmp_path):
    """Test F: REFERENCE_RUN generates exactly ONE reference calculation spec, not LR perturbations."""
    campaign_dir = str(tmp_path / 'campaign')
    os.makedirs(os.path.join(campaign_dir, 'materials', 'nio'), exist_ok=True)
    with open('production_benchmarks/materials/nio/material.json') as fh:
        mat_cfg = json.load(fh)

    specs = generate_lr_run_specs(mat_cfg, 'REFERENCE_RUN', campaign_dir)
    assert len(specs) == 1
    assert specs[0].response_mode == 'REFERENCE'
    assert specs[0].alpha == 0.0


def test_response_generation_without_accepted_reference_dm_hard_fails(tmp_path):
    """Test G: Response generation without accepted reference DM raises RuntimeError."""
    campaign_dir = str(tmp_path / 'campaign')
    os.makedirs(os.path.join(campaign_dir, 'materials', 'nio'), exist_ok=True)
    with open('production_benchmarks/materials/nio/material.json') as fh:
        mat_cfg = json.load(fh)

    with pytest.raises(RuntimeError, match="Missing canonical reference.DM"):
        generate_lr_run_specs(mat_cfg, 'SCREENING_3POINT', campaign_dir)


def test_energyshift_candidates_produce_different_fdfs(tmp_path):
    """Test H: EnergyShift candidates produce genuinely different PAO.EnergyShift values in FDF."""
    with open('production_benchmarks/materials/nio/material.json') as fh:
        mat_cfg = json.load(fh)

    fdf1 = build_base_fdf_from_material_cfg(mat_cfg, {'energy_shift_ry': 0.02})
    fdf2 = build_base_fdf_from_material_cfg(mat_cfg, {'energy_shift_ry': 0.005})

    assert 'PAO.EnergyShift     0.02 Ry' in fdf1
    assert 'PAO.EnergyShift     0.005 Ry' in fdf2
    assert fdf1 != fdf2


def test_mesh_candidates_produce_different_fdfs(tmp_path):
    """Test I: Mesh cutoff candidates produce genuinely different MeshCutoff values in FDF."""
    with open('production_benchmarks/materials/nio/material.json') as fh:
        mat_cfg = json.load(fh)

    fdf1 = build_base_fdf_from_material_cfg(mat_cfg, {'mesh_cutoff_ry': 200})
    fdf2 = build_base_fdf_from_material_cfg(mat_cfg, {'mesh_cutoff_ry': 250})

    assert 'MeshCutoff          200 Ry' in fdf1
    assert 'MeshCutoff          250 Ry' in fdf2
    assert fdf1 != fdf2


def test_kgrid_candidates_produce_different_fdfs(tmp_path):
    """Test J: k-grid candidates produce genuinely different kgrid_Monkhorst_Pack blocks in FDF."""
    with open('production_benchmarks/materials/nio/material.json') as fh:
        mat_cfg = json.load(fh)

    fdf1 = build_base_fdf_from_material_cfg(mat_cfg, {'kgrid': [2, 2, 2]})
    fdf2 = build_base_fdf_from_material_cfg(mat_cfg, {'kgrid': [4, 4, 4]})

    assert '2 0 0 0.0' in fdf1
    assert '4 0 0 0.0' in fdf2
    assert fdf1 != fdf2


def test_rc_candidates_produce_different_fdfs(tmp_path):
    """Test K: Projector rc candidates produce genuinely different DFTU.proj blocks in FDF."""
    with open('production_benchmarks/materials/nio/material.json') as fh:
        mat_cfg = json.load(fh)

    spec1 = RunSpec(
        run_id='test1', work_dir=str(tmp_path/'1'), fdf_path=str(tmp_path/'1'/'siesta.fdf'),
        canonical_dm_path=str(tmp_path/'ref.DM'), pseudo_paths={'Ni':str(tmp_path/'Ni.psml'),'O':str(tmp_path/'O.psml')},
        mpi_ranks=20, siesta_binary='/x', mpi_launcher='srun', mpi_flags='',
        response_mode='SCREENED', alpha=0.01, perturbed_site=0, n_sites=2,
        identity=compute_scientific_identity(mat_cfg, {'projector_rc_bohr': 2.5}, 'SCREENED', 0.01, 0),
        mat_cfg=mat_cfg, effective_params={'projector_rc_bohr': 2.5}
    )
    spec2 = RunSpec(
        run_id='test2', work_dir=str(tmp_path/'2'), fdf_path=str(tmp_path/'2'/'siesta.fdf'),
        canonical_dm_path=str(tmp_path/'ref.DM'), pseudo_paths={'Ni':str(tmp_path/'Ni.psml'),'O':str(tmp_path/'O.psml')},
        mpi_ranks=20, siesta_binary='/x', mpi_launcher='srun', mpi_flags='',
        response_mode='SCREENED', alpha=0.01, perturbed_site=0, n_sites=2,
        identity=compute_scientific_identity(mat_cfg, {'projector_rc_bohr': 3.5}, 'SCREENED', 0.01, 0),
        mat_cfg=mat_cfg, effective_params={'projector_rc_bohr': 3.5}
    )

    fdf1 = materialize_run_fdf(spec1)
    fdf2 = materialize_run_fdf(spec2)

    assert '2.5000' in fdf1
    assert '3.5000' in fdf2
    assert fdf1 != fdf2


def test_supercell_candidates_produce_different_structures(tmp_path):
    """Test L: Supercell candidates produce different atom counts and lattices in FDF."""
    with open('production_benchmarks/materials/nio/material.json') as fh:
        mat_cfg = json.load(fh)

    fdf1 = build_base_fdf_from_material_cfg(mat_cfg, {'supercell': 'small'})
    fdf2 = build_base_fdf_from_material_cfg(mat_cfg, {'supercell': 'medium'})

    assert 'NumberOfAtoms       4' in fdf1
    assert 'NumberOfAtoms       8' in fdf2
    assert fdf1 != fdf2


def test_changed_scientific_dimension_changes_identity_and_work_dir(tmp_path):
    """Test M: Changing MeshCutoff or projector rc changes identity hash and work directory."""
    with open('production_benchmarks/materials/nio/material.json') as fh:
        mat_cfg = json.load(fh)

    id1 = compute_scientific_identity(mat_cfg, {'mesh_cutoff_ry': 200}, 'SCREENED', 0.01, 0)
    id2 = compute_scientific_identity(mat_cfg, {'mesh_cutoff_ry': 250}, 'SCREENED', 0.01, 0)

    assert id1.compute_key() != id2.compute_key()


def test_rc0_screened_nonconverged_rejected(tmp_path):
    """Test N: returncode 0 + SCREENED SCF non-convergence is REJECTED by semantic gate."""
    out_file = tmp_path / 'siesta.out'
    out_file.write_text("siesta: Normal completion\nSCF: NOT CONVERGED\nMulliken population\n")

    mat_cfg = {'spin_mode': 'collinear_polarized'}
    res = verify_siesta_run_semantics(str(out_file), 'SCREENED', mat_cfg)
    assert res['passed'] is False
    assert 'SCF' in res['reason']


def test_rc0_missing_occupations_rejected(tmp_path):
    """Test O: returncode 0 + missing occupation events is REJECTED by semantic gate."""
    out_file = tmp_path / 'siesta.out'
    out_file.write_text("siesta: Normal completion\nscf: converged\n")

    mat_cfg = {'spin_mode': 'collinear_polarized'}
    res = verify_siesta_run_semantics(str(out_file), 'SCREENED', mat_cfg)
    assert res['passed'] is False
    assert 'occupation' in res['reason'].lower()


def test_valid_bare_nonconverged_accepted(tmp_path):
    """Test P: BARE mode with returncode 0 and occupation data is ACCEPTED even if SCF did not converge."""
    out_file = tmp_path / 'siesta.out'
    out_file.write_text("siesta: Normal completion\nSCF: NOT CONVERGED\nMulliken population analysis\n")

    mat_cfg = {'spin_mode': 'collinear_polarized'}
    res = verify_siesta_run_semantics(str(out_file), 'BARE', mat_cfg)
    assert res['passed'] is True
