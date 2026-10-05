"""Product artifacts record planning states separately from production admission.

An immutable campaign identity binds the requested inputs and full TASK 12 plan.
Unavailable production evidence cannot be supplied by a user override.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from typing import TYPE_CHECKING, cast

from hubbardflow.domain.coverage_models import CoverageQualification
from hubbardflow.domain.perturbation_plan import PlanStatus
from hubbardflow.domain.perturbation_plan_evidence import (
    freeze_inventory,
    inventory_from_mapping,
    inventory_mapping,
)
from hubbardflow.domain.subspace_inventory import CorrelatedSubspaceInventory
from hubbardflow.domain.validation import require_sha256
from hubbardflow.execution.campaign_plan import CampaignPlanning

if TYPE_CHECKING:
    from hubbardflow.execution.campaign_split import CampaignSplitStaging

SCHEMA = "hubbardflow.product_plan.v1"
LOCK_SCHEMA = "hubbardflow.product_campaign_lock.v1"
RECEIPT_SCHEMA = "hubbardflow.product_execution_boundary.v1"


class ProductError(ValueError):
    """Product inputs or frozen provenance cannot support the requested action."""


class ProductReason(str, Enum):
    LR_CONFIG_REQUIRED = "LR_CONFIG_REQUIRED"
    SCIENTIFIC_STATE_NOT_ESTABLISHED = "SCIENTIFIC_STATE_NOT_ESTABLISHED"
    PILOT_REUSE_NOT_ESTABLISHED = "PILOT_REUSE_NOT_ESTABLISHED"
    CALIBRATED_VALIDATION_NOT_ESTABLISHED = "CALIBRATED_VALIDATION_NOT_ESTABLISHED"
    CALIBRATION_PROTOCOL_REQUIRED = "CALIBRATION_PROTOCOL_REQUIRED"
    STAGED_PENDING_GENERATED_IDENTITY = "STAGED_PENDING_GENERATED_IDENTITY"
    SHARED_LABEL_NEEDS_SPLIT = "SHARED_LABEL_NEEDS_SPLIT"
    PLAN_NOT_READY = "PLAN_NOT_READY"


class ProductCommand(str, Enum):
    PLAN = "plan"
    RUN = "run"
    REFERENCE = "reference"
    SUBMIT = "submit"


class DownstreamStatus(str, Enum):
    NOT_ASSESSED = "NOT_ASSESSED"


class V6ProtectionStatus(str, Enum):
    PROTECTED = "PROTECTED"
    NO_WORKSPACE_ON_PATH = "NO_WORKSPACE_ON_PATH"


def canonical(value: object) -> str:
    """Canonical JSON rejects nonfinite numbers rather than storing silent NaNs."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def json_object(text: str) -> dict[str, object]:
    try:
        value: object = json.loads(text)
        if not isinstance(value, dict):
            raise ProductError("expected a JSON object")
        canonical(value)
        return cast(dict[str, object], value)
    except (ValueError, TypeError) as exc:
        raise ProductError(f"invalid product JSON: {exc}") from exc


