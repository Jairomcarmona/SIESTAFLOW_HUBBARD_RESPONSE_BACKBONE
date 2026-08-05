import pytest
import numpy as np

from siestaflow_hubbard.domain.cardinals import Cardinals
from siestaflow_hubbard.domain.exceptions import (
    CardinalConstraintViolation,
    AggregationShapeViolation,
    IllConditionedMatrixError,
    SingularMatrixError,
    InversionResidualFailure,
    SelectionPolicyNotLocked,
    SiestaflowError
)
from siestaflow_hubbard.domain.matrix_pipeline import (
    assemble_raw,
    compute_antisymmetry,
    symmetrize,
    select_matrix,
    compute_diagnostics,
    invert_matrix
)
from siestaflow_hubbard.domain.alpha_grid import AlphaGrid

from siestaflow_hubbard.synthetic_backend.recovery import recover_U

def make_dummy_alpha_grids(p_count=2):
    grid = AlphaGrid(
        alpha_values_ev=[-0.10, -0.05, 0.0, 0.05, 0.10],
        K_p=5,
        symmetric_pairs=True,
        k_negative=2,
        k_zero=1,
        k_positive=2
    )
    return {f"P{i}": grid for i in range(p_count)}

# --- 1. CARDINAL & SHAPE ADVERSARIAL ATTACKS ---

def test_attack_p_not_equal_n():
    """ADVERSARIAL: Attempting to instantiate Cardinals with P != N must fail immediately."""
    A = np.ones((2, 4))
    grids = make_dummy_alpha_grids(p_count=3)
    with pytest.raises(CardinalConstraintViolation):
        Cardinals(P=3, O=4, N=2, alpha_grids=grids, A=A)

def test_attack_a_shape_mismatch():
    """ADVERSARIAL: Attempting to supply A matrix with wrong shape must fail."""
    A = np.ones((3, 4))  # N=2 expected
    grids = make_dummy_alpha_grids(p_count=2)
    with pytest.raises(AggregationShapeViolation):
        Cardinals(P=2, O=4, N=2, alpha_grids=grids, A=A)

def test_attack_r_shape_mismatch():
    """ADVERSARIAL: Passing R matrix with wrong dimensions to chi() must raise AggregationShapeViolation."""
    A = np.ones((2, 4))
    grids = make_dummy_alpha_grids(p_count=2)
    card = Cardinals(P=2, O=4, N=2, alpha_grids=grids, A=A)
    R_invalid = np.ones((3, 2))  # Expected (4, 2)
    with pytest.raises(AggregationShapeViolation):
        card.chi(R_invalid)

# --- 2. MATRIX PIPELINE & NUMERICAL STABILITY ATTACKS ---

def test_attack_singular_matrix_inversion():
    """ADVERSARIAL: Attempting direct inversion on a rank-deficient matrix must raise SingularMatrixError or IllConditionedMatrixError."""
    M_singular = np.array([[1.0, 2.0], [2.0, 4.0]])
    with pytest.raises((SingularMatrixError, IllConditionedMatrixError)):
        diag = compute_diagnostics(M_singular, condition_threshold=1e18)
        invert_matrix(M_singular, diag, tolerance=1e-10)

def test_attack_ill_conditioned_matrix():
    """ADVERSARIAL: Matrix with condition number exceeding threshold must be rejected."""
    M_ill = np.array([[1.0, 1.0], [1.0, 1.0 + 1e-12]])
    with pytest.raises(IllConditionedMatrixError):
        compute_diagnostics(M_ill, condition_threshold=1000.0)

def test_attack_selection_policy_unlocked():
    """ADVERSARIAL: Selecting a matrix without providing methodology_lock_ref must fail."""
    M_raw = np.array([[-1.0, -0.1], [-0.1, -1.0]])
    M_sym = np.array([[-1.0, -0.1], [-0.1, -1.0]])
    with pytest.raises(SelectionPolicyNotLocked):
        select_matrix(M_raw, M_sym, policy="symmetrized", methodology_lock_ref=None)

def test_attack_invalid_selection_policy():
    """ADVERSARIAL: Attempting to use an unsupported selection policy must raise ValueError."""
    M_raw = np.array([[-1.0, -0.1], [-0.1, -1.0]])
    M_sym = np.array([[-1.0, -0.1], [-0.1, -1.0]])
    with pytest.raises(ValueError):
        select_matrix(M_raw, M_sym, policy="pseudoinverse_magic", methodology_lock_ref="LOCK_123")

# --- 3. ALPHA GRID ADVERSARIAL ATTACKS ---

def test_attack_incomplete_alpha_grid():
    """ADVERSARIAL: Alpha grid missing negative or positive points must flag gate ineligibility."""
    grid = AlphaGrid(
        alpha_values_ev=[0.0, 0.05, 0.10],
        K_p=3,
        symmetric_pairs=False,
        k_negative=0,
        k_zero=1,
        k_positive=2
    )
    assert grid.is_fully_evaluable() is False

def test_attack_unsymmetric_alpha_grid():
    """ADVERSARIAL: Asymmetric alpha grid must be flagged."""
    grid = AlphaGrid(
        alpha_values_ev=[-0.10, -0.05, 0.0, 0.05, 0.20],
        K_p=5,
        symmetric_pairs=False,
        k_negative=2,
        k_zero=1,
        k_positive=2
    )
    assert grid.symmetric_pairs is False
    assert grid.is_fully_evaluable() is False

# --- 4. RECOVERY ADVERSARIAL ATTACKS ---

def test_attack_corrupted_response_in_recovery():
    """ADVERSARIAL: If response matrix chi is singular, recover_U must fail gracefully with domain exception."""
    A = np.array([[1.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 1.0]])
    grids = make_dummy_alpha_grids(p_count=2)
    cardinals = Cardinals(P=2, O=4, N=2, alpha_grids=grids, A=A)
    
    R_bare = np.array([[-0.50, -0.05], [-0.50, -0.05], [-0.05, -0.50], [-0.05, -0.50]])
    R_screened_corrupted = np.array([[-0.40, -0.40], [-0.40, -0.40], [-0.40, -0.40], [-0.40, -0.40]])
    
    with pytest.raises((IllConditionedMatrixError, SingularMatrixError, SiestaflowError)):
        recover_U(R_bare, R_screened_corrupted, cardinals, condition_threshold=1000.0)
