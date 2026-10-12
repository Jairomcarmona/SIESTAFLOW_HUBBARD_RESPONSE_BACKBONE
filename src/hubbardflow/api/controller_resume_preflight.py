"""Read-only B.3 early rejection before native campaign admission."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from hubbardflow.api import check_resume

from .controller_contracts import ControllerContractError, load_strict_json
from .controller_ledger import ControllerLedgerObserver
from .controller_resume import (
    ResumeDecision,
    ResumeReason,
    ResumeVerdict,
    classify_resume_rules_1_to_3,
    validate_resume_verdict,
)
from .controller_resume_baseline import load_resume_request_raw


@dataclass(frozen=True)
class ResumePreflightOutcome:
    """Early B.3 refusal, or None to continue through native campaign validation."""

    verdict: ResumeVerdict | None


def preflight_resume_rejection(
    observer: ControllerLedgerObserver, manifest_path: Path
) -> ResumePreflightOutcome:
    """Run only B.3 rules 1–3 from authored files; neutral status grants no admission."""
    descriptor = observer.to_mapping()
    attempt_number = descriptor["attempt_number"]
    if not isinstance(attempt_number, int) or isinstance(attempt_number, bool):
        raise ControllerContractError("controller attempt_number must be an integer")
    previous = descriptor["previous_attempt"]
    if attempt_number <= 1:
        return ResumePreflightOutcome(None)
    if not isinstance(previous, dict):
        return ResumePreflightOutcome(_refusal(observer, "", ResumeReason.RESUME_EVIDENCE_INVALID, None, ()))
    previous_id = str(previous["attempt_id"])

    try:
        raw_campaign_value = load_strict_json(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(raw_campaign_value, dict):
            raise ControllerContractError("raw campaign manifest must be an object")
        baseline_value = load_strict_json(
            (observer.state_dir_path / "resume-baseline.json").read_text(encoding="utf-8")
        )
        if not isinstance(baseline_value, dict) or baseline_value.get("responses") != []:
            raise ControllerContractError("resume baseline is not a complete no-response request")
        # The public API validates the original request's complete shape and all
        # native plan/file fields. Refreshing observed evidence alone must not
        # turn a truncated or extended baseline into a valid B.3 request.
        check_resume(baseline_value)
        if (
            not _same_json_value(baseline_value["observed_plan"], baseline_value["expected_plan"])
            or not _same_json_value(baseline_value["observed_policies"], baseline_value["expected_policies"])
            or any(row["observed_sha256"] != row["expected_sha256"] for row in baseline_value["files"])
        ):
            raise ControllerContractError("resume baseline violates B.2 expected/observed equality")
        request = load_resume_request_raw(
            observer.state_dir_path / "resume-baseline.json", manifest_path, raw_campaign_value
        )
        result = check_resume(request.to_mapping())
        payload = load_strict_json(result.payload_json)
        if not isinstance(payload, dict):
            raise ControllerContractError("check_resume payload must be an object")
        native: dict[str, object] = {
            "native_status": result.native_status,
            "assessment": result.assessment.value,
            **{key: payload[key] for key in ("changed", "reusable_response_ids", "physical_equivalence")},
        }
    except (ControllerContractError, OSError, UnicodeDecodeError, ValueError, TypeError, KeyError):
        return ResumePreflightOutcome(
            _refusal(observer, previous_id, ResumeReason.RESUME_EVIDENCE_INVALID, None, ())
        )

    early = classify_resume_rules_1_to_3(native)
    if early.reason is None:
        return ResumePreflightOutcome(None)
    return ResumePreflightOutcome(_refusal(observer, previous_id, early.reason, native, early.blocking))


def _same_json_value(left: object, right: object) -> bool:
    """Compare B.2's authored JSON without Python's bool/int or int/float equality."""
    return json.dumps(
        left, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ) == json.dumps(right, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _refusal(
    observer: ControllerLedgerObserver,
    previous_attempt_id: str,
    reason: ResumeReason,
    native: Mapping[str, object] | None,
    blocking: tuple[str, ...],
) -> ResumeVerdict:
    verdict = ResumeVerdict(
        observer.task_id,
        observer.attempt_id,
        previous_attempt_id or "missing-previous-attempt",
        None,
        ResumeDecision.REFUSE,
        reason,
        None if native is None else dict(native),
        blocking,
        None,
    )
    validate_resume_verdict(verdict.to_mapping())
    return verdict
