import pytest

from siestaflow_hubbard.domain.adaptive_alpha_control import (
    AdaptiveAlphaControlError,
    AdaptiveAlphaPolicy,
    AdaptiveDecision,
    decide_round,
    initial_siesta_node_cost,
    symmetric_refinement_pair,
)


def _fit(window, method="polynomial", degree=3, dof=1):
    return {
        "active_window_eV": window,
        "estimator": method,
        "polynomial_degree": degree,
        "minimum_residual_dof": dof,
        "matrix_for_inversion": "raw",
    }


def _policy(**overrides):
    payload = {
        "schema": "siestaflow.adaptive_alpha_policy.v1",
        "h_eV": 0.05,
        "alpha_seed_span_eV": 0.15,
        "alpha_ceiling_eV": 0.25,
        "max_refinement_rounds": 2,
        "max_alpha_points": 11,
        "total_siesta_node_budget": 200,
        "round_analysis": {
            "initial": _fit(0.15),
            "shrink": [_fit(0.10), _fit(0.05)],
            "expand": [_fit(0.20), _fit(0.25)],
        },
        "probe_trigger_ratio": 5.0,
        "tol_abs_eV": 0.02,
        "tol_rel": 0.01,
        "truncation_threshold_eV": 0.1,
        "sensitivity_delta_tolerance_eV": 0.01,
        "scf_materiality_ratio": 2.0,
        "rho_min": 1.0,
        "scf_probe_level": {
            "level_id": "strict-1",
            "fdf_overrides": {"SCF.Mixer.Method": "Pulay"},
        },
    }
    payload.update(overrides)
    return AdaptiveAlphaPolicy.from_mapping(payload)


def _signature(window, scf="base"):
    return {
        "active_window_eV": window,
        "estimator": "polynomial",
        "polynomial_degree": 3,
        "minimum_residual_dof": 1,
        "matrix_for_inversion": "raw",
        "window_selection_rule": "policy_declared_active_window_by_round",
        "scf_level_id": scf,
        "policy_digest": "frozen-policy",
    }


def _signals(values=(1.0, 1.0), sites=("A", "B")):
    return {
        f"{site}|{mode}": {
            "perturbed_site_id": site,
            "signal_vector_electron": list(values),
            "rounding_bound_vector_electron": [0.001, 0.001],
        }
        for site in sites for mode in ("BARE", "SCREENED")
    }


def _decision(policy, **overrides):
    arguments = {
        "round_index": 0,
        "current_grid_ev": policy.seed_grid_ev,
        "completed_node_count": initial_siesta_node_cost(2, 6),
        "site_count": 2,
        "candidate_u_by_site_ev": {"A": 4.0, "B": 5.0},
        "previous_u_by_site_ev": None,
        "stable_comparisons": 0,
        "matrix_usable": True,
        "branch_consistent": True,
        "scf_converged": True,
        "truncation_metric_ev": 0.0,
        "sensitivity_metric_ev": 0.1,
        "previous_sensitivity_metric_ev": 0.1,
        "signal_vectors_by_mode_column": _signals(),
        "current_fit_signature": _signature(0.10),
        "previous_fit_signature": None,
        "scf_probe": None,
    }
    arguments.update(overrides)
    return decide_round(policy, **arguments)


def _probe_vectors(signal_vectors, strict_values=(0.001, 0.001)):
    return {
        "validated": True,
        "by_mode_column": {
            key: {
                "v_base_electron": item["signal_vector_electron"],
                "v_strict_electron": list(strict_values),
                "q_rounding_bound_electron": [0.001, 0.001],
                "branch_consistent": True,
            }
            for key, item in signal_vectors.items()
        },
    }


def test_policy_seed_and_budget_include_shared_reference_once():
    policy = _policy()
    assert policy.seed_grid_ev == pytest.approx((-0.15, -0.1, -0.05, 0.05, 0.1, 0.15))
    assert symmetric_refinement_pair(policy, policy.seed_grid_ev, "shrink") == pytest.approx((-0.025, 0.025))
    assert initial_siesta_node_cost(1, 6) == 13
    assert initial_siesta_node_cost(2, 6) == 25
    with pytest.raises(AdaptiveAlphaControlError, match="at least 2"):
        _policy(max_refinement_rounds=1, max_alpha_points=9)


