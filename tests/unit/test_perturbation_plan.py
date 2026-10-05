"""Frozen plan serialization, evidence binding and malformed-input properties."""

from __future__ import annotations

import json
from dataclasses import replace
from typing import cast

import pytest
from hypothesis import given
from hypothesis import strategies as st

from hubbardflow.domain.coverage import CoverageQualification, UserCoveragePolicy, qualify_coverage
from hubbardflow.domain.perturbation_plan import AlphaStrategy, PlanStatus, ResolvedPerturbationPlan
from hubbardflow.domain.perturbation_plan_evidence import PerturbationPlanError
from hubbardflow.domain.perturbation_planner import resolve_perturbation_plan
from hubbardflow.domain.response_protocol import (
    EstimatorKind,
    PerturbationStrategy,
    ResolvedResponseProtocol,
    protocol_from_fixed_grid,
)
from hubbardflow.domain.subspace_inventory import CorrelatedSubspaceInventory
from hubbardflow.domain.symmetry_operation_models import coverage_policy_v1
from tests.unit.test_coverage import DIGEST, _toy


def inputs(
    *, enabled: bool = True, calibrated: bool = False
) -> tuple[CorrelatedSubspaceInventory, CoverageQualification, ResolvedResponseProtocol]:
    inv, ref, model = _toy(4)
    cov = qualify_coverage(inv, ref, model, coverage_policy_v1(), UserCoveragePolicy("test-v1", enabled, ()))
    protocol = protocol_from_fixed_grid(
        tuple(s.site_id for s in inv.subspaces),
        (-0.02, -0.01, 0.01, 0.02),
        estimator=EstimatorKind.LINEAR_LSQ,
        polynomial_degree=None,
        scf_level_id="declared-scf-v1",
        reference_node_id="reference",
        observable_id="siesta_occupations_total-v1",
        strategy=PerturbationStrategy.CALIBRATED if calibrated else PerturbationStrategy.FIXED_PROTOCOL_GRID,
        protocol_version="synthetic-v1",
    )
    return inv, cov, protocol


def plan(*, enabled: bool = True) -> ResolvedPerturbationPlan:
    return resolve_perturbation_plan(
        *inputs(enabled=enabled),
        source_fdf_sha256=DIGEST,
        alpha_strategy=AlphaStrategy.FIXED_PROTOCOL_GRID,
        planner_version="planner-v1",
        backend_identity="siesta-binary-sha256:" + DIGEST,
        tau_u_ev=None,
    )


def test_schema_roundtrip_and_full_evidence_not_certificate() -> None:
    original = plan()
    mapping = json.loads(json.dumps(original.to_mapping()))
    restored = ResolvedPerturbationPlan.from_mapping(mapping)
    assert restored == original
    assert restored.digest == original.digest
    assert restored.schema == "hubbardflow.resolved_perturbation_plan.v1"
    assert restored.calibration[0].qualification.status.value == "NOT_ASSESSED"
    assert restored.reference.parent_dm_sha256 == DIGEST
    assert mapping["bands"] == mapping["coverage"]["policy"]
    assert all(c["estimator_weights"] for c in mapping["calibration"])
    assert "certificate" not in mapping


@pytest.mark.parametrize(
    "field", ["source_fdf_sha256", "effective_fdf_sha256", "inventory", "bands", "estimator_weights"]
)
def test_tampered_serialized_provenance_rejected(field: str) -> None:
    mapping = json.loads(json.dumps(plan().to_mapping()))
    if field == "inventory":
        mapping[field]["digest"] = "0" * 64
    elif field == "bands":
        mapping[field]["version"] = "changed"
    elif field == "estimator_weights":
        mapping["calibration"][0][field][0][1] += 1
    else:
        mapping[field] = "0" * 64
    if field in {"source_fdf_sha256", "effective_fdf_sha256", "inventory"}:
        restored = ResolvedPerturbationPlan.from_mapping(mapping)
        assert restored.status is plan().status
        assert restored.traceability_warnings
        assert restored.run_specs == plan().run_specs
        assert restored.reconstruction_maps == plan().reconstruction_maps
    else:
        with pytest.raises(PerturbationPlanError):
            ResolvedPerturbationPlan.from_mapping(mapping)


@given(st.sampled_from((float("nan"), float("inf"), -float("inf"))))
def test_nonfinite_anywhere_in_frozen_plan_rejected(bad: float) -> None:
    original = plan(enabled=False)
    with pytest.raises(PerturbationPlanError):
        replace(original, tau_u_ev=bad)
    mapping = json.loads(json.dumps(original.to_mapping()))
    mapping["reference"]["state"]["moments_by_atom"][0]["moment_e"] = bad
    with pytest.raises(PerturbationPlanError):
        ResolvedPerturbationPlan.from_mapping(mapping)


def test_cannot_promote_candidate_to_ready_by_relabeling_plan() -> None:
    original = plan()
    with pytest.raises(PerturbationPlanError, match="proven omissions"):
        replace(original, status=PlanStatus.READY, reason_codes=())


def test_run_specs_and_reconstruction_must_be_complete() -> None:
    original = plan()
    with pytest.raises(PerturbationPlanError, match="run specs"):
        replace(original, run_specs=original.run_specs[1:])
    with pytest.raises(PerturbationPlanError, match="reconstruction map"):
        replace(original, reconstruction_maps=())
    mapping = cast(dict[str, object], json.loads(json.dumps(original.to_mapping())))
    mapping["unknown"] = True
    with pytest.raises(PerturbationPlanError):
        ResolvedPerturbationPlan.from_mapping(mapping)


@pytest.mark.parametrize("field", ["source_fdf_sha256", "effective_fdf_sha256"])
@pytest.mark.parametrize("value", [None, "", "malformed"])
def test_plan_file_hash_metadata_is_optional_warning(field, value):
    original = plan()
    mapping = json.loads(json.dumps(original.to_mapping()))
    if value is None:
        mapping.pop(field)
    else:
        mapping[field] = value
    restored = ResolvedPerturbationPlan.from_mapping(mapping)
    assert restored.status is original.status
    assert restored.run_specs == original.run_specs
    assert restored.reconstruction_maps == original.reconstruction_maps
    assert restored.traceability_warnings
    assert "traceability_warnings" in restored.to_mapping()
