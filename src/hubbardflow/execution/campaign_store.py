"""Durable execution records and checkpoint coordination for a campaign.

The store owns receipt records and forensic attempt archiving. It resolves the
checkpoint manager through an accessor on every operation because shadow and
adaptive graph updates replace that manager while a campaign is running.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping
from hashlib import sha256
from pathlib import Path
from typing import Any, Protocol

from hubbardflow.execution.dag_contract import NodeState
from hubbardflow.execution.generic_executor import ExecutionContractError, NodeReceipt
from hubbardflow.execution.lr_dag import LRDagNode


class CheckpointManager(Protocol):
    """Narrow live interface used to persist validated node receipts."""

    def load(self) -> dict[str, NodeReceipt]: ...

    def save(self, receipts: dict[str, NodeReceipt]) -> None: ...


def atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    """Write canonical JSON by replacing a complete temporary file atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


class CampaignStore:
    """Own campaign node evidence while resolving the current checkpoint live."""

    def __init__(
        self,
        records_path: Path,
        checkpoint_accessor: Callable[[], CheckpointManager],
    ) -> None:
        self.records_path = records_path
        self._checkpoint_accessor = checkpoint_accessor
        self.records: dict[str, Any] = {}

    def load_records(self, identity: Mapping[str, str]) -> dict[str, Any]:
        try:
            value = json.loads(self.records_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self.records = {}
            return self.records
        if not isinstance(value, dict):
            self.records = {}
            return self.records
        if value.get("identity") != identity:
            raise ExecutionContractError("node evidence belongs to a different campaign input/DAG identity")
        records = value.get("nodes", {})
        self.records = records if isinstance(records, dict) else {}
        return self.records

    def save_records(self, identity: Mapping[str, str]) -> None:
        atomic_json(self.records_path, {"identity": identity, "nodes": self.records})

    def checkpoint(self) -> dict[str, NodeReceipt]:
        return self._checkpoint_accessor().load()

    def save_checkpoint(self, receipts: dict[str, NodeReceipt]) -> None:
        self._checkpoint_accessor().save(receipts)

    def record_receipt(
        self,
        identity: Mapping[str, str],
        node: LRDagNode,
        receipt: NodeReceipt,
        extra: Mapping[str, Any] | None = None,
    ) -> None:
        self.records[node.node_id] = {
            "state": receipt.state.value,
            "evidence_digest": receipt.evidence_digest,
            "recorded_epoch": time.time(),
            **dict(extra or {}),
        }
        self.save_records(identity)
        receipts = self.checkpoint()
        receipts[node.node_id] = receipt
        self.save_checkpoint(receipts)

    def archive_unvalidated_attempts(self, control: Path, node_ids: set[str]) -> None:
        archive = control / "archive" / "attempts"
        for node_id in node_ids:
            key = sha256(node_id.encode()).hexdigest()[:20]
            node_root = control / "attempts" / key
            if not node_root.is_dir():
                continue
            for attempt in list(node_root.iterdir()):
                if not attempt.is_dir():
                    continue
                destination = archive / key / f"{attempt.name}-{time.time_ns()}"
                destination.parent.mkdir(parents=True, exist_ok=True)
                try:
                    attempt.replace(destination)
                except OSError:
                    # Keep the original forensic data and do not reuse it; the
                    # next materialization always receives a unique attempt ID.
                    pass

    def archive_orphaned_attempts(
        self,
        control: Path,
        receipts: Mapping[str, NodeReceipt],
    ) -> None:
        """Archive partial/orphan attempts while retaining validated node dirs."""
        retained: set[Path] = set()
        for node_id, receipt in receipts.items():
            record = self.records.get(node_id, {})
            command = record.get("command", {}) if isinstance(record, dict) else {}
            if receipt.state is NodeState.VALIDATED and isinstance(command, dict) and command.get("cwd"):
                retained.add(Path(command["cwd"]).parent.resolve())
        attempts_root = control / "attempts"
        if not attempts_root.is_dir():
            return
        archive_root = control / "archive" / "attempts"
        for node_root in attempts_root.iterdir():
            if not node_root.is_dir():
                continue
            for attempt in list(node_root.iterdir()):
                if not attempt.is_dir() or attempt.resolve() in retained:
                    continue
                destination = archive_root / node_root.name / f"{attempt.name}-{time.time_ns()}"
                destination.parent.mkdir(parents=True, exist_ok=True)
                try:
                    attempt.replace(destination)
                except OSError:
                    pass
