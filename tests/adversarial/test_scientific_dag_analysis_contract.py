"""Adversarial tests for typed Gate 4 analysis acceptance and provenance."""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "tools"))
ANALYSIS_TOOL_SOURCE = ROOT / "tools" / "scientific_dag_analysis.py"

import scientific_dag_analysis  # noqa: E402
from scientific_dag_analysis import verify_analysis  # noqa: E402
from scientific_dag_gate import complete, invalidate_from, is_complete, load, report  # noqa: E402


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _base(tmp_path: Path, *, status: str = "PASS", acceptance: dict | None = None) -> dict[str, Path]:
    campaign = tmp_path / "campaign"
    scripts = campaign / "scripts"
    results = campaign / "results"
    scripts.mkdir(parents=True)
    results.mkdir()
    installed_tools = campaign / "tools"
    installed_tools.mkdir()
    installed_analysis_tool = installed_tools / "scientific_dag_analysis.py"
    shutil.copy2(ANALYSIS_TOOL_SOURCE, installed_analysis_tool)
    # Production installs the verifier inside the campaign. Point the imported
    # function at this byte-identical fixture copy so its provenance contract
    # matches a real installed campaign tree.
    scientific_dag_analysis.__file__ = str(installed_analysis_tool)
    analysis_script = scripts / "analyze.py"
    analysis_script.write_text("# frozen analysis entrypoint\n", encoding="utf-8")
    result_path = results / "analysis.json"
    result_data = {"status": status, "matrix_dimension": 16, "rank_chi0": 16, "rank_chi": 16}
    if acceptance and acceptance.get("kind") == "campaign_hook":
        result_data["campaign_id"] = acceptance.get("campaign_id")
    result_path.write_text(json.dumps(result_data) + "\n", encoding="utf-8")
    config_path = scripts / "scientific_dag.json"
    config_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "analysis_acceptance": acceptance or {"schema_version": 1, "kind": "generic_full_rank"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "campaign": campaign,
        "analysis_script": analysis_script,
        "result": result_path,
        "config": config_path,
        "verdict": results / "analysis-verdict.json",
    }


def _verify(paths: dict[str, Path]) -> dict:
    return verify_analysis(
        paths["result"],
        paths["config"],
        paths["analysis_script"],
        paths["campaign"],
        paths["verdict"],
    )


def _seed_parent_gates(state_path: Path, artifact: Path) -> None:
    for gate in ("PROJECTOR_AUDIT", "REFERENCE", "CHILDREN_MATERIALIZED", "RESPONSES"):
        complete(state_path, gate, [artifact], f"fixture {gate}")


def _record_analysis_gate(paths: dict[str, Path], verdict: dict, *, include_evidence: bool = True) -> Path:
    artifact = paths["campaign"] / "results" / "prerequisite.json"
    artifact.write_text('{"fixture":true}\n', encoding="utf-8")
    state_path = paths["campaign"] / "results" / "scientific_dag_state.json"
    _seed_parent_gates(state_path, artifact)
    status = "VALIDATED" if verdict["gate_decision"] == "ACCEPTED" else "RECORDED"
    complete(
        state_path,
        "ANALYSIS",
        [paths["result"], paths["verdict"]],
        "typed analysis verdict recorded",
        status=status,
        analysis_verdict=paths["verdict"],
    )
    if include_evidence:
        evidence_report = paths["campaign"] / "results" / "evidence" / "scientific_dag_protocol.json"
        evidence_report.parent.mkdir(parents=True, exist_ok=True)
        evidence_report.write_text(report(state_path) + "\n", encoding="utf-8")
        complete(
            state_path,
            "EVIDENCE",
            [evidence_report, paths["result"], paths["verdict"]],
            "protocol and analysis record captured; physical acceptance remains separately classified",
            status="RECORDED",
        )
        evidence_report.write_text(report(state_path) + "\n", encoding="utf-8")
    return state_path


