"""Serializable result records for the pure I.5 state consistency gate."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum


class StateGateError(ValueError):
    """Invalid I.5 result record."""


class StateGateMode(str, Enum):
    BARE = "BARE"
    SCREENED = "SCREENED"


class StateGateVerdict(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_ESTABLISHED = "NOT_ESTABLISHED"


class StateCheck(str, Enum):
    G1 = "G1"
    G2 = "G2"
    G3A = "G3a"
    G3 = "G3"
    G4 = "G4"


class CheckOutcome(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_DEFINED = "NOT_DEFINED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NOT_AVAILABLE = "NOT_AVAILABLE"
    NOT_ESTABLISHED = "NOT_ESTABLISHED"


class StateGateReason(str, Enum):
    NODE_NOT_VALIDATED = "NODE_NOT_VALIDATED"
    OCCUPATION_COUNT_CHANGED = "OCCUPATION_COUNT_CHANGED"
    SUBSPACE_AMBIGUOUS = "SUBSPACE_AMBIGUOUS"
    ORBITAL_ORDER_CHANGED = "ORBITAL_ORDER_CHANGED"
    MOMENT_SIGN_CHANGED = "MOMENT_SIGN_CHANGED"
    BAND_COUNT_CHANGED = "BAND_COUNT_CHANGED"
    BAND_COUNT_AMBIGUOUS = "BAND_COUNT_AMBIGUOUS"
    EIG_STDOUT_FERMI_MISMATCH = "EIG_STDOUT_FERMI_MISMATCH"
    SMOOTHNESS_REQUIRES_SCF_LADDER = "SMOOTHNESS_REQUIRES_SCF_LADDER"
    MISSING_REQUIRED_EVIDENCE = "MISSING_REQUIRED_EVIDENCE"
    INVALID_STATE_EVIDENCE = "INVALID_STATE_EVIDENCE"


DetailValue = str | bool | int | float


@dataclass(frozen=True)
class StateCheckResult:
    check: StateCheck
    outcome: CheckOutcome
    reasons: tuple[StateGateReason, ...] = ()
    atom_index: int | None = None
    spin: int | None = None
    details: tuple[tuple[str, DetailValue], ...] = ()

    def __post_init__(self) -> None:
        if self.atom_index is not None and self.atom_index < 1:
            raise StateGateError("atom_index must be positive")
        if self.spin is not None and self.spin < 1:
            raise StateGateError("spin must be positive")
        if self.reasons != tuple(sorted(set(self.reasons), key=lambda item: item.value)):
            raise StateGateError("check reasons must be unique and sorted")
        if self.details != tuple(sorted(self.details, key=lambda item: item[0])):
            raise StateGateError("check details must be sorted by key")
        if len({key for key, _ in self.details}) != len(self.details):
            raise StateGateError("check detail keys must be unique")
        for key, value in self.details:
            if not key or (isinstance(value, float) and not math.isfinite(value)):
                raise StateGateError("check detail keys must be non-empty and floats finite")

    def to_mapping(self) -> dict[str, object]:
        return {
            "check": self.check.value,
            "outcome": self.outcome.value,
            "reasons": [reason.value for reason in self.reasons],
            "atom_index": self.atom_index,
            "spin": self.spin,
            "details": {key: value for key, value in self.details},
        }

    @classmethod
    def from_mapping(cls, value: object) -> StateCheckResult:
        if not isinstance(value, dict):
            raise StateGateError("state check result must be an object")
        try:
            reasons = value["reasons"]
            details = value["details"]
            if not isinstance(reasons, list) or not isinstance(details, dict):
                raise TypeError("reasons must be an array and details an object")
            return cls(
                check=StateCheck(value["check"]),
                outcome=CheckOutcome(value["outcome"]),
                reasons=tuple(
                    sorted({StateGateReason(item) for item in reasons}, key=lambda item: item.value)
                ),
                atom_index=None if value["atom_index"] is None else int(value["atom_index"]),
                spin=None if value["spin"] is None else int(value["spin"]),
                details=tuple(sorted(details.items())),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise StateGateError(f"invalid state check result: {exc}") from exc


@dataclass(frozen=True)
class StatePointResult:
    alpha_ev: float
    checks: tuple[StateCheckResult, ...]

    def __post_init__(self) -> None:
        if not math.isfinite(self.alpha_ev) or self.alpha_ev == 0:
            raise StateGateError("state point alpha_ev must be finite and non-zero")

    def to_mapping(self) -> dict[str, object]:
        return {"alpha_ev": self.alpha_ev, "checks": [item.to_mapping() for item in self.checks]}

    @classmethod
    def from_mapping(cls, value: object) -> StatePointResult:
        if not isinstance(value, dict) or not isinstance(value.get("checks"), list):
            raise StateGateError("state point result must contain a checks array")
        try:
            return cls(
                alpha_ev=float(value["alpha_ev"]),
                checks=tuple(StateCheckResult.from_mapping(item) for item in value["checks"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise StateGateError(f"invalid state point result: {exc}") from exc


@dataclass(frozen=True)
class AmplitudeGateResult:
    amplitude_ev: float
    positive: StatePointResult | None
    negative: StatePointResult | None
    admissible: bool
    excluded_by_monotone_rule: bool
    reasons: tuple[StateGateReason, ...] = ()

    def __post_init__(self) -> None:
        if not math.isfinite(self.amplitude_ev) or self.amplitude_ev <= 0:
            raise StateGateError("amplitude_ev must be positive and finite")
        if self.reasons != tuple(sorted(set(self.reasons), key=lambda item: item.value)):
            raise StateGateError("amplitude reasons must be unique and sorted")

    def to_mapping(self) -> dict[str, object]:
        return {
            "amplitude_ev": self.amplitude_ev,
            "positive": None if self.positive is None else self.positive.to_mapping(),
            "negative": None if self.negative is None else self.negative.to_mapping(),
            "admissible": self.admissible,
            "excluded_by_monotone_rule": self.excluded_by_monotone_rule,
            "reasons": [reason.value for reason in self.reasons],
        }

    @classmethod
    def from_mapping(cls, value: object) -> AmplitudeGateResult:
        if not isinstance(value, dict) or not isinstance(value.get("reasons"), list):
            raise StateGateError("amplitude gate result must be an object")
        try:
            return cls(
                amplitude_ev=float(value["amplitude_ev"]),
                positive=None
                if value["positive"] is None
                else StatePointResult.from_mapping(value["positive"]),
                negative=None
                if value["negative"] is None
                else StatePointResult.from_mapping(value["negative"]),
                admissible=bool(value["admissible"]),
                excluded_by_monotone_rule=bool(value["excluded_by_monotone_rule"]),
                reasons=tuple(
                    sorted({StateGateReason(item) for item in value["reasons"]}, key=lambda item: item.value)
                ),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise StateGateError(f"invalid amplitude gate result: {exc}") from exc


@dataclass(frozen=True)
class StateGateResult:
    policy_id: str
    column_id: str
    mode: StateGateMode
    verdict: StateGateVerdict
    amplitudes: tuple[AmplitudeGateResult, ...]
    admissible_amplitudes_ev: tuple[float, ...]
    excluded_amplitudes_ev: tuple[float, ...]
    reasons: tuple[StateGateReason, ...]
    smoothness: StateCheckResult

    def __post_init__(self) -> None:
        if not self.policy_id or not self.column_id:
            raise StateGateError("policy_id and column_id must be non-empty")
        if self.smoothness.check is not StateCheck.G3:
            raise StateGateError("smoothness result must describe G3")
        if self.reasons != tuple(sorted(set(self.reasons), key=lambda item: item.value)):
            raise StateGateError("state gate reasons must be unique and sorted")
        if self.admissible_amplitudes_ev != tuple(sorted(set(self.admissible_amplitudes_ev))):
            raise StateGateError("admissible amplitudes must be unique and sorted")
        if self.excluded_amplitudes_ev != tuple(sorted(set(self.excluded_amplitudes_ev))):
            raise StateGateError("excluded amplitudes must be unique and sorted")

    def to_mapping(self) -> dict[str, object]:
        return {
            "policy_id": self.policy_id,
            "column_id": self.column_id,
            "mode": self.mode.value,
            "verdict": self.verdict.value,
            "amplitudes": [item.to_mapping() for item in self.amplitudes],
            "admissible_amplitudes_ev": list(self.admissible_amplitudes_ev),
            "excluded_amplitudes_ev": list(self.excluded_amplitudes_ev),
            "reasons": [reason.value for reason in self.reasons],
            "smoothness": self.smoothness.to_mapping(),
        }

    @classmethod
    def from_mapping(cls, value: object) -> StateGateResult:
        if not isinstance(value, dict):
            raise StateGateError("state gate result must be an object")
        try:
            arrays = (
                value["amplitudes"],
                value["admissible_amplitudes_ev"],
                value["excluded_amplitudes_ev"],
                value["reasons"],
            )
            if not all(isinstance(item, list) for item in arrays):
                raise TypeError("amplitude and reason fields must be arrays")
            return cls(
                policy_id=str(value["policy_id"]),
                column_id=str(value["column_id"]),
                mode=StateGateMode(value["mode"]),
                verdict=StateGateVerdict(value["verdict"]),
                amplitudes=tuple(AmplitudeGateResult.from_mapping(item) for item in value["amplitudes"]),
                admissible_amplitudes_ev=tuple(float(item) for item in value["admissible_amplitudes_ev"]),
                excluded_amplitudes_ev=tuple(float(item) for item in value["excluded_amplitudes_ev"]),
                reasons=tuple(
                    sorted({StateGateReason(item) for item in value["reasons"]}, key=lambda item: item.value)
                ),
                smoothness=StateCheckResult.from_mapping(value["smoothness"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise StateGateError(f"invalid state gate result: {exc}") from exc
