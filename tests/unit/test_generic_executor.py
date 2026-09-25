from pathlib import Path

import pytest

from siestaflow_hubbard.execution.dag_contract import NodeState
from siestaflow_hubbard.execution.generic_executor import (
    ExecutionContractError,
    GenericDagExecutor,
    NodeReceipt,
)
from siestaflow_hubbard.execution.lr_dag import build_initial_lr_dag
from siestaflow_hubbard.domain.symmetry_reduction import SymmetryReductionPolicy, build_symmetry_reduction_plan
from tests.support import certificate


class RecordingAdapter:
    def __init__(self):
        self.seen = []

    def execute(self, node):
        self.seen.append(node.node_id)
        return NodeReceipt(node.node_id, NodeState.VALIDATED, f"digest:{node.node_id}")


def _dag():
    plan = build_symmetry_reduction_plan(
        ["a", "b"], ["a", "b"], certificate(2), SymmetryReductionPolicy(alpha_ev=0.05)
    )
    return build_initial_lr_dag(plan)


def test_executor_preserves_dependency_order_and_reuses_validated_checkpoint(tmp_path: Path):
    executor = GenericDagExecutor(_dag(), tmp_path / "state.json")
    adapter = RecordingAdapter()
    first = executor.advance(adapter, max_nodes=1)
    assert [item.node_id for item in first] == ["reference"]
    assert executor.advance(adapter, max_nodes=1)[0].node_id.startswith("response:")
    resumed = GenericDagExecutor(_dag(), tmp_path / "state.json")
    assert all(node.node_id != "reference" for node in resumed.runnable())


def test_executor_refuses_resume_against_a_different_scientific_dag(tmp_path: Path):
    state = tmp_path / "state.json"
    executor = GenericDagExecutor(_dag(), state)
    executor.advance(RecordingAdapter(), max_nodes=1)
    other_plan = build_symmetry_reduction_plan(
        ["a", "b"], ["a", "b"], certificate(2), SymmetryReductionPolicy(alpha_ev=0.10)
    )
    other = GenericDagExecutor(build_initial_lr_dag(other_plan), state)
    with pytest.raises(ExecutionContractError, match="different scientific DAG"):
        other.runnable()
