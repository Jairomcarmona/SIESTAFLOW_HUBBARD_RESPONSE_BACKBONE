"""Typed specification for projector scans and plateau assessment.

This module describes a one-column diagnostic and its declared assessment
inputs. It deliberately does not schedule calculations or decide a plateau
from raw response data; those belong to a later execution engine.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum


class ProjectorPlateauError(ValueError):
    """Invalid projector scan specification or evidence."""


class ProjectorScanStage(str, Enum):
    COARSE_SCAN = "COARSE_SCAN"
    REFINEMENT = "REFINEMENT"
    EVALUATION = "EVALUATION"
    PLATEAU_DETECTION = "PLATEAU_DETECTION"
    LOCK = "LOCK"
    FULL_RESPONSE = "FULL_RESPONSE"


class ProjectorParameterKind(str, Enum):
    CUTOFF_NORM = "CUTOFF_NORM"
    EXPLICIT_RC = "EXPLICIT_RC"


class ProjectorAssessment(str, Enum):
    PROJECTOR_PLATEAU_CONFIRMED = "PROJECTOR_PLATEAU_CONFIRMED"
    PROJECTOR_NOT_ASSESSED = "PROJECTOR_NOT_ASSESSED"
    PROJECTOR_NO_PLATEAU = "PROJECTOR_NO_PLATEAU"


class PlateauGateState(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_ASSESSED = "NOT_ASSESSED"


class PlateauRequirement(str, Enum):
    RESULT_STABILITY = "RESULT_STABILITY"
    RESPONSE_LINEARITY = "RESPONSE_LINEARITY"
    ELECTRONIC_STATE_CONTINUITY = "ELECTRONIC_STATE_CONTINUITY"
    MAGNETIC_STABILITY = "MAGNETIC_STABILITY"
    MATRIX_CONDITIONING = "MATRIX_CONDITIONING"
    LOCAL_SENSITIVITY_STABILITY = "LOCAL_SENSITIVITY_STABILITY"
    NO_BLOCKING_GATE_FAILED = "NO_BLOCKING_GATE_FAILED"


REQUIRED_PLATEAU_REQUIREMENTS = tuple(PlateauRequirement)


PROJECTOR_SCAN_STAGES = (
    ProjectorScanStage.COARSE_SCAN,
    ProjectorScanStage.REFINEMENT,
    ProjectorScanStage.EVALUATION,
    ProjectorScanStage.PLATEAU_DETECTION,
    ProjectorScanStage.LOCK,
    ProjectorScanStage.FULL_RESPONSE,
)


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ProjectorPlateauError(f"{label} must be a non-empty string without surrounding whitespace")
    return value


def _mapping_number(value: object, label: str) -> int | float:
    """Accept JSON numeric values without coercing strings or booleans."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProjectorPlateauError(f"{label} must be a number")
    return value


