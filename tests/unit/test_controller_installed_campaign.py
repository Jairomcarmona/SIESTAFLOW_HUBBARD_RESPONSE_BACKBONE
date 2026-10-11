"""Installed console lifecycle using synthetic, non-scientific child processes."""

from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path

import pytest

from hubbardflow.domain.perturbation_plan import ResolvedPerturbationPlan
from tests.unit.controller_installed_campaign_support import (
    initialize_synthetic_campaign,
    ledger_node_id,
    read_controller_ledger,
    run_installed_controller_attempt,
    terminate_installed_controller_after_child_ready,
    write_controller_reservation,
)


@pytest.mark.skipif(
    os.name != "posix", reason="installed campaign lifecycle requires Linux/WSL POSIX process semantics"
)
def test_installed_console_runs_synthetic_campaign_resume_and_changed_input_refusals(tmp_path: Path) -> None:
    manifest, _siesta, mpi = initialize_synthetic_campaign(tmp_path)
    stop_after_reference = tmp_path / "tasks/hf1-lru/attempt-1-stop.json"
    first = run_installed_controller_attempt(
        tmp_path,
        manifest,
        mpi,
        1,
        {"HF_TEST_STOP_AFTER_REFERENCE": str(stop_after_reference)},
    )
    assert first.returncode == 0, first.stderr
    first_rows = read_controller_ledger(tmp_path / "tasks/hf1-lru/attempt-1.jsonl")
    assert [row["event"] for row in first_rows] == [
        "LAUNCH_INTENT",
        "LAUNCH_STARTED",
        "LAUNCH_FINISHED",
        "NODE_SETTLED",
    ]
    assert ledger_node_id(first_rows[-1]) == "reference"
    assert (manifest.parent / ".siestaflow/dag-checkpoint.json").is_file()
    assert (manifest.parent / "resume-baseline.json").is_file()

    descriptor, prior_ledger = write_controller_reservation(
        tmp_path,
        manifest,
        mpi,
        2,
        {
            "HF_TEST_BLOCK_AFTER_REFERENCE": "1",
            "HF_TEST_CHILD_STARTED": str(tmp_path / "attempt-2-child-started"),
            "HF_TEST_CHILD_TERM": str(tmp_path / "attempt-2-child-term"),
        },
    )
    neutral = terminate_installed_controller_after_child_ready(
        tmp_path,
        manifest,
        descriptor,
        tmp_path / "attempt-2-child-started",
        prior_ledger=prior_ledger,
    )
    assert neutral.returncode == 0, neutral.stderr
    second_rows = read_controller_ledger(tmp_path / "tasks/hf1-lru/attempt-2.jsonl")
    assert [row["event"] for row in second_rows] == [
        "LAUNCH_INTENT",
        "LAUNCH_STARTED",
        "LAUNCH_ABANDONED",
    ]
    assert ledger_node_id(second_rows[0]) != "reference"
    assert (tmp_path / "attempt-2-child-term").read_text(encoding="utf-8") == "term"
    assert (tmp_path / "fake-launch-count").read_text(encoding="utf-8") == "2"
    verdict = json.loads((tmp_path / "tasks/hf1-lru/resume-verdict-2.json").read_text(encoding="utf-8"))
    assert verdict["decision"] == "CONTINUE"
    assert verdict["check_resume"]["native_status"] == "NOT_ESTABLISHED"
    reference_launches = [
        row
        for row in (*first_rows, *second_rows)
        if row["event"] == "LAUNCH_INTENT" and ledger_node_id(row) == "reference"
    ]
    assert len(reference_launches) == 1


@pytest.mark.skipif(
    os.name != "posix", reason="installed campaign lifecycle requires Linux/WSL POSIX process semantics"
)
@pytest.mark.parametrize("changed", ["policy", "plan", "pseudo", "parent_dm"])
def test_installed_campaign_changed_inputs_exit_75_without_current_launch(
    tmp_path: Path, changed: str
) -> None:
    manifest, _siesta, mpi = initialize_synthetic_campaign(tmp_path)
    first = run_installed_controller_attempt(
        tmp_path,
        manifest,
        mpi,
        1,
        {"HF_TEST_STOP_AFTER_REFERENCE": str(tmp_path / "tasks/hf1-lru/attempt-1-stop.json")},
    )
    assert first.returncode == 0, first.stderr

    if changed == "policy":
        campaign = json.loads(manifest.read_text(encoding="utf-8"))
        campaign["analysis_policy"]["polynomial_degree"] = 1
        manifest.write_text(json.dumps(campaign), encoding="utf-8")
    elif changed == "plan":
        plan_path = manifest.parent / str(
            json.loads(manifest.read_text(encoding="utf-8"))["resolved_perturbation_plan_file"]
        )
        old_plan = ResolvedPerturbationPlan.from_mapping(json.loads(plan_path.read_text(encoding="utf-8")))
        new_plan = replace(old_plan, planner_version=f"{old_plan.planner_version}-synthetic-change")
        plan_path.write_text(json.dumps(new_plan.to_mapping()), encoding="utf-8")
        assert (
            ResolvedPerturbationPlan.from_mapping(json.loads(plan_path.read_text(encoding="utf-8")))
            == new_plan
        )
    elif changed == "pseudo":
        (manifest.parent / "pseudopotentials/Co.psml").write_text(
            "<psml><functional>PBE GGA</functional><input-file>Co 27</input-file><!-- changed --></psml>\n",
            encoding="utf-8",
        )
    else:
        (manifest.parent / "static/parent.DM").write_bytes(b"changed synthetic parent density matrix\n")

    launch_count_before = (tmp_path / "fake-launch-count").read_text(encoding="utf-8")
    second = run_installed_controller_attempt(tmp_path, manifest, mpi, 2)
    assert second.returncode == 75, second.stderr
    assert read_controller_ledger(tmp_path / "tasks/hf1-lru/attempt-2.jsonl") == []
    assert (tmp_path / "fake-launch-count").read_text(encoding="utf-8") == launch_count_before
    verdict = json.loads((tmp_path / "tasks/hf1-lru/resume-verdict-2.json").read_text(encoding="utf-8"))
    assert verdict["decision"] == "REFUSE"
    assert verdict["reason"] == "RESUME_INPUTS_CHANGED"


