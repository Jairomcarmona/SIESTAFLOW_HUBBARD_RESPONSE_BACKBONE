"""Versioned capabilities describe transport support, not validated execution."""

from importlib.metadata import version

from .results import API_VERSION, ApiOperation, ApiResult, result
from .serialization import object_fields, string


def describe_capabilities() -> ApiResult:
    """Report installed API support without implying HF-1 runtime qualification."""
    return result(
        ApiOperation.DESCRIBE_CAPABILITIES,
        "NOT_ESTABLISHED",
        {
            "capability_id": "hubbardflow.linear_response",
            "api_version": API_VERSION,
            "distribution": "hubbardflow",
            "distribution_version": version("hubbardflow"),
            "operations": [operation.value for operation in ApiOperation],
            "integration_modes": ["HF-1"],
            "runtime_qualified": False,
            "alpha_strategies": ["FIXED_PROTOCOL_GRID", "USER_EXPLICIT_GRID", "CALIBRATED_GRID"],
            "schemas": [
                "hubbardflow.api_result.v1",
                "hubbardflow.analysis_result.v1",
                "hubbardflow.worker_status.v1",
            ],
            "native_plan_digest_encoding": "json.dumps(sort_keys=True,separators=(',',':'),allow_nan=False,ensure_ascii=True)",
            "hubbard_parameter_semantics": "U_scalar_charge",
            "hf2_available": False,
            "worker_targets": ["linux", "wsl"],
            "transport_targets": ["windows", "linux", "wsl"],
        },
    )


def worker_status(request: object) -> ApiResult:
    """Wrap an existing worker-state snapshot without interpreting execution as science.

    No worker is observed here; raw snapshots belong to execution. Unknown
    native statuses are preserved, with conservative NOT_ESTABLISHED assessment.
    """
    row = object_fields(request, {"snapshot"})
    from .serialization import mapping

    snapshot = mapping(row["snapshot"], "snapshot")
    status = string(snapshot.get("status"), "snapshot.status")
    return result(ApiOperation.WORKER_STATUS, status, snapshot)
