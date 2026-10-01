"""Composable local and in-allocation Slurm adapters for ``GenericDagExecutor``.

Neither adapter contains a cluster name, module name, FDF rule, or SIESTA
command.  Those belong to a versioned private execution profile and a command
factory.  This permits the same scientific DAG to be tested locally and then
executed inside an already granted Slurm allocation without resubmitting each
response as a separate job.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from os import environ
from pathlib import Path
from subprocess import CompletedProcess, run
from typing import Mapping, Protocol, Sequence

from .dag_contract import NodeState
from .execution_profile import ExecutionProfile, ProfileValidationError
from .generic_executor import NodeReceipt
from .lr_dag import LRDagNode
from .slurm_environment import SlurmEnvironment


@dataclass(frozen=True)
class NodeCommand:
    argv: tuple[str, ...]
    cwd: Path
    stdin_path: Path | None = None
    stdout_path: Path | None = None
    stderr_path: Path | None = None

    def validate(self) -> None:
        if not self.argv or not all(isinstance(part, str) and part for part in self.argv):
            raise ValueError("node command must be a non-empty argv vector")
        if not self.cwd.is_dir():
            raise ValueError("node command working directory does not exist")
        for name, path in (("stdin", self.stdin_path), ("stdout", self.stdout_path), ("stderr", self.stderr_path)):
            if path is None:
                continue
            try:
                path.resolve().relative_to(self.cwd.resolve())
            except ValueError as exc:
                raise ValueError(f"node command {name} path escapes working directory") from exc
            if name == "stdin" and not path.is_file():
                raise ValueError("node command stdin path is missing")
            if name != "stdin" and not path.parent.is_dir():
                raise ValueError(f"node command {name} parent directory is missing")


class CommandFactory(Protocol):
    def command_for(self, node: LRDagNode) -> NodeCommand: ...


class OutputValidator(Protocol):
    """Backend-specific validator: normal exit alone is never enough."""

    def validate(self, node: LRDagNode, command: NodeCommand, completed: CompletedProcess[str]) -> NodeReceipt: ...


def _failed_receipt(node: LRDagNode, completed: CompletedProcess[str]) -> NodeReceipt:
    digest = sha256(
        (node.node_id + "\0" + str(completed.returncode) + "\0" + (completed.stdout or "") + "\0" + (completed.stderr or "")).encode()
    ).hexdigest()
    return NodeReceipt(node.node_id, NodeState.FAILED_EXECUTION, digest)


class LocalSubprocessExecutor:
    """Run one materialized node locally using argv execution, never a shell."""

    def __init__(self, factory: CommandFactory, validator: OutputValidator):
        self.factory, self.validator = factory, validator

    def execute(self, node: LRDagNode) -> NodeReceipt:
        command = self.factory.command_for(node)
        command.validate()
        stdin_handle = command.stdin_path.open("r", encoding="utf-8") if command.stdin_path else None
        stdout_handle = command.stdout_path.open("w", encoding="utf-8", newline="\n") if command.stdout_path else None
        stderr_handle = command.stderr_path.open("w", encoding="utf-8", newline="\n") if command.stderr_path else None
        try:
            completed = run(
                command.argv, cwd=command.cwd, stdin=stdin_handle,
                stdout=stdout_handle if stdout_handle else None,
                stderr=stderr_handle if stderr_handle else None,
                capture_output=stdout_handle is None and stderr_handle is None,
                text=True, shell=False, check=False,
            )
        except OSError as exc:
            completed = CompletedProcess(command.argv, 127, "", str(exc))
        finally:
            for handle in (stdin_handle, stdout_handle, stderr_handle):
                if handle is not None:
                    handle.close()
        if completed.returncode != 0:
            return _failed_receipt(node, completed)
        receipt = self.validator.validate(node, command, completed)
        receipt.validate()
        if receipt.node_id != node.node_id:
            raise ValueError("output validator returned a receipt for a different node")
        return receipt


class SlurmAllocationExecutor:
    """Permit execution only inside a validated existing Slurm allocation.

    The class deliberately does not call ``sbatch``.  Campaign-level
    submission remains a thin private wrapper; after allocation, all DAG nodes
    use the already granted resources through the injected command factory.
    """

    def __init__(
        self,
        profile: ExecutionProfile,
        hosts: Sequence[str],
        factory: CommandFactory,
        validator: OutputValidator,
        *,
        environment: Mapping[str, str] | None = None,
    ):
        profile.require_submission_evidence()
        actual_environment = dict(environ if environment is None else environment)
        slurm = SlurmEnvironment.from_environ(actual_environment)
        slurm.validate_profile(profile, hosts)
        self.profile, self.slurm, self.hosts = profile, slurm, tuple(hosts)
        self._delegate = LocalSubprocessExecutor(factory, validator)

    def execute(self, node: LRDagNode) -> NodeReceipt:
        return self._delegate.execute(node)
