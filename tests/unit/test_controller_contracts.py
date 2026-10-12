"""Synthetic checks for the ADR-017 QRAFT wire formats."""

from __future__ import annotations

import json
import os
import sys
from io import TextIOWrapper
from pathlib import Path
from threading import Event, Timer
from typing import Literal

import pytest

from hubbardflow.api.controller_contracts import (
    ControllerContractError,
    load_controller_reservation,
)
from hubbardflow.api.controller_ledger import (
    ControllerLedger,
    ControllerLedgerObserver,
    LedgerEntry,
    argv_sha256,
)
from hubbardflow.api.controller_resume import (
    DagNode,
    NodeEvidence,
    ResumeDecision,
    ResumeEvidence,
    ResumeReason,
    evaluate_resume,
)
from hubbardflow.api.controller_resume_ledger import parse_ledger_history
from hubbardflow.execution.dag_contract import NodeState
from hubbardflow.execution.generic_executor import NodeReceipt
from hubbardflow.execution.lr_dag import LRDagNode, LRNodeKind
from hubbardflow.execution.runtime_adapters import (
    ControllerLaunchFailed,
    ControllerStopRequested,
    LocalSubprocessExecutor,
    NodeCommand,
)


def _reservation_payload(*, stop_at: str = "2099-10-11T19:00:00Z") -> dict[str, object]:
    return {
        "contract": "qraft.controller-reservation@1.0",
        "run_fingerprint": "a" * 64,
        "task_id": "hf1-lru",
        "attempt_id": "attempt-1",
        "attempt_number": 1,
        "authority_generation": None,
        "capability": {"capability_id": "hubbardflow.hf1.lr-u", "version": "1", "plugin_version": "1"},
        "allocation": {"scheduler": "local", "allocation_id": "local-1"},
        "reserved": {
            "hosts": ["node-a"],
            "nodes": 1,
            "runtime_cpus": 4,
            "min_cpus": 4,
            "scheduler_cpus_on_host": {"value": 4, "source": "LOCAL_PROFILE_DECLARATION"},
        },
        "containment": {
            "method": "SUBREAPER_PIDFD",
            "supervisor": {
                "pid": 10,
                "start_time_ticks": "1",
                "boot_id": "12345678-1234-1234-1234-123456789abc",
            },
        },
        "inner": {
            "launcher_kind": "openmpi",
            "launcher_command": ["/usr/bin/mpiexec"],
            "processes_per_node": 4,
            "cpus_per_process": 1,
            "max_concurrent": 1,
            "environment": {},
        },
        "deadline": {"stop_launching_at": stop_at, "hard_stop_at": "2099-10-11T20:00:00Z"},
        "paths": {
            "state_dir": "controller-state/hf1-lru",
            "stop_request": "tasks/hf1-lru/stop-request.json",
            "inner_ledger": "tasks/hf1-lru/inner-ledger.jsonl",
            "resume_verdict": "tasks/hf1-lru/resume-verdict.json",
        },
        "previous_attempt": None,
    }


def test_ledger_appends_validated_lines_and_continues_sequence(tmp_path: Path) -> None:
    ledger_path = tmp_path / "inner.jsonl"
    ledger = ControllerLedger(ledger_path)
    key = {"checkpoint_identity": "adaptive:abc", "node_id": "reference"}
    ledger.append(
        LedgerEntry(
            1,
            "LAUNCH_INTENT",
            "hf1",
            "attempt-1",
            key["checkpoint_identity"],
            key["node_id"],
            trace_id="hf1/attempt-1/1",
            at="2026-10-11T19:00:00Z",
            hosts=("node-a",),
            ranks=4,
            cpus_per_rank=1,
            argv_sha256=argv_sha256(("mpiexec", "siesta")),
        )
    )
    continued = ControllerLedger(ledger_path)
    continued.append(
        LedgerEntry(
            2,
            "LAUNCH_STARTED",
            "hf1",
            "attempt-1",
            key["checkpoint_identity"],
            key["node_id"],
            trace_id="hf1/attempt-1/1",
            at="2026-10-11T19:00:01Z",
            pid=1234,
        )
    )
    rows = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines()]
    assert [row["seq"] for row in rows] == [1, 2]
    assert rows[0]["key"] == key
    assert rows[0]["trace_id"] == "hf1/attempt-1/1"


