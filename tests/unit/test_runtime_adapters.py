import json
import os
import signal
import sys
from hashlib import sha256
from pathlib import Path
from subprocess import CompletedProcess
from typing import Any

import pytest

import hubbardflow.execution.campaign_runner as campaign_runner
from hubbardflow.execution.dag_contract import NodeState
from hubbardflow.execution.execution_profile import ExecutionProfile
from hubbardflow.execution.generic_executor import NodeReceipt
from hubbardflow.execution.lr_dag import LRDagNode, LRNodeKind
from hubbardflow.execution.runtime_adapters import LocalSubprocessExecutor, NodeCommand


class Factory:
    def __init__(self, command: NodeCommand) -> None:
        self.command = command

    def command_for(self, node: LRDagNode) -> NodeCommand:
        return self.command


class Validator:
    def validate(
        self,
        node: LRDagNode,
        command: NodeCommand,
        completed: CompletedProcess[str],
    ) -> NodeReceipt:
        assert completed.returncode == 0
        return NodeReceipt(node.node_id, NodeState.VALIDATED, "verified-output-digest")


def _node() -> LRDagNode:
    return LRDagNode("reference", LRNodeKind.REFERENCE, ())


def test_local_adapter_uses_argv_and_requires_a_backend_validator(tmp_path: Path) -> None:
    command = NodeCommand(
        (sys.executable, "-c", "print('ok')"),
        tmp_path,
        stdout_path=tmp_path / "stdout",
        stderr_path=tmp_path / "stderr",
    )
    receipt = LocalSubprocessExecutor(Factory(command), Validator()).execute(_node())
    assert receipt.state is NodeState.VALIDATED
    assert (tmp_path / "stdout").read_text().strip() == "ok"
    assert not (tmp_path / "failure.json").exists()


def test_local_adapter_records_execution_failure_without_calling_output_validator(tmp_path: Path) -> None:
    command = NodeCommand((sys.executable, "-c", "import sys; sys.exit(7)"), tmp_path)
    receipt = LocalSubprocessExecutor(Factory(command), Validator()).execute(_node())
    assert receipt.state is NodeState.FAILED_EXECUTION
    failure = json.loads((tmp_path / "failure.json").read_text(encoding="utf-8"))
    assert failure["returncode"] == 7
    assert failure["returncode_meaning"] == "EXIT"


def test_local_adapter_failure_record_keeps_file_tails_and_argv(tmp_path: Path) -> None:
    stdout_path = tmp_path / "stdout"
    command = NodeCommand(
        (
            sys.executable,
            "-c",
            "print('\\n'.join(f'o{i}' for i in range(25))); import sys; print('err', file=sys.stderr); sys.exit(3)",
        ),
        tmp_path,
        stdout_path=stdout_path,
    )
    receipt = LocalSubprocessExecutor(Factory(command), Validator()).execute(_node())
    failure = json.loads((tmp_path / "failure.json").read_text(encoding="utf-8"))
    assert failure["stdout_tail"] == "\n".join(f"o{i}" for i in range(5, 25))
    assert failure["stderr_tail"] == "err"
    assert failure["argv"] == list(command.argv)
    assert failure["returncode_meaning"] == "EXIT"
    previous_digest_input = "reference\0" + "3\0\0"
    assert receipt.evidence_digest == sha256(previous_digest_input.encode()).hexdigest()


@pytest.mark.skipif(os.name == "nt", reason="negative subprocess return codes are POSIX signal exits")
def test_local_adapter_records_direct_sigterm(tmp_path: Path) -> None:
    command = NodeCommand(
        (sys.executable, "-c", "import os, signal; os.kill(os.getpid(), signal.SIGTERM)"),
        tmp_path,
    )
    LocalSubprocessExecutor(Factory(command), Validator()).execute(_node())
    failure = json.loads((tmp_path / "failure.json").read_text(encoding="utf-8"))
    assert failure["returncode"] == -signal.SIGTERM
    assert failure["returncode_meaning"] == "SIGNAL:SIGTERM"


