import hashlib
import json
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Tuple, Dict, Any
import numpy as np

def canonical_json(payload: Any) -> str:
    """Recursively converts objects to JSON-serializable types and serializes with sorted keys."""
    def _convert(obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, (np.int64, np.int32)):
            return int(obj)
        elif isinstance(obj, (np.float64, np.float32)):
            return float(obj)
        elif isinstance(obj, dict):
            return {k: _convert(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [_convert(v) for v in obj]
        elif hasattr(obj, '__dict__'):
            return _convert(vars(obj))
        elif hasattr(obj, '__dataclass_fields__'):
            return _convert(asdict(obj))
        else:
            return obj
            
    clean_payload = _convert(payload)
    return json.dumps(clean_payload, sort_keys=True, separators=(',', ':'))

def compute_artifact_id(payload: Any) -> str:
    """Computes SHA-256 hash of the canonical JSON payload."""
    payload_str = canonical_json(payload)
    return hashlib.sha256(payload_str.encode("utf-8")).hexdigest()

@dataclass(kw_only=True)
class ScientificArtifact:
    """Base class for auditable scientific artifacts."""
    artifact_id: str = field(init=False)
    artifact_type: str = field(init=False)
    schema_version: str = "1.0.0"
    methodology_lock_hash: str = ""
    source_artifact_ids: List[str] = field(default_factory=list)
    
    def generate_identity(self, payload: Any):
        self.artifact_id = compute_artifact_id(payload)

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
class ResponseMatrix(ScientificArtifact):
    """Explicit provenance wrapper for response matrices (R0, R, chi0, chi)."""
    matrix: np.ndarray
    row_ids: List[str]
    column_ids: List[str]
    units: str
    regression_ids: Dict[Tuple[str, str], List[str]] = field(default_factory=dict)
    
    raw_matrix: Optional[np.ndarray] = None
    symmetrized_matrix: Optional[np.ndarray] = None
    antisymmetry_norm: float = 0.0
    
    def __post_init__(self):
        self.artifact_type = "ResponseMatrix"
        shape = self.matrix.shape
        if len(self.row_ids) != shape[0] or len(self.column_ids) != shape[1]:
            raise ValueError(
                f"Matrix shape {shape} does not match explicit identities: "
                f"rows={len(self.row_ids)}, cols={len(self.column_ids)}"
            )
            
        payload = {
            "artifact_type": self.artifact_type,
            "schema_version": self.schema_version,
            "units": self.units,
            "matrix": self.matrix,
            "raw_matrix": self.raw_matrix,
            "symmetrized_matrix": self.symmetrized_matrix,
            "antisymmetry_norm": self.antisymmetry_norm,
            "row_ids": self.row_ids,
            "column_ids": self.column_ids,
            "regression_ids": {f"{r}_{c}": v for (r, c), v in self.regression_ids.items()},
            "methodology_lock_hash": self.methodology_lock_hash,
            "source_artifact_ids": self.source_artifact_ids
        }
        self.generate_identity(payload)

    @property
    def shape(self) -> Tuple[int, int]:
        return self.matrix.shape
