from dataclasses import dataclass
import numpy as np
from typing import Dict
from .alpha_grid import AlphaGrid
from .exceptions import CardinalConstraintViolation, AggregationShapeViolation

@dataclass(frozen=True)
class Cardinals:
    P: int
    O: int
    N: int
    alpha_grids: Dict[str, AlphaGrid]
    A: np.ndarray
    A_version: str = "v0.1.0"

    def __post_init__(self):
        if self.P != self.N:
            raise CardinalConstraintViolation(
                f"v0.1.0: P must equal N. Got P={self.P}, N={self.N}. "
                f"P≠N requires B-transform (OD-007, deferred to v0.2.0)."
            )
        if self.A.shape != (self.N, self.O):
            raise AggregationShapeViolation(f"Aggregation matrix A shape {self.A.shape} != ({self.N}, {self.O})")
        if len(self.alpha_grids) != self.P:
            raise CardinalConstraintViolation(f"Number of alpha grids {len(self.alpha_grids)} != P {self.P}")
        if self.N > self.O:
            raise CardinalConstraintViolation(f"Subspaces N ({self.N}) cannot exceed observables O ({self.O})")

    @property
    def total_records_per_mode(self) -> int:
        """O × Σ(K_p for p in channels)"""
        return self.O * sum(g.K_p for g in self.alpha_grids.values())

    def chi(self, R: np.ndarray) -> np.ndarray:
        """chi = A @ R; shape (N, N) when P=N."""
        if R.shape != (self.O, self.P):
            raise AggregationShapeViolation(f"Slope matrix R shape {R.shape} != ({self.O}, {self.P})")
        result = self.A @ R
        if result.shape != (self.N, self.N):
            raise AggregationShapeViolation(f"Resulting chi shape {result.shape} != ({self.N}, {self.N})")
        return result
