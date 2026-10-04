"""Composable local and in-allocation Slurm adapters for ``GenericDagExecutor``.

Neither adapter contains a cluster name, module name, FDF rule, or SIESTA
command.  Those belong to a versioned private execution profile and a command
factory.  This permits the same scientific DAG to be tested locally and then
executed inside an already granted Slurm allocation without resubmitting each
response as a separate job.
"""

from __future__ import annotations

import json
import os
import signal
import sys
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from os import environ
from pathlib import Path
from subprocess import PIPE, CompletedProcess, run
from typing import Protocol

from .dag_contract import NodeState
from .execution_profile import ExecutionProfile
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
        for name, path in (
            ("stdin", self.stdin_path),
            ("stdout", self.stdout_path),
            ("stderr", self.stderr_path),
        ):
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

    def validate(
        self, node: LRDagNode, command: NodeCommand, completed: CompletedProcess[str]
    ) -> NodeReceipt: ...


def _failed_receipt(node: LRDagNode, completed: CompletedProcess[str]) -> NodeReceipt:
    digest = sha256(
        (
            node.node_id
            + "\0"
            + str(completed.returncode)
            + "\0"
            + (completed.stdout or "")
            + "\0"
            + (completed.stderr or "")
        ).encode()
    ).hexdigest()
    return NodeReceipt(node.node_id, NodeState.FAILED_EXECUTION, digest)


def _returncode_meaning(returncode: int, *, synthetic_oserror: bool) -> str:
    if synthetic_oserror:
        return "SYNTHETIC_OSERROR"
    if returncode < 0:
        return f"SIGNAL:{signal.Signals(-returncode).name}"
    signal_number = returncode - 128
    if returncode > 128:
        try:
            signal_name = signal.Signals(signal_number).name
        except ValueError:
            return "EXIT"
        return f"PROBABLE_SIGNAL:{signal_name} (128+N via launcher)"
    return "EXIT"


def _last_lines(path: Path | None, captured: str | None) -> str:
    text = path.read_text(encoding="utf-8", errors="replace") if path is not None else (captured or "")
    return "\n".join(text.splitlines()[-20:])


def _write_failure_record(
    command: NodeCommand,
    completed: CompletedProcess[str],
    *,
    synthetic_oserror: bool,
    captured_stdout: str | None = None,
    captured_stderr: str | None = None,
) -> None:
    payload = {
        "returncode": completed.returncode,
        "returncode_meaning": _returncode_meaning(completed.returncode, synthetic_oserror=synthetic_oserror),
        "stdout_tail": _last_lines(
            command.stdout_path, captured_stdout if captured_stdout is not None else completed.stdout
        ),
        "stderr_tail": _last_lines(
            command.stderr_path, captured_stderr if captured_stderr is not None else completed.stderr
        ),
        "argv": list(command.argv),
    }
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=command.cwd,
            prefix=".failure.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, command.cwd / "failure.json")
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


class LocalSubprocessExecutor:
    """Run one materialized node locally using argv execution, never a shell."""

    def __init__(
        self,
        factory: CommandFactory,
        validator: OutputValidator,
        *,
        env: Mapping[str, str] | None = None,
    ):
        self.factory, self.validator = factory, validator
        self.env = env

    def execute(self, node: LRDagNode) -> NodeReceipt:
        command = self.factory.command_for(node)
        command.validate()
        stdin_handle = command.stdin_path.open("r", encoding="utf-8") if command.stdin_path else None
        stdout_handle = (
            command.stdout_path.open("w", encoding="utf-8", newline="\n") if command.stdout_path else None
        )
        stderr_handle = (
            command.stderr_path.open("w", encoding="utf-8", newline="\n") if command.stderr_path else None
        )
        partially_redirected = (stdout_handle is None) != (stderr_handle is None)
        diagnostic_stdout: str | None = None
        diagnostic_stderr: str | None = None
        synthetic_oserror = False
        try:
            completed = run(
                command.argv,
                cwd=command.cwd,
                stdin=stdin_handle,
                stdout=stdout_handle if stdout_handle else (PIPE if partially_redirected else None),
                stderr=stderr_handle if stderr_handle else (PIPE if partially_redirected else None),
                capture_output=stdout_handle is None and stderr_handle is None,
                text=True,
                shell=False,
                check=False,
                env=self.env,
            )
        except OSError as exc:
            synthetic_oserror = True
            completed = CompletedProcess(command.argv, 127, "", str(exc))
        finally:
            for handle in (stdin_handle, stdout_handle, stderr_handle):
                if handle is not None:
                    handle.close()
        if partially_redirected and not synthetic_oserror:
            diagnostic_stdout = completed.stdout if command.stdout_path is None else None
            diagnostic_stderr = completed.stderr if command.stderr_path is None else None
            if diagnostic_stdout:
                sys.stdout.write(diagnostic_stdout)
                sys.stdout.flush()
            if diagnostic_stderr:
                sys.stderr.write(diagnostic_stderr)
                sys.stderr.flush()
            # Preserve the historical receipt digest and validator input for partial redirection.
            completed = CompletedProcess(command.argv, completed.returncode, None, None)
        if completed.returncode != 0:
            _write_failure_record(
                command,
                completed,
                synthetic_oserror=synthetic_oserror,
                captured_stdout=diagnostic_stdout,
                captured_stderr=diagnostic_stderr,
            )
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
        self._delegate = LocalSubprocessExecutor(factory, validator, env=actual_environment)

    def execute(self, node: LRDagNode) -> NodeReceipt:
        return self._delegate.execute(node)
