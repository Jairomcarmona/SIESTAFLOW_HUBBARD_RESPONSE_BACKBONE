"""
convergence_engine.py – Scientific Convergence Campaign Engine for NxN Hubbard response.

Manages convergence studies (MeshCutoff, k-grid, basis, supercell, projector rc/omega, alpha-window)
over arbitrary materials and arbitrary N correlated sites.

Design principles:
  - Reusable, material-agnostic configuration and result data structures.
  - Strict physical reuse validation: calculations are reused ONLY if physical parameters match.
  - Single-dimension scan generation to prevent Cartesian explosion.
  - Quantitative comparative diagnostics (absolute and relative differences) without hardcoded pass/fail gates.
  - Default status: DIAGNOSTICS_ONLY.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional, Sequence, Any
import hashlib
import json
import numpy as np

from .matrix_lr import MatrixResponseResult, ResponseObservation, analyze_matrix_response_campaign


# ─────────────────────────────────────────────
# SCIENTIFIC CONFIGURATION
# ─────────────────────────────────────────────

@dataclass
class LRScientificConfiguration:
    """
    Complete scientific specification for a Linear Response campaign.

    Supports arbitrary N correlated sites and arbitrary materials.
    Unit semantics for DFTU.proj method-2 are explicitly declared in Bohr.
    """
    system_label: str
    structure_summary: dict                 # e.g. {"lattice_constant": 4.445, "atoms": 4}
    correlated_sites: list[int]             # e.g. [0, 1]
    species_labels: list[str]               # e.g. ["MnLR0", "MnLR1"]
    pseudopotentials: dict[str, str]        # e.g. {"MnLR0": "Mn.psml", ...}
    basis_size: str                         # e.g. "SZ", "DZP"
    mesh_cutoff_ry: float                   # e.g. 150.0, 200.0
    kgrid: tuple[int, int, int]             # e.g. (1, 1, 1)
    supercell: tuple[int, int, int]         # e.g. (2, 1, 1)
    projector_n: int = 3
    projector_l: int = 2
    projector_rc_bohr: float = 3.0          # SIESTA Method-2 unit: Bohr
    projector_omega_bohr: float = 0.05      # SIESTA Method-2 unit: Bohr
    projector_units: str = "Bohr"
    pao_energy_shift_ry: float = 0.02       # Ry
    pao_split_norm: float = 0.15
    pao_basis_type: str = "split"
    alpha_grid: list[float] = field(default_factory=lambda: [-0.02, -0.01, 0.00, 0.01, 0.02])
    spin_configuration: str = "polarized"

    @property
    def projector_rc(self) -> float:
        """Backward-compatibility property returning projector_rc_bohr."""
        return self.projector_rc_bohr

    @property
    def projector_omega(self) -> float:
        """Backward-compatibility property returning projector_omega_bohr."""
        return self.projector_omega_bohr

    def n_sites(self) -> int:
        return len(self.correlated_sites)

    def configuration_id(self) -> str:
        """
        Deterministic identity hash of the complete scientific configuration.
        """
        payload = {
            "system_label": self.system_label,
            "structure_summary": self.structure_summary,
            "correlated_sites": self.correlated_sites,
            "species_labels": self.species_labels,
            "basis_size": self.basis_size,
            "mesh_cutoff_ry": float(self.mesh_cutoff_ry),
            "kgrid": list(self.kgrid),
            "supercell": list(self.supercell),
            "projector_n": self.projector_n,
            "projector_l": self.projector_l,
            "projector_rc_bohr": float(self.projector_rc_bohr),
            "projector_omega_bohr": float(self.projector_omega_bohr),
            "projector_units": self.projector_units,
            "pao_energy_shift_ry": float(self.pao_energy_shift_ry),
            "pao_split_norm": float(self.pao_split_norm),
            "pao_basis_type": self.pao_basis_type,
            "alpha_grid": [float(a) for a in self.alpha_grid],
            "spin_configuration": self.spin_configuration,
        }
        json_str = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(json_str.encode("utf-8")).hexdigest()[:16]

    def physical_identity_hash(self) -> str:
        """
        Hash of physical/numerical parameters excluding alpha_grid.
        Configurations with identical physical_identity_hash can reuse reference/alpha=0 runs.
        """
        payload = {
            "system_label": self.system_label,
            "structure_summary": self.structure_summary,
            "correlated_sites": self.correlated_sites,
            "species_labels": self.species_labels,
            "basis_size": self.basis_size,
            "mesh_cutoff_ry": float(self.mesh_cutoff_ry),
            "kgrid": list(self.kgrid),
            "supercell": list(self.supercell),
            "projector_n": self.projector_n,
            "projector_l": self.projector_l,
            "projector_rc_bohr": float(self.projector_rc_bohr),
            "projector_omega_bohr": float(self.projector_omega_bohr),
            "projector_units": self.projector_units,
            "pao_energy_shift_ry": float(self.pao_energy_shift_ry),
            "pao_split_norm": float(self.pao_split_norm),
            "pao_basis_type": self.pao_basis_type,
            "spin_configuration": self.spin_configuration,
        }
        json_str = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(json_str.encode("utf-8")).hexdigest()[:16]

    def can_reuse_reference_with(self, other: LRScientificConfiguration) -> bool:
        """
        Returns True if `other` shares the exact same physical configuration,
        allowing reuse of the reference and alpha=0 calculations.
        """
        return self.physical_identity_hash() == other.physical_identity_hash()


# ─────────────────────────────────────────────
# CONVERGENCE RESULT
# ─────────────────────────────────────────────

@dataclass
class ConvergenceResult:
    """
    Scientific output for a single configuration in a convergence campaign.
    """
    config: LRScientificConfiguration
    config_id: str

    # Raw response matrices (N x N)
    chi0_raw: np.ndarray
    chi_raw: np.ndarray

    # Interaction matrix (N x N), None if rank deficient
    U_matrix: Optional[np.ndarray]

    # Diagnostics
    diagonal_U: list[float]                          # U_00, U_11, ...
    off_diagonal_kernel: dict[tuple[int, int], float]  # (I, J) -> U_IJ
    eigenmode_diagnostics: dict[str, dict]            # uniform, staggered, etc.

    # Matrix condition
    rank_chi0: int
    rank_chi: int
    cond_chi0: float
    cond_chi: float

    # Computational cost
    scf_cost_siesta_runs: int
    scientific_status: str = "DIAGNOSTICS_ONLY"


# ─────────────────────────────────────────────
# CONVERGENCE COMPARISON
# ─────────────────────────────────────────────

@dataclass
class ConvergenceComparison:
    """
    Quantitative comparison between two convergence results (A vs B).
    Reports absolute and relative differences for all key quantities.
    """
    config_a_id: str
    config_b_id: str
    param_varied: str
    val_a: Any
    val_b: Any

    # Frobenius norm differences
    abs_diff_chi0: float
    rel_diff_chi0: float
    abs_diff_chi: float
    rel_diff_chi: float

    abs_diff_U: float
    rel_diff_U: float

    # Per-site diagonal U differences
    diagonal_U_abs_diffs: list[float]
    diagonal_U_rel_diffs: list[float]

    # Off-diagonal kernel differences
    off_diagonal_abs_diffs: dict[tuple[int, int], float]

    # Mode differences
    mode_abs_diffs: dict[str, float]

    status: str = "COMPARISON_COMPUTED"


# ─────────────────────────────────────────────
# CAMPAIGN ENGINE FUNCTIONS
# ─────────────────────────────────────────────

def generate_single_dimension_scan(
    base_config: LRScientificConfiguration,
    param_name: str,
    param_values: list[Any],
) -> list[LRScientificConfiguration]:
    """
    Generate a list of configurations varying ONLY `param_name`.
    Prevents Cartesian parameter explosions.

    Supported parameters:
      - 'mesh_cutoff_ry'
      - 'kgrid'
      - 'basis_size'
      - 'supercell'
      - 'projector_rc'
      - 'projector_omega'
      - 'alpha_grid'
    """
    valid_params = {
        "mesh_cutoff_ry", "kgrid", "basis_size", "supercell",
        "projector_rc", "projector_omega", "projector_rc_bohr", "projector_omega_bohr",
        "pao_energy_shift_ry", "pao_split_norm", "pao_basis_type", "alpha_grid"
    }
    if param_name not in valid_params:
        raise ValueError(
            f"Unsupported scan parameter '{param_name}'. Valid options: {sorted(valid_params)}"
        )

    configs = []
    for val in param_values:
        d = asdict(base_config)
        d[param_name] = val
        configs.append(LRScientificConfiguration(**d))

    return configs


def can_reuse_calculations(
    config_a: LRScientificConfiguration,
    config_b: LRScientificConfiguration,
) -> bool:
    """
    Strict validation of computational reuse:
    Reference and alpha=0 calculations can be reused if and only if
    physical parameters match exactly.
    """
    return config_a.can_reuse_reference_with(config_b)


def compare_convergence_results(
    res_a: ConvergenceResult,
    res_b: ConvergenceResult,
    param_name: str = "",
) -> ConvergenceComparison:
    """
    Quantitatively compare two ConvergenceResults (A vs B).
    Computes absolute and relative differences without hardcoding pass/fail gates.
    """
    val_a = getattr(res_a.config, param_name, None) if param_name else None
    val_b = getattr(res_b.config, param_name, None) if param_name else None

    # Chi0 difference
    diff_chi0 = res_b.chi0_raw - res_a.chi0_raw
    abs_diff_chi0 = float(np.linalg.norm(diff_chi0, "fro"))
    norm_a_chi0 = float(np.linalg.norm(res_a.chi0_raw, "fro"))
    rel_diff_chi0 = abs_diff_chi0 / norm_a_chi0 if norm_a_chi0 > 1e-12 else float("nan")

    # Chi difference
    diff_chi = res_b.chi_raw - res_a.chi_raw
    abs_diff_chi = float(np.linalg.norm(diff_chi, "fro"))
    norm_a_chi = float(np.linalg.norm(res_a.chi_raw, "fro"))
    rel_diff_chi = abs_diff_chi / norm_a_chi if norm_a_chi > 1e-12 else float("nan")

    # U matrix difference (if both present)
    if res_a.U_matrix is not None and res_b.U_matrix is not None:
        diff_U = res_b.U_matrix - res_a.U_matrix
        abs_diff_U = float(np.linalg.norm(diff_U, "fro"))
        norm_a_U = float(np.linalg.norm(res_a.U_matrix, "fro"))
        rel_diff_U = abs_diff_U / norm_a_U if norm_a_U > 1e-12 else float("nan")

        diag_abs = [
            abs(res_b.diagonal_U[i] - res_a.diagonal_U[i])
            for i in range(len(res_a.diagonal_U))
        ]
        diag_rel = [
            abs(res_b.diagonal_U[i] - res_a.diagonal_U[i]) / (abs(res_a.diagonal_U[i]) + 1e-12)
            for i in range(len(res_a.diagonal_U))
        ]

        off_abs = {}
        for pair in res_a.off_diagonal_kernel:
            if pair in res_b.off_diagonal_kernel:
                off_abs[pair] = abs(
                    res_b.off_diagonal_kernel[pair] - res_a.off_diagonal_kernel[pair]
                )
    else:
        abs_diff_U = float("nan")
        rel_diff_U = float("nan")
        diag_abs = []
        diag_rel = []
        off_abs = {}

    # Mode differences
    mode_abs = {}
    for m in res_a.eigenmode_diagnostics:
        if m in res_b.eigenmode_diagnostics:
            u_a = res_a.eigenmode_diagnostics[m].get("U", float("nan"))
            u_b = res_b.eigenmode_diagnostics[m].get("U", float("nan"))
            if not np.isnan(u_a) and not np.isnan(u_b):
                mode_abs[m] = abs(u_b - u_a)

    return ConvergenceComparison(
        config_a_id=res_a.config_id,
        config_b_id=res_b.config_id,
        param_varied=param_name,
        val_a=val_a,
        val_b=val_b,
        abs_diff_chi0=abs_diff_chi0,
        rel_diff_chi0=rel_diff_chi0,
        abs_diff_chi=abs_diff_chi,
        rel_diff_chi=rel_diff_chi,
        abs_diff_U=abs_diff_U,
        rel_diff_U=rel_diff_U,
        diagonal_U_abs_diffs=diag_abs,
        diagonal_U_rel_diffs=diag_rel,
        off_diagonal_abs_diffs=off_abs,
        mode_abs_diffs=mode_abs,
    )


def build_convergence_result_from_observations(
    config: LRScientificConfiguration,
    observations: list[ResponseObservation],
    scf_cost: int,
) -> ConvergenceResult:
    """
    Pass raw ResponseObservation list into the production NxN matrix engine
    and construct a ConvergenceResult.
    """
    matrix_res: MatrixResponseResult = analyze_matrix_response_campaign(observations)
    N = config.n_sites()

    chi0 = matrix_res.chi0_raw
    chi = matrix_res.chi_raw
    U_mat = matrix_res.U_matrix

    diag_U = [U_mat[i, i] for i in range(N)] if U_mat is not None else [float("nan")] * N

    off_diag = {}
    if U_mat is not None:
        for i in range(N):
            for j in range(N):
                if i != j:
                    off_diag[(i, j)] = float(U_mat[i, j])

    # Eigenmode diagnostics
    mode_diags = {}
    if N == 2:
        v_u = np.array([1.0, 1.0]) / np.sqrt(2.0)
        v_s = np.array([1.0, -1.0]) / np.sqrt(2.0)

        c0_u = float(v_u.T @ chi0 @ v_u)
        c_u = float(v_u.T @ chi @ v_u)
        u_u = float(v_u.T @ U_mat @ v_u) if U_mat is not None else float("nan")

        c0_s = float(v_s.T @ chi0 @ v_s)
        c_s = float(v_s.T @ chi @ v_s)
        u_s = float(v_s.T @ U_mat @ v_s) if U_mat is not None else float("nan")

        mode_diags["uniform_mode"] = {"chi0": c0_u, "chi": c_u, "U": u_u}
        mode_diags["staggered_mode"] = {"chi0": c0_s, "chi": c_s, "U": u_s}

    return ConvergenceResult(
        config=config,
        config_id=config.configuration_id(),
        chi0_raw=chi0,
        chi_raw=chi,
        U_matrix=U_mat,
        diagonal_U=diag_U,
        off_diagonal_kernel=off_diag,
        eigenmode_diagnostics=mode_diags,
        rank_chi0=matrix_res.condition_chi0.rank,
        rank_chi=matrix_res.condition_chi.rank,
        cond_chi0=matrix_res.condition_chi0.condition_number,
        cond_chi=matrix_res.condition_chi.condition_number,
        scf_cost_siesta_runs=scf_cost,
        scientific_status="DIAGNOSTICS_ONLY",
    )