def _hook(paths: dict[str, Path], *, gate_decision: str = "RECORDED_ONLY", physical: str = "NOT_ESTABLISHED") -> Path:
    evidence = paths["campaign"] / "results" / "response-receipt.json"
    evidence.write_text('{"receipt":"locked fixture evidence"}\n', encoding="utf-8")
    script = paths["campaign"] / "scripts" / "validate_analysis.py"
    script.write_text(
        """import hashlib, json, sys
from pathlib import Path
result = Path(sys.argv[sys.argv.index('--result') + 1])
campaign = Path(__file__).resolve().parents[1]
evidence = campaign / 'results/response-receipt.json'
source = json.loads(result.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
print(json.dumps({
  'schema_version': 1,
  'campaign_id': 'fixture-campaign',
  'source_status': source['status'],
  'analysis_state': source['status'],
  'gate_decision': %r,
  'physical_acceptance': %r,
  'evidence': [{'path': 'results/response-receipt.json', 'sha256': sha(evidence)}],
}))
""" % (gate_decision, physical),
        encoding="utf-8",
    )
    acceptance = {
        "schema_version": 1,
        "kind": "campaign_hook",
        "campaign_id": "fixture-campaign",
        "validator_script": "scripts/validate_analysis.py",
        "validator_sha256": _sha(script),
    }
    result = json.loads(paths["result"].read_text(encoding="utf-8"))
    result["campaign_id"] = "fixture-campaign"
    paths["result"].write_text(json.dumps(result) + "\n", encoding="utf-8")
    paths["config"].write_text(
        json.dumps({"schema_version": 1, "analysis_acceptance": acceptance}) + "\n",
        encoding="utf-8",
    )
    paths["hook"] = script
    paths["evidence"] = evidence
    return script


def test_generic_full_rank_pass_requires_positive_integer_ranks(tmp_path):
    paths = _base(tmp_path)

    verdict = _verify(paths)

    assert verdict["schema"] == "siestaflow-analysis-verdict-v1"
    assert verdict["source_status"] == "PASS"
    assert verdict["analysis_state"] == "PASS"
    assert verdict["gate_decision"] == "ACCEPTED"
    assert verdict["physical_acceptance"] == "NOT_ASSESSED"
    assert verdict["provenance"]["source_result_sha256"] == _sha(paths["result"])


@pytest.mark.parametrize(
    "patch",
    [
        {"matrix_dimension": None, "rank_chi0": None, "rank_chi": None},
        {"matrix_dimension": 0, "rank_chi0": 0, "rank_chi": 0},
        {"matrix_dimension": True, "rank_chi0": True, "rank_chi": True},
        {"matrix_dimension": 16, "rank_chi0": "16", "rank_chi": 16},
        {"matrix_dimension": 16, "rank_chi0": 16, "__remove__": ["rank_chi"]},
        {"matrix_dimension": 16, "rank_chi0": 15, "rank_chi": 16},
        {"matrix_dimension": 16, "rank_chi0": 16, "rank_chi": 0},
    ],
)
def test_generic_full_rank_rejects_malformed_or_incomplete_rank_evidence(tmp_path, patch):
    paths = _base(tmp_path)
    result = {"status": "PASS", "matrix_dimension": 16, "rank_chi0": 16, "rank_chi": 16}
    patch = dict(patch)
    remove = patch.pop("__remove__", [])
    result.update(patch)
    for key in remove:
        result.pop(key, None)
    paths["result"].write_text(json.dumps(result) + "\n", encoding="utf-8")

    with pytest.raises(ValueError):
        _verify(paths)

    assert not paths["verdict"].exists()


def test_generic_full_rank_rejects_native_fail_status(tmp_path):
    paths = _base(tmp_path, status="FAIL")

    with pytest.raises(ValueError, match="requires source status PASS"):
        _verify(paths)

    assert not paths["verdict"].exists()


@pytest.mark.parametrize("status", [None, "", True, 0, [], {}])
def test_analysis_contract_rejects_malformed_native_status(tmp_path, status):
    paths = _base(tmp_path)
    result = json.loads(paths["result"].read_text(encoding="utf-8"))
    result["status"] = status
    paths["result"].write_text(json.dumps(result) + "\n", encoding="utf-8")

    with pytest.raises(ValueError):
        _verify(paths)

    assert not paths["verdict"].exists()


