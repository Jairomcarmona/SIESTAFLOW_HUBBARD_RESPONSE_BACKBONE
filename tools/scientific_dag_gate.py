"""Persistent scientific gates for a resumable LR-U DAG.

The ledger is deliberately small.  It records that a gate passed only after
the caller has validated the relevant artifacts.  On resume, the Slurm script
must still inspect those artifacts; the ledger is not evidence by itself.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path


COMPLETION_STATUSES = {"VALIDATED", "RECORDED"}
ANALYSIS_DECISIONS = {"ACCEPTED", "RECORDED_ONLY", "REJECTED"}
ANALYSIS_VERDICT_SCHEMA = "siestaflow-analysis-verdict-v1"

ORDER = (
    "PROJECTOR_AUDIT",
    "REFERENCE",
    "CHILDREN_MATERIALIZED",
    "RESPONSES",
    "ANALYSIS",
    "EVIDENCE",
)
PARENTS = {gate: ORDER[index - 1] for index, gate in enumerate(ORDER) if index}


def load(path: Path) -> dict:
    if not path.exists():
        return {"schema_version": 2, "gates": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") not in (1, 2) or not isinstance(data.get("gates"), dict):
        raise ValueError(f"invalid scientific-DAG state file: {path}")
    data["schema_version"] = 2
    return data


def save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        json.dump(data, stream, indent=2)
        stream.write("\n")
        temporary = Path(stream.name)
    os.replace(temporary, path)


def required_present(requirements: list[Path]) -> bool:
    return all(path.is_file() and path.stat().st_size > 0 for path in requirements)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_analysis_verdict(verdict_path: Path, status: str | None = None) -> dict:
    try:
        verdict = json.loads(verdict_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read analysis verdict {verdict_path}: {exc}") from exc
    if not isinstance(verdict, dict) or verdict.get("schema") != ANALYSIS_VERDICT_SCHEMA:
        raise ValueError("analysis verdict has an unsupported schema")
    decision = verdict.get("gate_decision")
    if decision not in ANALYSIS_DECISIONS:
        raise ValueError("analysis verdict has an invalid gate_decision")
    expected_status = "VALIDATED" if decision == "ACCEPTED" else "RECORDED"
    if status is not None and status != expected_status:
        raise ValueError(f"analysis verdict {decision} requires ledger status {expected_status}")
    provenance = verdict.get("provenance")
    if not isinstance(provenance, dict) or not isinstance(provenance.get("campaign_root"), str):
        raise ValueError("analysis verdict is missing provenance campaign_root")
    files = provenance.get("verified_files")
    if not isinstance(files, list) or not files:
        raise ValueError("analysis verdict must bind its source/config/script files")
    return verdict


def _analysis_inputs_current(verdict: dict) -> bool:
    provenance = verdict.get("provenance", {})
    root = Path(provenance.get("campaign_root", "")).resolve()
    if not root.is_dir():
        return False
    files = provenance.get("verified_files")
    if not isinstance(files, list) or not files:
        return False
    seen: set[str] = set()
    for item in files:
        if not isinstance(item, dict):
            return False
        relative, expected = item.get("path"), item.get("sha256")
        if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
            return False
        if not isinstance(expected, str) or len(expected) != 64:
            return False
        path = (root / Path(relative)).resolve()
        try:
            canonical = path.relative_to(root).as_posix()
        except ValueError:
            return False
        if canonical in seen or not path.is_file():
            return False
        seen.add(canonical)
        if _sha256(path) != expected:
            return False
    return True


def _analysis_verdict_semantics_valid(verdict: dict) -> bool:
    provenance = verdict.get("provenance", {})
    root = Path(provenance.get("campaign_root", "")).resolve()
    files = provenance.get("verified_files")
    if not isinstance(files, list):
        return False
    hashes = {item.get("path"): item.get("sha256") for item in files if isinstance(item, dict)}
    result_relative = provenance.get("source_result_path")
    config_relative = provenance.get("config_path")
    if not isinstance(result_relative, str) or not isinstance(config_relative, str):
        return False
    if hashes.get(result_relative) != provenance.get("source_result_sha256"):
        return False
    if hashes.get(config_relative) != provenance.get("config_sha256"):
        return False
    try:
        result_path = (root / result_relative).resolve()
        config_path = (root / config_relative).resolve()
        result_path.relative_to(root)
        config_path.relative_to(root)
        result = json.loads(result_path.read_text(encoding="utf-8"))
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return False
    if not isinstance(result, dict) or not isinstance(config, dict):
        return False
    source_status = verdict.get("source_status")
    analysis_state = verdict.get("analysis_state")
    decision = verdict.get("gate_decision")
    physical = verdict.get("physical_acceptance")
    if not isinstance(source_status, str) or result.get("status") != source_status:
        return False
    if not isinstance(analysis_state, str) or decision not in ANALYSIS_DECISIONS:
        return False
    if physical not in {"ACCEPTED", "REJECTED", "NOT_ESTABLISHED", "NOT_ASSESSED", "NOT_APPLICABLE"}:
        return False
    if source_status == "FAIL" and decision != "REJECTED":
        return False
    numerical_interval = "REPORTABLE_NUMERICAL_U_INTERVAL"
    if source_status == numerical_interval or analysis_state == numerical_interval:
        if source_status != numerical_interval or analysis_state != numerical_interval:
            return False
        if decision != "RECORDED_ONLY" or physical != "NOT_ESTABLISHED":
            return False
    if physical == "ACCEPTED" and (decision != "ACCEPTED" or result.get("physical_acceptance") != "ACCEPTED"):
        return False

    contract = config.get("analysis_acceptance")
    if not isinstance(contract, dict) or contract.get("schema_version") != 1:
        return False
    if contract.get("kind") == "generic_full_rank":
        if source_status != "PASS" or decision != "ACCEPTED" or physical != "NOT_ASSESSED":
            return False
        dimension = result.get("matrix_dimension")
        rank0, rank = result.get("rank_chi0"), result.get("rank_chi")
        if any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in (dimension, rank0, rank)):
            return False
        if rank0 != dimension or rank != dimension:
            return False
        if verdict.get("analysis_state") != "PASS" or verdict.get("campaign_id") is not None:
            return False
    elif contract.get("kind") == "campaign_hook":
        campaign_id = contract.get("campaign_id")
        validator_relative = contract.get("validator_script")
        validator_hash = contract.get("validator_sha256")
        if not isinstance(campaign_id, str) or verdict.get("campaign_id") != campaign_id:
            return False
        if result.get("campaign_id") != campaign_id:
            return False
        if not isinstance(validator_relative, str) or hashes.get(validator_relative) != validator_hash:
            return False
    else:
        return False
    return True


def complete(
    path: Path,
    gate: str,
    requirements: list[Path],
    detail: str | None,
    status: str = "VALIDATED",
    analysis_verdict: Path | None = None,
) -> None:
    if gate not in ORDER:
        raise ValueError(f"unknown gate {gate!r}")
    if status not in COMPLETION_STATUSES:
        raise ValueError(f"invalid completion status {status!r}")
    if not required_present(requirements):
        missing = [str(item) for item in requirements if not item.is_file() or item.stat().st_size == 0]
        raise ValueError(f"cannot complete {gate}; missing or empty: {', '.join(missing)}")
    verdict = None
    if gate == "ANALYSIS":
        if analysis_verdict is None:
            raise ValueError("ANALYSIS completion requires --analysis-verdict")
        verdict = _read_analysis_verdict(analysis_verdict, status)
        if not _analysis_inputs_current(verdict) or not _analysis_verdict_semantics_valid(verdict):
            raise ValueError("analysis inputs changed or are unverifiable; re-run the analysis contract")
    data = load(path)
    parent = PARENTS.get(gate)
    if parent and data["gates"].get(parent, {}).get("status") not in COMPLETION_STATUSES:
        raise ValueError(f"cannot complete {gate}; parent gate {parent} is not complete")
    recorded_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    record = {
        "status": status,
        "recorded_at_utc": recorded_at,
        "required_artifacts": [str(item) for item in requirements],
        "detail": detail or "",
    }
    if status == "VALIDATED":
        record["validated_at_utc"] = recorded_at
    if verdict is not None and analysis_verdict is not None:
        record["analysis"] = {
            "verdict_path": str(analysis_verdict.resolve()),
            "verdict_sha256": _sha256(analysis_verdict),
            "source_status": verdict["source_status"],
            "analysis_state": verdict["analysis_state"],
            "gate_decision": verdict["gate_decision"],
            "physical_acceptance": verdict["physical_acceptance"],
            "campaign_id": verdict.get("campaign_id"),
        }
    data["gates"][gate] = record
    save(path, data)


def is_complete(
    path: Path,
    gate: str,
    requirements: list[Path],
    analysis_verdict: Path | None = None,
) -> bool:
    data = load(path)
    record = data["gates"].get(gate, {})
    if record.get("status") not in COMPLETION_STATUSES or not required_present(requirements):
        return False
    if gate != "ANALYSIS":
        return True
    if analysis_verdict is None or not analysis_verdict.is_file():
        return False
    analysis = record.get("analysis", {})
    if analysis.get("verdict_path") != str(analysis_verdict.resolve()):
        return False
    if analysis.get("verdict_sha256") != _sha256(analysis_verdict):
        return False
    try:
        verdict = _read_analysis_verdict(analysis_verdict, record.get("status"))
    except ValueError:
        return False
    if not _analysis_inputs_current(verdict) or not _analysis_verdict_semantics_valid(verdict):
        return False
    return all(analysis.get(key) == verdict.get(source) for key, source in (
        ("source_status", "source_status"),
        ("analysis_state", "analysis_state"),
        ("gate_decision", "gate_decision"),
        ("physical_acceptance", "physical_acceptance"),
        ("campaign_id", "campaign_id"),
    ))


def invalidate_from(path: Path, gate: str) -> None:
    if gate not in ORDER:
        raise ValueError(f"unknown gate {gate!r}")
    data = load(path)
    start = ORDER.index(gate)
    for item in ORDER[start:]:
        data["gates"].pop(item, None)
    save(path, data)


def report(path: Path) -> str:
    data = load(path)
    rows = []
    for gate in ORDER:
        record = data["gates"].get(gate, {})
        row = {
            "gate": gate,
            "status": record.get("status", "PENDING"),
            "recorded_at_utc": record.get("recorded_at_utc") or record.get("validated_at_utc"),
        }
        if gate == "ANALYSIS" and isinstance(record.get("analysis"), dict):
            row.update(record["analysis"])
        rows.append(row)
    return json.dumps({
        "schema_version": 2,
        "state_file": str(path),
        "evidence_scope": "protocol and analysis record; does not itself assert physical validation",
        "gates": rows,
    }, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("complete", "is-complete"):
        command = commands.add_parser(name)
        command.add_argument("gate", choices=ORDER)
        command.add_argument("--require", type=Path, action="append", default=[])
        if name == "complete":
            command.add_argument("--detail")
            command.add_argument("--status", choices=sorted(COMPLETION_STATUSES), default="VALIDATED")
            command.add_argument("--analysis-verdict", type=Path)
        else:
            command.add_argument("--analysis-verdict", type=Path)
    invalidate = commands.add_parser("invalidate")
    invalidate.add_argument("--from", dest="from_gate", choices=ORDER, required=True)
    commands.add_parser("report")
    args = parser.parse_args()
    if args.command == "complete":
        complete(args.state, args.gate, args.require, args.detail, args.status, args.analysis_verdict)
    elif args.command == "is-complete":
        raise SystemExit(0 if is_complete(args.state, args.gate, args.require, args.analysis_verdict) else 1)
    elif args.command == "invalidate":
        invalidate_from(args.state, args.from_gate)
    else:
        print(report(args.state))


if __name__ == "__main__":
    main()
