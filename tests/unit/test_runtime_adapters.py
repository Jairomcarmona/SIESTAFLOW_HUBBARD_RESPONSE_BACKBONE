import sys
from pathlib import Path

from siestaflow_hubbard.execution.dag_contract import NodeState
from siestaflow_hubbard.execution.lr_dag import LRDagNode, LRNodeKind
from siestaflow_hubbard.execution.runtime_adapters import LocalSubprocessExecutor, NodeCommand
from siestaflow_hubbard.execution.generic_executor import NodeReceipt


class Factory:
    def __init__(self, command):
        self.command = command

    def command_for(self, node):
        return self.command


class Validator:
    def validate(self, node, command, completed):
        assert completed.returncode == 0
        return NodeReceipt(node.node_id, NodeState.VALIDATED, "verified-output-digest")


def _node():
    return LRDagNode("reference", LRNodeKind.REFERENCE, ())


def test_local_adapter_uses_argv_and_requires_a_backend_validator(tmp_path: Path):
    command = NodeCommand(
        (sys.executable, "-c", "print('ok')"), tmp_path,
        stdout_path=tmp_path / "stdout", stderr_path=tmp_path / "stderr",
    )
    receipt = LocalSubprocessExecutor(Factory(command), Validator()).execute(_node())
    assert receipt.state is NodeState.VALIDATED
    assert (tmp_path / "stdout").read_text().strip() == "ok"


def test_local_adapter_records_execution_failure_without_calling_output_validator(tmp_path: Path):
    command = NodeCommand((sys.executable, "-c", "import sys; sys.exit(7)"), tmp_path)
    receipt = LocalSubprocessExecutor(Factory(command), Validator()).execute(_node())
    assert receipt.state is NodeState.FAILED_EXECUTION
