"""Native consumer fixtures preserve science and reject malformed transport."""

from __future__ import annotations

import copy
import json
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from hubbardflow import api
from hubbardflow.domain.lr_analysis_v2 import LRAnalysisPolicy, analyze_verified_lr
from hubbardflow.domain.matrix_lr import ResponseObservation

FIXTURE = Path(__file__).parents[1] / "fixtures/public_api_v1/native_consumer.json"
DATA: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "case", DATA["cases"], ids=lambda row: row["operation"] + ":" + row["expected_status"]
)
def test_native_consumer_equivalence(case: dict[str, Any]) -> None:
    receipt = getattr(api, case["operation"])(case["request"])
    assert receipt.native_status == case["expected_status"]
    assert receipt.native_digest == case["expected_digest"]
    expected = case["expected_payload"]
    if case["operation"] == "analyze":
        # Compare native/facade in the same numerical environment, not BLAS
        # rounding across different operating systems. No tolerance is added.
        observations = []
        for item in case["request"]["observations"]:
            native_item = {
                **item,
                "projector_fingerprints": {
                    int(key): value for key, value in item["projector_fingerprints"].items()
                },
            }
            observations.append(ResponseObservation(**native_item))
        expected = analyze_verified_lr(observations, LRAnalysisPolicy(**case["request"]["policy"]))
    assert receipt.to_mapping()["payload"] == expected
    assert api.ApiResult.from_mapping(receipt.to_mapping()) == receipt
    assert receipt.assessment is api.SafeAssessment.NOT_ESTABLISHED


def test_result_deep_immutability_and_unknown_native_enum() -> None:
    receipt = api.worker_status({"snapshot": {"status": "FUTURE_STATUS", "completed_nodes": []}})
    assert receipt.native_status == "FUTURE_STATUS"
    assert receipt.assessment is api.SafeAssessment.NOT_ESTABLISHED
    mapping = receipt.to_mapping()
    payload = mapping["payload"]
    assert isinstance(payload, dict)
    payload["completed_nodes"].append("unauthorized")
    assert receipt.to_mapping()["payload"] == {"status": "FUTURE_STATUS", "completed_nodes": []}
    with pytest.raises(FrozenInstanceError):
        setattr(receipt, "native_status", "PASS")  # noqa: B010 -- exercising frozen dataclass at runtime
    forged = receipt.to_mapping()
    forged["assessment"] = "PASS"
    with pytest.raises(api.PublicApiError):
        api.ApiResult.from_mapping(forged)


def test_capabilities_are_installed_transport_not_runtime_qualification() -> None:
    receipt = api.describe_capabilities()
    payload = receipt.to_mapping()["payload"]
    assert isinstance(payload, dict)
    assert payload["distribution_version"] == "0.1.3"
    assert payload["runtime_qualified"] is False
    assert payload["hf2_available"] is False
    assert payload["hubbard_parameter_semantics"] == "U_scalar_charge"
    assert payload["api_version"] == api.API_VERSION


@pytest.mark.parametrize("field", ["complete", "dm_read_verified", "return_code", "occupation"])
@pytest.mark.parametrize("value", ["true", True, None])
def test_observation_scalar_types_are_not_coerced(field: str, value: object) -> None:
    if value is True and field in {"complete", "dm_read_verified"}:
        return
    request = copy.deepcopy(DATA["cases"][3]["request"])
    request["observation"][field] = value
    with pytest.raises(api.PublicApiError):
        api.validate_observation(request)


@pytest.mark.parametrize(
    "operation", ["resolve_plan", "validate_observation", "evaluate_gate", "analyze", "check_resume"]
)
def test_missing_and_unknown_request_fields_fail_closed(operation: str) -> None:
    with pytest.raises(api.PublicApiError):
        getattr(api, operation)({})
    with pytest.raises(api.PublicApiError):
        getattr(api, operation)({"unknown": True})


