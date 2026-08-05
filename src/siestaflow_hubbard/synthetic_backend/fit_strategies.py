import abc
import numpy as np

class FitterStrategy(abc.ABC):
    @abc.abstractmethod
    def fit(self, alpha_vals: np.ndarray, occupations: np.ndarray) -> tuple[float, float]:
        """Fits occupations to alpha_vals and returns (slope, intercept)."""
        pass


class OLSFitterStrategy(FitterStrategy):
    def fit(self, alpha_vals: np.ndarray, occupations: np.ndarray) -> tuple[float, float]:
        if len(alpha_vals) < 2:
            return 0.0, 0.0
        A = np.vstack([alpha_vals, np.ones(len(alpha_vals))]).T
        m, c = np.linalg.lstsq(A, occupations, rcond=None)[0]
        return float(m), float(c)


class WeightedFitterStrategy(FitterStrategy):
    def fit(self, alpha_vals: np.ndarray, occupations: np.ndarray) -> tuple[float, float]:
        if len(alpha_vals) < 2:
            return 0.0, 0.0
        # Example weighting: higher weight for smaller alphas
        weights = 1.0 / (np.abs(alpha_vals) + 0.1)
        W = np.diag(weights)
        A = np.vstack([alpha_vals, np.ones(len(alpha_vals))]).T
        Aw = W @ A
        yw = W @ occupations
        m, c = np.linalg.lstsq(Aw, yw, rcond=None)[0]
        return float(m), float(c)
