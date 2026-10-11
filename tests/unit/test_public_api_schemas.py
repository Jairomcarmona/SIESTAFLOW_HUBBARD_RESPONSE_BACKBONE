"""Schemas preserve native states and reject invented scientific acceptance."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, ValidationError

from hubbardflow import api

DATA: dict[str, Any] = json.loads(
    (Path(__file__).parents[1] / "fixtures/public_api_v1/native_consumer.json").read_text(encoding="utf-8")
)


@pytest.mark.parametrize(
    "schema_id",
    ["hubbardflow.api_result.v1", "hubbardflow.analysis_result.v1", "hubbardflow.worker_status.v1"],
)
def test_schema_is_installed_versioned_and_roundtrips(schema_id: str) -> None:
    doc = api.get_schema(schema_id)
    Draft202012Validator.check_schema(doc.to_mapping())
    assert api.SchemaDocument.from_mapping(doc.to_mapping()).to_mapping() == doc.to_mapping()


@pytest.mark.parametrize("case", DATA["cases"])
def test_valid_native_receipts(case: dict[str, Any]) -> None:
    receipt = getattr(api, case["operation"])(case["request"]).to_mapping()
    Draft202012Validator(api.get_schema("hubbardflow.api_result.v1").to_mapping()).validate(receipt)
    if case["operation"] == "analyze":
        Draft202012Validator(api.get_schema("hubbardflow.analysis_result.v1").to_mapping()).validate(
            receipt["payload"]
        )


def test_future_enum_retained_and_never_success() -> None:
    receipt = api.worker_status({"snapshot": {"status": "FUTURE_CERTIFIED"}}).to_mapping()
    validator = Draft202012Validator(api.get_schema("hubbardflow.api_result.v1").to_mapping())
    validator.validate(receipt)
    receipt["assessment"] = "PASS"
    with pytest.raises(ValidationError):
        validator.validate(receipt)
    with pytest.raises(api.PublicApiError):
        api.get_schema("../../unauthorized")


@pytest.mark.parametrize(
    "field,value", [("quantity", "Ueff_Dudarev"), ("physical_acceptance", "PASS"), ("units", "Hartree")]
)
def test_analysis_schema_rejects_scientific_reinterpretation(field: str, value: str) -> None:
    payload = copy.deepcopy(DATA["cases"][-1]["expected_payload"])
    payload[field] = value
    with pytest.raises(ValidationError):
        Draft202012Validator(api.get_schema("hubbardflow.analysis_result.v1").to_mapping()).validate(payload)


def test_worker_snapshot_schema_and_api_require_status() -> None:
    with pytest.raises(ValidationError):
        Draft202012Validator(api.get_schema("hubbardflow.worker_status.v1").to_mapping()).validate({})
    with pytest.raises(api.PublicApiError):
        api.worker_status({"snapshot": {}})
