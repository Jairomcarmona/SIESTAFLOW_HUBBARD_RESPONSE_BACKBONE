"""Technical continuation checks for QRAFT retries; never grants scientific reuse."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from .controller_contracts import ControllerContractError, load_strict_json
from .controller_resume_ledger import FinishedLaunch, LedgerSettlement


class ResumeDecision(str, Enum):
    CONTINUE = "CONTINUE"
    REFUSE = "REFUSE"


class ResumeReason(str, Enum):
    TECHNICAL_CONTINUATION = "TECHNICAL_CONTINUATION"
    RESUME_EVIDENCE_INVALID = "RESUME_EVIDENCE_INVALID"
    RESUME_INPUTS_CHANGED = "RESUME_INPUTS_CHANGED"
    RESUME_STATUS_UNRECOGNIZED = "RESUME_STATUS_UNRECOGNIZED"
    CHECKPOINT_IDENTITY_MISMATCH = "CHECKPOINT_IDENTITY_MISMATCH"
    LEDGER_CHECKPOINT_INCONSISTENT = "LEDGER_CHECKPOINT_INCONSISTENT"
    SETTLED_FAILURE_PRESENT = "SETTLED_FAILURE_PRESENT"
    SETTLED_EVIDENCE_INVALID = "SETTLED_EVIDENCE_INVALID"


@dataclass(frozen=True)
class NodeEvidence:
    node_id: str
    kind: str
    state: str
    evidence_digest: str | None
    revalidation: str


@dataclass(frozen=True)
class DagNode:
    node_id: str
    kind: str
    dependencies: tuple[str, ...]


@dataclass(frozen=True)
class ResumeEvidence:
    task_id: str
    attempt_id: str
    previous_attempt_id: str
    check_resume: dict[str, object] | None
    checkpoint_loaded: bool
    checkpoint_identity: str | None
    ledger_checkpoint_identity: str | None
    settlements: tuple[LedgerSettlement, ...]
    finished_unsettled: tuple[FinishedLaunch, ...]
    receipts: tuple[NodeEvidence, ...]
    dag: tuple[DagNode, ...]
    ledger_errors: tuple[str, ...] = ()
    ledger_node_ids: tuple[str, ...] = ()
    revalidation_warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResumeContinuation:
    retained: tuple[str, ...]
    recovered: tuple[str, ...]
    launch_pending: tuple[str, ...]

    def to_mapping(self) -> dict[str, object]:
        return {
            "retained": list(self.retained),
            "recovered": list(self.recovered),
            "launch_pending": list(self.launch_pending),
        }


@dataclass(frozen=True)
class ResumeVerdict:
    task_id: str
    attempt_id: str
    previous_attempt_id: str
    checkpoint_identity: str | None
    decision: ResumeDecision
    reason: ResumeReason
    check_resume: dict[str, object] | None
    blocking: tuple[str, ...]
    continuation: ResumeContinuation | None

    def to_mapping(self) -> dict[str, object]:
        return {
            "contract": "qraft.controller-resume-verdict@1.0",
            "task_id": self.task_id,
            "attempt_id": self.attempt_id,
            "previous_attempt_id": self.previous_attempt_id,
            "checkpoint_identity": self.checkpoint_identity,
            "decision": self.decision.value,
            "reason": self.reason.value,
            "check_resume": self.check_resume,
            "blocking": list(self.blocking),
            "continuation": None if self.continuation is None else self.continuation.to_mapping(),
            "scientific_effect": "NONE",
        }


@dataclass(frozen=True)
class ResumeEarlyDecision:
    """B.3 rules 1–3 result, before checkpoint and native receipt inspection."""

    reason: ResumeReason | None
    blocking: tuple[str, ...]


def validate_resume_verdict(value: dict[str, object]) -> None:
    """Validate emitted verdicts against the byte-identical native schema."""
    schema_path = Path(__file__).with_name("schemas") / "qraft-controller-resume-verdict.schema"
    schema = load_strict_json(schema_path.read_text(encoding="utf-8"))
    if not isinstance(schema, dict):
        raise ControllerContractError("resume verdict schema must be a JSON object")
    errors = list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(value))
    if errors:
        raise ControllerContractError(f"invalid controller resume verdict: {errors[0].message}")


def evaluate_resume(evidence: ResumeEvidence) -> ResumeVerdict:
    """Apply ADR-017 B.3 in order using only native status and checkpoint facts."""
    native = evidence.check_resume
    decision = ResumeDecision.REFUSE
    early = classify_resume_rules_1_to_3(native)
    reason = early.reason or ResumeReason.RESUME_EVIDENCE_INVALID
    blocking = early.blocking
    continuation: ResumeContinuation | None = None
    if early.reason is None:
        if (
            not evidence.checkpoint_loaded
            or evidence.checkpoint_identity is None
            or (
                evidence.ledger_checkpoint_identity is not None
                and evidence.ledger_checkpoint_identity != evidence.checkpoint_identity
            )
        ):
            reason = ResumeReason.CHECKPOINT_IDENTITY_MISMATCH
        else:
            checkpoint_reason, blocking, continuation = _evaluate_checkpoint(evidence)
            reason = checkpoint_reason or ResumeReason.LEDGER_CHECKPOINT_INCONSISTENT
            if reason is ResumeReason.TECHNICAL_CONTINUATION:
                decision = ResumeDecision.CONTINUE
    verdict = ResumeVerdict(
        evidence.task_id,
        evidence.attempt_id,
        evidence.previous_attempt_id,
        evidence.checkpoint_identity,
        decision,
        reason,
        native,
        blocking,
        continuation,
    )
    validate_resume_verdict(verdict.to_mapping())
    return verdict


def classify_resume_rules_1_to_3(native: dict[str, object] | None) -> ResumeEarlyDecision:
    """Classify only native B.3 rules 1–3; neutral status grants no continuation."""
    if native is None:
        return ResumeEarlyDecision(ResumeReason.RESUME_EVIDENCE_INVALID, ())
    if native.get("native_status") == "IDENTITY_MISMATCH" and native.get("assessment") == "FAIL":
        raw_changed = native.get("changed")
        changed = tuple(sorted(str(item) for item in raw_changed)) if isinstance(raw_changed, list) else ()
        if not changed:
            raise ControllerContractError(
                "ADR-017 B.3 identity-mismatch with empty changed list is unresolved; see DFT issue #59"
            )
        return ResumeEarlyDecision(ResumeReason.RESUME_INPUTS_CHANGED, changed)
    if (
        native.get("native_status") != "NOT_ESTABLISHED"
        or native.get("assessment") != "NOT_ESTABLISHED"
        or native.get("changed") != []
        or native.get("reusable_response_ids") != []
        or native.get("physical_equivalence") != "NOT_ESTABLISHED"
    ):
        return ResumeEarlyDecision(ResumeReason.RESUME_STATUS_UNRECOGNIZED, ())
    return ResumeEarlyDecision(None, ())


def recoverable_settlements(evidence: ResumeEvidence) -> tuple[LedgerSettlement, ...]:
    """Return terminal receipts safe to annotate after B.3 rules 1–5 pass."""
    native = evidence.check_resume
    if not _native_resume_is_neutral(native):
        return ()
    if (
        not evidence.checkpoint_loaded
        or evidence.checkpoint_identity is None
        or (
            evidence.ledger_checkpoint_identity is not None
            and evidence.ledger_checkpoint_identity != evidence.checkpoint_identity
        )
    ):
        return ()
    reason, _blocking, _continuation = _evaluate_checkpoint(evidence, apply_terminal_rules=False)
    if reason is not None:
        return ()
    receipt_by_id = {item.node_id: item for item in evidence.receipts}
    settled_ids = {item.node_id for item in evidence.settlements}
    finished = {item.node_id: item for item in evidence.finished_unsettled}
    launchable = {node.node_id for node in evidence.dag if node.kind in {"REFERENCE", "PERTURBATION"}}
    return tuple(
        LedgerSettlement(node_id, receipt.state, receipt.evidence_digest, finished[node_id].attempt_id)
        for node_id, receipt in sorted(receipt_by_id.items())
        if node_id in launchable and node_id not in settled_ids and node_id in finished
    )


def _native_resume_is_neutral(native: dict[str, object] | None) -> bool:
    return (
        native is not None
        and native.get("native_status") == "NOT_ESTABLISHED"
        and native.get("assessment") == "NOT_ESTABLISHED"
        and native.get("changed") == []
        and native.get("reusable_response_ids") == []
        and native.get("physical_equivalence") == "NOT_ESTABLISHED"
    )


def _evaluate_checkpoint(
    evidence: ResumeEvidence,
    *,
    apply_terminal_rules: bool = True,
) -> tuple[ResumeReason | None, tuple[str, ...], ResumeContinuation | None]:
    receipt_by_id = {item.node_id: item for item in evidence.receipts}
    settlement_counts: dict[str, int] = {}
    settlements: dict[str, LedgerSettlement] = {}
    for item in evidence.settlements:
        settlement_counts[item.node_id] = settlement_counts.get(item.node_id, 0) + 1
        settlements[item.node_id] = item
    finished = {item.node_id: item for item in evidence.finished_unsettled}
    launchable = {node.node_id for node in evidence.dag if node.kind in {"REFERENCE", "PERTURBATION"}}
    dag_ids = {node.node_id for node in evidence.dag}
    bad: set[str] = set(evidence.ledger_errors)
    bad.update(set(evidence.ledger_node_ids) - dag_ids)
    bad.update(node_id for node_id, count in settlement_counts.items() if count > 1)
    bad.update(set(settlements) - launchable)
    bad.update(set(finished) - launchable)
    for node_id in launchable:
        settled = settlements.get(node_id)
        receipt = receipt_by_id.get(node_id)
        if settled is not None:
            if (
                receipt is None
                or settled.state != receipt.state
                or settled.evidence_digest != receipt.evidence_digest
            ):
                bad.add(node_id)
        elif receipt is not None and node_id not in finished:
            bad.add(node_id)
    if bad:
        return ResumeReason.LEDGER_CHECKPOINT_INCONSISTENT, tuple(sorted(bad)), None
    if not apply_terminal_rules:
        return None, (), None
    failures = {
        node_id
        for node_id in launchable
        if node_id in receipt_by_id and receipt_by_id[node_id].state != "VALIDATED"
    }
    if failures:
        return ResumeReason.SETTLED_FAILURE_PRESENT, tuple(sorted(failures)), None
    warnings = {
        item.node_id
        for item in evidence.receipts
        if item.node_id in launchable and item.revalidation == "DIGEST_WARNING"
    }
    warnings.update(
        warning.split(":", 1)[1]
        for warning in evidence.revalidation_warnings
        if warning.startswith("NODE_EVIDENCE_DIGEST_MISMATCH:") and warning.split(":", 1)[1] in launchable
    )
    invalid = {
        item.node_id
        for item in evidence.receipts
        if item.node_id in launchable and item.revalidation == "INVALID"
    }
    for node_id in tuple(invalid):
        pending = [node_id]
        while pending:
            parent = pending.pop()
            for node in evidence.dag:
                if parent in node.dependencies and node.node_id not in invalid:
                    invalid.add(node.node_id)
                    pending.append(node.node_id)
    invalid_launchable = invalid & launchable
    if invalid_launchable or warnings:
        return ResumeReason.SETTLED_EVIDENCE_INVALID, tuple(sorted(invalid_launchable | warnings)), None
    retained = tuple(
        sorted(
            node_id
            for node_id in launchable
            if node_id in receipt_by_id
            and receipt_by_id[node_id].state == "VALIDATED"
            and receipt_by_id[node_id].revalidation == "RETAINED"
        )
    )
    recovered = tuple(
        sorted(node_id for node_id in retained if node_id in finished and node_id not in settlements)
    )
    launch_pending = tuple(sorted(launchable - set(retained)))
    continuation = ResumeContinuation(retained, recovered, launch_pending)
    return ResumeReason.TECHNICAL_CONTINUATION, (), continuation
