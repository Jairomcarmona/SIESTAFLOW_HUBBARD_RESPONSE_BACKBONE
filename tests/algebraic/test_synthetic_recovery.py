import pytest
import numpy as np
from siestaflow_hubbard.synthetic_backend.recovery import recover_U
from siestaflow_hubbard.domain.cardinals import Cardinals

def test_synthetic_recovery():
    # Test recover_U without cardinals
    # U = inv(chi0) - inv(chi)
    chi0 = np.array([[2.0, 0.0], [0.0, 2.0]])
    chi = np.array([[1.0, 0.0], [0.0, 1.0]])
    # inv(chi0) = 0.5 * I, inv(chi) = I
    # U = 0.5 * I - I = -0.5 * I
    
    U_recovered = recover_U(chi0, chi)
    np.testing.assert_allclose(U_recovered, [[-0.5, 0.0], [0.0, -0.5]])
    
    # Test with cardinals
    # cardinals.chi = A @ R
    from unittest.mock import MagicMock
    c = MagicMock()
    c.chi.side_effect = lambda x: x
    
    U_card = recover_U(chi0, chi, cardinals=c)
    np.testing.assert_allclose(U_card, [[-0.5, 0.0], [0.0, -0.5]])

def test_synthetic_recovery_asymmetric():
    # numerical noise in chi0
    chi0 = np.array([[2.0, 0.1], [-0.1, 2.0]])
    chi = np.array([[1.0, 0.0], [0.0, 1.0]])
    
    # invert_chi(chi0) = (1/4.01) * [[2.0, -0.1], [0.1, 2.0]]
    # U_raw = [[2/4.01 - 1, -0.1/4.01], [0.1/4.01, 2/4.01 - 1]]
    # U_sym will be exactly symmetric
    
    U_recovered = recover_U(chi0, chi)
    
    # Ensure it's symmetrized
    np.testing.assert_allclose(U_recovered, U_recovered.T)
    # diagonal elements
    diag_val = 2.0/4.01 - 1.0
    np.testing.assert_allclose(np.diag(U_recovered), [diag_val, diag_val])
    # off-diagonal elements are 0 because it's anti-symmetric in U_raw and we take symmetric part
    np.testing.assert_allclose(U_recovered[0, 1], 0.0)
    np.testing.assert_allclose(U_recovered[1, 0], 0.0)
