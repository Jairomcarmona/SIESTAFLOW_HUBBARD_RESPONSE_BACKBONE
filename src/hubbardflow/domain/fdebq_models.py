"""Versioned records for conditional FD-EBQ rounds, separate from certificates."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Self

from .hash_traceability import DigestWarning, digest_warning
from .response_budget_models import BoundKind, CandidateBudget, ElementSeries, ResponseBudgetError, _Record
from .response_protocol import EstimatorSpec
from .scf_ladder_models import ScfEnvelope
from .symmetry_reduction import ResponseMode
from .validation import (
    require_fdf_representable_ev,
    require_int,
    require_nonnegative_finite,
    require_positive_finite,
    require_sha256,
)


class FdebqRoundsError(ResponseBudgetError):
    """Round evidence or the declared calibration protocol is inconsistent."""


class _RoundRecord(_Record):
    def __post_init__(self) -> None:
        try:
            super().__post_init__()
        except ValueError as exc:
            raise FdebqRoundsError(str(exc)) from exc

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> Self:
        try:
            return super().from_mapping(payload)
        except ValueError as exc:
            raise FdebqRoundsError(f"invalid {cls.__name__}: {exc}") from exc


class ColumnStatus(str, Enum):
    RESOLVED = "RESOLVED"
    UNRESOLVED = "UNRESOLVED"


class RoundStatus(str, Enum):
    WAITING = "WAITING"
    CONTINUE = "CONTINUE"
    QUALIFIED = "QUALIFIED"
    REVIEW = "REVIEW"
    NOT_ESTABLISHED = "NOT_ESTABLISHED"


class RoundReason(str, Enum):
    ROUND_BARRIER = "ROUND_BARRIER"
    NO_COMMON_ESTIMATOR = "NO_COMMON_ESTIMATOR"
    LATTICE_EXHAUSTED = "LATTICE_EXHAUSTED"
    MAX_ROUNDS = "MAX_ROUNDS"
    SCF_ESTIMATE_MISSING = "SCF_ESTIMATE_MISSING"
    SCIENTIFIC_STATE_NOT_ESTABLISHED = "SCIENTIFIC_STATE_NOT_ESTABLISHED"
    MATRIX_NOT_RESOLVED = "MATRIX_NOT_RESOLVED"
    REQUIREMENT_NOT_MET = "REQUIREMENT_NOT_MET"
    BUDGET_FALSIFIED = "BUDGET_FALSIFIED"
    VALIDATION_NOT_ESTABLISHED = "VALIDATION_NOT_ESTABLISHED"
    SCF_UNDER_RESOLVED = "SCF_UNDER_RESOLVED"
    NOISE_FLOOR_NOT_ESTABLISHED = "NOISE_FLOOR_NOT_ESTABLISHED"
    SCF_ENVELOPE_NOT_COVERED = "SCF_ENVELOPE_NOT_COVERED"


@dataclass(frozen=True)
class CalibrationProtocol(_RoundRecord):
    """All lattice, seed, budget, and U requirements are explicit and digest-bound.

    Four initial scales are mandatory to expose mixed cancelling terms. Seeds
    are shared by all columns of a mode; later grids may differ by column.
    """

    version: str
    candidate_lattice_ev: tuple[float, ...]
    seed_bare_ev: tuple[float, ...]
    seed_screened_ev: tuple[float, ...]
    max_rounds: int
    kappa: float
    tau_u_ev: float
    scf_level_id: str
    t0_t4_result_sha256: str | None

    def __post_init__(self) -> None:
        super().__post_init__()
        try:
            require_int(self.max_rounds, "max_rounds", minimum=1)
            require_positive_finite(self.kappa, "kappa")
            require_positive_finite(self.tau_u_ev, "tau_u_ev")
            if self.t0_t4_result_sha256 is not None:
                require_sha256(self.t0_t4_result_sha256, "t0_t4_result_sha256")
            for name in ("candidate_lattice_ev", "seed_bare_ev", "seed_screened_ev"):
                values = getattr(self, name)
                ordered = tuple(sorted(values))
                if len(set(values)) != len(values) or len(values) < 4:
                    raise FdebqRoundsError(f"{name} requires at least four distinct amplitudes")
                for value in values:
                    require_positive_finite(value, name)
                    require_fdf_representable_ev(value, name)
                object.__setattr__(self, name, ordered)
            if any(
                not set(seed) <= set(self.candidate_lattice_ev)
                for seed in (self.seed_bare_ev, self.seed_screened_ev)
            ):
                raise FdebqRoundsError("seeds must belong to candidate_lattice_ev")
        except ValueError as exc:
            raise FdebqRoundsError(str(exc)) from exc

    @property
    def digest(self) -> str:
        return hashlib.sha256(
            json.dumps(self.to_mapping(), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        ).hexdigest()

    def seed(self, mode: ResponseMode) -> tuple[float, ...]:
        return self.seed_bare_ev if mode is ResponseMode.BARE else self.seed_screened_ev


@dataclass(frozen=True)
class ScfCandidateEstimate(_RoundRecord):
    """TASK17 supplies a slope ESTIMATE only for the covered candidate functional.

    An under-resolved ladder may contribute a radius while retaining REVIEW.
    Missing estimates are never replaced by a numerical zero noise claim.
    """

    site_observed: str
    estimator: EstimatorSpec
    radius_e_per_ev: float
    kind: BoundKind
    admissible: bool
    qualified: bool

    def __post_init__(self) -> None:
        super().__post_init__()
        try:
            require_nonnegative_finite(self.radius_e_per_ev, "radius_e_per_ev")
        except ValueError as exc:
            raise FdebqRoundsError(str(exc)) from exc
        if self.kind is not BoundKind.ESTIMATE:
            raise FdebqRoundsError("SCF candidate uncertainty must be ESTIMATE")


@dataclass(frozen=True)
class ColumnEvidence(_RoundRecord):
    site_id: str
    mode: ResponseMode
    series: tuple[ElementSeries, ...]
    failed_amplitudes_ev: tuple[float, ...]
    scf_estimates: tuple[ScfCandidateEstimate, ...]
    state_gate_established: bool
    scf_envelopes: tuple[ScfEnvelope, ...] = ()

    def __post_init__(self) -> None:
        super().__post_init__()
        if not self.series or len({s.site_observed for s in self.series}) != len(self.series):
            raise FdebqRoundsError("column requires distinct observed rows")
        if any(s.site_perturbed != self.site_id or s.mode is not self.mode for s in self.series):
            raise FdebqRoundsError("series key disagrees with column")
        grids = {tuple(abs(p.alpha_ev) for p in s.points if p.alpha_ev > 0) for s in self.series}
        if len(grids) != 1:
            raise FdebqRoundsError("all rows of a column must share the same amplitudes")
        for a in self.failed_amplitudes_ev:
            try:
                require_positive_finite(a, "failed amplitude")
                require_fdf_representable_ev(a, "failed amplitude")
            except ValueError as exc:
                raise FdebqRoundsError(str(exc)) from exc
        keys = {(e.site_observed, e.estimator) for e in self.scf_estimates}
        if len(keys) != len(self.scf_estimates) or any(
            e.site_observed not in {s.site_observed for s in self.series} for e in self.scf_estimates
        ):
            raise FdebqRoundsError("SCF estimates require distinct known row/estimator keys")
        if self.scf_envelopes:
            if self.scf_estimates:
                raise FdebqRoundsError("supply measured SCF envelopes or injected estimates, never both")
            if {e.site_observed for e in self.scf_envelopes} != {s.site_observed for s in self.series} or (
                len(self.scf_envelopes) != len(self.series)
            ):
                raise FdebqRoundsError("SCF envelopes must cover every distinct observed row")
            if any(e.site_perturbed != self.site_id or e.mode is not self.mode for e in self.scf_envelopes):
                raise FdebqRoundsError("SCF envelope key disagrees with column")
            object.__setattr__(
                self, "scf_envelopes", tuple(sorted(self.scf_envelopes, key=lambda e: e.site_observed))
            )
        object.__setattr__(self, "series", tuple(sorted(self.series, key=lambda s: s.site_observed)))
        object.__setattr__(self, "failed_amplitudes_ev", tuple(sorted(set(self.failed_amplitudes_ev))))
        object.__setattr__(
            self,
            "scf_estimates",
            tuple(
                sorted(
                    self.scf_estimates,
                    key=lambda e: (
                        e.site_observed,
                        e.estimator.kind.value,
                        e.estimator.amplitudes_ev,
                        e.estimator.polynomial_degree or 0,
                    ),
                )
            ),
        )


@dataclass(frozen=True)
class SelectedElement(_RoundRecord):
    site_observed: str
    candidate: CandidateBudget
    scf_estimate_e_per_ev: float | None
    scf_qualified: bool

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.scf_estimate_e_per_ev is not None:
            try:
                require_nonnegative_finite(self.scf_estimate_e_per_ev, "scf_estimate_e_per_ev")
            except ValueError as exc:
                raise FdebqRoundsError(str(exc)) from exc
        elif self.scf_qualified:
            raise FdebqRoundsError("missing SCF cannot be qualified")


@dataclass(frozen=True)
class ColumnSelection(_RoundRecord):
    site_id: str
    mode: ResponseMode
    status: ColumnStatus
    observed_amplitudes_ev: tuple[float, ...]
    estimator: EstimatorSpec | None
    elements: tuple[SelectedElement, ...]
    diagnostic_best: tuple[tuple[str, CandidateBudget | None], ...]

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.status is not (ColumnStatus.UNRESOLVED if self.estimator is None else ColumnStatus.RESOLVED):
            raise FdebqRoundsError("column status disagrees with the common estimator")
        if self.estimator is None and self.elements:
            raise FdebqRoundsError("unresolved columns cannot supply production elements")
        if self.estimator is not None and (
            not self.elements
            or len({e.site_observed for e in self.elements}) != len(self.elements)
            or any(
                e.candidate.estimator != self.estimator or not e.candidate.admissible for e in self.elements
            )
        ):
            raise FdebqRoundsError("production elements require the same admissible column estimator")


@dataclass(frozen=True)
class ConditionalMatrixQualification(_RoundRecord):
    beta0: float
    beta: float
    half_width_u_ev: tuple[float, ...]
    passed: bool
    reasons: tuple[RoundReason, ...]
    label: str

    def __post_init__(self) -> None:
        super().__post_init__()
        try:
            require_nonnegative_finite(self.beta0, "beta0")
            require_nonnegative_finite(self.beta, "beta")
            for radius in self.half_width_u_ev:
                require_nonnegative_finite(radius, "half_width_u_ev")
        except ValueError as exc:
            raise FdebqRoundsError(str(exc)) from exc
        if self.label != "calificación condicional al modelo de error":
            raise FdebqRoundsError("matrix qualification must carry the conditional-model label")
        if self.passed and (self.beta0 >= 1 or self.beta >= 1 or not self.half_width_u_ev or self.reasons):
            raise FdebqRoundsError("passing matrix requires strict beta gates and resolved U intervals")


@dataclass(frozen=True)
class CalibrationQualification(_RoundRecord):
    status: RoundStatus
    columns: tuple[ColumnSelection, ...]
    matrix: ConditionalMatrixQualification | None
    reasons: tuple[RoundReason, ...]
    protocol_sha256: str
    evidence_sha256: str | None
    label: str

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> Self:
        raw = dict(payload)
        recorded = raw.pop("evidence_sha256", None)
        raw.pop("traceability_warnings", None)
        result = super().from_mapping({**raw, "evidence_sha256": None})
        object.__setattr__(
            result,
            "evidence_sha256",
            recorded if isinstance(recorded, str) or recorded is None else repr(recorded),
        )
        return result

    @property
    def traceability_warnings(self) -> tuple[DigestWarning, ...]:
        warning = digest_warning(self.evidence_sha256, None, "evidence_sha256")
        return () if warning is None else (warning,)

    def to_mapping(self) -> dict[str, object]:
        result = super().to_mapping()
        if self.traceability_warnings:
            result["traceability_warnings"] = [w.to_mapping() for w in self.traceability_warnings]
        return result

    def __post_init__(self) -> None:
        recorded = self.evidence_sha256
        object.__setattr__(self, "evidence_sha256", None)
        super().__post_init__()
        object.__setattr__(
            self,
            "evidence_sha256",
            recorded if isinstance(recorded, str) or recorded is None else repr(recorded),
        )
        try:
            require_sha256(self.protocol_sha256, "protocol_sha256")
        except ValueError as exc:
            raise FdebqRoundsError(str(exc)) from exc
        if self.label != "calificación condicional al modelo de error":
            raise FdebqRoundsError("qualification must carry the conditional-model label")
        if self.status is RoundStatus.QUALIFIED and (
            self.matrix is None
            or not self.matrix.passed
            or self.reasons
            or not self.columns
            or any(
                c.estimator is None or not c.elements or any(not e.scf_qualified for e in c.elements)
                for c in self.columns
            )
        ):
            raise FdebqRoundsError("QUALIFIED requires complete admissible columns, SCF and the full U gate")


@dataclass(frozen=True)
class RoundRequest(_RoundRecord):
    site_id: str
    mode: ResponseMode
    alpha_ev: float

    def __post_init__(self) -> None:
        super().__post_init__()
        try:
            require_fdf_representable_ev(self.alpha_ev, "alpha_ev")
        except ValueError as exc:
            raise FdebqRoundsError(str(exc)) from exc
        if self.alpha_ev == 0:
            raise FdebqRoundsError("round requests must be nonzero perturbations")


@dataclass(frozen=True)
class RoundDecision(_RoundRecord):
    qualification: CalibrationQualification
    next_requests: tuple[RoundRequest, ...]
