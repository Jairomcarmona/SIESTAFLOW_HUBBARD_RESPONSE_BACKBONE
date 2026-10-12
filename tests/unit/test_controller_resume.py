"""Conformance checks against the normative ADR-017 resume vectors."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import cast

import pytest

from hubbardflow.api.controller_contracts import ControllerContractError
from hubbardflow.api.controller_resume import (
    DagNode,
    NodeEvidence,
    ResumeDecision,
    ResumeEvidence,
    ResumeReason,
    evaluate_resume,
    recoverable_settlements,
    validate_resume_verdict,
)
from hubbardflow.api.controller_resume_baseline import create_resume_baseline
from hubbardflow.api.controller_resume_ledger import FinishedLaunch, LedgerSettlement
from hubbardflow.domain.perturbation_plan import ResolvedPerturbationPlan

_FIXTURE = Path(__file__).parents[2] / "tests" / "fixtures" / "controller-resume-rules" / "cases.json"


def test_all_normative_resume_vectors_match_expected_verdicts() -> None:
    payload = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    dag = tuple(
        DagNode(item["node_id"], item["kind"], tuple(item["dependencies"])) for item in payload["dag"]
    )
    for case in payload["cases"]:
        checkpoint = case["checkpoint"]
        ledger = case["ledger"]
        settlements = tuple(
            LedgerSettlement(item["node_id"], item["native_state"], item["evidence_digest"], "attempt-0001")
            for item in ledger["settled"]
        )
        finished = tuple(FinishedLaunch(node_id, "attempt-0001") for node_id in ledger["finished_unsettled"])
        receipts = tuple(
            NodeEvidence(
                item["node_id"],
                next(node.kind for node in dag if node.node_id == item["node_id"]),
                item["state"],
                item["evidence_digest"],
                item["revalidation"],
            )
            for item in case["receipts"]
        )
        evidence = ResumeEvidence(
            case["expect"]["task_id"],
            case["expect"]["attempt_id"],
            case["expect"]["previous_attempt_id"],
            cast(dict[str, object] | None, case["check_resume"]),
            checkpoint["loads"],
            checkpoint["campaign_digest"] if checkpoint["loads"] else None,
            ledger["checkpoint_identity"] if ledger["checkpoint_identity"] else None,
            settlements,
            finished,
            receipts,
            dag,
        )
        assert evaluate_resume(evidence).to_mapping() == case["expect"], case["name"]


def test_resume_baseline_uses_raw_resolved_plan_and_raw_campaign_mapping(tmp_path: Path) -> None:
    manifest = tmp_path / "campaign.json"
    manifest.write_text('{"raw":true}', encoding="utf-8")
    (tmp_path / "plan.json").write_text('{"resolved":{"native":true}}', encoding="utf-8")
    (tmp_path / "input.dat").write_text("source bytes", encoding="utf-8")
    raw_campaign: dict[str, object] = {
        "resolved_perturbation_plan_file": "plan.json",
        "input_files": [{"path": "input.dat"}],
        "policy_with_defaults_not_injected": {"value": "as-authored"},
    }

    baseline = create_resume_baseline(manifest, raw_campaign, cast(ResolvedPerturbationPlan, object()))

    assert baseline is not None
    mapped = baseline.to_mapping()
    assert mapped["expected_plan"] == {"resolved": {"native": True}}
    assert mapped["expected_policies"] == {"campaign": raw_campaign}


def _evidence(
    *,
    state: str = "VALIDATED",
    revalidation: str = "RETAINED",
    finished: tuple[FinishedLaunch, ...] = (),
    settlements: tuple[LedgerSettlement, ...] = (),
    native: dict[str, object] | None = None,
    warnings: tuple[str, ...] = (),
) -> ResumeEvidence:
    return ResumeEvidence(
        "task-1",
        "attempt-2",
        "attempt-1",
        native
        or {
            "native_status": "NOT_ESTABLISHED",
            "assessment": "NOT_ESTABLISHED",
            "changed": [],
            "reusable_response_ids": [],
            "physical_equivalence": "NOT_ESTABLISHED",
        },
        True,
        "checkpoint-1",
        "checkpoint-1",
        settlements,
        finished,
        (NodeEvidence("response:a", "PERTURBATION", state, "digest-a", revalidation),),
        (DagNode("response:a", "PERTURBATION", ()),),
        revalidation_warnings=warnings,
    )


def test_failed_checkpoint_receipt_recovers_finished_launch_before_refusing() -> None:
    evidence = _evidence(
        state="FAILED_EXECUTION",
        finished=(FinishedLaunch("response:a", "attempt-1"),),
    )

    recovered = recoverable_settlements(evidence)
    verdict = evaluate_resume(evidence)

    assert recovered == (LedgerSettlement("response:a", "FAILED_EXECUTION", "digest-a", "attempt-1"),)
    assert verdict.decision is ResumeDecision.REFUSE
    assert verdict.reason is ResumeReason.SETTLED_FAILURE_PRESENT
    assert verdict.blocking == ("response:a",)


def test_derived_digest_warning_does_not_veto_native_revalidation() -> None:
    evidence = _evidence(
        settlements=(LedgerSettlement("response:a", "VALIDATED", "digest-a", "attempt-1"),),
        warnings=("EVIDENCE_FILE_DIGEST_MISMATCH:response:a",),
    )

    verdict = evaluate_resume(evidence)

    assert verdict.decision is ResumeDecision.CONTINUE
    assert verdict.reason is ResumeReason.TECHNICAL_CONTINUATION


def test_identity_mismatch_without_changes_is_rule_one_with_literal_native_result() -> None:
    native: dict[str, object] = {
        "native_status": "IDENTITY_MISMATCH",
        "assessment": "FAIL",
        "changed": [],
        "reusable_response_ids": ["native-response-id"],
        "physical_equivalence": "NATIVE_RESULT_VALUE",
    }
    evidence = _evidence(native=native)

    verdict = evaluate_resume(evidence)

    assert verdict.to_mapping() == {
        "contract": "qraft.controller-resume-verdict@1.0",
        "task_id": "task-1",
        "attempt_id": "attempt-2",
        "previous_attempt_id": "attempt-1",
        "checkpoint_identity": "checkpoint-1",
        "decision": "REFUSE",
        "reason": "RESUME_EVIDENCE_INVALID",
        "check_resume": native,
        "blocking": [],
        "continuation": None,
        "scientific_effect": "NONE",
    }
    assert recoverable_settlements(evidence) == ()


@pytest.mark.parametrize("mutation", ["neutral", "changed", "blocking"])
def test_resume_evidence_invalid_schema_allows_only_null_or_empty_changed_mismatch(mutation: str) -> None:
    native: dict[str, object] = {
        "native_status": "IDENTITY_MISMATCH",
        "assessment": "FAIL",
        "changed": [],
        "reusable_response_ids": [],
        "physical_equivalence": "NOT_ESTABLISHED",
    }
    mapping = evaluate_resume(_evidence(native=native)).to_mapping()
    candidate = deepcopy(mapping)
    if mutation == "neutral":
        candidate["check_resume"] = {
            **native,
            "native_status": "NOT_ESTABLISHED",
            "assessment": "NOT_ESTABLISHED",
        }
    elif mutation == "changed":
        candidate["check_resume"] = {**native, "changed": ["input:file"]}
    else:
        candidate["blocking"] = ["invented-blocker"]

    with pytest.raises(ControllerContractError):
        validate_resume_verdict(candidate)
