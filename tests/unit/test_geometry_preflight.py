import pytest

from hubbardflow.domain.geometry_preflight import (
    GeometryAssessment,
    GeometryPreflightError,
    GeometryPreflightState,
    GeometryThresholdPolicy,
    assess_reference_geometry,
)


def _assess(
    *,
    maximum_force_ev_ang: float = 0.0,
    stress: tuple[float, float, float, float, float, float] = (0, 0, 0, 0, 0, 0),
    constrained: float | None = None,
    unreliable: bool = False,
) -> GeometryAssessment:
    return assess_reference_geometry(
        maximum_force_ev_ang=maximum_force_ev_ang,
        residual_ev_ang=0.0,
        maximum_constrained_force_ev_ang=constrained,
        stress_voigt_kbar=stress,
        source_lines=(("maximum_force", 10),),
        policy=GeometryThresholdPolicy(),
        unreliable_for_dftu_shift=unreliable,
    )


def test_assesses_near_equilibrium_and_records_pressure_convention() -> None:
    assessment = _assess(stress=(1, 1, 1, 0, 0, 0))

    assert assessment.state is GeometryPreflightState.NEAR_EQUILIBRIUM
    assert assessment.mean_pressure_kbar == -1.0
    assert assessment.maximum_shear_kbar == 0.0
    assert assessment.to_mapping()["decision_role"] == "RECORD_ONLY"


def test_pressure_or_force_above_advisory_limit_is_recorded() -> None:
    assessment = _assess(maximum_force_ev_ang=0.02, stress=(7.4, 7.4, 7.4, 0, 0, 0))

    assert assessment.state is GeometryPreflightState.ABOVE_REFERENCE_THRESHOLDS
    assert assessment.mean_pressure_kbar == pytest.approx(-7.4)


def test_constraints_and_nonzero_dftu_shift_are_not_assessed() -> None:
    assessment = _assess(constrained=0.01, unreliable=True)

    assert assessment.state is GeometryPreflightState.NOT_ASSESSED_CONSTRAINTS
    assert assessment.additional_states == (GeometryPreflightState.NOT_ASSESSED_UNRELIABLE_FOR_DFTU_SHIFT,)


def test_nonzero_dftu_shift_without_constraints_has_its_own_state() -> None:
    assessment = _assess(unreliable=True)

    assert assessment.state is GeometryPreflightState.NOT_ASSESSED_UNRELIABLE_FOR_DFTU_SHIFT


def test_missing_metrics_and_bad_thresholds_fail_closed() -> None:
    assessment = assess_reference_geometry(
        maximum_force_ev_ang=None,
        residual_ev_ang=None,
        maximum_constrained_force_ev_ang=None,
        stress_voigt_kbar=None,
        source_lines=(),
        policy=GeometryThresholdPolicy(),
        unreliable_for_dftu_shift=False,
    )
    assert assessment.state is GeometryPreflightState.NOT_ASSESSED_NO_OUTPUT
    with pytest.raises(GeometryPreflightError, match="nonnegative"):
        GeometryThresholdPolicy.from_mapping({"max_force_ev_ang": -1})


def test_policy_round_trip_preserves_declared_thresholds() -> None:
    policy = GeometryThresholdPolicy.from_mapping({"max_force_ev_ang": 0.02, "declared_by": "CONFIG"})

    assert GeometryThresholdPolicy.from_mapping(policy.to_mapping()) == policy
    assert policy.max_force_ev_ang == 0.02
    assert policy.max_abs_mean_pressure_kbar == 5.0
