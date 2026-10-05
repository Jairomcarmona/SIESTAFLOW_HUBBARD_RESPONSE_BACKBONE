"""Truth table for the legacy-equivalent direct fixed-grid admission."""

from __future__ import annotations

import json
from dataclasses import replace
from types import SimpleNamespace
from typing import Any, cast

import pytest

from hubbardflow.domain.perturbation_plan import AlphaStrategy, PlanStatus
from hubbardflow.domain.perturbation_plan_evidence import ProjectorEvidence
from hubbardflow.domain.subspace_inventory import CorrelatedSubspace, InventoryReason, InventoryStatus
from hubbardflow.execution.product_admission import (
    ExecutionAdmissionReason,
    ExecutionAdmissionStatus,
    ExecutionRequirementStatus,
    execution_admission,
)
from hubbardflow.execution.product_models import ProductSnapshot


def _valid_case() -> tuple[ProductSnapshot, dict[str, object]]:
    projector = ProjectorEvidence("Co", "1", 3, 2, 0.0, 0.0, 3.0, 1.0, (), "Co 1 3 2 0 0 3 1")
    subspace = CorrelatedSubspace("Co@0:3:2", 0, "Co", 27, projector, "a" * 64)
    inventory = SimpleNamespace(
        status=InventoryStatus.OK,
        subspaces=(subspace,),
        digest="a" * 64,
        effective_fdf_sha256="b" * 64,
        reason_codes=(),
    )
    run_specs = tuple(
        SimpleNamespace(site_id=subspace.site_id, mode=SimpleNamespace(value=mode), alpha_ev=alpha)
        for mode in ("BARE", "SCREENED")
        for alpha in (-0.02, 0.02)
    )
    plan = SimpleNamespace(
        alpha_strategy=AlphaStrategy.FIXED_PROTOCOL_GRID,
        computed_columns=(subspace.site_id,),
        reconstruction_maps=(),
        coverage=SimpleNamespace(classes=(SimpleNamespace(reduced=False),)),
        inventory=inventory,
        run_specs=run_specs,
        status=PlanStatus.NOT_ESTABLISHED,
    )
    snapshot = SimpleNamespace(
        planning=SimpleNamespace(plan=plan),
        inventory=inventory,
        status=PlanStatus.NOT_ESTABLISHED,
        split_staging=None,
    )
    config: dict[str, object] = {
        "alpha_strategy": "FIXED_PROTOCOL_GRID",
        "alpha_grid_ev": [-0.02, 0.02],
        "adaptive_alpha_policy": None,
        "coverage": "DISABLED",
        "allow_spin_flip": False,
        "allow_rotations": False,
        "auto_split_species": False,
        "sites": [{"site_id": subspace.species_label, "atom_index": 1}],
    }
    return cast(ProductSnapshot, snapshot), config


def test_explicit_direct_fixed_grid_does_not_require_i5_or_pilot_reuse() -> None:
    snapshot, config = _valid_case()
    admission = execution_admission(snapshot, config)
    assert admission.status is ExecutionAdmissionStatus.ADMISSIBLE_LEGACY_EQUIVALENT
    assert admission.reasons == ()
    assert admission.scientific_state_requirement is ExecutionRequirementStatus.NOT_REQUIRED
    assert admission.pilot_reuse_requirement is ExecutionRequirementStatus.NOT_REQUIRED
    assert admission.reference_reason_handling is ExecutionRequirementStatus.COVERAGE_DIAGNOSTIC_ONLY


