import pytest
import numpy as np

def test_swapping_chi0_chi_changes_u(A_2x4, R_BARE_C1, R_SCR_C1, U_TRUE_C1):
    chi0 = A_2x4 @ R_BARE_C1
    chi = A_2x4 @ R_SCR_C1
    U_original = np.linalg.inv(chi0) - np.linalg.inv(chi)
    U_swapped = np.linalg.inv(chi) - np.linalg.inv(chi0)
    np.testing.assert_allclose(U_swapped, -U_original)