@dataclass(frozen=True)
class ProductSnapshot:
    request_json: str
    inventory: CorrelatedSubspaceInventory
    planning: CampaignPlanning | None
    config_digest: str | None
    source_fdf_sha256: str
    status: PlanStatus
    reasons: tuple[ProductReason, ...]
    detail: str
    diagnostic_coverage: CoverageQualification | None
    split_staging: CampaignSplitStaging | None = None
    frozen_lr_config_json: str | None = None
    input_sha256_json: str = "{}"

    def __post_init__(self) -> None:
        if self.split_staging is not None:
            from hubbardflow.execution.campaign_split import CampaignSplitStaging

            object.__setattr__(
                self, "split_staging", CampaignSplitStaging.from_mapping(self.split_staging.to_mapping())
            )
            if self.planning is not None or self.status is not PlanStatus.NOT_ESTABLISHED:
                raise ProductError("staged aliases cannot supply an executable plan")
        object.__setattr__(self, "request_json", canonical(json_object(self.request_json)))
        object.__setattr__(self, "inventory", freeze_inventory(self.inventory))
        if self.planning is not None:
            object.__setattr__(self, "planning", CampaignPlanning.from_mapping(self.planning.to_mapping()))
        if self.diagnostic_coverage is not None:
            object.__setattr__(
                self,
                "diagnostic_coverage",
                CoverageQualification.from_mapping(self.diagnostic_coverage.to_mapping()),
            )
        require_sha256(self.source_fdf_sha256, "source FDF")
        if self.config_digest is not None:
            require_sha256(self.config_digest, "planning config")
        if self.frozen_lr_config_json is not None:
            object.__setattr__(
                self, "frozen_lr_config_json", canonical(json_object(self.frozen_lr_config_json))
            )
        input_hashes = json_object(self.input_sha256_json)
        for path, digest in input_hashes.items():
            if not isinstance(path, str) or not isinstance(digest, str):
                raise ProductError("input SHA256 map must contain string paths and digests")
            require_sha256(digest, f"input {path}")
        object.__setattr__(self, "input_sha256_json", canonical(input_hashes))
        if not isinstance(self.status, PlanStatus) or any(
            not isinstance(r, ProductReason) for r in self.reasons
        ):
            raise ProductError("product states and reasons must be enums")
        object.__setattr__(self, "reasons", tuple(sorted(set(self.reasons), key=lambda r: r.value)))
        if self.planning is not None and (
            self.status is not self.planning.plan.status
            or self.inventory.digest != self.planning.plan.inventory.digest
            or self.source_fdf_sha256 != self.planning.plan.source_fdf_sha256
            or self.diagnostic_coverage != self.planning.diagnostic_coverage
        ):
            raise ProductError("product snapshot disagrees with the resolved plan")

    def to_mapping(self) -> dict[str, object]:
        result: dict[str, object] = {
            "schema": SCHEMA,
            "request": json_object(self.request_json),
            "inventory": inventory_mapping(self.inventory),
            "planning": None if self.planning is None else self.planning.to_mapping(),
            "planning_config_digest": self.config_digest,
            "source_fdf_sha256": self.source_fdf_sha256,
            "status": self.status.value,
            "reason_codes": [r.value for r in self.reasons],
            "detail": self.detail,
            "diagnostic_coverage": None
            if self.diagnostic_coverage is None
            else self.diagnostic_coverage.to_mapping(),
            "downstream_status": DownstreamStatus.NOT_ASSESSED.value,
        }
        if self.split_staging is not None:
            result["split_staging"] = self.split_staging.to_mapping()
        if self.frozen_lr_config_json is not None:
            result["frozen_lr_config"] = json_object(self.frozen_lr_config_json)
            result["frozen_lr_config_sha256"] = self.frozen_lr_config_sha256
        result["input_sha256"] = json_object(self.input_sha256_json)
        return result

    @classmethod
    def from_mapping(cls, row: Mapping[str, object]) -> ProductSnapshot:
        from hubbardflow.execution.campaign_split import CampaignSplitStaging

        if row.get("schema") != SCHEMA or row.get("downstream_status") != DownstreamStatus.NOT_ASSESSED.value:
            raise ProductError("unsupported product plan schema or downstream state")
        raw = row["planning"]
        snapshot = cls(
            canonical(row["request"]),
            inventory_from_mapping(cast(Mapping[str, object], row["inventory"])),
            None if raw is None else CampaignPlanning.from_mapping(cast(Mapping[str, object], raw)),
            cast(str | None, row["planning_config_digest"]),
            cast(str, row["source_fdf_sha256"]),
            PlanStatus(cast(str, row["status"])),
            tuple(ProductReason(r) for r in cast(list[str], row["reason_codes"])),
            cast(str, row["detail"]),
            None
            if row["diagnostic_coverage"] is None
            else CoverageQualification.from_mapping(cast(Mapping[str, object], row["diagnostic_coverage"])),
            None
            if "split_staging" not in row
            else CampaignSplitStaging.from_mapping(cast(Mapping[str, object], row["split_staging"])),
            None if row.get("frozen_lr_config") is None else canonical(row["frozen_lr_config"]),
            canonical(row.get("input_sha256", {})),
        )
        if row.get("frozen_lr_config_sha256") != snapshot.frozen_lr_config_sha256:
            raise ProductError("frozen lr-config digest disagrees with its stored bytes")
        return snapshot

    @property
    def frozen_lr_config_sha256(self) -> str | None:
        if self.frozen_lr_config_json is None:
            return None
        return sha256((self.frozen_lr_config_json + "\n").encode()).hexdigest()

    @property
    def campaign_identity(self) -> str:
        return sha256(canonical(self.to_mapping()).encode()).hexdigest()


