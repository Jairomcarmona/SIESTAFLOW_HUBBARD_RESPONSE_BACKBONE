from siestaflow_hubbard.domain.symmetry_reduction import (
    ReductionState,
    ShadowObservation,
    SymmetryReductionPolicy,
    authorize_symmetry_reduction,
    build_symmetry_reduction_plan,
    explicit_expansion_specs,
)
from siestaflow_hubbard.execution.lr_dag import (
    LRNodeKind,
    adaptive_alpha_perturbations,
    append_explicit_fallback,
    build_adaptive_alpha_lr_dag,
    build_initial_lr_dag,
)
from siestaflow_hubbard.domain.adaptive_alpha import AdaptiveAlphaPolicy
from siestaflow_hubbard.domain.alpha_selection import AlphaSelectionPolicy
from tests.support import certificate


def _plan():
    return build_symmetry_reduction_plan(
        ["a", "b", "c", "d"], ["a", "b", "c", "d"], certificate(4),
        SymmetryReductionPolicy(alpha_ev=0.05),
    )


def _failed_observation(orbit_id):
    return ShadowObservation(
        orbit_id=orbit_id, scientific_output_valid=True,
        occupation_max_abs_e=0.0, chi0_max_abs_e_per_ev=0.0, chi0_relative_l2=0.0,
        chi_max_abs_e_per_ev=1.0, chi_relative_l2=0.0,
    )


def test_initial_dag_places_all_direct_responses_after_reference_and_before_gate():
    plan = _plan()
    dag = build_initial_lr_dag(plan)
    assert dag.analysis_requires_authorization is True
    assert dag.node("reference").dependencies == ()
    responses = [node for node in dag.nodes if node.kind is LRNodeKind.PERTURBATION]
    assert len(responses) == 8
    assert all(node.dependencies == ("reference",) for node in responses)
    assert set(dag.node("symmetry-shadow-gate").dependencies) == {node.node_id for node in responses}
    assert dag.node("matrix-analysis").dependencies == ("symmetry-shadow-gate",)


def test_rejected_shadow_replaces_gate_dependency_with_explicit_direct_fallback():
    plan = _plan()
    authorization = authorize_symmetry_reduction(
        plan, [_failed_observation(plan.orbit_plans[0].orbit_id)]
    )
    assert authorization.state is ReductionState.EXPLICIT_FALLBACK_REQUIRED
    fallback = explicit_expansion_specs(plan, authorization)
    assert len(fallback) == 16
    dag = append_explicit_fallback(build_initial_lr_dag(plan), fallback)
    analysis = dag.node("matrix-analysis")
    assert "symmetry-shadow-gate" not in analysis.dependencies
    assert len(analysis.dependencies) == 24
    assert dag.analysis_requires_authorization is False


def test_adaptive_alpha_dag_has_three_nonzero_scales_and_a_real_gate():
    plan = _plan()
    policy = AdaptiveAlphaPolicy(0.05, AlphaSelectionPolicy(occupation_noise=1e-6))
    specs = adaptive_alpha_perturbations(plan, policy)
    assert len(specs) == 24
    assert {abs(spec.alpha_ev) for spec in specs} == {0.025, 0.05, 0.1}
    dag = build_adaptive_alpha_lr_dag(plan, policy)
    assert dag.alpha_requires_authorization is True
    assert dag.node("alpha-linearity-gate").kind is LRNodeKind.ALPHA_GATE
    assert dag.node("symmetry-shadow-gate").dependencies == ("alpha-linearity-gate",)
