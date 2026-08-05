import pytest
from siestaflow_hubbard.domain.interfaces import BaseBackendAdapter

class MockAdapter(BaseBackendAdapter):
    def prepare_input(self, fdf_template: str, alpha: float, mode: str) -> str:
        return f"{fdf_template}_{alpha}_{mode}"
    def run_simulation(self, fdf_filename: str, out_filename: str, n_procs: int) -> None:
        pass
    def extract_occupations(self, out_filename: str) -> list:
        return [1.0, 2.0]

def test_interface_instantiation():
    adapter = MockAdapter()
    assert adapter.prepare_input("test", 1.0, "BARE") == "test_1.0_BARE"
    assert adapter.extract_occupations("out") == [1.0, 2.0]
