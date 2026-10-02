"""SCF shadow ESTIMATEs add to the preserved print BOUND."""

from __future__ import annotations

from dataclasses import replace

from hubbardflow.domain.coverage_models import CoverageStatus
from hubbardflow.domain.response_budget_models import BoundKind
from hubbardflow.domain.response_shadow import ShadowReason, qualify_shadows, response_budgets
from hubbardflow.domain.scf_ladder_models import ScfResponseEstimate, ScfStatus
from hubbardflow.execution.campaign_shadow_inputs import observation_series
from tests.unit.test_campaign_shadow import _observations, _plan


def test_additive_scf_component_and_incomplete_underresolved_model_expands() -> None:
    plan = _plan()
    observations, widths = _observations(plan, {0, 1}, fail=True)
    series = observation_series(plan, observations, widths, [5e-8] * 4)
    pure = qualify_shadows(plan, series, scientific_state_valid=True)
    assert pure[0].status is CoverageStatus.REJECTED_EXPANDED
    columns = {(c.site_id, c.mode): c for c in plan.response_protocol.columns}
    estimates = tuple(
        ScfResponseEstimate(
            j, mode, i, columns[(j, mode)].estimator, 0.3, ScfStatus.ESTABLISHED, BoundKind.ESTIMATE
        )
        for (j, mode, i), _ in response_budgets(plan, series)
    )
    mixed = qualify_shadows(plan, series, scientific_state_valid=True, scf_estimates=estimates)
    assert mixed[0].status is CoverageStatus.PROVEN
    assert mixed[0].comparisons[0].direct_scf_estimate_e_per_ev == 0.3
    assert mixed[0].comparisons[0].direct_bound_e_per_ev == pure[0].comparisons[0].direct_bound_e_per_ev
    for partial in (estimates[:1], tuple(replace(e, status=ScfStatus.SCF_UNDER_RESOLVED) for e in estimates)):
        rejected = qualify_shadows(plan, series, scientific_state_valid=True, scf_estimates=partial)
        assert rejected[0].status is CoverageStatus.REJECTED_EXPANDED
        assert rejected[0].reason is ShadowReason.SCF_ESTIMATE_NOT_ESTABLISHED
