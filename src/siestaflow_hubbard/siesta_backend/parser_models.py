from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional
import numpy as np

class ObservationRole(Enum):
    UNCLASSIFIED = "UNCLASSIFIED"
    REFERENCE = "REFERENCE"
    CANDIDATE_BARE = "CANDIDATE_BARE"
    CANDIDATE_SCREENED = "CANDIDATE_SCREENED"

@dataclass
class HubbardAtomPopulation:
    """Immutable representation of a single atom's population event."""
    atom_index: int
    species_index: int
    raw_matrix_up: np.ndarray
    raw_matrix_down: Optional[np.ndarray]
    channel_count: int
    trace_up: float
    trace_down: float
    trace_total: float
    printed_total_trace: float
    printed_up_trace: Optional[float] = None
    printed_down_trace: Optional[float] = None
    
    def validate_traces(self, tol: float = 1e-4) -> bool:
        """Validates that computed diagonal traces match the printed summary."""
        if self.printed_up_trace is not None and abs(self.trace_up - self.printed_up_trace) > tol:
            return False
        if self.printed_down_trace is not None and abs(self.trace_down - self.printed_down_trace) > tol:
            return False
        if abs(self.trace_total - self.printed_total_trace) > tol:
            return False
        return True

@dataclass
class HubbardPopulationEvent:
    """Immutable representation of a complete population recalculation event."""
    occurrence_index: int
    dftu_population_iteration: Optional[int]
    scf_iteration: Optional[int]
    context: str
    atoms: List[HubbardAtomPopulation] = field(default_factory=list)
    source_start_line: Optional[int] = None
    source_end_line: Optional[int] = None
    role: ObservationRole = ObservationRole.UNCLASSIFIED
