import numpy as np
from siestaflow_hubbard.domain.semantic_validation import SemanticValidator
from siestaflow_hubbard.domain.matrix_pipeline import symmetrize

def test_matrix_constraints():
    assert isinstance(SemanticValidator().validate_campaign(None), list)

def test_raw_vs_symmetrized_u_matrix_numerical_difference():
    chi0_raw = np.array([[-8.0, 0.5], [0.2, -7.5]])
    chi_raw = np.array([[-0.2, 0.05], [0.01, -0.15]])
    
    U_from_raw = np.linalg.inv(chi0_raw) - np.linalg.inv(chi_raw)
    U_from_pre_sym = np.linalg.inv(symmetrize(chi0_raw)) - np.linalg.inv(symmetrize(chi_raw))
    
    diff = U_from_raw - U_from_pre_sym
    rel_diff = np.linalg.norm(diff, 'fro') / np.linalg.norm(U_from_raw, 'fro')
    
    # Proves numerically that pre-inversion symmetrization alters the inverted result
    assert rel_diff > 0.05
    assert not np.allclose(U_from_raw, U_from_pre_sym)
