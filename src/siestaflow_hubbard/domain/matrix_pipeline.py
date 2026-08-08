from dataclasses import dataclass
import numpy as np

from siestaflow_hubbard.domain.exceptions import (
    IllConditionedMatrixError,
    SingularMatrixError,
    InversionResidualFailure,
    SelectionPolicyNotLocked,
    AggregationShapeViolation
)

@dataclass
class MatrixDiagnostics:
    condition_number: float
    singular_values: np.ndarray
    numerical_rank: int
    tolerance: float
    is_full_rank: bool

def assemble_raw(R: np.ndarray, A: np.ndarray) -> np.ndarray:
    """Assembles raw susceptibility matrix chi = A @ R."""
    if A.shape[1] != R.shape[0]:
        raise AggregationShapeViolation(f"Cannot multiply A shape {A.shape} by R shape {R.shape}")
    return A @ R

def compute_antisymmetry(M: np.ndarray) -> tuple[np.ndarray, float, float]:
    """Computes antisymmetry part (M - M.T)/2 and Frobenius norm."""
    anti = 0.5 * (M - M.T)
    frob = float(np.linalg.norm(anti, 'fro'))
    m_norm = float(np.linalg.norm(M, 'fro'))
    rel_frob = frob / max(m_norm, 1e-12)
    return anti, frob, rel_frob

def symmetrize(M: np.ndarray) -> np.ndarray:
    """Computes symmetric part (M + M.T)/2."""
    return 0.5 * (M + M.T)

def select_matrix(M_raw: np.ndarray, M_sym: np.ndarray, policy: str, methodology_lock_ref: str | None) -> np.ndarray:
    """Selects raw vs symmetrized matrix based on locked methodology policy."""
    if methodology_lock_ref is None:
        raise SelectionPolicyNotLocked("Cannot select matrix without locked methodology_lock_ref")
    if policy == "raw":
        return M_raw
    elif policy == "symmetrized":
        return M_sym
    else:
        raise ValueError(f"Unsupported matrix selection policy: {policy}")

def compute_diagnostics(M: np.ndarray, condition_threshold: float = 1000.0) -> MatrixDiagnostics:
    """Computes condition number and rank diagnostics. Prohibits ill-conditioned matrices."""
    cond = float(np.linalg.cond(M))
    s = np.linalg.svd(M, compute_uv=False)
    tol = s[0] * max(M.shape) * np.finfo(s.dtype).eps
    rank = int(np.sum(s > tol))
    is_full = rank == M.shape[0]
    
    if cond > condition_threshold:
        raise IllConditionedMatrixError(f"Matrix condition number {cond:.2f} exceeds threshold {condition_threshold}")
        
    return MatrixDiagnostics(
        condition_number=cond,
        singular_values=s,
        numerical_rank=rank,
        tolerance=tol,
        is_full_rank=is_full
    )

def invert_matrix(M: np.ndarray, diagnostics: MatrixDiagnostics, tolerance: float = 1e-10) -> np.ndarray:
    """Inverts square response matrix using direct np.linalg.inv. lstsq/pinv prohibited."""
    if not diagnostics.is_full_rank:
        raise SingularMatrixError("Cannot invert rank-deficient matrix")
        
    try:
        M_inv = np.linalg.inv(M)
    except np.linalg.LinAlgError as e:
        raise SingularMatrixError(f"Direct inversion failed: {e}")
        
    left_res = float(np.linalg.norm(M_inv @ M - np.eye(M.shape[0]), 'fro'))
    right_res = float(np.linalg.norm(M @ M_inv - np.eye(M.shape[0]), 'fro'))
    
    if left_res > tolerance or right_res > tolerance:
        raise InversionResidualFailure(f"Inversion residual left={left_res:.2e}, right={right_res:.2e} exceeded tolerance {tolerance:.2e}")
        
    return M_inv

def invert_chi(chi: np.ndarray, condition_threshold: float = 1000.0) -> np.ndarray:
    """Convenience direct inversion for U = inv(chi0) - inv(chi)."""
    diag = compute_diagnostics(chi, condition_threshold=condition_threshold)
    return invert_matrix(chi, diag)
