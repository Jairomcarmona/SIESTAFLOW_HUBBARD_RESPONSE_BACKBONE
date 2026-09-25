"""Backend-neutral, resumable executor for the scientific LR DAG.

This is intentionally not a Slurm script.  It advances a DAG only when an
injected local or scheduler adapter returns validated scientific evidence.
The adapter owns command execution; this core owns dependencies, immutable
campaign identity and restart safety.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Protocol

from .dag_contract import NodeState, TERMINAL_FAILURES, may_start
from .lr_dag import LRDag, LRDagNode


class ExecutionContractError(RuntimeError):
    """Invalid adapter result, campaign mismatch, or unsafe resume."""


@dataclass(frozen=True)
class NodeReceipt:
    node_id: str
    state: NodeState
    evidence_digest: str

    def validate(self) -> None:
        if not self.node_id or not self.evidence_digest or not isinstance(self.state, NodeState):
            raise ExecutionContractError("invalid node receipt")


class NodeExecutor(Protocol):
    """Implemented privately by local or scheduler runtime plugins."""

    def execute(self, node: LRDagNode) -> NodeReceipt: ...


def dag_digest(dag: LRDag) -> str:
    """Stable identity that makes checkpoints incompatible after plan changes."""
    payload = [
        {
            "node_id": node.node_id,
            "kind": node.kind.value,
            "dependencies": node.dependencies,
            "perturbation": asdict(node.perturbation) if node.perturbation else None,
        }
        for node in dag.nodes
    ]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return sha256(encoded).hexdigest()


class JsonDagCheckpoint:
    """Small, inspectable state file; no database or scheduler state is needed."""

    VERSION = 1

    def __init__(self, path: Path, campaign_digest: str):
        self.path, self.campaign_digest = path, campaign_digest

    def load(self) -> dict[str, NodeReceipt]:
        if not self.path.exists():
            return {}
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        if raw.get("version") != self.VERSION or raw.get("campaign_digest") != self.campaign_digest:
            raise ExecutionContractError("checkpoint belongs to a different scientific DAG")
        receipts = {}
        for item in raw.get("receipts", []):
            try:
                receipt = NodeReceipt(item["node_id"], NodeState(item["state"]), item["evidence_digest"])
                receipt.validate()
            except (KeyError, ValueError) as exc:
                raise ExecutionContractError("malformed checkpoint receipt") from exc
            if receipt.node_id in receipts:
                raise ExecutionContractError("duplicate checkpoint receipt")
            receipts[receipt.node_id] = receipt
        return receipts

    def save(self, receipts: dict[str, NodeReceipt]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": self.VERSION,
            "campaign_digest": self.campaign_digest,
            "receipts": [
                {"node_id": receipt.node_id, "state": receipt.state.value,
                 "evidence_digest": receipt.evidence_digest}
                for _, receipt in sorted(receipts.items())
            ],
        }
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(self.path)


class GenericDagExecutor:
    """Advance executable nodes serially; preserve validated work on restart."""

    def __init__(self, dag: LRDag, checkpoint_path: Path):
        self.dag = dag
        self._nodes = {node.node_id: node for node in dag.nodes}
        if len(self._nodes) != len(dag.nodes):
            raise ExecutionContractError("DAG contains duplicate node IDs")
        unknown = [dep for node in dag.nodes for dep in node.dependencies if dep not in self._nodes]
        if unknown:
            raise ExecutionContractError(f"DAG has unknown dependencies: {sorted(set(unknown))}")
        self.checkpoint = JsonDagCheckpoint(checkpoint_path, dag_digest(dag))

    def runnable(self) -> tuple[LRDagNode, ...]:
        receipts = self.checkpoint.load()
        available = []
        for node in self.dag.nodes:
            if node.node_id in receipts:
                continue
            # An incomplete parent is not a failed parent: it merely makes the
            # descendant unavailable.  Looking it up eagerly would turn an
            # ordinary first pass through a DAG into a KeyError.
            if any(dependency not in receipts for dependency in node.dependencies):
                continue
            parent_states = [receipts[dependency].state for dependency in node.dependencies]
            if may_start(parent_states):
                available.append(node)
        return tuple(available)

    def advance(self, adapter: NodeExecutor, *, max_nodes: int | None = None) -> tuple[NodeReceipt, ...]:
        """Execute ready nodes; stop immediately at a terminal failure.

        `max_nodes` is mainly useful for a scheduler plugin that releases the
        process between scientific gates.  It does not change dependencies.
        """
        receipts = self.checkpoint.load()
        completed: list[NodeReceipt] = []
        while max_nodes is None or len(completed) < max_nodes:
            ready = self.runnable()
            if not ready:
                break
            node = ready[0]
            receipt = adapter.execute(node)
            receipt.validate()
            if receipt.node_id != node.node_id:
                raise ExecutionContractError("adapter receipt node does not match executed node")
            receipts[receipt.node_id] = receipt
            self.checkpoint.save(receipts)
            completed.append(receipt)
            if receipt.state in TERMINAL_FAILURES:
                break
        return tuple(completed)
