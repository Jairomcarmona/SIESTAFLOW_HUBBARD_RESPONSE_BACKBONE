"""Serializable plan resolution delegating every scientific choice upstream."""

from __future__ import annotations

from hubbardflow.domain.coverage_models import CoverageQualification
from hubbardflow.domain.fdebq_models import CalibrationProtocol, CalibrationQualification
from hubbardflow.domain.perturbation_plan import AlphaStrategy
from hubbardflow.domain.perturbation_plan_evidence import inventory_from_mapping, inventory_mapping
from hubbardflow.domain.perturbation_planner import resolve_perturbation_plan
from hubbardflow.domain.response_protocol import ResolvedResponseProtocol
from hubbardflow.domain.validation import require_finite

from .results import ApiOperation, ApiResult, result
from .serialization import PublicApiError, array, explicit_native_fields, mapping, object_fields, string


def resolve_plan(request: object) -> ApiResult:
    """Resolve native evidence, without reading files, choosing tolerances or scheduling.

    All physical records and policies are supplied in native serializable form.
    Missing evidence retains the planner's NOT_ESTABLISHED; the native plan
    digest (including ensure_ascii=True) is returned verbatim.
    """
    row = object_fields(
        request,
        {
            "inventory",
            "coverage",
            "response_protocol",
            "source_fdf_sha256",
            "alpha_strategy",
            "planner_version",
            "backend_identity",
            "tau_u_ev",
        },
        {"explicit_sites", "calibration_protocol", "calibration_qualification"},
    )
    try:
        sites = row.get("explicit_sites")
        inventory = inventory_from_mapping(mapping(row["inventory"]))
        coverage = CoverageQualification.from_mapping(mapping(row["coverage"]))
        protocol = ResolvedResponseProtocol.from_mapping(mapping(row["response_protocol"]))
        explicit_native_fields(row["inventory"], inventory_mapping(inventory))
        explicit_native_fields(row["coverage"], coverage.to_mapping())
        explicit_native_fields(row["response_protocol"], protocol.to_mapping())
        resolved = resolve_perturbation_plan(
            inventory,
            coverage,
            protocol,
            source_fdf_sha256=string(row["source_fdf_sha256"], "source_fdf_sha256"),
            alpha_strategy=AlphaStrategy(string(row["alpha_strategy"], "alpha_strategy")),
            planner_version=string(row["planner_version"], "planner_version"),
            backend_identity=string(row["backend_identity"], "backend_identity"),
            tau_u_ev=None if row["tau_u_ev"] is None else require_finite(row["tau_u_ev"], "tau_u_ev"),
            explicit_sites=None
            if sites is None
            else tuple(string(item, "site") for item in array(sites, "sites")),
            calibration_protocol=(
                None
                if row.get("calibration_protocol") is None
                else CalibrationProtocol.from_mapping(mapping(row["calibration_protocol"]))
            ),
            calibration_qualification=(
                None
                if row.get("calibration_qualification") is None
                else CalibrationQualification.from_mapping(mapping(row["calibration_qualification"]))
            ),
        )
        return result(
            ApiOperation.RESOLVE_PLAN, resolved.status.value, resolved.to_mapping(), resolved.digest
        )
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        raise PublicApiError(f"cannot resolve_plan: {exc}") from exc
