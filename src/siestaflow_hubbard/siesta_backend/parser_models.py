from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional
import numpy as np

class ObservationRole(Enum):
    UNCLASSIFIED = "UNCLASSIFIED"
    REFERENCE = "REFERENCE"
    CANDIDATE_BARE = "CANDIDATE_BARE"
    CANDIDATE_SCREENED = "CANDIDATE_SCREENED"

@dataclass(frozen=True)
class ObservationContext:
    siesta_version: str
    calculation_mode: str
    reference_dm_sha256: Optional[str]
    projector_fingerprint: str

    scf_mix_target: Optional[str]
    scf_mixer_method: Optional[str]
    scf_mixer_weight: Optional[float]
    max_scf_iterations: Optional[int]

    convergence_confirmed: bool
    final_scf_iteration: Optional[int]
    post_scf_population_occurrence: Optional[int]

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

from ..domain.provenance import ScientificArtifact

@dataclass
class ObservationSelection(ScientificArtifact):
    role: ObservationRole
    policy_id: str
    evidence: str
    event: HubbardPopulationEvent

    def __post_init__(self):
        self.artifact_type = "ObservationSelection"
        payload = {
            "artifact_type": self.artifact_type,
            "schema_version": self.schema_version,
            "role": self.role.name,
            "policy_id": self.policy_id,
            "evidence": self.evidence,
            "event_occurrence_index": self.event.occurrence_index,
            "methodology_lock_hash": self.methodology_lock_hash,
            "source_artifact_ids": self.source_artifact_ids
        }
        self.generate_identity(payload)
