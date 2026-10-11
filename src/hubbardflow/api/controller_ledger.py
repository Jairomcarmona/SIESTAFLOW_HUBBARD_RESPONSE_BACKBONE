"""Attempt-scoped, append-only controller ledgers and native launch observer."""

from __future__ import annotations

import json
import os
import time
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path, PurePosixPath

from .controller_contracts import (
    ControllerContractError,
    ControllerReservation,
    controller_schema_validator,
    load_strict_json,
    utc_timestamp_nanoseconds,
)


@dataclass(frozen=True)
class LedgerEntry:
    """One native ledger event; optional fields are checked against its event schema."""

    seq: int
    event: str
    task_id: str
    attempt_id: str
    checkpoint_identity: str
    node_id: str
    trace_id: str | None = None
    at: str | None = None
    hosts: tuple[str, ...] | None = None
    ranks: int | None = None
    cpus_per_rank: int | None = None
    argv_sha256: str | None = None
    pid: int | None = None
    exit_code: int | None = None
    reason: str | None = None
    native_state: str | None = None
    evidence_digest: str | None = None
    source_attempt_id: str | None = None

    def to_mapping(self) -> dict[str, object]:
        """Serialize only fields present in this event."""
        fields: dict[str, object] = {
            "contract": "qraft.controller-inner-ledger@1.0",
            "seq": self.seq,
            "event": self.event,
            "at": self.at or datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "task_id": self.task_id,
            "attempt_id": self.attempt_id,
            "key": {"checkpoint_identity": self.checkpoint_identity, "node_id": self.node_id},
        }
        optional: tuple[tuple[str, object | None], ...] = (
            ("trace_id", self.trace_id),
            ("hosts", None if self.hosts is None else list(self.hosts)),
            ("ranks", self.ranks),
            ("cpus_per_rank", self.cpus_per_rank),
            ("argv_sha256", self.argv_sha256),
            ("pid", self.pid),
            ("exit_code", self.exit_code),
            ("reason", self.reason),
            ("native_state", self.native_state),
            ("evidence_digest", self.evidence_digest),
            ("source_attempt_id", self.source_attempt_id),
        )
        fields.update({key: value for key, value in optional if value is not None})
        if self.event == "NODE_SETTLED":
            fields["evidence_digest"] = self.evidence_digest
        return fields