def _mapping_integer(value: object, label: str) -> int:
    """Accept only an actual integer; in particular, reject bool and 2.0."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ProjectorPlateauError(f"{label} must be an integer")
    return value


def _mapping_boolean(value: object, label: str) -> bool:
    if not isinstance(value, bool):
        raise ProjectorPlateauError(f"{label} must be a boolean")
    return value


def _mapping_string(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise ProjectorPlateauError(f"{label} must be a string")
    return value


def _positive_finite(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProjectorPlateauError(f"{label} must be a positive finite number")
    normalized = float(value)
    if not math.isfinite(normalized) or normalized <= 0.0:
        raise ProjectorPlateauError(f"{label} must be a positive finite number")
    return normalized


def _nonnegative_finite(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProjectorPlateauError(f"{label} must be a non-negative finite number")
    normalized = float(value)
    if not math.isfinite(normalized) or normalized < 0.0:
        raise ProjectorPlateauError(f"{label} must be a non-negative finite number")
    return normalized


def _finite(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProjectorPlateauError(f"{label} must be finite")
    normalized = float(value)
    if not math.isfinite(normalized):
        raise ProjectorPlateauError(f"{label} must be finite")
    return normalized


@dataclass(frozen=True)
class ProjectorValue:
    """A U result is tied to the exact projector parameter that produced it."""

    kind: ProjectorParameterKind
    value: float
    method: int = 2

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ProjectorParameterKind):
            raise ProjectorPlateauError("kind must be a ProjectorParameterKind")
        object.__setattr__(self, "value", _positive_finite(self.value, "projector value"))
        if isinstance(self.method, bool) or not isinstance(self.method, int) or self.method != 2:
            raise ProjectorPlateauError("projector scans require ProjectorGenerationMethod 2")

    def to_mapping(self) -> dict[str, object]:
        return {"kind": self.kind.value, "value": self.value, "method": self.method}

    @classmethod
    def from_mapping(cls, value: object) -> ProjectorValue:
        if not isinstance(value, dict):
            raise ProjectorPlateauError("projector value must be an object")
        try:
            return cls(
                ProjectorParameterKind(value["kind"]),
                _mapping_number(value["value"], "projector value"),
                _mapping_integer(value["method"], "method"),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ProjectorPlateauError(f"invalid projector value: {exc}") from exc


@dataclass(frozen=True)
class ProjectorProbePoint:
    """One projector candidate used by its one-column probe."""

    projector: ProjectorValue

    def __post_init__(self) -> None:
        if not isinstance(self.projector, ProjectorValue):
            raise ProjectorPlateauError("projector must be a ProjectorValue")

    def to_mapping(self) -> dict[str, object]:
        return {"projector": self.projector.to_mapping()}

    @classmethod
    def from_mapping(cls, value: object) -> ProjectorProbePoint:
        if not isinstance(value, dict):
            raise ProjectorPlateauError("probe point must be an object")
        try:
            return cls(ProjectorValue.from_mapping(value["projector"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise ProjectorPlateauError(f"invalid probe point: {exc}") from exc


@dataclass(frozen=True)
class ProjectorUResult:
    """A calculated U stays attached to its exact projector identity."""

    projector: ProjectorValue
    u_ev: float

    def __post_init__(self) -> None:
        if not isinstance(self.projector, ProjectorValue):
            raise ProjectorPlateauError("projector must be a ProjectorValue")
        object.__setattr__(self, "u_ev", _finite(self.u_ev, "u_ev"))

    def to_mapping(self) -> dict[str, object]:
        return {"projector": self.projector.to_mapping(), "u_ev": self.u_ev}

    @classmethod
    def from_mapping(cls, value: object) -> ProjectorUResult:
        if not isinstance(value, dict):
            raise ProjectorPlateauError("projector U result must be an object")
        try:
            return cls(
                ProjectorValue.from_mapping(value["projector"]),
                _mapping_number(value["u_ev"], "u_ev"),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ProjectorPlateauError(f"invalid projector U result: {exc}") from exc


@dataclass(frozen=True)
class PlateauCriteria:
    """User-declared thresholds; absent criteria intentionally mean unassessed."""

    maximum_u_variation_ev: float | None = None
    minimum_points: int | None = None
    refinement_step: float | None = None

    def __post_init__(self) -> None:
        if self.maximum_u_variation_ev is not None:
            object.__setattr__(
                self,
                "maximum_u_variation_ev",
                _nonnegative_finite(self.maximum_u_variation_ev, "maximum_u_variation_ev"),
            )
        if self.refinement_step is not None:
            object.__setattr__(
                self, "refinement_step", _positive_finite(self.refinement_step, "refinement_step")
            )
        if self.minimum_points is not None and (
            isinstance(self.minimum_points, bool)
            or not isinstance(self.minimum_points, int)
            or self.minimum_points < 1
        ):
            raise ProjectorPlateauError("minimum_points must be a positive integer")

    @property
    def complete(self) -> bool:
        return (
            self.maximum_u_variation_ev is not None
            and self.minimum_points is not None
            and self.refinement_step is not None
        )

    def to_mapping(self) -> dict[str, object]:
        return {
            "maximum_u_variation_ev": self.maximum_u_variation_ev,
            "minimum_points": self.minimum_points,
            "refinement_step": self.refinement_step,
        }

    @classmethod
    def from_mapping(cls, value: object) -> PlateauCriteria:
        if not isinstance(value, dict):
            raise ProjectorPlateauError("plateau criteria must be an object")
        try:
            max_variation = value["maximum_u_variation_ev"]
            minimum_points = value["minimum_points"]
            refinement_step = value["refinement_step"]
            return cls(
                None if max_variation is None else _mapping_number(max_variation, "maximum_u_variation_ev"),
                None if minimum_points is None else _mapping_integer(minimum_points, "minimum_points"),
                None if refinement_step is None else _mapping_number(refinement_step, "refinement_step"),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ProjectorPlateauError(f"invalid plateau criteria: {exc}") from exc


@dataclass(frozen=True)
class PlateauGateEvidence:
    """Externally evaluated outcome for one required plateau criterion."""

    requirement: PlateauRequirement
    state: PlateauGateState

    def __post_init__(self) -> None:
        if not isinstance(self.requirement, PlateauRequirement):
            raise ProjectorPlateauError("requirement must be a PlateauRequirement")
        if not isinstance(self.state, PlateauGateState):
            raise ProjectorPlateauError("state must be a PlateauGateState")

    def to_mapping(self) -> dict[str, str]:
        return {"requirement": self.requirement.value, "state": self.state.value}

    @classmethod
    def from_mapping(cls, value: object) -> PlateauGateEvidence:
        if not isinstance(value, dict):
            raise ProjectorPlateauError("plateau gate evidence must be an object")
        try:
            return cls(PlateauRequirement(value["requirement"]), PlateauGateState(value["state"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise ProjectorPlateauError(f"invalid plateau gate evidence: {exc}") from exc


@dataclass(frozen=True)
class ProjectorScanSpec:
    """One-site, one-column scan contract. No execution plan is produced here."""

    representative_site_id: str
    kind: ProjectorParameterKind
    production_projector: ProjectorValue
    points: tuple[ProjectorProbePoint, ...]
    criteria: PlateauCriteria

    def __post_init__(self) -> None:
        _identifier(self.representative_site_id, "representative_site_id")
        if not isinstance(self.kind, ProjectorParameterKind):
            raise ProjectorPlateauError("kind must be a ProjectorParameterKind")
        if (
            not isinstance(self.production_projector, ProjectorValue)
            or self.production_projector.kind is not self.kind
        ):
            raise ProjectorPlateauError("production_projector must use the scan parameter kind")
        if not isinstance(self.criteria, PlateauCriteria):
            raise ProjectorPlateauError("criteria must be PlateauCriteria")
        if not isinstance(self.points, tuple) or len(self.points) < 2:
            raise ProjectorPlateauError("points must contain at least two projector candidates")
        values = tuple(point.projector.value for point in self.points)
        if len(set(values)) != len(values):
            raise ProjectorPlateauError("projector candidate values must be distinct")
        production_points = tuple(
            point for point in self.points if point.projector == self.production_projector
        )
        if len(production_points) != 1:
            raise ProjectorPlateauError(
                "the production projector must occur exactly once in the scan candidates"
            )
        for point in self.points:
            if point.projector.kind is not self.kind:
                raise ProjectorPlateauError("all candidates must use the scan parameter kind")

    @property
    def responses_per_probe(self) -> int:
        """Twelve signed perturbation response runs, plus one reference run."""
        return 12

    @property
    def total_runs_per_probe(self) -> int:
        return self.responses_per_probe + 1

    def validate_production_control(self, control: ProductionControl) -> None:
        """Require the internal control to use this scan's production projector."""
        if not isinstance(control, ProductionControl) or control.projector != self.production_projector:
            raise ProjectorPlateauError("production control must use the declared production projector")

    def to_mapping(self) -> dict[str, object]:
        return {
            "representative_site_id": self.representative_site_id,
            "kind": self.kind.value,
            "production_projector": self.production_projector.to_mapping(),
            "points": [point.to_mapping() for point in self.points],
            "criteria": self.criteria.to_mapping(),
            "responses_per_probe": self.responses_per_probe,
            "total_runs_per_probe": self.total_runs_per_probe,
        }

    @classmethod
    def from_mapping(cls, value: object) -> ProjectorScanSpec:
        if not isinstance(value, dict) or not isinstance(value.get("points"), list):
            raise ProjectorPlateauError("projector scan must contain a points array")
        try:
            result = cls(
                representative_site_id=_mapping_string(
                    value["representative_site_id"], "representative_site_id"
                ),
                kind=ProjectorParameterKind(value["kind"]),
                production_projector=ProjectorValue.from_mapping(value["production_projector"]),
                points=tuple(ProjectorProbePoint.from_mapping(item) for item in value["points"]),
                criteria=PlateauCriteria.from_mapping(value["criteria"]),
            )
            if value.get("responses_per_probe") != result.responses_per_probe:
                raise ProjectorPlateauError("responses_per_probe must be 12")
            if value.get("total_runs_per_probe") != result.total_runs_per_probe:
                raise ProjectorPlateauError("total_runs_per_probe must be 13")
            return result
        except (KeyError, TypeError, ValueError) as exc:
            raise ProjectorPlateauError(f"invalid projector scan: {exc}") from exc