def test_numerical_only_rejects_without_explicit_campaign_hook(tmp_path):
    paths = _base(tmp_path, status="REPORTABLE_NUMERICAL_U_INTERVAL")

    with pytest.raises(ValueError, match="requires source status PASS"):
        _verify(paths)

    assert not paths["verdict"].exists()


def test_campaign_hook_records_numerical_only_without_physical_acceptance(tmp_path):
    paths = _base(tmp_path, status="REPORTABLE_NUMERICAL_U_INTERVAL")
    _hook(paths)

    verdict = _verify(paths)

    assert verdict["source_status"] == "REPORTABLE_NUMERICAL_U_INTERVAL"
    assert verdict["analysis_state"] == "REPORTABLE_NUMERICAL_U_INTERVAL"
    assert verdict["gate_decision"] == "RECORDED_ONLY"
    assert verdict["physical_acceptance"] == "NOT_ESTABLISHED"
    assert verdict["provenance"]["source_result_sha256"] == _sha(paths["result"])
    assert verdict["provenance"]["config_sha256"] == _sha(paths["config"])
    assert verdict["provenance"]["analysis_script_sha256"] == _sha(paths["analysis_script"])
    assert verdict["provenance"]["campaign_validator_sha256"] == _sha(paths["hook"])
    assert {item["path"] for item in verdict["provenance"]["verified_files"]} >= {
        "results/analysis.json",
        "scripts/scientific_dag.json",
        "scripts/analyze.py",
        "scripts/validate_analysis.py",
        "results/response-receipt.json",
    }
    state_path = _record_analysis_gate(paths, verdict)
    state = load(state_path)
    assert state["gates"]["ANALYSIS"]["status"] == "RECORDED"
    assert state["gates"]["ANALYSIS"]["analysis"]["physical_acceptance"] == "NOT_ESTABLISHED"
    assert state["gates"]["EVIDENCE"]["status"] == "RECORDED"
    evidence_text = (paths["campaign"] / "results" / "evidence" / "scientific_dag_protocol.json").read_text(encoding="utf-8")
    evidence_json = json.loads(evidence_text)
    assert "does not itself assert physical validation" in evidence_json["evidence_scope"]
    analysis = next(gate for gate in evidence_json["gates"] if gate["gate"] == "ANALYSIS")
    assert analysis["physical_acceptance"] == "NOT_ESTABLISHED"
    assert "physical acceptance remains separately classified" in state["gates"]["EVIDENCE"]["detail"]


def test_generic_full_rank_acceptance_is_algebra_only_in_gate5_report(tmp_path):
    paths = _base(tmp_path)
    verdict = _verify(paths)

    state_path = _record_analysis_gate(paths, verdict)
    state = load(state_path)
    evidence_json = json.loads(report(state_path))
    analysis = next(gate for gate in evidence_json["gates"] if gate["gate"] == "ANALYSIS")
    evidence = next(gate for gate in evidence_json["gates"] if gate["gate"] == "EVIDENCE")
    assert analysis["status"] == "VALIDATED"
    assert analysis["gate_decision"] == "ACCEPTED"
    assert analysis["physical_acceptance"] == "NOT_ASSESSED"
    assert evidence["status"] == "RECORDED"
    assert "does not itself assert physical validation" in evidence_json["evidence_scope"]
    assert "physical acceptance remains separately classified" in state["gates"]["EVIDENCE"]["detail"]


def test_numerical_only_cannot_claim_gate_or_physical_acceptance(tmp_path):
    paths = _base(tmp_path, status="REPORTABLE_NUMERICAL_U_INTERVAL")
    _hook(paths, gate_decision="ACCEPTED", physical="ACCEPTED")

    with pytest.raises(ValueError):
        _verify(paths)

    assert not paths["verdict"].exists()