def test_ledger_rejects_invalid_event_without_writing(tmp_path: Path) -> None:
    ledger_path = tmp_path / "inner.jsonl"
    ledger = ControllerLedger(ledger_path)
    with pytest.raises(ControllerContractError, match="invalid ledger event"):
        ledger.append(
            LedgerEntry(
                1,
                "LAUNCH_INTENT",
                "hf1",
                "attempt-1",
                "adaptive:abc",
                "reference",
                trace_id="hf1/attempt-1/1",
            )
        )
    assert not ledger_path.exists()


def test_ledger_rejects_non_contiguous_existing_book(tmp_path: Path) -> None:
    ledger_path = tmp_path / "inner.jsonl"
    ledger_path.write_text('{"seq":2}\n', encoding="utf-8")
    with pytest.raises(ControllerContractError, match="non-contiguous"):
        ControllerLedger(ledger_path)


def test_node_settled_serializes_null_digest_and_attempt_books_are_independent(tmp_path: Path) -> None:
    prior_path = tmp_path / "attempt-1.jsonl"
    prior = ControllerLedger(prior_path)
    prior.append(
        LedgerEntry(
            1,
            "NODE_SETTLED",
            "hf1-lru",
            "attempt-1",
            "adaptive:abc",
            "reference",
            trace_id="hf1-lru/attempt-1/1",
            native_state="FAILED",
            evidence_digest=None,
        )
    )
    settled = json.loads(prior_path.read_text(encoding="utf-8"))
    assert "evidence_digest" in settled and settled["evidence_digest"] is None

    current_path = tmp_path / "attempt-2.jsonl"
    current = ControllerLedger(current_path)
    assert current.next_seq == 1
    with pytest.raises(ControllerContractError, match="already settled"):
        current.require_launch_allowed("adaptive:abc", "reference", "attempt-2", prior.entries)
    assert not current_path.exists()


def test_ledger_rejects_duplicate_json_keys_and_non_finite_numbers(tmp_path: Path) -> None:
    ledger_path = tmp_path / "inner.jsonl"
    ledger_path.write_text('{"seq":1,"seq":1}\n', encoding="utf-8")
    with pytest.raises(ControllerContractError, match="duplicate JSON property"):
        ControllerLedger(ledger_path)
    ledger_path.write_text('{"seq":NaN}\n', encoding="utf-8")
    with pytest.raises(ControllerContractError, match="non-finite JSON"):
        ControllerLedger(ledger_path)


def test_reservation_loader_rejects_unknown_fields(tmp_path: Path) -> None:
    descriptor_path = tmp_path / "reservation.json"
    descriptor_path.write_text(
        '{"contract":"qraft.controller-reservation@1.0","extra":true}', encoding="utf-8"
    )
    with pytest.raises(ControllerContractError, match="invalid controller reservation"):
        load_controller_reservation(descriptor_path)


def test_reservation_accepts_equal_deadlines_and_compares_nanoseconds(tmp_path: Path) -> None:
    descriptor_path = tmp_path / "reservation.json"
    value = _reservation_payload(stop_at="2099-10-11T20:00:00.000000000Z")
    descriptor_path.write_text(json.dumps(value), encoding="utf-8")
    load_controller_reservation(descriptor_path)

    deadline = value["deadline"]
    assert isinstance(deadline, dict)
    deadline["stop_launching_at"] = "2099-10-11T20:00:00.000000001Z"
    descriptor_path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ControllerContractError, match="must not exceed"):
        load_controller_reservation(descriptor_path)


class _SyntheticFactory:
    def __init__(self, command: NodeCommand):
        self.command = command

    def command_for(self, _node: LRDagNode) -> NodeCommand:
        return self.command


