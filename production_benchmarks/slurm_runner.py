from dataclasses import dataclass

@dataclass
class SlurmProfile:
    partition: str
    nodes: int
    ntasks_total: int
    cpus_per_task: int
    mem_per_node: int
    walltime: str
    siesta_binary: str
    mpi_launcher: str

def calculate_ranks_per_run(ntasks_total, max_concurrent) -> int:
    return ntasks_total // max_concurrent

def generate_slurm_script(profile, campaign_dir, material, dag_node, run_ids, n_concurrent) -> str:
    return ""

def write_slurm_script(script_str, output_path):
    pass

def estimate_run_counts(material_config, convergence_dims) -> dict:
    return {}
