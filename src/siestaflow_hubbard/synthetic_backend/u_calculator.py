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

def compute_u_matrix(chi0: ResponseMatrix, chi: ResponseMatrix, policy: NumericalPolicy) -> HubbardInteractionMatrix:
    """
    Computes the Hubbard U matrix from bare (chi0) and screened (chi) susceptibilities.
    """
    chi0_val, chi_val = align_matrices(chi0, chi)
    
    # Verify chi0/chi swap convention
    # Physically, the bare response (chi0) should be larger in magnitude than screened response (chi) on the diagonal
    if np.any(np.abs(np.diag(chi_val)) > np.abs(np.diag(chi0_val))):
        raise ConventionSwapError("Diagonal elements of chi are larger than chi0. Did you swap chi and chi0?")
        
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
    try:
        if policy.allow_pinv_fallback and rank_status == GaugeRankStatus.ILL_CONDITIONED:
            inv_chi0 = np.linalg.pinv(chi0_val)
            inv_chi = np.linalg.pinv(chi_val)
        else:
            inv_chi0 = np.linalg.inv(chi0_val)
            inv_chi = np.linalg.inv(chi_val)
    except np.linalg.LinAlgError as e:
        rank_status = GaugeRankStatus.RANK_DEFICIENT_INVALID
        if not policy.allow_pinv_fallback:
            raise InversionError(f"Singular matrix encountered: {e}")
        inv_chi0 = np.linalg.pinv(chi0_val)
        inv_chi = np.linalg.pinv(chi_val)

    # U = inv(chi0) - inv(chi)
    U_val = inv_chi0 - inv_chi
    
    return HubbardInteractionMatrix(
        row_subspace_ids=chi0.row_ids.copy(),
        column_subspace_ids=chi0.column_ids.copy(),
        values=U_val,
        chi0_source_id=chi0.methodology_lock_hash,
        chi_source_id=chi.methodology_lock_hash,
        methodology_lock_hash="U_MATRIX_LOCK",
        rank_diagnostics=rank_status,
        condition_diagnostics=max_cond,
        inverse_residuals=0.0, # Not strictly calculated for simple inverse unless solving Ax=B
        uncertainty_info=None,
        units="eV",
        recommended_single_U_ev=None
    )
