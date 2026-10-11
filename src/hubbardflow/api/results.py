"""Immutable native API envelopes preserving status vocabulary and payload."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum

from hubbardflow.domain.validation import require_sha256

from .serialization import PublicApiError, json_bytes, mapping, object_fields, string

API_VERSION = "1.0.0"


class ApiOperation(str, Enum):
    DESCRIBE_CAPABILITIES = "describe_capabilities"
    RESOLVE_PLAN = "resolve_plan"
    VALIDATE_OBSERVATION = "validate_observation"
    EVALUATE_GATE = "evaluate_gate"
    ANALYZE = "analyze"
    CHECK_RESUME = "check_resume"
    WORKER_STATUS = "worker_status"


class NumericalStatus(str, Enum):
    NUMERICAL_CANDIDATE = "NUMERICAL_CANDIDATE"
    NUMERICAL_CANDIDATE_SENSITIVE = "NUMERICAL_CANDIDATE_SENSITIVE"
    NUMERICAL_CANDIDATE_UNASSESSED = "NUMERICAL_CANDIDATE_UNASSESSED"
    NO_NUMERICAL_U = "NO_NUMERICAL_U"
    NO_SINGLE_STATE_U = "NO_SINGLE_STATE_U"
    NOT_ESTABLISHED = "NOT_ESTABLISHED"


class SafeAssessment(str, Enum):
    """Transport assessment never certifies physical validity of Hubbard U."""

    NOT_ESTABLISHED = "NOT_ESTABLISHED"
    FAIL = "FAIL"


@dataclass(frozen=True)
class ApiResult:
    """Deeply immutable JSON receipt; each to_mapping returns a fresh copy.

    native_status is a transported, open vocabulary, not an admission decision.
    New/unknown values survive round trips and never gain a PASS projection.
    The original payload, including inverse-certification tokens, is unchanged.
    """

    operation: ApiOperation
    native_status: str
    payload_json: str
    native_digest: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.operation, ApiOperation):
            raise PublicApiError("operation must be ApiOperation")
        string(self.native_status, "native_status")
        payload = mapping(json.loads(self.payload_json))
        object.__setattr__(self, "payload_json", json_bytes(payload).decode())
        if self.native_digest is not None:
            require_sha256(self.native_digest, "native_digest")

    @property
    def assessment(self) -> SafeAssessment:
        if self.native_status in {"FAIL", "IDENTITY_MISMATCH"}:
            return SafeAssessment.FAIL
        return SafeAssessment.NOT_ESTABLISHED

    def to_mapping(self) -> dict[str, object]:
        return {
            "schema": "hubbardflow.api_result.v1",
            "api_version": API_VERSION,
            "operation": self.operation.value,
            "native_status": self.native_status,
            "assessment": self.assessment.value,
            "native_digest": self.native_digest,
            "payload": json.loads(self.payload_json),
        }

    @classmethod
    def from_mapping(cls, value: object) -> ApiResult:
        row = object_fields(
            value,
            {"schema", "api_version", "operation", "native_status", "assessment", "native_digest", "payload"},
        )
        if row["schema"] != "hubbardflow.api_result.v1" or row["api_version"] != API_VERSION:
            raise PublicApiError("unsupported API result schema/version")
        result = cls(
            ApiOperation(string(row["operation"], "operation")),
            string(row["native_status"], "native_status"),
            json_bytes(mapping(row["payload"])).decode(),
            None if row["native_digest"] is None else string(row["native_digest"], "native_digest"),
        )
        if result.assessment.value != row["assessment"]:
            raise PublicApiError("assessment contradicts the conservative native projection")
        return result


def result(operation: ApiOperation, status: str, payload: object, digest: str | None = None) -> ApiResult:
    return ApiResult(operation, status, json_bytes(mapping(payload)).decode(), digest)
