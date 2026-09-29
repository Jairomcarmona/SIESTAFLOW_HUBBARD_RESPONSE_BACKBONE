from dataclasses import replace
from copy import deepcopy
from pathlib import Path

from siestaflow_hubbard.domain.adaptive_alpha_control import AdaptiveAlphaPolicy
from siestaflow_hubbard.domain.symmetry_reduction import ResponseMode
from siestaflow_hubbard.execution.campaign_runner import CampaignRunner
from siestaflow_hubbard.execution import campaign_runner as runner_module
from siestaflow_hubbard.execution.dag_contract import NodeState
from siestaflow_hubbard.execution.generic_executor import GenericDagExecutor, NodeReceipt
from siestaflow_hubbard.execution.lr_dag import (
    LRDag, LRDagNode, LRNodeKind, build_adaptive_campaign_dag,
)


def _policy(budget=40):
    fit = {
        "active_window_eV": 0.15, "estimator": "polynomial",
        "polynomial_degree": 3, "minimum_residual_dof": 1,
        "matrix_for_inversion": "raw",
    }
    return AdaptiveAlphaPolicy.from_mapping({
        "schema": "siestaflow.adaptive_alpha_policy.v1",
        "h_eV": 0.05, "alpha_seed_span_eV": 0.15, "alpha_ceiling_eV": None,
        "max_refinement_rounds": 2, "max_alpha_points": 11,
        "total_siesta_node_budget": budget,
        "round_analysis": {
            "initial": fit,
            "shrink": [{**fit, "active_window_eV": 0.10}, {**fit, "active_window_eV": 0.05}],
            "expand": [fit, fit],
        },
        "probe_trigger_ratio": None, "tol_abs_eV": None, "tol_rel": None,
        "truncation_threshold_eV": None, "sensitivity_delta_tolerance_eV": None,
        "scf_materiality_ratio": None, "rho_min": None, "scf_probe_level": None,
    })


def _rounds(policy):
    first = {
        "round_index": 0, "direction": "initial", "alpha_grid_ev": list(policy.seed_grid_ev),
        "scf_level_id": "base", "active_window_eV": 0.15,
    }
    second = {
        "round_index": 1, "direction": "shrink",
        "alpha_grid_ev": sorted([*policy.seed_grid_ev, -0.025, 0.025]),
        "scf_level_id": "base", "active_window_eV": 0.10,
    }
    return [first, second]


def test_dynamic_dag_reuses_response_ids_and_receipts_with_stable_identity():
    policy = _policy()
    sites = [{"site_id": "A", "atom_index": 1}, {"site_id": "B", "atom_index": 2}]
    initial, initial_specs, _ = build_adaptive_campaign_dag(
        sites, _rounds(policy)[:1], campaign_id="campaign", policy_digest="policy-v1",
    )
    extended, extended_specs, _ = build_adaptive_campaign_dag(
        sites, _rounds(policy), campaign_id="campaign", policy_digest="policy-v1",
    )
    initial_ids = {node.node_id for node in initial.nodes}
    extended_ids = {node.node_id for node in extended.nodes}
    assert initial_ids.issubset(extended_ids)
    assert len(extended_ids) == len(extended.nodes)
    assert len(initial_specs) == 2 * 6 * 2
    assert len(extended_specs) == 2 * 8 * 2
    added = extended_ids - initial_ids
    assert any(":r1:lr_s" in node_id and "_m0p025_" in node_id for node_id in added)
    response = next(node for node in extended.nodes if node.kind is LRNodeKind.PERTURBATION)
    assert response.scf_level_id == "base"
    assert response.parent_dm_node_id in extended_ids

    identity = "input-identity+policy-digest"
    first_executor = GenericDagExecutor(initial, Path("unused-dag-checkpoint.json"), checkpoint_identity=identity)
    reference = next(node for node in initial.nodes if node.kind is LRNodeKind.REFERENCE)
    durable_receipts = {}
    first_executor.checkpoint.save = lambda receipts: durable_receipts.update(receipts)
    first_executor.checkpoint.save({reference.node_id: NodeReceipt(reference.node_id, NodeState.VALIDATED, "ref-digest")})
    resumed = GenericDagExecutor(extended, Path("unused-dag-checkpoint.json"), checkpoint_identity=identity)
    resumed.checkpoint.load = lambda: dict(durable_receipts)
    assert first_executor.checkpoint.campaign_digest == resumed.checkpoint.campaign_digest
    assert resumed.checkpoint.load()[reference.node_id].evidence_digest == "ref-digest"


