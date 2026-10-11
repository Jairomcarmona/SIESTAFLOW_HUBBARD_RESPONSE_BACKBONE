"""Analysis transport preserving LR-U units, evidence, policies and native results."""

from __future__ import annotations

from typing import Any, cast

from hubbardflow.domain.lr_analysis_v2 import LRAnalysisPolicy, analyze_verified_lr
from hubbardflow.domain.matrix_lr import ResponseObservation
from hubbardflow.domain.validation import require_finite, require_int

from .results import ApiOperation, ApiResult, result
from .serialization import (
    PublicApiError,
    ScientificEvidenceError,
    array,
    decode_record,
    mapping,
    object_fields,
    string,
)


def response_observation(value: object) -> ResponseObservation:
    row = mapping(value)
    record = decode_record(ResponseObservation, row)
    # JSON object keys are strings; native scientific site IDs remain integers.
    fingerprints: dict[int, str] = {}
    for key, digest in mapping(row["projector_fingerprints"]).items():
        if not key.isascii() or not key.isdigit() or str(int(key)) != key:
            raise PublicApiError("projector_fingerprints keys must be canonical nonnegative integer strings")
        fingerprints[int(key)] = string(digest, "projector fingerprint")
    record.projector_fingerprints = fingerprints
    return record


def analyze(request: object) -> ApiResult:
    """Call the established analyzer; no new estimator, cutoff or certification.

    policies require every native policy field, including explicit nulls. JSON
    tuple-key maps use rows, checked for duplicates before reconstructing native
    keys. The resulting numerical candidate is never physical acceptance.
    """
    row = object_fields(
        request,
        {"observations", "policy"},
        {
            "campaign",
            "magnetic_state_labels",
            "scf_validated",
            "active_window_ev",
            "trace_half_widths_electron",
            "occupation_source",
            "occupation_noise_calibration",
            "response_grid_reproducibility_calibration",
        },
    )
    observations = [response_observation(item) for item in array(row["observations"], "observations")]
    policy = decode_record(LRAnalysisPolicy, row["policy"])
    kwargs: dict[str, Any] = {}
    for key in ("campaign", "occupation_noise_calibration", "response_grid_reproducibility_calibration"):
        if key in row:
            kwargs[key] = None if row[key] is None else mapping(row[key], key)
    if "scf_validated" in row:
        if row["scf_validated"] is not None and type(row["scf_validated"]) is not bool:
            raise PublicApiError("scf_validated must be boolean or null")
        kwargs["scf_validated"] = row["scf_validated"]
    if "active_window_ev" in row:
        kwargs["active_window_ev"] = (
            None
            if row["active_window_ev"] is None
            else require_finite(row["active_window_ev"], "active_window_ev")
        )
    if "occupation_source" in row:
        kwargs["occupation_source"] = string(row["occupation_source"], "occupation_source")
    if row.get("magnetic_state_labels") is not None:
        labels: dict[float, str] = {}
        for item in array(row["magnetic_state_labels"], "magnetic_state_labels"):
            label = object_fields(item, {"alpha_ev", "label"})
            alpha = require_finite(label["alpha_ev"], "alpha_ev")
            if alpha in labels:
                raise PublicApiError("duplicate magnetic-state alpha_ev")
            labels[alpha] = string(label["label"], "label")
        kwargs["magnetic_state_labels"] = labels
    if row.get("trace_half_widths_electron") is not None:
        widths: dict[tuple[int, float, str], list[float]] = {}
        for item in array(row["trace_half_widths_electron"], "trace_half_widths_electron"):
            width = object_fields(item, {"perturbation_site", "alpha_ev", "mode", "half_widths_electron"})
            key_tuple = (
                require_int(width["perturbation_site"], "perturbation_site", minimum=0),
                require_finite(width["alpha_ev"], "alpha_ev"),
                string(width["mode"], "mode"),
            )
            if key_tuple in widths or key_tuple[2] not in {"bare", "screened"}:
                raise PublicApiError("duplicate or invalid trace-width identity")
            widths[key_tuple] = [
                require_finite(number, "trace half-width")
                for number in array(width["half_widths_electron"], "half_widths_electron")
            ]
        kwargs["trace_half_widths_electron"] = widths
    try:
        native = analyze_verified_lr(observations, policy, **kwargs)
        return result(ApiOperation.ANALYZE, cast(str, native["numerical_status"]), native)
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        raise ScientificEvidenceError(f"analysis rejected: {exc}") from exc
