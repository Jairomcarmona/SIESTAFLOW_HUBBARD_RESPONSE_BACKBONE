"""
Unit tests for the Scientific Convergence Campaign Engine (convergence_engine.py).

Tests cover:
  - single-parameter scan generation
  - configuration identity (deterministic SHA-256)
  - physical identity hash and reuse validation
  - incompatible reuse rejection (changing cutoff, supercell, projector, basis, kgrid)
  - comparison of two known U matrices (absolute and relative differences)
  - supercell identity
  - projector identity
  - alpha-window identity
  - arbitrary-N compatibility (N=3 test)
"""

import pytest
import numpy as np

from siestaflow_hubbard.domain.convergence_engine import (
    LRScientificConfiguration,
    ConvergenceResult,
    ConvergenceComparison,
    generate_single_dimension_scan,
    can_reuse_calculations,
    compare_convergence_results,
    build_convergence_result_from_observations,
)
from siestaflow_hubbard.domain.matrix_lr import ResponseObservation


# ─────────────────────────────────────────────
# FIXTURES
# ─────────────────────────────────────────────

@pytest.fixture
def base_config_2site():
    return LRScientificConfiguration(
        system_label="MnO_2x1x1",
        structure_summary={"lattice_constant": 4.445, "n_atoms": 4},
        correlated_sites=[0, 1],
        species_labels=["MnLR0", "MnLR1"],
        pseudopotentials={"MnLR0": "Mn.psml", "MnLR1": "Mn.psml", "O": "O.psml"},
        basis_size="SZ",
        mesh_cutoff_ry=150.0,
        kgrid=(1, 1, 1),
        supercell=(2, 1, 1),
        projector_rc=3.0,
        projector_omega=0.05,
        alpha_grid=[-0.02, -0.01, 0.00, 0.01, 0.02],
        spin_configuration="polarized",
    )


# ─────────────────────────────────────────────
# CONFIGURATION IDENTITY & REUSE TESTS
# ─────────────────────────────────────────────

def test_configuration_id_deterministic(base_config_2site):
    """Identical configurations must produce identical configuration_id."""
    id1 = base_config_2site.configuration_id()
    id2 = base_config_2site.configuration_id()
    assert id1 == id2
    assert len(id1) == 16


def test_physical_identity_hash_excludes_alpha_grid(base_config_2site):
    """Changing alpha_grid must NOT change physical_identity_hash (permitting ref/alpha=0 reuse)."""
    cfg1 = base_config_2site
    cfg2 = LRScientificConfiguration(
        system_label="MnO_2x1x1",
        structure_summary={"lattice_constant": 4.445, "n_atoms": 4},
        correlated_sites=[0, 1],
        species_labels=["MnLR0", "MnLR1"],
        pseudopotentials={"MnLR0": "Mn.psml", "MnLR1": "Mn.psml", "O": "O.psml"},
        basis_size="SZ",
        mesh_cutoff_ry=150.0,
        kgrid=(1, 1, 1),
        supercell=(2, 1, 1),
        projector_rc=3.0,
        projector_omega=0.05,
        alpha_grid=[-0.01, 0.00, 0.01],  # different alpha grid
        spin_configuration="polarized",
    )

    assert cfg1.physical_identity_hash() == cfg2.physical_identity_hash()
    assert can_reuse_calculations(cfg1, cfg2) is True
    # But configuration_id must differ
    assert cfg1.configuration_id() != cfg2.configuration_id()


def test_incompatible_reuse_rejection_mesh_cutoff(base_config_2site):
    """Changing MeshCutoff must reject computational reuse."""
    cfg1 = base_config_2site
    cfg2 = LRScientificConfiguration(
        **{**base_config_2site.__dict__, "mesh_cutoff_ry": 200.0}
    )
    assert can_reuse_calculations(cfg1, cfg2) is False


def test_incompatible_reuse_rejection_supercell(base_config_2site):
    """Changing supercell must reject computational reuse."""
    cfg1 = base_config_2site
    cfg2 = LRScientificConfiguration(
        **{**base_config_2site.__dict__, "supercell": (2, 2, 1)}
    )
    assert can_reuse_calculations(cfg1, cfg2) is False


def test_incompatible_reuse_rejection_projector_rc(base_config_2site):
    """Changing projector rc must reject computational reuse."""
    cfg1 = base_config_2site
    cfg2 = LRScientificConfiguration(
        **{**base_config_2site.__dict__, "projector_rc": 3.5}
    )
    assert can_reuse_calculations(cfg1, cfg2) is False


def test_incompatible_reuse_rejection_kgrid(base_config_2site):
    """Changing kgrid must reject computational reuse."""
    cfg1 = base_config_2site
    cfg2 = LRScientificConfiguration(
        **{**base_config_2site.__dict__, "kgrid": (2, 2, 2)}
    )
    assert can_reuse_calculations(cfg1, cfg2) is False


def test_incompatible_reuse_rejection_basis(base_config_2site):
    """Changing basis size must reject computational reuse."""
    cfg1 = base_config_2site
    cfg2 = LRScientificConfiguration(
        **{**base_config_2site.__dict__, "basis_size": "DZP"}
    )
    assert can_reuse_calculations(cfg1, cfg2) is False


# ─────────────────────────────────────────────
# SCAN GENERATION TESTS
# ─────────────────────────────────────────────

def test_generate_single_dimension_scan_mesh_cutoff(base_config_2site):
    """Single-dimension scan over mesh_cutoff_ry must vary ONLY mesh_cutoff_ry."""
    cutoffs = [150.0, 200.0, 250.0, 300.0]
    configs = generate_single_dimension_scan(base_config_2site, "mesh_cutoff_ry", cutoffs)

    assert len(configs) == 4
    for i, cfg in enumerate(configs):
        assert cfg.mesh_cutoff_ry == cutoffs[i]
        # All other fields unchanged
        assert cfg.basis_size == base_config_2site.basis_size
        assert cfg.kgrid == base_config_2site.kgrid
        assert cfg.supercell == base_config_2site.supercell