def test_budget_reservation_is_atomic_and_idempotent_by_node_id():
    policy = _policy(budget=2)
    runner = object.__new__(CampaignRunner)
    runner.adaptive_policy = policy
    runner.adaptive_policy_digest = "policy-digest"
    runner.adaptive_state = {"reserved_nodes": {}, "budget": {}}
    persisted_snapshots = []
    def record_persistence():
        count = len(runner.adaptive_state["reserved_nodes"])
        runner.adaptive_state["budget"] = {
            "total_siesta_node_budget": policy.total_siesta_node_budget,
            "reserved_nodes": count,
            "remaining_nodes": policy.total_siesta_node_budget - count,
        }
        persisted_snapshots.append(deepcopy(runner.adaptive_state))
    runner._persist_adaptive_state = record_persistence
    reference = LRDagNode("reference:adaptive:policy:base", LRNodeKind.REFERENCE, (), scf_level_id="base")
    assert runner._reserve_adaptive_node(reference) is True
    assert runner._reserve_adaptive_node(reference) is True
    assert len(runner.adaptive_state["reserved_nodes"]) == 1

    spec = next(iter(build_adaptive_campaign_dag(
        [{"site_id": "A", "atom_index": 1}],
        [{"round_index": 0, "alpha_grid_ev": list(policy.seed_grid_ev), "scf_level_id": "base"}],
        campaign_id="campaign", policy_digest="policy",
    )[1].values()))
    second = LRDagNode(
        "response:adaptive:r0:one", LRNodeKind.PERTURBATION, (), spec,
        scf_level_id="base", parent_dm_node_id=reference.node_id,
    )
    assert runner._reserve_adaptive_node(second) is True
    assert runner._reserve_adaptive_node(replace(second, node_id="response:adaptive:r0:two")) is False
    assert set(runner.adaptive_state["reserved_nodes"]) == {reference.node_id, second.node_id}
    assert len(persisted_snapshots) == 2
    assert persisted_snapshots[-1]["budget"]["remaining_nodes"] == 0


def test_node_identity_binds_site_mode_alpha_level_parent_round_campaign_and_policy():
    policy = _policy()
    sites = [{"site_id": "A", "atom_index": 1}]
    rounds = _rounds(policy)[:1]
    first, first_specs, _ = build_adaptive_campaign_dag(
        sites, rounds, campaign_id="campaign-a", policy_digest="policy-a",
    )
    second, second_specs, _ = build_adaptive_campaign_dag(
        sites, rounds, campaign_id="campaign-b", policy_digest="policy-a",
    )
    first_node = next(iter(first_specs))
    assert first_node != next(iter(second_specs))
    node = next(item for item in first.nodes if item.node_id == first_node)
    assert node.perturbation is not None
    assert node.perturbation.mode in {ResponseMode.BARE, ResponseMode.SCREENED}
    assert node.parent_dm_node_id is not None
    assert ":r0:" in node.node_id


def test_invalidating_refined_round_truncates_descendants_and_keeps_reservations():
    runner = object.__new__(CampaignRunner)
    first_gate = "adaptive:campaign:round:0:decision"
    second_gate = "adaptive:campaign:round:1:decision"
    runner.dag = LRDag((
        LRDagNode(first_gate, LRNodeKind.ALPHA_GATE, ()),
        LRDagNode(second_gate, LRNodeKind.ALPHA_GATE, (first_gate,)),
    ), analysis_requires_authorization=False)
    runner.adaptive_state = {
        "decisions": [
            {"node_id": first_gate, "decision": "REFINE", "candidate_status": "SENSITIVE"},
            {"node_id": second_gate, "decision": "REFINE", "candidate_status": "SENSITIVE"},
        ],
        "rounds": [
            {"round_index": 0, "status": "DECIDED", "decision": {"decision": "REFINE"}},
            {"round_index": 1, "status": "DECIDED", "decision": {"decision": "REFINE"}},
        ],
        "scf_reruns": [], "probe_plan": None,
        "reserved_nodes": {"executed-node": {"reservation_status": "SPENT"}},
        "stable_comparisons": 1, "candidate_status": "SENSITIVE", "campaign_status": "RUNNING",
    }
    runner._persist_adaptive_state = lambda: None

    runner._rollback_adaptive_after_invalidation({"response-from-round-0", first_gate, second_gate})

    assert [item["round_index"] for item in runner.adaptive_state["rounds"]] == [0]
    assert runner.adaptive_state["decisions"] == []
    assert "decision" not in runner.adaptive_state["rounds"][0]
    assert runner.adaptive_state["rounds"][0]["status"] == "PENDING"
    assert "executed-node" in runner.adaptive_state["reserved_nodes"]


