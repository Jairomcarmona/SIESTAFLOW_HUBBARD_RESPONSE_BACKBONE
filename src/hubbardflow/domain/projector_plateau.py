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
    PROJECTOR_DECLARED_AND_CHARACTERIZED = "PROJECTOR_DECLARED_AND_CHARACTERIZED"
    PROJECTOR_NOT_ASSESSED = "PROJECTOR_NOT_ASSESSED"


class PlateauOutcome(str, Enum):
    """Optional evidence about a plateau, independent of U usability."""

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

    def is_for_declared_projector(self, declared_projector: ProjectorValue) -> bool:
        """U is usable only for the exact projector that the user declared."""
        if not isinstance(declared_projector, ProjectorValue):
            raise ProjectorPlateauError("declared_projector must be a ProjectorValue")
        return self.projector == declared_projector

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
class ProjectorCurveSegment:
    """Observed secant slope between adjacent projector-specific U values."""

    lower_projector: ProjectorValue
    upper_projector: ProjectorValue
    slope_ev_per_parameter: float

    def __post_init__(self) -> None:
        if not isinstance(self.lower_projector, ProjectorValue) or not isinstance(
            self.upper_projector, ProjectorValue
        ):
            raise ProjectorPlateauError("curve segment projectors must be ProjectorValue values")
        if self.lower_projector.kind is not self.upper_projector.kind:
            raise ProjectorPlateauError("curve segment projectors must use the same parameter kind")
        if self.upper_projector.value <= self.lower_projector.value:
            raise ProjectorPlateauError("curve segment projector values must be increasing")
        object.__setattr__(
            self,
            "slope_ev_per_parameter",
            _finite(self.slope_ev_per_parameter, "slope_ev_per_parameter"),
        )

    def to_mapping(self) -> dict[str, object]:
        return {
            "lower_projector": self.lower_projector.to_mapping(),
            "upper_projector": self.upper_projector.to_mapping(),
            "slope_ev_per_parameter": self.slope_ev_per_parameter,
        }

    @classmethod
    def from_mapping(cls, value: object) -> ProjectorCurveSegment:
        if not isinstance(value, dict):
            raise ProjectorPlateauError("projector curve segment must be an object")
        try:
            return cls(
                ProjectorValue.from_mapping(value["lower_projector"]),
                ProjectorValue.from_mapping(value["upper_projector"]),
                _mapping_number(value["slope_ev_per_parameter"], "slope_ev_per_parameter"),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ProjectorPlateauError(f"invalid projector curve segment: {exc}") from exc


@dataclass(frozen=True)
class ProjectorCurve:
    """User-facing U(parameter) evidence; values are never averaged."""

    points: tuple[ProjectorUResult, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.points, tuple) or len(self.points) < 2:
            raise ProjectorPlateauError("projector curve requires at least two U points")
        if any(not isinstance(point, ProjectorUResult) for point in self.points):
            raise ProjectorPlateauError("projector curve points must be ProjectorUResult values")
        projectors = tuple(point.projector for point in self.points)
        if len({projector.kind for projector in projectors}) != 1:
            raise ProjectorPlateauError("projector curve points must use one parameter kind")
        values = tuple(projector.value for projector in projectors)
        if len(set(values)) != len(values):
            raise ProjectorPlateauError("projector curve values must be distinct")
        object.__setattr__(
            self,
            "points",
            tuple(sorted(self.points, key=lambda point: point.projector.value)),
        )

    @property
    def segments(self) -> tuple[ProjectorCurveSegment, ...]:
        return tuple(
            ProjectorCurveSegment(
                lower_projector=left.projector,
                upper_projector=right.projector,
                slope_ev_per_parameter=(right.u_ev - left.u_ev)
                / (right.projector.value - left.projector.value),
            )
            for left, right in zip(self.points, self.points[1:], strict=False)
        )

    def to_mapping(self) -> dict[str, object]:
        return {
            "points": [point.to_mapping() for point in self.points],
            "segments": [segment.to_mapping() for segment in self.segments],
        }

    @classmethod
    def from_mapping(cls, value: object) -> ProjectorCurve:
        if not isinstance(value, dict) or not isinstance(value.get("points"), list):
            raise ProjectorPlateauError("projector curve must contain a points array")
        try:
            result = cls(tuple(ProjectorUResult.from_mapping(item) for item in value["points"]))
            if "segments" in value:
                raw_segments = value["segments"]
                if not isinstance(raw_segments, list):
                    raise ProjectorPlateauError("projector curve segments must be an array")
                parsed_segments = tuple(ProjectorCurveSegment.from_mapping(item) for item in raw_segments)
                if len(parsed_segments) != len(result.segments):
                    raise ProjectorPlateauError("projector curve segment count does not match its points")
            # Serialized segments are derived output. Their values and ordering
            # never decide the curve; recompute them from canonical source points.
            return result
        except (KeyError, TypeError, ValueError) as exc:
            raise ProjectorPlateauError(f"invalid projector curve: {exc}") from exc

    def no_plateau_report_line(self) -> str:
        """Return the required record-only phrase with observed adjacent slopes."""
        slopes = ", ".join(f"{segment.slope_ev_per_parameter:.6g}" for segment in self.segments)
        kind = self.points[0].projector.kind
        parameter = "norm" if kind is ProjectorParameterKind.CUTOFF_NORM else "rc"
        return f"no plateau; U is projector-specific; dU/d({parameter})=[{slopes}] eV per {parameter}"


@dataclass(frozen=True)
class ProjectorSupportGeometry:
    """Record-only comparison of generated support radius and site separation."""

    npts: int | None
    delta_bohr: float | None
    support_radius_bohr: float
    minimum_hubbard_site_distance_bohr: float

    def __post_init__(self) -> None:
        if self.npts is not None and (
            isinstance(self.npts, bool) or not isinstance(self.npts, int) or self.npts < 1
        ):
            raise ProjectorPlateauError("npts must be a positive integer when supplied")
        if (self.npts is None) != (self.delta_bohr is None):
            raise ProjectorPlateauError("npts and delta_bohr must be supplied together")
        if self.delta_bohr is not None:
            object.__setattr__(self, "delta_bohr", _positive_finite(self.delta_bohr, "delta_bohr"))
        object.__setattr__(
            self, "support_radius_bohr", _nonnegative_finite(self.support_radius_bohr, "support_radius_bohr")
        )
        object.__setattr__(
            self,
            "minimum_hubbard_site_distance_bohr",
            _positive_finite(self.minimum_hubbard_site_distance_bohr, "minimum_hubbard_site_distance_bohr"),
        )

    @property
    def half_minimum_distance_bohr(self) -> float:
        return self.minimum_hubbard_site_distance_bohr / 2.0

    @property
    def support_exceeds_half_distance(self) -> bool:
        """Geometric overlap flag only; it never gates a scan or a U result."""
        return self.support_radius_bohr > self.half_minimum_distance_bohr

    def to_mapping(self) -> dict[str, object]:
        return {
            "npts": self.npts,
            "delta_bohr": self.delta_bohr,
            "support_radius_bohr": self.support_radius_bohr,
            "minimum_hubbard_site_distance_bohr": self.minimum_hubbard_site_distance_bohr,
            "half_minimum_distance_bohr": self.half_minimum_distance_bohr,
            "support_exceeds_half_distance": self.support_exceeds_half_distance,
            "decision_role": "RECORD_ONLY",
        }

    @classmethod
    def from_mapping(cls, value: object) -> ProjectorSupportGeometry:
        if not isinstance(value, dict):
            raise ProjectorPlateauError("projector support geometry must be an object")
        try:
            result = cls(
                None if value["npts"] is None else _mapping_integer(value["npts"], "npts"),
                None if value["delta_bohr"] is None else _mapping_number(value["delta_bohr"], "delta_bohr"),
                _mapping_number(value["support_radius_bohr"], "support_radius_bohr"),
                _mapping_number(
                    value["minimum_hubbard_site_distance_bohr"], "minimum_hubbard_site_distance_bohr"
                ),
            )
            # Derived geometry fields are evidence for display, not inputs to a
            # decision. Validate their serialized types, then recompute from the
            # source radii and distances instead of exact-comparing float text.
            _positive_finite(
                _mapping_number(value["half_minimum_distance_bohr"], "half_minimum_distance_bohr"),
                "half_minimum_distance_bohr",
            )
            _mapping_boolean(value["support_exceeds_half_distance"], "support_exceeds_half_distance")
            if value.get("decision_role") != "RECORD_ONLY":
                raise ProjectorPlateauError("geometry decision_role must be RECORD_ONLY")
            return result
        except (KeyError, TypeError, ValueError) as exc:
            raise ProjectorPlateauError(f"invalid projector support geometry: {exc}") from exc


@dataclass(frozen=True)
class ProjectorAssessmentResult:
    """Declaration/characterization status and optional plateau evidence."""

    status: ProjectorAssessment
    plateau_outcome: PlateauOutcome
    reason: str
    declared_projector: ProjectorValue | None = None
    curve: ProjectorCurve | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, ProjectorAssessment):
            raise ProjectorPlateauError("status must be a ProjectorAssessment")
        if not isinstance(self.plateau_outcome, PlateauOutcome):
            raise ProjectorPlateauError("plateau_outcome must be a PlateauOutcome")
        if self.declared_projector is not None and not isinstance(self.declared_projector, ProjectorValue):
            raise ProjectorPlateauError("declared_projector must be a ProjectorValue when supplied")
        if self.curve is not None and not isinstance(self.curve, ProjectorCurve):
            raise ProjectorPlateauError("curve must be a ProjectorCurve when supplied")
        if (self.declared_projector is None) != (self.curve is None):
            raise ProjectorPlateauError(
                "declared projector and characterization curve must be supplied together"
            )
        if self.curve is not None and self.declared_projector not in tuple(
            point.projector for point in self.curve.points
        ):
            raise ProjectorPlateauError("declared projector must have a U value in the characterized curve")
        if self.status is ProjectorAssessment.PROJECTOR_NOT_ASSESSED and self.curve is not None:
            raise ProjectorPlateauError("NOT_ASSESSED cannot carry a declared-projector characterization")
        if self.status is not ProjectorAssessment.PROJECTOR_NOT_ASSESSED and self.curve is None:
            raise ProjectorPlateauError("characterized status requires declared-projector curve evidence")
        if self.status is ProjectorAssessment.PROJECTOR_PLATEAU_CONFIRMED and (
            self.plateau_outcome is not PlateauOutcome.PROJECTOR_PLATEAU_CONFIRMED
        ):
            raise ProjectorPlateauError("confirmed status requires confirmed optional plateau evidence")
        if self.status is ProjectorAssessment.PROJECTOR_DECLARED_AND_CHARACTERIZED and (
            self.plateau_outcome is PlateauOutcome.PROJECTOR_PLATEAU_CONFIRMED
        ):
            raise ProjectorPlateauError("confirmed plateau evidence requires the confirmed status")
        if self.status is ProjectorAssessment.PROJECTOR_NOT_ASSESSED and (
            self.plateau_outcome is PlateauOutcome.PROJECTOR_PLATEAU_CONFIRMED
        ):
            raise ProjectorPlateauError("a plateau cannot be confirmed without declared characterization")
        _identifier(self.reason, "reason")

    @property
    def u_acceptable_for_declared_projector(self) -> bool:
        """Plateau evidence is optional; characterization is enough for declared-projector U."""
        return (
            self.status
            in (
                ProjectorAssessment.PROJECTOR_DECLARED_AND_CHARACTERIZED,
                ProjectorAssessment.PROJECTOR_PLATEAU_CONFIRMED,
            )
            and self.declared_projector is not None
            and self.curve is not None
        )

    def to_mapping(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "plateau_outcome": self.plateau_outcome.value,
            "u_acceptable_for_declared_projector": self.u_acceptable_for_declared_projector,
            "reason": self.reason,
            "declared_projector": (
                None if self.declared_projector is None else self.declared_projector.to_mapping()
            ),
            "curve": None if self.curve is None else self.curve.to_mapping(),
        }

    @classmethod
    def from_mapping(cls, value: object) -> ProjectorAssessmentResult:
        if not isinstance(value, dict):
            raise ProjectorPlateauError("assessment result must be an object")
        try:
            result = cls(
                ProjectorAssessment(value["status"]),
                PlateauOutcome(value["plateau_outcome"]),
                _mapping_string(value["reason"], "reason"),
                None
                if value["declared_projector"] is None
                else ProjectorValue.from_mapping(value["declared_projector"]),
                None if value["curve"] is None else ProjectorCurve.from_mapping(value["curve"]),
            )
            serialized_acceptable = _mapping_boolean(
                value["u_acceptable_for_declared_projector"], "u_acceptable_for_declared_projector"
            )
            if serialized_acceptable != result.u_acceptable_for_declared_projector:
                raise ProjectorPlateauError("declared-projector U acceptability is inconsistent")
            return result
        except (KeyError, TypeError, ValueError) as exc:
            raise ProjectorPlateauError(f"invalid assessment result: {exc}") from exc