def test_generate_single_dimension_scan_unsupported_param_raises(base_config_2site):
    """Unsupported parameter name must raise ValueError."""
    with pytest.raises(ValueError, match="Unsupported scan parameter"):
        generate_single_dimension_scan(base_config_2site, "invalid_param", [1, 2])


# ─────────────────────────────────────────────
# COMPARISON ENGINE TESTS
# ─────────────────────────────────────────────

def _make_dummy_result(config, U_diag_val, chi0_val, chi_val):
    N = config.n_sites()
    chi0_raw = np.eye(N) * chi0_val
    chi_raw = np.eye(N) * chi_val
    U_matrix = np.eye(N) * U_diag_val
    diag_U = [U_diag_val] * N
    off_diag = {}
    mode_diags = {"uniform_mode": {"U": U_diag_val}}
    return ConvergenceResult(
        config=config,
        config_id=config.configuration_id(),
        chi0_raw=chi0_raw,
        chi_raw=chi_raw,
        U_matrix=U_matrix,
        diagonal_U=diag_U,
        off_diagonal_kernel=off_diag,
        eigenmode_diagnostics=mode_diags,
        rank_chi0=N,
        rank_chi=N,
        cond_chi0=1.0,
        cond_chi=1.0,
        scf_cost_siesta_runs=10,
        scientific_status="DIAGNOSTICS_ONLY",
    )


def test_compare_convergence_results_abs_and_rel_diff(base_config_2site):
    """Comparison of two known results must calculate correct absolute and relative differences."""
    cfg1 = base_config_2site
    cfg2 = LRScientificConfiguration(
        **{**base_config_2site.__dict__, "mesh_cutoff_ry": 200.0}
    )

    res1 = _make_dummy_result(cfg1, U_diag_val=10.0, chi0_val=-0.20, chi_val=-0.05)
    res2 = _make_dummy_result(cfg2, U_diag_val=11.0, chi0_val=-0.18, chi_val=-0.04)

    cmp = compare_convergence_results(res1, res2, param_name="mesh_cutoff_ry")

    assert cmp.param_varied == "mesh_cutoff_ry"
    assert cmp.val_a == 150.0
    assert cmp.val_b == 200.0

    # Frobenius norm diff of U_matrix: ||diag(11) - diag(10)||_F = sqrt(1^2 + 1^2) = sqrt(2) ≈ 1.4142
    assert abs(cmp.abs_diff_U - np.sqrt(2.0)) < 1e-6
    # Relative diff: sqrt(2) / sqrt(10^2 + 10^2) = sqrt(2) / (10 * sqrt(2)) = 0.10 (10%)
    assert abs(cmp.rel_diff_U - 0.10) < 1e-6

    # Per-site diagonal diffs
    assert len(cmp.diagonal_U_abs_diffs) == 2
    assert abs(cmp.diagonal_U_abs_diffs[0] - 1.0) < 1e-6
    assert abs(cmp.diagonal_U_rel_diffs[0] - 0.10) < 1e-6


# ─────────────────────────────────────────────
# ARBITRARY N COMPATIBILITY TEST
# ─────────────────────────────────────────────

def test_arbitrary_n_compatibility_3site():
    """Convergence engine must work seamlessly for N=3 correlated sites."""
    cfg_3site = LRScientificConfiguration(
        system_label="TriSite_Material",
        structure_summary={"n_atoms": 6},
        correlated_sites=[0, 1, 2],
        species_labels=["M0", "M1", "M2"],
        pseudopotentials={"M0": "M.psml", "M1": "M.psml", "M2": "M.psml", "O": "O.psml"},
        basis_size="SZ",
        mesh_cutoff_ry=150.0,
        kgrid=(1, 1, 1),
        supercell=(1, 1, 1),
        projector_rc=3.0,
        projector_omega=0.05,
        alpha_grid=[-0.02, -0.01, 0.00, 0.01, 0.02],
        spin_configuration="polarized",
    )

    assert cfg_3site.n_sites() == 3

    # Build synthetic observations for N=3
    N = 3
    chi0_true = np.eye(N) * (-0.5)
    chi_true = np.eye(N) * (-0.1)
    n_ref = [5.0, 5.0, 5.0]

    obs = []
    for J in range(N):
        for alpha in [-0.02, -0.01, 0.00, 0.01, 0.02]:
            occ_bare = [n_ref[i] + chi0_true[i, J] * alpha for i in range(N)]
            occ_scrn = [n_ref[i] + chi_true[i, J] * alpha for i in range(N)]
            obs.append(ResponseObservation(
                perturbation_site=J,
                alpha=alpha,
                site_labels=[0, 1, 2],
                occupations_ref=n_ref,
                occupations_bare=occ_bare,
                occupations_screened=occ_scrn,
            ))

    res = build_convergence_result_from_observations(cfg_3site, obs, scf_cost=30)

    assert res.rank_chi0 == 3
    assert res.rank_chi == 3
    assert res.U_matrix is not None
    assert res.U_matrix.shape == (3, 3)
    assert len(res.diagonal_U) == 3
    # Diagonal U = 1/(-0.5) - 1/(-0.1) = -2 + 10 = 8.0 eV
    assert abs(res.diagonal_U[0] - 8.0) < 1e-6
    assert abs(res.diagonal_U[1] - 8.0) < 1e-6
    assert abs(res.diagonal_U[2] - 8.0) < 1e-6
