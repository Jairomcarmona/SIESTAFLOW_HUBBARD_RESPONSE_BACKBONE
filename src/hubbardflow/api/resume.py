"""Read-only inspection of declared resume evidence; never starts a worker."""

from __future__ import annotations

from hubbardflow.domain.perturbation_plan import ResolvedPerturbationPlan
from hubbardflow.domain.response_reuse import ResponseRunIdentity, ReuseStatus, qualify_response_reuse
from hubbardflow.domain.validation import require_sha256

from .results import ApiOperation, ApiResult, result
from .serialization import (
    PublicApiError,
    array,
    decode_record,
    explicit_native_fields,
    json_bytes,
    mapping,
    object_fields,
    string,
)


def check_resume(request: object) -> ApiResult:
    """Inspect native plans, policies, artifact hashes and response identities.

    File evidence is supplied by the caller: no filesystem, clock, locks,
    writes or worker mutation occur. Equal hashes do not establish physical
    equivalence. Existing reuse policy therefore emits NOT_ESTABLISHED, with
    no reusable responses, unless it identifies an explicit native mismatch.
    The caller must execute a direct recalculation for non-established reuse.
    """
    row = object_fields(
        request,
        {"expected_plan", "observed_plan", "expected_policies", "observed_policies", "files", "responses"},
    )
    try:
        expected = ResolvedPerturbationPlan.from_mapping(mapping(row["expected_plan"]))
        observed = ResolvedPerturbationPlan.from_mapping(mapping(row["observed_plan"]))
        explicit_native_fields(row["expected_plan"], expected.to_mapping())
        explicit_native_fields(row["observed_plan"], observed.to_mapping())
        changed: list[str] = []
        if expected.digest != observed.digest:
            changed.append("plan")
        if json_bytes(mapping(row["expected_policies"])) != json_bytes(mapping(row["observed_policies"])):
            changed.append("policies")
        files: list[dict[str, object]] = []
        file_ids: set[str] = set()
        for item in array(row["files"], "files"):
            file = object_fields(item, {"artifact_id", "expected_sha256", "observed_sha256"})
            identity = string(file["artifact_id"], "artifact_id")
            if identity in file_ids:
                raise PublicApiError("duplicate file artifact_id")
            file_ids.add(identity)
            require_sha256(file["expected_sha256"], "expected_sha256")
            actual = file["observed_sha256"]
            if actual is not None:
                require_sha256(actual, "observed_sha256")
            match = file["expected_sha256"] == actual
            if not match:
                changed.append(f"file:{identity}")
            files.append({**file, "matches": match})
        qualifications: list[dict[str, object]] = []
        response_ids: set[str] = set()
        mismatch = False
        for item in array(row["responses"], "responses"):
            response = object_fields(item, {"response_id", "pilot", "production"})
            response_id = string(response["response_id"], "response_id")
            if response_id in response_ids:
                raise PublicApiError("duplicate response_id")
            response_ids.add(response_id)
            qualification = qualify_response_reuse(
                decode_record(ResponseRunIdentity, response["pilot"]),
                decode_record(ResponseRunIdentity, response["production"]),
            )
            mismatch = mismatch or qualification.status is ReuseStatus.IDENTITY_MISMATCH
            qualifications.append({"response_id": response_id, **qualification.to_mapping()})
        status = ReuseStatus.IDENTITY_MISMATCH if changed or mismatch else ReuseStatus.NOT_ESTABLISHED
        sorted_files = sorted(files, key=lambda item: str(item["artifact_id"]))
        sorted_qualifications = sorted(qualifications, key=lambda item: str(item["response_id"]))
        return result(
            ApiOperation.CHECK_RESUME,
            status.value,
            {
                "expected_plan_digest": expected.digest,
                "observed_plan_digest": observed.digest,
                "changed": sorted(changed),
                "files": sorted_files,
                "responses": sorted_qualifications,
                "reusable_response_ids": [],
                "physical_equivalence": "NOT_ESTABLISHED",
            },
        )
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        raise PublicApiError(f"resume evidence rejected: {exc}") from exc
