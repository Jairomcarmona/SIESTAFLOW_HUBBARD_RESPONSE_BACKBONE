"""
matrix_lr.py – N×N Hubbard linear-response engine.

Generalizes the validated scalar pipeline to arbitrary N correlated sites.

Convention (explicit everywhere):
    row I    = observed site
    column J = perturbed site

    chi0_IJ = ∂n_I^(0)/∂alpha_J   (BARE response)
    chi_IJ  = ∂n_I    /∂alpha_J   (SCREENED response)

    U_matrix = inv(chi0) - inv(chi)

No hardcoded site count, geometry, or species.
No hardcoded scientific thresholds.
No silent pinv/lstsq/regularization.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional, Sequence
import numpy as np

from .scalar_lr import fit_response, select_inner_alpha_window, LinearFit


# ─────────────────────────────────────────────
# DATA STRUCTURES
# ─────────────────────────────────────────────

@dataclass
class ResponseObservation:
    """
    One perturbation step in the N-site response campaign.

    perturbation_site : int
        Zero-based index J of the site receiving alpha.
    alpha : float
        Perturbation strength applied to site J (eV).
    site_labels : list[int]
        Ordered list of site indices I = 0..N-1.
        Site identity is never inferred from position alone.
    occupations_ref : list[float]
        n_I^ref at SCF iteration 1, length N.
    occupations_bare : list[float]
        n_I^(0)(alpha_J): BARE (frozen-DM) occupations, length N.
    occupations_screened : list[float]
        n_I(alpha_J): SCREENED (converged) occupations, length N.
    # provenance
    parent_dm_sha256 : str
    projector_fingerprints : dict[int, str]
        Maps site index → projector fingerprint hash.
    bare_fdf_sha256 : str
    bare_out_sha256 : str
    screened_fdf_sha256 : str
    screened_out_sha256 : str
    """
    perturbation_site: int
    alpha: float
    site_labels: list[int]
    occupations_ref: list[float]
    occupations_bare: list[float]
    occupations_screened: list[float]
    parent_dm_sha256: str = ""
    projector_fingerprints: dict = field(default_factory=dict)
    bare_fdf_sha256: str = ""
    bare_out_sha256: str = ""
    screened_fdf_sha256: str = ""
    screened_out_sha256: str = ""

    def n_sites(self) -> int:
        return len(self.site_labels)


@dataclass(frozen=True)
class ResponseFitPolicy:
    """Declared response-curve estimator used to build chi0 and chi.

    ``linear`` preserves the historical OLS estimator. ``polynomial`` fits a
    polynomial in the supplied alpha interval and takes its analytic
    derivative at alpha=0. Polynomial degree is capped at three; the fit must
    retain at least ``minimum_residual_dof`` residual degrees of freedom.
    An optional symmetric alpha window lets a caller use a window already
    admitted by an independent alpha-linearity policy.
    """

    method: Literal["linear", "polynomial"] = "linear"
    polynomial_degree: int = 3
    minimum_residual_dof: int = 1
    alpha_window_ev: Optional[float] = None

    def validate(self) -> None:
        if self.method not in {"linear", "polynomial"}:
            raise ValueError("response fit method must be 'linear' or 'polynomial'")
        if (isinstance(self.polynomial_degree, bool)
                or not isinstance(self.polynomial_degree, int)
                or not 1 <= self.polynomial_degree <= 3):
            raise ValueError("polynomial_degree must be an integer from 1 through 3")
        if (isinstance(self.minimum_residual_dof, bool)
                or not isinstance(self.minimum_residual_dof, int)
                or self.minimum_residual_dof < 1):
            raise ValueError("minimum_residual_dof must be a positive integer")
        if self.alpha_window_ev is not None and (
            not np.isfinite(self.alpha_window_ev) or self.alpha_window_ev <= 0.0
        ):
            raise ValueError("alpha_window_ev must be positive and finite")


@dataclass
class PolynomialFit:
    """Polynomial response fit and derivative at zero."""

    slope: float
    intercept: float
    degree: int
    coefficients: list[float]
    r_squared: float
    residuals: list[float] = field(default_factory=list)
    max_abs_residual: float = 0.0
    residual_rms: float = 0.0
    n_points: int = 0
    residual_dof: int = 0
    design_condition_number: float = 0.0


@dataclass
class ElementDiagnostics:
    """Scalar linearity diagnostics for one (I, J) matrix element."""
    obs_site: int          # I
    pert_site: int         # J
    mode: str              # 'bare' or 'screened'
    fit_full: LinearFit | PolynomialFit
    fit_full_linear: LinearFit
    fit_inner: LinearFit


@dataclass
class MatrixConditionReport:
    """Condition diagnostics for one response matrix."""
    shape: tuple
    rank: int
    is_full_rank: bool
    det: float
    singular_values: list[float]
    condition_number: float
    matrix_status: str     # 'FULL_RANK' | 'RANK_DEFICIENT'


@dataclass
class InversionReport:
    """Result of inverting a response matrix."""
    inverse: np.ndarray
    left_residual: float    # ||M_inv @ M - I||_F
    right_residual: float   # ||M @ M_inv - I||_F
    method: str             # always 'direct_inv'


@dataclass
class MatrixResponseResult:
    """Complete N×N linear-response result."""
    site_labels: list[int]
    n_sites: int

    # Raw matrices (row=observed, col=perturbed)
    chi0_raw: np.ndarray
    chi_raw: np.ndarray

    # Symmetry diagnostics
    chi0_asymmetry_norm: float       # ||chi0_raw - chi0_raw.T||_F
    chi_asymmetry_norm: float
    chi0_sym: np.ndarray             # (chi0_raw + chi0_raw.T) / 2
    chi_sym: np.ndarray

    # The one and only matrix representation used for rank, inverse and U.
    # Raw and symmetric representations are always retained as evidence.
    matrix_for_inversion: Literal["raw", "symmetrized"]
    chi0_selected: np.ndarray
    chi_selected: np.ndarray

    # Condition reports for the selected matrices
    condition_chi0: MatrixConditionReport
    condition_chi: MatrixConditionReport

    # Inversion (None if rank deficient)
    inversion_chi0: Optional[InversionReport]
    inversion_chi: Optional[InversionReport]

    # Interaction matrix (None if inversion failed)
    U_matrix: Optional[np.ndarray]

    # Per-element diagnostics
    element_diagnostics: list[ElementDiagnostics]

    # Verdict
    matrix_status: str   # 'FULL_RANK' | 'RANK_DEFICIENT' | 'INVERSION_FAILED'
    response_fit_method: Literal["linear", "polynomial"]
    response_polynomial_degree: Optional[int]
    response_minimum_residual_dof: int
    response_alpha_window_ev: Optional[float]


# ─────────────────────────────────────────────
# MATRIX PIPELINE FUNCTIONS
# ─────────────────────────────────────────────

def fit_polynomial_response(
    alpha: Sequence[float],
    occupations: Sequence[float],
    *,
    degree: int = 3,
    minimum_residual_dof: int = 1,
) -> PolynomialFit:
    """Fit n(alpha) and return the analytic derivative at alpha=0.

    Alpha is scaled to [-1, 1] before least squares to stabilize the
    Vandermonde design. Coefficients are converted back to physical alpha
    units. A degree is never silently lowered to make a fit possible.
    """
    a = np.asarray(alpha, dtype=float)
    n = np.asarray(occupations, dtype=float)
    if a.ndim != 1 or n.ndim != 1 or len(a) != len(n):
        raise ValueError("alpha and occupations must be one-dimensional arrays of equal length")
    if not np.all(np.isfinite(a)) or not np.all(np.isfinite(n)):
        raise ValueError("alpha and occupations must contain only finite values")
    if (isinstance(degree, bool) or not isinstance(degree, int)
            or not 1 <= degree <= 3):
        raise ValueError("polynomial degree must be an integer from 1 through 3")
    if (isinstance(minimum_residual_dof, bool)
            or not isinstance(minimum_residual_dof, int)
            or minimum_residual_dof < 1):
        raise ValueError("minimum_residual_dof must be a positive integer")
    if np.unique(a).size != a.size:
        raise ValueError("duplicate alpha observations require explicit aggregation before fitting")
    residual_dof = int(a.size - (degree + 1))
    if residual_dof < minimum_residual_dof:
        required = degree + 1 + minimum_residual_dof
        raise ValueError(
            f"degree-{degree} fit requires at least {required} distinct alpha points; got {a.size}"
        )
    if np.min(a) >= 0.0 or np.max(a) <= 0.0:
        raise ValueError("polynomial derivative at zero requires alpha points on both sides of zero")

    alpha_scale = float(np.max(np.abs(a)))
    if not np.isfinite(alpha_scale) or alpha_scale <= 0.0:
        raise ValueError("alpha scale must be positive and finite")
    x = a / alpha_scale
    design = np.polynomial.polynomial.polyvander(x, degree)
    scaled_coefficients, _, rank, singular_values = np.linalg.lstsq(design, n, rcond=None)
    if int(rank) != degree + 1:
        raise ValueError(f"degree-{degree} polynomial design is rank deficient")

    predicted = design @ scaled_coefficients
    residuals_array = n - predicted
    ss_res = float(residuals_array @ residuals_array)
    centered = n - float(np.mean(n))
    ss_tot = float(centered @ centered)
    r_squared = 1.0 - ss_res / ss_tot if ss_tot > 1e-30 else float("nan")
    physical_coefficients = [
        float(coefficient / (alpha_scale ** power))
        for power, coefficient in enumerate(scaled_coefficients)
    ]
    return PolynomialFit(
        slope=physical_coefficients[1],
        intercept=physical_coefficients[0],
        degree=degree,
        coefficients=physical_coefficients,
        r_squared=float(r_squared),
        residuals=[float(value) for value in residuals_array],
        max_abs_residual=float(np.max(np.abs(residuals_array))),
        residual_rms=float(np.sqrt(ss_res / a.size)),
        n_points=int(a.size),
        residual_dof=residual_dof,
        design_condition_number=float(singular_values[0] / singular_values[-1]),
    )

def fit_response_matrix(
    observations: list[ResponseObservation],
    *,
    fit_policy: Optional[ResponseFitPolicy] = None,
) -> tuple[np.ndarray, np.ndarray, list[ElementDiagnostics]]:
    """
    Build chi0_raw and chi_raw from a list of ResponseObservation.

    For each (I, J) pair, collects n_I(alpha_J) across all alpha values
    from perturbation_site == J, then calls fit_response.

    Returns
    -------
    chi0_raw : ndarray shape (N, N)
    chi_raw  : ndarray shape (N, N)
    element_diagnostics : list[ElementDiagnostics]
    """
    if not observations:
        raise ValueError("No observations provided")
    fit_policy = fit_policy or ResponseFitPolicy()
    fit_policy.validate()

    # Validate consistent site_labels
    all_labels = observations[0].site_labels
    N = len(all_labels)
    for obs in observations:
        if obs.site_labels != all_labels:
            raise ValueError(
                f"Inconsistent site_labels: {obs.site_labels} vs {all_labels}"
            )
        if len(obs.occupations_bare) != N:
            raise ValueError(f"occupations_bare length {len(obs.occupations_bare)} != N={N}")
        if len(obs.occupations_screened) != N:
            raise ValueError(f"occupations_screened length {len(obs.occupations_screened)} != N={N}")

    chi0_raw = np.zeros((N, N), dtype=float)
    chi_raw = np.zeros((N, N), dtype=float)
    diagnostics: list[ElementDiagnostics] = []

    for J_idx, J in enumerate(all_labels):
        # Collect observations for perturbation column J
        col_obs = sorted(
            [o for o in observations if o.perturbation_site == J],
            key=lambda o: o.alpha,
        )
        if fit_policy.alpha_window_ev is not None:
            tolerance = max(1e-12, fit_policy.alpha_window_ev * 1e-12)
            col_obs = [o for o in col_obs if abs(o.alpha) <= fit_policy.alpha_window_ev + tolerance]
        if len(col_obs) < 2:
            raise ValueError(
                f"Column J={J}: fewer than 2 alpha points (got {len(col_obs)})"
            )

        alpha_vals = [o.alpha for o in col_obs]

        for I_idx, I in enumerate(all_labels):
            # row I = observed site
            bare_occ = [o.occupations_bare[I_idx] for o in col_obs]
            scrn_occ = [o.occupations_screened[I_idx] for o in col_obs]
            fit0_linear = fit_response(alpha_vals, bare_occ)
            fit_linear = fit_response(alpha_vals, scrn_occ)

            if fit_policy.method == "polynomial":
                fit0_full = fit_polynomial_response(
                    alpha_vals,
                    bare_occ,
                    degree=fit_policy.polynomial_degree,
                    minimum_residual_dof=fit_policy.minimum_residual_dof,
                )
                fit_full = fit_polynomial_response(
                    alpha_vals,
                    scrn_occ,
                    degree=fit_policy.polynomial_degree,
                    minimum_residual_dof=fit_policy.minimum_residual_dof,
                )
            else:
                fit0_full = fit0_linear
                fit_full = fit_linear

            # Fit the smallest measured alpha shell; do not assume a fixed grid.
            inner_mask = select_inner_alpha_window(alpha_vals)
            alpha_inner = [a for a, m in zip(alpha_vals, inner_mask) if m]
            bare_inner = [n for n, m in zip(bare_occ, inner_mask) if m]
            scrn_inner = [n for n, m in zip(scrn_occ, inner_mask) if m]
            fit0_inner = fit_response(alpha_inner, bare_inner)
            fit_inner = fit_response(alpha_inner, scrn_inner)

            chi0_raw[I_idx, J_idx] = fit0_full.slope
            chi_raw[I_idx, J_idx] = fit_full.slope

            diagnostics.append(ElementDiagnostics(
                obs_site=I,
                pert_site=J,
                mode="bare",
                fit_full=fit0_full,
                fit_full_linear=fit0_linear,
                fit_inner=fit0_inner,
            ))
            diagnostics.append(ElementDiagnostics(
                obs_site=I,
                pert_site=J,
                mode="screened",
                fit_full=fit_full,
                fit_full_linear=fit_linear,
                fit_inner=fit_inner,
            ))

    return chi0_raw, chi_raw, diagnostics


def analyze_matrix_condition(M: np.ndarray) -> MatrixConditionReport:
    """
    Compute shape, rank, det, SVD, condition number for a square matrix.
    No hardcoded threshold — all values are returned as diagnostics.
    """
    if M.ndim != 2 or M.shape[0] != M.shape[1]:
        raise ValueError(f"Matrix must be square, got shape {M.shape}")

    N = M.shape[0]
    svd = np.linalg.svd(M, compute_uv=False)
    tol = svd[0] * N * np.finfo(float).eps * 1e3  # generous numerical rank threshold
    rank = int(np.sum(svd > tol))
    is_full_rank = (rank == N)
    cond = float(svd[0] / svd[-1]) if svd[-1] > 0 else float("inf")
    det = float(np.linalg.det(M))
    status = "FULL_RANK" if is_full_rank else "RANK_DEFICIENT"

    return MatrixConditionReport(
        shape=(N, N),
        rank=rank,
        is_full_rank=is_full_rank,
        det=det,
        singular_values=list(svd),
        condition_number=cond,
        matrix_status=status,
    )


def invert_response_matrix(
    M: np.ndarray,
    condition: MatrixConditionReport,
) -> InversionReport:
    """
    Invert a square full-rank response matrix using np.linalg.inv only.
    Raises ValueError if rank deficient.
    Never uses pinv, lstsq, or regularization.
    """
    if not condition.is_full_rank:
        raise ValueError(
            f"Cannot invert rank-deficient matrix (rank={condition.rank}, "
            f"N={condition.shape[0]}). MATRIX_STATUS = RANK_DEFICIENT"
        )

    try:
        M_inv = np.linalg.inv(M)
    except np.linalg.LinAlgError as e:
        raise ValueError(f"np.linalg.inv failed: {e}")

    N = M.shape[0]
    left_res = float(np.linalg.norm(M_inv @ M - np.eye(N), "fro"))
    right_res = float(np.linalg.norm(M @ M_inv - np.eye(N), "fro"))

    return InversionReport(
        inverse=M_inv,
        left_residual=left_res,
        right_residual=right_res,
        method="direct_inv",
    )


def compute_interaction_matrix(
    inv_chi0: np.ndarray,
    inv_chi: np.ndarray,
) -> np.ndarray:
    """
    U_matrix = inv(chi0) - inv(chi)
    Both inputs must already be inverted matrices of the same shape.
    """
    if inv_chi0.shape != inv_chi.shape:
        raise ValueError(
            f"Shape mismatch: inv_chi0 {inv_chi0.shape} vs inv_chi {inv_chi.shape}"
        )
    return inv_chi0 - inv_chi


def analyze_matrix_response_campaign(
    observations: list[ResponseObservation],
    *,
    matrix_for_inversion: Literal["raw", "symmetrized"] = "raw",
    fit_policy: Optional[ResponseFitPolicy] = None,
) -> MatrixResponseResult:
    """
    Run the complete N×N linear-response analysis.

    Parameters
    ----------
    observations : list[ResponseObservation]
        All ResponseObservation objects for all perturbation columns and alpha
        values. Must cover every (J, alpha) combination needed.
    matrix_for_inversion : {"raw", "symmetrized"}
        Locked scientific policy for *all* numerical diagnostics, direct
        inversions and U.  This is never inferred from a reporting choice.
        Both representations remain in the returned evidence object.

    Returns
    -------
    MatrixResponseResult
    """
    if not observations:
        raise ValueError("No observations provided")
    fit_policy = fit_policy or ResponseFitPolicy()
    fit_policy.validate()

    site_labels = observations[0].site_labels
    N = len(site_labels)

    # 1. Build response matrices via regression
    chi0_raw, chi_raw, element_diags = fit_response_matrix(
        observations,
        fit_policy=fit_policy,
    )

    # 2. Symmetry diagnostics (raw preserved as primary)
    chi0_anti = chi0_raw - chi0_raw.T
    chi_anti = chi_raw - chi_raw.T
    chi0_asym_norm = float(np.linalg.norm(chi0_anti, "fro"))
    chi_asym_norm = float(np.linalg.norm(chi_anti, "fro"))
    chi0_sym = 0.5 * (chi0_raw + chi0_raw.T)
    chi_sym = 0.5 * (chi_raw + chi_raw.T)

    if matrix_for_inversion == "raw":
        chi0_selected, chi_selected = chi0_raw, chi_raw
    elif matrix_for_inversion == "symmetrized":
        chi0_selected, chi_selected = chi0_sym, chi_sym
    else:
        raise ValueError(
            "matrix_for_inversion must be 'raw' or 'symmetrized', got "
            f"{matrix_for_inversion!r}"
        )

    # 3. Condition analysis of exactly the representation selected above.
    cond_chi0 = analyze_matrix_condition(chi0_selected)
    cond_chi = analyze_matrix_condition(chi_selected)

    # 4. Inversion (only if full rank)
    inv_report_chi0: Optional[InversionReport] = None
    inv_report_chi: Optional[InversionReport] = None
    U_matrix: Optional[np.ndarray] = None
    matrix_status = "FULL_RANK"

    if not cond_chi0.is_full_rank or not cond_chi.is_full_rank:
        matrix_status = "RANK_DEFICIENT"
    else:
        try:
            inv_report_chi0 = invert_response_matrix(chi0_selected, cond_chi0)
            inv_report_chi = invert_response_matrix(chi_selected, cond_chi)
            U_matrix = compute_interaction_matrix(
                inv_report_chi0.inverse, inv_report_chi.inverse
            )
        except (ValueError, np.linalg.LinAlgError) as e:
            matrix_status = f"INVERSION_FAILED: {e}"

    return MatrixResponseResult(
        site_labels=site_labels,
        n_sites=N,
        chi0_raw=chi0_raw,
        chi_raw=chi_raw,
        chi0_asymmetry_norm=chi0_asym_norm,
        chi_asymmetry_norm=chi_asym_norm,
        chi0_sym=chi0_sym,
        chi_sym=chi_sym,
        matrix_for_inversion=matrix_for_inversion,
        chi0_selected=chi0_selected,
        chi_selected=chi_selected,
        condition_chi0=cond_chi0,
        condition_chi=cond_chi,
        inversion_chi0=inv_report_chi0,
        inversion_chi=inv_report_chi,
        U_matrix=U_matrix,
        element_diagnostics=element_diags,
        matrix_status=matrix_status,
        response_fit_method=fit_policy.method,
        response_polynomial_degree=(
            fit_policy.polynomial_degree if fit_policy.method == "polynomial" else None
        ),
        response_minimum_residual_dof=fit_policy.minimum_residual_dof,
        response_alpha_window_ev=fit_policy.alpha_window_ev,
    )
