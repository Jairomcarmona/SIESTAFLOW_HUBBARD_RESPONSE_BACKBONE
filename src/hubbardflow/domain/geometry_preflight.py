"""Advisory assessment of reference forces and stress for the supplied cell."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any

import numpy as np

from hubbardflow.domain.validation import (
    ValidationError,
    require_finite,
    require_nonnegative_finite,
)


class GeometryPreflightError(ValueError):
    """Raised when geometry-preflight inputs or serialized evidence are invalid."""


class GeometryPreflightState(str, Enum):
    """Informational geometry status; it never changes campaign admission."""

    NEAR_EQUILIBRIUM = "NEAR_EQUILIBRIUM"
    ABOVE_REFERENCE_THRESHOLDS = "ABOVE_REFERENCE_THRESHOLDS"
    NOT_ASSESSED_NO_OUTPUT = "NOT_ASSESSED_NO_OUTPUT"
    NOT_ASSESSED_UNRELIABLE_FOR_DFTU_SHIFT = "NOT_ASSESSED_UNRELIABLE_FOR_DFTU_SHIFT"
    NOT_ASSESSED_CONSTRAINTS = "NOT_ASSESSED_CONSTRAINTS"


@dataclass(frozen=True)
class GeometryThresholdPolicy:
    """Declared advisory thresholds for a fixed-geometry reference output."""

    max_force_ev_ang: float = 0.01
    max_abs_mean_pressure_kbar: float = 5.0
    max_shear_kbar: float = 5.0
    declared_by: str = "DEFAULT"
    version: str = "reference-geometry-preflight-v1"

    def __post_init__(self) -> None:
        for name in ("max_force_ev_ang", "max_abs_mean_pressure_kbar", "max_shear_kbar"):
            try:
                value = require_nonnegative_finite(getattr(self, name), name)
            except ValidationError as exc:
                raise GeometryPreflightError(str(exc)) from exc
            object.__setattr__(self, name, value)
        if self.declared_by not in {"DEFAULT", "CONFIG"}:
            raise GeometryPreflightError("declared_by must be DEFAULT or CONFIG")
        if self.version != "reference-geometry-preflight-v1":
            raise GeometryPreflightError("unsupported geometry-preflight policy version")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | None) -> GeometryThresholdPolicy:
        """Load explicit user thresholds, filling omitted values from this version."""
        if value is None:
            return cls()
        if not isinstance(value, Mapping):
            raise GeometryPreflightError("geometry_preflight must be an object")
        allowed = {
            "max_force_ev_ang",
            "max_abs_mean_pressure_kbar",
            "max_shear_kbar",
            "declared_by",
            "version",
        }
        unknown = sorted(set(value) - allowed)
        if unknown:
            raise GeometryPreflightError(f"unknown geometry_preflight fields: {unknown}")
        defaults = cls()
        declared_by = value.get("declared_by", "CONFIG")
        if not isinstance(declared_by, str):
            raise GeometryPreflightError("geometry_preflight.declared_by must be text")
        version = value.get("version", defaults.version)
        if not isinstance(version, str):
            raise GeometryPreflightError("geometry_preflight.version must be text")
        try:
            return cls(
                max_force_ev_ang=value.get("max_force_ev_ang", defaults.max_force_ev_ang),
                max_abs_mean_pressure_kbar=value.get(
                    "max_abs_mean_pressure_kbar", defaults.max_abs_mean_pressure_kbar
                ),
                max_shear_kbar=value.get("max_shear_kbar", defaults.max_shear_kbar),
                declared_by=declared_by,
                version=version,
            )
        except (TypeError, ValueError) as exc:
            raise GeometryPreflightError(str(exc)) from exc

    def to_mapping(self) -> dict[str, float | str]:
        """Return deterministic JSON-compatible policy data."""
        return {
            "version": self.version,
            "max_force_ev_ang": self.max_force_ev_ang,
            "max_abs_mean_pressure_kbar": self.max_abs_mean_pressure_kbar,
            "max_shear_kbar": self.max_shear_kbar,
            "declared_by": self.declared_by,
        }


@dataclass(frozen=True)
class GeometryAssessment:
    """Reference-only force/stress evidence and its advisory classification."""

    state: GeometryPreflightState
    additional_states: tuple[GeometryPreflightState, ...]
    maximum_force_ev_ang: float | None
    residual_ev_ang: float | None
    maximum_constrained_force_ev_ang: float | None
    stress_voigt_kbar: tuple[float, float, float, float, float, float] | None
    mean_pressure_kbar: float | None
    maximum_shear_kbar: float | None
    constraints_detected: bool
    source_lines: tuple[tuple[str, int], ...]
    policy: GeometryThresholdPolicy

    def to_mapping(self) -> dict[str, Any]:
        """Serialize the assessment without converting statuses to free text."""
        return {
            "state": self.state.value,
            "additional_states": [state.value for state in self.additional_states],
            "maximum_force_ev_ang": self.maximum_force_ev_ang,
            "residual_ev_ang": self.residual_ev_ang,
            "maximum_constrained_force_ev_ang": self.maximum_constrained_force_ev_ang,
            "stress_voigt_kbar": None if self.stress_voigt_kbar is None else list(self.stress_voigt_kbar),
            "mean_pressure_kbar": self.mean_pressure_kbar,
            "maximum_shear_kbar": self.maximum_shear_kbar,
            "constraints_detected": self.constraints_detected,
            "source_lines": {name: line for name, line in self.source_lines},
            "policy": self.policy.to_mapping(),
            "decision_role": "RECORD_ONLY",
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> GeometryAssessment:
        """Restore a saved assessment and reject malformed/non-finite evidence."""
        try:
            state = GeometryPreflightState(value["state"])
            extra_raw = value.get("additional_states", [])
            if not isinstance(extra_raw, list):
                raise GeometryPreflightError("additional_states must be an array")
            extra = tuple(GeometryPreflightState(item) for item in extra_raw)
            stress_raw = value.get("stress_voigt_kbar")
            stress = (
                None
                if stress_raw is None
                else tuple(require_finite(item, "stress_voigt_kbar") for item in stress_raw)
            )
            if stress is not None and len(stress) != 6:
                raise GeometryPreflightError("stress_voigt_kbar must contain six values")
            lines_raw = value.get("source_lines", {})
            if not isinstance(lines_raw, Mapping):
                raise GeometryPreflightError("source_lines must be an object")
            lines = tuple(sorted((str(name), int(line)) for name, line in lines_raw.items()))
            if any(line < 1 for _, line in lines):
                raise GeometryPreflightError("source line numbers must be positive")
            constraints = value.get("constraints_detected")
            if type(constraints) is not bool:
                raise GeometryPreflightError("constraints_detected must be a boolean")
            policy_raw = value.get("policy")
            if not isinstance(policy_raw, Mapping):
                raise GeometryPreflightError("policy must be an object")
            optional_values = {
                name: None if value.get(name) is None else require_finite(value[name], name)
                for name in (
                    "maximum_force_ev_ang",
                    "residual_ev_ang",
                    "maximum_constrained_force_ev_ang",
                    "mean_pressure_kbar",
                    "maximum_shear_kbar",
                )
            }
            return cls(
                state=state,
                additional_states=extra,
                **optional_values,
                stress_voigt_kbar=stress,
                constraints_detected=constraints,
                source_lines=lines,
                policy=GeometryThresholdPolicy.from_mapping(policy_raw),
            )
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            if isinstance(exc, GeometryPreflightError):
                raise
            raise GeometryPreflightError(f"invalid geometry assessment: {exc}") from exc


def assess_reference_geometry(
    *,
    maximum_force_ev_ang: float | None,
    residual_ev_ang: float | None,
    maximum_constrained_force_ev_ang: float | None,
    stress_voigt_kbar: tuple[float, float, float, float, float, float] | None,
    source_lines: tuple[tuple[str, int], ...],
    policy: GeometryThresholdPolicy,
    unreliable_for_dftu_shift: bool,
) -> GeometryAssessment:
    """Classify reference metrics only; thresholds never affect campaign state.

    SIESTA stress is reported as the energy derivative with respect to strain.
    Mean pressure is therefore ``-trace(stress)/3`` (positive in compression).
    Maximum shear is half the range of principal stresses.
    """
    numeric_values = (
        maximum_force_ev_ang,
        residual_ev_ang,
        maximum_constrained_force_ev_ang,
    )
    try:
        normalized = tuple(
            None if item is None else require_nonnegative_finite(item, "force metric")
            for item in numeric_values
        )
        stress = (
            None
            if stress_voigt_kbar is None
            else tuple(require_finite(item, "stress_voigt_kbar") for item in stress_voigt_kbar)
        )
    except ValidationError as exc:
        raise GeometryPreflightError(str(exc)) from exc
    if stress is not None and len(stress) != 6:
        raise GeometryPreflightError("stress_voigt_kbar must contain six values")
    if type(unreliable_for_dftu_shift) is not bool:
        raise GeometryPreflightError("unreliable_for_dftu_shift must be a boolean")
    if any(
        not name or isinstance(line, bool) or not isinstance(line, int) or line < 1
        for name, line in source_lines
    ):
        raise GeometryPreflightError("source line records require a name and positive integer line")

    maximum_force, residual, constrained_force = normalized
    if maximum_force is None or residual is None or stress is None:
        return GeometryAssessment(
            GeometryPreflightState.NOT_ASSESSED_NO_OUTPUT,
            (),
            maximum_force,
            residual,
            constrained_force,
            stress,
            None,
            None,
            False,
            tuple(sorted(source_lines)),
            policy,
        )

    xx, yy, zz, yz, xz, xy = stress
    mean_pressure = -(xx + yy + zz) / 3.0
    tensor = np.asarray([[xx, xy, xz], [xy, yy, yz], [xz, yz, zz]], dtype=float)
    principal = np.linalg.eigvalsh(tensor)
    maximum_shear = float((principal[-1] - principal[0]) / 2.0)
    constraints_detected = constrained_force is not None and constrained_force != maximum_force
    additional_states: tuple[GeometryPreflightState, ...] = ()

    if constraints_detected:
        state = GeometryPreflightState.NOT_ASSESSED_CONSTRAINTS
        if unreliable_for_dftu_shift:
            additional_states = (GeometryPreflightState.NOT_ASSESSED_UNRELIABLE_FOR_DFTU_SHIFT,)
    elif unreliable_for_dftu_shift:
        state = GeometryPreflightState.NOT_ASSESSED_UNRELIABLE_FOR_DFTU_SHIFT
    else:
        exceeds = (
            maximum_force > policy.max_force_ev_ang
            or abs(mean_pressure) > policy.max_abs_mean_pressure_kbar
            or maximum_shear > policy.max_shear_kbar
        )
        state = (
            GeometryPreflightState.ABOVE_REFERENCE_THRESHOLDS
            if exceeds
            else GeometryPreflightState.NEAR_EQUILIBRIUM
        )

    return GeometryAssessment(
        state,
        additional_states,
        maximum_force,
        residual,
        constrained_force,
        stress,
        mean_pressure,
        maximum_shear,
        constraints_detected,
        tuple(sorted(source_lines)),
        policy,
    )
