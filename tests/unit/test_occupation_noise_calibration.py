import pytest

from hubbardflow.domain.occupation_noise_calibration import (
    OccupationNoiseCalibrationError,
    OccupationNoiseCalibrationPolicy,
    derive_occupation_noise,
)


def test_mode_centered_noise_excludes_inter_role_offset() -> None:
    from hubbardflow.domain.occupation_noise_calibration import derive_mode_centered_occupation_noise
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


@pytest.mark.parametrize("digest", [None, "", "malformed"])
def test_replica_dm_and_evidence_hashes_are_optional_warnings(tmp_path, digest):
    import json
    from hashlib import sha256
    from hubbardflow.domain.occupation_noise_calibration import (
        derive_mode_centered_occupation_noise, validate_calibration_result)
    policy = OccupationNoiseCalibrationPolicy(3, 2.0, 5e-5, 5e-5)
    derived = derive_mode_centered_occupation_noise({mode: [4.0] * 3 for mode in policy.required_modes}, policy)
    lock = {"schema": "siestaflow-occupation-noise-calibration-lock-v1", "campaign_id": "synthetic",
            "preregistration": {}, "runtime": {}, "observable": {}, "reference_semantics": {},
            "input_provenance": {}, "result_binding": {}, "fail_closed": True,
            "calibration": {"replica_count": 3, "independence": "jobs", "required_modes": list(policy.required_modes),
                "control_alpha_ev": 0.0, "safety_factor": 2.0, "output_quantum_e": 5e-5,
                "output_quantum_evidence": "synthetic", "deterministic_floor_e": 5e-5,
                "statistic": "within-mode", "zero_rule": "floor"}}
    lock_path = tmp_path / "lock.json"
    lock_path.write_text(json.dumps(lock), encoding="utf-8")
    receipts = [{"replica_id": f"r{i}", "slurm_job_id": str(i + 1),
                 "replica_result_path": f"results/calibration-replicas/r{i}/replica-result.json"}
                for i in range(3)]
    if digest is not None:
        for receipt in receipts:
            receipt.update({key: digest for key in ("receipts_sha256", "reference_dm_sha256", "replica_result_sha256")})
    result = {"schema": "siestaflow-occupation-noise-calibration-result-v1",
              "calibration_lock_sha256": sha256(lock_path.read_bytes()).hexdigest(),
              "occupation_noise_e": derived.occupation_noise_e, "by_mode": derived.by_mode,
              "policy": {"replica_count": 3, "safety_factor": 2.0, "deterministic_floor_e": 5e-5,
                         "output_quantum_e": 5e-5, "orbital_count": policy.orbital_count,
                         "spin_factor": policy.spin_factor, "required_modes": list(policy.required_modes)},
              "replica_receipts": receipts}
    result_path = tmp_path / "result.json"
    result_path.write_text(json.dumps(result), encoding="utf-8")
    validated = validate_calibration_result(result_path, lock_path)
    assert validated["occupation_noise_e"] == derived.occupation_noise_e
    assert len(validated["traceability_warnings"]) == 9
    result["occupation_noise_e"] *= 2
    result_path.write_text(json.dumps(result), encoding="utf-8")
    with pytest.raises(OccupationNoiseCalibrationError, match="locked statistic"):
        validate_calibration_result(result_path, lock_path)