def test_local_adapter_records_launcher_signal_exit(tmp_path: Path) -> None:
    if os.name == "nt":
        pytest.skip("launcher exit status 143 is a POSIX convention")
    launcher = tmp_path / "launcher.sh"
    launcher.write_text("#!/bin/sh\nexit 143\n", encoding="utf-8")
    launcher.chmod(0o755)
    command = NodeCommand((str(launcher),), tmp_path)
    LocalSubprocessExecutor(Factory(command), Validator()).execute(_node())
    failure = json.loads((tmp_path / "failure.json").read_text(encoding="utf-8"))
    assert failure["returncode"] == 143
    assert failure["returncode_meaning"] == "PROBABLE_SIGNAL:SIGTERM (128+N via launcher)"


def test_local_adapter_distinguishes_synthetic_oserror(tmp_path: Path) -> None:
    command = NodeCommand((str(tmp_path / "missing-executable"),), tmp_path)
    LocalSubprocessExecutor(Factory(command), Validator()).execute(_node())
    failure = json.loads((tmp_path / "failure.json").read_text(encoding="utf-8"))
    assert failure["returncode"] == 127
    assert failure["returncode_meaning"] == "SYNTHETIC_OSERROR"


def test_local_adapter_treats_invalid_high_exit_code_as_exit(tmp_path: Path) -> None:
    command = NodeCommand((sys.executable, "-c", "raise SystemExit(255)"), tmp_path)
    LocalSubprocessExecutor(Factory(command), Validator()).execute(_node())
    failure = json.loads((tmp_path / "failure.json").read_text(encoding="utf-8"))
    assert failure["returncode"] == 255
    assert failure["returncode_meaning"] == "EXIT"


def test_profile_environment_is_passed_to_processes_without_mutating_os_environ(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = ExecutionProfile.from_mapping(
        {
            "target": "slurm",
            "evidence": "VALIDATED_RUNTIME",
            "slurm": {"partition": "cpu", "account": None, "qos": None},
            "allocation": {
                "nodes": 1,
                "total_cpus": 1,
                "memory": "1G",
                "walltime": "01:00:00",
                "max_parallel_steps": 1,
                "shutdown_margin_seconds": 60,
                "termination_grace_seconds": 30,
            },
            "runtime": {
                "module_commands": [],
                "siesta_executable": sys.executable,
                "exclusive": True,
                "environment": {"HUBBARDFLOW_PROFILE_TEST": "profile-value"},
                "launcher": {
                    "kind": "hydra",
                    "command": ["mpiexec"],
                    "bootstrap": "ssh",
                    "processes_per_node": 1,
                },
            },
            "task_policy": {"max_attempts": 1, "require_scf_converged": True},
        }
    )
    baseline = dict(os.environ)
    environment = {**os.environ, **profile.runtime.environment}
    command = NodeCommand(
        (
            sys.executable,
            "-c",
            "import os; print(os.environ['HUBBARDFLOW_PROFILE_TEST'])",
        ),
        tmp_path,
        stdout_path=tmp_path / "stdout",
        stderr_path=tmp_path / "stderr",
    )
    LocalSubprocessExecutor(Factory(command), Validator(), env=environment).execute(_node())
    assert (tmp_path / "stdout").read_text(encoding="utf-8").strip() == "profile-value"

    runner = campaign_runner.CampaignRunner.__new__(campaign_runner.CampaignRunner)
    runner.environment = {
        **environment,
        "SLURM_JOB_ID": "123",
        "SLURM_SUBMIT_DIR": str(tmp_path),
        "SLURM_JOB_END_TIME": "2026-10-04T00:00:00",
        "SLURM_NNODES": "1",
        "SLURM_NTASKS": "1",
        "SLURM_CPUS_PER_TASK": "1",
        "SLURM_JOB_NODELIST": "node0",
    }
    seen_env: dict[str, str] = {}

    def fake_scontrol(args: list[str], **kwargs: Any) -> CompletedProcess[str]:
        environment_argument = kwargs.get("env")
        assert isinstance(environment_argument, dict)
        seen_env.update(environment_argument)
        return CompletedProcess(args, 0, "node0\n", "")

    monkeypatch.setattr(campaign_runner, "subprocess_run", fake_scontrol)
    assert campaign_runner.CampaignRunner._slurm_hosts(runner) == ("node0",)
    assert seen_env["HUBBARDFLOW_PROFILE_TEST"] == "profile-value"
    assert os.environ == baseline
