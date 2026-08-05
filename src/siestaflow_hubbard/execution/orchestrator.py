from typing import List, Dict, Any, Tuple
import numpy as np

from siestaflow_hubbard.domain.interfaces import BaseBackendAdapter
from siestaflow_hubbard.domain.alpha_grid import AlphaGrid
from siestaflow_hubbard.synthetic_backend.population_generator import OccupationRecord
from siestaflow_hubbard.domain.matrix_pipeline import invert_chi
from siestaflow_hubbard.synthetic_backend.fit_engine import FitEngine


class CampaignOrchestrator:
    """Orchestrates the reference -> SCREENED -> BARE -> Fit -> Inversion pipeline."""

    def __init__(
        self,
        adapter: BaseBackendAdapter,
        alpha_grid: AlphaGrid,
        systems: List[str]
    ):
        self.adapter = adapter
        self.alpha_grid = alpha_grid
        self.systems = systems

    def run_reference(self, system: str, base_fdf: str) -> None:
        """Runs the reference zero-alpha calculation."""
        fdf_path = self.adapter.prepare_input(base_fdf, 0.0, "SCREENED")
        self.adapter.run_simulation(fdf_path, f"{system}_ref.out", 4)

    def run_perturbations(self, system: str, base_fdf: str) -> Tuple[List[OccupationRecord], List[OccupationRecord]]:
        """Runs BARE and SCREENED perturbations for all alphas."""
        screened_records = []
        bare_records = []

        for alpha in self.alpha_grid.alpha_values_ev:
            if alpha == 0.0:
                continue
            
            # SCREENED
            fdf_path_scr = self.adapter.prepare_input(base_fdf, alpha, "SCREENED")
            out_scr = f"{system}_SCREENED_{alpha}.out"
            self.adapter.run_simulation(fdf_path_scr, out_scr, 4)
            scr_rec = self.adapter.extract_occupations(out_scr, "SCREENED", alpha)
            screened_records.extend(scr_rec)

            # BARE
            fdf_path_bare = self.adapter.prepare_input(base_fdf, alpha, "BARE")
            out_bare = f"{system}_BARE_{alpha}.out"
            self.adapter.run_simulation(fdf_path_bare, out_bare, 4)
            bare_rec = self.adapter.extract_occupations(out_bare, "BARE", alpha)
            bare_records.extend(bare_rec)

        return bare_records, screened_records

    def compute_u(self, bare_records: List[OccupationRecord], screened_records: List[OccupationRecord]) -> np.ndarray:
        """Fits matrices and computes U."""
        engine = FitEngine()
        chi_bare = engine.fit_response_matrix(bare_records, "BARE")
        chi_screened = engine.fit_response_matrix(screened_records, "SCREENED")

        return invert_chi(chi_bare) - invert_chi(chi_screened)

    def execute_campaign(self, system_fdf_map: Dict[str, str]) -> Dict[str, np.ndarray]:
        """Executes the full campaign for all systems."""
        results = {}
        for system in self.systems:
            base_fdf = system_fdf_map.get(system)
            if not base_fdf:
                continue
            self.run_reference(system, base_fdf)
            bare_recs, scr_recs = self.run_perturbations(system, base_fdf)
            u_matrix = self.compute_u(bare_recs, scr_recs)
            results[system] = u_matrix
        return results