class _SyntheticValidator:
    def validate(self, node: LRDagNode, _command: NodeCommand, _completed: object) -> NodeReceipt:
        return NodeReceipt(node.node_id, NodeState.VALIDATED, "b" * 64)


def test_synthetic_process_lifecycle_writes_intent_before_settlement(tmp_path: Path) -> None:
    descriptor_path = tmp_path / "reservation.json"
    descriptor_path.write_text(json.dumps(_reservation_payload()), encoding="utf-8")
    descriptor = load_controller_reservation(descriptor_path)
    observer = ControllerLedgerObserver(descriptor, tmp_path)
    node = LRDagNode("reference", LRNodeKind.REFERENCE, ())
    command = NodeCommand((sys.executable, "-c", "print('synthetic')"), tmp_path)
    executor = LocalSubprocessExecutor(
        _SyntheticFactory(command),
        _SyntheticValidator(),
        observer=observer,
        checkpoint_identity="adaptive:abc",
    )

    receipt = executor.execute(node)
    observer.node_settled(node.node_id, receipt.state.value, receipt.evidence_digest)

    ledger = [
        json.loads(line)
        for line in (tmp_path / "tasks" / "hf1-lru" / "inner-ledger.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert [item["event"] for item in ledger] == [
        "LAUNCH_INTENT",
        "LAUNCH_STARTED",
        "LAUNCH_FINISHED",
        "NODE_SETTLED",
    ]
    assert ledger[0]["key"] == {"checkpoint_identity": "adaptive:abc", "node_id": "reference"}
    assert ledger[1]["pid"] > 0


@pytest.mark.skipif(os.name != "posix", reason="cooperative SIGTERM semantics require POSIX")
def test_synthetic_stop_abandons_running_process_without_settlement(tmp_path: Path) -> None:
    descriptor_path = tmp_path / "reservation.json"
    descriptor_path.write_text(json.dumps(_reservation_payload()), encoding="utf-8")
    descriptor = load_controller_reservation(descriptor_path)
    observer = ControllerLedgerObserver(descriptor, tmp_path)
    node = LRDagNode("reference", LRNodeKind.REFERENCE, ())
    marker = tmp_path / "cooperative-term-received"
    script = (
        f"import pathlib,signal,sys,time; marker=pathlib.Path({str(marker)!r}); "
        "signal.signal(signal.SIGTERM, lambda *_: (marker.write_text('term'), sys.exit(0))); "
        "time.sleep(10)"
    )
    command = NodeCommand(
        (sys.executable, "-c", script),
        tmp_path,
    )
    stop_event = Event()
    executor = LocalSubprocessExecutor(
        _SyntheticFactory(command),
        _SyntheticValidator(),
        observer=observer,
        checkpoint_identity="adaptive:abc",
        stop_event=stop_event,
    )
    timer = Timer(0.8, stop_event.set)
    timer.start()
    try:
        with pytest.raises(ControllerStopRequested):
            executor.execute(node)
    finally:
        timer.cancel()
    ledger = [
        json.loads(line)
        for line in (tmp_path / "tasks" / "hf1-lru" / "inner-ledger.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert [item["event"] for item in ledger] == ["LAUNCH_INTENT", "LAUNCH_STARTED", "LAUNCH_ABANDONED"]
    assert not (tmp_path / "failure.json").exists()
    assert marker.read_text(encoding="utf-8") == "term"


def test_stop_before_launch_is_cooperative_without_intent_or_open_handles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    descriptor_path = tmp_path / "reservation.json"
    descriptor_path.write_text(json.dumps(_reservation_payload()), encoding="utf-8")
    observer = ControllerLedgerObserver(load_controller_reservation(descriptor_path), tmp_path)
    node = LRDagNode("reference", LRNodeKind.REFERENCE, ())
    stdin_path = tmp_path / "input.fdf"
    stdin_path.write_text("synthetic input", encoding="utf-8")
    command = NodeCommand(
        (sys.executable, "-c", "raise SystemExit(0)"),
        tmp_path,
        stdin_path=stdin_path,
        stdout_path=tmp_path / "stdout.txt",
        stderr_path=tmp_path / "stderr.txt",
    )
    stop_event = Event()
    stop_event.set()
    opened: list[TextIOWrapper] = []
    original_open = Path.open

    def capture_open(
        path: Path,
        mode: Literal["r", "w"] = "r",
        *,
        encoding: str | None = None,
        newline: str | None = None,
    ) -> TextIOWrapper:
        handle = original_open(path, mode, encoding=encoding, newline=newline)
        opened.append(handle)
        return handle

    from hubbardflow.execution import runtime_adapters

    monkeypatch.setattr(Path, "open", capture_open)
    monkeypatch.setattr(
        runtime_adapters,
        "Popen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("stop forbids launch")),
    )
    executor = LocalSubprocessExecutor(
        _SyntheticFactory(command),
        _SyntheticValidator(),
        observer=observer,
        checkpoint_identity="adaptive:abc",
        stop_event=stop_event,
    )

    with pytest.raises(ControllerStopRequested):
        executor.execute(node)

    assert opened and all(handle.closed for handle in opened)
    assert not observer.ledger.path.exists()
    assert not (tmp_path / "failure.json").exists()


def test_process_creation_oserror_is_abandoned_without_fake_exit_or_checkpoint(tmp_path: Path) -> None:
    descriptor_path = tmp_path / "reservation.json"
    descriptor_path.write_text(json.dumps(_reservation_payload()), encoding="utf-8")
    descriptor = load_controller_reservation(descriptor_path)
    observer = ControllerLedgerObserver(descriptor, tmp_path)
    node = LRDagNode("reference", LRNodeKind.REFERENCE, ())
    command = NodeCommand((str(tmp_path / "missing-launcher"),), tmp_path)
    executor = LocalSubprocessExecutor(
        _SyntheticFactory(command),
        _SyntheticValidator(),
        observer=observer,
        checkpoint_identity="adaptive:abc",
    )
    with pytest.raises(ControllerLaunchFailed):
        executor.execute(node)
    rows = [json.loads(line) for line in observer.ledger.path.read_text(encoding="utf-8").splitlines()]
    assert [item["event"] for item in rows] == ["LAUNCH_INTENT", "LAUNCH_ABANDONED"]
    assert rows[-1]["reason"] == "LAUNCH_FAILED"
    assert "exit_code" not in rows[-1]
    assert not (tmp_path / "failure.json").exists()


def test_process_creation_valueerror_is_abandoned_without_fake_exit_or_checkpoint(tmp_path: Path) -> None:
    descriptor_path = tmp_path / "reservation.json"
    descriptor_path.write_text(json.dumps(_reservation_payload()), encoding="utf-8")
    observer = ControllerLedgerObserver(load_controller_reservation(descriptor_path), tmp_path)
    node = LRDagNode("reference", LRNodeKind.REFERENCE, ())
    command = NodeCommand((sys.executable, "-c", "\x00"), tmp_path)
    executor = LocalSubprocessExecutor(
        _SyntheticFactory(command),
        _SyntheticValidator(),
        observer=observer,
        checkpoint_identity="adaptive:abc",
    )
    with pytest.raises(ControllerLaunchFailed):
        executor.execute(node)
    rows = [json.loads(line) for line in observer.ledger.path.read_text(encoding="utf-8").splitlines()]
    assert [item["event"] for item in rows] == ["LAUNCH_INTENT", "LAUNCH_ABANDONED"]
    assert rows[-1]["reason"] == "LAUNCH_FAILED"
    assert "exit_code" not in rows[-1]
    assert not (tmp_path / "failure.json").exists()


def test_settlement_must_match_the_exact_finished_trace_when_building_resume_evidence(
    tmp_path: Path,
) -> None:
    descriptor_path = tmp_path / "reservation.json"
    descriptor_path.write_text(json.dumps(_reservation_payload()), encoding="utf-8")
    observer = ControllerLedgerObserver(load_controller_reservation(descriptor_path), tmp_path)
    observer.set_checkpoint_identity("adaptive:abc")
    observer.launch_intent("reference", "adaptive:abc", ("python", "-c", "pass"))
    observer.launch_started("reference", 1234)
    observer.launch_finished("reference", 0)
    observer.ledger.append(
        LedgerEntry(
            observer.ledger.next_seq,
            "NODE_SETTLED",
            observer.task_id,
            observer.attempt_id,
            "adaptive:abc",
            "reference",
            trace_id=f"{observer.task_id}/{observer.attempt_id}/999",
            native_state="VALIDATED",
            evidence_digest="b" * 64,
        )
    )

    history = parse_ledger_history(observer.history_entries, observer.task_id, {"reference"})
    evidence = ResumeEvidence(
        observer.task_id,
        "attempt-2",
        "attempt-1",
        {
            "native_status": "NOT_ESTABLISHED",
            "assessment": "NOT_ESTABLISHED",
            "changed": [],
            "reusable_response_ids": [],
            "physical_equivalence": "NOT_ESTABLISHED",
        },
        True,
        "adaptive:abc",
        history.checkpoint_identity,
        history.settlements,
        history.finished_unsettled,
        (NodeEvidence("reference", "REFERENCE", "VALIDATED", "b" * 64, "RETAINED"),),
        (DagNode("reference", "REFERENCE", ()),),
        history.errors,
        history.node_ids,
    )

    verdict = evaluate_resume(evidence)

    assert "ledger:settlement-trace-mismatch:reference" in history.errors
    assert verdict.decision is ResumeDecision.REFUSE
    assert verdict.reason is ResumeReason.LEDGER_CHECKPOINT_INCONSISTENT


def test_prepare_controller_attempt_refuses_settlement_from_another_finished_trace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import SimpleNamespace

    from hubbardflow.api import controller_resume_baseline
    from hubbardflow.api.controller_resume_baseline import ResumeRequest
    from hubbardflow.execution.campaign_runner import CampaignRunner, ReuseInspection

    previous_path = tmp_path / "tasks" / "hf1-lru" / "attempt-1.jsonl"
    previous = ControllerLedger(previous_path)
    trace = "hf1-lru/attempt-1/1"
    previous.append(
        LedgerEntry(
            1,
            "LAUNCH_INTENT",
            "hf1-lru",
            "attempt-1",
            "adaptive:abc",
            "reference",
            trace_id=trace,
            hosts=("node-a",),
            ranks=4,
            cpus_per_rank=1,
            argv_sha256="d" * 64,
        )
    )
    previous.append(
        LedgerEntry(
            2,
            "LAUNCH_STARTED",
            "hf1-lru",
            "attempt-1",
            "adaptive:abc",
            "reference",
            trace_id=trace,
            pid=321,
        )
    )
    previous.append(
        LedgerEntry(
            3,
            "LAUNCH_FINISHED",
            "hf1-lru",
            "attempt-1",
            "adaptive:abc",
            "reference",
            trace_id=trace,
            exit_code=0,
        )
    )
    previous.append(
        LedgerEntry(
            4,
            "NODE_SETTLED",
            "hf1-lru",
            "attempt-1",
            "adaptive:abc",
            "reference",
            trace_id="hf1-lru/attempt-1/999",
            native_state="VALIDATED",
            evidence_digest="b" * 64,
        )
    )
    raw_descriptor = _reservation_payload()
    raw_descriptor.update(
        {
            "attempt_id": "attempt-2",
            "attempt_number": 2,
            "previous_attempt": {
                "attempt_id": "attempt-1",
                "outcome": "INTERRUPTED",
                "closure": "CLOSED",
                "state_manifest_sha256": "c" * 64,
            },
        }
    )
    raw_descriptor["paths"] = {
        "state_dir": "controller-state/hf1-lru",
        "stop_request": "tasks/hf1-lru/attempt-2-stop.json",
        "inner_ledger": "tasks/hf1-lru/attempt-2.jsonl",
        "resume_verdict": "tasks/hf1-lru/resume-verdict.json",
    }
    descriptor_path = tmp_path / "reservation.json"
    descriptor_path.write_text(json.dumps(raw_descriptor), encoding="utf-8")
    observer = ControllerLedgerObserver(
        load_controller_reservation(descriptor_path), tmp_path, prior_ledger_paths=(previous_path,)
    )

    manifest_path = tmp_path / "controller-state" / "hf1-lru" / "campaign.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text("{}", encoding="utf-8")
    receipt = NodeReceipt("reference", NodeState.VALIDATED, "b" * 64)
    checkpoint_path = tmp_path / "checkpoint.json"
    checkpoint_path.write_text("{}", encoding="utf-8")
    runner = object.__new__(CampaignRunner)
    runner.manifest_path = manifest_path
    runner.campaign = {"_perturbation_plan": object()}
    runner.controller_observer = observer
    monkeypatch.setattr(
        runner,
        "dag",
        SimpleNamespace(nodes=(LRDagNode("reference", LRNodeKind.REFERENCE, ()),)),
        raising=False,
    )
    monkeypatch.setattr(
        runner,
        "executor",
        SimpleNamespace(
            checkpoint=SimpleNamespace(
                path=checkpoint_path,
                campaign_digest="adaptive:abc",
                load=lambda: {"reference": receipt},
            )
        ),
        raising=False,
    )
    monkeypatch.setattr(
        runner,
        "_revalidate_reuse",
        lambda *, dry_run: ReuseInspection((), (), ()),
    )
    monkeypatch.setattr(
        controller_resume_baseline,
        "load_resume_request",
        lambda *_args: ResumeRequest({}, {}, {}, {}, ()),
    )
    monkeypatch.setattr(
        "hubbardflow.api.check_resume",
        lambda _request: SimpleNamespace(
            native_status="NOT_ESTABLISHED",
            assessment=SimpleNamespace(value="NOT_ESTABLISHED"),
            payload_json=json.dumps(
                {
                    "changed": [],
                    "reusable_response_ids": [],
                    "physical_equivalence": "NOT_ESTABLISHED",
                }
            ),
        ),
    )

    assert runner.prepare_controller_attempt() == 75
    verdict = json.loads(observer.resume_verdict_path.read_text(encoding="utf-8"))
    assert verdict["decision"] == "REFUSE"
    assert verdict["reason"] == "LEDGER_CHECKPOINT_INCONSISTENT"
    assert "ledger:settlement-trace-mismatch:reference" in verdict["blocking"]


def test_new_same_key_intent_clears_observers_old_finish_before_settlement(tmp_path: Path) -> None:
    descriptor_path = tmp_path / "reservation.json"
    descriptor_path.write_text(json.dumps(_reservation_payload()), encoding="utf-8")
    observer = ControllerLedgerObserver(load_controller_reservation(descriptor_path), tmp_path)
    observer.set_checkpoint_identity("adaptive:abc")
    node_id = "reference"
    first_trace = observer.launch_intent(node_id, "adaptive:abc", ("python", "-c", "first"))
    observer.launch_started(node_id, 1234)
    observer.launch_finished(node_id, 0)

    second_trace = observer.launch_intent(node_id, "adaptive:abc", ("python", "-c", "second"))
    observer.node_settled(node_id, "VALIDATED", "c" * 64)
    rows_after_stale_settlement = observer.ledger.entries
    assert not any(row.get("event") == "NODE_SETTLED" for row in rows_after_stale_settlement)

    observer.launch_started(node_id, 1235)
    observer.launch_finished(node_id, 0)
    observer.node_settled(node_id, "VALIDATED", "c" * 64)
    settled = [row for row in observer.ledger.entries if row.get("event") == "NODE_SETTLED"]
    assert len(settled) == 1
    assert settled[0]["trace_id"] == second_trace
    assert settled[0]["trace_id"] != first_trace
