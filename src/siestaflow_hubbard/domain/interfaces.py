import abc
from typing import List

class BaseBackendAdapter(abc.ABC):
    @abc.abstractmethod
    def prepare_input(self, fdf_template: str, alpha: float, mode: str) -> str:
        """Prepare input for simulation."""
        pass

    @abc.abstractmethod
    def run_simulation(self, fdf_filename: str, out_filename: str, n_procs: int) -> None:
        """Run the simulation."""
        pass

    @abc.abstractmethod
    def extract_occupations(self, out_filename: str) -> List[float]:
        """Extract occupations from output."""
        pass
