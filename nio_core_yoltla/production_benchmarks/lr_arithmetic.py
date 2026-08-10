"""
production_benchmarks/lr_arithmetic.py

Real linear-response arithmetic for 3-point screening and 5-point final modes.
Reuses the validated domain.matrix_lr engine where possible; this module
provides the orchestration-layer matrix builders from observation dictionaries.

NO pseudoinverse. NO zero-filled placeholders. NO hardcoded diagnostics.
"""
from __future__ import annotations
import numpy as np
from typing import Dict, List, Tuple, Optional, Any


# ─────────────────────────────────────────────────────────────────────────────
# 3-point central derivative
# ─────────────────────────────────────────────────────────────────────────────

def central_3point(n_minus: float, n_plus: float, delta: float) -> float:
    """Central finite difference: (n(+δ) - n(-δ)) / (2δ)."""
    if abs(delta) < 1e-15:
        raise ValueError(f"delta must be nonzero, got {delta}")
    return (n_plus - n_minus) / (2.0 * delta)


# ─────────────────────────────────────────────────────────────────────────────
# 5-point linear fit
# ─────────────────────────────────────────────────────────────────────────────

def fit_5point(alphas: List[float], occupations: List[float]) -> dict:
    """
    Fit n(alpha) = slope * alpha + intercept over 5 points.

    Expected alpha ordering: [-2δ, -δ, 0, +δ, +2δ]

    Returns
    -------
    dict with:
      slope, intercept, residuals, r2,
      inner_central_slope  : (n[3]-n[1]) / (2δ)   from inner pair
      outer_slope          : (n[4]-n[0]) / (4δ)   from outer pair
      positive_slope       : linear fit over alpha >= 0
      negative_slope       : linear fit over alpha <= 0
      asymmetry            : |pos_slope - neg_slope| / max(|pos|, |neg|)
    """
    a = np.asarray(alphas, dtype=float)
    n = np.asarray(occupations, dtype=float)

    if len(a) != 5:
        raise ValueError(f"fit_5point requires exactly 5 points, got {len(a)}")

    # Sort by alpha
    order = np.argsort(a)
    a = a[order]
    n = n[order]

    # Full 5-point linear regression
    A = np.column_stack([a, np.ones(5)])
    coeffs, residuals_raw, rank, sv = np.linalg.lstsq(A, n, rcond=None)
    slope, intercept = float(coeffs[0]), float(coeffs[1])

    n_fit  = slope * a + intercept
    res    = n - n_fit
    ss_res = float(np.sum(res**2))
    ss_tot = float(np.sum((n - np.mean(n))**2))
    r2     = 1.0 - ss_res / ss_tot if ss_tot > 1e-30 else 0.0

    # Inner central slope: between alpha[1] and alpha[3]
    delta_inner = a[3] - a[1]
    inner_central_slope = (n[3] - n[1]) / delta_inner if abs(delta_inner) > 1e-15 else 0.0

    # Outer slope: between alpha[0] and alpha[4]
    delta_outer = a[4] - a[0]
    outer_slope = (n[4] - n[0]) / delta_outer if abs(delta_outer) > 1e-15 else 0.0

    # Positive-side slope: fit over alpha >= 0 (indices 2,3,4)
    a_pos = a[2:]
    n_pos = n[2:]
    A_pos = np.column_stack([a_pos, np.ones(3)])
    c_pos, _, _, _ = np.linalg.lstsq(A_pos, n_pos, rcond=None)
    positive_slope = float(c_pos[0])

    # Negative-side slope: fit over alpha <= 0 (indices 0,1,2)
    a_neg = a[:3]
    n_neg = n[:3]
    A_neg = np.column_stack([a_neg, np.ones(3)])
    c_neg, _, _, _ = np.linalg.lstsq(A_neg, n_neg, rcond=None)
    negative_slope = float(c_neg[0])

    # Asymmetry
    denom = max(abs(positive_slope), abs(negative_slope))
    asymmetry = abs(positive_slope - negative_slope) / denom if denom > 1e-15 else 0.0

    return {
        'slope':               slope,
        'intercept':           intercept,
        'residuals':           res.tolist(),
        'r2':                  float(r2),
        'inner_central_slope': float(inner_central_slope),
        'outer_slope':         float(outer_slope),
        'positive_slope':      float(positive_slope),
        'negative_slope':      float(negative_slope),
        'asymmetry':           float(asymmetry),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 3-point matrix builder
# ─────────────────────────────────────────────────────────────────────────────

def build_chi_matrix_3point(
    obs_dict: Dict[Tuple, List[float]],
    n_sites: int,
    delta: float,
    response_semantic: str,  # 'BARE' or 'SCREENED'
) -> np.ndarray:
    """
    Build the N×N linear-response matrix from 3-point observations.

    Parameters
    ----------
    obs_dict          : dict keyed by (perturbed_site_J, alpha, mode)
                        -> list[float] of length n_sites
    n_sites           : number of correlated sites N
    delta             : perturbation step size (positive)
    response_semantic : 'BARE' for chi0, 'SCREENED' for chi

    Returns
    -------
    (N, N) numpy array

    Raises
    ------
    KeyError  if a required observation is missing
    ValueError if delta <= 0
    """
    if delta <= 0:
        raise ValueError(f"delta must be positive, got {delta}")
    if response_semantic not in ('BARE', 'SCREENED'):
        raise ValueError(f"response_semantic must be 'BARE' or 'SCREENED', "
                         f"got {response_semantic!r}")

    mat = np.zeros((n_sites, n_sites))
    mode = response_semantic

    for J in range(n_sites):
        key_minus = (J, -delta, mode)
        key_plus  = (J, +delta, mode)
        if key_minus not in obs_dict:
            raise KeyError(
                f"Missing observation for J={J}, alpha={-delta}, mode={mode}. "
                f"Available keys: {list(obs_dict.keys())}"
            )
        if key_plus not in obs_dict:
            raise KeyError(
                f"Missing observation for J={J}, alpha={+delta}, mode={mode}. "
                f"Available keys: {list(obs_dict.keys())}"
            )
        n_minus = obs_dict[key_minus]
        n_plus  = obs_dict[key_plus]
        if len(n_minus) != n_sites or len(n_plus) != n_sites:
            raise ValueError(
                f"Observation vector length mismatch for J={J}: "
                f"expected {n_sites}, got {len(n_minus)}/{len(n_plus)}"
            )
        for I in range(n_sites):
            mat[I, J] = central_3point(n_minus[I], n_plus[I], delta)

    return mat


# ─────────────────────────────────────────────────────────────────────────────
# 5-point matrix builder
# ─────────────────────────────────────────────────────────────────────────────

def build_chi_matrix_5point(
    obs_dict: Dict[Tuple, List[float]],
    n_sites: int,
    delta: float,
    response_semantic: str,  # 'BARE' or 'SCREENED'
) -> dict:
    """
    Build the N×N linear-response matrix from 5-point linear fits.

    Parameters
    ----------
    obs_dict          : dict keyed by (J, alpha, mode) -> list[float, n_sites]
                        Expected alphas per column J: [-2δ,-δ,0,+δ,+2δ]
    n_sites           : N
    delta             : step size (positive)
    response_semantic : 'BARE' or 'SCREENED'

    Returns
    -------
    dict with:
      matrix              : (N,N) ndarray of fitted slopes
      fit_diagnostics     : dict[(I,J)] -> fit_5point output
      min_r2, max_r2, mean_r2
      max_asymmetry, mean_asymmetry
    """
    if delta <= 0:
        raise ValueError(f"delta must be positive, got {delta}")
    if response_semantic not in ('BARE', 'SCREENED'):
        raise ValueError(f"response_semantic must be 'BARE' or 'SCREENED'")

    mode = response_semantic
    alphas_expected = [-2*delta, -delta, 0.0, +delta, +2*delta]
    mat = np.zeros((n_sites, n_sites))
    diagnostics: Dict[Tuple[int,int], dict] = {}

    for J in range(n_sites):
        # Collect 5-point observations for column J
        occs_per_alpha: Dict[float, List[float]] = {}
        for alpha in alphas_expected:
            key = (J, alpha, mode)
            if key not in obs_dict:
                raise KeyError(
                    f"Missing observation for J={J}, alpha={alpha}, mode={mode}. "
                    f"Required alphas: {alphas_expected}"
                )
            occs_per_alpha[alpha] = obs_dict[key]

        for I in range(n_sites):
            occ_vals = [occs_per_alpha[alpha][I] for alpha in alphas_expected]
            fit = fit_5point(alphas_expected, occ_vals)
            mat[I, J] = fit['slope']
            diagnostics[(I, J)] = fit

    # Aggregate diagnostics
    r2_vals   = [d['r2'] for d in diagnostics.values()]
    asym_vals = [d['asymmetry'] for d in diagnostics.values()]

    return {
        'matrix':        mat,
        'fit_diagnostics': diagnostics,
        'min_r2':        float(min(r2_vals)),
        'max_r2':        float(max(r2_vals)),
        'mean_r2':       float(np.mean(r2_vals)),
        'max_asymmetry': float(max(asym_vals)),
        'mean_asymmetry':float(np.mean(asym_vals)),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Matrix inversion and U computation
# ─────────────────────────────────────────────────────────────────────────────

def compute_U_matrix(chi0: np.ndarray, chi: np.ndarray) -> dict:
    """
    Compute Hubbard U matrix: U = chi0^{-1} - chi^{-1}

    Direct inversion only. No pseudoinverse. No least-squares.

    Returns full diagnostics: SVD, condition numbers, inversion residuals,
    antisymmetry norm.

    Raises
    ------
    ValueError if either matrix is rank-deficient.
    """
    chi0 = np.asarray(chi0, dtype=float)
    chi  = np.asarray(chi,  dtype=float)
    N    = chi0.shape[0]

    if chi0.shape != (N, N) or chi.shape != (N, N):
        raise ValueError(f"chi0 and chi must be square NxN, got {chi0.shape}, {chi.shape}")

    # SVD of both matrices
    sv0 = np.linalg.svd(chi0, compute_uv=False)
    sv  = np.linalg.svd(chi,  compute_uv=False)

    r_chi0 = int(np.linalg.matrix_rank(chi0))
    r_chi  = int(np.linalg.matrix_rank(chi))

    if r_chi0 < N:
        raise ValueError(
            f"chi0 is rank deficient: rank={r_chi0} < N={N}. "
            f"Singular values: {sv0}. Direct inversion impossible."
        )
    if r_chi < N:
        raise ValueError(
            f"chi is rank deficient: rank={r_chi} < N={N}. "
            f"Singular values: {sv}. Direct inversion impossible."
        )

    cond0 = float(sv0[0] / sv0[-1]) if sv0[-1] > 0 else float('inf')
    cond  = float(sv[0]  / sv[-1])  if sv[-1]  > 0 else float('inf')

    inv_chi0 = np.linalg.inv(chi0)
    inv_chi  = np.linalg.inv(chi)

    # Inversion residuals
    I = np.eye(N)
    left_res_chi0  = float(np.max(np.abs(chi0 @ inv_chi0 - I)))
    right_res_chi0 = float(np.max(np.abs(inv_chi0 @ chi0 - I)))
    left_res_chi   = float(np.max(np.abs(chi  @ inv_chi  - I)))
    right_res_chi  = float(np.max(np.abs(inv_chi  @ chi  - I)))

    U = inv_chi0 - inv_chi
    U_antisym_norm = float(np.max(np.abs(U - U.T)))

    return {
        'U':                U,
        'inv_chi0':         inv_chi0,
        'inv_chi':          inv_chi,
        'chi0_rank':        r_chi0,
        'chi_rank':         r_chi,
        'chi0_svd':         sv0.tolist(),
        'chi_svd':          sv.tolist(),
        'chi0_cond':        cond0,
        'chi_cond':         cond,
        'chi0_left_residual':  left_res_chi0,
        'chi0_right_residual': right_res_chi0,
        'chi_left_residual':   left_res_chi,
        'chi_right_residual':  right_res_chi,
        'left_residual':    max(left_res_chi0, left_res_chi),   # compat
        'right_residual':   max(right_res_chi0, right_res_chi), # compat
        'U_antisym_norm':   U_antisym_norm,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Eigenmode analysis
# ─────────────────────────────────────────────────────────────────────────────

def eigenmode_analysis(U: np.ndarray, n_sites: int) -> dict:
    """
    Compute eigenvalues/eigenvectors of U and identify the uniform mode.

    The uniform mode is the eigenvector closest to (1,1,...,1)/sqrt(N).

    Returns
    -------
    dict with eigenvalues, eigenvectors, uniform_mode_overlap,
         uniform_mode_eigenvalue, transverse_eigenvalues
    """
    U = np.asarray(U, dtype=float)
    if U.shape != (n_sites, n_sites):
        raise ValueError(f"U must be ({n_sites},{n_sites}), got {U.shape}")

    # Use eigh for real symmetric; eig for general
    try:
        vals, vecs = np.linalg.eigh(U)
    except np.linalg.LinAlgError:
        vals, vecs = np.linalg.eig(U)
        vals = vals.real
        vecs = vecs.real

    v_uniform = np.ones(n_sites) / np.sqrt(n_sites)
    overlaps  = np.abs(vecs.T @ v_uniform)
    best_idx  = int(np.argmax(overlaps))

    return {
        'eigenvalues':            vals.tolist(),
        'eigenvectors':           vecs.tolist(),
        'uniform_mode_overlap':   float(overlaps[best_idx]),
        'uniform_mode_eigenvalue':float(vals[best_idx]),
        'uniform_mode_index':     best_idx,
        'transverse_eigenvalues': [float(vals[i]) for i in range(n_sites)
                                   if i != best_idx],
    }