def test_round_fit_windows_are_branch_specific_and_cover_materialized_shrink_pair():
    policy = _policy()
    assert policy.analysis_for_round(1, "shrink")["active_window_eV"] == 0.10
    assert policy.analysis_for_round(1, "expand")["active_window_eV"] == 0.20
    with pytest.raises(AdaptiveAlphaControlError, match="active window"):
        _policy(round_analysis={
            "initial": _fit(0.15), "shrink": [_fit(0.075), _fit(0.05)],
            "expand": [_fit(0.20), _fit(0.25)],
        })


def test_policy_rejects_polynomial_degree_unsupported_by_response_analyzer():
    with pytest.raises(AdaptiveAlphaControlError, match="polynomial_degree must be between 1 and 3"):
        _policy(round_analysis={
            "initial": _fit(0.15, degree=4),
            "shrink": [_fit(0.10), _fit(0.05)],
            "expand": [_fit(0.20), _fit(0.25)],
        })


def test_missing_stability_thresholds_can_never_claim_stability():
    policy = _policy(tol_abs_eV=None, tol_rel=None)
    result = _decision(
        policy,
        candidate_u_by_site_ev={"A": 4.0, "B": 5.0},
        previous_u_by_site_ev={"A": 4.0, "B": 5.0},
        current_fit_signature=_signature(0.10),
        previous_fit_signature=_signature(0.10),
        stable_comparisons=1,
    )
    assert result["decision"] == AdaptiveDecision.STOP_LIMIT_SENSITIVE.value
    assert result["stable_comparisons"] == 0
    assert result["reason"] == "decision_predicate_or_threshold_not_satisfied"


def test_truncation_refines_inward_only_when_policy_threshold_passes():
    result = _decision(_policy(), truncation_metric_ev=0.2)
    assert result["decision"] == AdaptiveDecision.REFINE.value
    assert result["direction"] == "shrink"
    assert result["add_alpha_ev"] == pytest.approx([-0.025, 0.025])
    assert result["required_budget"] == 8


def test_scf_probe_materiality_and_expansion_require_full_equivalent_scope():
    policy = _policy()
    weak = _signals(values=(0.001, 0.001))
    pending = _decision(policy, signal_vectors_by_mode_column=weak)
    assert pending["decision"] == AdaptiveDecision.PROBE_SCF.value

    material = _decision(
        policy,
        signal_vectors_by_mode_column=weak,
        scf_probe=_probe_vectors(weak, strict_values=(0.01, 0.01)),
    )
    assert material["decision"] == AdaptiveDecision.IMPROVE_SCF_FIRST.value
    assert material["probe_is_error_bound"] is False
    assert material["required_budget"] == 25

    small = _decision(policy, signal_vectors_by_mode_column=weak, scf_probe=_probe_vectors(weak))
    assert small["decision"] == AdaptiveDecision.REFINE.value
    assert small["direction"] == "expand"
    assert small["add_alpha_ev"] == pytest.approx([-0.2, 0.2])

    partial = {key: value for key, value in _probe_vectors(weak)["by_mode_column"].items() if key.startswith("A|")}
    incomplete = _decision(
        policy,
        signal_vectors_by_mode_column=weak,
        scf_probe={"validated": True, "by_mode_column": partial},
    )
    assert incomplete["decision"] == AdaptiveDecision.STOP_LIMIT_SENSITIVE.value
    assert incomplete["reason"] == "probe_scope_incomplete_for_common_grid_expansion"


def test_single_weak_column_probes_every_site_and_mode_before_common_grid_expansion():
    policy = _policy()
    signals = _signals(values=(1.0, 1.0))
    signals["A|BARE"]["signal_vector_electron"] = [0.001, 0.001]

    pending = _decision(policy, signal_vectors_by_mode_column=signals)
    assert pending["decision"] == AdaptiveDecision.PROBE_SCF.value
    assert pending["affected_mode_columns"] == ["A|BARE"]
    assert pending["affected_site_ids"] == ["A"]
    assert pending["probe_site_ids"] == ["A", "B"]
    assert pending["probe_scope"] == "all_sites_all_modes_for_common_grid_expansion"
    assert pending["required_budget"] == 9  # shared strict reference + 2 sites × 2 modes × ±h

    full_probe = {
        "validated": True,
        "by_mode_column": {
            key: {
                "v_base_electron": item["signal_vector_electron"],
                "v_strict_electron": item["signal_vector_electron"],
                "q_rounding_bound_electron": [0.001, 0.001],
                "branch_consistent": True,
            }
            for key, item in signals.items()
        },
    }
    decision = _decision(
        policy, signal_vectors_by_mode_column=signals, scf_probe=full_probe,
    )
    assert decision["decision"] == AdaptiveDecision.REFINE.value
    assert decision["direction"] == "expand"