@dataclass(frozen=True)
class ProductBoundary:
    command: ProductCommand
    campaign_identity: str
    plan_digest: str | None
    plan_status: PlanStatus
    reasons: tuple[ProductReason, ...]
    override_reason: str | None
    partition: str | None
    account: str | None
    v6_protection: V6ProtectionStatus = V6ProtectionStatus.PROTECTED
    execution_admission_json: str | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.command, ProductCommand)
            or self.command is ProductCommand.PLAN
            or not isinstance(self.plan_status, PlanStatus)
            or not isinstance(self.v6_protection, V6ProtectionStatus)
            or any(not isinstance(reason, ProductReason) for reason in self.reasons)
        ):
            raise ProductError("execution command, states and reasons must be enums")
        require_sha256(self.campaign_identity, "campaign identity")
        if self.plan_digest is not None:
            require_sha256(self.plan_digest, "plan digest")
        if self.override_reason is not None and not self.override_reason.strip():
            raise ProductError("override requires an explicit nonempty reason")
        if self.command is ProductCommand.SUBMIT and (self.partition is None or not self.partition.strip()):
            raise ProductError("submit requires a user-selected partition")
        if self.account is not None and not self.account.strip():
            raise ProductError("SLURM account must be a nonempty user choice")
        if self.execution_admission_json is not None:
            object.__setattr__(
                self,
                "execution_admission_json",
                canonical(json_object(self.execution_admission_json)),
            )

    def to_mapping(self) -> dict[str, object]:
        result: dict[str, object] = {
            "schema": RECEIPT_SCHEMA,
            "command": self.command.value,
            "campaign_identity": self.campaign_identity,
            "resolved_perturbation_plan_digest": self.plan_digest,
            "plan_status": self.plan_status.value,
            "status": PlanStatus.NOT_ESTABLISHED.value,
            "reason_codes": [r.value for r in self.reasons],
            "override_reason": self.override_reason,
            "partition": self.partition,
            "account": self.account,
            "v6_protection": self.v6_protection.value,
            "downstream_status": DownstreamStatus.NOT_ASSESSED.value,
        }
        if self.execution_admission_json is not None:
            result["execution_admission"] = json_object(self.execution_admission_json)
        return result

    @classmethod
    def from_mapping(cls, row: Mapping[str, object]) -> ProductBoundary:
        if (
            row.get("schema") != RECEIPT_SCHEMA
            or row.get("status") != PlanStatus.NOT_ESTABLISHED.value
            or row.get("downstream_status") != DownstreamStatus.NOT_ASSESSED.value
        ):
            raise ProductError("unsupported boundary receipt schema or status")
        return cls(
            ProductCommand(cast(str, row["command"])),
            cast(str, row["campaign_identity"]),
            cast(str | None, row["resolved_perturbation_plan_digest"]),
            PlanStatus(cast(str, row["plan_status"])),
            tuple(ProductReason(r) for r in cast(list[str], row["reason_codes"])),
            cast(str | None, row["override_reason"]),
            cast(str | None, row["partition"]),
            cast(str | None, row["account"]),
            V6ProtectionStatus(cast(str, row.get("v6_protection", V6ProtectionStatus.PROTECTED.value))),
            None if row.get("execution_admission") is None else canonical(row["execution_admission"]),
        )