def projector_assessment(
    criteria: PlateauCriteria,
    required_gates: tuple[PlateauGateEvidence, ...],
    declared_projector: ProjectorValue | None = None,
    curve: ProjectorCurve | None = None,
) -> ProjectorAssessmentResult:
    """Assess optional plateau evidence separately from declared-projector U.

    A declared projector with a characterized U(parameter) curve remains usable
    even when plateau criteria are absent or the optional plateau is not found.
    Numeric threshold evaluation remains outside this specification skeleton.
    """
    if not isinstance(criteria, PlateauCriteria):
        raise ProjectorPlateauError("criteria must be PlateauCriteria")
    if not isinstance(required_gates, tuple) or any(
        not isinstance(item, PlateauGateEvidence) for item in required_gates
    ):
        raise ProjectorPlateauError("required_gates must be a tuple of PlateauGateEvidence values")
    if declared_projector is not None and not isinstance(declared_projector, ProjectorValue):
        raise ProjectorPlateauError("declared_projector must be a ProjectorValue when supplied")
    if curve is not None and not isinstance(curve, ProjectorCurve):
        raise ProjectorPlateauError("curve must be a ProjectorCurve when supplied")
    if (declared_projector is None) != (curve is None):
        raise ProjectorPlateauError(
            "a declared projector and its characterized curve must be supplied together"
        )
    if curve is not None and declared_projector not in tuple(point.projector for point in curve.points):
        raise ProjectorPlateauError("declared projector must have a U value in the characterized curve")
    requirements = tuple(item.requirement for item in required_gates)
    if (
        not criteria.complete
        or set(requirements) != set(REQUIRED_PLATEAU_REQUIREMENTS)
        or len(requirements) != len(REQUIRED_PLATEAU_REQUIREMENTS)
        or any(item.state is PlateauGateState.NOT_ASSESSED for item in required_gates)
    ):
        plateau_outcome = PlateauOutcome.PROJECTOR_NOT_ASSESSED
    elif any(item.state is PlateauGateState.FAIL for item in required_gates):
        plateau_outcome = PlateauOutcome.PROJECTOR_NO_PLATEAU
    else:
        plateau_outcome = PlateauOutcome.PROJECTOR_PLATEAU_CONFIRMED

    if declared_projector is None:
        return ProjectorAssessmentResult(
            ProjectorAssessment.PROJECTOR_NOT_ASSESSED,
            PlateauOutcome.PROJECTOR_NOT_ASSESSED,
            "no declared-projector U(parameter) curve is attached",
            None,
            None,
        )
    if plateau_outcome is PlateauOutcome.PROJECTOR_PLATEAU_CONFIRMED:
        return ProjectorAssessmentResult(
            ProjectorAssessment.PROJECTOR_PLATEAU_CONFIRMED,
            plateau_outcome,
            "declared projector characterized; optional plateau evidence confirmed",
            declared_projector,
            curve,
        )
    return ProjectorAssessmentResult(
        ProjectorAssessment.PROJECTOR_DECLARED_AND_CHARACTERIZED,
        plateau_outcome,
        "declared projector characterized; optional plateau is absent or unassessed",
        declared_projector,
        curve,
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
            # This is derived evidence: validate its serialized shape/value, then
            # recompute from the source U values to avoid float-printing gates.
            _finite(_mapping_number(value["delta_u_ev"], "delta_u_ev"), "delta_u_ev")
            return result
        except (KeyError, TypeError, ValueError) as exc:
            raise ProjectorPlateauError(f"invalid production control: {exc}") from exc
