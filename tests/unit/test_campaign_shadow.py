"""Synthetic runner barriers, raw reconstruction, rejection and resume.

The injected SIESTA adapter supplies validated receipts and known occupations;
the real CampaignRunner dispatch, barrier and analysis execute unchanged.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import replace
from fractions import Fraction
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from hubbardflow.domain.coverage import UserCoveragePolicy, qualify_coverage
from hubbardflow.domain.coverage_models import CoverageStatus
from hubbardflow.domain.lr_analysis_v2 import LRAnalysisPolicy
from hubbardflow.domain.matrix_lr import ResponseObservation
from hubbardflow.domain.perturbation_plan import AlphaStrategy, ResolvedPerturbationPlan
from hubbardflow.domain.perturbation_planner import resolve_perturbation_plan
from hubbardflow.domain.response_error_budget import ElementSeries, PointObservation, printed_response_budget
from hubbardflow.domain.response_protocol import (
    EstimatorKind,
    EstimatorSpec,
    PerturbationStrategy,
    protocol_from_fixed_grid,
)
from hubbardflow.domain.response_shadow import ShadowComparison, ShadowOutcome, ShadowReason, qualify_shadows
from hubbardflow.domain.scientific_profile import V6_PBE_REFERENCE_PROFILE
from hubbardflow.domain.symmetry_operation_models import coverage_policy_v1
from hubbardflow.domain.symmetry_reduction import ResponseMode
from hubbardflow.execution.campaign_runner import CampaignRunner, _build_dag, _Heartbeat
from hubbardflow.execution.campaign_shadow import CampaignShadow
from hubbardflow.execution.campaign_shadow_inputs import build_shadow_dag, observation_series
from hubbardflow.execution.campaign_store import CampaignStore
from hubbardflow.execution.dag_contract import NodeState
from hubbardflow.execution.generic_executor import (
    ExecutionContractError,
    GenericDagExecutor,
    NodeReceipt,
    dag_digest,
)
from hubbardflow.execution.lr_dag import LRDagNode, LRNodeKind
from hubbardflow.execution.observation_assembly import ObservationAssembler
from hubbardflow.siesta_backend.output_validator import SiestaArtifactSpec
from hubbardflow.siesta_backend.siesta542_bare_profile import Siesta542PotentialShiftHamiltonianProfile
from tests.unit.test_coverage import DIGEST, _toy


def _plan(count: int = 4) -> ResolvedPerturbationPlan:
    inv, ref, model = _toy(count)
    cov = qualify_coverage(inv, ref, model, coverage_policy_v1(), UserCoveragePolicy("test-v1", True, ()))
    protocol = protocol_from_fixed_grid(
        tuple(s.site_id for s in inv.subspaces),
        (-0.02, -0.01, 0.01, 0.02),
        estimator=EstimatorKind.LINEAR_LSQ,
        polynomial_degree=None,
        scf_level_id="base",
        reference_node_id="reference",
        observable_id="siesta_occupations_total",
        strategy=PerturbationStrategy.FIXED_PROTOCOL_GRID,
        protocol_version="synthetic-v1",
    )
    return resolve_perturbation_plan(
        inv,
        cov,
        protocol,
        source_fdf_sha256=DIGEST,
        alpha_strategy=AlphaStrategy.FIXED_PROTOCOL_GRID,
        planner_version="test-v1",
        backend_identity="test-binary:" + DIGEST,
        tau_u_ev=None,
    )


def _observations(
    plan: ResolvedPerturbationPlan, computed: set[int], *, fail: bool = False
) -> tuple[
    list[ResponseObservation],
    dict[tuple[int, float, str], list[float]],
]:
    size = len(plan.inventory.subspaces)
    observations, widths = [], {}
    for j in sorted(computed):
        for alpha in (-0.02, -0.01, 0.01, 0.02):
            bare = [1 + alpha * (-2 if i == j else -0.25) for i in range(size)]
            screened = [1 + alpha * (-1 if i == j else -0.1) for i in range(size)]
            if fail and j == 1:
                screened[0] += alpha * 0.5
            observations.append(
                ResponseObservation(
                    j, alpha, list(range(size)), [1.0] * size, bare, screened, parent_dm_sha256=DIGEST
                )
            )
            for mode in ("bare", "screened"):
                widths[(j, alpha, mode)] = [5e-8] * size
    return observations, widths


def _runner(
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
    plan: ResolvedPerturbationPlan,
    *,
    fail: bool = False,
    coverage: str = "TRANSLATION_SHADOWED",
    stop_after: int | None = None,
    invalid_shadow: bool = False,
    invalid_shadow_once: bool = False,
    complete_synthetic_state: bool = True,
    rejection_policy: str = "EXPAND",
) -> tuple[CampaignRunner, list[str], _Heartbeat]:
    runner = object.__new__(CampaignRunner)
    runner.root = root
    runner.control = root / ".siestaflow"
    runner.control.mkdir(parents=True, exist_ok=True)
    runner.results = root / "results"
    runner.checkpoint_path = runner.control / "dag-checkpoint.json"
    runner.records_path = runner.control / "node-evidence.json"
    runner._input_sha256_by_path = {}
    runner._minimum_occupation_decimal_places = None
    runner.observations = ObservationAssembler()
    runner.campaign = {
        "campaign_id": "synthetic",
        "input_identity": DIGEST,
        "functional": "PBE",
        "name": "synthetic",
        "_xc_profile": V6_PBE_REFERENCE_PROFILE.to_mapping(),
    }
    runner.sites = [
        {"index": i, "site_id": s.site_id, "atom_index": i + 1}
        for i, s in enumerate(plan.inventory.subspaces)
    ]
    runner.alpha_grid = [-0.02, -0.01, 0.01, 0.02]
    runner.config = {
        "analysis_policy": {"estimator": "linear"},
        "shadow_rejection_policy": rejection_policy,
    }
    runner.admitted = cast(
        Any,
        SimpleNamespace(factory=SimpleNamespace(bare_profile=Siesta542PotentialShiftHamiltonianProfile())),
    )
    runner.analysis_policy = LRAnalysisPolicy(estimator="linear")
    runner.adaptive_policy = None
    runner.adaptive_state = None
    runner.adaptive_policy_digest = None
    runner.response_grid_calibration = None
    runner.shadow = (
        CampaignShadow(plan, runner.control, DIGEST) if coverage == "TRANSLATION_SHADOWED" else None
    )
    if runner.shadow is not None:
        runner.shadow.install(runner)
    else:
        runner.dag, runner.specs = _build_dag(runner.sites, runner.alpha_grid)
        runner.executor = GenericDagExecutor(runner.dag, runner.checkpoint_path)
    runner.store = CampaignStore(runner.records_path, lambda: runner.executor.checkpoint)
    runner.records = runner._load_records()
    executed: list[str] = []
    heartbeat = _Heartbeat(runner.control / "state.json", campaign_id="synthetic")
    heartbeat.start()

    def siesta(node: LRDagNode, _: _Heartbeat) -> NodeReceipt:
        executed.append(node.node_id)
        state = NodeState.VALIDATED
        if (
            (invalid_shadow or invalid_shadow_once)
            and node.perturbation is not None
            and node.perturbation.purpose == "shadow"
            and executed.count(node.node_id) == 1
            and (not invalid_shadow_once or (runner.shadow is not None and len(runner.shadow.expanded) == 0))
        ):
            state = NodeState.FAILED_OUTPUT_VALIDATION
        receipt = NodeReceipt(node.node_id, state, DIGEST)
        runner._record_receipt(
            node,
            receipt,
            {"kind": "synthetic-siesta", "provenance": {"artifacts": {"dm": DIGEST}}},
        )
        if stop_after is not None and len(executed) == stop_after:
            (runner.control / "stop-request.json").write_text("{}", encoding="utf-8")
        return receipt

    def verified(**kwargs: Any) -> tuple[Any, ...]:
        receipts = runner._checkpoint()
        computed = {
            s.site_index
            for k, s in runner.specs.items()
            if k in receipts and receipts[k].state is NodeState.VALIDATED
        }
        requested = set(kwargs.get("site_indices") or computed)
        assert requested <= computed
        observations, widths = _observations(plan, requested, fail=fail)
        return (
            observations,
            {a: "reference_branch" for a in runner.alpha_grid},
            {},
            widths,
            [5e-8] * len(runner.sites),
        )

    def dataset(observations: list[ResponseObservation], **_: Any) -> dict[str, Any]:
        return {
            "reference_source": {"dm_sha256": DIGEST},
            "rows": [
                {
                    "column": o.perturbation_site,
                    "alpha": o.alpha,
                    "bare": o.occupations_bare,
                    "screened": o.occupations_screened,
                }
                for o in observations
            ],
        }

    monkeypatch.setattr(runner, "_execute_siesta", siesta)
    monkeypatch.setattr(runner.observations, "verified_observations", verified)
    monkeypatch.setattr(runner.observations, "response_observation_dataset", dataset)
    monkeypatch.setattr(runner, "_analysis_input_provenance", dict)
    monkeypatch.setattr(runner, "_revalidate_reuse", lambda: None)
    if runner.shadow is not None and complete_synthetic_state:
        # All synthetic orbital/gap/state curves are prescribed constant with
        # a unique branch. This oracle is injected only in tests; the runtime
        # has no parameter or flag permitting an incomplete I.5 gate to pass.
        monkeypatch.setattr(runner.shadow, "_complete_state_gate", lambda *_: True)
    return runner, executed, heartbeat


def _analysis(root: Path) -> dict[str, Any]:
    return json.loads((root / "results" / "lr_u_analysis.v3.json").read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def test_runner_all_pass_reconstructs_raw_matrices_and_preserves_direct_shadow(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner, executed, heartbeat = _runner(tmp_path, monkeypatch, _plan())
    assert runner.advance("run", heartbeat) == 0
    assert len(executed) == 1 + 2 * 4 * 2
    analysis = _analysis(tmp_path)
    np.testing.assert_allclose(analysis["primary"]["chi0_raw"], np.full((4, 4), -0.25) - np.eye(4) * 1.75)
    np.testing.assert_allclose(analysis["primary"]["chi_raw"], np.full((4, 4), -0.1) - np.eye(4) * 0.9)
    direct = analysis["response_observation_dataset"]
    assert len(direct["rows"]) == 8
    shadow = direct["translation_shadow"]
    assert shadow["outcomes"][0]["status"] == "PROVEN"
    assert len(shadow["outcomes"][0]["comparisons"]) == 8
    assert shadow["direct_data_retained"] is True
    np.testing.assert_allclose(
        shadow["reconstructed_raw_matrices"]["chi_raw"], analysis["primary"]["chi_raw"]
    )


def test_failed_shadow_expands_and_equals_explicit_raw_matrix(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _plan()
    reduced, executed, heartbeat = _runner(tmp_path / "reduced", monkeypatch, plan, fail=True)
    assert reduced.advance("run", heartbeat) == 0
    explicit, all_executed, all_heartbeat = _runner(
        tmp_path / "explicit", monkeypatch, plan, fail=True, coverage="DISABLED"
    )
    assert explicit.advance("run", all_heartbeat) == 0
    assert len(executed) == len(all_executed) == 33
    assert len(set(executed)) == len(executed)  # valid representative and shadow runs are reused
    actual = _analysis(tmp_path / "reduced")
    expected = _analysis(tmp_path / "explicit")
    assert actual["primary"] == expected["primary"]
    shadow = actual["response_observation_dataset"]["translation_shadow"]
    assert shadow["outcomes"][0]["status"] == "REJECTED_EXPANDED"
    assert shadow["outcomes"][0]["reason"] == "OUTSIDE_PRINT_BOUNDS"
    assert len(shadow["outcomes"][0]["comparisons"]) == 8


def test_store_uses_post_expansion_checkpoint_and_round_trips_records(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner, _, _ = _runner(tmp_path, monkeypatch, _plan(), fail=True)
    assert runner.shadow is not None
    initial_checkpoint = runner.executor.checkpoint

    for node in runner.dag.nodes:
        if node.kind.value == "PERTURBATION":
            runner._record_receipt(node, NodeReceipt(node.node_id, NodeState.VALIDATED, DIGEST))

    # The real barrier observes incomplete evidence, expands the plan, and
    # installs a replacement executor after the runner/store already exist.
    assert runner.shadow.prepare(runner) is False
    assert runner.executor.checkpoint is not initial_checkpoint

    node = runner.dag.nodes[0]
    receipt = NodeReceipt(node.node_id, NodeState.VALIDATED, DIGEST)
    runner._record_receipt(node, receipt, {"kind": "post-expansion-store-test"})
    assert runner.checkpoint()[node.node_id] == receipt

    reloaded = CampaignStore(runner.records_path, lambda: runner.executor.checkpoint)
    records = reloaded.load_records(runner._identity())
    assert records[node.node_id]["kind"] == "post-expansion-store-test"
    assert reloaded.checkpoint()[node.node_id] == receipt


def test_real_observation_assembler_reads_nodes_added_by_shadow_expansion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner, _, _ = _runner(tmp_path, monkeypatch, _plan(), fail=True)
    assert runner.shadow is not None
    for node in runner.dag.nodes:
        if node.perturbation is not None:
            runner._record_receipt(node, NodeReceipt(node.node_id, NodeState.VALIDATED, DIGEST))

    # This real barrier rejects the synthetic shadow and installs the expanded graph.
    assert runner.shadow.prepare(runner) is False
    expanded_ids = {node.node_id for node in runner.dag.nodes if node.perturbation is not None}
    assert len(expanded_ids) == len(runner.sites) * len(runner.alpha_grid) * 2

    # Replace the shadow-test oracle with the production assembler after graph replacement.
    runner.observations = ObservationAssembler()
    runner.admitted = cast(
        Any,
        SimpleNamespace(factory=SimpleNamespace(bare_profile=Siesta542PotentialShiftHamiltonianProfile())),
    )
    pseudo_dir = tmp_path / "pseudos"
    pseudo_dir.mkdir()
    pseudo_hashes: dict[str, str] = {}
    pseudo_paths: dict[str, str] = {}
    for site in runner.sites:
        pseudo = pseudo_dir / f"{site['site_id']}.psml"
        pseudo.write_text("verified synthetic PSML placeholder\n", encoding="utf-8")
        pseudo_paths[site["site_id"]] = str(pseudo)
        pseudo_hashes[pseudo.relative_to(tmp_path).as_posix()] = sha256(pseudo.read_bytes()).hexdigest()
    runner.config = {"pseudopotentials": pseudo_paths}
    runner._input_sha256_by_path = pseudo_hashes

    projection_rows: list[str] = []
    for site in runner.sites:
        projection_rows.extend((f"{site['site_id']} 1", "1 0", "0.0 0.0", "2.0 0.2"))
    fdf_text = (
        f"NumberOfAtoms {len(runner.sites)}\nSpin non-polarized\n"
        "%block DFTU.Proj\n" + "\n".join(projection_rows) + "\n%endblock DFTU.Proj\n"
    )

    def population_event(occupation: float) -> str:
        rows = ["hubbard_term: recalculating local occupations 1"]
        for atom_index in range(1, len(runner.sites) + 1):
            rows.extend(
                (
                    f"hubbard_term: atom, species: {atom_index} 1",
                    f"1 1 {occupation:.6f}",
                    f"Occupations: {occupation:.6f} {occupation:.6f}",
                )
            )
        rows.append("recalculating Hamiltonian")
        return "\n".join(rows)

    reference_output = (
        "\n".join(
            (
                "redata: Spin configuration = none",
                "redata: Number of spin components = 1",
                "redata: Time-Reversal Symmetry = T",
                "SCF Convergence by density criterion",
                "Using DM_out to compute the final energy and forces",
                population_event(0.500000),
                "Job completed",
                "siesta: normal completion",
            )
        )
        + "\n"
    )
    dm_hash = sha256(b"reference density matrix\n").hexdigest()

    def register(node: LRDagNode) -> NodeReceipt:
        node_dir = tmp_path / "assembled" / sha256(node.node_id.encode()).hexdigest()[:16]
        node_dir.mkdir(parents=True)
        fdf_path = node_dir / "input.fdf"
        out_path = node_dir / "siesta.out"
        dm_path = node_dir / "run.DM"
        fdf_path.write_text(fdf_text, encoding="utf-8")
        if node.perturbation is None:
            out_path.write_text(reference_output, encoding="utf-8")
            dm_path.write_bytes(b"reference density matrix\n")
            artifact_spec = {"dm": "run.DM"}
            semantic: dict[str, Any] = {}
        else:
            spec = node.perturbation
            if spec.mode is ResponseMode.BARE:
                output = (
                    "\n".join(
                        (
                            "redata: SCF mix quantity = Hamiltonian",
                            population_event(0.500000),
                            "stepf: Fermi-Dirac step function",
                            population_event(0.490000),
                            "scf: 1",
                            "siesta: normal completion",
                        )
                    )
                    + "\n"
                )
            else:
                output = (
                    "\n".join(
                        (
                            "redata: Spin configuration = none",
                            "redata: Number of spin components = 1",
                            "redata: Time-Reversal Symmetry = T",
                            "SCF Convergence by density criterion",
                            "Using DM_out to compute the final energy and forces",
                            population_event(0.490000),
                            "Job completed",
                            "siesta: normal completion",
                        )
                    )
                    + "\n"
                )
            out_path.write_text(output, encoding="utf-8")
            dm_path.write_bytes(f"{node.node_id}\n".encode())
            parent_path = node_dir / "reference.DM"
            parent_path.write_bytes(b"reference density matrix\n")
            artifact_spec = {"dm": "run.DM", "reference_dm": "reference.DM"}
            semantic = {"reference_dm_sha256": dm_hash}

        digest = sha256(node.node_id.encode()).hexdigest()
        artifacts = {
            "fdf": sha256(fdf_path.read_bytes()).hexdigest(),
            "output": sha256(out_path.read_bytes()).hexdigest(),
            "dm": sha256(dm_path.read_bytes()).hexdigest(),
        }
        runner.records[node.node_id] = {
            "evidence_digest": digest,
            "artifact_spec": artifact_spec,
            "command": {
                "cwd": str(node_dir),
                "stdin_path": str(fdf_path),
                "stdout_path": str(out_path),
            },
            "provenance": {"artifacts": artifacts, "semantic": semantic},
            "reference_dm_sha256": dm_hash if node.perturbation is not None else None,
        }
        return NodeReceipt(node.node_id, NodeState.VALIDATED, digest)

    receipts = {
        node.node_id: register(node)
        for node in runner.dag.nodes
        if node.node_id == "reference" or node.node_id in expanded_ids
    }
    runner.executor.checkpoint.save(receipts)

    observations, _, _, _, _ = runner.shadow._data(runner)
    assert {observation.perturbation_site for observation in observations} == set(range(len(runner.sites)))
    assert len(observations) == len(runner.sites) * len(runner.alpha_grid)


def test_production_without_complete_orbital_gap_and_smoothness_gate_expands(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner, executed, heartbeat = _runner(tmp_path, monkeypatch, _plan(), complete_synthetic_state=False)
    assert runner.advance("run", heartbeat) == 0
    assert len(executed) == 33
    shadow = _analysis(tmp_path)["response_observation_dataset"]["translation_shadow"]
    assert shadow["complete_state_gate"] == "NOT_ESTABLISHED"
    assert shadow["outcomes"][0]["status"] == "REJECTED_EXPANDED"
    assert shadow["outcomes"][0]["reason"] == "SCIENTIFIC_STATE_NOT_ESTABLISHED"
    assert len(shadow["outcomes"][0]["comparisons"]) == 8


def test_mno_like_16_to_one_candidate_has_two_direct_columns() -> None:
    plan = _plan(16)
    dag, specs = build_shadow_dag(plan, ())
    assert plan.coverage.would_reduce_to == 1
    assert len({s.site_index for s in specs.values()}) == 2  # mandatory shadow counted in D2
    assert len(dag.nodes) == 19
    assert {s.purpose for s in specs.values()} == {"representative", "shadow"}


def test_resume_after_interruption_reuses_valid_runs_and_replays_barrier(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _plan()
    runner, executed, heartbeat = _runner(tmp_path, monkeypatch, plan, stop_after=6)
    assert runner.advance("run", heartbeat) == 0
    assert len(executed) == 6
    (runner.control / "stop-request.json").unlink()
    resumed, more, more_heartbeat = _runner(tmp_path, monkeypatch, plan)
    assert resumed.advance("resume", more_heartbeat) == 0
    assert len(executed) + len(more) == 17
    assert not set(executed) & set(more)
    completed, again, again_heartbeat = _runner(tmp_path, monkeypatch, plan)
    assert completed.advance("resume", again_heartbeat) == 0
    assert again == []
    assert (
        _analysis(tmp_path)["response_observation_dataset"]["translation_shadow"]["outcomes"][0]["status"]
        == "PROVEN"
    )


def test_resume_after_expansion_keeps_full_class(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _plan()
    runner, _, heartbeat = _runner(tmp_path, monkeypatch, plan, fail=True, stop_after=20)
    assert runner.advance("run", heartbeat) == 0
    (runner.control / "stop-request.json").unlink()
    resumed, executed, resumed_heartbeat = _runner(tmp_path, monkeypatch, plan, fail=True)
    assert resumed.shadow is not None
    assert resumed.shadow.expanded == tuple(s.site_id for s in plan.inventory.subspaces)
    assert resumed.advance("resume", resumed_heartbeat) == 0
    assert len(executed) == 13


def test_invalid_shadow_receipt_is_retried_explicitly_and_never_reused(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner, executed, heartbeat = _runner(tmp_path, monkeypatch, _plan(), invalid_shadow=True)
    assert runner.advance("run", heartbeat) == 1  # persistent invalid explicit response fails closed
    retried = [n for n in set(executed) if executed.count(n) == 2]
    assert len(retried) == 1
    assert runner.shadow is not None and len(runner.shadow.expanded) == 4
    assert runner.shadow.failed_runs[0]["receipt"]["state"] == "FAILED_OUTPUT_VALIDATION"
    assert "reason" not in json.loads((runner.control / "state.json").read_text(encoding="utf-8"))


def test_stop_policy_rejects_shadow_without_installing_expansion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner, executed, heartbeat = _runner(
        tmp_path, monkeypatch, _plan(), invalid_shadow=True, rejection_policy="STOP"
    )
    assert runner.advance("run", heartbeat) == 1
    assert len(executed) == 10  # stops after the first invalid shadow response
    assert runner.shadow is not None and runner.shadow.expanded == ()
    assert (
        json.loads((runner.control / "state.json").read_text(encoding="utf-8"))["reason"] == "SHADOW_REJECTED"
    )
    gate = json.loads((runner.results / "i5_state_gate.json").read_text(encoding="utf-8"))
    assert gate["schema_version"] == "hubbardflow.i5_state_gate.v1"
    state = json.loads((runner.control / "translation-shadow-state.json").read_text(encoding="utf-8"))
    assert state["outcomes"][0]["status"] == "REJECTED_EXPANDED"


def test_stop_policy_prepare_rejection_runs_once_and_does_not_expand(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner, executed, heartbeat = _runner(tmp_path, monkeypatch, _plan(), fail=True, rejection_policy="STOP")
    assert runner.shadow is not None
    prepares = 0
    original_prepare = runner.shadow.prepare

    def counted_prepare(current: CampaignRunner) -> bool:
        nonlocal prepares
        prepares += 1
        return original_prepare(current)

    monkeypatch.setattr(runner.shadow, "prepare", counted_prepare)
    assert runner.advance("run", heartbeat) == 1
    assert prepares == 1
    assert len(executed) == 17
    assert runner.shadow.expanded == ()
    assert (
        json.loads((runner.control / "state.json").read_text(encoding="utf-8"))["reason"] == "SHADOW_REJECTED"
    )


def test_parent_dm_digest_never_stops_perturbations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _plan()
    for matches in (False, True):
        case_root = tmp_path / ("match" if matches else "mismatch")
        runner, executed, heartbeat = _runner(case_root, monkeypatch, plan)
        runner.perturbation_plan = plan
        runner.config["parent_reproduction"] = "PRINT_EQUIVALENT"
        original_execute = runner._execute_siesta
        dm_path = case_root / "parent.DM"
        dm_path.parent.mkdir(parents=True, exist_ok=True)

        def execute_with_parent_check(
            node: LRDagNode,
            current: _Heartbeat,
            *,
            current_runner: CampaignRunner = runner,
            current_dm_path: Path = dm_path,
            current_matches: bool = matches,
            current_execute: Any = original_execute,
        ) -> NodeReceipt:
            if node.kind is LRNodeKind.REFERENCE:
                current_dm_path.write_bytes(
                    b"declared synthetic reference" if current_matches else b"different parent DM"
                )
                reproduction = current_runner._reference_reproduction_evidence(
                    current_dm_path, current_dm_path.parent / "siesta.out"
                )
                if reproduction.rejects_reduction:
                    receipt = NodeReceipt(node.node_id, NodeState.FAILED_OUTPUT_VALIDATION, DIGEST)
                    current_runner._record_receipt(
                        node,
                        receipt,
                        {
                            "kind": "siesta_failure",
                            "reason": reproduction.reason.value,
                            "expected_parent_dm_sha256": reproduction.planning_parent_dm_sha256,
                            "observed_parent_dm_sha256": reproduction.campaign_parent_dm_sha256,
                            "reference_reproduction": reproduction.to_mapping(),
                        },
                    )
                    return receipt
            return cast(NodeReceipt, current_execute(node, current))

        monkeypatch.setattr(runner, "_execute_siesta", execute_with_parent_check)
        result = runner.advance("run", heartbeat)
        assert result == 0
        assert any(node_id != "reference" for node_id in executed)


def test_shadow_parent_digest_mismatch_is_traceability_warning_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _plan()
    runner, _, _ = _runner(tmp_path, monkeypatch, plan)
    assert runner.shadow is not None
    runner.records["reference"] = {"provenance": {"artifacts": {"dm": DIGEST}}}
    observations, widths = _observations(plan, {0, 1})
    data: tuple[
        list[ResponseObservation],
        dict[float, str] | None,
        dict[str, Any],
        dict[tuple[int, float, str], list[float]],
        list[float] | None,
    ] = (observations, {a: "reference_branch" for a in runner.alpha_grid}, {}, widths, [5e-8] * 4)
    assert all(item.status is CoverageStatus.PROVEN for item in runner.shadow._outcomes(runner, data))
    runner.records["reference"]["provenance"]["artifacts"]["dm"] = "f" * 64
    assert all(item.status is CoverageStatus.PROVEN for item in runner.shadow._outcomes(runner, data))
    warnings = runner.shadow._parent_dm_digest_warnings(runner, observations)
    assert warnings
    assert {row["reason_code"] for row in warnings} == {"PARENT_DM_DIGEST_MISMATCH"}


@pytest.mark.parametrize("validator_state", [NodeState.VALIDATED, NodeState.FAILED_OUTPUT_VALIDATION])
def test_unparseable_reference_records_digests_without_hash_rejection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    validator_state: NodeState,
) -> None:
    """Exercise the real runner gate with a receipt-only adapter; no subprocess runs."""
    runner, _, heartbeat = _runner(tmp_path, monkeypatch, _plan(), rejection_policy="STOP")
    runner.perturbation_plan = _plan()
    planning_output = tmp_path / "planning.out"
    output_path = tmp_path / "observed.out"
    planning_output.write_text("unsupported reference", encoding="utf-8")
    output_path.write_text("unsupported reference", encoding="utf-8")
    dm_path = tmp_path / "observed.DM"
    dm_path.write_bytes(b"different recalculated reference DM")
    runner.config.update(
        {"planning_reference_output": str(planning_output), "parent_reproduction": "PRINT_EQUIVALENT"}
    )
    command = SimpleNamespace(
        cwd=tmp_path,
        argv=(),
        stdin_path=tmp_path / "input.fdf",
        stdout_path=output_path,
        stderr_path=None,
    )
    parented: list[Path] = []
    runner.factory = cast(
        Any,
        SimpleNamespace(
            command_for=lambda _: command,
            prepare=lambda _: None,
            reference_completed=lambda path, _: parented.append(path),
        ),
    )
    runner.admitted = cast(
        Any,
        SimpleNamespace(
            factory=SimpleNamespace(
                artifacts=defaultdict(
                    lambda: SiestaArtifactSpec("input.fdf", "observed.out", "observed.DM", "fake")
                )
            ),
            validator=SimpleNamespace(last_provenance={}),
        ),
    )
    runner.profile = cast(Any, SimpleNamespace(target="local_wsl"))
    runner.environment = {}
    runner.resource_lock_path = tmp_path / "resource.lock"
    calls: list[str] = []

    class ReceiptOnlyAdapter:
        def __init__(self, factory: Any, validator: Any, env: Any) -> None:
            self.factory = factory

        def execute(self, node: LRDagNode) -> NodeReceipt:
            calls.append(node.node_id)
            self.factory.command_for(node)
            return NodeReceipt(node.node_id, validator_state, DIGEST)

    monkeypatch.setattr("hubbardflow.execution.runtime_adapters.LocalSubprocessExecutor", ReceiptOnlyAdapter)
    monkeypatch.setattr(
        "hubbardflow.execution.campaign_runner.fcntl",
        SimpleNamespace(
            LOCK_EX=1,
            LOCK_UN=2,
            flock=lambda *_: None,
        ),
    )
    monkeypatch.setattr(
        runner, "_execute_siesta", lambda node, current: CampaignRunner._execute_siesta(runner, node, current)
    )
    result = runner.advance("run", heartbeat)
    assert result == (0 if validator_state is NodeState.VALIDATED else 1)
    assert calls[0] == "reference"
    assert parented == ([dm_path] if validator_state is NodeState.VALIDATED else [])
    assert runner.shadow is not None and runner.shadow.expanded == ()
    record = runner.records["reference"]
    evidence = record["reference_reproduction"]
    assert evidence["planning_parent_dm_sha256"] == runner.perturbation_plan.reference.parent_dm_sha256
    assert evidence["campaign_parent_dm_sha256"] == sha256(dm_path.read_bytes()).hexdigest()
    assert evidence["reason"] == "EQUIVALENCE_NOT_ASSESSED"
    if validator_state is NodeState.VALIDATED:
        assert len(calls) > 1


def test_transient_invalid_shadow_retries_only_invalid_run_then_completes_expansion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner, executed, heartbeat = _runner(tmp_path, monkeypatch, _plan(), invalid_shadow_once=True)
    assert runner.advance("run", heartbeat) == 0
    assert len(executed) == 34
    assert len(set(executed)) == 33
    assert runner.shadow is not None and len(runner.shadow.expanded) == 4
    assert len(runner.shadow.failed_runs) == 1
    assert (
        _analysis(tmp_path)["response_observation_dataset"]["translation_shadow"]["outcomes"][0]["status"]
        == "REJECTED_EXPANDED"
    )


def test_disabled_and_diagnostic_analysis_bytes_and_dag_identity_unchanged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outputs = []
    digests = []
    for mode in ("DISABLED", "DIAGNOSTIC"):
        runner, executed, heartbeat = _runner(tmp_path / mode, monkeypatch, _plan(), coverage=mode)
        assert runner.advance("run", heartbeat) == 0
        assert len(executed) == 33
        outputs.append((runner.results / "lr_u_analysis.v3.json").read_bytes())
        digests.append(dag_digest(runner.dag))
    assert outputs[0] == outputs[1]
    assert digests[0] == digests[1]


def test_print_budget_boundary_is_inclusive_without_relative_or_occupation_cutoff() -> None:
    comparison = ShadowComparison("s0", ResponseMode.BARE, 0.25, 0, 0.125, 0.125)
    assert comparison.passed
    assert not replace(comparison, direct_e_per_ev=np.nextafter(0.25, 1)).passed
    outcome = ShadowOutcome(
        "s0", "s1", CoverageStatus.PROVEN, (comparison,), ShadowReason.WITHIN_PRINT_BOUNDS
    )
    assert ShadowOutcome.from_mapping(outcome.to_mapping()) == outcome


@given(st.permutations((-0.02, -0.01, 0.01, 0.02)))
def test_print_budget_input_order_invariance(alphas: tuple[float, ...]) -> None:
    points = tuple(PointObservation(a, 1 + a * -2, 5e-8) for a in alphas)
    series = ElementSeries("s0", ResponseMode.BARE, "s0", 1, 5e-8, points)
    estimator = EstimatorSpec(EstimatorKind.LINEAR_LSQ, None, (0.01, 0.02))
    assert printed_response_budget(series, estimator) == printed_response_budget(
        replace(series, points=tuple(reversed(points))), estimator
    )


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_shadow_evidence_rejected(bad: float) -> None:
    with pytest.raises(ValueError):
        ShadowComparison("s0", ResponseMode.BARE, bad, 0, 0.1, 0.1)
    with pytest.raises(ValueError):
        ShadowComparison("s0", ResponseMode.BARE, 0, 0, bad, 0.1)


def test_overflowing_additive_bounds_or_residual_cannot_authorize_shadow() -> None:
    with pytest.raises(ValueError, match="summed bounds"):
        ShadowComparison("s0", ResponseMode.BARE, 0, 0, 1e308, 1e308)
    with pytest.raises(ValueError, match="shadow residual"):
        ShadowComparison("s0", ResponseMode.BARE, 1e308, -1e308, 1, 1)


@given(st.tuples(*(st.integers(-5, 5) for _ in range(4))))
def test_print_bound_covers_known_linear_truth_with_declared_point_errors(
    errors: tuple[int, int, int, int],
) -> None:
    points = tuple(
        PointObservation(alpha, float(1 - 2 * Fraction(str(alpha)) + Fraction(error, 100000000)), 5e-8)
        for alpha, error in zip((-0.02, -0.01, 0.01, 0.02), errors, strict=True)
    )
    budget = printed_response_budget(
        ElementSeries("s0", ResponseMode.BARE, "s0", 1, 5e-8, points),
        EstimatorSpec(EstimatorKind.LINEAR_LSQ, None, (0.01, 0.02)),
    )
    assert abs(budget.estimate_e_per_ev + 2) <= budget.print_bound_e_per_ev


def test_wrong_parent_dm_digest_does_not_veto_complete_synthetic_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner, _, _ = _runner(tmp_path, monkeypatch, _plan())
    assert runner.shadow is not None
    runner.records["reference"] = {"provenance": {"artifacts": {"dm": "f" * 64}}}
    observations, widths = _observations(runner.shadow.plan, {0, 1})
    data: tuple[
        list[ResponseObservation],
        dict[float, str],
        dict[str, Any],
        dict[tuple[int, float, str], list[float]],
        list[float],
    ] = (
        [replace(o, parent_dm_sha256="0" * 64) for o in observations],
        {a: "reference_branch" for a in runner.alpha_grid},
        {},
        widths,
        [5e-8] * 4,
    )
    outcome = runner.shadow._outcomes(runner, data)[0]
    assert outcome.status is CoverageStatus.PROVEN


def test_missing_widths_state_or_parent_evidence_expands_without_thresholds() -> None:
    plan = _plan()
    observations, widths = _observations(plan, {0, 1})
    series = observation_series(plan, observations, widths, [5e-8] * 4)
    assert (
        qualify_shadows(plan, series, scientific_state_valid=False)[0].status
        is CoverageStatus.REJECTED_EXPANDED
    )
    incomplete = observation_series(plan, observations, {}, None)
    assert (
        qualify_shadows(plan, incomplete, scientific_state_valid=True)[0].reason
        is ShadowReason.INCOMPLETE_RESPONSE_EVIDENCE
    )


def test_resume_rejects_plan_change_or_partial_expansion(tmp_path: Path) -> None:
    plan = _plan()
    controller = CampaignShadow(plan, tmp_path, DIGEST)
    controller.path.write_text(
        json.dumps(
            {
                "schema": "hubbardflow.translation_shadow_state.v1",
                "plan_digest": plan.digest,
                "expanded": [plan.inventory.subspaces[-1].site_id],
                "outcomes": [],
                "failed_runs": [],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ExecutionContractError, match="every member"):
        CampaignShadow(plan, tmp_path, DIGEST)
    changed = replace(plan, planner_version="different-v2")
    with pytest.raises(ExecutionContractError, match="frozen plan"):
        CampaignShadow(changed, tmp_path, DIGEST)


def test_resume_rejects_nonfinite_values_inside_preserved_failure_records(tmp_path: Path) -> None:
    plan = _plan()
    controller = CampaignShadow(plan, tmp_path, DIGEST)
    controller.path.write_text(
        json.dumps(
            {
                "schema": "hubbardflow.translation_shadow_state.v1",
                "plan_digest": plan.digest,
                "expanded": [],
                "outcomes": [],
                "failed_runs": [
                    {"node_id": "failed-shadow", "receipt": {}, "record": {"occupation_e": float("nan")}}
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ExecutionContractError, match="JSON compliant"):
        CampaignShadow(plan, tmp_path, DIGEST)


@pytest.mark.parametrize("failure_kind", ["occupation", "identity", "fermi"])
def test_reference_difference_expands_every_affected_class_using_typed_indices(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_kind: str,
) -> None:
    from hubbardflow.domain.reference_reproduction import (
        ParentReproduction,
        ReferenceReproduction,
        ReproductionReason,
    )

    original = _plan(12)
    prototype = _plan().coverage.classes[0]
    assert prototype.reduced
    classes = tuple(
        replace(
            prototype,
            members=tuple(f"s{i}" for i in range(start, start + 4)),
            representative=f"s{start}",
            shadow=f"s{start + 1}",
            ops_rep_to_member=(),
        )
        for start in (0, 4, 8)
    )
    # Exercise fallback localization independently of translation discovery.
    # The existing end-to-end tests verify install builds direct response DAGs.
    plan = cast(
        Any,
        SimpleNamespace(
            inventory=original.inventory, coverage=SimpleNamespace(classes=classes), digest=original.digest
        ),
    )
    shadow = CampaignShadow(plan, tmp_path, DIGEST)
    runner = cast(Any, SimpleNamespace(shadow=shadow))
    installed = []
    monkeypatch.setattr(shadow, "install", lambda current: installed.append(current))
    evidence = ReferenceReproduction(
        ParentReproduction.PRINT_EQUIVALENT,
        {
            "occupation": ReproductionReason.PARENT_STATE_NOT_EQUIVALENT,
            "identity": ReproductionReason.PARENT_IDENTITY_NOT_ESTABLISHED,
            "fermi": ReproductionReason.PARENT_FERMI_NOT_EQUIVALENT,
        }[failure_kind],
        DIGEST,
        "f" * 64,
        "atom 1 is the first detail only",
        affected_atom_indices=(1, 5) if failure_kind != "fermi" else (),
        all_reduced_classes_affected=failure_kind != "occupation",
    )
    runner.shadow.expand_for_reference_difference(runner, evidence.to_mapping())
    expected = tuple(f"s{i}" for i in range(8 if failure_kind == "occupation" else 12))
    assert runner.shadow.expanded == expected
    assert installed == [runner]
    stored = json.loads(runner.shadow.path.read_text(encoding="utf-8"))
    assert tuple(stored["expanded"]) == expected
    assert {item["representative"] for item in stored["outcomes"]} == (
        {"s0", "s4"} if failure_kind == "occupation" else {"s0", "s4", "s8"}
    )
    assert {item["reason"] for item in stored["outcomes"]} == {
        "REFERENCE_FERMI_NOT_EQUIVALENT" if failure_kind == "fermi" else "REFERENCE_STATE_NOT_EQUIVALENT"
    }
