"""Validate and provenance-bind a scientific-DAG analysis result.

The generic contract accepts only a full-rank ``PASS``. Campaign-specific
interpretation requires an explicitly hash-pinned validator hook. Native result
statuses are copied verbatim into the verdict; recording an analysis is not a
claim of physical acceptance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


VERDICT_SCHEMA = "siestaflow-analysis-verdict-v1"
HOOK_DECISIONS = {"ACCEPTED", "RECORDED_ONLY", "REJECTED"}
PHYSICAL_STATES = {"ACCEPTED", "REJECTED", "NOT_ESTABLISHED", "NOT_ASSESSED", "NOT_APPLICABLE"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {label} JSON: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object: {path}")
    return value


def _relative_file(root: Path, relative: str, label: str) -> tuple[Path, str]:
    if not isinstance(relative, str) or not relative.strip():
        raise ValueError(f"{label} path must be a non-empty campaign-relative path")
    raw = Path(relative)
    if raw.is_absolute():
        raise ValueError(f"{label} path must be relative to the campaign: {relative}")
    resolved_root = root.resolve()
    resolved = (resolved_root / raw).resolve()
    try:
        canonical = resolved.relative_to(resolved_root).as_posix()
    except ValueError as exc:
        raise ValueError(f"{label} path escapes campaign root: {relative}") from exc
    if not resolved.is_file():
        raise ValueError(f"{label} file is missing: {relative}")
    return resolved, canonical


def _provenance_file(root: Path, path: Path, label: str, inputs: dict[str, str]) -> None:
    try:
        relative = path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise ValueError(f"{label} must be inside the campaign root: {path}") from exc
    if not path.is_file():
        raise ValueError(f"{label} file is missing: {path}")
    inputs[relative] = _sha256(path)


def _campaign_hook_result(
    *,
    root: Path,
    result_path: Path,
    result: dict[str, Any],
    acceptance: dict[str, Any],
    inputs: dict[str, str],
) -> dict[str, Any]:
    campaign_id = acceptance.get("campaign_id")
    if not isinstance(campaign_id, str) or not campaign_id.strip():
        raise ValueError("campaign_hook requires a non-empty campaign_id")
    if result.get("campaign_id") != campaign_id:
        raise ValueError("native result campaign_id does not match the pinned campaign contract")

    validator_path, validator_relative = _relative_file(root, acceptance.get("validator_script"), "analysis validator")
    expected_validator_sha = acceptance.get("validator_sha256")
    if not isinstance(expected_validator_sha, str) or not SHA256_RE.fullmatch(expected_validator_sha):
        raise ValueError("campaign_hook requires a lowercase SHA-256 validator_sha256")
    validator_sha = _sha256(validator_path)
    if validator_sha != expected_validator_sha:
        raise ValueError("analysis validator differs from the hash pinned in scientific_dag.json")
    inputs[validator_relative] = validator_sha

    completed = subprocess.run(
        [sys.executable, str(validator_path), "--result", str(result_path)],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or f"exit {completed.returncode}"
        raise ValueError(f"campaign analysis validator rejected the result: {detail}")
    try:
        hook = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError("campaign analysis validator stdout must contain one JSON object") from exc
    if not isinstance(hook, dict) or hook.get("schema_version") != 1:
        raise ValueError("campaign analysis validator returned an unsupported contract")
    if hook.get("campaign_id") != campaign_id:
        raise ValueError("validator campaign_id does not match the pinned campaign contract")
    source_status = result.get("status")
    if not isinstance(source_status, str) or not source_status.strip():
        raise ValueError("native result must contain a non-empty status")
    if hook.get("source_status") != source_status:
        raise ValueError("validator must preserve the native result status verbatim")

    analysis_state = hook.get("analysis_state")
    gate_decision = hook.get("gate_decision")
    physical_acceptance = hook.get("physical_acceptance")
    if not isinstance(analysis_state, str) or not analysis_state.strip():
        raise ValueError("validator must provide a non-empty analysis_state")
    if gate_decision not in HOOK_DECISIONS:
        raise ValueError(f"validator gate_decision must be one of {sorted(HOOK_DECISIONS)}")
    if physical_acceptance not in PHYSICAL_STATES:
        raise ValueError(f"validator physical_acceptance must be one of {sorted(PHYSICAL_STATES)}")
    if source_status == "FAIL" and gate_decision != "REJECTED":
        raise ValueError("native status FAIL must remain a rejected campaign result")
    numerical_interval = "REPORTABLE_NUMERICAL_U_INTERVAL"
    if source_status == numerical_interval or analysis_state == numerical_interval:
        if source_status != numerical_interval or analysis_state != numerical_interval:
            raise ValueError("numerical interval status must be preserved in both source_status and analysis_state")
        if gate_decision != "RECORDED_ONLY" or physical_acceptance != "NOT_ESTABLISHED":
            raise ValueError("a reportable numerical U interval is recorded only; physical acceptance is NOT_ESTABLISHED")
    if physical_acceptance == "ACCEPTED":
        if gate_decision != "ACCEPTED" or result.get("physical_acceptance") != "ACCEPTED":
            raise ValueError("physical acceptance requires an explicit native result field and accepted hook decision")
    elif gate_decision == "REJECTED" and physical_acceptance == "ACCEPTED":
        raise ValueError("a rejected analysis cannot claim physical acceptance")

    evidence = hook.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        raise ValueError("campaign validator must bind at least one source-evidence file")
    verified_evidence: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in evidence:
        if not isinstance(item, dict):
            raise ValueError("validator evidence entries must be objects")
        evidence_path, evidence_relative = _relative_file(root, item.get("path"), "campaign evidence")
        if evidence_relative in seen:
            raise ValueError(f"duplicate campaign evidence path: {evidence_relative}")
        seen.add(evidence_relative)
        declared_sha = item.get("sha256")
        if not isinstance(declared_sha, str) or not SHA256_RE.fullmatch(declared_sha):
            raise ValueError(f"invalid SHA-256 for campaign evidence: {evidence_relative}")
        actual_sha = _sha256(evidence_path)
        if actual_sha != declared_sha:
            raise ValueError(f"campaign evidence hash mismatch: {evidence_relative}")
        inputs[evidence_relative] = actual_sha
        verified_evidence.append({"path": evidence_relative, "sha256": actual_sha})

    reason = hook.get("reason", "")
    if not isinstance(reason, str):
        raise ValueError("validator reason must be a string")
    return {
        "campaign_id": campaign_id,
        "source_status": source_status,
        "analysis_state": analysis_state,
        "gate_decision": gate_decision,
        "physical_acceptance": physical_acceptance,
        "reason": reason,
        "evidence": verified_evidence,
        "validator_sha256": validator_sha,
    }


def verify_analysis(
    result_path: Path,
    config_path: Path,
    analysis_script_path: Path,
    campaign_root: Path,
    output_path: Path,
) -> dict[str, Any]:
    """Validate an analysis result under its explicit configured contract."""
    root = campaign_root.resolve()
    result_path = result_path.resolve()
    config_path = config_path.resolve()
    analysis_script_path = analysis_script_path.resolve()
    output_path = output_path.resolve()
    result = _object(result_path, "analysis result")
    config = _object(config_path, "scientific DAG config")
    acceptance = config.get("analysis_acceptance")
    if not isinstance(acceptance, dict) or acceptance.get("schema_version") != 1:
        raise ValueError("scientific DAG config must declare analysis_acceptance schema_version 1")

    inputs: dict[str, str] = {}
    for path, label in (
        (result_path, "source result"),
        (config_path, "analysis contract/config"),
        (analysis_script_path, "analysis script"),
        (Path(__file__).resolve(), "analysis contract validator"),
    ):
        _provenance_file(root, path, label, inputs)

    source_status = result.get("status")
    if not isinstance(source_status, str) or not source_status.strip():
        raise ValueError("analysis result must contain a non-empty status")

    kind = acceptance.get("kind")
    contract_provenance: dict[str, Any] = {
        "contract_kind": kind,
        "campaign_id": None,
        "validator_sha256": None,
        "evidence": [],
    }
    if kind == "generic_full_rank":
        if source_status != "PASS":
            raise ValueError(f"generic_full_rank requires source status PASS; got {source_status!r}")
        dimension = result.get("matrix_dimension")
        rank_chi0 = result.get("rank_chi0")
        rank_chi = result.get("rank_chi")
        for name, value in (("matrix_dimension", dimension), ("rank_chi0", rank_chi0), ("rank_chi", rank_chi)):
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"generic_full_rank requires positive integer {name}")
        if rank_chi0 != dimension or rank_chi != dimension:
            raise ValueError("generic_full_rank requires rank_chi0 == rank_chi == matrix_dimension")
        analysis_state = "PASS"
        gate_decision = "ACCEPTED"
        physical_acceptance = "NOT_ASSESSED"
        reason = "generic full-rank algebra contract satisfied"
    elif kind == "campaign_hook":
        contract_provenance = _campaign_hook_result(
            root=root,
            result_path=result_path,
            result=result,
            acceptance=acceptance,
            inputs=inputs,
        )
        analysis_state = contract_provenance["analysis_state"]
        gate_decision = contract_provenance["gate_decision"]
        physical_acceptance = contract_provenance["physical_acceptance"]
        reason = contract_provenance["reason"]
    else:
        raise ValueError(f"unsupported or absent analysis acceptance kind: {kind!r}")

    verdict = {
        "schema": VERDICT_SCHEMA,
        "campaign_id": contract_provenance.get("campaign_id"),
        "source_status": source_status,
        "analysis_state": analysis_state,
        "gate_decision": gate_decision,
        "physical_acceptance": physical_acceptance,
        "reason": reason,
        "provenance": {
            "campaign_root": str(root),
            "source_result_path": result_path.relative_to(root).as_posix(),
            "config_path": config_path.relative_to(root).as_posix(),
            "analysis_script_path": analysis_script_path.relative_to(root).as_posix(),
            "verifier_path": Path(__file__).resolve().relative_to(root).as_posix(),
            "source_result_sha256": _sha256(result_path),
            "config_sha256": _sha256(config_path),
            "analysis_script_sha256": _sha256(analysis_script_path),
            "verifier_sha256": _sha256(Path(__file__).resolve()),
            "campaign_validator_sha256": contract_provenance.get("validator_sha256"),
            "verified_files": [{"path": path, "sha256": digest} for path, digest in sorted(inputs.items())],
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=output_path.parent, delete=False) as stream:
        json.dump(verdict, stream, indent=2, sort_keys=True)
        stream.write("\n")
        temporary = Path(stream.name)
    os.replace(temporary, output_path)
    return verdict


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-root", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--analysis-script", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        verdict = verify_analysis(args.result, args.config, args.analysis_script, args.campaign_root, args.output)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        parser.exit(2, f"analysis acceptance failed closed: {exc}\n")
    print(json.dumps({key: verdict[key] for key in ("source_status", "analysis_state", "gate_decision", "physical_acceptance")}, sort_keys=True))


if __name__ == "__main__":
    main()
