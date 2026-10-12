"""B.3 early refusals precede HubbardFlow campaign admission."""

from __future__ import annotations

import importlib
import json
import os
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from hubbardflow.api import ApiOperation, ApiResult, controller_resume_preflight
from hubbardflow.api.controller_contracts import load_controller_reservation
from hubbardflow.api.controller_ledger import ControllerLedgerObserver
from hubbardflow.api.controller_resume import ResumeReason
from hubbardflow.api.controller_resume_baseline import create_resume_baseline, write_resume_baseline
from hubbardflow.api.controller_resume_preflight import preflight_resume_rejection
from tests.unit.test_perturbation_plan import plan as synthetic_plan


def _raw_campaign() -> dict[str, object]:
    return {
        "campaign_id": "synthetic-controller",
        "resolved_perturbation_plan_file": "resolved-plan.json",
        "input_files": [{"path": "pseudo.psml"}, {"path": "parent.DM"}],
        "policy": {"xc": "PBE", "analysis": "frozen"},
    }


def _prepared_retry(tmp_path: Path) -> tuple[Path, dict[str, object], ControllerLedgerObserver, Path]:
    root = tmp_path / "controller-state" / "hf1-lru"
    root.mkdir(parents=True)
    manifest = root / "campaign.json"
    raw = _raw_campaign()
    manifest.write_text(json.dumps(raw), encoding="utf-8")
    (root / "resolved-plan.json").write_text(json.dumps(synthetic_plan().to_mapping()), encoding="utf-8")
    (root / "pseudo.psml").write_bytes(b"synthetic pseudo input")
    (root / "parent.DM").write_bytes(b"synthetic parent density matrix")
    baseline = create_resume_baseline(manifest, raw, synthetic_plan())
    assert baseline is not None
    baseline_path = root / "resume-baseline.json"
    write_resume_baseline(baseline_path, baseline)

    descriptor = {
        "contract": "qraft.controller-reservation@1.0",
        "run_fingerprint": "a" * 64,
        "task_id": "hf1-lru",
        "attempt_id": "attempt-2",
        "attempt_number": 2,
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
        "deadline": {
            "stop_launching_at": "2099-10-11T19:00:00Z",
            "hard_stop_at": "2099-10-11T20:00:00Z",
        },
        "paths": {
            "state_dir": "controller-state/hf1-lru",
            "stop_request": "tasks/hf1-lru/attempt-2-stop.json",
            "inner_ledger": "tasks/hf1-lru/attempt-2.jsonl",
            "resume_verdict": "tasks/hf1-lru/resume-verdict.json",
        },
        "previous_attempt": {
            "attempt_id": "attempt-1",
            "outcome": "INTERRUPTED",
            "closure": "CLOSED",
            "state_manifest_sha256": "b" * 64,
        },
    }
    descriptor_path = tmp_path / "reservation.json"
    descriptor_path.write_text(json.dumps(descriptor), encoding="utf-8")
    observer = ControllerLedgerObserver(load_controller_reservation(descriptor_path), tmp_path)
    return manifest, raw, observer, baseline_path


def test_neutral_preflight_allows_full_native_validation_to_follow(tmp_path: Path) -> None:
    manifest, _raw, observer, _baseline = _prepared_retry(tmp_path)

    outcome = preflight_resume_rejection(observer, manifest)

    assert outcome.verdict is None


def test_neutral_controller_attempt_reaches_full_campaign_loader_and_runner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest, _raw, observer, _baseline = _prepared_retry(tmp_path)
    from hubbardflow.execution import campaign_runner

    calls: list[str] = []
    root = manifest.parent

    def load_campaign(_path: str | Path) -> dict[str, object]:
        calls.append("load")
        return {"_campaign_root": str(root), "campaign_id": "synthetic-controller"}

    class FakeRunner:
        def __init__(self, _manifest: Path, **_kwargs: object) -> None:
            calls.append("runner")
            self.factory = SimpleNamespace(state=None)

        def prepare_controller_attempt(self) -> None:
            calls.append("prepare")

        def advance(self, mode: str, _heartbeat: object) -> int:
            calls.append(f"advance:{mode}")
            return 0

    monkeypatch.setattr(campaign_runner, "load_campaign_v2", load_campaign)
    monkeypatch.setattr(campaign_runner, "CampaignRunner", FakeRunner)
    monkeypatch.setattr(
        campaign_runner,
        "fcntl",
        SimpleNamespace(LOCK_EX=1, LOCK_NB=2, flock=lambda *_args: None),
    )

    assert campaign_runner.run_campaign_worker(manifest, "run", controller_observer=observer) == 0
    assert calls == ["load", "runner", "prepare", "advance:resume"]


