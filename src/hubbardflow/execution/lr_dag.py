"""Backend- and scheduler-neutral DAG primitives for a finite-difference LR-U run.

The graph records scientific dependencies, rather than pretending that a
submission system can decide whether a symmetry assumption passed.  A runtime
executes this initial graph, records direct shadow observations, then either
authorizes matrix reconstruction or calls ``explicit_expansion_specs`` to
append only the scientifically necessary fallback nodes.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import re
from typing import Any, Mapping, Sequence
from math import isclose

from hubbardflow.domain.adaptive_alpha import AdaptiveAlphaPolicy
from hubbardflow.domain.symmetry_reduction import (
    PerturbationSpec,
    ReductionState,
    ResponseMode,
    SymmetryReductionPlan,
)


class LRNodeKind(str, Enum):
    REFERENCE = "REFERENCE"
    PERTURBATION = "PERTURBATION"
    ALPHA_GATE = "ALPHA_GATE"
    SHADOW_GATE = "SHADOW_GATE"
    MATRIX_ANALYSIS = "MATRIX_ANALYSIS"
    U_CERTIFICATION = "U_CERTIFICATION"
    U_RELEASE_GATE = "U_RELEASE_GATE"


@dataclass(frozen=True)
class LRDagNode:
    node_id: str
    kind: LRNodeKind
    dependencies: tuple[str, ...]
    perturbation: PerturbationSpec | None = None
    scf_level_id: str | None = None
    parent_dm_node_id: str | None = None


@dataclass(frozen=True)
class LRDag:
    nodes: tuple[LRDagNode, ...]
    analysis_requires_authorization: bool
    alpha_requires_authorization: bool = False

    def node(self, node_id: str) -> LRDagNode:
        return next(node for node in self.nodes if node.node_id == node_id)


def build_initial_lr_dag(plan: SymmetryReductionPlan) -> LRDag:
    """Create the reference and direct-response graph from a scientific plan."""
    reference = LRDagNode("reference", LRNodeKind.REFERENCE, ())
    response_nodes = tuple(
        LRDagNode(f"response:{spec.run_id}", LRNodeKind.PERTURBATION, ("reference",), spec)
        for spec in plan.perturbations
    )
    dependencies = tuple(node.node_id for node in response_nodes)
    if plan.state is ReductionState.SHADOW_VALIDATION_REQUIRED:
        gate = LRDagNode("symmetry-shadow-gate", LRNodeKind.SHADOW_GATE, dependencies)
        analysis = LRDagNode("matrix-analysis", LRNodeKind.MATRIX_ANALYSIS, (gate.node_id,))
        return LRDag((reference, *response_nodes, gate, analysis), True)
    analysis = LRDagNode("matrix-analysis", LRNodeKind.MATRIX_ANALYSIS, dependencies)
    return LRDag((reference, *response_nodes, analysis), False)


def append_u_release_nodes(dag: LRDag, analysis_node_id: str = "matrix-analysis") -> LRDag:
    """Append pure post-processing stages; neither stage launches SIESTA."""
    analysis = dag.node(analysis_node_id)
    certificate = LRDagNode("u-certification", LRNodeKind.U_CERTIFICATION, (analysis.node_id,))
    release = LRDagNode("u-release-gate", LRNodeKind.U_RELEASE_GATE, (certificate.node_id,))
    if any(node.node_id in {certificate.node_id, release.node_id} for node in dag.nodes):
        raise ValueError("U certification/release stages are already present")
    return LRDag((*dag.nodes, certificate, release), dag.analysis_requires_authorization,
                 dag.alpha_requires_authorization)


def _alpha_tag(alpha_ev: float) -> str:
    sign = "p" if alpha_ev > 0.0 else "m"
    return f"{sign}{abs(alpha_ev):.12g}".replace(".", "p")


def _node_part(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_.")[:40] or "item"


def _adaptive_response_node(
    site: Mapping[str, Any], site_index: int, alpha_ev: float, mode: ResponseMode,
    *, scf_level_id: str, parent_dm_node_id: str, dependencies: tuple[str, ...],
    identity_prefix: str, round_index: int,
    purpose: str,
) -> LRDagNode:
    run_id = (
        f"lr_s{site_index:03d}_{_alpha_tag(alpha_ev)}_{mode.value.lower()}"
        f"_scf_{_node_part(scf_level_id)}_parent_{_node_part(parent_dm_node_id)}"
    )
    spec = PerturbationSpec(
        run_id=run_id, orbit_id=str(site.get("orbit_id", site["site_id"])),
        site_index=site_index, site_id=str(site["site_id"]), mode=mode,
        alpha_ev=float(alpha_ev), purpose=purpose,
    )
    node_id = f"response:{identity_prefix}:r{round_index}:{run_id}"
    return LRDagNode(
        node_id, LRNodeKind.PERTURBATION, dependencies, spec,
        scf_level_id=scf_level_id, parent_dm_node_id=parent_dm_node_id,
    )


def build_adaptive_campaign_dag(
    sites: Sequence[Mapping[str, Any]],
    rounds: Sequence[Mapping[str, Any]],
    *,
    probe_plan: Mapping[str, Any] | None = None,
    scf_reruns: Sequence[Mapping[str, Any]] = (),
    campaign_id: str = "",
    policy_digest: str = "",
) -> tuple[LRDag, dict[str, PerturbationSpec], dict[str, dict[str, str]]]:
    """Build the cumulative, resumable DAG described by durable round state.

    A response is keyed by site, alpha, mode, SCF level and reference-DM node.
    This makes strict-level probes reusable by a later consistent matrix pass
    while keeping base/strict observations distinct.
    """
    if not sites or not rounds:
        raise ValueError("adaptive DAG requires sites and at least the initial round")
    nodes: list[LRDagNode] = []
    specs: dict[str, PerturbationSpec] = {}
    metadata: dict[str, dict[str, str]] = {}
    identity_prefix = sha256(f"{campaign_id}\0{policy_digest}".encode()).hexdigest()[:16]
    references: dict[str, str] = {}
    response_nodes: dict[tuple[str, int, float, str], LRDagNode] = {}
    previous_final_gate: str | None = None

    def ensure_reference(level_id: str, after: str | None = None) -> str:
        existing = references.get(level_id)
        if existing is not None:
            return existing
        node_id = f"reference:adaptive:{identity_prefix}:{_node_part(level_id)}"
        dependencies = (after,) if after else ()
        nodes.append(LRDagNode(node_id, LRNodeKind.REFERENCE, dependencies, scf_level_id=level_id))
        references[level_id] = node_id
        return node_id

    def ensure_response(
        site_index: int, alpha: float, mode: ResponseMode, level_id: str,
        after: str | None, purpose: str, round_index: int,
    ) -> LRDagNode:
        reference_id = ensure_reference(level_id, after)
        key = (level_id, site_index, float(alpha), mode.value)
        existing = response_nodes.get(key)
        if existing is not None:
            return existing
        dependencies = (reference_id, after) if after and after != reference_id else (reference_id,)
        node = _adaptive_response_node(
            sites[site_index], site_index, float(alpha), mode,
            scf_level_id=level_id, parent_dm_node_id=reference_id,
            dependencies=dependencies, identity_prefix=identity_prefix,
            round_index=round_index, purpose=purpose,
        )
        nodes.append(node)
        response_nodes[key] = node
        specs[node.node_id] = node.perturbation  # type: ignore[assignment]
        metadata[node.node_id] = {"scf_level_id": level_id, "parent_dm_node_id": reference_id}
        return node

    for round_state in rounds:
        round_index = int(round_state["round_index"])
        alpha_grid = sorted({float(value) for value in round_state["alpha_grid_ev"]})
        level_id = str(round_state.get("scf_level_id", "base"))
        new_node_dependencies = previous_final_gate
        response_ids: list[str] = []
        for site_index in range(len(sites)):
            for alpha in alpha_grid:
                for mode in (ResponseMode.BARE, ResponseMode.SCREENED):
                    response = ensure_response(
                        site_index, alpha, mode, level_id, new_node_dependencies,
                        "adaptive_alpha_round", round_index,
                    )
                    response_ids.append(response.node_id)
        analysis_id = f"adaptive:round:{round_index}:analysis"
        nodes.append(LRDagNode(analysis_id, LRNodeKind.MATRIX_ANALYSIS, tuple(dict.fromkeys(response_ids)), scf_level_id=level_id))
        decision_id = f"adaptive:round:{round_index}:decision"
        nodes.append(LRDagNode(decision_id, LRNodeKind.ALPHA_GATE, (analysis_id,), scf_level_id=level_id))
        round_final_gate = decision_id

        if probe_plan is not None and int(probe_plan.get("round_index", -1)) == round_index:
            probe_level = str(probe_plan["scf_level_id"])
            affected = sorted({int(index) for index in probe_plan["site_indices"]})
            h_ev = float(probe_plan["h_eV"])
            probe_response_ids: list[str] = []
            for site_index in affected:
                for alpha in (-h_ev, h_ev):
                    for mode in (ResponseMode.BARE, ResponseMode.SCREENED):
                        response = ensure_response(
                            site_index, alpha, mode, probe_level, decision_id,
                            "adaptive_scf_noise_probe", round_index,
                        )
                        probe_response_ids.append(response.node_id)
            after_probe_id = f"adaptive:round:{round_index}:decision-after-probe"
            nodes.append(LRDagNode(
                after_probe_id, LRNodeKind.ALPHA_GATE,
                tuple(dict.fromkeys(probe_response_ids)), scf_level_id=probe_level,
            ))
            round_final_gate = after_probe_id

        for rerun in scf_reruns:
            if int(rerun["round_index"]) != round_index:
                continue
            rerun_level = str(rerun["scf_level_id"])
            rerun_grid = sorted({float(value) for value in rerun["alpha_grid_ev"]})
            response_ids: list[str] = []
            for site_index in range(len(sites)):
                for alpha in rerun_grid:
                    for mode in (ResponseMode.BARE, ResponseMode.SCREENED):
                        response = ensure_response(
                            site_index, alpha, mode, rerun_level, round_final_gate,
                            "adaptive_scf_consistent_rerun", round_index,
                        )
                        response_ids.append(response.node_id)
            rerun_analysis_id = f"adaptive:scf-rerun:{round_index}:analysis"
            nodes.append(LRDagNode(
                rerun_analysis_id, LRNodeKind.MATRIX_ANALYSIS,
                tuple(dict.fromkeys(response_ids)), scf_level_id=rerun_level,
            ))
            rerun_decision_id = f"adaptive:scf-rerun:{round_index}:decision"
            nodes.append(LRDagNode(
                rerun_decision_id, LRNodeKind.ALPHA_GATE,
                (rerun_analysis_id,), scf_level_id=rerun_level,
            ))
            round_final_gate = rerun_decision_id
        previous_final_gate = round_final_gate

    dag = LRDag(tuple(nodes), analysis_requires_authorization=False, alpha_requires_authorization=False)
    return dag, specs, metadata


def adaptive_alpha_perturbations(
    plan: SymmetryReductionPlan, policy: AdaptiveAlphaPolicy,
) -> tuple[PerturbationSpec, ...]:
    """Expand each direct response to ±h/2, ±h and ±2h.

    Alpha zero is represented exactly once by the reference node, never by a
    perturbation with an arbitrary BARE/SCREENED interpretation.  The policy
    must use the same nominal amplitude as the symmetry plan, otherwise the
    two scientific policies would refer to different experiments.
    """
    policy.validate()
    if not isclose(policy.initial_alpha_ev, plan.policy.alpha_ev, rel_tol=1e-12, abs_tol=0.0):
        raise ValueError("adaptive alpha nominal amplitude must match symmetry policy alpha_ev")
    output: list[PerturbationSpec] = []
    for base in plan.perturbations:
        direction = 1.0 if base.alpha_ev > 0.0 else -1.0
        for scale in (0.5, 1.0, 2.0):
            alpha_ev = direction * scale * policy.initial_alpha_ev
            output.append(
                PerturbationSpec(
                    run_id=f"{base.run_id}_alpha_{_alpha_tag(alpha_ev)}",
                    orbit_id=base.orbit_id,
                    site_index=base.site_index,
                    site_id=base.site_id,
                    mode=base.mode,
                    alpha_ev=alpha_ev,
                    purpose=f"{base.purpose}_alpha_scan",
                )
            )
    return tuple(output)


def build_adaptive_alpha_lr_dag(
    plan: SymmetryReductionPlan, policy: AdaptiveAlphaPolicy,
) -> LRDag:
    """Build a complete seven-point LR graph with an explicit alpha gate.

    A runtime must execute the alpha gate with real BARE and SCREENED
    occupations/magnetic evidence via ``authorize_alpha_window``.  It cannot
    validate the gate merely because all SIESTA processes exited normally.
    """
    reference = LRDagNode("reference", LRNodeKind.REFERENCE, ())
    response_nodes = tuple(
        LRDagNode(f"response:{spec.run_id}", LRNodeKind.PERTURBATION, ("reference",), spec)
        for spec in adaptive_alpha_perturbations(plan, policy)
    )
    response_ids = tuple(node.node_id for node in response_nodes)
    alpha_gate = LRDagNode("alpha-linearity-gate", LRNodeKind.ALPHA_GATE, response_ids)
    if plan.state is ReductionState.SHADOW_VALIDATION_REQUIRED:
        symmetry_gate = LRDagNode("symmetry-shadow-gate", LRNodeKind.SHADOW_GATE, (alpha_gate.node_id,))
        analysis = LRDagNode("matrix-analysis", LRNodeKind.MATRIX_ANALYSIS, (symmetry_gate.node_id,))
        return LRDag(
            (reference, *response_nodes, alpha_gate, symmetry_gate, analysis),
            analysis_requires_authorization=True,
            alpha_requires_authorization=True,
        )
    analysis = LRDagNode("matrix-analysis", LRNodeKind.MATRIX_ANALYSIS, (alpha_gate.node_id,))
    return LRDag(
        (reference, *response_nodes, alpha_gate, analysis),
        analysis_requires_authorization=False,
        alpha_requires_authorization=True,
    )


def append_explicit_fallback(dag: LRDag, fallback: tuple[PerturbationSpec, ...]) -> LRDag:
    """Append direct fallback nodes after a rejected symmetry gate.

    This function does not remove prior valid runs; a checkpoint-aware runtime
    can satisfy duplicate response nodes from its validated provenance record.
    """
    if not fallback:
        return dag
    analysis = dag.node("matrix-analysis")
    additions = tuple(
        LRDagNode(f"fallback:{spec.run_id}", LRNodeKind.PERTURBATION, ("reference",), spec)
        for spec in fallback
    )
    prior_responses = tuple(node.node_id for node in dag.nodes if node.kind is LRNodeKind.PERTURBATION)
    replacement = LRDagNode(
        analysis.node_id, analysis.kind,
        (*prior_responses, *(node.node_id for node in additions)), analysis.perturbation,
    )
    nodes = tuple(node for node in dag.nodes if node.node_id != analysis.node_id)
    return LRDag((*nodes, *additions, replacement), False, dag.alpha_requires_authorization)
