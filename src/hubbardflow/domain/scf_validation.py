"""Prerecorded T0–T4 metrics checked against a preregistered protocol.

This validates supplied evidence and never runs a simulator or creates a truth
reference. A passing record alone cannot establish the production state gate.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum

from .scf_ladder_models import ScfLadderError, _ScfRecord
from .validation import require_int, require_positive_finite, require_sha256


class ValidationCase(str, Enum):
    T0 = "T0"
    T1 = "T1"
    T2 = "T2"
    T3 = "T3"
    T4 = "T4"


class ValidationStatus(str, Enum):
    PASSED = "PASSED"
    REVIEW = "REVIEW"


class ValidationReason(str, Enum):
    EVIDENCE_INCOMPLETE = "EVIDENCE_INCOMPLETE"
    COVERAGE_TARGET_NOT_MET = "COVERAGE_TARGET_NOT_MET"
    FALSE_PASS = "FALSE_PASS"
    RECIPROCITY_VIOLATION = "RECIPROCITY_VIOLATION"
    ORDER_OR_GRID_DEPENDENT = "ORDER_OR_GRID_DEPENDENT"
    HOLDOUT_NOT_ESTABLISHED = "HOLDOUT_NOT_ESTABLISHED"
    PROTOCOL_NOT_FROZEN = "PROTOCOL_NOT_FROZEN"


@dataclass(frozen=True)
class ValidationProtocol(_ScfRecord):
    version: str
    coverage_target: float
    frozen_scientific_protocol_sha256: str
    t4_required: bool

    def __post_init__(self) -> None:
        super().__post_init__()
        try:
            require_positive_finite(self.coverage_target, "coverage_target")
            require_sha256(self.frozen_scientific_protocol_sha256, "frozen_scientific_protocol_sha256")
            if self.coverage_target > 1:
                raise ScfLadderError("coverage_target must not exceed one")
        except ValueError as exc:
            raise ScfLadderError(str(exc)) from exc


@dataclass(frozen=True)
class ValidationMetrics(_ScfRecord):
    case: ValidationCase
    sample_count: int
    covered_count: int
    false_pass_count: int
    reciprocity_violation_count: int
    order_invariant: bool
    grid_shift_invariant: bool
    holdout: bool
    blind_review_agrees: bool
    scientific_protocol_sha256: str
    evidence_sha256: tuple[str, ...]

    def __post_init__(self) -> None:
        super().__post_init__()
        try:
            for name in ("sample_count", "covered_count", "false_pass_count", "reciprocity_violation_count"):
                require_int(getattr(self, name), name, minimum=0)
            if (
                max(self.covered_count, self.false_pass_count, self.reciprocity_violation_count)
                > self.sample_count
            ):
                raise ScfLadderError("counts must not exceed sample_count")
            require_sha256(self.scientific_protocol_sha256, "scientific_protocol_sha256")
            for digest in self.evidence_sha256:
                require_sha256(digest, "evidence_sha256")
            if len(set(self.evidence_sha256)) != len(self.evidence_sha256):
                raise ScfLadderError("evidence digests must be distinct")
            object.__setattr__(self, "evidence_sha256", tuple(sorted(self.evidence_sha256)))
        except ValueError as exc:
            raise ScfLadderError(str(exc)) from exc


@dataclass(frozen=True)
class ValidationResult(_ScfRecord):
    protocol: ValidationProtocol
    metrics: tuple[ValidationMetrics, ...]
    status: ValidationStatus
    reasons: tuple[ValidationReason, ...]

    @property
    def digest(self) -> str:
        return hashlib.sha256(
            json.dumps(self.to_mapping(), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        ).hexdigest()


def validate_t0_t4(protocol: ValidationProtocol, metrics: tuple[ValidationMetrics, ...]) -> ValidationResult:
    """Apply §K preregistered coverage and zero false PASS requirements.

    T4 is explicitly optional in the scientific review. T2 requires separate
    development and blind holdout records bound to the frozen protocol.
    """
    reasons = []
    required = {ValidationCase.T0, ValidationCase.T1, ValidationCase.T2, ValidationCase.T3}
    if protocol.t4_required:
        required.add(ValidationCase.T4)
    if not required <= {m.case for m in metrics} or any(
        not m.sample_count or not m.evidence_sha256 for m in metrics
    ):
        reasons.append(ValidationReason.EVIDENCE_INCOMPLETE)
    for m in metrics:
        if m.scientific_protocol_sha256 != protocol.frozen_scientific_protocol_sha256:
            reasons.append(ValidationReason.PROTOCOL_NOT_FROZEN)
        if m.case in (ValidationCase.T0, ValidationCase.T1, ValidationCase.T2) and (
            not m.sample_count or m.covered_count / m.sample_count < protocol.coverage_target
        ):
            reasons.append(ValidationReason.COVERAGE_TARGET_NOT_MET)
        if m.case is ValidationCase.T3 and m.false_pass_count:
            reasons.append(ValidationReason.FALSE_PASS)
        if m.reciprocity_violation_count:
            reasons.append(ValidationReason.RECIPROCITY_VIOLATION)
        if not m.order_invariant or not m.grid_shift_invariant:
            reasons.append(ValidationReason.ORDER_OR_GRID_DEPENDENT)
    t2 = [m for m in metrics if m.case is ValidationCase.T2]
    if not any(m.holdout and m.blind_review_agrees for m in t2) or not any(not m.holdout for m in t2):
        reasons.append(ValidationReason.HOLDOUT_NOT_ESTABLISHED)
    return ValidationResult(
        protocol,
        tuple(sorted(metrics, key=lambda m: (m.case.value, m.holdout, m.evidence_sha256))),
        ValidationStatus.REVIEW if reasons else ValidationStatus.PASSED,
        tuple(sorted(set(reasons), key=lambda r: r.value)),
    )
