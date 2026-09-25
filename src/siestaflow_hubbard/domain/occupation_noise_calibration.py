"""Predeclared, independent calibration of a Hubbard-occupation noise bound.

The calibration input is deliberately limited to repeated zero-shift controls.
It has no alpha coordinate and cannot select a fitting window.  This keeps the
noise bound independent of the response measurements that it later gates.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from statistics import median
from typing import Any, Mapping, Sequence
import json
from hashlib import sha256
from pathlib import Path


class OccupationNoiseCalibrationError(ValueError):
    """The external repeatability calibration is incomplete or malformed."""


_SHA256_RE = __import__("re").compile(r"[0-9a-f]{64}\Z")


def load_strict_json(path: Path) -> dict[str, Any]:
    """Load an object-only JSON document and reject non-standard constants.

    Python's standard decoder otherwise accepts ``NaN`` and infinities, which
    are not JSON values and must never reach a numerical admission decision.
    """
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=lambda item: (_ for _ in ()).throw(
                OccupationNoiseCalibrationError(f"non-finite JSON constant: {item}")
            ),
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise OccupationNoiseCalibrationError(f"invalid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise OccupationNoiseCalibrationError("JSON document must be an object")
    return value


def _strict_object(value: object, required: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != required:
        raise OccupationNoiseCalibrationError(f"{label} has missing or unexpected fields")
    return value


def _sha256(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise OccupationNoiseCalibrationError(f"{label} must be a lowercase SHA-256")
    return value


def _finite_number(value: object, label: str, *, positive: bool = False) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not isfinite(value):
        raise OccupationNoiseCalibrationError(f"{label} must be a finite number")
    number = float(value)
    if positive and number <= 0.0:
        raise OccupationNoiseCalibrationError(f"{label} must be positive")
    return number


@dataclass(frozen=True)
class OccupationNoiseCalibrationPolicy:
    """Immutable recipe for a conservative repeatability-derived bound.

    ``max(abs(n_r - median(n)))`` is distribution-free.  The safety factor
    expands that observed spread without asserting a Gaussian error model.
    A positive deterministic floor is retained when all repeats agree exactly:
    an identical printed transcript is evidence of repeatability, not proof of
    mathematically zero uncertainty.
    """

    replica_count: int
    safety_factor: float
    deterministic_floor_e: float
    output_quantum_e: float
    orbital_count: int = 5
    spin_factor: int = 2
    required_modes: tuple[str, ...] = ("REFERENCE", "BARE", "SCREENED")

    def validate(self) -> None:
        if self.replica_count < 3:
            raise OccupationNoiseCalibrationError("at least three independent replicas are required")
        if not isfinite(self.safety_factor) or self.safety_factor < 1.0:
            raise OccupationNoiseCalibrationError("safety_factor must be finite and at least one")
        if not isfinite(self.output_quantum_e) or self.output_quantum_e <= 0.0:
            raise OccupationNoiseCalibrationError("output_quantum_e must be positive and finite")
        if not isfinite(self.deterministic_floor_e) or self.deterministic_floor_e <= 0.0:
            raise OccupationNoiseCalibrationError("deterministic_floor_e must be positive and finite")
        if self.deterministic_floor_e < self.output_quantum_e:
            raise OccupationNoiseCalibrationError(
                "deterministic_floor_e cannot be smaller than the observable output quantum"
            )
        expected_quantum = 0.5e-5 * self.orbital_count * self.spin_factor
        if self.output_quantum_e < expected_quantum:
            raise OccupationNoiseCalibrationError(
                "output_quantum_e is below the l=2 spin-summed printed-matrix quantization bound"
            )
        if not self.required_modes or len(set(self.required_modes)) != len(self.required_modes):
            raise OccupationNoiseCalibrationError("required_modes must be a non-empty unique sequence")


@dataclass(frozen=True)
class OccupationNoiseCalibrationResult:
    """Auditable numeric result of one completed independent calibration."""

    occupation_noise_e: float
    by_mode: dict[str, dict[str, float | bool | list[float]]]
    policy: OccupationNoiseCalibrationPolicy


def validate_calibration_result(result_path: Path, lock_path: Path, *, expected_result_sha256: str | None = None,
                                expected_lock_sha256: str | None = None) -> dict[str, Any]:
    """Validate the immutable result binding shared by all response consumers.

    This deliberately validates the result's complete structural contract as
    well as recomputing the statistic.  Receipt payloads are validated by the
    binder before this compact immutable result is written.
    """
    if not result_path.is_file() or not lock_path.is_file():
        raise OccupationNoiseCalibrationError("calibration result or lock is missing")
    result_hash, lock_hash = sha256(result_path.read_bytes()).hexdigest(), sha256(lock_path.read_bytes()).hexdigest()
    if expected_result_sha256 is not None and result_hash != expected_result_sha256:
        raise OccupationNoiseCalibrationError("calibration result hash differs from frozen submission hash")
    if expected_lock_sha256 is not None and lock_hash != expected_lock_sha256:
        raise OccupationNoiseCalibrationError("calibration lock hash differs from frozen submission hash")
    result, lock = load_strict_json(result_path), load_strict_json(lock_path)
    lock = _strict_object(lock, {
        "schema", "campaign_id", "preregistration", "calibration", "runtime", "observable",
        "reference_semantics", "input_provenance", "result_binding", "fail_closed",
    }, "calibration lock")
    if lock["schema"] != "siestaflow-occupation-noise-calibration-lock-v1":
        raise OccupationNoiseCalibrationError("calibration lock schema is invalid")
    recipe = _strict_object(lock["calibration"], {
        "replica_count", "independence", "required_modes", "control_alpha_ev", "safety_factor",
        "output_quantum_e", "output_quantum_evidence", "deterministic_floor_e", "statistic", "zero_rule",
    }, "calibration lock recipe")
    if result.get("schema") != "siestaflow-occupation-noise-calibration-result-v1" or result.get("calibration_lock_sha256") != lock_hash:
        raise OccupationNoiseCalibrationError("calibration result schema or lock binding is invalid")
    modes = recipe["required_modes"]
    if not isinstance(modes, list) or any(not isinstance(mode, str) for mode in modes):
        raise OccupationNoiseCalibrationError("calibration lock required_modes is invalid")
    policy = OccupationNoiseCalibrationPolicy(
        replica_count=recipe["replica_count"],
        safety_factor=recipe["safety_factor"],
        deterministic_floor_e=recipe["deterministic_floor_e"],
        output_quantum_e=recipe["output_quantum_e"],
        required_modes=tuple(modes),
    )
    policy.validate()
    expected_result_fields = {"schema", "calibration_lock_sha256", "occupation_noise_e", "by_mode", "policy", "replica_receipts"}
    result = _strict_object(result, expected_result_fields, "calibration result")
    _sha256(result["calibration_lock_sha256"], "calibration result lock hash")
    _finite_number(result["occupation_noise_e"], "occupation_noise_e", positive=True)
    expected_policy = {
        "replica_count": policy.replica_count, "safety_factor": policy.safety_factor,
        "deterministic_floor_e": policy.deterministic_floor_e, "output_quantum_e": policy.output_quantum_e,
        "orbital_count": policy.orbital_count, "spin_factor": policy.spin_factor,
        "required_modes": list(policy.required_modes),
    }
    if result["policy"] != expected_policy:
        raise OccupationNoiseCalibrationError("calibration result policy differs from the lock")
    receipts = result["replica_receipts"]
    if not isinstance(receipts, list) or len(receipts) != policy.replica_count:
        raise OccupationNoiseCalibrationError("calibration result has an invalid receipt count")
    seen_jobs: set[str] = set()
    for receipt in receipts:
        receipt = _strict_object(receipt, {
            "replica_id", "slurm_job_id", "receipts_sha256", "reference_dm_sha256",
            "replica_result_path", "replica_result_sha256",
        }, "replica receipt")
        if not isinstance(receipt["replica_id"], str) or not receipt["replica_id"]:
            raise OccupationNoiseCalibrationError("replica receipt id is invalid")
        if not isinstance(receipt["slurm_job_id"], str) or not receipt["slurm_job_id"].isdigit() or receipt["slurm_job_id"] in seen_jobs:
            raise OccupationNoiseCalibrationError("replica receipt Slurm job id is invalid or duplicated")
        seen_jobs.add(receipt["slurm_job_id"])
        _sha256(receipt["receipts_sha256"], "replica receipts hash")
        _sha256(receipt["reference_dm_sha256"], "replica reference DM hash")
        _sha256(receipt["replica_result_sha256"], "replica result hash")
        if not isinstance(receipt["replica_result_path"], str):
            raise OccupationNoiseCalibrationError("replica result path is not campaign-relative evidence")
        evidence_path = Path(receipt["replica_result_path"])
        if (evidence_path.is_absolute() or
                evidence_path.name != "replica-result.json" or ".." in evidence_path.parts or
                evidence_path.parts[:2] not in (("results", "calibration-replicas"),
                                                 ("results-v2", "calibration-replicas"))):
            raise OccupationNoiseCalibrationError("replica result path is not campaign-relative evidence")
    by_mode = result["by_mode"]
    if not isinstance(by_mode, dict) or set(by_mode) != {*policy.required_modes, "paired_controls"}:
        raise OccupationNoiseCalibrationError("calibration result has invalid mode diagnostics")
    values = {mode: by_mode[mode].get("occupations") if isinstance(by_mode[mode], dict) else None
              for mode in policy.required_modes}
    statistic = recipe.get("statistic", "")
    derived = (derive_mode_centered_occupation_noise(values, policy)
               if isinstance(statistic, str) and ("within-mode" in statistic or "systematic diagnostics" in statistic)
               else derive_occupation_noise(values, policy))
    if result["occupation_noise_e"] != derived.occupation_noise_e or result["by_mode"] != derived.by_mode:
        raise OccupationNoiseCalibrationError("calibration result bound does not equal locked statistic")
    return {"occupation_noise_e": derived.occupation_noise_e, "result_sha256": result_hash, "lock_sha256": lock_hash}


def derive_occupation_noise(
    occupations_by_mode: Mapping[str, Sequence[float]],
    policy: OccupationNoiseCalibrationPolicy,
) -> OccupationNoiseCalibrationResult:
    """Derive the sole positive ``occupation_noise`` value from controls.

    Every required BARE and SCREENED control must contribute exactly the
    preregistered number of finite scalar projected occupations.  The response
    grid is intentionally absent from this interface.
    """
    policy.validate()
    if set(occupations_by_mode) != set(policy.required_modes):
        raise OccupationNoiseCalibrationError("calibration must contain exactly the preregistered modes")
    diagnostics: dict[str, dict[str, float | bool | list[float]]] = {}
    normalized: dict[str, list[float]] = {}
    for mode in policy.required_modes:
        values = list(occupations_by_mode[mode])
        if len(values) != policy.replica_count:
            raise OccupationNoiseCalibrationError(
                f"{mode} requires exactly {policy.replica_count} independent replicas"
            )
        if any(not isinstance(value, (int, float)) or isinstance(value, bool) or not isfinite(value)
               for value in values):
            raise OccupationNoiseCalibrationError(f"{mode} occupations must be finite real values")
        center = float(median(values))
        maximum_deviation = max(abs(float(value) - center) for value in values)
        scaled_deviation = policy.safety_factor * maximum_deviation
        mode_noise = max(scaled_deviation, policy.deterministic_floor_e)
        diagnostics[mode] = {
            "occupations": [float(value) for value in values],
            "median_occupation": center,
            "maximum_absolute_deviation_e": maximum_deviation,
            "scaled_deviation_e": scaled_deviation,
            "deterministic": maximum_deviation == 0.0,
            "occupation_noise_e": mode_noise,
        }
        normalized[mode] = [float(value) for value in values]
    reference = normalized["REFERENCE"]
    reference_center = float(median(reference))
    reference_spread = max(abs(value - reference_center) for value in reference)
    paired_offsets = {
        mode: max(abs(value - ref) for value, ref in zip(normalized[mode], reference))
        for mode in ("BARE", "SCREENED")
    }
    conservative_deviation = max(reference_spread, *paired_offsets.values())
    bound = max(policy.deterministic_floor_e, policy.safety_factor * conservative_deviation)
    diagnostics["paired_controls"] = {"reference_median_occupation": reference_center,
        "reference_maximum_absolute_deviation_e": reference_spread,
        "bare_reference_maximum_offset_e": paired_offsets["BARE"],
        "screened_reference_maximum_offset_e": paired_offsets["SCREENED"],
        "conservative_deviation_e": conservative_deviation, "occupation_noise_e": bound}
    return OccupationNoiseCalibrationResult(
        occupation_noise_e=bound, by_mode=diagnostics, policy=policy,
    )


def derive_mode_centered_occupation_noise(
    occupations_by_mode: Mapping[str, Sequence[float]], policy: OccupationNoiseCalibrationPolicy,
) -> OccupationNoiseCalibrationResult:
    """Calibrate numerical noise from repeatability within each semantic role.

    A BARE first-Hamiltonian value and a converged SCREENED value are different
    observables at alpha=0.  Their difference is retained as a diagnostic, but
    must never be treated as numerical uncertainty of either response.
    """
    policy.validate()
    if set(occupations_by_mode) != set(policy.required_modes):
        raise OccupationNoiseCalibrationError("calibration must contain exactly the preregistered modes")
    diagnostics: dict[str, dict[str, float | bool | list[float]]] = {}
    centers: dict[str, float] = {}
    bound = policy.deterministic_floor_e
    for mode in policy.required_modes:
        values = [float(x) for x in occupations_by_mode[mode]]
        if len(values) != policy.replica_count or any(not isfinite(x) for x in values):
            raise OccupationNoiseCalibrationError(f"{mode} requires finite independent replicas")
        center = float(median(values))
        deviation = max(abs(x - center) for x in values)
        noise = max(policy.deterministic_floor_e, policy.safety_factor * deviation)
        diagnostics[mode] = {"occupations": values, "median_occupation": center,
            "maximum_absolute_deviation_e": deviation, "scaled_deviation_e": policy.safety_factor * deviation,
            "deterministic": deviation == 0.0, "occupation_noise_e": noise}
        centers[mode] = center
        bound = max(bound, noise)
    diagnostics["paired_controls"] = {"reference_median_occupation": centers["REFERENCE"],
        "bare_reference_systematic_offset_e": centers["BARE"] - centers["REFERENCE"],
        "screened_reference_systematic_offset_e": centers["SCREENED"] - centers["REFERENCE"],
        "bare_screened_systematic_offset_e": centers["BARE"] - centers["SCREENED"],
        "occupation_noise_e": bound}
    return OccupationNoiseCalibrationResult(bound, diagnostics, policy)
