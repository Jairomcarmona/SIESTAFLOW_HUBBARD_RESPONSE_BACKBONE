import json
import os
import hashlib
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional

class CampaignState(str, Enum):
    DRAFT = "DRAFT"
    LOCKED = "LOCKED"
    CONVERGENCE_RUNNING = "CONVERGENCE_RUNNING"
    CONVERGED = "CONVERGED"
    LINEAR_RESPONSE_RUNNING = "LINEAR_RESPONSE_RUNNING"
    COMPLETED = "COMPLETED"
    SUSPENDED = "SUSPENDED"

@dataclass
class CampaignManifest:
    name: str = "default_campaign"
    state: CampaignState = CampaignState.DRAFT
    cell_info: Dict[str, Any] = field(default_factory=dict)
    species: Dict[str, Any] = field(default_factory=dict)
    pseudo_hashes: Dict[str, str] = field(default_factory=dict)
    convergence_criteria: Dict[str, Any] = field(default_factory=dict)
    parameters: Dict[str, Any] = field(default_factory=dict)

    def transition(self, new_state: CampaignState):
        valid_transitions = {
            CampaignState.DRAFT: [CampaignState.LOCKED],
            CampaignState.LOCKED: [CampaignState.CONVERGENCE_RUNNING, CampaignState.SUSPENDED],
            CampaignState.CONVERGENCE_RUNNING: [CampaignState.CONVERGED, CampaignState.SUSPENDED],
            CampaignState.CONVERGED: [CampaignState.LINEAR_RESPONSE_RUNNING, CampaignState.SUSPENDED],
            CampaignState.LINEAR_RESPONSE_RUNNING: [CampaignState.COMPLETED, CampaignState.SUSPENDED],
            CampaignState.SUSPENDED: [CampaignState.CONVERGENCE_RUNNING, CampaignState.LINEAR_RESPONSE_RUNNING],
            CampaignState.COMPLETED: []
        }
        if new_state not in valid_transitions.get(self.state, []):
            raise ValueError(f"Invalid transition from {self.state} to {new_state}")
        self.state = new_state

    def to_dict(self):
        return {
            "name": self.name,
            "state": self.state.value,
            "cell_info": self.cell_info,
            "species": self.species,
            "pseudo_hashes": self.pseudo_hashes,
            "convergence_criteria": self.convergence_criteria,
            "parameters": self.parameters
        }

    @classmethod
    def from_dict(cls, data: dict):
        manifest = cls(
            name=data.get("name", "default_campaign"),
            cell_info=data.get("cell_info", {}),
            species=data.get("species", {}),
            pseudo_hashes=data.get("pseudo_hashes", {}),
            convergence_criteria=data.get("convergence_criteria", {}),
            parameters=data.get("parameters", {})
        )
        if "state" in data:
            manifest.state = CampaignState(data["state"])
        return manifest

    def save_to_file(self, path: str):
        temp_path = path + ".tmp"
        with open(temp_path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
        os.replace(temp_path, path)

    @classmethod
    def load_from_file(cls, path: str):
        with open(path, "r") as f:
            data = json.load(f)
        return cls.from_dict(data)

    def update_pseudo_hashes(self, pseudo_dir: str, species_list: list):
        for species in species_list:
            path = os.path.join(pseudo_dir, f"{species}.psf")
            if os.path.exists(path):
                with open(path, "rb") as f:
                    file_hash = hashlib.sha256(f.read()).hexdigest()
                self.pseudo_hashes[species] = file_hash