def test_numerical_only_cannot_be_gate_accepted_even_without_physical_acceptance(tmp_path):
    paths = _base(tmp_path, status="REPORTABLE_NUMERICAL_U_INTERVAL")
    _hook(paths, gate_decision="ACCEPTED", physical="NOT_ESTABLISHED")

    with pytest.raises(ValueError):
        _verify(paths)

    assert not paths["verdict"].exists()


def test_campaign_hook_cannot_promote_native_fail_to_accepted(tmp_path):
    paths = _base(tmp_path, status="FAIL")
    _hook(paths, gate_decision="ACCEPTED", physical="ACCEPTED")

    with pytest.raises(ValueError):
        _verify(paths)

    assert not paths["verdict"].exists()


def test_campaign_hook_must_exist_and_match_its_pinned_hash(tmp_path):
    paths = _base(
        tmp_path,
        status="REPORTABLE_NUMERICAL_U_INTERVAL",
        acceptance={
            "schema_version": 1,
            "kind": "campaign_hook",
            "campaign_id": "fixture-campaign",
            "validator_script": "scripts/missing_validator.py",
            "validator_sha256": "0" * 64,
        },
    )

    with pytest.raises(ValueError, match="missing"):
        _verify(paths)

    assert not paths["verdict"].exists()


@pytest.mark.parametrize("mutation", ["result", "config", "analysis_script", "hook", "evidence"])
def test_provenance_detects_mutated_gate_inputs_before_resume(tmp_path, mutation):
    paths = _base(tmp_path, status="REPORTABLE_NUMERICAL_U_INTERVAL")
    _hook(paths)
    verdict = _verify(paths)
    verified = {item["path"]: item["sha256"] for item in verdict["provenance"]["verified_files"]}
    relative = {
        "result": "results/analysis.json",
        "config": "scripts/scientific_dag.json",
        "analysis_script": "scripts/analyze.py",
        "hook": "scripts/validate_analysis.py",
        "evidence": "results/response-receipt.json",
    }[mutation]
    target = paths["campaign"] / relative
    state_path = _record_analysis_gate(paths, verdict, include_evidence=False)
    assert is_complete(state_path, "ANALYSIS", [paths["result"], paths["verdict"]], paths["verdict"])
    target.write_text(target.read_text(encoding="utf-8") + "# changed after verdict\n", encoding="utf-8")

    assert verified[relative] != _sha(target)
    assert not is_complete(state_path, "ANALYSIS", [paths["result"], paths["verdict"]], paths["verdict"])


def test_mutated_verdict_invalidates_analysis_ledger_before_resume(tmp_path):
    paths = _base(tmp_path)
    verdict = _verify(paths)
    state_path = _record_analysis_gate(paths, verdict, include_evidence=False)

    assert is_complete(state_path, "ANALYSIS", [paths["result"], paths["verdict"]], paths["verdict"])
    paths["verdict"].write_text(paths["verdict"].read_text(encoding="utf-8") + " ", encoding="utf-8")

    assert not is_complete(state_path, "ANALYSIS", [paths["result"], paths["verdict"]], paths["verdict"])


def test_failed_reanalysis_cannot_resume_with_stale_analysis_or_evidence(tmp_path):
    paths = _base(tmp_path)
    verdict = _verify(paths)
    state_path = _record_analysis_gate(paths, verdict)
    assert is_complete(state_path, "ANALYSIS", [paths["result"], paths["verdict"]], paths["verdict"])

    # The Slurm template invalidates ANALYSIS/EVIDENCE before rerunning analysis.
    invalidate_from(state_path, "ANALYSIS")
    result = json.loads(paths["result"].read_text(encoding="utf-8"))
    result["status"] = "FAIL"
    paths["result"].write_text(json.dumps(result) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="requires source status PASS"):
        _verify(paths)

    state = load(state_path)
    assert "ANALYSIS" not in state["gates"]
    assert "EVIDENCE" not in state["gates"]
    assert not is_complete(state_path, "ANALYSIS", [paths["result"], paths["verdict"]], paths["verdict"])
