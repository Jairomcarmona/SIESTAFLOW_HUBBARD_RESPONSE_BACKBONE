import pytest
import numpy as np

@pytest.fixture
def A_2x4():
    return np.array([[1.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 1.0]])

@pytest.fixture
def ALPHA_SYMMETRIC():
    return [-0.10, -0.05, 0.00, 0.05, 0.10]

@pytest.fixture
def INTERCEPTS():
    return np.array([2.5, 2.5, 2.5, 2.5])

@pytest.fixture
def R_BARE_C1():
    return np.array([[-0.50, -0.05], [-0.50, -0.05], [-0.05, -0.50], [-0.05, -0.50]])

@pytest.fixture
def R_SCR_C1():
    return np.array([[-0.40, -0.04], [-0.40, -0.04], [-0.04, -0.40], [-0.04, -0.40]])

@pytest.fixture
def U_TRUE_C1():
    return np.array([[0.25252525252525254, -0.025252525252525245], [-0.025252525252525245, 0.25252525252525254]])