@pytest.mark.parametrize(
    ("reason_codes", "expected_status", "expected_reason"),
    [
        pytest.param(
            (InventoryReason.SPECIES_IDENTITY_NOT_ESTABLISHED,),
            ExecutionAdmissionStatus.ADMISSIBLE_LEGACY_EQUIVALENT,
            None,
            id="species-identity-only",
        ),
        pytest.param(
            (
                InventoryReason.SPECIES_IDENTITY_NOT_ESTABLISHED,
                InventoryReason.DFTU_LABEL_NO_ATOM,
            ),
            ExecutionAdmissionStatus.BLOCKED,
            ExecutionAdmissionReason.INVENTORY_NOT_READY,
            id="species-identity-and-label-no-atom",
        ),
        pytest.param(
            (InventoryReason.DFTU_LABEL_NO_ATOM,),
            ExecutionAdmissionStatus.BLOCKED,
            ExecutionAdmissionReason.INVENTORY_NOT_READY,
            id="label-no-atom-only",
        ),
        pytest.param(
            (),
            ExecutionAdmissionStatus.BLOCKED,
            ExecutionAdmissionReason.INVENTORY_NOT_READY,
            id="no-reason-codes",
        ),
    ],
)
def test_species_identity_only_inventory_allows_explicit_direct_plans(
    reason_codes: tuple[InventoryReason, ...],
    expected_status: ExecutionAdmissionStatus,
    expected_reason: ExecutionAdmissionReason | None,
) -> None:
    snapshot, config = _valid_case()
    inventory = SimpleNamespace(
        **{
            **snapshot.inventory.__dict__,
            "status": InventoryStatus.SUBSPACE_MAPPING_NOT_ESTABLISHED,
            "reason_codes": reason_codes,
        }
    )
    plan = SimpleNamespace(**{**cast(Any, snapshot.planning).plan.__dict__, "inventory": inventory})
    snapshot = cast(
        ProductSnapshot,
        SimpleNamespace(
            **{
                **snapshot.__dict__,
                "planning": SimpleNamespace(plan=plan),
                "inventory": inventory,
            }
        ),
    )

    admission = execution_admission(snapshot, config)

    assert admission.status is expected_status
    if expected_reason is None:
        assert admission.reasons == ()
    else:
        assert admission.reasons == (expected_reason,)


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ("missing_plan", ExecutionAdmissionReason.FROZEN_PLAN_MISSING),
        ("inventory", ExecutionAdmissionReason.INVENTORY_NOT_READY),
        ("grid", ExecutionAdmissionReason.GRID_NOT_EXPLICIT),
        ("adaptive", ExecutionAdmissionReason.ADAPTIVE_POLICY_PRESENT),
        ("reduced", ExecutionAdmissionReason.REDUCED_COLUMNS_PRESENT),
        ("symmetry", ExecutionAdmissionReason.OPTIONAL_SYMMETRY_ENABLED),
        ("split", ExecutionAdmissionReason.SPLIT_STAGING_PENDING),
        ("coverage", ExecutionAdmissionReason.COVERAGE_POLICY_UNSUPPORTED),
        ("snapshot", ExecutionAdmissionReason.SNAPSHOT_INCONSISTENT),
    ],
)
def test_each_admission_condition_fails_closed_alone(change: str, reason: ExecutionAdmissionReason) -> None:
    snapshot, config = _valid_case()
    if change == "missing_plan":
        snapshot = cast(ProductSnapshot, SimpleNamespace(**{**snapshot.__dict__, "planning": None}))
    elif change == "inventory":
        bad_inventory = SimpleNamespace(
            **{
                **snapshot.inventory.__dict__,
                "status": InventoryStatus.SUBSPACE_MAPPING_NOT_ESTABLISHED,
            }
        )
        snapshot = cast(ProductSnapshot, SimpleNamespace(**{**snapshot.__dict__, "inventory": bad_inventory}))
    elif change == "grid":
        config.pop("alpha_grid_ev")
    elif change == "adaptive":
        config["adaptive_alpha_policy"] = {"schema": "declared"}
    elif change == "reduced":
        plan = SimpleNamespace(**{**cast(Any, snapshot.planning).plan.__dict__, "computed_columns": ()})
        planning = SimpleNamespace(plan=plan)
        snapshot = cast(ProductSnapshot, SimpleNamespace(**{**snapshot.__dict__, "planning": planning}))
    elif change == "symmetry":
        config["allow_rotations"] = True
    elif change == "split":
        snapshot = cast(ProductSnapshot, SimpleNamespace(**{**snapshot.__dict__, "split_staging": object()}))
    elif change == "coverage":
        config["coverage"] = "UNSUPPORTED"
    elif change == "snapshot":
        bad_inventory = SimpleNamespace(
            **{
                **snapshot.inventory.__dict__,
                "subspaces": (replace(snapshot.inventory.subspaces[0], atomic_number=28),),
            }
        )
        snapshot = cast(ProductSnapshot, SimpleNamespace(**{**snapshot.__dict__, "inventory": bad_inventory}))
    result = execution_admission(snapshot, config)
    assert result.status is ExecutionAdmissionStatus.BLOCKED
    assert reason in result.reasons


def test_override_is_not_an_admission_input() -> None:
    snapshot, config = _valid_case()
    config["adaptive_alpha_policy"] = {"schema": "declared"}
    blocked = execution_admission(snapshot, config)
    assert blocked.status is ExecutionAdmissionStatus.BLOCKED
    # The policy input deliberately has no override field to grant admission.
    assert not hasattr(blocked, "override_plan_state")


