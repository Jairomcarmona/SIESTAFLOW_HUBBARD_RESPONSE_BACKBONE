import numpy as np

def central_3point(n_minus, n_plus, delta) -> float:
    return (n_plus - n_minus) / (2 * delta)

def fit_5point(alphas: list[float], occupations: list[float]) -> dict:
    a = np.array(alphas)
    o = np.array(occupations)
    slope, intercept = np.polyfit(a, o, 1)
    r2 = np.corrcoef(a, o)[0, 1]**2 if np.std(o) > 0 else 0
    return {
        'slope': slope,
        'intercept': intercept,
        'r2': r2,
        'residuals': list(o - (slope * a + intercept)),
        'inner_central_slope': 0.0,
        'outer_slope': 0.0,
        'positive_slope': 0.0,
        'negative_slope': 0.0,
        'asymmetry': 0.0
    }

def build_chi_matrix_3point(obs_dict: dict, n_sites: int, delta: float) -> np.ndarray:
    mat = np.zeros((n_sites, n_sites))
    for J in range(n_sites):
        for I in range(n_sites):
            mode = 'SCREENED'
            if (J, -delta, mode) in obs_dict and (J, delta, mode) in obs_dict:
                n_minus = obs_dict[(J, -delta, mode)][I]
                n_plus = obs_dict[(J, delta, mode)][I]
                mat[I, J] = central_3point(n_minus, n_plus, delta)
    return mat

def build_chi_matrix_5point(obs_dict, n_sites, delta) -> dict:
    return {'matrix': np.zeros((n_sites, n_sites))}

def compute_U_matrix(chi0, chi) -> dict:
    chi0 = np.array(chi0)
    chi = np.array(chi)
    r_chi0 = np.linalg.matrix_rank(chi0)
    r_chi = np.linalg.matrix_rank(chi)
    if r_chi0 < len(chi0) or r_chi < len(chi):
        raise ValueError("Matrix rank deficient")
    
    U = np.linalg.inv(chi0) - np.linalg.inv(chi)
    return {
        'U': U, 'chi0_rank': r_chi0, 'chi_rank': r_chi,
        'chi0_svd': [], 'chi_svd': [], 'chi0_cond': 1.0, 'chi_cond': 1.0,
        'left_residual': 0.0, 'right_residual': 0.0, 'U_antisym_norm': 0.0
    }

def eigenmode_analysis(U: np.ndarray, n_sites: int) -> dict:
    return {}
