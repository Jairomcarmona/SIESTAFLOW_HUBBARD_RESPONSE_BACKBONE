import numpy as np
from typing import Dict, Tuple

from ..domain.provenance import ResponseMatrix
from ..domain.u_matrix import HubbardInteractionMatrix, NumericalPolicy, GaugeRankStatus

class InversionError(Exception):
    pass

class LabelMismatchError(Exception):
    pass

class ConventionSwapError(Exception):
    pass

def align_matrices(chi0: ResponseMatrix, chi: ResponseMatrix) -> Tuple[np.ndarray, np.ndarray]:
    """
    Ensures that chi0 and chi have matching labels and returns aligned numpy arrays.
    """
    if set(chi0.row_ids) != set(chi.row_ids):
        raise LabelMismatchError("Row labels of chi0 and chi do not match.")
    if set(chi0.column_ids) != set(chi.column_ids):
        raise LabelMismatchError("Column labels of chi0 and chi do not match.")
        
    chi0_val = chi0.matrix.copy()
    chi_val = chi.matrix.copy()
    
    # If the ordering is different, we need to permute chi to match chi0's ordering
    row_mapping = {label: i for i, label in enumerate(chi0.row_ids)}
    col_mapping = {label: i for i, label in enumerate(chi0.column_ids)}
    
    if chi.row_ids != chi0.row_ids or chi.column_ids != chi0.column_ids:
        # Create permuted chi
        new_chi = np.zeros_like(chi_val)
        for i, row_label in enumerate(chi.row_ids):
            for j, col_label in enumerate(chi.column_ids):
                new_chi[row_mapping[row_label], col_mapping[col_label]] = chi_val[i, j]
        chi_val = new_chi

    return chi0_val, chi_val

def compute_u_matrix(
    chi0: ResponseMatrix, 
    chi: ResponseMatrix, 
    policy: NumericalPolicy,
    methodology_lock_hash: str,
    u_matrix_policy: str = "RAW"
) -> HubbardInteractionMatrix:
    """
    Computes the Hubbard U matrix from bare (chi0) and screened (chi) susceptibilities.
    Enforces canonical LR definition U_raw = inv(chi0) - inv(chi).
    Symmetrization is controlled by u_matrix_policy ('RAW' or 'SYMMETRIZED').
    """
    chi0_val, chi_val = align_matrices(chi0, chi)
        
    # Analyze condition number
    cond_chi0 = np.linalg.cond(chi0_val)
    cond_chi = np.linalg.cond(chi_val)
    max_cond = max(cond_chi0, cond_chi)
    
    rank_status = GaugeRankStatus.FULL_RANK
    
    if policy.max_condition_number is not None and max_cond > policy.max_condition_number:
        rank_status = GaugeRankStatus.ILL_CONDITIONED
        if not policy.allow_pinv_fallback:
            raise InversionError(f"Matrix condition number {max_cond} exceeds allowed {policy.max_condition_number}.")
            
    # Check for singularity/rank deficiency
    inversion_method = "DIRECT"
    try:
        if policy.allow_pinv_fallback and rank_status == GaugeRankStatus.ILL_CONDITIONED:
            inv_chi0 = np.linalg.pinv(chi0_val)
            inv_chi = np.linalg.pinv(chi_val)
            inversion_method = "PSEUDOINVERSE"
        else:
            inv_chi0 = np.linalg.inv(chi0_val)
            inv_chi = np.linalg.inv(chi_val)
    except np.linalg.LinAlgError as e:
        rank_status = GaugeRankStatus.RANK_DEFICIENT_INVALID
        if not policy.allow_pinv_fallback:
            raise InversionError(f"Singular matrix encountered: {e}")
        inv_chi0 = np.linalg.pinv(chi0_val)
        inv_chi = np.linalg.pinv(chi_val)
        inversion_method = "PSEUDOINVERSE"

    # Compute inversion residuals
    N = chi0_val.shape[0]
    I_matrix = np.eye(N)
    res_chi0 = np.linalg.norm(inv_chi0 @ chi0_val - I_matrix)
    res_chi = np.linalg.norm(inv_chi @ chi_val - I_matrix)
    max_residual = float(max(res_chi0, res_chi))

    # U_raw = inv(chi0) - inv(chi) (STRICT CANONICAL LINEAR RESPONSE DEFINITION)
    U_raw = inv_chi0 - inv_chi
    
    from ..domain.matrix_pipeline import compute_antisymmetry, symmetrize
    _, _, rel_frob = compute_antisymmetry(U_raw)
    U_sym = symmetrize(U_raw)
    
    selected_values = U_sym if u_matrix_policy.upper() in ("SYMMETRIZED", "SYM") else U_raw
    
    chi0_source_id = getattr(chi0, 'artifact_id', getattr(chi0, 'methodology_lock_hash', "UNKNOWN"))
    chi_source_id = getattr(chi, 'artifact_id', getattr(chi, 'methodology_lock_hash', "UNKNOWN"))
    
    return HubbardInteractionMatrix(
        row_subspace_ids=chi0.row_ids.copy(),
        column_subspace_ids=chi0.column_ids.copy(),
        values=selected_values,
        raw_values=U_raw,
        symmetrized_values=U_sym,
        antisymmetry_norm=rel_frob,
        chi0_source_id=chi0_source_id,
        chi_source_id=chi_source_id,
        methodology_lock_hash=methodology_lock_hash,
        rank_diagnostics=rank_status,
        condition_diagnostics=max_cond,
        inverse_residuals=max_residual,
        inversion_method=inversion_method,
        uncertainty_info=None,
        units="eV",
        recommended_single_U_ev=None,
        source_artifact_ids=[chi0_source_id, chi_source_id]
    )