@pytest.mark.parametrize("changed_input", ["policy", "plan", "pseudo", "parent_dm"])
def test_changed_resume_inputs_refuse_before_campaign_admission(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, changed_input: str
) -> None:
    manifest, raw, observer, _baseline = _prepared_retry(tmp_path)
    root = manifest.parent
    if changed_input == "policy":
        raw["policy"] = {"xc": "PBE", "analysis": "changed"}
        manifest.write_text(json.dumps(raw), encoding="utf-8")
    elif changed_input == "plan":
        changed_plan = replace(synthetic_plan(), planner_version="synthetic-planner-changed")
        (root / "resolved-plan.json").write_text(json.dumps(changed_plan.to_mapping()), encoding="utf-8")
    elif changed_input == "pseudo":
        (root / "pseudo.psml").write_bytes(b"changed pseudo input")
    else:
        (root / "parent.DM").write_bytes(b"changed parent density matrix")

    from hubbardflow.execution import campaign_runner

    def campaign_admission_was_reached(_path: str | Path) -> dict[str, object]:
        raise AssertionError("campaign loader must not run before B.3 early refusal")

    monkeypatch.setattr(campaign_runner, "load_campaign_v2", campaign_admission_was_reached)
    monkeypatch.setattr(
        campaign_runner,
        "fcntl",
        SimpleNamespace(LOCK_EX=1, LOCK_NB=2, flock=lambda *_args: None),
    )

    exit_code = campaign_runner.run_campaign_worker(manifest, "resume", controller_observer=observer)

    assert exit_code == 75
    verdict = json.loads(observer.resume_verdict_path.read_text(encoding="utf-8"))
    assert verdict["decision"] == "REFUSE"
    assert verdict["reason"] == ResumeReason.RESUME_INPUTS_CHANGED.value
    assert verdict["checkpoint_identity"] is None


@pytest.mark.parametrize("baseline_text", [None, "{"])
def test_missing_or_malformed_baseline_refuses_before_check_resume(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, baseline_text: str | None
) -> None:
    manifest, _raw, observer, baseline_path = _prepared_retry(tmp_path)
    monkeypatch.setattr(
        controller_resume_preflight,
        "check_resume",
        lambda _request: (_ for _ in ()).throw(AssertionError("check_resume must not run")),
    )
    if baseline_text is None:
        baseline_path.unlink()
    else:
        baseline_path.write_text(baseline_text, encoding="utf-8")

    outcome = preflight_resume_rejection(observer, manifest)

    assert outcome.verdict is not None
    assert outcome.verdict.reason is ResumeReason.RESUME_EVIDENCE_INVALID
    assert outcome.verdict.check_resume is None