class ControllerLedger:
    """Append-only JSONL ledger that flushes each validated event to storage."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._validator = controller_schema_validator("qraft-controller-ledger-entry.schema.json")
        self._next_seq = self._read_next_seq()

    def append(self, entry: LedgerEntry) -> None:
        """Validate, append, flush and fsync one ledger event."""
        if entry.seq != self._next_seq:
            raise ControllerContractError(f"ledger sequence must be {self._next_seq}")
        if (
            entry.seq <= 0
            or (entry.ranks is not None and entry.ranks <= 0)
            or (entry.cpus_per_rank is not None and entry.cpus_per_rank <= 0)
        ):
            raise ControllerContractError("ledger sequence, ranks, and CPUs per rank must be positive")
        value = entry.to_mapping()
        errors = sorted(self._validator.iter_errors(value), key=lambda item: list(item.path))
        if errors:
            raise ControllerContractError(f"invalid ledger event: {errors[0].message}")
        encoded = json.dumps(
            value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(encoded + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        self._next_seq += 1

    def require_launch_allowed(
        self,
        checkpoint_identity: str,
        node_id: str,
        attempt_id: str,
        prior_entries: tuple[Mapping[str, object], ...] = (),
    ) -> None:
        """Reject an already settled key or a duplicate active launch intent."""
        active: set[str] = set()
        for row in (*prior_entries, *self.entries):
            key = row.get("key")
            if not isinstance(key, dict) or key.get("checkpoint_identity") != checkpoint_identity:
                continue
            if key.get("node_id") != node_id:
                continue
            if row.get("event") in {"NODE_SETTLED", "SETTLEMENT_RECOVERED"}:
                raise ControllerContractError(f"native node key is already settled: {node_id}")
            if row.get("attempt_id") != attempt_id:
                continue
            if row.get("event") == "LAUNCH_INTENT" and row.get("attempt_id") == attempt_id:
                active.add(str(row.get("trace_id", "")))
            elif (
                row.get("event") in {"LAUNCH_FINISHED", "LAUNCH_ABANDONED"}
                and row.get("attempt_id") == attempt_id
            ):
                active.discard(str(row.get("trace_id", "")))
        if active:
            raise ControllerContractError(f"native node already has an unclosed launch intent: {node_id}")

    @property
    def next_seq(self) -> int:
        """Return the sequence number assigned to the next appended entry."""
        return self._next_seq

    @property
    def entries(self) -> tuple[Mapping[str, object], ...]:
        """Return validated, detached prior ledger rows in sequence order."""
        if not self.path.exists():
            return ()
        values: list[Mapping[str, object]] = []
        with self.path.open("r", encoding="utf-8") as stream:
            for line in stream:
                value = load_strict_json(line)
                if not isinstance(value, dict):
                    raise ControllerContractError("existing ledger row is not an object")
                values.append(value)
        return tuple(values)

    def _read_next_seq(self) -> int:
        if not self.path.exists():
            return 1
        expected = 1
        try:
            with self.path.open("r", encoding="utf-8") as stream:
                for line in stream:
                    value = load_strict_json(line)
                    if not isinstance(value, dict) or value.get("seq") != expected:
                        raise ControllerContractError(
                            "existing ledger has malformed or non-contiguous sequence"
                        )
                    errors = list(self._validator.iter_errors(value))
                    if errors:
                        raise ControllerContractError("existing ledger contains an invalid event")
                    expected += 1
        except (OSError, json.JSONDecodeError) as exc:
            raise ControllerContractError(f"existing ledger is unreadable: {exc}") from exc
        return expected


class ControllerLedgerObserver:
    """Translate native node process callbacks into ADR-017 ledger records."""

    def __init__(
        self,
        descriptor: ControllerReservation,
        run_root: str | Path,
        *,
        prior_ledger_paths: tuple[Path, ...] = (),
    ):
        self.descriptor = descriptor
        value = descriptor.to_mapping()
        paths = value["paths"]
        reserved = value["reserved"]
        inner = value["inner"]
        if not isinstance(paths, dict) or not isinstance(reserved, dict) or not isinstance(inner, dict):
            raise ControllerContractError("validated reservation has malformed nested data")
        self.task_id = str(value["task_id"])
        self.attempt_id = str(value["attempt_id"])
        self.checkpoint_identity: str | None = None
        self.hosts = tuple(str(host) for host in reserved["hosts"])
        self._reserved_cpus = int(reserved["runtime_cpus"])
        self.ranks = int(inner["processes_per_node"])
        self.cpus_per_rank = int(inner["cpus_per_process"])
        launcher_command = inner["launcher_command"]
        if not isinstance(launcher_command, list):
            raise ControllerContractError("validated inner launcher command must be an array")
        self.launcher_command = tuple(str(part) for part in launcher_command)
        self.launcher_kind = str(inner["launcher_kind"])
        environment = inner["environment"]
        if not isinstance(environment, dict) or not all(
            isinstance(key, str) and isinstance(item, str) for key, item in environment.items()
        ):
            raise ControllerContractError("validated inner environment must map strings to strings")
        self.inner_environment = dict(environment)
        deadline = value["deadline"]
        self.stop_launching_at = str(deadline["stop_launching_at"]) if isinstance(deadline, dict) else ""
        root = Path(run_root).resolve()
        self.state_dir_path = resolve_controller_path(root, str(paths["state_dir"]))
        self.stop_request_path = resolve_controller_path(root, str(paths["stop_request"]))
        self.inner_ledger_path = resolve_controller_path(root, str(paths["inner_ledger"]))
        self.resume_verdict_path = resolve_controller_path(root, str(paths["resume_verdict"]))
        self.ledger = ControllerLedger(self.inner_ledger_path)
        self.prior_ledgers = tuple(ControllerLedger(path) for path in prior_ledger_paths)
        for row in self.ledger.entries:
            if row.get("task_id") != self.task_id or row.get("attempt_id") != self.attempt_id:
                raise ControllerContractError("current ledger contains another task or attempt")
        for book in self.prior_ledgers:
            if any(row.get("task_id") != self.task_id for row in book.entries):
                raise ControllerContractError("prior ledger belongs to another QRAFT task")
        self._traces: dict[str, str] = {}
        self._finished_nodes: dict[str, str] = {}
        self._abandoned_nodes: set[str] = set()

    @property
    def reserved_hosts(self) -> tuple[str, ...]:
        """Return the host list granted by QRAFT for this controller attempt."""
        return self.hosts

    @property
    def reserved_cpus(self) -> int:
        """Return the observed runtime CPU reservation from the descriptor."""
        return self._reserved_cpus

    def to_mapping(self) -> dict[str, object]:
        """Return a detached copy of the validated reservation descriptor."""
        return self.descriptor.to_mapping()

    @property
    def history_entries(self) -> tuple[Mapping[str, object], ...]:
        """Return explicit prior-attempt books followed by this attempt's book."""
        return tuple(row for ledger in self.prior_ledgers for row in ledger.entries) + self.ledger.entries

    def should_stop_launching(self) -> bool:
        """Return whether the stop file or the declared launch deadline has arrived."""
        if self.stop_request_path.exists():
            return True
        deadline = utc_timestamp_nanoseconds(self.stop_launching_at)
        return time.time_ns() >= deadline

    def launch_intent(self, node_id: str, checkpoint_identity: str, argv: tuple[str, ...]) -> str:
        """Persist the native checkpoint key before process creation."""
        if self.checkpoint_identity is None:
            self.checkpoint_identity = checkpoint_identity
        elif checkpoint_identity != self.checkpoint_identity:
            raise ControllerContractError("native checkpoint identity changed during controller run")
        if self.should_stop_launching():
            raise ControllerContractError("launch deadline or stop request has arrived")
        prior_entries = tuple(row for book in self.prior_ledgers for row in book.entries)
        self.ledger.require_launch_allowed(checkpoint_identity, node_id, self.attempt_id, prior_entries)
        seq = self.ledger.next_seq
        trace_id = f"{self.task_id}/{self.attempt_id}/{seq}"
        self.ledger.append(
            LedgerEntry(
                seq,
                "LAUNCH_INTENT",
                self.task_id,
                self.attempt_id,
                checkpoint_identity,
                node_id,
                trace_id=trace_id,
                hosts=self.hosts,
                ranks=self.ranks,
                cpus_per_rank=self.cpus_per_rank,
                argv_sha256=argv_sha256(argv),
            )
        )
        self._traces[node_id] = trace_id
        self._finished_nodes.pop(node_id, None)
        self._abandoned_nodes.discard(node_id)
        return trace_id

    def set_checkpoint_identity(self, checkpoint_identity: str) -> None:
        """Bind retry reconciliation to the native checkpoint identity."""
        if self.checkpoint_identity not in {None, checkpoint_identity}:
            raise ControllerContractError("native checkpoint identity changed during controller run")
        self.checkpoint_identity = checkpoint_identity

    def settlement_recovered(
        self,
        node_id: str,
        native_state: str,
        evidence_digest: str | None,
        source_attempt_id: str,
    ) -> None:
        """Record a checkpoint receipt whose prior process finished before its ledger settlement."""
        if self.checkpoint_identity is None:
            raise ControllerContractError("settlement recovery has no native checkpoint identity")
        self.ledger.append(
            LedgerEntry(
                self.ledger.next_seq,
                "SETTLEMENT_RECOVERED",
                self.task_id,
                self.attempt_id,
                self.checkpoint_identity,
                node_id,
                native_state=native_state,
                evidence_digest=evidence_digest,
                source_attempt_id=source_attempt_id,
            )
        )

    def launch_started(self, node_id: str, pid: int) -> None:
        """Record the created native process."""
        self._append_for_node(node_id, "LAUNCH_STARTED", pid=pid)

    def launch_finished(self, node_id: str, exit_code: int) -> None:
        """Record a process that exited without cooperative abandonment."""
        self._append_for_node(node_id, "LAUNCH_FINISHED", exit_code=exit_code)
        trace_id = self._traces[node_id]
        self._finished_nodes[node_id] = trace_id
        self._abandoned_nodes.discard(node_id)

    def launch_abandoned(self, node_id: str, reason: str) -> None:
        """Record a launch interrupted by a cooperative stop request."""
        self._append_for_node(node_id, "LAUNCH_ABANDONED", reason=reason)
        self._finished_nodes.pop(node_id, None)
        self._abandoned_nodes.add(node_id)

    def node_settled(self, node_id: str, native_state: str, evidence_digest: str | None) -> None:
        """Record settlement after the native checkpoint write has returned."""
        trace_id = self._traces.get(node_id)
        if (
            trace_id is None
            or self._finished_nodes.get(node_id) != trace_id
            or node_id in self._abandoned_nodes
        ):
            return
        self._append_for_node(
            node_id, "NODE_SETTLED", native_state=native_state, evidence_digest=evidence_digest
        )

    def _append_for_node(
        self,
        node_id: str,
        event: str,
        *,
        pid: int | None = None,
        exit_code: int | None = None,
        reason: str | None = None,
        native_state: str | None = None,
        evidence_digest: str | None = None,
    ) -> None:
        trace_id = self._traces.get(node_id)
        if trace_id is None or self.checkpoint_identity is None:
            raise ControllerContractError(f"ledger event {event} has no launch intent for {node_id}")
        entry = LedgerEntry(
            self.ledger.next_seq,
            event,
            self.task_id,
            self.attempt_id,
            self.checkpoint_identity,
            node_id,
            trace_id=trace_id,
            pid=pid,
            exit_code=exit_code,
            reason=reason,
            native_state=native_state,
            evidence_digest=evidence_digest,
        )
        self.ledger.append(entry)


def argv_sha256(argv: tuple[str, ...]) -> str:
    """Digest a command vector without executing or normalizing its arguments."""
    encoded = json.dumps(list(argv), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return sha256(encoded).hexdigest()


def resolve_controller_path(root: Path, value: str) -> Path:
    relative = PurePosixPath(value)
    if relative.is_absolute() or "\\" in value or any(part in {"", ".", ".."} for part in value.split("/")):
        raise ControllerContractError("controller descriptor paths must be safe and POSIX relative paths")
    resolved = (root / Path(*relative.parts)).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ControllerContractError("controller descriptor path escapes the QRAFT run directory") from exc
    return resolved
