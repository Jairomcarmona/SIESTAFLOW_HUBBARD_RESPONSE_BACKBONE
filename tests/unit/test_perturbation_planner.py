"""Deterministic fixed-grid reproduction and translation/shadow planning."""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from hubbardflow.domain.coverage import (
    CoverageClass,
    CoverageQualification,
    CoverageReason,
    CoverageStatus,
    CoverageStrategy,
    UserCoveragePolicy,
)
from hubbardflow.domain.perturbation_plan import AlphaStrategy, PlanReason, PlanStatus
from hubbardflow.domain.perturbation_plan_evidence import PerturbationPlanError
from hubbardflow.domain.perturbation_planner import resolve_perturbation_plan
from hubbardflow.domain.response_protocol import EstimatorKind, protocol_from_fixed_grid
from hubbardflow.domain.state_evidence import EvidenceStatus
from hubbardflow.domain.subspace_inventory import build_inventory
from hubbardflow.execution.campaign_runner import _build_dag
from hubbardflow.execution.campaign_v2 import resolve_fdf_includes, validate_reference_fdf
from hubbardflow.siesta_backend.fdf_model import parse_effective_fdf, species_identity
from tests.unit.test_coverage import DIGEST
from tests.unit.test_perturbation_plan import inputs, plan

ROOT = Path(__file__).resolve().parents[2]


def test_translation_candidates_keep_mandatory_shadow_and_review() -> None:
    resolved = plan()
    assert resolved.coverage.strategy is CoverageStrategy.SYMMETRY_REDUCED
    assert resolved.computed_columns == ("s0", "s1")
    assert resolved.status is PlanStatus.REVIEW
    assert resolved.reason_codes == (PlanReason.SHADOW_PENDING,)
    assert {r.omitted_site_id for r in resolved.reconstruction_maps} == {"s2", "s3"}
    assert len(resolved.run_specs) == 16


def test_disabled_default_all_subspaces_ready_with_complete_evidence() -> None:
    resolved = plan(enabled=False)
    assert resolved.coverage.strategy is CoverageStrategy.ALL_SUBSPACES
    assert resolved.computed_columns == ("s0", "s1", "s2", "s3")
    assert resolved.status is PlanStatus.READY
    assert not resolved.reconstruction_maps
    assert len(resolved.run_specs) == 32


def test_proven_translation_may_be_ready_but_retains_direct_shadow() -> None:
    inv, cov, protocol = inputs()
    cov = replace(cov, classes=tuple(replace(c, status=CoverageStatus.PROVEN) for c in cov.classes))
    resolved = resolve_perturbation_plan(
        inv,
        cov,
        protocol,
        source_fdf_sha256=DIGEST,
        alpha_strategy=AlphaStrategy.FIXED_PROTOCOL_GRID,
        planner_version="v1",
        backend_identity="declared",
        tau_u_ev=None,
    )
    assert resolved.status is PlanStatus.READY
    assert resolved.computed_columns == ("s0", "s1")


def test_shadow_inherits_representative_grid_estimator_and_scf_level() -> None:
    inv, cov, protocol = inputs()
    protocol = replace(
        protocol,
        columns=tuple(
            replace(c, scf_level_id="independent-shadow-input") if c.site_id == "s1" else c
            for c in protocol.columns
        ),
    )
    resolved = resolve_perturbation_plan(
        inv,
        cov,
        protocol,
        source_fdf_sha256=DIGEST,
        alpha_strategy=AlphaStrategy.FIXED_PROTOCOL_GRID,
        planner_version="v1",
        backend_identity="declared",
        tau_u_ev=None,
    )
    columns = {(c.column_plan.site_id, c.column_plan.mode): c.column_plan for c in resolved.calibration}
    for mode in {c.mode for c in protocol.columns}:
        assert columns[("s1", mode)] == replace(columns[("s0", mode)], site_id="s1")


