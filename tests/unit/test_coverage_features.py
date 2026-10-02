"""TASK18 opt-ins, frozen provenance and additive rotation-shadow failures.

Synthetic state oracles exercise wiring only; they are not prospective V2.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from hubbardflow.domain.coverage import UserCoveragePolicy, qualify_coverage
from hubbardflow.domain.coverage_models import CoverageQualification, CoverageStatus
from hubbardflow.domain.perturbation_plan import (
    AlphaStrategy,
    EggBoxQuantification,
    PlanReason,
    PlanStatus,
    ReconstructionMap,
    ResolvedPerturbationPlan,
)
from hubbardflow.domain.perturbation_plan_evidence import PerturbationPlanError
from hubbardflow.domain.perturbation_planner import resolve_perturbation_plan
from hubbardflow.domain.response_shadow import (
    ResponseShadowError,
    ShadowReason,
    qualify_shadows,
    reconstruction_classes,
)
from hubbardflow.domain.symmetry_operation_models import (
    ExactnessClass,
    Operation,
    Rotation,
    coverage_policy_v1,
)
from hubbardflow.domain.symmetry_operations import CandidateOperations
from hubbardflow.execution.campaign_plan import (
    CampaignPlanError,
    freeze_campaign_plan,
    resolve_campaign_planning,
    verify_frozen_campaign_plan,
)
from hubbardflow.execution.campaign_shadow_inputs import observation_series
from hubbardflow.execution.campaign_v2 import CampaignV2Error, load_campaign_v2
from hubbardflow.execution.wsl_campaign_init import initialize_campaign
from tests.unit.test_campaign_plan import inputs, normalized
from tests.unit.test_campaign_shadow import _analysis, _observations, _plan, _runner
from tests.unit.test_coverage import DIGEST, _toy
from tests.unit.test_perturbation_plan import plan


@pytest.mark.parametrize("flag", ["allow_spin_flip", "allow_rotations"])
@pytest.mark.parametrize("nested", [False, True])
def test_config_to_plan_flags_digest_and_resume(tmp_path: Path, flag: str, nested: bool) -> None:
    fdf, raw, _ = inputs(tmp_path)
    off_config = normalized(fdf, raw)
    assert off_config["allow_spin_flip"] is off_config["allow_rotations"] is False
    off = resolve_campaign_planning(fdf, off_config)
    if nested:
        raw["coverage_policy"] = replace(
            coverage_policy_v1(),
            allow_spin_flip=flag == "allow_spin_flip",
            allow_rotations=flag == "allow_rotations",
        ).to_mapping()
    else:
        raw[flag] = True
    on_config = normalized(fdf, raw)
    on = resolve_campaign_planning(fdf, on_config)
    assert on_config[flag] is True
    assert getattr(on.plan.coverage.policy, flag) is True
    assert getattr(on.diagnostic_coverage.policy, flag) is True
    assert on.plan.status is off.plan.status is PlanStatus.NOT_ESTABLISHED
    assert on.plan.digest != off.plan.digest
    assert on.plan.coverage.policy.digest != off.plan.coverage.policy.digest
    assert on.plan.egg_box_quantification is EggBoxQuantification.NOT_QUANTIFIED
    freeze_campaign_plan(tmp_path, on, on_config)
    assert verify_frozen_campaign_plan(tmp_path, on_config) == on.plan
    with pytest.raises(CampaignPlanError, match="invalidated"):
        verify_frozen_campaign_plan(tmp_path, off_config)


@pytest.mark.parametrize("flag", ["allow_spin_flip", "allow_rotations"])
@given(st.one_of(st.integers(), st.text(), st.none()))
def test_flag_must_be_boolean(flag: str, value: object) -> None:
    from hubbardflow.execution.campaign_coverage_policy import (
        CampaignCoveragePolicyError,
        campaign_coverage_policy,
    )

    with pytest.raises(CampaignCoveragePolicyError, match="boolean"):
        campaign_coverage_policy({flag: value})


def test_conflicting_nested_and_top_level_flags_rejected(tmp_path: Path) -> None:
    fdf, raw, _ = inputs(tmp_path)
    with pytest.raises(CampaignV2Error, match="conflicts"):
        normalized(
            fdf,
            {**raw, "allow_rotations": True, "coverage_policy": coverage_policy_v1().to_mapping()},
        )


@pytest.mark.parametrize("flag", ["allow_spin_flip", "allow_rotations"])
@pytest.mark.parametrize("enabled", [False, True])
def test_portable_campaign_materialization_preserves_policy_flag(
    tmp_path: Path, flag: str, enabled: bool
) -> None:
    fdf, raw, profile = inputs(tmp_path / "inputs")
    raw[flag] = enabled
    config_path = fdf.parent / "lr.json"
    config_path.write_text(json.dumps(raw), encoding="utf-8")
    result = initialize_campaign(
        fdf_path=str(fdf),
        lr_config_path=str(config_path),
        profile_path=str(profile),
        name="task18-flags",
        campaign_root=str(tmp_path / "campaigns"),
    )
    manifest = load_campaign_v2(result["manifest_path"])
    root = Path(manifest["_campaign_root"])
    stored = json.loads((root / "lr_config.json").read_text(encoding="utf-8"))
    config = normalized(root / "reference.fdf", stored)
    frozen = verify_frozen_campaign_plan(root, config)
    assert config[flag] is enabled
    assert getattr(frozen.coverage.policy, flag) is enabled
    assert frozen.status is PlanStatus.NOT_ESTABLISHED
    assert frozen.egg_box_quantification is EggBoxQuantification.NOT_QUANTIFIED


def _resolved(coverage: CoverageQualification) -> ResolvedPerturbationPlan:
    base = _plan(len(coverage.reference.state.occupation_spectra_by_subspace))
    return resolve_perturbation_plan(
        base.inventory,
        coverage,
        base.response_protocol,
        source_fdf_sha256=DIGEST,
        alpha_strategy=AlphaStrategy.FIXED_PROTOCOL_GRID,
        planner_version="synthetic-task18-v1",
        backend_identity="synthetic-test",
        tau_u_ev=None,
    )


def test_mno_spin_flip_candidate_is_not_automatically_admitted() -> None:
    inventory, reference, model = _toy(16, antiferromagnet=True)
    off = qualify_coverage(
        inventory, reference, model, coverage_policy_v1(), UserCoveragePolicy("test-v1", True, ())
    )
    on = qualify_coverage(
        inventory,
        reference,
        model,
        replace(coverage_policy_v1(), allow_spin_flip=True),
        UserCoveragePolicy("test-v1", True, ()),
    )
    assert off.would_reduce_to == 2 and on.would_reduce_to == 1
    assert all(c.status is CoverageStatus.CANDIDATE_PENDING_SHADOW for c in on.classes)
    resolved = _resolved(on)
    assert resolved.status is PlanStatus.REVIEW
    assert PlanReason.FEATURES_NOT_ENABLED in resolved.reason_codes
    assert resolved.computed_columns == tuple(f"s{i}" for i in range(16))
    assert not resolved.reconstruction_maps
    assert all(c.status is CoverageStatus.REJECTED_EXPANDED for c in resolved.coverage.classes)
    with pytest.raises(PerturbationPlanError, match="READY"):
        replace(resolved, status=PlanStatus.READY, reason_codes=())


def test_coo_like_two_site_candidate_retains_no_saving_fallback() -> None:
    inventory, reference, model = _toy(2, antiferromagnet=True)
    coverage = qualify_coverage(
        inventory,
        reference,
        model,
        replace(coverage_policy_v1(), allow_spin_flip=True),
        UserCoveragePolicy("synthetic-coo-v1", True, ()),
    )
    assert coverage.would_reduce_to == 1
    assert coverage.computed_columns == ("s0", "s1")
    assert coverage.classes[0].status is CoverageStatus.REJECTED_EXPANDED
    assert tuple(r.value for r in coverage.classes[0].reasons) == ("NO_SAVING",)
    assert _resolved(coverage).status is PlanStatus.REVIEW


def _rotation_candidate(monkeypatch: pytest.MonkeyPatch) -> CoverageQualification:
    inventory, reference, model = _toy(4)
    coords = ((0.25, 0.0, 0.0), (0.0, 0.25, 0.0), (0.75, 0.0, 0.0), (0.0, 0.75, 0.0))
    model = replace(
        model,
        lattice_vectors_angstrom=((1.0, 0, 0), (0, 1.0, 0), (0, 0, 1.0)),
        atoms=tuple(replace(a, coordinates_fractional=coords[a.atom_index]) for a in model.atoms),
    )
    rotations: tuple[Rotation, ...] = (
        ((1, 0, 0), (0, 1, 0), (0, 0, 1)),
        ((0, -1, 0), (1, 0, 0), (0, 0, 1)),
        ((-1, 0, 0), (0, -1, 0), (0, 0, 1)),
        ((0, 1, 0), (-1, 0, 0), (0, 0, 1)),
    )
    operations = tuple(
        Operation(
            r, (0, 0, 0), 1, tuple((i + k) % 4 for i in range(4)), tuple((i + k) % 4 for i in range(4)), model
        )
        for k, r in enumerate(rotations)
    )
    monkeypatch.setattr(
        "hubbardflow.domain.coverage.candidate_operations",
        lambda *_: CandidateOperations(operations, ()),
    )
    return qualify_coverage(
        inventory,
        reference,
        model,
        replace(coverage_policy_v1(), allow_rotations=True),
        UserCoveragePolicy("synthetic-task18-v1", True, ()),
    )


def _laboratory_plan(coverage: CoverageQualification) -> ResolvedPerturbationPlan:
    """Inject candidates to test the shadow barrier without production admission."""
    expanded = _resolved(coverage)
    computed = coverage.computed_columns
    return replace(
        expanded,
        coverage=coverage,
        computed_columns=computed,
        calibration=tuple(c for c in expanded.calibration if c.column_plan.site_id in computed),
        run_specs=tuple(r for r in expanded.run_specs if r.site_id in computed),
        reconstruction_maps=tuple(
            ReconstructionMap(s, c.representative, i)
            for c in coverage.classes
            for s, i in c.ops_rep_to_member
            if s not in computed
        ),
    )


def test_spin_swap_shadow_correct_scalar_permutation_cannot_promote_from_opt_in() -> None:
    inventory, reference, model = _toy(4, antiferromagnet=True)
    coverage = qualify_coverage(
        inventory,
        reference,
        model,
        replace(coverage_policy_v1(), allow_spin_flip=True),
        UserCoveragePolicy("synthetic-spin-swap-v1", True, ()),
    )
    candidate = _laboratory_plan(coverage)
    observations, widths = _observations(candidate, {0, 1})
    series = observation_series(candidate, observations, widths, [5e-8] * 4)
    outcomes = qualify_shadows(candidate, series, scientific_state_valid=True)
    assert all(c.passed for c in outcomes[0].comparisons)
    assert outcomes[0].reason is ShadowReason.FEATURE_VALIDATION_NOT_ESTABLISHED
    assert outcomes[0].status is CoverageStatus.REJECTED_EXPANDED
    forged = replace(outcomes[0], status=CoverageStatus.PROVEN, reason=ShadowReason.WITHIN_PRINT_BOUNDS)
    with pytest.raises(ResponseShadowError, match="prospective validation"):
        reconstruction_classes(candidate, (forged,))


@pytest.mark.parametrize("egg_box_failure", [False, True])
def test_rotation_shadow_additive_bounds_and_whole_class_expansion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, egg_box_failure: bool
) -> None:
    coverage = _rotation_candidate(monkeypatch)
    assert coverage.would_reduce_to == 1
    assert coverage.classes[0].shadow is not None
    assert any(
        c.operation.exactness_class is ExactnessClass.EXACT_IN_CONTINUUM_ONLY for c in coverage.operations
    )
    expanded = _resolved(coverage)
    assert expanded.computed_columns == ("s0", "s1", "s2", "s3")
    assert expanded.status is PlanStatus.REVIEW
    candidate = _laboratory_plan(coverage)
    runner, executed, heartbeat = _runner(tmp_path, monkeypatch, candidate, fail=egg_box_failure)
    assert runner.advance("run", heartbeat) == 0
    assert len(executed) == 33
    assert runner.shadow is not None and runner.shadow.expanded == ("s0", "s1", "s2", "s3")
    outcome = _analysis(tmp_path)["response_observation_dataset"]["translation_shadow"]["outcomes"][0]
    assert outcome["status"] == "REJECTED_EXPANDED"
    assert outcome["reason"] == (
        "OUTSIDE_PRINT_BOUNDS" if egg_box_failure else "FEATURE_VALIDATION_NOT_ESTABLISHED"
    )
    assert len(outcome["comparisons"]) == 8
    explicit_dir = tmp_path / "explicit"
    explicit, _, explicit_heartbeat = _runner(
        explicit_dir, monkeypatch, candidate, fail=egg_box_failure, coverage="DISABLED"
    )
    assert explicit.advance("run", explicit_heartbeat) == 0
    assert _analysis(tmp_path)["primary"] == _analysis(explicit_dir)["primary"]
    for row in outcome["comparisons"]:
        within = abs(row["direct_e_per_ev"] - row["reconstructed_e_per_ev"]) <= (
            row["direct_bound_e_per_ev"] + row["representative_bound_e_per_ev"]
        )
        if not egg_box_failure:
            assert within


def test_egg_box_roundtrip_legacy_v1_and_fabricated_quantification_rejection() -> None:
    original = plan()
    row = json.loads(json.dumps(original.to_mapping()))
    assert row["egg_box_quantification"] == "NOT_QUANTIFIED"
    assert ResolvedPerturbationPlan.from_mapping(row) == original
    legacy = dict(row)
    del legacy["egg_box_quantification"]
    assert (
        ResolvedPerturbationPlan.from_mapping(legacy).egg_box_quantification
        is EggBoxQuantification.NOT_QUANTIFIED
    )
    row["egg_box_quantification"] = "QUANTIFIED"
    with pytest.raises(PerturbationPlanError):
        ResolvedPerturbationPlan.from_mapping(row)