@dataclass(frozen=True)
class ProjectorAssessmentResult:
    """Assessment status plus whether a projector candidate may advance to lock."""

    status: ProjectorAssessment
    candidate_eligible_for_lock: bool
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.status, ProjectorAssessment):
            raise ProjectorPlateauError("status must be a ProjectorAssessment")
        if self.candidate_eligible_for_lock != (
            self.status is ProjectorAssessment.PROJECTOR_PLATEAU_CONFIRMED
        ):
            raise ProjectorPlateauError("a candidate may advance to lock only when a plateau is confirmed")
        _identifier(self.reason, "reason")

    def to_mapping(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "candidate_eligible_for_lock": self.candidate_eligible_for_lock,
            "reason": self.reason,
        }

    @classmethod
    def from_mapping(cls, value: object) -> ProjectorAssessmentResult:
        if not isinstance(value, dict):
            raise ProjectorPlateauError("assessment result must be an object")
        try:
            return cls(
                ProjectorAssessment(value["status"]),
                _mapping_boolean(value["candidate_eligible_for_lock"], "candidate_eligible_for_lock"),
                _mapping_string(value["reason"], "reason"),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ProjectorPlateauError(f"invalid assessment result: {exc}") from exc


def projector_assessment(
    criteria: PlateauCriteria, required_gates: tuple[PlateauGateEvidence, ...]
) -> ProjectorAssessmentResult:
    """Map declared criteria and externally evaluated gates to a status only.

    Numeric threshold evaluation remains outside this specification skeleton.
    Missing criteria or unevaluated gates cannot confirm a plateau.
    """
    if not isinstance(criteria, PlateauCriteria):
        raise ProjectorPlateauError("criteria must be PlateauCriteria")
    if not isinstance(required_gates, tuple) or any(
        not isinstance(item, PlateauGateEvidence) for item in required_gates
    ):
        raise ProjectorPlateauError("required_gates must be a tuple of PlateauGateEvidence values")
    requirements = tuple(item.requirement for item in required_gates)
    if (
        not criteria.complete
        or set(requirements) != set(REQUIRED_PLATEAU_REQUIREMENTS)
        or len(requirements) != len(REQUIRED_PLATEAU_REQUIREMENTS)
        or any(item.state is PlateauGateState.NOT_ASSESSED for item in required_gates)
    ):
        return ProjectorAssessmentResult(
            ProjectorAssessment.PROJECTOR_NOT_ASSESSED,
            False,
            "criteria or required plateau-gate evidence is incomplete",
        )
    if any(item.state is PlateauGateState.FAIL for item in required_gates):
        return ProjectorAssessmentResult(
            ProjectorAssessment.PROJECTOR_NO_PLATEAU,
            False,
            "at least one required plateau gate failed",
        )
    return ProjectorAssessmentResult(
        ProjectorAssessment.PROJECTOR_PLATEAU_CONFIRMED,
        True,
        "all declared criteria and required gates were evaluated externally",
    )


@dataclass(frozen=True)
class ProductionControl:
    """Internal control comparing scan U at the production projector to full-run U."""

    projector: ProjectorValue
    scan_u_ev: float
    full_campaign_u_ev: float

    def __post_init__(self) -> None:
        if not isinstance(self.projector, ProjectorValue):
            raise ProjectorPlateauError("projector must be a ProjectorValue")
        object.__setattr__(self, "scan_u_ev", _finite(self.scan_u_ev, "scan_u_ev"))
        object.__setattr__(self, "full_campaign_u_ev", _finite(self.full_campaign_u_ev, "full_campaign_u_ev"))

    @property
    def delta_u_ev(self) -> float:
        """Absolute difference; this control is reported, not a hidden acceptance gate."""
        return abs(self.scan_u_ev - self.full_campaign_u_ev)

    def to_mapping(self) -> dict[str, object]:
        return {
            "projector": self.projector.to_mapping(),
            "scan_u_ev": self.scan_u_ev,
            "full_campaign_u_ev": self.full_campaign_u_ev,
            "delta_u_ev": self.delta_u_ev,
        }

    @classmethod
    def from_mapping(cls, value: object) -> ProductionControl:
        if not isinstance(value, dict):
            raise ProjectorPlateauError("production control must be an object")
        try:
            result = cls(
                ProjectorValue.from_mapping(value["projector"]),
                _mapping_number(value["scan_u_ev"], "scan_u_ev"),
                _mapping_number(value["full_campaign_u_ev"], "full_campaign_u_ev"),
            )
            if _mapping_number(value["delta_u_ev"], "delta_u_ev") != result.delta_u_ev:
                raise ProjectorPlateauError("delta_u_ev must equal the absolute U difference")
            return result
        except (KeyError, TypeError, ValueError) as exc:
            raise ProjectorPlateauError(f"invalid production control: {exc}") from exc
