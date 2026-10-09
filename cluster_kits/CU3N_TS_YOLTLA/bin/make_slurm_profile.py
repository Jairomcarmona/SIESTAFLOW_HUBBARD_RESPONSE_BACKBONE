#!/usr/bin/env python3
"""Write the serial, pinned Yoltla execution profile."""

import json
import os
from pathlib import Path

root = Path(os.environ["ROOT"])
nodes = int(os.environ["HF_NODES"])
ppn = int(os.environ["HF_PPN"])
executable = (root / "config/siesta-executable.path").read_text().strip()
payload = {
    "target": "slurm",
    "evidence": "VALIDATED_RUNTIME",
    "slurm": {"partition": os.environ["HF_PARTITION"], "account": None, "qos": None},
    "allocation": {
        "nodes": nodes,
        "total_cpus": nodes * ppn,
        "memory": os.environ["HF_MEMORY"],
        "walltime": os.environ["HF_WALLTIME"],
        "max_parallel_steps": 1,
        "shutdown_margin_seconds": int(os.environ["HF_SHUTDOWN_MARGIN_SECONDS"]),
        "termination_grace_seconds": 300,
    },
    "runtime": {
        "module_commands": ["module load python/3.12", "module load siesta/5.4.2"],
        "siesta_executable": executable,
        "exclusive": True,
        "environment": {"OMP_NUM_THREADS": "1"},
        "launcher": {
            "kind": "hydra",
            "command": [str((root / "bin/mpiexec.hydra").resolve())],
            "bootstrap": "ssh",
            "processes_per_node": ppn,
        },
    },
    "task_policy": {"max_attempts": 1, "require_scf_converged": True},
}
out = root / "config/slurm-profile.json"
out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
print("SLURM_PROFILE_WRITTEN config/slurm-profile.json")
