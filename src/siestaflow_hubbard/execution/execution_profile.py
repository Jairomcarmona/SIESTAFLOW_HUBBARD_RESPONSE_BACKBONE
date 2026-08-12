"""Public, site-neutral execution-profile contract for scheduler plugins."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping


class ProfileValidationError(ValueError):
    """A profile is incomplete, inconsistent, or unsuitable for execution."""


class EvidenceLevel(str, Enum):
    VALIDATED_RUNTIME = "VALIDATED_RUNTIME"
    OBSERVED = "OBSERVED"
    RENDERED_ONLY = "RENDERED_ONLY"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"

    @property
    def permits_submission(self) -> bool:
        return self is EvidenceLevel.VALIDATED_RUNTIME


@dataclass(frozen=True)
class SlurmRequest:
    partition: str
    account: str | None
    qos: str | None


@dataclass(frozen=True)
class Allocation:
    nodes: int
    total_cpus: int
    memory: str
    walltime: str
    max_parallel_steps: int
    shutdown_margin_seconds: int
    termination_grace_seconds: int


@dataclass(frozen=True)
class HydraLauncher:
    command: tuple[str, ...]
    bootstrap: str
    processes_per_node: int


@dataclass(frozen=True)
class Runtime:
    module_commands: tuple[str, ...]
    siesta_executable: str
    exclusive: bool
    environment: dict[str, str]
    launcher: HydraLauncher


@dataclass(frozen=True)
class TaskPolicy:
    max_attempts: int
    require_scf_converged: bool


@dataclass(frozen=True)
class ExecutionProfile:
    """Concrete profile supplied by a private site plugin at runtime."""
    target: str
    slurm: SlurmRequest
    allocation: Allocation
    runtime: Runtime
    task_policy: TaskPolicy
    evidence: EvidenceLevel = EvidenceLevel.UNKNOWN

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "ExecutionProfile":
        def mapping(name: str) -> Mapping[str, Any]:
            value = payload.get(name)
            if not isinstance(value, Mapping):
                raise ProfileValidationError(f"missing object: {name}")
            return value

        def text(value: Any, name: str, *, allow_empty: bool = False) -> str:
            if not isinstance(value, str) or (not allow_empty and not value.strip()):
                raise ProfileValidationError(f"invalid string: {name}")
            return value

        def positive(value: Any, name: str) -> int:
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ProfileValidationError(f"{name} must be a positive integer")
            return value

        if payload.get("target") != "slurm":
            raise ProfileValidationError("target must be 'slurm'")
        slurm, allocation, runtime, policy = (mapping(k) for k in ("slurm", "allocation", "runtime", "task_policy"))
        launcher = runtime.get("launcher")
        if not isinstance(launcher, Mapping) or launcher.get("kind") != "hydra":
            raise ProfileValidationError("runtime.launcher.kind must be 'hydra'")
        command = launcher.get("command")
        if not isinstance(command, list) or not command or not all(isinstance(x, str) and x for x in command):
            raise ProfileValidationError("runtime.launcher.command must be a non-empty string list")
        if launcher.get("bootstrap") != "ssh":
            raise ProfileValidationError("runtime.launcher.bootstrap must be 'ssh'")
        environment = runtime.get("environment")
        if not isinstance(environment, Mapping) or not all(isinstance(k, str) and isinstance(v, str) for k, v in environment.items()):
            raise ProfileValidationError("runtime.environment must map strings to strings")
        modules = runtime.get("module_commands")
        if not isinstance(modules, list) or not all(isinstance(x, str) and x.strip() for x in modules):
            raise ProfileValidationError("runtime.module_commands must be a string list")
        try:
            evidence = EvidenceLevel(payload.get("evidence", EvidenceLevel.UNKNOWN.value))
        except ValueError as exc:
            raise ProfileValidationError("invalid evidence level") from exc
        if not isinstance(runtime.get("exclusive"), bool):
            raise ProfileValidationError("runtime.exclusive must be boolean")
        if not isinstance(policy.get("require_scf_converged"), bool):
            raise ProfileValidationError("task_policy.require_scf_converged must be boolean")
        result = cls(
            target="slurm",
            slurm=SlurmRequest(text(slurm.get("partition"), "slurm.partition"),
                               slurm.get("account") if isinstance(slurm.get("account"), str) else None,
                               slurm.get("qos") if isinstance(slurm.get("qos"), str) else None),
            allocation=Allocation(positive(allocation.get("nodes"), "allocation.nodes"),
                                  positive(allocation.get("total_cpus"), "allocation.total_cpus"),
                                  text(allocation.get("memory"), "allocation.memory"),
                                  text(allocation.get("walltime"), "allocation.walltime"),
                                  positive(allocation.get("max_parallel_steps"), "allocation.max_parallel_steps"),
                                  positive(allocation.get("shutdown_margin_seconds"), "allocation.shutdown_margin_seconds"),
                                  positive(allocation.get("termination_grace_seconds"), "allocation.termination_grace_seconds")),
            runtime=Runtime(tuple(modules), text(runtime.get("siesta_executable"), "runtime.siesta_executable"), runtime.get("exclusive"),
                            dict(environment), HydraLauncher(tuple(command), "ssh", positive(launcher.get("processes_per_node"), "runtime.launcher.processes_per_node"))),
            task_policy=TaskPolicy(positive(policy.get("max_attempts"), "task_policy.max_attempts"), policy.get("require_scf_converged")),
            evidence=evidence,
        )
        if result.allocation.total_cpus < result.runtime.launcher.processes_per_node:
            raise ProfileValidationError("allocation.total_cpus is smaller than launcher processes_per_node")
        return result

    def require_submission_evidence(self) -> None:
        if not self.evidence.permits_submission:
            raise ProfileValidationError(f"profile evidence is {self.evidence.value}; runtime validation is required before submission")
