"""Versioned D5 SCF evidence: every radius remains a conditional ESTIMATE."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from fractions import Fraction
from itertools import pairwise
from typing import Self

from .response_budget_models import BoundKind, ElementSeries, ResponseBudgetError, _Record
from .response_protocol import EstimatorSpec
from .symmetry_reduction import ResponseMode
from .validation import require_nonnegative_finite, require_positive_finite


class ScfLadderError(ResponseBudgetError):
    """Ladder evidence does not support the declared D5 calculation."""


class _ScfRecord(_Record):
    def __post_init__(self) -> None:
        try:
            super().__post_init__()
        except ValueError as exc:
            raise ScfLadderError(str(exc)) from exc

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> Self:
        try:
            return super().from_mapping(payload)
        except ValueError as exc:
            raise ScfLadderError(str(exc)) from exc


class ScfStatus(str, Enum):
    ESTABLISHED = "ESTABLISHED"
    SCF_UNDER_RESOLVED = "SCF_UNDER_RESOLVED"
    NOISE_FLOOR_NOT_ESTABLISHED = "NOISE_FLOOR_NOT_ESTABLISHED"
    DISABLED = "DISABLED"
    NOT_ESTABLISHED = "NOT_ESTABLISHED"


class ScfReason(str, Enum):
    SCF_UNDER_RESOLVED = "SCF_UNDER_RESOLVED"
    NOISE_FLOOR_NOT_ESTABLISHED = "NOISE_FLOOR_NOT_ESTABLISHED"
    SCF_ENVELOPE_NOT_COVERED = "SCF_ENVELOPE_NOT_COVERED"
    SCF_LADDER_DISABLED = "SCF_LADDER_DISABLED"
    SCF_LADDER_PROTOCOL_V1 = "SCF_LADDER_PROTOCOL_V1"
    PARENT_LEVEL_NOT_DISTINCT = "PARENT_LEVEL_NOT_DISTINCT"
    SCF_LEVEL_NOT_APPLIED = "SCF_LEVEL_NOT_APPLIED"
    SCF_CRITERIA_NOT_ACTIVE = "SCF_CRITERIA_NOT_ACTIVE"
    LEVEL_REFERENCE_NOT_CONVERGED = "LEVEL_REFERENCE_NOT_CONVERGED"


@dataclass(frozen=True)
class ScfLevel(_ScfRecord):
    level_id: str
    dm_tolerance: float
    # None preserves historical algebraic v1 records, never a production H default.
    h_tolerance_ev: float | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        try:
            require_positive_finite(self.dm_tolerance, "dm_tolerance")
            if self.h_tolerance_ev is not None:
                require_positive_finite(self.h_tolerance_ev, "h_tolerance_ev")
        except ValueError as exc:
            raise ScfLadderError(str(exc)) from exc

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> Self:
        historical = dict(payload)
        if "h_tolerance_ev" not in historical:
            historical["h_tolerance_ev"] = None
        return super().from_mapping(historical)

    def require_echo_representable(self) -> None:
        """The six-decimal SIESTA echo must prove both declared tolerances exactly."""
        for name, value in (("dm_tolerance", self.dm_tolerance), ("h_tolerance_ev", self.h_tolerance_ev)):
            if value is None:
                raise ScfLadderError(f"v2 requires explicit {name}")
            units = Fraction(str(value)) * 1_000_000
            if units < 1 or units.denominator != 1:
                raise ScfLadderError(f"{name} must be >= 1e-6 and an exact multiple of 1e-6")


@dataclass(frozen=True)
class ScfLadderProtocol(_ScfRecord):
    """Explicit three-level ladder, safety multiplier and contraction ceiling.

    A disabled policy is representable; evaluation requires explicit enablement.
    No scientifically calibrated parameter has a built-in profile or default.
    """

    version: str
    enabled: bool
    levels: tuple[ScfLevel, ...]
    theta: float
    rho_max: float

    def __post_init__(self) -> None:
        super().__post_init__()
        try:
            require_positive_finite(self.theta, "theta")
            require_nonnegative_finite(self.rho_max, "rho_max")
            if self.rho_max >= 1:
                raise ScfLadderError("rho_max must be less than one for the geometric estimate")
            if len(self.levels) != 3 or len({level.level_id for level in self.levels}) != 3:
                raise ScfLadderError("D5 requires exactly three distinct SCF levels")
            ordered = tuple(sorted(self.levels, key=lambda level: -level.dm_tolerance))
            if len({level.dm_tolerance for level in ordered}) != 3:
                raise ScfLadderError("SCF tolerances must strictly decrease")
            object.__setattr__(self, "levels", ordered)
            if self.version in {"v2", "scf-ladder-v2"}:
                for level in ordered:
                    level.require_echo_representable()
                h_tolerances = tuple(level.h_tolerance_ev for level in ordered)
                if any(lo is None or hi is None or lo <= hi for lo, hi in pairwise(h_tolerances)):
                    raise ScfLadderError("SCF H tolerances must strictly decrease with DM tolerances")
        except ValueError as exc:
            raise ScfLadderError(str(exc)) from exc

    @property
    def digest(self) -> str:
        return hashlib.sha256(
            json.dumps(self.to_mapping(), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        ).hexdigest()

    @property
    def status(self) -> ScfStatus:
        """Historical algebraic ladders cannot establish user-produced SCF evidence."""
        return ScfStatus.ESTABLISHED if self.version in {"v2", "scf-ladder-v2"} else ScfStatus.NOT_ESTABLISHED

    @property
    def reason_codes(self) -> tuple[ScfReason, ...]:
        return () if self.status is ScfStatus.ESTABLISHED else (ScfReason.SCF_LADDER_PROTOCOL_V1,)

    def require_evidence_v2(self) -> None:
        if self.status is not ScfStatus.ESTABLISHED:
            raise ScfLadderError("NOT_ESTABLISHED: SCF_LADDER_PROTOCOL_V1")
        for level in self.levels:
            level.require_echo_representable()


@dataclass(frozen=True)
class LadderEvidence(_ScfRecord):
    """One row's paired nonzero perturbations, at one declared SCF level."""

    level_id: str
    series: ElementSeries


