from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict
import numpy as np

@dataclass(frozen=True)
class PerturbationIdentity:
    """Explicit identity for a single perturbation channel."""
    channel_id: str
    target_subspace_id: str
    projector_identity: str
    alpha_grid_hash: str

@dataclass(frozen=True)
class ObservableIdentity:
    """Explicit identity for a single observable channel."""
    channel_id: str
    subspace_id: str
    occupation_definition: str

@dataclass
class ResponseMatrix:
    """Explicit provenance wrapper for response matrices (R0, R, chi0, chi)."""
    matrix: np.ndarray
    row_ids: List[str]
    column_ids: List[str]
    units: str
    regression_ids: Dict[Tuple[str, str], str] = field(default_factory=dict)
    methodology_lock_hash: str = "TBD"

    def __post_init__(self):
        shape = self.matrix.shape
        if len(self.row_ids) != shape[0] or len(self.column_ids) != shape[1]:
            raise ValueError(
                f"Matrix shape {shape} does not match explicit identities: "
                f"rows={len(self.row_ids)}, cols={len(self.column_ids)}"
            )

    @property
    def shape(self) -> Tuple[int, int]:
        return self.matrix.shape
