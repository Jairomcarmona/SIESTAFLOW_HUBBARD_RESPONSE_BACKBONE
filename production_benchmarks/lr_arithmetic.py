"""
production_benchmarks/lr_arithmetic.py

Real linear-response arithmetic for 3-point screening and 5-point final modes.
Reuses the validated domain.matrix_lr engine where possible; this module
provides the orchestration-layer matrix builders from observation dictionaries.

NO pseudoinverse. NO zero-filled placeholders. NO hardcoded diagnostics.
"""
from __future__ import annotations

import math
import re
from typing import Dict, List, Tuple, Optional, Any, Mapping, Sequence

import numpy as np

from siestaflow_hubbard.domain.matrix_lr import (
    ResponseObservation,
    analyze_matrix_condition,
    compute_interaction_matrix,
    fit_polynomial_response,
    invert_response_matrix,
)
from siestaflow_hubbard.domain.scalar_lr import fit_response


# ─────────────────────────────────────────────────────────────────────────────
# 3-point central derivative
# ─────────────────────────────────────────────────────────────────────────────

def central_3point(n_minus: float, n_plus: float, delta: float) -> float:
    """Compatibility wrapper around the shared domain linear response fitter."""
    if abs(delta) < 1e-15:
        raise ValueError(f"delta must be nonzero, got {delta}")
    return float(fit_response([-delta, delta], [n_minus, n_plus]).slope)


# ─────────────────────────────────────────────────────────────────────────────
# 5-point response fit
# ─────────────────────────────────────────────────────────────────────────────

