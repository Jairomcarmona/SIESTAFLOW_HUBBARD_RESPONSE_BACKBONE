#!/usr/bin/env python3
"""Record code, binary, scheduler, and input provenance for one job."""

import hashlib
import json
import os
import platform
import socket
import subprocess
import sys
import time
from pathlib import Path

import hubbardflow
import numpy

root = Path(os.environ["ROOT"])
tag = sys.argv[1]
vendor = root / "vendor/hubbardflow-src"
commit = subprocess.run(
    ["git", "rev-parse", "HEAD"], cwd=vendor, check=True, capture_output=True, text=True
).stdout.strip()
expected_commit = (root / "vendor/HUBBARDFLOW_COMMIT.txt").read_text().strip()
if commit != expected_commit:
    raise SystemExit("ERROR: vendor commit differs from the required pin")


def sha(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


data = {
    "schema": "cu3n_ts_yoltla.provenance.v1",
    "tag": tag,
    "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "host": socket.gethostname(),
    "user": os.environ.get("USER"),
    "python": sys.version.split()[0],
    "numpy": numpy.__version__,
    "platform": platform.platform(),
    "module_list": os.environ.get("HF_MODULE_LIST", ""),
    "hubbardflow_file": hubbardflow.__file__,
    "hubbardflow_commit": commit,
    "hubbardflow_tree_clean": subprocess.run(
        ["git", "status", "--porcelain"], cwd=vendor, check=True,
        capture_output=True, text=True
    ).stdout.strip() == "",
    "expected_commit": expected_commit,
    "siesta_executable": (root / "config/siesta-executable.path").read_text().strip(),
    "siesta_sha256": sha(
        Path((root / "config/siesta-executable.path").read_text().strip())
    ),
    "slurm": {
        key: os.environ.get(key)
        for key in (
            "SLURM_JOB_ID", "SLURM_JOB_PARTITION", "SLURM_JOB_NODELIST",
            "SLURM_NNODES", "SLURM_NTASKS", "SLURM_CPUS_PER_TASK",
            "SLURM_SUBMIT_DIR", "SLURM_JOB_END_TIME",
        )
    },
    "file_sha256": {
        relative: sha(root / relative)
        for relative in (
            "inputs/reference.fdf", "config/lr-config.json",
            "config/slurm-profile.json", "config/backend_compatibility.json",
            "config/siesta-version.txt", "bin/mpiexec.hydra",
            "inputs/INPUTS.sha256",
        )
    },
    "pseudopotential_sha256": {
        path.name: sha(path) for path in sorted((root / "inputs").glob("*.psml"))
    },
}
if not data["hubbardflow_tree_clean"]:
    raise SystemExit("ERROR: vendored source tree has local changes")
results = root / "results"
results.mkdir(exist_ok=True)
out = results / f"provenance_{tag}.json"
out.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print("PROVENANCE_WRITTEN", out.relative_to(root))
