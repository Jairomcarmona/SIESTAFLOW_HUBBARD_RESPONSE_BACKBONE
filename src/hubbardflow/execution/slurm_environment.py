"""Validation of a granted Slurm allocation, without site-specific discovery."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from .execution_profile import ExecutionProfile, ProfileValidationError


@dataclass(frozen=True)
class SlurmEnvironment:
    job_id: str
    submit_dir: str
    job_end_time: str
    nodes: int
    ntasks: int
    cpus_per_task: int
    nodelist: str

    @classmethod
    def from_environ(cls, environ: Mapping[str, str]) -> "SlurmEnvironment":
        required = ("SLURM_JOB_ID", "SLURM_SUBMIT_DIR", "SLURM_JOB_END_TIME", "SLURM_NNODES", "SLURM_NTASKS", "SLURM_CPUS_PER_TASK", "SLURM_JOB_NODELIST")
        missing = [key for key in required if not environ.get(key)]
        if missing:
            raise ProfileValidationError("missing Slurm environment: " + ", ".join(missing))
        try:
            return cls(environ["SLURM_JOB_ID"], environ["SLURM_SUBMIT_DIR"], environ["SLURM_JOB_END_TIME"], int(environ["SLURM_NNODES"]), int(environ["SLURM_NTASKS"]), int(environ["SLURM_CPUS_PER_TASK"]), environ["SLURM_JOB_NODELIST"])
        except ValueError as exc:
            raise ProfileValidationError("invalid integer in Slurm environment") from exc

    def validate_profile(self, profile: ExecutionProfile, hosts: Sequence[str]) -> None:
        if self.nodes < profile.allocation.nodes:
            raise ProfileValidationError("granted allocation has fewer nodes than profile")
        if self.ntasks * self.cpus_per_task < profile.allocation.total_cpus:
            raise ProfileValidationError("granted allocation has fewer CPUs than profile")
        if len(hosts) != self.nodes or len(set(hosts)) != self.nodes:
            raise ProfileValidationError("host resolution does not match granted node count")