def fit_5point(
    alphas: List[float],
    occupations: List[float],
    *,
    fit_method: str = 'linear',
    polynomial_degree: int = 3,
    minimum_residual_dof: int = 1,
) -> dict:
    """Compatibility diagnostics backed by the shared domain fitters."""
    a = np.asarray(alphas, dtype=float)
    n = np.asarray(occupations, dtype=float)
    if len(a) != 5:
        raise ValueError(f"fit_5point requires exactly 5 points, got {len(a)}")
    if not np.all(np.isfinite(a)) or not np.all(np.isfinite(n)):
        raise ValueError("alphas and occupations must be finite")
    order = np.argsort(a)
    a = a[order]
    n = n[order]
    linear = fit_response(a.tolist(), n.tolist())
    linear_reference = {
        'slope': float(linear.slope),
        'intercept': float(linear.intercept),
        'residuals': [float(value) for value in linear.residuals],
        'r2': float(linear.r_squared),
        'residual_rms': float(np.sqrt(np.mean(np.square(linear.residuals)))),
        'residual_dof': len(a) - 2,
        'design_condition_number': None,
    }

    if fit_method == 'linear':
        slope, intercept = float(linear.slope), float(linear.intercept)
        res, r2 = np.asarray(linear.residuals, dtype=float), float(linear.r_squared)
        regression = {
            'method': 'linear',
            'degree': 1,
            'coefficients': [intercept, slope],
            'residual_rms': linear_reference['residual_rms'],
            'residual_dof': linear_reference['residual_dof'],
            'design_condition_number': None,
        }
    elif fit_method == 'polynomial':
        fitted = fit_polynomial_response(
            a,
            n,
            degree=polynomial_degree,
            minimum_residual_dof=minimum_residual_dof,
        )
        slope, intercept = fitted.slope, fitted.intercept
        res = np.asarray(fitted.residuals, dtype=float)
        r2 = fitted.r_squared
        regression = {
            'method': 'polynomial',
            'degree': fitted.degree,
            'coefficients': fitted.coefficients,
            'residual_rms': fitted.residual_rms,
            'residual_dof': fitted.residual_dof,
            'design_condition_number': fitted.design_condition_number,
        }
    else:
        raise ValueError("fit_method must be 'linear' or 'polynomial'")

    inner = fit_response(a[1:4:2].tolist(), n[1:4:2].tolist())
    outer = fit_response(a[[0, 4]].tolist(), n[[0, 4]].tolist())
    positive = fit_response(a[2:].tolist(), n[2:].tolist())
    negative = fit_response(a[:3].tolist(), n[:3].tolist())
    positive_slope, negative_slope = float(positive.slope), float(negative.slope)
    denom = max(abs(positive_slope), abs(negative_slope))
    asymmetry = abs(positive_slope - negative_slope) / denom if denom > 1e-15 else 0.0

    return {
        'regression':          regression,
        'linear_reference':    linear_reference,
        'slope':               slope,
        'intercept':           intercept,
        'residuals':           res.tolist(),
        'r2':                  float(r2),
        'inner_central_slope': float(inner.slope),
        'outer_slope':         float(outer.slope),
        'positive_slope':      float(positive_slope),
        'negative_slope':      float(negative_slope),
        'asymmetry':           float(asymmetry),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 3-point matrix builder
# ─────────────────────────────────────────────────────────────────────────────

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def response_observations_from_records(
    records: Sequence[Mapping[str, Any]], *, n_sites: int,
) -> list[ResponseObservation]:
    """Convert receipt-backed legacy rows to complete shared analyzer inputs.

    The stored alpha=0 BARE and SCREENED rows are common to all perturbation
    columns. They must each occur once (with site index 0) and are expanded in
    memory across columns. Nonzero observations must be unique per
    site/alpha/mode. A verified REFERENCE row supplies the reference vector.
    """
    if isinstance(n_sites, bool) or not isinstance(n_sites, int) or n_sites < 1:
        raise ValueError("n_sites must be a positive integer")
    if not records:
        raise ValueError("No legacy response observations were provided")

    def require_sha(record: Mapping[str, Any], field: str) -> str:
        value = record.get(field)
        if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
            raise ValueError(f"verified observation requires a valid {field}")
        return value

    def vector(record: Mapping[str, Any], label: str) -> list[float]:
        values = record.get("occupation_vector")
        if not isinstance(values, list) or len(values) != n_sites:
            raise ValueError(f"{label} occupation_vector must contain exactly {n_sites} values")
        try:
            output = [float(value) for value in values]
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{label} occupation_vector must be numeric") from exc
        if not all(math.isfinite(value) for value in output):
            raise ValueError(f"{label} occupation_vector must be finite")
        return output

    reference_rows: list[Mapping[str, Any]] = []
    observations: dict[tuple[int, float, str], Mapping[str, Any]] = {}
    atom_indices: list[int] | None = None
    for index, record in enumerate(records):
        mode = str(record.get("mode", "")).upper()
        if mode not in {"REFERENCE", "BARE", "SCREENED"}:
            raise ValueError(f"observation {index} has unsupported mode {mode!r}")
        if not isinstance(record.get("identity_key"), str) or not record["identity_key"]:
            raise ValueError(f"observation {index} has no completed-run identity receipt")
        require_sha(record, "stdout_sha256")
        require_sha(record, "fdf_sha256")
        selected_index = record.get("selected_occurrence_index")
        if isinstance(selected_index, bool) or not isinstance(selected_index, int) or selected_index < 0:
            raise ValueError(f"observation {index} has no selected semantic event index")
        if not record.get("selection_evidence"):
            raise ValueError(f"observation {index} has no semantic selection evidence")
        ids = record.get("atom_indices")
        if not isinstance(ids, list) or len(ids) != n_sites or len(set(ids)) != n_sites:
            raise ValueError(f"observation {index} atom_indices must identify exactly {n_sites} sites")
        if atom_indices is None:
            atom_indices = [int(value) for value in ids]
        elif [int(value) for value in ids] != atom_indices:
            raise ValueError("observation rows use inconsistent atom ordering")
        vector(record, f"observation {index}")
        try:
            alpha = float(record["alpha"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"observation {index} has no numeric alpha") from exc
        if not math.isfinite(alpha):
            raise ValueError(f"observation {index} alpha must be finite")
        if mode == "REFERENCE":
            if abs(alpha) > 1e-12:
                raise ValueError("reference occupation row must be at alpha=0")
            require_sha(record, "canonical_dm_sha256")
            reference_rows.append(record)
            continue
        parent_sha = require_sha(record, "parent_dm_sha256")
        site = record.get("perturbed_site")
        if isinstance(site, bool) or not isinstance(site, int) or not 0 <= site < n_sites:
            raise ValueError(f"observation {index} perturbed_site is outside [0, {n_sites})")
        if abs(alpha) <= 1e-12:
            if site != 0:
                raise ValueError("shared alpha=0 response rows must be stored once at perturbed_site=0")
            alpha = 0.0
        key = (site, round(alpha, 12), mode)
        if key in observations:
            raise ValueError(f"duplicate response observation for site={site}, alpha={alpha}, mode={mode}")
        observations[key] = record

    if len(reference_rows) != 1:
        raise ValueError(f"expected exactly one verified REFERENCE row, found {len(reference_rows)}")
    reference = reference_rows[0]
    reference_values = vector(reference, "REFERENCE")
    reference_dm_sha = require_sha(reference, "canonical_dm_sha256")
    if atom_indices is None:
        raise ValueError("no response observation rows were supplied")

    zero_rows: dict[str, Mapping[str, Any]] = {}
    nonzero_alphas = sorted({key[1] for key in observations if abs(key[1]) > 1e-12})
    for mode in ("BARE", "SCREENED"):
        row = observations.get((0, 0.0, mode))
        if row is None:
            raise ValueError(f"missing shared alpha=0 {mode} response observation")
        zero_rows[mode] = row
    if not any(value < 0 for value in nonzero_alphas) or not any(value > 0 for value in nonzero_alphas):
        raise ValueError("response observations must include negative and positive alpha")

    expected_parent_hashes = {reference_dm_sha}
    expected_parent_hashes.update(
        str(row.get("parent_dm_sha256")) for row in observations.values()
    )
    if len(expected_parent_hashes) != 1:
        raise ValueError("response rows do not share the verified reference DM")

    per_column_alpha_sets: list[set[float]] = []
    converted: list[ResponseObservation] = []
    for site in range(n_sites):
        alpha_values = [0.0, *nonzero_alphas]
        per_column_alpha_sets.append(set(alpha_values))
        for alpha in alpha_values:
            source_site = 0 if alpha == 0.0 else site
            bare = zero_rows["BARE"] if alpha == 0.0 else observations.get((source_site, round(alpha, 12), "BARE"))
            screened = zero_rows["SCREENED"] if alpha == 0.0 else observations.get((source_site, round(alpha, 12), "SCREENED"))
            if bare is None or screened is None:
                missing_mode = "BARE" if bare is None else "SCREENED"
                raise ValueError(f"missing {missing_mode} observation for site={site}, alpha={alpha}")
            if bare.get("parent_dm_sha256") != screened.get("parent_dm_sha256"):
                raise ValueError(f"BARE/SCREENED rows use different parent DMs for site={site}, alpha={alpha}")
            converted.append(ResponseObservation(
                perturbation_site=site,
                alpha=alpha,
                site_labels=list(range(n_sites)),
                occupations_ref=reference_values,
                occupations_bare=vector(bare, "BARE"),
                occupations_screened=vector(screened, "SCREENED"),
                parent_dm_sha256=reference_dm_sha,
                bare_fdf_sha256=str(bare["fdf_sha256"]),
                bare_out_sha256=str(bare["stdout_sha256"]),
                screened_fdf_sha256=str(screened["fdf_sha256"]),
                screened_out_sha256=str(screened["stdout_sha256"]),
            ))
    if any(values != per_column_alpha_sets[0] for values in per_column_alpha_sets[1:]):
        raise ValueError("every perturbation column must cover the same alpha grid")
    return converted

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
    *,
    fit_method: str = 'linear',
    polynomial_degree: int = 3,
    minimum_residual_dof: int = 1,
) -> dict:
    """
    Build the N×N linear-response matrix from 5-point response fits.

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
            fit = fit_5point(
                alphas_expected,
                occ_vals,
                fit_method=fit_method,
                polynomial_degree=polynomial_degree,
                minimum_residual_dof=minimum_residual_dof,
            )
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

    condition0 = analyze_matrix_condition(chi0)
    condition = analyze_matrix_condition(chi)
    sv0 = np.asarray(condition0.singular_values)
    sv = np.asarray(condition.singular_values)
    r_chi0 = condition0.rank
    r_chi = condition.rank

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

    cond0 = condition0.condition_number
    cond  = condition.condition_number

    inv_chi0 = invert_response_matrix(chi0, condition0).inverse
    inv_chi  = invert_response_matrix(chi, condition).inverse

    # Inversion residuals
    I = np.eye(N)
    left_res_chi0  = float(np.max(np.abs(chi0 @ inv_chi0 - I)))
    right_res_chi0 = float(np.max(np.abs(inv_chi0 @ chi0 - I)))
    left_res_chi   = float(np.max(np.abs(chi  @ inv_chi  - I)))
    right_res_chi  = float(np.max(np.abs(inv_chi  @ chi  - I)))

    U = compute_interaction_matrix(inv_chi0, inv_chi)
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
