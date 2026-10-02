"""Versioned frozen plan: coverage evidence, resolved estimators and direct runs.

This contract records qualification separately from the unchanged U certificate.
No numerical tolerance or scientific selector is supplied implicitly.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from enum import Enum
from hashlib import sha256
from typing import cast

from .coverage_models import CoverageQualification, CoverageReferenceEvidence, CoverageStatus
from .perturbation_plan_evidence import (
    PerturbationPlanError,
    freeze_inventory,
    identifier,
    inventory_from_mapping,
    inventory_mapping,
)
from .response_protocol import ColumnPlan, EstimatorKind, EstimatorSpec, ResolvedResponseProtocol
from .state_evidence import EvidenceStatus
from .subspace_inventory import CorrelatedSubspaceInventory, InventoryStatus
from .symmetry_reduction import ResponseMode
from .validation import require_fdf_representable_ev, require_int, require_positive_finite, require_sha256

SCHEMA = "hubbardflow.resolved_perturbation_plan.v1"
ReferenceEvidence = CoverageReferenceEvidence


class PlanStatus(str, Enum):
    READY = "READY"
    REVIEW = "REVIEW"
    NOT_ESTABLISHED = "NOT_ESTABLISHED"
    FAIL = "FAIL"


class PlanReason(str, Enum):
    CALIBRATION_NOT_ENABLED = "CALIBRATION_NOT_ENABLED"
    INVENTORY_NOT_ESTABLISHED = "INVENTORY_NOT_ESTABLISHED"
    REFERENCE_NOT_ADMISSIBLE = "REFERENCE_NOT_ADMISSIBLE"
    PARENT_DM_NOT_ESTABLISHED = "PARENT_DM_NOT_ESTABLISHED"
    SHADOW_PENDING = "SHADOW_PENDING"
    FEATURES_NOT_ENABLED = "FEATURES_NOT_ENABLED"
    DISABLED_OR_FIXED = "DISABLED_OR_FIXED"


class AlphaStrategy(str, Enum):
    FIXED_PROTOCOL_GRID = "FIXED_PROTOCOL_GRID"
    USER_EXPLICIT_GRID = "USER_EXPLICIT_GRID"
    CALIBRATED_GRID = "CALIBRATED_GRID"


class CalibrationStatus(str, Enum):
    NOT_ASSESSED = "NOT_ASSESSED"


@dataclass(frozen=True)
class CalibrationQualification:
    """Explicit grids retain their estimator without claiming error qualification."""

    status: CalibrationStatus
    evidence_sha256: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.status, CalibrationStatus):
            raise PerturbationPlanError("calibration status must be a CalibrationStatus")
        for digest in self.evidence_sha256:
            require_sha256(digest, "calibration evidence")
        object.__setattr__(self, "evidence_sha256", tuple(sorted(set(self.evidence_sha256))))

    def to_mapping(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_mapping(cls, row: Mapping[str, object]) -> CalibrationQualification:
        return cls(
            CalibrationStatus(cast(str, row["status"])), tuple(cast(Sequence[str], row["evidence_sha256"]))
        )


@dataclass(frozen=True)
class ColumnCalibration:
    alpha_strategy: AlphaStrategy
    column_plan: ColumnPlan
    qualification: CalibrationQualification

    def to_mapping(self) -> dict[str, object]:
        return {
            "alpha_strategy": self.alpha_strategy.value,
            "column_plan": asdict(self.column_plan),
            "estimator_weights": self.column_plan.estimator.weights(),
            "qualification": self.qualification.to_mapping(),
        }

    @classmethod
    def from_mapping(cls, row: Mapping[str, object]) -> ColumnCalibration:
        c = cast(Mapping[str, object], row["column_plan"])
        e = cast(Mapping[str, object], c["estimator"])
        column = ColumnPlan(
            cast(str, c["site_id"]),
            ResponseMode(cast(str, c["mode"])),
            tuple(cast(Sequence[float], c["amplitudes_ev"])),
            EstimatorSpec(
                EstimatorKind(cast(str, e["kind"])),
                cast(int | None, e["polynomial_degree"]),
                tuple(cast(Sequence[float], e["amplitudes_ev"])),
            ),
            cast(str, c["scf_level_id"]),
        )
        return cls(
            AlphaStrategy(cast(str, row["alpha_strategy"])),
            column,
            CalibrationQualification.from_mapping(cast(Mapping[str, object], row["qualification"])),
        )


@dataclass(frozen=True)
class RunSpec:
    site_id: str
    mode: ResponseMode
    alpha_ev: float

    def __post_init__(self) -> None:
        identifier(self.site_id, "run site")
        if not isinstance(self.mode, ResponseMode):
            raise PerturbationPlanError("run mode must be a ResponseMode")
        if require_fdf_representable_ev(self.alpha_ev, "alpha_ev") == 0:
            raise PerturbationPlanError("zero belongs to the shared reference, not a perturbation")

    def to_mapping(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_mapping(cls, row: Mapping[str, object]) -> RunSpec:
        return cls(
            cast(str, row["site_id"]), ResponseMode(cast(str, row["mode"])), cast(float, row["alpha_ev"])
        )

    @property
    def identity(self) -> tuple[str, ResponseMode, float]:
        """Directory-independent experiment identity, matching the fixed campaign."""
        return self.site_id, self.mode, self.alpha_ev


@dataclass(frozen=True)
class ReconstructionMap:
    omitted_site_id: str
    representative: str
    operation_id: int

    def __post_init__(self) -> None:
        identifier(self.omitted_site_id, "omitted site")
        identifier(self.representative, "representative")
        require_int(self.operation_id, "operation id", minimum=0)

    def to_mapping(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_mapping(cls, row: Mapping[str, object]) -> ReconstructionMap:
        return cls(
            cast(str, row["omitted_site_id"]),
            cast(str, row["representative"]),
            cast(int, row["operation_id"]),
        )


@dataclass(frozen=True)
class ResolvedPerturbationPlan:
    schema: str
    source_fdf_sha256: str
    effective_fdf_sha256: str
    inventory: CorrelatedSubspaceInventory
    reference: ReferenceEvidence
    coverage: CoverageQualification
    response_protocol: ResolvedResponseProtocol
    calibration: tuple[ColumnCalibration, ...]
    computed_columns: tuple[str, ...]
    run_specs: tuple[RunSpec, ...]
    reconstruction_maps: tuple[ReconstructionMap, ...]
    protocol_version: str
    planner_version: str
    backend_identity: str
    tau_u_ev: float | None
    status: PlanStatus
    reason_codes: tuple[PlanReason, ...]

    def __post_init__(self) -> None:
        try:
            self._validate()
            # Reject nonfinite values anywhere in nested evidence, including fallback states.
            _ = self.digest
        except (ValueError, TypeError, AttributeError, KeyError) as exc:
            raise PerturbationPlanError(f"invalid resolved perturbation plan: {exc}") from exc

    def _validate(self) -> None:
        if self.schema != SCHEMA:
            raise PerturbationPlanError(f"schema must be {SCHEMA}")
        for digest in (self.source_fdf_sha256, self.effective_fdf_sha256):
            require_sha256(digest, "FDF identity")
        for name in ("protocol_version", "planner_version", "backend_identity"):
            identifier(getattr(self, name), name)
        if self.tau_u_ev is not None:
            require_positive_finite(self.tau_u_ev, "tau_u_ev")
        if not isinstance(self.status, PlanStatus) or any(
            not isinstance(r, PlanReason) for r in self.reason_codes
        ):
            raise PerturbationPlanError("plan status and reasons must be enums")
        inv = freeze_inventory(self.inventory)
        object.__setattr__(self, "inventory", inv)
        # Canonical domain snapshot also normalizes protocol integer/float
        # representations before the digest is frozen.
        object.__setattr__(self, "coverage", CoverageQualification.from_mapping(self.coverage.to_mapping()))
        object.__setattr__(self, "reference", ReferenceEvidence.from_mapping(self.reference.to_mapping()))
        sites = tuple(s.site_id for s in inv.subspaces)
        index = {s: i for i, s in enumerate(sites)}
        if not (
            inv.effective_fdf_sha256
            == self.coverage.effective_fdf_sha256
            == self.reference.state.input_fdf_sha256
            == self.effective_fdf_sha256
        ):
            raise PerturbationPlanError("effective FDF evidence binding mismatch")
        if self.coverage.inventory_digest != inv.digest or self.coverage.reference != self.reference:
            raise PerturbationPlanError("coverage evidence binding mismatch")
        if self.source_fdf_sha256 != self.reference.input_file_sha256:
            raise PerturbationPlanError("source FDF evidence binding mismatch")
        if {s for c in self.coverage.classes for s in c.members} != set(sites):
            raise PerturbationPlanError("coverage must partition the inventory")
        if len(set(self.computed_columns)) != len(self.computed_columns) or not set(
            self.computed_columns
        ) <= set(sites):
            raise PerturbationPlanError("computed columns must be unique inventory sites")
        object.__setattr__(
            self, "computed_columns", tuple(sorted(self.computed_columns, key=index.__getitem__))
        )
        object.__setattr__(
            self,
            "calibration",
            tuple(
                sorted(
                    self.calibration, key=lambda c: (index[c.column_plan.site_id], c.column_plan.mode.value)
                )
            ),
        )
        object.__setattr__(
            self,
            "run_specs",
            tuple(sorted(self.run_specs, key=lambda s: (index[s.site_id], s.mode.value, s.alpha_ev))),
        )
        object.__setattr__(
            self,
            "reconstruction_maps",
            tuple(sorted(self.reconstruction_maps, key=lambda r: index[r.omitted_site_id])),
        )
        object.__setattr__(self, "reason_codes", tuple(sorted(set(self.reason_codes), key=lambda r: r.value)))
        keys = [(c.column_plan.site_id, c.column_plan.mode) for c in self.calibration]
        declared = {(c.site_id, c.mode): c for c in self.response_protocol.columns}
        if self.protocol_version != self.response_protocol.protocol_version or any(
            not isinstance(c.alpha_strategy, AlphaStrategy)
            or declared.get((c.column_plan.site_id, c.column_plan.mode)) != c.column_plan
            for c in self.calibration
        ):
            raise PerturbationPlanError("calibration must preserve the resolved protocol and version")
        expected = {(s, m) for s in self.computed_columns for m in ResponseMode}
        if len(keys) != len(set(keys)) or set(keys) != expected:
            raise PerturbationPlanError("calibration needs exactly both modes for each computed column")
        runs = tuple(s.identity for s in self.run_specs)
        expected_runs = {
            (c.column_plan.site_id, c.column_plan.mode, a)
            for c in self.calibration
            for magnitude in c.column_plan.amplitudes_ev
            for a in (-magnitude, magnitude)
        }
        if len(runs) != len(set(runs)) or set(runs) != expected_runs:
            raise PerturbationPlanError("run specs must match every resolved column amplitude exactly")
        maps = {r.omitted_site_id: r for r in self.reconstruction_maps}
        disabled_calibration = (
            self.status is PlanStatus.NOT_ESTABLISHED
            and PlanReason.CALIBRATION_NOT_ENABLED in self.reason_codes
        )
        omitted = set() if disabled_calibration else set(sites) - set(self.computed_columns)
        if disabled_calibration and (self.computed_columns or self.run_specs or self.calibration):
            raise PerturbationPlanError("disabled calibration cannot emit executable runs")
        if len(maps) != len(self.reconstruction_maps) or set(maps) != omitted:
            raise PerturbationPlanError("every omitted column requires exactly one reconstruction map")
        for site, entry in maps.items():
            group = next(c for c in self.coverage.classes if site in c.members)
            if (
                not group.reduced
                or entry.representative != group.representative
                or (site, entry.operation_id) not in group.ops_rep_to_member
            ):
                raise PerturbationPlanError("omitted column lacks a qualified coverage operation")
        if (
            self.status is PlanStatus.READY
            and self.reason_codes
            and set(self.reason_codes) != {PlanReason.DISABLED_OR_FIXED}
        ):
            raise PerturbationPlanError("READY cannot carry unresolved reason codes")
        if self.status is PlanStatus.READY and (
            inv.status is not InventoryStatus.OK
            or not sites
            or self.reference.status is not EvidenceStatus.ADMISSIBLE
            or self.reference.parent_dm_sha256 is None
            or not self.reference.input_output_consistent
            or self.reference.perturbation_detected
            or not self.reference.state.normal_completion_verified
            or not self.reference.state.scf_converged
            or any(c.status is CoverageStatus.CANDIDATE_PENDING_SHADOW for c in self.coverage.classes)
        ):
            raise PerturbationPlanError(
                "READY requires resolved inventory, admissible reference, parent DM and proven omissions"
            )

    @property
    def bands(self) -> dict[str, object]:
        return self.coverage.policy.to_mapping()

    @property
    def state_evidence_sha256(self) -> str:
        return sha256(
            json.dumps(
                asdict(self.reference.state), sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode()
        ).hexdigest()

    def to_mapping(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "source_fdf_sha256": self.source_fdf_sha256,
            "effective_fdf_sha256": self.effective_fdf_sha256,
            "inventory": inventory_mapping(self.inventory),
            "reference": {**self.reference.to_mapping(), "state_evidence_sha256": self.state_evidence_sha256},
            "coverage": self.coverage.to_mapping(),
            "response_protocol": self.response_protocol.to_mapping(),
            "calibration": [c.to_mapping() for c in self.calibration],
            "computed_columns": self.computed_columns,
            "run_specs": [s.to_mapping() for s in self.run_specs],
            "reconstruction_maps": [r.to_mapping() for r in self.reconstruction_maps],
            "protocol_version": self.protocol_version,
            "planner_version": self.planner_version,
            "backend_identity": self.backend_identity,
            "bands": self.bands,
            "tau_u_ev": self.tau_u_ev,
            "status": self.status.value,
            "reason_codes": [r.value for r in self.reason_codes],
        }

    @property
    def digest(self) -> str:
        return sha256(
            json.dumps(self.to_mapping(), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        ).hexdigest()

    @classmethod
    def from_mapping(cls, row: Mapping[str, object]) -> ResolvedPerturbationPlan:
        try:
            protocol = ResolvedResponseProtocol.from_mapping(
                cast(Mapping[str, object], row["response_protocol"])
            )
            calibration = tuple(
                ColumnCalibration.from_mapping(raw)
                for raw in cast(Sequence[Mapping[str, object]], row["calibration"])
            )
            result = cls(
                cast(str, row["schema"]),
                cast(str, row["source_fdf_sha256"]),
                cast(str, row["effective_fdf_sha256"]),
                inventory_from_mapping(cast(Mapping[str, object], row["inventory"])),
                ReferenceEvidence.from_mapping(cast(Mapping[str, object], row["reference"])),
                CoverageQualification.from_mapping(cast(Mapping[str, object], row["coverage"])),
                protocol,
                tuple(calibration),
                tuple(cast(Sequence[str], row["computed_columns"])),
                tuple(
                    RunSpec.from_mapping(r) for r in cast(Sequence[Mapping[str, object]], row["run_specs"])
                ),
                tuple(
                    ReconstructionMap.from_mapping(r)
                    for r in cast(Sequence[Mapping[str, object]], row["reconstruction_maps"])
                ),
                cast(str, row["protocol_version"]),
                cast(str, row["planner_version"]),
                cast(str, row["backend_identity"]),
                cast(float | None, row["tau_u_ev"]),
                PlanStatus(cast(str, row["status"])),
                tuple(PlanReason(r) for r in cast(Sequence[str], row["reason_codes"])),
            )
            if json.dumps(result.to_mapping(), sort_keys=True, allow_nan=False) != json.dumps(
                row, sort_keys=True, allow_nan=False
            ):
                raise PerturbationPlanError(
                    "serialized fields, bands or estimator weights disagree with the resolved evidence"
                )
            return result
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise PerturbationPlanError(f"invalid plan mapping: {exc}") from exc
