"""Calibrated evidence freezes reviewable plans; production stays fail closed."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from hubbardflow.domain.fdebq_models import ColumnEvidence
from hubbardflow.domain.fdebq_rounds import decide_round, seed_requests
from hubbardflow.domain.perturbation_plan import (
    AlphaStrategy,
    PlanReason,
    PlanStatus,
    ResolvedPerturbationPlan,
)
from hubbardflow.domain.perturbation_plan_evidence import PerturbationPlanError
from hubbardflow.domain.perturbation_planner import resolve_perturbation_plan
from hubbardflow.domain.symmetry_reduction import ResponseMode
from hubbardflow.execution.campaign_plan import campaign_inventory
from hubbardflow.execution.campaign_v2 import CampaignV2Error, validate_lr_config, validate_reference_fdf
from tests.unit.test_campaign_plan import inputs as campaign_inputs
from tests.unit.test_coverage import DIGEST
from tests.unit.test_fdebq_rounds import protocol, series
from tests.unit.test_perturbation_plan import inputs


def test_calibrated_plan_freezes_single_column_functional_and_protocol_at_review() -> None:
    inventory, coverage, response = inputs(calibrated=True)
    sites = tuple(s.site_id for s in inventory.subspaces)
    p = protocol()
    data = []
    for site in sites:
        for mode in ResponseMode:
            rows = tuple(
                series(site, mode, observed, chi=-2.0 if site == observed else 0.0) for observed in sites
            )
            data.append(ColumnEvidence(site, mode, rows, (), (), True))
    requests = seed_requests(sites, p)
    qualification = decide_round(data, p, requested=requests, terminal=requests).qualification
    result = resolve_perturbation_plan(
        inventory,
        coverage,
        response,
        source_fdf_sha256=DIGEST,
        alpha_strategy=AlphaStrategy.CALIBRATED_GRID,
        planner_version="test-v1",
        backend_identity="test",
        tau_u_ev=p.tau_u_ev,
        calibration_protocol=p,
        calibration_qualification=qualification,
    )
    assert result.status is PlanStatus.REVIEW
    assert PlanReason.CALIBRATION_REVIEW in result.reason_codes
    assert result.run_specs
    assert result.protocol_version == p.version
    for calibration in result.calibration:
        assert calibration.qualification.round_protocol == p
        assert calibration.qualification.round_qualification == qualification
        assert calibration.column_plan.estimator.amplitudes_ev == calibration.column_plan.amplitudes_ev
    shadow = next(
        c
        for c in result.calibration
        if c.column_plan.site_id == "s1" and c.column_plan.mode is ResponseMode.BARE
    )
    representative = next(
        c
        for c in result.calibration
        if c.column_plan.site_id == "s0" and c.column_plan.mode is ResponseMode.BARE
    )
    assert shadow.column_plan.estimator == representative.column_plan.estimator
    assert ResolvedPerturbationPlan.from_mapping(json.loads(json.dumps(result.to_mapping()))) == result
    with pytest.raises(PerturbationPlanError, match="READY"):
        replace(result, status=PlanStatus.READY)
    with pytest.raises(PerturbationPlanError, match="tau_u_ev"):
        resolve_perturbation_plan(
            inventory,
            coverage,
            response,
            source_fdf_sha256=DIGEST,
            alpha_strategy=AlphaStrategy.CALIBRATED_GRID,
            planner_version="test-v1",
            backend_identity="test",
            tau_u_ev=None,
            calibration_protocol=p,
            calibration_qualification=qualification,
        )


@pytest.mark.parametrize("flag", ("CALIBRATED", "CALIBRATED_GRID"))
def test_calibrated_campaign_cannot_enter_legacy_controller_without_state_gate(
    tmp_path: Path, flag: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    import hubbardflow.domain.adaptive_alpha_control as legacy_domain
    import hubbardflow.execution.campaign_runner as legacy_runner

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("CALIBRATED must never invoke the legacy U-stability controller")

    monkeypatch.setattr(legacy_domain, "decide_round", forbidden)
    monkeypatch.setattr(legacy_runner, "decide_round", forbidden)
    fdf, config, _ = campaign_inputs(tmp_path)
    _, species, sites = validate_reference_fdf(fdf.read_text(encoding="utf-8"), "PBE")
    inventory = campaign_inventory(fdf, (tmp_path,))
    config["alpha_strategy"] = flag
    config["calibration_protocol"] = protocol().to_mapping()
    with pytest.raises(CampaignV2Error, match="NOT_ESTABLISHED: SCIENTIFIC_STATE_NOT_ESTABLISHED"):
        validate_lr_config(config, species, sites, 2, inventory=inventory)
    del config["calibration_protocol"]["tau_u_ev"]
    with pytest.raises(CampaignV2Error, match="invalid calibration_protocol"):
        validate_lr_config(config, species, sites, 2, inventory=inventory)
    del config["calibration_protocol"]
    with pytest.raises(CampaignV2Error, match="explicit calibration_protocol with tau_u_ev"):
        validate_lr_config(config, species, sites, 2, inventory=inventory)
