from hubbardflow.domain.matrix_lr import ResponseObservation
from hubbardflow.domain.scientific_profile import V6_PBE_REFERENCE_PROFILE
from hubbardflow.execution.campaign_runner import CampaignRunner, _build_dag, _build_verified_dataset
from hubbardflow.execution.lr_dag import LRNodeKind
from hubbardflow.domain.symmetry_reduction import ResponseMode


def test_fixed_grid_dag_is_explicit_and_alpha_diagnostic_does_not_veto_analysis():
    sites = [
        {"index": 0, "site_id": "M0", "atom_index": 1, "orbit_id": "M0"},
        {"index": 1, "site_id": "M1", "atom_index": 2, "orbit_id": "M1"},
    ]
    alphas = [-0.1, 0.1]

    dag, specs = _build_dag(sites, alphas)

    reference = dag.node("reference")
    gate = dag.node("alpha-diagnostic-gate")
    analysis = dag.node("matrix-analysis")
    responses = [node for node in dag.nodes if node.kind is LRNodeKind.PERTURBATION]
    assert reference.kind is LRNodeKind.REFERENCE
    assert len(responses) == len(sites) * len(alphas) * 2
    assert len(specs) == len(responses)
    assert {spec.mode for spec in specs.values()} == {ResponseMode.BARE, ResponseMode.SCREENED}
    assert {spec.alpha_ev for spec in specs.values()} == set(alphas)
    assert set(gate.dependencies) == {node.node_id for node in responses}
    assert analysis.dependencies == (gate.node_id,)

    # A failed linear-window diagnosis is not a dependency veto: the fixed
    # grid always reaches matrix analysis, which decides what can be reported.
    runner = object.__new__(CampaignRunner)
    runner.campaign = {
        "campaign_id": "synthetic", "name": "fixed-grid", "material": "fixture",
        "input_identity": "a" * 64, "_xc_profile": V6_PBE_REFERENCE_PROFILE.to_mapping(),
    }
    runner.sites = sites
    runner.alpha_grid = alphas
    runner.config = {"analysis_policy": {"estimator": "auto"}}
    runner.campaign["functional"] = "PBE"
    runner._analysis_input_provenance = lambda: {}
    result = runner._no_numerical_result("synthetic_no_linear_window")
    assert result["numerical_status"] == "NO_NUMERICAL_U"
    assert result["primary"]["U_matrix_eV"] is None
    assert result["reasons"][-1] == "synthetic_no_linear_window"


def test_verified_observation_dataset_persists_site_mapping_occupations_and_sources():
    observation = ResponseObservation(
        perturbation_site=1,
        alpha=-0.1,
        site_labels=[0, 1],
        occupations_ref=[5.0, 4.0],
        occupations_bare=[5.1, 4.1],
        occupations_screened=[5.2, 4.2],
    )
    reference_source = {"node_id": "reference", "out_path": "reference.out", "evidence_digest": "a" * 64}
    bare_source = {"node_id": "bare", "mode": "BARE", "fdf_path": "bare.fdf", "out_path": "bare.out", "evidence_digest": "b" * 64}
    screened_source = {"node_id": "screened", "mode": "SCREENED", "fdf_path": "screened.fdf", "out_path": "screened.out", "evidence_digest": "c" * 64}

    dataset = _build_verified_dataset(
        [observation],
        [{"site_id": "NiA", "atom_index": 1}, {"site_id": "NiB", "atom_index": 2}],
        reference_source=reference_source,
        response_sources={(1, -0.1): {"bare": bare_source, "screened": screened_source}},
        trace_half_widths_electron={
            (1, -0.1, "bare"): [0.00005, 0.00005],
            (1, -0.1, "screened"): [0.00005, 0.00005],
        },
        reference_trace_half_widths_electron=[0.00005, 0.00005],
    )

    assert dataset["schema_version"] == "siestaflow.lr_u_verified_dataset.v1"
    assert dataset["matrix_index_to_site_id"] == {"0": "NiA", "1": "NiB"}
    row = dataset["rows"][0]
    assert row["perturbed_site_id"] == "NiB"
    assert row["observed_sites"][1]["occupations_electron"] == {
        "reference": 4.0, "bare": 4.1, "screened": 4.2,
    }
    assert row["observed_sites"][1]["matrix_trace_half_widths_electron"] == {
        "reference": 0.00005, "bare": 0.00005, "screened": 0.00005,
    }
    assert row["sources"]["bare"]["evidence_digest"] == "b" * 64
    assert row["sources"]["screened"]["out_path"] == "screened.out"


