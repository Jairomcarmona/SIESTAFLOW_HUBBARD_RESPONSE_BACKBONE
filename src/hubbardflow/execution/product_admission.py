"""Decide whether a frozen direct fixed-grid product can use the legacy runner."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import cast

from hubbardflow.domain.perturbation_plan import ResolvedPerturbationPlan
from hubbardflow.domain.subspace_inventory import InventoryReason, InventoryStatus
from hubbardflow.execution.product_models import ProductSnapshot


class ExecutionAdmissionStatus(str, Enum):
    ADMISSIBLE_LEGACY_EQUIVALENT = "ADMISSIBLE_LEGACY_EQUIVALENT"
    ADMISSIBLE_TRANSLATION_SHADOWED = "ADMISSIBLE_TRANSLATION_SHADOWED"
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
    PARENT_DM_REQUIRED = "PARENT_DM_REQUIRED"
    REFERENCE_NOT_ADMISSIBLE = "REFERENCE_NOT_ADMISSIBLE"
    PLAN_REASONS_PRESENT = "PLAN_REASONS_PRESENT"
    NO_TRANSLATION_REDUCTION = "NO_TRANSLATION_REDUCTION"
    REFERENCE_DM_NAME_MISMATCH = "REFERENCE_DM_NAME_MISMATCH"


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
    translation_shadowed = (
        frozen_lr_config is not None and frozen_lr_config.get("coverage") == "TRANSLATION_SHADOWED"
    )
    if translation_shadowed and frozen_lr_config is not None:
        return _translation_shadowed_admission(snapshot, frozen_lr_config, plan)
    if plan is None or frozen_lr_config is None:
        reasons.add(ExecutionAdmissionReason.FROZEN_PLAN_MISSING)
    # Species semantic identity is evidence for symmetry equivalence (F2) only.
    # A plan that perturbs every column directly needs the static label/atom
    # mapping, exactly as legacy init (``inventory_sites``) does.
    identity_only = snapshot.inventory.status is InventoryStatus.SUBSPACE_MAPPING_NOT_ESTABLISHED and set(
        getattr(snapshot.inventory, "reason_codes", ()) or ()
    ) == {InventoryReason.SPECIES_IDENTITY_NOT_ESTABLISHED}
    if (
        snapshot.inventory.status is not InventoryStatus.OK and not identity_only
    ) or not snapshot.inventory.subspaces:
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


def _translation_shadowed_admission(
    snapshot: ProductSnapshot,
    config: Mapping[str, object],
    plan: ResolvedPerturbationPlan | None,
) -> ExecutionAdmission:
    """Admit only a frozen, complete, parent-bound translation reduction.

    TS is a separate product route because every omitted column must have a
    measured shadow and a reproducible parent DM before the runner starts.
    """
    reasons: set[ExecutionAdmissionReason] = set()
    if plan is None or getattr(snapshot, "frozen_lr_config_json", None) is None:
        reasons.add(ExecutionAdmissionReason.FROZEN_PLAN_MISSING)
    if snapshot.inventory.status is not InventoryStatus.OK or not snapshot.inventory.subspaces:
        reasons.add(ExecutionAdmissionReason.INVENTORY_NOT_READY)
    if snapshot.split_staging is not None:
        reasons.add(ExecutionAdmissionReason.SPLIT_STAGING_PENDING)

    if config.get("adaptive_alpha_policy") is not None:
        reasons.add(ExecutionAdmissionReason.ADAPTIVE_POLICY_PRESENT)
    if config.get("alpha_strategy", "FIXED_PROTOCOL_GRID") not in {
        "FIXED_PROTOCOL_GRID",
        "USER_EXPLICIT_GRID",
    }:
        reasons.add(ExecutionAdmissionReason.GRID_NOT_EXPLICIT)
    if any(
        config.get(flag, False) is not False
        for flag in ("allow_spin_flip", "allow_rotations", "auto_split_species")
    ):
        reasons.add(ExecutionAdmissionReason.OPTIONAL_SYMMETRY_ENABLED)

    grid = config.get("alpha_grid_ev")
    if not isinstance(grid, list) or not grid:
        reasons.add(ExecutionAdmissionReason.GRID_NOT_EXPLICIT)
    if plan is not None:
        plan_inventory = plan.inventory
        if snapshot.inventory.digest != plan_inventory.digest or snapshot.status is not plan.status:
            reasons.add(ExecutionAdmissionReason.SNAPSHOT_INCONSISTENT)
        reference = getattr(plan, "reference", None)
        parent_dm_sha256 = getattr(reference, "parent_dm_sha256", None)
        reference_status = getattr(getattr(reference, "status", None), "value", None)
        if reference_status != "ADMISSIBLE" or not parent_dm_sha256:
            reasons.add(ExecutionAdmissionReason.REFERENCE_NOT_ADMISSIBLE)
        if not parent_dm_sha256:
            reasons.add(ExecutionAdmissionReason.PARENT_DM_REQUIRED)
        if not {reason.value for reason in plan.reason_codes} <= {"SHADOW_PENDING"}:
            reasons.add(ExecutionAdmissionReason.PLAN_REASONS_PRESENT)

        reduced = [group for group in plan.coverage.classes if group.reduced]
        if not reduced:
            reasons.add(ExecutionAdmissionReason.NO_TRANSLATION_REDUCTION)
        if any(group.shadow is None for group in reduced):
            reasons.add(ExecutionAdmissionReason.NO_TRANSLATION_REDUCTION)

        if not isinstance(grid, list) or not grid:
            reasons.add(ExecutionAdmissionReason.GRID_NOT_EXPLICIT)
        else:
            expected_runs = {
                (site, mode, float(alpha))
                for site in plan.computed_columns
                for mode in ("BARE", "SCREENED")
                for alpha in grid
            }
            actual_runs = {(run.site_id, run.mode.value, run.alpha_ev) for run in plan.run_specs}
            if actual_runs != expected_runs:
                reasons.add(ExecutionAdmissionReason.REDUCED_COLUMNS_PRESENT)

        configured_sites = config.get("sites")
        if not isinstance(configured_sites, list):
            reasons.add(ExecutionAdmissionReason.GRID_NOT_EXPLICIT)
        else:
            declared_sites = {
                (site.get("site_id"), site.get("atom_index"))
                for site in configured_sites
                if isinstance(site, Mapping)
            }
            inventory_sites = {(site.species_label, site.atom_index + 1) for site in plan_inventory.subspaces}
            if declared_sites != inventory_sites:
                reasons.add(ExecutionAdmissionReason.GRID_NOT_EXPLICIT)

        expected_dm_name = reference_dm_name_for_request(snapshot.request_json)
        if config.get("reference_dm_name") != expected_dm_name:
            reasons.add(ExecutionAdmissionReason.REFERENCE_DM_NAME_MISMATCH)

    ordered = tuple(sorted(reasons, key=lambda reason: reason.value))
    admissible = not ordered
    return ExecutionAdmission(
        ExecutionAdmissionStatus.ADMISSIBLE_TRANSLATION_SHADOWED
        if admissible
        else ExecutionAdmissionStatus.BLOCKED,
        ordered,
        ExecutionRequirementStatus.REQUIRED_BY_PLAN,
        ExecutionRequirementStatus.REQUIRED_BY_PLAN,
        ExecutionRequirementStatus.REQUIRED_BY_PLAN,
    )


def reference_dm_name_for_request(request_json: str) -> str:
    """Resolve the only valid reference DM name from a product request's FDF."""
    import json
    import re
    from pathlib import Path

    try:
        request = json.loads(request_json)
        fdf = Path(request["fdf"])
        from hubbardflow.execution.campaign_v2 import resolve_fdf_includes

        text, _ = resolve_fdf_includes(fdf)
    except (OSError, ValueError, TypeError, KeyError):
        return ""
    labels = [
        match.group(1)
        for line in text.splitlines()
        if (match := re.match(r"^\s*SystemLabel\s+([^\s#]+)", line, re.IGNORECASE))
    ]
    if len(labels) > 1:
        return ""
    return f"{labels[0]}.DM" if labels else "siesta.DM"
