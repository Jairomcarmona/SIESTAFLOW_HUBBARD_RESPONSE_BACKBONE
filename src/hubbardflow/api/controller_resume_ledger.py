"""Reconcile attempt-scoped controller ledgers against complete launch traces."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class LedgerSettlement:
    node_id: str
    state: str
    evidence_digest: str | None
    source_attempt_id: str


@dataclass(frozen=True)
class FinishedLaunch:
    node_id: str
    attempt_id: str


@dataclass(frozen=True)
class ParsedLedgerHistory:
    """Attempt-history projection after matching complete native launch traces."""

    checkpoint_identity: str | None
    settlements: tuple[LedgerSettlement, ...]
    finished_unsettled: tuple[FinishedLaunch, ...]
    node_ids: tuple[str, ...]
    errors: tuple[str, ...]


def parse_ledger_history(
    entries: Sequence[Mapping[str, object]], task_id: str, dag_node_ids: set[str]
) -> ParsedLedgerHistory:
    """Project explicit attempt books and reject events detached from their full launch trace."""
    errors: list[str] = []
    node_ids: list[str] = []
    identities: set[str] = set()
    intents: set[tuple[str, str, str, str]] = set()
    started: set[tuple[str, str, str, str]] = set()
    closed: set[tuple[str, str, str, str]] = set()
    finished: set[tuple[str, str, str, str]] = set()
    settlements: list[LedgerSettlement] = []
    latest_finish: dict[str, tuple[FinishedLaunch, tuple[str, str, str, str]]] = {}
    trace_events = {
        "LAUNCH_INTENT",
        "LAUNCH_STARTED",
        "LAUNCH_FINISHED",
        "LAUNCH_ABANDONED",
        "NODE_SETTLED",
    }

    for row in entries:
        raw_key = row.get("key")
        if not isinstance(raw_key, Mapping):
            errors.append("ledger:missing-key")
            continue
        node_id = str(raw_key.get("node_id", ""))
        identity = str(raw_key.get("checkpoint_identity", ""))
        node_ids.append(node_id)
        if node_id not in dag_node_ids:
            errors.append(f"ledger:unknown-node:{node_id}")
        if row.get("task_id") != task_id:
            errors.append("ledger:foreign-task")
        if identity:
            identities.add(identity)
        event = row.get("event")
        attempt_id = str(row.get("attempt_id", ""))
        trace_id = str(row.get("trace_id", ""))
        trace_key = (attempt_id, trace_id, node_id, identity)
        if event in trace_events and (not attempt_id or not trace_id or not identity):
            errors.append(f"ledger:missing-trace-identity:{node_id}")

        if event == "LAUNCH_INTENT":
            if trace_id != f"{task_id}/{attempt_id}/{row.get('seq')}":
                errors.append(f"ledger:intent-trace-mismatch:{node_id}")
            if trace_key in intents:
                errors.append(f"ledger:duplicate-intent:{node_id}")
            intents.add(trace_key)
            latest_finish.pop(node_id, None)
        elif event == "LAUNCH_STARTED":
            if trace_key not in intents or trace_key in started:
                errors.append(f"ledger:invalid-start:{node_id}")
            started.add(trace_key)
        elif event == "LAUNCH_FINISHED":
            if trace_key not in started or trace_key in closed:
                errors.append(f"ledger:invalid-finish:{node_id}")
            closed.add(trace_key)
            finished.add(trace_key)
            latest_finish[node_id] = (FinishedLaunch(node_id, attempt_id), trace_key)
        elif event == "LAUNCH_ABANDONED":
            if trace_key not in intents or trace_key in closed:
                errors.append(f"ledger:invalid-abandon:{node_id}")
            closed.add(trace_key)
            current = latest_finish.get(node_id)
            if current is not None and current[1] == trace_key:
                latest_finish.pop(node_id, None)

        if event in {"NODE_SETTLED", "SETTLEMENT_RECOVERED"}:
            source_attempt = str(row.get("source_attempt_id", attempt_id))
            raw_digest = row.get("evidence_digest")
            if event == "NODE_SETTLED":
                if source_attempt != attempt_id:
                    errors.append(f"ledger:settlement-attempt-mismatch:{node_id}")
                if trace_key not in finished:
                    errors.append(f"ledger:settlement-trace-mismatch:{node_id}")
            elif not any(
                trace[0] == source_attempt and trace[2] == node_id and trace[3] == identity
                for trace in finished
            ):
                errors.append(f"ledger:recovery-without-finish:{node_id}")
            settlements.append(
                LedgerSettlement(
                    node_id,
                    str(row.get("native_state", "")),
                    raw_digest if isinstance(raw_digest, str) else None,
                    source_attempt,
                )
            )
            current = latest_finish.get(node_id)
            clears_current = current is not None and (
                (event == "NODE_SETTLED" and current[1] == trace_key)
                or (event == "SETTLEMENT_RECOVERED" and current[0].attempt_id == source_attempt)
            )
            if clears_current:
                latest_finish.pop(node_id, None)

    checkpoint_identity = (
        next(iter(identities))
        if len(identities) == 1
        else "multiple-checkpoint-identities"
        if identities
        else None
    )
    return ParsedLedgerHistory(
        checkpoint_identity,
        tuple(settlements),
        tuple(item[0] for _, item in sorted(latest_finish.items())),
        tuple(node_ids),
        tuple(sorted(set(errors))),
    )