def test_verified_observation_dataset_rejects_misordered_site_indices():
    import pytest

    observation = ResponseObservation(
        perturbation_site=0,
        alpha=0.1,
        site_labels=[1, 0],
        occupations_ref=[5.0, 4.0],
        occupations_bare=[5.1, 4.1],
        occupations_screened=[5.2, 4.2],
    )
    with pytest.raises(ValueError, match="site index map"):
        _build_verified_dataset(
            [observation],
            [{"site_id": "NiA"}, {"site_id": "NiB"}],
            reference_source={},
            response_sources={(0, 0.1): {"bare": {}, "screened": {}}},
        )


def test_reference_worker_mode_executes_only_reference_and_stops(tmp_path):
    from types import SimpleNamespace

    from hubbardflow.execution.dag_contract import NodeState
    from hubbardflow.execution.generic_executor import NodeReceipt
    from hubbardflow.execution.lr_dag import LRDagNode

    reference_node = LRDagNode("reference", LRNodeKind.REFERENCE, ())
    executed = []
    state = {"receipts": {}}

    class Heartbeat:
        def __init__(self):
            self.finished = None

        def update(self, **changes):
            pass

        def finish(self, status, **changes):
            self.finished = {"status": status, **changes}

    runner = object.__new__(CampaignRunner)
    runner.checkpoint_path = tmp_path / "checkpoint.json"
    runner.executor = SimpleNamespace(runnable=lambda: [reference_node])
    runner.control = tmp_path
    runner.store = SimpleNamespace(records={})
    runner._checkpoint = lambda: state["receipts"]
    runner._reserve_adaptive_node = lambda _: True

    def execute(node, _heartbeat):
        executed.append(node.node_id)
        receipt = NodeReceipt(node.node_id, NodeState.VALIDATED, "a" * 64)
        state["receipts"] = {node.node_id: receipt}
        return receipt

    runner._execute_siesta = execute
    heartbeat = Heartbeat()

    assert runner.advance("reference", heartbeat) == 0
    assert executed == ["reference"]
    assert heartbeat.finished == {
        "status": "STOPPED",
        "stop_reason": "reference_only",
        "completed_nodes": ["reference"],
    }


def test_reference_worker_mode_preserves_failed_reference_status(tmp_path):
    from types import SimpleNamespace

    from hubbardflow.execution.dag_contract import NodeState
    from hubbardflow.execution.generic_executor import NodeReceipt
    from hubbardflow.execution.lr_dag import LRDagNode

    reference_node = LRDagNode("reference", LRNodeKind.REFERENCE, ())
    receipt = NodeReceipt("reference", NodeState.FAILED_EXECUTION, "b" * 64)

    class Heartbeat:
        def __init__(self):
            self.finished = None

        def update(self, **changes):
            pass

        def finish(self, status, **changes):
            self.finished = {"status": status, **changes}

    runner = object.__new__(CampaignRunner)
    runner.checkpoint_path = tmp_path / "checkpoint.json"
    runner.executor = SimpleNamespace(runnable=lambda: [reference_node])
    runner.control = tmp_path
    runner.store = SimpleNamespace(records={})
    runner.shadow = None
    runner._checkpoint = lambda: {"reference": receipt}
    runner._reserve_adaptive_node = lambda _: True
    runner._execute_siesta = lambda _node, _heartbeat: receipt
    heartbeat = Heartbeat()

    assert runner.advance("reference", heartbeat) == 1
    assert heartbeat.finished["status"] == "FAILED"
    assert heartbeat.finished["failed_node"] == "reference"
