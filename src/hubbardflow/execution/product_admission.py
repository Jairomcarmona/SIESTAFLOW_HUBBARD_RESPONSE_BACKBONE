"""Decide whether a frozen direct fixed-grid product can use the legacy runner."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import cast

from hubbardflow.domain.subspace_inventory import InventoryStatus
from hubbardflow.execution.product_models import ProductSnapshot


class ExecutionAdmissionStatus(str, Enum):
    ADMISSIBLE_LEGACY_EQUIVALENT = "ADMISSIBLE_LEGACY_EQUIVALENT"
    BLOCKED = "BLOCKED"


class ExecutionAdmissionReason(str, Enum):
    FROZEN_PLAN_MISSING = "FROZEN_PLAN_MISSING"
    INVENTORY_NOT_READY = "INVENTORY_NOT_READY"
    GRID_NOT_EXPLICIT = "GRID_NOT_EXPLICIT"
    ADAPTIVE_POLICY_PRESENT = "ADAPTIVE_POLICY_PRESENT"
    REDUCED_COLUMNS_PRESENT = "REDUCED_COLUMNS_PRESENT"
    OPTIONAL_SYMMETRY_ENABLED = "OPTIONAL_SYMMETRY_ENABLED"
    SPLIT_STAGING_PENDING = "SPLIT_STAGING_PENDING"
    COVERAGE_POLICY_UNSUPPORTED = "COVERAGE_POLICY_UNSUPPORTED"
    SNAPSHOT_INCONSISTENT = "SNAPSHOT_INCONSISTENT"


class ExecutionRequirementStatus(str, Enum):
    REQUIRED_BY_PLAN = "REQUIRED_BY_PLAN"
    NOT_REQUIRED = "NOT_REQUIRED"
    COVERAGE_DIAGNOSTIC_ONLY = "COVERAGE_DIAGNOSTIC_ONLY"


@dataclass(frozen=True)
class ExecutionAdmission:
    """Typed execution boundary for plans that preserve legacy direct runs."""

    status: ExecutionAdmissionStatus
    reasons: tuple[ExecutionAdmissionReason, ...]
    scientific_state_requirement: ExecutionRequirementStatus
    pilot_reuse_requirement: ExecutionRequirementStatus
    reference_reason_handling: ExecutionRequirementStatus

    def to_mapping(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "reason_codes": [reason.value for reason in self.reasons],
            "scientific_state_requirement": self.scientific_state_requirement.value,
            "pilot_reuse_requirement": self.pilot_reuse_requirement.value,
            "reference_reason_handling": self.reference_reason_handling.value,
        }


def execution_admission(
    snapshot: ProductSnapshot, frozen_lr_config: Mapping[str, object] | None
) -> ExecutionAdmission:
    """Permit only explicit, unreduced fixed-grid plans with a verified frozen config.

    Missing reference/parent-DM state does not block this legacy-equivalent route;
    the plan retains those diagnostics, while reductions and calibrated execution
    continue to require their full scientific state evidence.
    """
    reasons: set[ExecutionAdmissionReason] = set()
    plan = None if snapshot.planning is None else snapshot.planning.plan
    if plan is None or frozen_lr_config is None:
        reasons.add(ExecutionAdmissionReason.FROZEN_PLAN_MISSING)
    if snapshot.inventory.status is not InventoryStatus.OK or not snapshot.inventory.subspaces:
        reasons.add(ExecutionAdmissionReason.INVENTORY_NOT_READY)
    if snapshot.split_staging is not None:
        reasons.add(ExecutionAdmissionReason.SPLIT_STAGING_PENDING)
    if frozen_lr_config is not None:
        grid = frozen_lr_config.get("alpha_grid_ev")
        if not isinstance(grid, list) or not grid:
            reasons.add(ExecutionAdmissionReason.GRID_NOT_EXPLICIT)
        if frozen_lr_config.get("adaptive_alpha_policy") is not None:
            reasons.add(ExecutionAdmissionReason.ADAPTIVE_POLICY_PRESENT)
        if frozen_lr_config.get("coverage", "DIAGNOSTIC") not in {"DISABLED", "DIAGNOSTIC"}:
            reasons.add(ExecutionAdmissionReason.COVERAGE_POLICY_UNSUPPORTED)
        if (
            frozen_lr_config.get("allow_spin_flip", False) is True
            or frozen_lr_config.get("allow_rotations", False) is True
            or frozen_lr_config.get("auto_split_species", False) is True
        ):
            reasons.add(ExecutionAdmissionReason.OPTIONAL_SYMMETRY_ENABLED)
    else:
        reasons.add(ExecutionAdmissionReason.GRID_NOT_EXPLICIT)
    if plan is not None:
        strategy = (
            None
            if frozen_lr_config is None
            else frozen_lr_config.get("alpha_strategy", "FIXED_PROTOCOL_GRID")
        )
        if strategy not in {"FIXED_PROTOCOL_GRID", "USER_EXPLICIT_GRID"}:
            reasons.add(ExecutionAdmissionReason.GRID_NOT_EXPLICIT)
        site_ids = {site.site_id for site in plan.inventory.subspaces}
        if (
            set(plan.computed_columns) != site_ids
            or plan.reconstruction_maps
            or any(group.reduced for group in plan.coverage.classes)
        ):
            reasons.add(ExecutionAdmissionReason.REDUCED_COLUMNS_PRESENT)
        if snapshot.inventory.digest != plan.inventory.digest or snapshot.status is not plan.status:
            reasons.add(ExecutionAdmissionReason.SNAPSHOT_INCONSISTENT)
        if frozen_lr_config is not None:
            configured_sites = frozen_lr_config.get("sites")
            configured_grid = frozen_lr_config.get("alpha_grid_ev")
            if (
                not isinstance(configured_sites, list)
                or not isinstance(configured_grid, list)
                or not configured_sites
            ):
                reasons.add(ExecutionAdmissionReason.GRID_NOT_EXPLICIT)
            else:
                declared_sites = {
                    (site.get("site_id"), site.get("atom_index"))
                    for site in configured_sites
                    if isinstance(site, Mapping)
                }
                inventory_sites = {
                    (site.species_label, site.atom_index + 1) for site in plan.inventory.subspaces
                }
                if declared_sites != inventory_sites:
                    reasons.add(ExecutionAdmissionReason.GRID_NOT_EXPLICIT)
                expected = {
                    (site, mode, float(alpha))
                    for site in plan.computed_columns
                    for mode in ("BARE", "SCREENED")
                    for alpha in cast(list[float], configured_grid)
                }
                actual = {(run.site_id, run.mode.value, run.alpha_ev) for run in plan.run_specs}
                if actual != expected:
                    reasons.add(ExecutionAdmissionReason.REDUCED_COLUMNS_PRESENT)
    ordered = tuple(sorted(reasons, key=lambda reason: reason.value))
    admissible = not ordered
    return ExecutionAdmission(
        ExecutionAdmissionStatus.ADMISSIBLE_LEGACY_EQUIVALENT
        if admissible
        else ExecutionAdmissionStatus.BLOCKED,
        ordered,
        ExecutionRequirementStatus.NOT_REQUIRED
        if admissible
        else ExecutionRequirementStatus.REQUIRED_BY_PLAN,
        ExecutionRequirementStatus.NOT_REQUIRED
        if admissible
        else ExecutionRequirementStatus.REQUIRED_BY_PLAN,
        ExecutionRequirementStatus.COVERAGE_DIAGNOSTIC_ONLY
        if admissible
        else ExecutionRequirementStatus.REQUIRED_BY_PLAN,
    )
