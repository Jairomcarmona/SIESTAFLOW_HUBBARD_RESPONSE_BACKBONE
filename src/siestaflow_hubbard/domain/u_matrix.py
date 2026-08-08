from dataclasses import dataclass
from typing import List, Optional, Any
from enum import Enum
import numpy as np


class GaugeRankStatus(Enum):
    """
    Categorizes the theoretical rank/gauge status of the calculated Hubbard U matrix.
    """
    FULL_RANK = "FULL_RANK"
    PHYSICAL_GAUGE_MODE = "PHYSICAL_GAUGE_MODE"
    RANK_DEFICIENT_INVALID = "RANK_DEFICIENT_INVALID"
    ILL_CONDITIONED = "ILL_CONDITIONED"


@dataclass(frozen=True)
class NumericalPolicy:
    """
    Configures the tolerances and acceptance criteria for numerical inversion and matrix conditions.
    """
    max_condition_number: Optional[float] = None
    zero_tolerance: float = 1e-12
    allow_pinv_fallback: bool = False
    enforce_physical_gauge: bool = False


from .provenance import ScientificArtifact

@dataclass
class HubbardInteractionMatrix(ScientificArtifact):
    """
    Strict provenance-bearing container for the calculated Hubbard U interaction matrix.
    """
    row_subspace_ids: List[str]
    column_subspace_ids: List[str]
    values: np.ndarray
    chi0_source_id: str
    chi_source_id: str
    rank_diagnostics: GaugeRankStatus
    condition_diagnostics: float
    inverse_residuals: float
    uncertainty_info: Any  # TBD for full uncertainty quantification
    units: str = "eV"
    
    raw_values: Optional[np.ndarray] = None
    symmetrized_values: Optional[np.ndarray] = None
    antisymmetry_norm: float = 0.0
    
    # Explicitly enforce separation of human decision from the bare matrix computation
    recommended_single_U_ev: Optional[float] = None

    def __post_init__(self):
        """
        Enforce dimensional consistency between row/column IDs and the underlying numpy array.
        """
        self.artifact_type = "HubbardInteractionMatrix"
        O = len(self.row_subspace_ids)
        P = len(self.column_subspace_ids)
        
        if self.values.shape != (O, P):
            raise ValueError(
                f"Matrix shape mismatch. Expected ({O}, {P}) based on subspace IDs, "
                f"but got {self.values.shape}."
            )
            
        payload = {
            "artifact_type": self.artifact_type,
            "schema_version": self.schema_version,
            "units": self.units,
            "matrix": self.values,
            "raw_matrix": self.raw_values,
            "symmetrized_matrix": self.symmetrized_values,
            "antisymmetry_norm": self.antisymmetry_norm,
            "row_subspace_ids": self.row_subspace_ids,
            "column_subspace_ids": self.column_subspace_ids,
            "chi0_source_id": self.chi0_source_id,
            "chi_source_id": self.chi_source_id,
            "rank_diagnostics": self.rank_diagnostics.name,
            "condition_diagnostics": self.condition_diagnostics,
            "inverse_residuals": self.inverse_residuals,
            "methodology_lock_hash": self.methodology_lock_hash,
            "source_artifact_ids": self.source_artifact_ids
        }
        self.generate_identity(payload)