@dataclass(frozen=True)
class ScfAmplitudeEstimate(_ScfRecord):
    amplitude_ev: float
    response_magnitude_e: float
    eta1_plus_e: float
    eta1_minus_e: float
    eta2_plus_e: float
    eta2_minus_e: float
    rho_hat: float
    delta_estimate_e: float | None
    status: ScfStatus
    kind: BoundKind

    def __post_init__(self) -> None:
        super().__post_init__()
        try:
            require_positive_finite(self.amplitude_ev, "amplitude_ev")
            for value in (
                self.response_magnitude_e,
                self.eta1_plus_e,
                self.eta1_minus_e,
                self.eta2_plus_e,
                self.eta2_minus_e,
                self.rho_hat,
            ):
                require_nonnegative_finite(value, "SCF amplitude quantity")
            if self.delta_estimate_e is not None:
                require_nonnegative_finite(self.delta_estimate_e, "delta_estimate_e")
            if self.kind is not BoundKind.ESTIMATE:
                raise ScfLadderError("SCF quantities must be ESTIMATE")
            failed = self.status is ScfStatus.NOISE_FLOOR_NOT_ESTABLISHED
            if failed != (self.delta_estimate_e is None) or self.status is ScfStatus.DISABLED:
                raise ScfLadderError("SCF amplitude status disagrees with available estimate")
        except ValueError as exc:
            raise ScfLadderError(str(exc)) from exc


@dataclass(frozen=True)
class ScfEnvelope(_ScfRecord):
    """Two measured endpoints bind a conditional per-point absolute/relative model.

    The largest endpoint rho is used for both components (conservative D5
    implementation decision). No amplitude outside the closed interval is covered.
    Evidence and protocol are retained so injected mappings can be checked again.
    """

    site_perturbed: str
    mode: ResponseMode
    site_observed: str
    protocol: ScfLadderProtocol
    evidence: tuple[LadderEvidence, ...]
    amplitudes: tuple[ScfAmplitudeEstimate, ...]
    eps_abs_e: float | None
    eps_rel: float | None
    rho_hat: float | None
    status: ScfStatus
    kind: BoundKind

    def __post_init__(self) -> None:
        super().__post_init__()
        try:
            for value in (self.eps_abs_e, self.eps_rel, self.rho_hat):
                if value is not None:
                    require_nonnegative_finite(value, "SCF envelope quantity")
            if self.kind is not BoundKind.ESTIMATE:
                raise ScfLadderError("SCF envelope must be ESTIMATE")
            if (
                len(self.amplitudes) != 2
                or not self.amplitudes[0].amplitude_ev < self.amplitudes[1].amplitude_ev
            ):
                raise ScfLadderError("envelope requires two increasing measured amplitudes")
            present = self.eps_abs_e is not None and self.eps_rel is not None and self.rho_hat is not None
            if present != (self.status in (ScfStatus.ESTABLISHED, ScfStatus.SCF_UNDER_RESOLVED)):
                raise ScfLadderError("SCF envelope status disagrees with available model")
        except ValueError as exc:
            raise ScfLadderError(str(exc)) from exc

    @property
    def qualified(self) -> bool:
        return self.status is ScfStatus.ESTABLISHED

    def covers(self, amplitudes_ev: tuple[float, ...]) -> bool:
        small, large = (item.amplitude_ev for item in self.amplitudes)
        return bool(amplitudes_ev) and all(small <= a <= large for a in amplitudes_ev)


@dataclass(frozen=True)
class ScfResponseEstimate(_ScfRecord):
    site_perturbed: str
    mode: ResponseMode
    site_observed: str
    estimator: EstimatorSpec
    radius_e_per_ev: float
    status: ScfStatus
    kind: BoundKind

    def __post_init__(self) -> None:
        super().__post_init__()
        try:
            require_nonnegative_finite(self.radius_e_per_ev, "radius_e_per_ev")
            if self.kind is not BoundKind.ESTIMATE or self.status not in (
                ScfStatus.ESTABLISHED,
                ScfStatus.SCF_UNDER_RESOLVED,
            ):
                raise ScfLadderError("response estimate requires an available ESTIMATE model")
        except ValueError as exc:
            raise ScfLadderError(str(exc)) from exc
