"""The single-node Slurm submission contract used by preregistered campaigns."""
from __future__ import annotations

from pathlib import Path
import subprocess


FOREGROUND_EXPORT = "--export=NONE,OMP_NUM_THREADS=1"


def four_rank_foreground_command(invocation: str) -> list[str]:
    """Build the canonical isolated Slurm command.

    ``--wait`` keeps the evidence-producing job in the caller's control and
    the explicit OpenMP export prevents an MPI/OpenMP oversubscription.
    """
    return [
        "sbatch", "--wait", "--no-requeue", "--parsable", "-p", "local", "-N", "1",
        "-n", "4", "-c", "1", "--exclusive", FOREGROUND_EXPORT,
        "--wrap", invocation,
    ]


def submit_four_rank_foreground(invocation: str, *, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Submit exactly the canonical command and wait for its completion."""
    return subprocess.run(
        four_rank_foreground_command(invocation), cwd=cwd, check=True,
        text=True, capture_output=True,
    )
