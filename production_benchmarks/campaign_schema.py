from dataclasses import dataclass
from typing import List, Dict, Optional, Any
from enum import Enum
import hashlib
import json

@dataclass
class MaterialConfig:
    name: str
    structure_file: str
    n_sites: int
    n_species: int
    spin_mode: str
    pseudopotentials: Dict[str, Any]
    correlated_manifold: Dict[str, Any]

@dataclass
class ProjectorSpec:
    species: str
    n: int
    l: int
    rc_bohr: float
    omega_bohr: float

@dataclass
class ConvergenceStep:
    dimension: str
    values: List[Any]
    accepted_value: Optional[Any] = None

@dataclass
class CampaignDimensions:
    basis: str
    energy_shift_ry: float
    mesh_cutoff_ry: float
    kgrid: List[int]
    supercell_matrix: List[List[int]]
    projector_rc_bohr: float
    projector_omega_bohr: float
    alpha_grid_ev: List[float]
    n_alpha_points: int

class LRMode(Enum):
    SCREENING_3POINT = "SCREENING_3POINT"
    FINAL_5POINT = "FINAL_5POINT"

class MaterialDAGStatus(Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    REFERENCE_ACCEPTED = "REFERENCE_ACCEPTED"
    SCREENING = "SCREENING"
    CONVERGED = "CONVERGED"
    FINAL = "FINAL"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"

@dataclass
class CalculationIdentity:
    geometry_sha256: str
    species_map: str
    pseudopotential_sha256s: str
    siesta_version: str
    spin_mode: str
    basis: str
    energy_shift_ry: float
    mesh_cutoff_ry: float
    kgrid: str
    supercell: str
    projector_method: int
    projector_nl: str
    projector_rc: float
    projector_omega: float
    alpha: float
    perturbed_site: int
    mode: str
    reference_dm_sha256: str

    def compute_key(self) -> str:
        d = self.__dict__.copy()
        s = json.dumps(d, sort_keys=True)
        return hashlib.sha256(s.encode()).hexdigest()
