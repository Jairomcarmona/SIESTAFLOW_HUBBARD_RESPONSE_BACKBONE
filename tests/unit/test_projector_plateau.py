import json
from pathlib import Path
from typing import cast

import pytest

from hubbardflow.domain.projector_plateau import (
    PlateauCriteria,
    PlateauGateEvidence,
    PlateauGateState,
    PlateauRequirement,
    ProductionControl,
    ProjectorAssessment,
    ProjectorAssessmentResult,
    ProjectorCurve,
    ProjectorParameterKind,
    ProjectorPlateauError,
    ProjectorProbePoint,
    ProjectorScanSpec,
    ProjectorScanStage,
    ProjectorSupportGeometry,
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


def _m1_curve() -> ProjectorCurve:
    fixture = Path(__file__).parents[1] / "fixtures" / "projector_curve_m1_provisional.json"
    return ProjectorCurve.from_mapping(json.loads(fixture.read_text(encoding="utf-8")))


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
                "plateau_outcome": "PROJECTOR_NOT_ASSESSED",
                "u_acceptable_for_declared_projector": "false",
                "reason": "missing evidence",
                "declared_projector": None,
                "curve": None,
            },
            "u_acceptable_for_declared_projector must be a boolean",
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
    assert not result.u_acceptable_for_declared_projector


def test_passing_plateau_gates_without_a_declared_curve_remains_not_assessed() -> None:
    result = projector_assessment(
        PlateauCriteria(0.2, 3, 0.05),
        _gate_evidence(),
    )

    assert result.status is ProjectorAssessment.PROJECTOR_NOT_ASSESSED
    assert result.plateau_outcome.value == "PROJECTOR_NOT_ASSESSED"
    assert not result.u_acceptable_for_declared_projector


def test_passed_declared_criteria_and_gates_confirm_optional_plateau() -> None:
    curve = _m1_curve()
    declared = ProjectorValue(ProjectorParameterKind.CUTOFF_NORM, 0.90)
    result = projector_assessment(
        PlateauCriteria(0.2, 3, 0.05),
        _gate_evidence(),
        declared,
        curve,
    )

    assert result.status is ProjectorAssessment.PROJECTOR_PLATEAU_CONFIRMED
    assert result.u_acceptable_for_declared_projector
    assert ProjectorAssessmentResult.from_mapping(result.to_mapping()) == result
    assert result.curve == curve
    assert result.declared_projector == declared


def test_failed_optional_plateau_keeps_declared_projector_u_characterized() -> None:
    curve = _m1_curve()
    declared = ProjectorValue(ProjectorParameterKind.CUTOFF_NORM, 0.90)
    result = projector_assessment(
        PlateauCriteria(0.2, 3, 0.05),
        _gate_evidence(PlateauGateState.FAIL),
        declared,
        curve,
    )

    assert result.status is ProjectorAssessment.PROJECTOR_DECLARED_AND_CHARACTERIZED
    assert result.plateau_outcome.value == "PROJECTOR_NO_PLATEAU"
    assert result.u_acceptable_for_declared_projector
    assert curve.no_plateau_report_line().startswith("no plateau; U is projector-specific; dU/d(norm)=")


def test_missing_required_gate_cannot_confirm_plateau() -> None:
    result = projector_assessment(
        PlateauCriteria(0.2, 3, 0.05),
        _gate_evidence()[:-1],
        ProjectorValue(ProjectorParameterKind.CUTOFF_NORM, 0.90),
        _m1_curve(),
    )

    assert result.status is ProjectorAssessment.PROJECTOR_DECLARED_AND_CHARACTERIZED
    assert result.plateau_outcome.value == "PROJECTOR_NOT_ASSESSED"
    assert result.u_acceptable_for_declared_projector


def test_duplicate_gate_with_missing_requirement_cannot_confirm_plateau() -> None:
    gates = _gate_evidence()[:-1] + (
        PlateauGateEvidence(PlateauRequirement.RESULT_STABILITY, PlateauGateState.PASS),
    )
    result = projector_assessment(
        PlateauCriteria(0.2, 3, 0.05),
        gates,
        ProjectorValue(ProjectorParameterKind.CUTOFF_NORM, 0.90),
        _m1_curve(),
    )

    assert result.status is ProjectorAssessment.PROJECTOR_DECLARED_AND_CHARACTERIZED
    assert result.plateau_outcome.value == "PROJECTOR_NOT_ASSESSED"
    assert result.u_acceptable_for_declared_projector