def _translation_shadowed_case(tmp_path: Any) -> tuple[ProductSnapshot, dict[str, object]]:
    snapshot, config = _valid_case()
    fdf = tmp_path / "source.fdf"
    fdf.write_text("SystemLabel TS_PARENT\n", encoding="utf-8")
    site = snapshot.inventory.subspaces[0]
    plan = cast(Any, snapshot.planning).plan
    reference = SimpleNamespace(status=SimpleNamespace(value="ADMISSIBLE"), parent_dm_sha256="a" * 64)
    plan = SimpleNamespace(
        **{
            **plan.__dict__,
            "reference": reference,
            "reason_codes": (SimpleNamespace(value="SHADOW_PENDING"),),
            "coverage": SimpleNamespace(classes=(SimpleNamespace(reduced=True, shadow="Co@1:3:2"),)),
        }
    )
    snapshot = cast(
        ProductSnapshot,
        SimpleNamespace(
            **{
                **snapshot.__dict__,
                "planning": SimpleNamespace(plan=plan),
                "frozen_lr_config_json": "{}",
                "request_json": json.dumps({"fdf": str(fdf)}),
            }
        ),
    )
    config.update(
        coverage="TRANSLATION_SHADOWED",
        reference_dm_name="TS_PARENT.DM",
        sites=[{"site_id": site.species_label, "atom_index": site.atom_index + 1}],
    )
    return snapshot, config


def test_complete_translation_shadowed_plan_is_admissible(tmp_path: Any) -> None:
    snapshot, config = _translation_shadowed_case(tmp_path)
    admission = execution_admission(snapshot, config)
    assert admission.status is ExecutionAdmissionStatus.ADMISSIBLE_TRANSLATION_SHADOWED
    assert admission.reasons == ()


def test_missing_parent_dm_digest_is_not_an_admission_blocker(tmp_path: Any) -> None:
    snapshot, config = _translation_shadowed_case(tmp_path)
    plan = cast(Any, snapshot.planning).plan
    plan = SimpleNamespace(
        **{
            **vars(plan),
            "reference": SimpleNamespace(**{**vars(plan.reference), "parent_dm_sha256": None}),
        }
    )
    snapshot.planning = SimpleNamespace(**{**vars(snapshot.planning), "plan": plan})
    admission = execution_admission(snapshot, config)
    assert admission.status is ExecutionAdmissionStatus.ADMISSIBLE_TRANSLATION_SHADOWED
    assert admission.reasons == ()


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ("spin_flip", ExecutionAdmissionReason.OPTIONAL_SYMMETRY_ENABLED),
        ("adaptive", ExecutionAdmissionReason.ADAPTIVE_POLICY_PRESENT),
        ("plan_reason", ExecutionAdmissionReason.PLAN_REASONS_PRESENT),
        ("no_reduction", ExecutionAdmissionReason.NO_TRANSLATION_REDUCTION),
        ("dm_name", ExecutionAdmissionReason.REFERENCE_DM_NAME_MISMATCH),
    ],
)
def test_translation_shadowed_admission_fails_closed(
    tmp_path: Any, change: str, reason: ExecutionAdmissionReason
) -> None:
    snapshot, config = _translation_shadowed_case(tmp_path)
    if change == "spin_flip":
        config["allow_spin_flip"] = True
    elif change == "adaptive":
        config["adaptive_alpha_policy"] = {"schema": "declared"}
    elif change == "plan_reason":
        plan = cast(Any, snapshot.planning).plan
        plan = SimpleNamespace(**{**plan.__dict__, "reason_codes": (SimpleNamespace(value="OTHER"),)})
        snapshot = cast(
            ProductSnapshot, SimpleNamespace(**{**snapshot.__dict__, "planning": SimpleNamespace(plan=plan)})
        )
    elif change == "no_reduction":
        plan = cast(Any, snapshot.planning).plan
        plan = SimpleNamespace(
            **{
                **plan.__dict__,
                "coverage": SimpleNamespace(classes=(SimpleNamespace(reduced=False, shadow=None),)),
            }
        )
        snapshot = cast(
            ProductSnapshot, SimpleNamespace(**{**snapshot.__dict__, "planning": SimpleNamespace(plan=plan)})
        )
    elif change == "dm_name":
        config["reference_dm_name"] = "wrong.DM"
    admission = execution_admission(snapshot, config)
    assert admission.status is ExecutionAdmissionStatus.BLOCKED
    assert reason in admission.reasons


@pytest.mark.parametrize("digest", [None, "", "malformed", "c" * 64])
def test_inventory_digest_discrepancies_only_warn(digest):
    snapshot, config = _valid_case()
    changed = SimpleNamespace(**{**snapshot.inventory.__dict__, "digest": digest})
    snapshot = cast(ProductSnapshot, SimpleNamespace(**{**snapshot.__dict__, "inventory": changed}))
    result = execution_admission(snapshot, config)
    assert result.status is ExecutionAdmissionStatus.ADMISSIBLE_LEGACY_EQUIVALENT
    assert result.reasons == ()
    assert any(w.field == "digest" for w in result.traceability_warnings)