def test_user_explicit_grid_executes_without_reselecting_estimator() -> None:
    inv, cov, protocol = inputs(enabled=False)
    from hubbardflow.domain.response_protocol import PerturbationStrategy

    protocol = replace(protocol, strategy=PerturbationStrategy.USER_EXPLICIT_GRID)
    resolved = resolve_perturbation_plan(
        inv,
        cov,
        protocol,
        source_fdf_sha256=DIGEST,
        alpha_strategy=AlphaStrategy.USER_EXPLICIT_GRID,
        planner_version="v1",
        backend_identity="declared",
        tau_u_ev=None,
    )
    assert resolved.status is PlanStatus.READY
    assert all(c.alpha_strategy is AlphaStrategy.USER_EXPLICIT_GRID for c in resolved.calibration)
    assert {r.alpha_ev for r in resolved.run_specs} == {-0.02, -0.01, 0.01, 0.02}


def test_changing_parent_dm_or_bands_changes_plan_digest() -> None:
    inv, cov, protocol = inputs(enabled=False)
    original = plan(enabled=False)
    for changed in (
        replace(cov, reference=replace(cov.reference, parent_dm_sha256="0" * 64)),
        replace(cov, policy=replace(cov.policy, version="different-declared-bands-v2")),
    ):
        resolved = resolve_perturbation_plan(
            inv,
            changed,
            protocol,
            source_fdf_sha256=DIGEST,
            alpha_strategy=AlphaStrategy.FIXED_PROTOCOL_GRID,
            planner_version="planner-v1",
            backend_identity="siesta-binary-sha256:" + DIGEST,
            tau_u_ev=None,
        )
        assert resolved.digest != original.digest


def test_calibrated_grid_is_explicitly_disabled_without_executable_runs() -> None:
    resolved = resolve_perturbation_plan(
        *inputs(calibrated=True),
        source_fdf_sha256=DIGEST,
        alpha_strategy=AlphaStrategy.CALIBRATED_GRID,
        planner_version="v1",
        backend_identity="declared",
        tau_u_ev=0.02,
    )
    assert resolved.status is PlanStatus.NOT_ESTABLISHED
    assert PlanReason.CALIBRATION_NOT_ENABLED in resolved.reason_codes
    assert not resolved.run_specs and not resolved.computed_columns and not resolved.calibration


@pytest.mark.parametrize("cause", ["parent", "reference"])
def test_missing_reference_evidence_never_promotes_ready(cause: str) -> None:
    inv, cov, protocol = inputs(enabled=False)
    ref = (
        replace(cov.reference, parent_dm_sha256=None)
        if cause == "parent"
        else replace(cov.reference, status=EvidenceStatus.REFERENCE_NOT_ADMISSIBLE)
    )
    resolved = resolve_perturbation_plan(
        inv,
        replace(cov, reference=ref),
        protocol,
        source_fdf_sha256=DIGEST,
        alpha_strategy=AlphaStrategy.FIXED_PROTOCOL_GRID,
        planner_version="v1",
        backend_identity="declared",
        tau_u_ev=None,
    )
    assert resolved.status is PlanStatus.NOT_ESTABLISHED
    assert len(resolved.run_specs) == 32


@settings(max_examples=24, deadline=None)
@given(st.permutations((0, 1, 2, 3)))
def test_digest_invariant_to_inventory_protocol_and_explicit_target_order(order: list[int]) -> None:
    inv, cov, protocol = inputs(enabled=False)
    first = plan(enabled=False)
    inv = replace(inv, subspaces=tuple(inv.subspaces[i] for i in order))
    protocol = replace(protocol, columns=tuple(reversed(protocol.columns)))
    resolved = resolve_perturbation_plan(
        inv,
        cov,
        protocol,
        source_fdf_sha256=DIGEST,
        alpha_strategy=AlphaStrategy.FIXED_PROTOCOL_GRID,
        planner_version="planner-v1",
        backend_identity="siesta-binary-sha256:" + DIGEST,
        tau_u_ev=None,
    )
    assert first.digest == resolved.digest
    a = resolve_perturbation_plan(
        inv,
        cov,
        protocol,
        source_fdf_sha256=DIGEST,
        alpha_strategy=AlphaStrategy.FIXED_PROTOCOL_GRID,
        planner_version="v1",
        backend_identity="declared",
        tau_u_ev=None,
        explicit_sites=tuple(f"s{i}" for i in order),
    )
    b = resolve_perturbation_plan(
        inv,
        cov,
        protocol,
        source_fdf_sha256=DIGEST,
        alpha_strategy=AlphaStrategy.FIXED_PROTOCOL_GRID,
        planner_version="v1",
        backend_identity="declared",
        tau_u_ev=None,
        explicit_sites=("s0", "s1", "s2", "s3"),
    )
    assert a.digest == b.digest


