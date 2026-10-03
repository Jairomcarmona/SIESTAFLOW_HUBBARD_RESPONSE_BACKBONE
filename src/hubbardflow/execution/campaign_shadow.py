"""Plan-backed shadow barrier, expansion and restart for translation coverage.

The fixed all-column dispatcher never calls this adapter. Decisions are delegated
to domain functions; persisted expansion is monotone and never grants PROVEN.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Any

from hubbardflow.domain.coverage_models import CoverageStatus
from hubbardflow.domain.matrix_lr import ResponseObservation
from hubbardflow.domain.perturbation_plan import ResolvedPerturbationPlan
from hubbardflow.domain.response_shadow import (
    ShadowOutcome,
    ShadowReason,
    qualify_shadows,
    reconstruct_responses,
    response_budgets,
)
from hubbardflow.domain.symmetry_reduction import ResponseMode
from hubbardflow.execution.campaign_shadow_inputs import build_shadow_dag, observation_series
from hubbardflow.execution.generic_executor import ExecutionContractError, GenericDagExecutor
from hubbardflow.execution.lr_dag import LRDagNode

if TYPE_CHECKING:
    from hubbardflow.execution.campaign_runner import CampaignRunner


class CampaignShadow:
    """Monotone fallback state; qualification is recomputed from validated runs."""

    def __init__(self, plan: ResolvedPerturbationPlan, control: Path, input_identity: str):
        self.plan = plan
        self.path = control / "translation-shadow-state.json"
        self.identity = f"translation-shadow:{input_identity}:{plan.digest}"
        self.expanded: tuple[str, ...] = ()
        self.failed_runs: list[dict[str, Any]] = []
        if self.path.exists():
            try:
                row = json.loads(self.path.read_text(encoding="utf-8"))
                # Includes original failed-run records, not only active comparisons.
                json.dumps(row, allow_nan=False)
                if set(row) != {"schema", "plan_digest", "expanded", "outcomes", "failed_runs"} or (
                    row["schema"] != "hubbardflow.translation_shadow_state.v1"
                    or row["plan_digest"] != plan.digest
                    or not isinstance(row["expanded"], list)
                    or any(not isinstance(s, str) for s in row["expanded"])
                ):
                    raise ValueError("state does not match the frozen plan")
                expanded = tuple(row["expanded"])
                if not isinstance(row["failed_runs"], list) or any(
                    not isinstance(r, dict) or set(r) != {"node_id", "receipt", "record"}
                    for r in row["failed_runs"]
                ):
                    raise ValueError("failed runs must retain their original receipt and evidence record")
                self.failed_runs = row["failed_runs"]
                if not isinstance(row["outcomes"], list):
                    raise TypeError("outcomes must be an array of shadow comparisons")
                outcomes = tuple(ShadowOutcome.from_mapping(o) for o in row["outcomes"])
                known = {c.representative: c.shadow for c in plan.coverage.classes if c.reduced}
                if len({o.representative for o in outcomes}) != len(outcomes) or any(
                    known.get(o.representative) != o.shadow for o in outcomes
                ):
                    raise ValueError("outcomes must name unique planned shadow classes")
                sites = tuple(s.site_id for s in plan.inventory.subspaces)
                if len(set(expanded)) != len(expanded) or not set(expanded) <= set(sites):
                    raise ValueError("expanded sites must be unique inventory sites")
                for group in plan.coverage.classes:
                    overlap = set(group.members) & set(expanded)
                    if overlap and overlap != set(group.members):
                        raise ValueError("rejected class must expand every member")
                self.expanded = tuple(s for s in sites if s in expanded)
            except (OSError, ValueError, TypeError, KeyError) as exc:
                raise ExecutionContractError(f"invalid translation shadow resume state: {exc}") from exc

    def install(self, runner: CampaignRunner) -> None:
        runner.dag, runner.specs = build_shadow_dag(self.plan, self.expanded)
        runner.executor = GenericDagExecutor(
            runner.dag, runner.checkpoint_path, checkpoint_identity=self.identity
        )
        runner.checkpoint_identity = self.identity
        if set(runner.executor.checkpoint.load()) - {n.node_id for n in runner.dag.nodes}:
            raise ExecutionContractError("shadow state removed previously scheduled expansion nodes")

    def _persist(self, outcomes: Sequence[ShadowOutcome]) -> None:
        payload = {
            "schema": "hubbardflow.translation_shadow_state.v1",
            "plan_digest": self.plan.digest,
            "expanded": self.expanded,
            "outcomes": [o.to_mapping() for o in outcomes],
            "failed_runs": self.failed_runs,
        }
        temporary = self.path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(payload, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
        temporary.replace(self.path)

    def _expand(self, runner: CampaignRunner, outcomes: Sequence[ShadowOutcome]) -> bool:
        rejected = {o.representative for o in outcomes if o.status is CoverageStatus.REJECTED_EXPANDED}
        expanded = set(self.expanded) | {
            s for c in self.plan.coverage.classes if c.representative in rejected for s in c.members
        }
        changed = expanded != set(self.expanded)
        self.expanded = tuple(s.site_id for s in self.plan.inventory.subspaces if s.site_id in expanded)
        self._persist(outcomes)
        if changed:
            self.install(runner)
        return changed

    def failed_shadow(self, runner: CampaignRunner, node: LRDagNode) -> bool:
        """Invalid shadows cannot be reused during their class's explicit retry."""
        spec = node.perturbation
        if spec is None or spec.purpose != "shadow":
            return False
        site_id = self.plan.inventory.subspaces[spec.site_index].site_id
        if site_id in self.expanded:
            return False
        group = next(c for c in self.plan.coverage.classes if c.shadow == site_id)
        assert group.shadow is not None
        outcome = ShadowOutcome(
            group.representative,
            group.shadow,
            CoverageStatus.REJECTED_EXPANDED,
            (),
            ShadowReason.INCOMPLETE_RESPONSE_EVIDENCE,
        )
        failed = runner.checkpoint()[node.node_id]
        self.failed_runs.append(
            {
                "node_id": node.node_id,
                "receipt": {"state": failed.state.value, "evidence_digest": failed.evidence_digest},
                "record": runner.records[node.node_id],
            }
        )
        receipts = {k: v for k, v in runner.checkpoint().items() if k != node.node_id}
        runner.executor.checkpoint.save(receipts)
        runner.records.pop(node.node_id, None)
        runner.save_records()
        return self._expand(runner, (outcome,))

    def _data(
        self, runner: CampaignRunner
    ) -> tuple[
        list[ResponseObservation],
        dict[float, str] | None,
        dict[str, Any],
        dict[tuple[int, float, str], list[float]],
        list[float] | None,
    ]:
        computed = set(self.plan.computed_columns) | set(self.expanded)
        return runner._verified_observations(
            site_indices=tuple(
                i for i, s in enumerate(self.plan.inventory.subspaces) if s.site_id in computed
            )
        )

    def _outcomes(
        self,
        runner: CampaignRunner,
        data: tuple[
            list[ResponseObservation],
            dict[float, str] | None,
            dict[str, Any],
            dict[tuple[int, float, str], list[float]],
            list[float] | None,
        ],
    ) -> tuple[ShadowOutcome, ...]:
        observations, states, _, widths, reference_widths = data
        parent_valid = all(o.parent_dm_sha256 == self.plan.reference.parent_dm_sha256 for o in observations)
        state_valid = (
            bool(observations)
            and parent_valid
            and self._complete_state_gate()
            and states is not None
            and set(states) == {float(o.alpha) for o in observations}
            and all(s == "reference_branch" for s in states.values())
            and runner.response_grid_calibration is None
        )
        outcomes = qualify_shadows(
            self.plan,
            observation_series(self.plan, observations, widths, reference_widths),
            scientific_state_valid=state_valid,
        )
        return tuple(
            replace(
                o,
                status=CoverageStatus.REJECTED_EXPANDED,
                reason=ShadowReason.PREVIOUSLY_REJECTED_CLASS,
            )
            if o.representative in self.expanded and o.status is CoverageStatus.PROVEN
            else o
            for o in outcomes
        )

    def _complete_state_gate(self) -> bool:
        """Fail closed until occupation-subspace, gap and smoothness gates exist.

        The runtime provides SCF validation and moment continuity only. FDRC
        I.5 also requires occupation spectra/occupied subspaces, gap or Fermi
        evidence and smoothness. There is no production opt-in bypass. Tests
        may inject their complete synthetic state oracle at this boundary.
        """
        return False

    def prepare(self, runner: CampaignRunner) -> bool:
        """Return True only when the current shadow barrier can be checkpointed."""
        data = self._data(runner)
        outcomes = self._outcomes(runner, data)
        return not self._expand(runner, outcomes)

    def replay_barrier(self, runner: CampaignRunner) -> None:
        """Resume grants no shadow status from JSON; recompute derived evidence."""
        derived = {"alpha-diagnostic-gate", "matrix-analysis"}
        runner.executor.checkpoint.save({k: v for k, v in runner.checkpoint().items() if k not in derived})
        for key in derived:
            runner.records.pop(key, None)
        runner.save_records()

    def analysis_data(
        self, runner: CampaignRunner
    ) -> tuple[
        list[ResponseObservation],
        dict[float, str] | None,
        dict[str, Any],
        dict[tuple[int, float, str], list[float]],
        list[float] | None,
        dict[str, Any],
    ]:
        data = self._data(runner)
        observations, states, magnetic, widths, reference_widths = data
        outcomes = self._outcomes(runner, data)
        if self._expand(runner, outcomes):
            raise ExecutionContractError(
                "shadow evidence changed; explicit expansion must finish before analysis"
            )
        dataset = runner._response_observation_dataset(
            observations,
            trace_half_widths_electron=widths,
            reference_trace_half_widths_electron=reference_widths,
            occupation_source="siesta_occupations_total",
        )
        budgets = dict(
            response_budgets(self.plan, observation_series(self.plan, observations, widths, reference_widths))
        )
        sites = tuple(s.site_id for s in self.plan.inventory.subspaces)
        columns = {
            (j, mode): [budgets[(site, mode, observed)].estimate_e_per_ev for observed in sites]
            for j, site in enumerate(sites)
            for mode in ResponseMode
            if (site, mode, sites[0]) in budgets
        }
        complete = all(
            (j, mode) in columns
            for j, site in enumerate(sites)
            for mode in ResponseMode
            if site in set(self.plan.computed_columns) | set(self.expanded)
        )
        matrices = reconstruct_responses(self.plan, outcomes, columns) if complete else None
        dataset["translation_shadow"] = {
            "plan_digest": self.plan.digest,
            "outcomes": [o.to_mapping() for o in outcomes],
            "direct_data_retained": True,
            "reconstructed_raw_matrices": None if matrices is None else matrices.to_mapping(),
            "failed_runs": self.failed_runs,
            "complete_state_gate": CoverageStatus.PROVEN.value
            if self._complete_state_gate()
            else CoverageStatus.NOT_ESTABLISHED.value,
            "reconstruction_maps": [
                {"destination": site, "representative": group.representative, "operation_id": op_id}
                for group in self.plan.coverage.classes
                if any(
                    o.representative == group.representative and o.status is CoverageStatus.PROVEN
                    for o in outcomes
                )
                for site, op_id in group.ops_rep_to_member
            ],
        }
        if not any(o.status is CoverageStatus.PROVEN for o in outcomes):
            return (*data, dataset)
        reconstructed = []
        reconstructed_widths = {}
        for alpha in sorted({float(o.alpha) for o in observations}):
            rows = {int(o.perturbation_site): o for o in observations if o.alpha == alpha}
            template = next(iter(rows.values()))
            delta = reconstruct_responses(
                self.plan,
                outcomes,
                {
                    (j, mode): [
                        float(value) - float(ref)
                        for value, ref in zip(
                            o.occupations_bare if mode is ResponseMode.BARE else o.occupations_screened,
                            o.occupations_ref,
                            strict=True,
                        )
                    ]
                    for j, o in rows.items()
                    for mode in ResponseMode
                },
            )
            radius = reconstruct_responses(
                self.plan,
                outcomes,
                {(j, mode): widths[(j, alpha, mode.value.lower())] for j in rows for mode in ResponseMode},
            )
            for j in range(len(sites)):
                values = {}
                for mode, matrix, bound in (
                    (ResponseMode.BARE, delta.chi0_raw, radius.chi0_raw),
                    (ResponseMode.SCREENED, delta.chi_raw, radius.chi_raw),
                ):
                    values[mode] = [
                        float(template.occupations_ref[i]) + matrix[i][j] for i in range(len(sites))
                    ]
                    reconstructed_widths[(j, alpha, mode.value.lower())] = [r[j] for r in bound]
                reconstructed.append(
                    replace(
                        template,
                        perturbation_site=j,
                        occupations_bare=values[ResponseMode.BARE],
                        occupations_screened=values[ResponseMode.SCREENED],
                        bare_fdf_sha256="",
                        bare_out_sha256="",
                        screened_fdf_sha256="",
                        screened_out_sha256="",
                    )
                )
        return reconstructed, states, magnetic, reconstructed_widths, reference_widths, dataset