def test_incomplete_or_underfunded_common_grid_probe_stops_before_dispatch():
    policy = _policy()
    partial = {
        "A|BARE": {
            "perturbed_site_id": "A",
            "signal_vector_electron": [0.001, 0.001],
            "rounding_bound_vector_electron": [0.001, 0.001],
        },
    }
    incomplete = _decision(policy, signal_vectors_by_mode_column=partial)
    assert incomplete["decision"] == AdaptiveDecision.STOP_LIMIT_SENSITIVE.value
    assert incomplete["reason"] == "probe_scope_incomplete_for_common_grid_expansion"

    one_node_short = _decision(
        policy, signal_vectors_by_mode_column=_signals(values=(0.001, 0.001)),
        completed_node_count=policy.total_siesta_node_budget - 8,
    )
    assert one_node_short["decision"] == AdaptiveDecision.STOP_LIMIT_SENSITIVE.value
    assert one_node_short["reason"] == "scf_probe_exceeds_remaining_budget"
    assert one_node_short["required_budget"] == 9


def test_two_comparisons_and_round_budget_are_enforced_without_comparing_windows_as_methods():
    policy = _policy(tol_abs_eV=0.05, tol_rel=0.01)
    common = {
        "previous_u_by_site_ev": {"A": 4.0, "B": 5.0},
        "candidate_u_by_site_ev": {"A": 4.04, "B": 5.049},
        "previous_sensitivity_metric_ev": 0.1,
        "sensitivity_metric_ev": 0.11,
        "current_fit_signature": _signature(0.10),
        "previous_fit_signature": _signature(0.10),
    }
    first = _decision(policy, **common, stable_comparisons=0)
    assert first["decision"] == AdaptiveDecision.STOP_LIMIT_SENSITIVE.value
    assert first["stable_comparisons"] == 1
    second = _decision(policy, **common, stable_comparisons=1)
    assert second["decision"] == AdaptiveDecision.STOP_STABLE.value
    assert second["stable_comparisons"] == 2

    no_budget = _decision(policy, truncation_metric_ev=0.2, completed_node_count=199)
    assert no_budget["decision"] == AdaptiveDecision.STOP_LIMIT_SENSITIVE.value
    assert no_budget["reason"] == "refinement_exceeds_remaining_budget"


def test_round_exhaustion_with_fewer_than_two_stable_comparisons_stays_sensitive():
    policy = _policy(tol_abs_eV=0.05, tol_rel=0.01)
    result = _decision(
        policy,
        round_index=policy.max_refinement_rounds,
        current_grid_ev=policy.seed_grid_ev,
        previous_u_by_site_ev={"A": 4.0, "B": 5.0},
        candidate_u_by_site_ev={"A": 4.06, "B": 5.0},
        current_fit_signature=_signature(0.10),
        previous_fit_signature=_signature(0.10),
        stable_comparisons=1,
        truncation_metric_ev=0.0,
        sensitivity_metric_ev=0.1,
        previous_sensitivity_metric_ev=0.1,
    )
    assert result["decision"] == AdaptiveDecision.STOP_LIMIT_SENSITIVE.value
    assert result["reason"] == "maximum_refinement_rounds_reached"
    assert result["stable_comparisons"] == 0


def test_incomplete_branch_or_matrix_is_terminal_before_refinement():
    policy = _policy()
    assert _decision(policy, branch_consistent=False)["decision"] == AdaptiveDecision.STOP_INVALID.value
    assert _decision(policy, matrix_usable=False)["decision"] == AdaptiveDecision.STOP_INVALID.value
