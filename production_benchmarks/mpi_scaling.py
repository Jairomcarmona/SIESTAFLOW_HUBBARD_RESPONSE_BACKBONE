from dataclasses import dataclass

@dataclass
class MPIScalingConfig:
    ranks_to_test: list
    n_scf_iterations: int
    material_label: str

def generate_scaling_fdf(base_fdf_content, n_scf_iters, label) -> str:
    return ""

def parse_scaling_result(out_text) -> dict:
    return {}

def recommend_mpi_config(scaling_results: list) -> dict:
    return {}