@given(st.sampled_from([float("nan"), float("inf"), -float("inf")]))
def test_nonfinite_evidence_is_rejected(value: float) -> None:
    request = copy.deepcopy(DATA["cases"][3]["request"])
    request["observation"]["occupation"] = value
    with pytest.raises(ValueError):
        api.validate_observation(request)


@given(st.permutations(tuple(DATA["cases"][0]["request"])))
@settings(deadline=None, max_examples=25)
def test_request_key_order_does_not_change_plan_digest(keys: list[str]) -> None:
    original = DATA["cases"][0]["request"]
    ordered = {key: original[key] for key in keys}
    assert api.resolve_plan(ordered).native_digest == DATA["cases"][0]["expected_digest"]


def test_missing_policy_does_not_inject_native_defaults() -> None:
    request = copy.deepcopy(DATA["cases"][-1]["request"])
    del request["policy"]["sensitivity_tolerance_eV"]
    with pytest.raises(api.PublicApiError):
        api.analyze(request)
    request = copy.deepcopy(DATA["cases"][0]["request"])
    del request["coverage"]["user_policy"]["enabled"]
    with pytest.raises(api.PublicApiError):
        api.resolve_plan(request)


def test_unknown_nested_native_plan_fields_are_rejected() -> None:
    request = copy.deepcopy(DATA["cases"][0]["request"])
    request["inventory"]["invented_scientific_authority"] = True
    with pytest.raises(api.PublicApiError):
        api.resolve_plan(request)


def test_resume_is_read_only_and_equal_hashes_never_grant_physical_reuse(tmp_path: Path) -> None:
    marker = tmp_path / "worker-state.json"
    marker.write_bytes(b"original")
    request = copy.deepcopy(DATA["resume_request"])
    before = json.dumps(request, sort_keys=True)
    receipt = api.check_resume(request)
    assert receipt.native_status == "NOT_ESTABLISHED"
    payload = receipt.to_mapping()["payload"]
    assert isinstance(payload, dict)
    assert payload["reusable_response_ids"] == []
    assert json.dumps(request, sort_keys=True) == before
    assert marker.read_bytes() == b"original"
    assert list(tmp_path.iterdir()) == [marker]


@pytest.mark.parametrize("change", ["file", "policy", "identity"])
def test_resume_changes_report_mismatch_without_worker_effects(change: str) -> None:
    request = copy.deepcopy(DATA["resume_request"])
    if change == "file":
        request["files"][0]["observed_sha256"] = "b" * 64
    elif change == "policy":
        request["observed_policies"]["new-policy"] = {"version": "explicit"}
    else:
        request["responses"][0]["production"]["backend_version"] = "changed"
    receipt = api.check_resume(request)
    assert receipt.native_status == "IDENTITY_MISMATCH"
    assert receipt.assessment is api.SafeAssessment.FAIL


def test_resume_duplicate_ids_and_missing_physical_fields_rejected() -> None:
    request = copy.deepcopy(DATA["resume_request"])
    request["responses"].append(request["responses"][0])
    with pytest.raises(api.PublicApiError):
        api.check_resume(request)


def test_scientific_rejection_has_a_distinct_typed_kind() -> None:
    request = copy.deepcopy(DATA["cases"][3]["request"])
    request["observation"]["complete"] = False
    with pytest.raises(api.ScientificEvidenceError) as rejection:
        api.validate_observation(request)
    assert rejection.value.kind is api.ApiErrorKind.SCIENTIFIC_REJECTION
    with pytest.raises(api.PublicApiError) as malformed:
        api.validate_observation({})
    assert malformed.value.kind is api.ApiErrorKind.TRANSPORT_INVALID


def test_resume_unknown_nested_fields_are_rejected() -> None:
    request = copy.deepcopy(DATA["resume_request"])
    request["expected_plan"]["unsupported"] = True
    with pytest.raises(api.PublicApiError):
        api.check_resume(request)
    request = copy.deepcopy(DATA["resume_request"])
    del request["responses"][0]["pilot"]["backend_version"]
    with pytest.raises(api.PublicApiError):
        api.check_resume(request)
