import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "tools"))
from scientific_dag_gate import complete, invalidate_from, is_complete, load  # noqa: E402


def test_gates_require_artifacts_and_order(tmp_path):
    state = tmp_path / "results" / "scientific_dag_state.json"
    artifact = tmp_path / "artifact.json"
    artifact.write_text("{}")

    with pytest.raises(ValueError, match="parent gate"):
        complete(state, "REFERENCE", [artifact], None)

    complete(state, "PROJECTOR_AUDIT", [artifact], "locality accepted")
    assert is_complete(state, "PROJECTOR_AUDIT", [artifact])
    artifact.unlink()
    assert not is_complete(state, "PROJECTOR_AUDIT", [artifact])
    assert load(state)["gates"]["PROJECTOR_AUDIT"]["status"] == "VALIDATED"


def test_analysis_record_preserves_typed_outcome_and_rechecks_provenance(tmp_path):
    campaign = tmp_path / "campaign"
    campaign.mkdir()
    result = campaign / "result.json"
    config = campaign / "scientific_dag.json"
    script = campaign / "analyze.py"
    validator = campaign / "validate_analysis.py"
    evidence = campaign / "receipt.json"
    validator.write_text("print('{}')\n", encoding="utf-8")
    result.write_text(
        "{\"campaign_id\":\"fixture-v1\",\"status\":\"REPORTABLE_NUMERICAL_U_INTERVAL\"}\n",
        encoding="utf-8",
    )
    config.write_text(json.dumps({"analysis_acceptance": {
        "schema_version": 1,
        "kind": "campaign_hook",
        "campaign_id": "fixture-v1",
        "validator_script": validator.name,
        "validator_sha256": hashlib.sha256(validator.read_bytes()).hexdigest(),
    }}), encoding="utf-8")
    for path, body in (
        (script, "print('analysis')\n"),
        (evidence, "{\"receipt\":true}\n"),
    ):
        path.write_text(body, encoding="utf-8")
    inputs = [
        {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        for path in (result, config, script, validator, evidence)
    ]
    verdict = campaign / "analysis-verdict.json"
    verdict.write_text(json.dumps({
        "schema": "siestaflow-analysis-verdict-v1",
        "campaign_id": "fixture-v1",
        "source_status": "REPORTABLE_NUMERICAL_U_INTERVAL",
        "analysis_state": "REPORTABLE_NUMERICAL_U_INTERVAL",
        "gate_decision": "RECORDED_ONLY",
        "physical_acceptance": "NOT_ESTABLISHED",
        "provenance": {
            "campaign_root": str(campaign),
            "source_result_path": result.name,
            "config_path": config.name,
            "source_result_sha256": hashlib.sha256(result.read_bytes()).hexdigest(),
            "config_sha256": hashlib.sha256(config.read_bytes()).hexdigest(),
            "verified_files": inputs,
        },
    }), encoding="utf-8")

    state = campaign / "results" / "state.json"
    for gate in ("PROJECTOR_AUDIT", "REFERENCE", "CHILDREN_MATERIALIZED", "RESPONSES"):
        complete(state, gate, [result], gate, "VALIDATED")
    complete(
        state,
        "ANALYSIS",
        [result, verdict],
        "native numerical interval recorded; physical acceptance not established",
        "RECORDED",
        verdict,
    )
    evidence_report = campaign / "evidence.json"
    evidence_report.write_text("{}\n", encoding="utf-8")
    complete(state, "EVIDENCE", [evidence_report, result], "analysis record captured", "RECORDED")

    assert is_complete(state, "ANALYSIS", [result, verdict], verdict)
    report = json.loads(__import__("scientific_dag_gate").report(state))
    analysis_row = next(row for row in report["gates"] if row["gate"] == "ANALYSIS")
    assert analysis_row["status"] == "RECORDED"
    assert analysis_row["source_status"] == "REPORTABLE_NUMERICAL_U_INTERVAL"
    assert analysis_row["physical_acceptance"] == "NOT_ESTABLISHED"
    assert "does not itself assert physical validation" in report["evidence_scope"]

    result.write_text("{\"status\":\"FAIL\"}\n", encoding="utf-8")
    assert not is_complete(state, "ANALYSIS", [result, verdict], verdict)
    invalidate_from(state, "ANALYSIS")
    assert load(state)["gates"].get("ANALYSIS") is None
    assert load(state)["gates"].get("EVIDENCE") is None
