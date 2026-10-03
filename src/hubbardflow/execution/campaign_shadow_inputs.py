"""Translate canonical plan identities into backend columns and printed series."""

from __future__ import annotations

from collections.abc import Sequence

from hubbardflow.domain.matrix_lr import ResponseObservation
from hubbardflow.domain.perturbation_plan import ResolvedPerturbationPlan
from hubbardflow.domain.response_error_budget import ElementSeries, PointObservation
from hubbardflow.domain.symmetry_reduction import PerturbationSpec, ResponseMode
from hubbardflow.execution.generic_executor import ExecutionContractError
from hubbardflow.execution.lr_dag import LRDag, LRDagNode, LRNodeKind


def build_shadow_dag(
    plan: ResolvedPerturbationPlan, expanded: Sequence[str]
) -> tuple[LRDag, dict[str, PerturbationSpec]]:
    """Stable coordinate IDs allow receipts to survive monotone class expansion."""
    sites = tuple(s.site_id for s in plan.inventory.subspaces)
    computed = set(plan.computed_columns) | set(expanded)
    if not computed <= set(sites):
        raise ExecutionContractError("shadow expansion contains an unknown inventory site")
    columns = {(c.site_id, c.mode): c for c in plan.response_protocol.columns}
    reference = LRDagNode("reference", LRNodeKind.REFERENCE, ())
    responses = []
    specs = {}
    for i, site in enumerate(sites):
        if site not in computed:
            continue
        group = next(c for c in plan.coverage.classes if site in c.members)
        purpose = (
            "representative"
            if group.reduced and site == group.representative
            else ("shadow" if group.reduced and site == group.shadow else "explicit_fallback")
        )
        for mode in ResponseMode:
            column = columns[(site, mode)]
            for alpha in sorted(a for magnitude in column.amplitudes_ev for a in (-magnitude, magnitude)):
                token = ("p" if alpha > 0 else "m") + f"{abs(alpha):.12g}".replace(".", "p")
                run_id = f"lr_s{i:03d}_{token}_{mode.value.lower()}"
                spec = PerturbationSpec(
                    run_id,
                    group.representative,
                    i,
                    plan.inventory.subspaces[i].species_label,
                    mode,
                    alpha,
                    purpose,
                )
                node_id = f"response:{run_id}"
                specs[node_id] = spec
                responses.append(LRDagNode(node_id, LRNodeKind.PERTURBATION, ("reference",), spec))
    gate = LRDagNode("alpha-diagnostic-gate", LRNodeKind.ALPHA_GATE, tuple(n.node_id for n in responses))
    analysis = LRDagNode("matrix-analysis", LRNodeKind.MATRIX_ANALYSIS, (gate.node_id,))
    return LRDag((reference, *responses, gate, analysis), False, False), specs


def observation_series(
    plan: ResolvedPerturbationPlan,
    observations: Sequence[ResponseObservation],
    widths: dict[tuple[int, float, str], list[float]],
    reference_widths: list[float] | None,
) -> tuple[ElementSeries, ...]:
    """Keep absent print precision absent; missing rows force explicit expansion."""
    sites = tuple(s.site_id for s in plan.inventory.subspaces)
    if reference_widths is None:
        return ()
    if len(reference_widths) != len(sites):
        raise ExecutionContractError("reference precision must cover every inventory site")
    columns = {(c.site_id, c.mode): c for c in plan.response_protocol.columns}
    result = []
    for j in sorted({int(o.perturbation_site) for o in observations}):
        rows = {float(o.alpha): o for o in observations if o.perturbation_site == j}
        for mode in ResponseMode:
            column = columns[(sites[j], mode)]
            alphas = sorted(a for magnitude in column.amplitudes_ev for a in (-magnitude, magnitude))
            if any(a not in rows or (j, a, mode.value.lower()) not in widths for a in alphas):
                continue
            for i, site in enumerate(sites):
                points = []
                for alpha in alphas:
                    observation = rows[alpha]
                    values = (
                        observation.occupations_bare
                        if mode is ResponseMode.BARE
                        else (observation.occupations_screened)
                    )
                    points.append(
                        PointObservation(alpha, float(values[i]), widths[(j, alpha, mode.value.lower())][i])
                    )
                result.append(
                    ElementSeries(
                        sites[j],
                        mode,
                        site,
                        float(rows[alphas[0]].occupations_ref[i]),
                        reference_widths[i],
                        tuple(points),
                    )
                )
    return tuple(result)
