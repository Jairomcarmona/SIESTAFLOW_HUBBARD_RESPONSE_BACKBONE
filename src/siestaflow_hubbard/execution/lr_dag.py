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
from math import isclose

from siestaflow_hubbard.domain.adaptive_alpha import AdaptiveAlphaPolicy
from siestaflow_hubbard.domain.symmetry_reduction import (
    PerturbationSpec,
    ReductionState,
    SymmetryReductionPlan,
)


class LRNodeKind(str, Enum):
    REFERENCE = "REFERENCE"
    PERTURBATION = "PERTURBATION"
    ALPHA_GATE = "ALPHA_GATE"
    SHADOW_GATE = "SHADOW_GATE"
    MATRIX_ANALYSIS = "MATRIX_ANALYSIS"


@dataclass(frozen=True)
class LRDagNode:
    node_id: str
    kind: LRNodeKind
    dependencies: tuple[str, ...]
    perturbation: PerturbationSpec | None = None


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


def _alpha_tag(alpha_ev: float) -> str:
    sign = "p" if alpha_ev > 0.0 else "m"
    return f"{sign}{abs(alpha_ev):.12g}".replace(".", "p")


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
