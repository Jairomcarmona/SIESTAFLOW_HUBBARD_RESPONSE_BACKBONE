"""Installed-wheel consumer: imports the public facade only, outside checkout."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

from hubbardflow import api


def main() -> None:
    data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    root = Path(sys.argv[2]).resolve()
    module = Path(api.__file__).resolve()
    assert not module.is_relative_to(root), (module, root)
    validator = Draft202012Validator(api.get_schema("hubbardflow.api_result.v1").to_mapping())
    analysis_validator = Draft202012Validator(api.get_schema("hubbardflow.analysis_result.v1").to_mapping())
    worker_validator = Draft202012Validator(api.get_schema("hubbardflow.worker_status.v1").to_mapping())
    for case in data["cases"]:
        receipt = getattr(api, case["operation"])(case["request"])
        output = receipt.to_mapping()
        validator.validate(output)
        if case["operation"] != "analyze":
            assert output["payload"] == case["expected_payload"]
        assert output["native_status"] == case["expected_status"]
        assert output["native_digest"] == case["expected_digest"]
        assert api.ApiResult.from_mapping(output) == receipt
        if case["operation"] == "analyze":
            analysis_validator.validate(output["payload"])
            payload = output["payload"]
            assert isinstance(payload, dict)
            for field in (
                "schema_version",
                "quantity",
                "units",
                "physical_acceptance",
                "site_labels",
                "numerical_status",
                "estimator_policy",
            ):
                assert payload[field] == case["expected_payload"][field]
    capabilities = api.describe_capabilities().to_mapping()
    validator.validate(capabilities)
    capability_payload = capabilities["payload"]
    assert isinstance(capability_payload, dict)
    assert capability_payload["runtime_qualified"] is False
    worker = api.worker_status({"snapshot": {"status": "FUTURE_SUCCESS", "campaign_id": "fixture"}})
    assert worker.assessment is api.SafeAssessment.NOT_ESTABLISHED
    worker_validator.validate(worker.to_mapping()["payload"])
    resume = api.check_resume(data["resume_request"])
    assert resume.native_status == "NOT_ESTABLISHED"
    resume_payload = resume.to_mapping()["payload"]
    assert isinstance(resume_payload, dict)
    assert resume_payload["reusable_response_ids"] == []
    validator.validate(resume.to_mapping())
    print(
        "Installed public consumer: native plan/observation/gate payload/digests, analysis semantics/schema, future enum and resume OK"
    )


if __name__ == "__main__":
    main()