def test_missing_plateau_thresholds_keep_declared_curve_characterized() -> None:
    result = projector_assessment(
        PlateauCriteria(),
        (),
        ProjectorValue(ProjectorParameterKind.CUTOFF_NORM, 0.90),
        _m1_curve(),
    )

    assert result.status is ProjectorAssessment.PROJECTOR_DECLARED_AND_CHARACTERIZED
    assert result.plateau_outcome.value == "PROJECTOR_NOT_ASSESSED"
    assert result.u_acceptable_for_declared_projector


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


def test_provisional_m1_curve_is_projector_specific_and_does_not_generalize_plateau() -> None:
    curve = _m1_curve()
    assert [point.projector.value for point in curve.points] == [0.80, 0.90, 0.95, 0.98]
    assert [point.u_ev for point in curve.points] == [13.0972, 10.6622, 8.2302, 6.2659]
    assert curve.segments[0].slope_ev_per_parameter == pytest.approx((10.6622 - 13.0972) / 0.10)
    assert "dU/d(norm)=" in curve.no_plateau_report_line()
    assert ProjectorCurve.from_mapping(curve.to_mapping()) == curve
    assert ProjectorUResult(curve.points[1].projector, curve.points[1].u_ev).is_for_declared_projector(
        curve.points[1].projector
    )
    assert not curve.points[0].is_for_declared_projector(curve.points[1].projector)


def test_projector_curve_canonicalizes_points_independent_of_input_order() -> None:
    curve = _m1_curve()
    reversed_curve = ProjectorCurve(tuple(reversed(curve.points)))
    mapping = curve.to_mapping()
    points = cast(list[dict[str, object]], mapping["points"])
    mapping["points"] = list(reversed(points))
    reversed_mapping_curve = ProjectorCurve.from_mapping(mapping)

    assert reversed_curve == curve
    assert reversed_mapping_curve == curve
    assert [point.projector.value for point in reversed_curve.points] == [0.80, 0.90, 0.95, 0.98]


def test_projector_curve_recomputes_serialized_slope_instead_of_exact_comparing() -> None:
    curve = _m1_curve()
    mapping = curve.to_mapping()
    segments = cast(list[dict[str, object]], mapping["segments"])
    segments[0]["slope_ev_per_parameter"] = -24.35

    restored = ProjectorCurve.from_mapping(mapping)

    assert restored == curve
    assert restored.segments[0].slope_ev_per_parameter == pytest.approx(-24.35)


def test_m1_production_control_records_delta_without_acceptance_gate() -> None:
    control = ProductionControl(ProjectorValue(ProjectorParameterKind.CUTOFF_NORM, 0.90), 10.6622, 10.658)

    assert control.delta_u_ev == pytest.approx(0.0042)
    assert ProductionControl.from_mapping(control.to_mapping()) == control


def test_production_control_recomputes_serialized_delta_without_exact_comparison() -> None:
    control = ProductionControl(ProjectorValue(ProjectorParameterKind.CUTOFF_NORM, 0.90), 10.6622, 10.658)
    mapping = control.to_mapping()
    mapping["delta_u_ev"] = 0.0042

    restored = ProductionControl.from_mapping(mapping)

    assert restored == control
    assert restored.delta_u_ev == pytest.approx(0.0042)


def test_projector_support_geometry_is_record_only_and_compares_half_distance() -> None:
    evidence = ProjectorSupportGeometry(None, None, 2.44, 5.38)
    overlapping = ProjectorSupportGeometry(None, None, 3.0, 5.38)

    assert evidence.half_minimum_distance_bohr == pytest.approx(2.69)
    assert not evidence.support_exceeds_half_distance
    assert ProjectorSupportGeometry.from_mapping(evidence.to_mapping()) == evidence
    assert evidence.to_mapping()["decision_role"] == "RECORD_ONLY"
    assert overlapping.support_exceeds_half_distance
    assert ProjectorSupportGeometry.from_mapping(overlapping.to_mapping()) == overlapping


def test_projector_support_geometry_recomputes_rounded_serialized_half_distance() -> None:
    evidence = ProjectorSupportGeometry(None, None, 2.44, 5.380000000000001)
    mapping = evidence.to_mapping()
    mapping["half_minimum_distance_bohr"] = 2.69
    mapping["support_exceeds_half_distance"] = False

    restored = ProjectorSupportGeometry.from_mapping(mapping)

    assert restored == evidence
    assert restored.half_minimum_distance_bohr == 5.380000000000001 / 2.0
    assert not restored.support_exceeds_half_distance


def test_projector_curve_must_include_the_declared_projector() -> None:
    with pytest.raises(ProjectorPlateauError, match="must have a U value"):
        projector_assessment(
            PlateauCriteria(),
            (),
            ProjectorValue(ProjectorParameterKind.CUTOFF_NORM, 0.85),
            _m1_curve(),
        )
