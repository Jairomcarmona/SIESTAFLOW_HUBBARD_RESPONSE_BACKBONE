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
from tests.unit.validation_tolerances import (
    M1_PROBE_CAMPAIGN_DELTA_TOLERANCE_EV,
    M1_PROJECTOR_SCAN_U_TOLERANCE_EV,
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


def _m1_fixture() -> dict[str, object]:
    fixture = Path(__file__).parents[1] / "fixtures" / "projector_curve_m1.json"
    return cast(dict[str, object], json.loads(fixture.read_text(encoding="utf-8")))


def _m1_curve() -> ProjectorCurve:
    return ProjectorCurve.from_mapping(_m1_fixture())


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


def test_measured_m1_curve_is_projector_specific_and_limited_to_sampled_points() -> None:
    curve = _m1_curve()
    assert [point.projector.value for point in curve.points] == [
        0.50,
        0.60,
        0.70,
        0.80,
        0.85,
        0.90,
        0.95,
        0.98,
        0.99,
    ]
    assert [point.u_ev for point in curve.points] == pytest.approx(
        [
            25.0833,
            19.0979,
            15.4146,
            13.0972,
            12.0211,
            10.6622,
            8.2302,
            6.2659,
            5.5708,
        ],
        abs=M1_PROJECTOR_SCAN_U_TOLERANCE_EV.value,
    )
    assert curve.segments[3].slope_ev_per_parameter == pytest.approx((12.0211 - 13.0972) / 0.05)
    assert "dU/d(norm)=" in curve.no_plateau_report_line()
    assert ProjectorCurve.from_mapping(curve.to_mapping()) == curve
    assert ProjectorUResult(curve.points[1].projector, curve.points[1].u_ev).is_for_declared_projector(
        curve.points[1].projector
    )
    assert not curve.points[0].is_for_declared_projector(curve.points[1].projector)

    fixture = _m1_fixture()
    measured_points = cast(list[dict[str, object]], fixture["points"])
    assert [cast(float, point["n_ref_e"]) for point in measured_points] == pytest.approx(
        [2.6050, 3.0697, 3.5521, 4.0605, 4.3436, 4.6739, 5.1445, 5.6680, 5.8848]
    )
    assert [cast(float, point["support_bohr"]) for point in measured_points] == pytest.approx(
        [
            1.452035750261572,
            1.588122997468477,
            1.765052169941702,
            2.011479793011571,
            2.188619831130068,
            2.439367465832430,
            2.872995373814031,
            3.455406057237902,
            3.893329137527022,
        ]
    )
    verification = cast(dict[str, object], fixture["verification"])
    assert verification["diff_verified"] is True
    assert verification["fdf_change"] == "DFTU.CutoffNorm line only"
    assert verification["magnetic_moment_range_mu_b"] == [2.9183, 2.9207]
    assert fixture["site_id"] == "MnLR00"
    assert fixture["formal_d_electrons"] == 3
    geometry = cast(dict[str, object], fixture["geometry_record_only"])
    assert cast(float, geometry["mn_mn_distance_bohr"]) == pytest.approx(5.390)
    assert cast(float, geometry["half_mn_mn_distance_bohr"]) == pytest.approx(2.695)
    assert cast(float, geometry["mn_o_distance_bohr"]) == pytest.approx(3.59)
    assert cast(float, geometry["pao_3d_radius_bohr"]) == pytest.approx(4.502)
    assert geometry["pao_3d_radius_is_constant_across_cutoff_norm"] is True
    control = cast(dict[str, object], fixture["production_control"])
    assert control["cutoff_norm"] == 0.90
    assert control["one_column_u_ev"] == 10.6622
    assert control["campaign_36x36_u_ev_range"] == pytest.approx([10.6578, 10.6586])
    assert control["maximum_absolute_difference_ev"] == pytest.approx(0.0044)


def test_projector_curve_canonicalizes_points_independent_of_input_order() -> None:
    curve = _m1_curve()
    reversed_curve = ProjectorCurve(tuple(reversed(curve.points)))
    mapping = curve.to_mapping()
    points = cast(list[dict[str, object]], mapping["points"])
    mapping["points"] = list(reversed(points))
    reversed_mapping_curve = ProjectorCurve.from_mapping(mapping)

    assert reversed_curve == curve
    assert reversed_mapping_curve == curve
    assert [point.projector.value for point in reversed_curve.points] == [
        0.50,
        0.60,
        0.70,
        0.80,
        0.85,
        0.90,
        0.95,
        0.98,
        0.99,
    ]


def test_projector_curve_recomputes_serialized_slope_instead_of_exact_comparing() -> None:
    curve = _m1_curve()
    mapping = curve.to_mapping()
    segments = cast(list[dict[str, object]], mapping["segments"])
    segments[3]["slope_ev_per_parameter"] = -21.52

    restored = ProjectorCurve.from_mapping(mapping)

    assert restored == curve
    assert restored.segments[3].slope_ev_per_parameter == pytest.approx((12.0211 - 13.0972) / 0.05)


def test_m1_production_control_records_delta_without_acceptance_gate() -> None:
    control = ProductionControl(ProjectorValue(ProjectorParameterKind.CUTOFF_NORM, 0.90), 10.6622, 10.6578)

    assert control.delta_u_ev == pytest.approx(0.0044, abs=M1_PROBE_CAMPAIGN_DELTA_TOLERANCE_EV.value)
    assert ProductionControl.from_mapping(control.to_mapping()) == control


def test_production_control_recomputes_serialized_delta_without_exact_comparison() -> None:
    control = ProductionControl(ProjectorValue(ProjectorParameterKind.CUTOFF_NORM, 0.90), 10.6622, 10.6578)
    mapping = control.to_mapping()
    mapping["delta_u_ev"] = 0.0044

    restored = ProductionControl.from_mapping(mapping)

    assert restored == control
    assert restored.delta_u_ev == pytest.approx(0.0044, abs=M1_PROBE_CAMPAIGN_DELTA_TOLERANCE_EV.value)


def test_projector_support_geometry_is_record_only_and_compares_half_distance() -> None:
    evidence = ProjectorSupportGeometry(None, None, 2.439367465832430, 5.390)
    overlapping = ProjectorSupportGeometry(None, None, 2.872995373814031, 5.390)

    assert evidence.half_minimum_distance_bohr == pytest.approx(2.695)
    assert not evidence.support_exceeds_half_distance
    assert ProjectorSupportGeometry.from_mapping(evidence.to_mapping()) == evidence
    assert evidence.to_mapping()["decision_role"] == "RECORD_ONLY"
    assert overlapping.support_exceeds_half_distance
    assert ProjectorSupportGeometry.from_mapping(overlapping.to_mapping()) == overlapping


def test_projector_support_geometry_recomputes_rounded_serialized_half_distance() -> None:
    evidence = ProjectorSupportGeometry(None, None, 2.439367465832430, 5.390000000000001)
    mapping = evidence.to_mapping()
    mapping["half_minimum_distance_bohr"] = 2.695
    mapping["support_exceeds_half_distance"] = False

    restored = ProjectorSupportGeometry.from_mapping(mapping)

    assert restored == evidence
    assert restored.half_minimum_distance_bohr == 5.390000000000001 / 2.0
    assert not restored.support_exceeds_half_distance


def test_projector_curve_must_include_the_declared_projector() -> None:
    with pytest.raises(ProjectorPlateauError, match="must have a U value"):
        projector_assessment(
            PlateauCriteria(),
            (),
            ProjectorValue(ProjectorParameterKind.CUTOFF_NORM, 0.88),
            _m1_curve(),
        )