def test_invalidated_after_probe_gate_restores_probe_decision_in_round_state():
    runner = object.__new__(CampaignRunner)
    probe_gate = "adaptive:campaign:round:0:decision"
    after_probe_gate = "adaptive:campaign:round:0:decision-after-probe"
    runner.dag = LRDag((
        LRDagNode(probe_gate, LRNodeKind.ALPHA_GATE, ()),
        LRDagNode(after_probe_gate, LRNodeKind.ALPHA_GATE, (probe_gate,)),
    ), analysis_requires_authorization=False)
    probe_decision = {"node_id": probe_gate, "decision": "PROBE_SCF", "candidate_status": "SENSITIVE"}
    runner.adaptive_state = {
        "decisions": [probe_decision, {"node_id": after_probe_gate, "decision": "REFINE"}],
        "rounds": [{"round_index": 0, "status": "DECIDED", "decision": {"decision": "REFINE"}}],
        "scf_reruns": [], "probe_plan": {"round_index": 0},
        "reserved_nodes": {}, "stable_comparisons": 0,
        "candidate_status": "SENSITIVE", "campaign_status": "RUNNING",
    }
    runner._persist_adaptive_state = lambda: None

    runner._rollback_adaptive_after_invalidation({after_probe_gate})

    assert runner.adaptive_state["decisions"] == [probe_decision]
    assert runner.adaptive_state["rounds"][0]["decision"] == probe_decision
    assert runner.adaptive_state["rounds"][0]["status"] == "PROBE_SCHEDULED"
    assert runner.adaptive_state["probe_plan"] == {"round_index": 0}


def test_probe_gate_schedules_the_decision_scope_not_only_the_weak_column(monkeypatch):
    policy_mapping = _policy().to_mapping()
    policy_mapping.pop("truncation_threshold_ev", None)
    policy_mapping.pop("sensitivity_delta_tolerance_ev", None)
    policy_mapping["truncation_threshold_eV"] = None
    policy_mapping["sensitivity_delta_tolerance_eV"] = None
    policy_mapping.update({
        "probe_trigger_ratio": 5.0,
        "scf_probe_level": {
            "level_id": "strict-1",
            "fdf_overrides": {"SCF.Mixer.Method": "Pulay"},
        },
    })
    policy = AdaptiveAlphaPolicy.from_mapping(policy_mapping)
    runner = object.__new__(CampaignRunner)
    runner.adaptive_policy = policy
    runner.adaptive_policy_digest = "policy-digest"
    runner.sites = [{"site_id": "A", "atom_index": 1}, {"site_id": "B", "atom_index": 2}]
    runner.control = Path("unused-control")
    runner.adaptive_state = {
        "rounds": [{
            "round_index": 0, "scf_level_id": "base", "fit_policy": {},
            "analysis_path": "synthetic-analysis.json",
            "alpha_grid_ev": list(policy.seed_grid_ev), "status": "PENDING",
        }],
        "decisions": [], "stable_comparisons": 0,
        "reserved_nodes": {}, "probe_plan": None, "probed_site_ids": [],
    }
    analysis = {
        "numerical_status": "NUMERICAL_CANDIDATE_SENSITIVE",
        "primary": {"matrix_status": "FULL_RANK"},
        "scf_and_magnetic_diagnostics": {
            "state_continuity_confirmed": True, "scf_validated": True,
        },
    }
    runner._analysis_metrics = lambda _path: analysis
    runner._fit_signature = lambda fit, level: {"scf_level_id": level, **fit}
    runner._analysis_u = lambda _analysis: {"A": 4.0, "B": 5.0}
    runner._signal_vectors = lambda _level: {"A|BARE": {"signal_vector_electron": [0.001]}}
    runner._scf_probe_evidence = lambda _signals: None
    runner._persist_adaptive_state = lambda: None
    runner._record_receipt = lambda *_args, **_kwargs: None
    rebuilt = []
    runner._rebuild_adaptive_graph = lambda: rebuilt.append(True)
    monkeypatch.setattr(runner_module, "_atomic_json", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(runner_module, "sha256_file", lambda *_args, **_kwargs: "a" * 64)
    monkeypatch.setattr(runner_module, "decide_round", lambda *_args, **_kwargs: {
        "decision": "PROBE_SCF", "reason": "weak-column-trigger",
        "affected_site_ids": ["A"], "affected_mode_columns": ["A|BARE"],
        "probe_site_ids": ["A", "B"],
        "probe_scope": "all_sites_all_modes_for_common_grid_expansion",
    })

    node = LRDagNode("adaptive:campaign:round:0:decision", LRNodeKind.ALPHA_GATE, ())
    runner._execute_adaptive_gate(node)

    assert runner.adaptive_state["probe_plan"]["site_indices"] == [0, 1]
    assert runner.adaptive_state["probe_plan"]["trigger_site_ids"] == ["A"]
    assert runner.adaptive_state["probe_plan"]["probe_site_ids"] == ["A", "B"]
    assert runner.adaptive_state["probe_plan"]["scope"] == "all_sites_all_modes_for_common_grid_expansion"
    assert runner.adaptive_state["probed_site_ids"] == ["A", "B"]
    assert rebuilt == [True]