@pytest.mark.parametrize(
    "mutation",
    ["missing_observed_plan", "missing_observed_policies", "missing_observed_digest", "extra_field"],
)
def test_incomplete_or_extended_original_baseline_refuses_before_campaign_admission(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    manifest, _raw, observer, baseline_path = _prepared_retry(tmp_path)
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    if mutation == "missing_observed_plan":
        del baseline["observed_plan"]
    elif mutation == "missing_observed_policies":
        del baseline["observed_policies"]
    elif mutation == "missing_observed_digest":
        del baseline["files"][0]["observed_sha256"]
    else:
        baseline["uncontracted"] = True
    baseline_path.write_text(json.dumps(baseline), encoding="utf-8")

    from hubbardflow.execution import campaign_runner

    def campaign_admission_was_reached(_path: str | Path) -> dict[str, object]:
        raise AssertionError("campaign loader must not run for an invalid original baseline")

    monkeypatch.setattr(campaign_runner, "load_campaign_v2", campaign_admission_was_reached)
    monkeypatch.setattr(
        campaign_runner,
        "fcntl",
        SimpleNamespace(LOCK_EX=1, LOCK_NB=2, flock=lambda *_args: None),
    )

    assert campaign_runner.run_campaign_worker(manifest, "resume", controller_observer=observer) == 75
    verdict = json.loads(observer.resume_verdict_path.read_text(encoding="utf-8"))
    assert verdict["reason"] == ResumeReason.RESUME_EVIDENCE_INVALID.value
    assert verdict["check_resume"] is None


@pytest.mark.skipif(os.name != "posix", reason="native flock exclusion requires POSIX")
def test_identity_mismatch_empty_changed_refuses_before_checkpoint_or_launch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest, _raw, observer, _baseline = _prepared_retry(tmp_path)
    from hubbardflow.execution import campaign_runner, generic_executor, runtime_adapters

    fcntl = importlib.import_module("fcntl")
    checkpoint = observer.state_dir_path / ".siestaflow" / "dag-checkpoint.json"
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    checkpoint.write_text("{ malformed checkpoint", encoding="utf-8")
    native = {
        "native_status": "IDENTITY_MISMATCH",
        "assessment": "FAIL",
        "changed": [],
        "reusable_response_ids": ["native-response-remains-literal"],
        "physical_equivalence": "NATIVE_VALUE_REMAINS_LITERAL",
    }
    check_resume_requests: list[object] = []

    def identity_mismatch_result(_request: object) -> ApiResult:
        check_resume_requests.append(_request)
        payload = {key: value for key, value in native.items() if key not in {"native_status", "assessment"}}
        return ApiResult(ApiOperation.CHECK_RESUME, "IDENTITY_MISMATCH", json.dumps(payload))

    monkeypatch.setattr(
        controller_resume_preflight,
        "check_resume",
        identity_mismatch_result,
    )

    def admission_forbidden(_path: str | Path) -> dict[str, object]:
        raise AssertionError("B.3 rule 1 must refuse before native campaign admission")

    checkpoint_loads: list[Path] = []
    process_creations: list[tuple[object, ...]] = []

    def checkpoint_load_forbidden(self: object) -> dict[str, object]:
        checkpoint_loads.append(checkpoint)
        raise AssertionError("B.3 rule 1 must precede checkpoint loading")

    def process_creation_forbidden(*args: object, **_kwargs: object) -> None:
        process_creations.append(args)
        raise AssertionError("B.3 rule 1 must not create a child process")

    monkeypatch.setattr(campaign_runner, "load_campaign_v2", admission_forbidden)
    monkeypatch.setattr(generic_executor.JsonDagCheckpoint, "load", checkpoint_load_forbidden)
    monkeypatch.setattr(runtime_adapters, "Popen", process_creation_forbidden)
    lock_path = observer.state_dir_path / ".siestaflow" / "worker.lock"
    with lock_path.open("a+b") as held_lock:
        fcntl.flock(held_lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        with monkeypatch.context() as patch:
            patch.setattr(
                controller_resume_preflight,
                "preflight_resume_rejection",
                lambda *_args: (_ for _ in ()).throw(
                    AssertionError("the native worker lock must exclude preflight")
                ),
            )
            assert campaign_runner.run_campaign_worker(manifest, "resume", controller_observer=observer) == 2
    assert not observer.resume_verdict_path.exists()

    assert campaign_runner.run_campaign_worker(manifest, "resume", controller_observer=observer) == 75
    verdict = json.loads(observer.resume_verdict_path.read_text(encoding="utf-8"))
    assert verdict["decision"] == "REFUSE"
    assert verdict["reason"] == ResumeReason.RESUME_EVIDENCE_INVALID.value
    assert verdict["check_resume"] == native
    assert verdict["blocking"] == []
    assert verdict["continuation"] is None
    assert verdict["checkpoint_identity"] is None
    assert len(check_resume_requests) == 2
    assert checkpoint_loads == []
    assert process_creations == []
    assert not observer.inner_ledger_path.exists()


@pytest.mark.parametrize("field", ["observed_plan", "observed_policies", "observed_sha256"])
def test_original_baseline_must_have_equal_expected_and_observed_evidence(tmp_path: Path, field: str) -> None:
    manifest, _raw, observer, baseline_path = _prepared_retry(tmp_path)
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    if field == "observed_plan":
        baseline[field] = replace(synthetic_plan(), planner_version="other-fixture-version").to_mapping()
    elif field == "observed_policies":
        baseline[field] = {"campaign": {"different": "synthetic policy"}}
    else:
        baseline["files"][0][field] = "0" * 64
    baseline_path.write_text(json.dumps(baseline), encoding="utf-8")

    verdict = preflight_resume_rejection(observer, manifest).verdict
    assert verdict is not None
    assert verdict.reason is ResumeReason.RESUME_EVIDENCE_INVALID
    assert verdict.check_resume is None


def test_missing_retry_manifest_through_entrypoint_emits_75_before_loader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest, _raw, observer, _baseline = _prepared_retry(tmp_path)
    manifest.unlink()
    from hubbardflow.api import controller
    from hubbardflow.execution import campaign_runner

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(controller, "os", SimpleNamespace(name="posix"))
    monkeypatch.setattr(
        campaign_runner, "fcntl", SimpleNamespace(LOCK_EX=1, LOCK_NB=2, flock=lambda *_args: None)
    )
    monkeypatch.setattr(
        campaign_runner,
        "load_campaign_v2",
        lambda *_: (_ for _ in ()).throw(AssertionError("missing manifest must refuse before loader")),
    )
    result = controller.main(
        [
            "--qraft-reservation",
            "reservation.json",
            "--campaign",
            manifest.relative_to(tmp_path).as_posix(),
            "--prior-ledger",
            "tasks/hf1-lru/attempt-1.jsonl",
        ]
    )
    assert result == 75
    verdict = json.loads(observer.resume_verdict_path.read_text(encoding="utf-8"))
    assert verdict["reason"] == ResumeReason.RESUME_EVIDENCE_INVALID.value
    assert verdict["checkpoint_identity"] is None
    assert not observer.inner_ledger_path.exists()


@pytest.mark.parametrize("observed", [True, 1.0])
def test_baseline_json_equality_distinguishes_boolean_and_number_types(
    tmp_path: Path, observed: bool | float
) -> None:
    manifest, raw, observer, baseline_path = _prepared_retry(tmp_path)
    raw["policy"] = {"fixture_value": 1}
    manifest.write_text(json.dumps(raw), encoding="utf-8")
    baseline_request = create_resume_baseline(manifest, raw, synthetic_plan())
    assert baseline_request is not None
    write_resume_baseline(baseline_path, baseline_request)
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    baseline["observed_policies"]["campaign"]["policy"]["fixture_value"] = observed
    baseline_path.write_text(json.dumps(baseline), encoding="utf-8")

    verdict = preflight_resume_rejection(observer, manifest).verdict
    assert verdict is not None
    assert verdict.reason is ResumeReason.RESUME_EVIDENCE_INVALID
    assert verdict.check_resume is None


@pytest.mark.skipif(os.name != "posix", reason="native flock exclusion requires POSIX")
def test_native_worker_lock_excludes_preflight_and_releases_after_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fcntl = importlib.import_module("fcntl")

    from hubbardflow.execution import campaign_runner

    manifest, _raw, observer, _baseline = _prepared_retry(tmp_path)
    control = manifest.parent / ".siestaflow"
    control.mkdir()
    lock_path = control / "worker.lock"
    with lock_path.open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        with monkeypatch.context() as patch:
            patch.setattr(
                controller_resume_preflight,
                "preflight_resume_rejection",
                lambda *_: (_ for _ in ()).throw(AssertionError("lock must exclude preflight")),
            )
            assert campaign_runner.run_campaign_worker(manifest, "resume", controller_observer=observer) == 2
    assert not observer.resume_verdict_path.exists()
    (manifest.parent / "pseudo.psml").write_bytes(b"changed synthetic pseudo")
    assert campaign_runner.run_campaign_worker(manifest, "resume", controller_observer=observer) == 75
    with lock_path.open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    assert not observer.inner_ledger_path.exists()
