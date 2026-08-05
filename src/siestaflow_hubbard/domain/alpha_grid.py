from dataclasses import dataclass
from typing import List

@dataclass(frozen=True)
class AlphaGrid:
    alpha_values_ev: List[float]
    K_p: int
    symmetric_pairs: bool
    k_negative: int
    k_zero: int
    k_positive: int

    def __post_init__(self):
        if self.K_p != len(self.alpha_values_ev):
            raise ValueError(f"K_p {self.K_p} != len(alpha_values_ev) {len(self.alpha_values_ev)}")

    def is_fully_evaluable(self) -> bool:
        return (
            self.K_p >= 5 and
            self.k_negative >= 2 and
            self.k_zero >= 1 and
            self.k_positive >= 2 and
            self.symmetric_pairs
        )
