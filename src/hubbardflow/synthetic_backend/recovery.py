import numpy as np
from ..domain.matrix_pipeline import invert_chi, assemble_raw
from ..domain.cardinals import Cardinals

def recover_U(R_bare: np.ndarray, R_screened: np.ndarray, cardinals: Cardinals | None = None, condition_threshold: float = 1000.0) -> np.ndarray:
    """
    Computes U = inv(chi0) - inv(chi).
    If cardinals is provided, assembles chi0 = A @ R_bare and chi = A @ R_screened first.
    Otherwise assumes R_bare and R_screened are already square chi0 and chi matrices.
    """
    if cardinals is not None:
        chi0 = cardinals.chi(R_bare)
        chi = cardinals.chi(R_screened)
    else:
        chi0 = R_bare
        chi = R_screened
        
    from ..domain.matrix_pipeline import symmetrize, select_matrix
    
    U_raw = invert_chi(chi0, condition_threshold=condition_threshold) - invert_chi(chi, condition_threshold=condition_threshold)
    U_sym = symmetrize(U_raw)
    
    # By default we should enforce the physical symmetric constraint
    return select_matrix(U_raw, U_sym, policy="symmetrized", methodology_lock_ref="U_RECOVERY")