@pytest.mark.parametrize(
    "source",
    [
        "benchmarks/lr_u/CoO/reference.fdf",
        "benchmarks/lr_u/stage_u_b/materials/NiO/reference.fdf",
        "campaigns/mno_afmii_strict_lr_v3r2/results/response-matrix-foreground-recovery-v4/00_REFERENCE/siesta.fdf",
        "tests/fixtures/cu3n_reference_siesta.fdf",
    ],
)
def test_archived_fixed_run_specs_identical_to_current_campaign(source: str) -> None:
    path = ROOT / source
    before = sha256(path.read_bytes()).hexdigest()
    model = parse_effective_fdf(path)
    inv = build_inventory(model, species_identity(model, (path.parent,)))
    text, _ = resolve_fdf_includes(path)
    _, _, labels = validate_reference_fdf(text, "PBE")
    assert set(labels) == {s.species_label for s in inv.subspaces}
    # Campaign names use unique species labels; inventory identifiers additionally bind projector/atom.
    campaign_sites = [{"site_id": s.species_label, "atom_index": s.atom_index + 1} for s in inv.subspaces]
    grid = (-0.06, -0.04, -0.02, 0.02, 0.04, 0.06)
    _, existing = _build_dag(campaign_sites, list(grid))
    _, synthetic_cov, _ = inputs(enabled=False)
    reference = replace(
        synthetic_cov.reference,
        input_file_sha256=before,
        state=replace(synthetic_cov.reference.state, input_fdf_sha256=inv.effective_fdf_sha256),
        status=EvidenceStatus.REFERENCE_NOT_ADMISSIBLE,
        parent_dm_sha256=None,
    )
    cov = CoverageQualification(
        inv.digest,
        inv.effective_fdf_sha256,
        reference,
        synthetic_cov.policy,
        UserCoveragePolicy("golden-disabled-v1", False, ()),
        (),
        tuple(
            CoverageClass(
                (s.site_id,),
                s.site_id,
                None,
                (),
                CoverageStatus.DISABLED,
                (CoverageReason.DISABLED_OR_FIXED,),
            )
            for s in inv.subspaces
        ),
        CoverageStrategy.ALL_SUBSPACES,
        (CoverageReason.DISABLED_OR_FIXED,),
        (),
        len(inv.subspaces),
        (),
    )
    protocol = protocol_from_fixed_grid(
        tuple(s.site_id for s in inv.subspaces),
        grid,
        estimator=EstimatorKind.POLYNOMIAL_LSQ,
        polynomial_degree=3,
        scf_level_id="archived-declared",
        reference_node_id="reference",
        observable_id="siesta_occupations_total",
        protocol_version="v6-fixed",
    )
    resolved = resolve_perturbation_plan(
        inv,
        cov,
        protocol,
        source_fdf_sha256=before,
        alpha_strategy=AlphaStrategy.FIXED_PROTOCOL_GRID,
        planner_version="v1",
        backend_identity="golden",
        tau_u_ev=None,
        explicit_sites=tuple(s.site_id for s in inv.subspaces),
    )
    names = {s.site_id: s.species_label for s in inv.subspaces}
    assert {(names[s.site_id], s.mode, s.alpha_ev) for s in resolved.run_specs} == {
        (s.site_id, s.mode, s.alpha_ev) for s in existing.values()
    }
    assert all(c.column_plan.estimator.polynomial_degree == 3 for c in resolved.calibration)
    assert resolved.status is PlanStatus.NOT_ESTABLISHED  # absent reference provenance is not fabricated
    assert sha256(path.read_bytes()).hexdigest() == before


def test_partial_explicit_target_list_is_rejected() -> None:
    with pytest.raises(PerturbationPlanError, match="whole inventory"):
        resolve_perturbation_plan(
            *inputs(),
            source_fdf_sha256=DIGEST,
            alpha_strategy=AlphaStrategy.FIXED_PROTOCOL_GRID,
            planner_version="v1",
            backend_identity="declared",
            tau_u_ev=None,
            explicit_sites=("s0",),
        )
