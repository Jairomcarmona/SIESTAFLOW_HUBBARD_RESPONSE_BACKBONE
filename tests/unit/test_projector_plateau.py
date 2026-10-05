from __future__ import annotations

import pytest

from hubbardflow.domain.projector_plateau import (
    PlateauCriteria,
    PlateauGateEvidence,
    PlateauGateState,
    PlateauRequirement,
    ProductionControl,
    ProjectorAssessment,
    ProjectorAssessmentResult,
    ProjectorParameterKind,
    ProjectorPlateauError,
    ProjectorProbePoint,
    ProjectorScanSpec,
    ProjectorScanStage,
    ProjectorUResult,
    ProjectorValue,
    projector_assessment,
)


def _scan(criteria: PlateauCriteria | None = None) -> ProjectorScanSpec:
    criteria = criteria or PlateauCriteria()
    return ProjectorScanSpec(
        representative_site_id="Mn-1",
        kind=ProjectorParameterKind.CUTOFF_NORM,
        production_projector=ProjectorValue(ProjectorParameterKind.CUTOFF_NORM, 0.90),
        points=(
            ProjectorProbePoint(ProjectorValue(ProjectorParameterKind.CUTOFF_NORM, 0.85)),
            ProjectorProbePoint(ProjectorValue(ProjectorParameterKind.CUTOFF_NORM, 0.90)),
        ),
        criteria=criteria,
    )


def _gate_evidence(state: PlateauGateState = PlateauGateState.PASS) -> tuple[PlateauGateEvidence, ...]:
    return tuple(PlateauGateEvidence(requirement, state) for requirement in PlateauRequirement)


def test_one_column_probe_counts_twelve_response_runs_and_reference() -> None:
    scan = _scan()

    assert scan.responses_per_probe == 12
    assert scan.total_runs_per_probe == 13


def test_scan_round_trip_preserves_user_criteria_and_projector_binding() -> None:
    criteria = PlateauCriteria(0.2, 3, 0.05)
    scan = _scan(criteria)

    restored = ProjectorScanSpec.from_mapping(scan.to_mapping())

    assert restored == scan
    assert restored.production_projector.kind is ProjectorParameterKind.CUTOFF_NORM
    assert [point.projector.value for point in restored.points] == [0.85, 0.90]


@pytest.mark.parametrize(
    ("mapping", "match"),
    [
        (
            {"kind": "CUTOFF_NORM", "value": 0.9, "method": 2.5},
            "method must be an integer",
        ),
        (
            {
                "maximum_u_variation_ev": 0.2,
                "minimum_points": True,
                "refinement_step": 0.05,
            },
            "minimum_points must be an integer",
        ),
        ({"kind": "CUTOFF_NORM", "value": True, "method": 2}, "projector value must be a number"),
        (
            {
                "status": "PROJECTOR_NOT_ASSESSED",
                "candidate_eligible_for_lock": "false",
                "reason": "missing evidence",
            },
            "candidate_eligible_for_lock must be a boolean",
        ),
        (
            {
                **_scan().to_mapping(),
                "representative_site_id": None,
            },
            "representative_site_id must be a string",
        ),
    ],
)
def test_from_mapping_rejects_coercible_but_wrong_types(mapping: dict[str, object], match: str) -> None:
    with pytest.raises(ProjectorPlateauError, match=match):
        if "status" in mapping:
            ProjectorAssessmentResult.from_mapping(mapping)
        elif "representative_site_id" in mapping:
            ProjectorScanSpec.from_mapping(mapping)
        elif "minimum_points" in mapping:
            PlateauCriteria.from_mapping(mapping)
        else:
            ProjectorValue.from_mapping(mapping)


def test_scan_stage_order_is_fixed_by_the_specification() -> None:
    assert tuple(stage.value for stage in ProjectorScanStage) == (
        "COARSE_SCAN",
        "REFINEMENT",
        "EVALUATION",
        "PLATEAU_DETECTION",
        "LOCK",
        "FULL_RESPONSE",
    )


def test_u_result_round_trip_keeps_the_projector_identity() -> None:
    result = ProjectorUResult(ProjectorValue(ProjectorParameterKind.EXPLICIT_RC, 2.5), -0.4)

    assert ProjectorUResult.from_mapping(result.to_mapping()) == result


def test_missing_thresholds_and_evidence_remain_not_assessed() -> None:
    result = projector_assessment(PlateauCriteria(), _gate_evidence())

    assert result.status is ProjectorAssessment.PROJECTOR_NOT_ASSESSED
    assert not result.candidate_eligible_for_lock


def test_passed_declared_criteria_and_gates_confirm_plateau() -> None:
    result = projector_assessment(
        PlateauCriteria(0.2, 3, 0.05),
        _gate_evidence(),
    )

    assert result.status is ProjectorAssessment.PROJECTOR_PLATEAU_CONFIRMED
    assert result.candidate_eligible_for_lock


def test_failed_gate_reports_no_plateau_without_disabling_calculation() -> None:
    result = projector_assessment(
        PlateauCriteria(0.2, 3, 0.05),
        _gate_evidence(PlateauGateState.FAIL),
    )

    assert result.status is ProjectorAssessment.PROJECTOR_NO_PLATEAU
    assert not result.candidate_eligible_for_lock
    assert "failed" in result.reason


def test_missing_required_gate_cannot_confirm_plateau() -> None:
    result = projector_assessment(
        PlateauCriteria(0.2, 3, 0.05),
        _gate_evidence()[:-1],
    )

    assert result.status is ProjectorAssessment.PROJECTOR_NOT_ASSESSED


def test_criteria_require_finite_positive_declared_values() -> None:
    with pytest.raises(ProjectorPlateauError, match="finite"):
        PlateauCriteria(float("nan"), 3, 0.05)
    with pytest.raises(ProjectorPlateauError, match="positive integer"):
        PlateauCriteria(0.2, 0, 0.05)


def test_production_control_records_exact_projector_and_difference() -> None:
    control = ProductionControl(ProjectorValue(ProjectorParameterKind.CUTOFF_NORM, 0.90), 4.2, 4.0)

    assert control.delta_u_ev == pytest.approx(0.2)
    assert ProductionControl.from_mapping(control.to_mapping()) == control
    _scan().validate_production_control(control)


def test_production_control_rejects_a_different_projector() -> None:
    control = ProductionControl(ProjectorValue(ProjectorParameterKind.CUTOFF_NORM, 0.95), 4.2, 4.0)

    with pytest.raises(ProjectorPlateauError, match="production projector"):
        _scan().validate_production_control(control)
