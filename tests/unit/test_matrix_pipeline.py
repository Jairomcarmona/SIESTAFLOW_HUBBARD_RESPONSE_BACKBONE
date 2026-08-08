import pytest
import numpy as np
from siestaflow_hubbard.domain.matrix_pipeline import (
    assemble_raw,
    compute_antisymmetry,
    symmetrize,
    select_matrix,
    compute_diagnostics,
    invert_matrix,
    invert_chi
)
from siestaflow_hubbard.domain.exceptions import (
    IllConditionedMatrixError,
    SingularMatrixError,
    SelectionPolicyNotLocked,
    AggregationShapeViolation
)

def test_assemble_raw():
    R = np.array([[1.0, 2.0], [3.0, 4.0]])
    A = np.eye(2)
    chi = assemble_raw(R, A)
    np.testing.assert_allclose(chi, R)
    
    # Test shape violation
    with pytest.raises(AggregationShapeViolation):
        assemble_raw(R, np.eye(3))

def test_symmetrize_and_antisymmetry():
    M = np.array([[1.0, 2.0], [0.0, 4.0]])
    sym = symmetrize(M)
    np.testing.assert_allclose(sym, [[1.0, 1.0], [1.0, 4.0]])
    
    anti, frob, rel_frob = compute_antisymmetry(M)
    np.testing.assert_allclose(anti, [[0.0, 1.0], [-1.0, 0.0]])
    assert frob > 0
    assert rel_frob > 0

def test_select_matrix():
    M_raw = np.array([[1.0, 2.0], [0.0, 4.0]])
    M_sym = symmetrize(M_raw)
    
    # Must have lock
    with pytest.raises(SelectionPolicyNotLocked):
        select_matrix(M_raw, M_sym, policy="raw", methodology_lock_ref=None)
        
    out_raw = select_matrix(M_raw, M_sym, policy="raw", methodology_lock_ref="LOCK")
    np.testing.assert_allclose(out_raw, M_raw)
    
    out_sym = select_matrix(M_raw, M_sym, policy="symmetrized", methodology_lock_ref="LOCK")
    np.testing.assert_allclose(out_sym, M_sym)

def test_compute_diagnostics_and_invert():
    # Good matrix
    M = np.array([[2.0, 0.0], [0.0, 3.0]])
    diag = compute_diagnostics(M)
    assert diag.is_full_rank
    assert diag.numerical_rank == 2
    
    inv_M = invert_matrix(M, diag)
    np.testing.assert_allclose(inv_M, [[0.5, 0.0], [0.0, 1/3]])
    
    inv_chi = invert_chi(M)
    np.testing.assert_allclose(inv_chi, [[0.5, 0.0], [0.0, 1/3]])

def test_ill_conditioned_and_singular():
    # Singular
    M_sing = np.array([[1.0, 1.0], [1.0, 1.0]])
    diag = compute_diagnostics(M_sing, condition_threshold=np.inf)
    assert not diag.is_full_rank
    
    with pytest.raises(SingularMatrixError):
        invert_matrix(M_sing, diag)
        
    # Ill-conditioned
    M_ill = np.array([[1.0, 1.0], [1.0, 1.0 + 1e-8]])
    with pytest.raises(IllConditionedMatrixError):
        compute_diagnostics(M_ill, condition_threshold=100.0)
