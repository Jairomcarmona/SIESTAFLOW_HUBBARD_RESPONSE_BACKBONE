import pytest

from siestaflow_hubbard.domain.symmetry_reduction import (
    ReductionState,
    ShadowObservation,
    SymmetryPlanError,
    SymmetryReductionPolicy,
    authorize_symmetry_reduction,
    build_symmetry_reduction_plan,
)
from tests.support import certificate


def _policy():
    return SymmetryReductionPolicy(alpha_ev=0.05)


def _observation(orbit_id, **changes):
    values = dict(
        orbit_id=orbit_id,
        scientific_output_valid=True,
        occupation_max_abs_e=1.0e-6,
        chi0_max_abs_e_per_ev=1.0e-6,
        chi0_relative_l2=1.0e-5,
        chi_max_abs_e_per_ev=1.0e-6,
        chi_relative_l2=1.0e-5,
    )
    values.update(changes)
    return ShadowObservation(**values)


def test_translation_plan_is_site_neutral_and_requires_direct_shadow_validation():
    plan = build_symmetry_reduction_plan(
        ["site_a", "site_b", "site_c", "site_d"],
        ["site_a", "site_b", "site_c", "site_d"],
        certificate(4),
        _policy(),
    )
    assert plan.state is ReductionState.SHADOW_VALIDATION_REQUIRED
    assert len(plan.orbit_plans) == 1
    orbit = plan.orbit_plans[0]
    assert orbit.representative_site_id == "site_a"
    assert orbit.shadow_site_id is not None
    assert len(plan.perturbations) == 8  # representative and shadow, 2 modes x +/- alpha
    assert {spec.alpha_ev for spec in plan.perturbations} == {-0.05, 0.05}
    assert {spec.mode.value for spec in plan.perturbations} == {"BARE", "SCREENED"}
    assert "Cu" not in repr(plan)
    assert "Yoltla" not in repr(plan)


def test_all_shadow_gates_must_pass_before_authorizing_reconstruction():
    plan = build_symmetry_reduction_plan(
        ["a", "b", "c", "d"], ["a", "b", "c", "d"], certificate(4), _policy()
    )
    result = authorize_symmetry_reduction(plan, [_observation(plan.orbit_plans[0].orbit_id)])
    assert result.state is ReductionState.REDUCTION_AUTHORIZED
    assert result.explicit_expansion_site_ids == ()


def test_failed_shadow_expands_entire_rejected_orbit_not_an_average():
    plan = build_symmetry_reduction_plan(
        ["a", "b", "c", "d"], ["a", "b", "c", "d"], certificate(4), _policy()
    )
    result = authorize_symmetry_reduction(
        plan, [_observation(plan.orbit_plans[0].orbit_id, chi_relative_l2=0.01)]
    )
    assert result.state is ReductionState.EXPLICIT_FALLBACK_REQUIRED
    assert result.explicit_expansion_site_ids == ("a", "b", "c", "d")


def test_missing_certificate_falls_back_to_all_explicit_perturbations():
    plan = build_symmetry_reduction_plan(["a", "b"], ["a", "b"], None, _policy())
    assert plan.state is ReductionState.EXPLICIT_REQUIRED
    assert len(plan.perturbations) == 8
    assert {spec.purpose for spec in plan.perturbations} == {"explicit_fallback"}


def test_partial_shadow_evidence_is_rejected_instead_of_authorized():
    plan = build_symmetry_reduction_plan(
        ["a", "b", "c", "d"], ["a", "b", "c", "d"], certificate(4), _policy()
    )
    with pytest.raises(SymmetryPlanError, match="exactly"):
        authorize_symmetry_reduction(plan, [])
