"""Observation and I.5 gate transport, without duplicating domain decisions."""

from __future__ import annotations

from hubbardflow.domain.observation_provenance import Observation, RunIdentity
from hubbardflow.domain.observation_provenance import validate_observation as native_validate
from hubbardflow.domain.state_gate_eval import qualify_state_gate
from hubbardflow.domain.state_gate_types import PointState, StateGatePoint

from .results import ApiOperation, ApiResult, result
from .serialization import ScientificEvidenceError, array, decode_record, object_fields, string


def validate_observation(request: object) -> ApiResult:
    """Admit explicit semantic evidence, not merely matching artifact hashes."""
    row = object_fields(request, {"observation", "expected"})
    observation = decode_record(Observation, row["observation"])
    expected = decode_record(RunIdentity, row["expected"])
    try:
        digest = native_validate(observation, expected)
        return result(ApiOperation.VALIDATE_OBSERVATION, "VALIDATED", {"observation_hash": digest}, digest)
    except ValueError as exc:
        raise ScientificEvidenceError(f"observation rejected: {exc}") from exc


def evaluate_gate(request: object) -> ApiResult:
    """Evaluate the existing state-continuity policy for supplied printed evidence."""
    row = object_fields(request, {"reference", "column_id", "mode", "points"})
    reference = decode_record(PointState, row["reference"])
    points = tuple(decode_record(StateGatePoint, item) for item in array(row["points"], "points"))
    try:
        gate = qualify_state_gate(
            reference, string(row["column_id"], "column_id"), string(row["mode"], "mode"), points
        )
        return result(ApiOperation.EVALUATE_GATE, gate.verdict.value, gate.to_mapping())
    except ValueError as exc:
        raise ScientificEvidenceError(f"gate evidence rejected: {exc}") from exc
