import abc
import numpy as np

class FitterStrategy(abc.ABC):
    @abc.abstractmethod
    def fit(self, alpha_vals: np.ndarray, occupations: np.ndarray) -> tuple[float, float, dict]:
        """
        Fits occupations to alpha_vals and returns:
        (slope, intercept, diagnostics_dict)
        """
        pass

def _compute_diagnostics(alpha_vals: np.ndarray, occupations: np.ndarray, m: float, c: float, A: np.ndarray, weights: np.ndarray = None) -> dict:
    if weights is None:
        weights = np.ones_like(alpha_vals)
        
    residuals = weights * (occupations - (m * alpha_vals + c))
    ss_res = np.sum(residuals**2)
    
    w2 = weights**2
    if np.sum(w2) > 0:
        w_mean = np.average(occupations, weights=w2)
    else:
        w_mean = np.mean(occupations)
    ss_tot = np.sum(w2 * (occupations - w_mean)**2)
    
    diagnostic_status = "FIT_VALID"
    r_squared = float("nan")
    
    if ss_tot < 1e-12:
        diagnostic_status = "CONSTANT_RESPONSE"
    else:
        r_squared = 1.0 - (ss_res / ss_tot)
    
    has_pos = np.any(alpha_vals > 0)
    has_neg = np.any(alpha_vals < 0)
    asymmetry_available = bool(has_pos and has_neg)
    
    if asymmetry_available:
        neg_alpha_res = np.sum(np.abs(residuals[alpha_vals < 0]))
        pos_alpha_res = np.sum(np.abs(residuals[alpha_vals > 0]))
        asymmetry = float(pos_alpha_res - neg_alpha_res)
    else:
        asymmetry = 0.0

    _, s, _ = np.linalg.svd(A)
    design_rank = np.linalg.matrix_rank(A)
    design_condition_number = float(np.linalg.cond(A))
    
    n = len(alpha_vals)
    if n > 2 and ss_tot > 1e-12 and design_rank == 2:
        s_err = np.sqrt(ss_res / (n - 2))
        try:
            cov = s_err**2 * np.linalg.inv(A.T @ A)
            slope_std_err = float(np.sqrt(cov[0, 0]))
        except np.linalg.LinAlgError:
            slope_std_err = float('nan')
    else:
        slope_std_err = float('nan')
        if n < 2:
            diagnostic_status = "INSUFFICIENT_DATA"
        elif design_rank < 2:
            diagnostic_status = "DEGENERATE_RESPONSE"

    return {
        "r_squared": r_squared,
        "residuals": [float(r) for r in residuals],
        "design_condition_number": design_condition_number,
        "design_rank": int(design_rank),
        "design_singular_values": [float(val) for val in s],
        "asymmetry": asymmetry,
        "asymmetry_available": asymmetry_available,
        "slope_std_err": slope_std_err,
        "diagnostic_status": diagnostic_status
    }

class OLSFitterStrategy(FitterStrategy):
    def fit(self, alpha_vals: np.ndarray, occupations: np.ndarray) -> tuple[float, float, dict]:
        n = len(alpha_vals)
        if n < 2:
            A = np.zeros((1, 2)) if n == 0 else np.vstack([alpha_vals, np.ones(n)]).T
            return 0.0, 0.0, _compute_diagnostics(alpha_vals, occupations, 0.0, 0.0, A)
        
        A = np.vstack([alpha_vals, np.ones(len(alpha_vals))]).T
        m, c = np.linalg.lstsq(A, occupations, rcond=None)[0]
        return float(m), float(c), _compute_diagnostics(alpha_vals, occupations, m, c, A)


class WeightedFitterStrategy(FitterStrategy):
    def fit(self, alpha_vals: np.ndarray, occupations: np.ndarray) -> tuple[float, float, dict]:
        n = len(alpha_vals)
        if n < 2:
            A = np.zeros((1, 2)) if n == 0 else np.vstack([alpha_vals, np.ones(n)]).T
            return 0.0, 0.0, _compute_diagnostics(alpha_vals, occupations, 0.0, 0.0, A)
            
        weights = 1.0 / (np.abs(alpha_vals) + 0.1)
        W = np.diag(weights)
        A = np.vstack([alpha_vals, np.ones(len(alpha_vals))]).T
        Aw = W @ A
        yw = W @ occupations
        m, c = np.linalg.lstsq(Aw, yw, rcond=None)[0]
        return float(m), float(c), _compute_diagnostics(alpha_vals, occupations, m, c, Aw, weights=weights)