@pytest.mark.skipif(
    os.name != "posix", reason="installed campaign lifecycle requires Linux/WSL POSIX process semantics"
)
def test_installed_console_cooperatively_terminates_active_synthetic_node(tmp_path: Path) -> None:
    manifest, _siesta, mpi = initialize_synthetic_campaign(tmp_path)
    descriptor, _ = write_controller_reservation(
        tmp_path,
        manifest,
        mpi,
        1,
        {
            "HF_TEST_BLOCK_AFTER_REFERENCE": "1",
            "HF_TEST_CHILD_STARTED": str(tmp_path / "child-started"),
            "HF_TEST_CHILD_TERM": str(tmp_path / "child-term"),
        },
    )
    worker = terminate_installed_controller_after_child_ready(
        tmp_path, manifest, descriptor, tmp_path / "child-started"
    )
    assert worker.returncode == 0, f"stdout={worker.stdout!r}, stderr={worker.stderr!r}"
    assert (tmp_path / "child-term").read_text(encoding="utf-8") == "term"
    rows = read_controller_ledger(tmp_path / "tasks/hf1-lru/attempt-1.jsonl")
    events = [str(row["event"]) for row in rows]
    assert events[:4] == ["LAUNCH_INTENT", "LAUNCH_STARTED", "LAUNCH_FINISHED", "NODE_SETTLED"]
    assert events[4:] == ["LAUNCH_INTENT", "LAUNCH_STARTED", "LAUNCH_ABANDONED"]
    assert rows[-1]["reason"] == "STOP_REQUESTED"
    interrupted_node = ledger_node_id(rows[-1])
    assert not any(row["event"] == "NODE_SETTLED" and ledger_node_id(row) == interrupted_node for row in rows)


@pytest.mark.skipif(
    os.name != "posix", reason="installed campaign lifecycle requires Linux/WSL POSIX process semantics"
)
def test_installed_console_recovers_checkpoint_before_missing_settlement(tmp_path: Path) -> None:
    manifest, _siesta, mpi = initialize_synthetic_campaign(tmp_path)
    first = run_installed_controller_attempt(
        tmp_path,
        manifest,
        mpi,
        1,
        {"HF_TEST_STOP_AFTER_REFERENCE": str(tmp_path / "tasks/hf1-lru/attempt-1-stop.json")},
    )
    assert first.returncode == 0, first.stderr
    original_path = tmp_path / "tasks/hf1-lru/attempt-1.jsonl"
    original_rows = read_controller_ledger(original_path)
    assert original_rows[-1]["event"] == "NODE_SETTLED"

    # Model the precise checkpoint-saved / settlement-not-appended crash window:
    # preserve the native receipt and FINISHED trace, omit only the final settle row.
    crash_window = tmp_path / "tasks/hf1-lru/attempt-1-crash-window.jsonl"
    crash_window.parent.mkdir(parents=True, exist_ok=True)
    crash_window.write_text(
        "\n".join(json.dumps(row, sort_keys=True, separators=(",", ":")) for row in original_rows[:-1])
        + "\n",
        encoding="utf-8",
    )
    descriptor, _ = write_controller_reservation(
        tmp_path,
        manifest,
        mpi,
        2,
        {
            "HF_TEST_BLOCK_AFTER_REFERENCE": "1",
            "HF_TEST_CHILD_STARTED": str(tmp_path / "attempt-2-child-started"),
            "HF_TEST_CHILD_TERM": str(tmp_path / "attempt-2-child-term"),
        },
    )
    worker = terminate_installed_controller_after_child_ready(
        tmp_path,
        manifest,
        descriptor,
        tmp_path / "attempt-2-child-started",
        prior_ledger=crash_window,
    )
    assert worker.returncode == 0, f"stdout={worker.stdout!r}, stderr={worker.stderr!r}"
    rows = read_controller_ledger(tmp_path / "tasks/hf1-lru/attempt-2.jsonl")
    assert [row["event"] for row in rows] == [
        "SETTLEMENT_RECOVERED",
        "LAUNCH_INTENT",
        "LAUNCH_STARTED",
        "LAUNCH_ABANDONED",
    ]
    assert ledger_node_id(rows[0]) == "reference"
    assert rows[0]["source_attempt_id"] == "attempt-1"
    assert ledger_node_id(rows[1]) != "reference"
    assert (tmp_path / "attempt-2-child-term").read_text(encoding="utf-8") == "term"
    assert (tmp_path / "fake-launch-count").read_text(encoding="utf-8") == "2"
