import pytest
import numpy as np
from siestaflow_hubbard.execution.orchestrator import CampaignOrchestrator
from siestaflow_hubbard.domain.alpha_grid import AlphaGrid
from tests.unit.test_interfaces import MockAdapter
from siestaflow_hubbard.synthetic_backend.population_generator import OccupationRecord

class OrchestratorMockAdapter(MockAdapter):
    def extract_occupations(self, out_filename: str, mode: str = "SCREENED", alpha: float = 0.0) -> list:
        # returns dummy occupation records to make fit_engine happy
        return [
            OccupationRecord(
                response_mode=mode,
                channel_index=0,
                alpha_ev=alpha,
                observable_index=0,
                occupation=1.0 + alpha
            )
        ]

def test_campaign_orchestrator():
    adapter = OrchestratorMockAdapter()
    alpha_grid = AlphaGrid(alpha_values_ev=[0.0, 0.1, 0.2], K_p=3, symmetric_pairs=False, k_negative=0, k_zero=1, k_positive=2)
    orchestrator = CampaignOrchestrator(adapter, alpha_grid, ["sysA"])
    
    # Overwrite compute_u for a simpler test, or let it run
    results = orchestrator.execute_campaign({"sysA": "sysA.fdf"})
    assert "sysA" in results
    assert isinstance(results["sysA"], np.ndarray)
