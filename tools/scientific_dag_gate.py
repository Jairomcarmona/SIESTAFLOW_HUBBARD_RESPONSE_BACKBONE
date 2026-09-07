"""Persistent scientific gates for a resumable LR-U DAG.

The ledger is deliberately small.  It records that a gate passed only after
the caller has validated the relevant artifacts.  On resume, the Slurm script
must still inspect those artifacts; the ledger is not evidence by itself.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path


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
        return {"schema_version": 1, "gates": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or not isinstance(data.get("gates"), dict):
        raise ValueError(f"invalid scientific-DAG state file: {path}")
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


def complete(path: Path, gate: str, requirements: list[Path], detail: str | None) -> None:
    if gate not in ORDER:
        raise ValueError(f"unknown gate {gate!r}")
    if not required_present(requirements):
        missing = [str(item) for item in requirements if not item.is_file() or item.stat().st_size == 0]
        raise ValueError(f"cannot complete {gate}; missing or empty: {', '.join(missing)}")
    data = load(path)
    parent = PARENTS.get(gate)
    if parent and data["gates"].get(parent, {}).get("status") != "VALIDATED":
        raise ValueError(f"cannot complete {gate}; parent gate {parent} is not VALIDATED")
    data["gates"][gate] = {
        "status": "VALIDATED",
        "validated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "required_artifacts": [str(item) for item in requirements],
        "detail": detail or "",
    }
    save(path, data)


def is_complete(path: Path, gate: str, requirements: list[Path]) -> bool:
    data = load(path)
    return data["gates"].get(gate, {}).get("status") == "VALIDATED" and required_present(requirements)


def report(path: Path) -> str:
    data = load(path)
    rows = []
    for gate in ORDER:
        record = data["gates"].get(gate, {})
        rows.append({"gate": gate, "status": record.get("status", "PENDING"), "validated_at_utc": record.get("validated_at_utc")})
    return json.dumps({"state_file": str(path), "gates": rows}, indent=2)


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
    commands.add_parser("report")
    args = parser.parse_args()
    if args.command == "complete":
        complete(args.state, args.gate, args.require, args.detail)
    elif args.command == "is-complete":
        raise SystemExit(0 if is_complete(args.state, args.gate, args.require) else 1)
    else:
        print(report(args.state))


if __name__ == "__main__":
    main()
