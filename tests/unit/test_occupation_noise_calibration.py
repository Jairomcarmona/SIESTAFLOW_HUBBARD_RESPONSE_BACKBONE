import pytest

from siestaflow_hubbard.domain.occupation_noise_calibration import (
    OccupationNoiseCalibrationError,
    OccupationNoiseCalibrationPolicy,
    derive_occupation_noise,
)


def test_mode_centered_noise_excludes_inter_role_offset() -> None:
    from siestaflow_hubbard.domain.occupation_noise_calibration import derive_mode_centered_occupation_noise
    policy = OccupationNoiseCalibrationPolicy(3, 2.0, 5e-5, 5e-5)
    result = derive_mode_centered_occupation_noise({
        "REFERENCE": [9.45436] * 3, "BARE": [9.45280] * 3, "SCREENED": [9.45100] * 3,
    }, policy)
    assert result.occupation_noise_e == 5e-5
    assert result.by_mode["paired_controls"]["bare_reference_systematic_offset_e"] != 0.0


def _policy(**changes):
    values = {
        "replica_count": 5,
        "safety_factor": 2.0,
        "deterministic_floor_e": 5e-5,
        "output_quantum_e": 5e-5,
        "required_modes": ("REFERENCE", "BARE", "SCREENED"),
    }
    values.update(changes)
    return OccupationNoiseCalibrationPolicy(**values)


def test_deterministic_controls_keep_the_observable_output_quantum():
    result = derive_occupation_noise({"REFERENCE": [4.0] * 5, "BARE": [4.0] * 5, "SCREENED": [4.0] * 5}, _policy())
    assert result.occupation_noise_e == 5e-5
    assert result.by_mode["BARE"]["deterministic"] is True


def test_maximum_median_deviation_is_expanded_by_the_preregistered_factor():
    result = derive_occupation_noise(
        {"REFERENCE": [1.0] * 5, "BARE": [1.0, 1.0, 1.0, 1.0, 1.00001], "SCREENED": [1.0] * 5}, _policy()
    )
    assert result.by_mode["BARE"]["maximum_absolute_deviation_e"] == pytest.approx(1e-5)
    assert result.occupation_noise_e == pytest.approx(5e-5)


def test_rejects_floor_smaller_than_observable_output_quantum():
    with pytest.raises(OccupationNoiseCalibrationError, match="observable output quantum"):
        _policy(deterministic_floor_e=1e-8).validate()


def test_rejects_missing_mode_or_wrong_replica_count():
    with pytest.raises(OccupationNoiseCalibrationError, match="exactly"):
        derive_occupation_noise({"BARE": [1.0] * 5}, _policy())
    with pytest.raises(OccupationNoiseCalibrationError, match="exactly 5"):
        derive_occupation_noise({"REFERENCE": [1.0] * 5, "BARE": [1.0] * 4, "SCREENED": [1.0] * 5}, _policy())
