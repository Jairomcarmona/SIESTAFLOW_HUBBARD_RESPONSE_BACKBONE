"""Public, site-neutral execution-profile contract for scheduler plugins."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import PurePosixPath
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
    kind: str = "hydra"


@dataclass(frozen=True)
class Runtime:
    module_commands: tuple[str, ...]
    siesta_executable: str
    exclusive: bool
    environment: dict[str, str]
    launcher: HydraLauncher


@dataclass(frozen=True)
class WslRuntime:
    """Windows-to-WSL service settings for a persistent local campaign."""
    distribution: str
    python_executable: str
    workspace_root: str

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "WslRuntime":
        def absolute_posix(name: str) -> str:
            raw = value.get(name)
            if not isinstance(raw, str) or not raw.startswith("/") or "\x00" in raw:
                raise ProfileValidationError(f"wsl.{name} must be an absolute POSIX path")
            path = PurePosixPath(raw)
            if ".." in path.parts:
                raise ProfileValidationError(f"wsl.{name} cannot traverse parent directories")
            return str(path)

        distribution = value.get("distribution")
        if not isinstance(distribution, str) or not distribution.strip():
            raise ProfileValidationError("wsl.distribution is required")
        return cls(distribution.strip(), absolute_posix("python_executable"), absolute_posix("workspace_root"))


@dataclass(frozen=True)
class TaskPolicy:
    max_attempts: int
    require_scf_converged: bool


@dataclass(frozen=True)
class ExecutionProfile:
    """Concrete profile supplied by a private site plugin at runtime."""
    target: str
    slurm: SlurmRequest | None
    allocation: Allocation
    runtime: Runtime
    task_policy: TaskPolicy
    evidence: EvidenceLevel = EvidenceLevel.UNKNOWN
    wsl: WslRuntime | None = None

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "ExecutionProfile":
        if not isinstance(payload, Mapping):
            raise ProfileValidationError("execution profile must be a JSON object")

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

        target = payload.get("target")
        if target not in {"slurm", "local_wsl"}:
            raise ProfileValidationError("target must be 'slurm' or 'local_wsl'")
        allocation, runtime, policy = (mapping(k) for k in ("allocation", "runtime", "task_policy"))
        slurm_payload = mapping("slurm") if target == "slurm" else None
        wsl_payload = mapping("wsl") if target == "local_wsl" else None
        launcher = runtime.get("launcher")
        if not isinstance(launcher, Mapping) or launcher.get("kind") not in {"hydra", "openmpi"}:
            raise ProfileValidationError("runtime.launcher.kind must be 'hydra' or 'openmpi'")
        launcher_kind = launcher["kind"]
        command = launcher.get("command")
        if not isinstance(command, list) or not command or not all(isinstance(x, str) and x for x in command):
            raise ProfileValidationError("runtime.launcher.command must be a non-empty string list")
        expected_bootstrap = "ssh" if target == "slurm" else "local"
        if launcher.get("bootstrap") != expected_bootstrap:
            raise ProfileValidationError(f"runtime.launcher.bootstrap must be {expected_bootstrap!r} for target {target!r}")
        if target == "local_wsl" and launcher_kind != "openmpi":
            raise ProfileValidationError("local_wsl requires the explicitly declared Open MPI launcher")
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
            target=target,
            slurm=(SlurmRequest(text(slurm_payload.get("partition"), "slurm.partition"),
                                slurm_payload.get("account") if isinstance(slurm_payload.get("account"), str) else None,
                                slurm_payload.get("qos") if isinstance(slurm_payload.get("qos"), str) else None)
                   if slurm_payload is not None else None),
            allocation=Allocation(positive(allocation.get("nodes"), "allocation.nodes"),
                                  positive(allocation.get("total_cpus"), "allocation.total_cpus"),
                                  text(allocation.get("memory"), "allocation.memory"),
                                  text(allocation.get("walltime"), "allocation.walltime"),
                                  positive(allocation.get("max_parallel_steps"), "allocation.max_parallel_steps"),
                                  positive(allocation.get("shutdown_margin_seconds"), "allocation.shutdown_margin_seconds"),
                                  positive(allocation.get("termination_grace_seconds"), "allocation.termination_grace_seconds")),
            runtime=Runtime(tuple(modules), text(runtime.get("siesta_executable"), "runtime.siesta_executable"), runtime.get("exclusive"),
                            dict(environment), HydraLauncher(tuple(command), expected_bootstrap, positive(launcher.get("processes_per_node"), "runtime.launcher.processes_per_node"), launcher_kind)),
            task_policy=TaskPolicy(positive(policy.get("max_attempts"), "task_policy.max_attempts"), policy.get("require_scf_converged")),
            evidence=evidence,
            wsl=WslRuntime.from_mapping(wsl_payload) if wsl_payload is not None else None,
        )
        if result.allocation.total_cpus < result.runtime.launcher.processes_per_node:
            raise ProfileValidationError("allocation.total_cpus is smaller than launcher processes_per_node")
        if target == "local_wsl":
            if result.allocation.nodes != 1:
                raise ProfileValidationError("local_wsl requires exactly one node")
            if result.allocation.max_parallel_steps != 1:
                raise ProfileValidationError("local_wsl requires max_parallel_steps=1")
            if result.runtime.launcher.processes_per_node != result.allocation.total_cpus:
                raise ProfileValidationError("local_wsl MPI ranks must equal the configured total_cpus")
        return result

    def require_submission_evidence(self) -> None:
        if not self.evidence.permits_submission:
            raise ProfileValidationError(f"profile evidence is {self.evidence.value}; runtime validation is required before submission")
