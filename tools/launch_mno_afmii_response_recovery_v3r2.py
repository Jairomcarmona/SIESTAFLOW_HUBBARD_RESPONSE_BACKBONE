#!/usr/bin/env python3
"""Submit one autonomous, fresh MnO response recovery allocation.

This is operational recovery only: it invokes the frozen scientific worker
unchanged, writes to a new evidence root, and analyzes only a complete receipt.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "tools" / "run_mno_afmii_response_v3r2.py"
RECOVERY_ROOT = "response-matrix-foreground-recovery-v3"


def main() -> int:
    environment = {**os.environ, "SIESTAFLOW_MNO_RESPONSE_RESULTS": RECOVERY_ROOT}
    verified = subprocess.run([sys.executable, str(RUNNER), "verify"], cwd=ROOT, text=True, capture_output=True,
                              env=environment)
    if verified.returncode:
        print(verified.stderr, file=sys.stderr, end="")
        return verified.returncode
    command_source = (
        "from pathlib import Path; import os, sys; "
        f"os.environ['SIESTAFLOW_MNO_RESPONSE_RESULTS'] = {RECOVERY_ROOT!r}; "
        f"sys.path.insert(0, {str(ROOT / 'tools')!r}); "
        "import run_mno_afmii_response_v3r2 as r; "
        "print(r._frozen_wheel_wrapper(r.RESULTS.with_suffix('.runtime')) + '; ' + "
        "'env SIESTAFLOW_MNO_RESPONSE_RESULTS=' + r.RESULTS.name + ' -u PYTHONPATH ' + "
        "str(r.RESULTS.with_suffix('.runtime') / 'bin/python') + ' ' + str(Path(r.__file__)) + ' analyze')"
    )
    wrapper = subprocess.run([sys.executable, "-c", command_source], cwd=ROOT, text=True, capture_output=True, check=True).stdout.strip()
    command = ["sbatch", "--wait", "--no-requeue", "--parsable", "-p", "local", "-N", "1", "-n", "4", "-c", "1", "--exclusive",
               "--export=NONE,OMP_NUM_THREADS=1", "--wrap", wrapper]
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=True, env=environment)
    job_id = completed.stdout.strip().split(";", 1)[0]
    launch = ROOT / "campaigns/mno_afmii_strict_lr_v3r2/results" / f"{RECOVERY_ROOT}-launch.json"
    launch.write_text(json.dumps({"schema": "siestaflow-mno-response-recovery-launch-v1", "job_id": job_id,
                                  "evidence_root": RECOVERY_ROOT, "contract": command[:-1]}, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "SUBMITTED", "slurm_job_id": job_id, "evidence_root": RECOVERY_ROOT}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
