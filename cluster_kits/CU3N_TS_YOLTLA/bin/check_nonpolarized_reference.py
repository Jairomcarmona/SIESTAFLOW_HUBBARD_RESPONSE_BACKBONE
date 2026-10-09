#!/usr/bin/env python3
"""Fail closed unless both FDF and output prove one-spin mode."""

import argparse
import hashlib
import json
import re
from pathlib import Path


def active_spin_line(path: Path) -> int | None:
    pattern = re.compile(r"^\s*Spin\s+non-polarized\s*$", re.IGNORECASE)
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if pattern.fullmatch(line.split("#", 1)[0]):
            return number
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("fdf", type=Path)
    parser.add_argument("siesta_output", type=Path)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    fdf_line = active_spin_line(args.fdf)
    if fdf_line is None:
        raise SystemExit("ERROR: active FDF line 'Spin non-polarized' is missing")

    patterns = {
        "spin_configuration": re.compile(
            r"^\s*redata:\s*Spin configuration\s*=\s*none\s*$", re.IGNORECASE
        ),
        "spin_components": re.compile(
            r"^\s*redata:\s*Number of spin components\s*=\s*1\s*$", re.IGNORECASE
        ),
        "time_reversal": re.compile(
            r"^\s*redata:\s*Time-Reversal Symmetry\s*=\s*T\s*$", re.IGNORECASE
        ),
    }
    found: dict[str, int] = {}
    for number, line in enumerate(
        args.siesta_output.read_text(encoding="utf-8", errors="replace").splitlines(),
        start=1,
    ):
        for key, pattern in patterns.items():
            if key not in found and pattern.fullmatch(line):
                found[key] = number
    missing = sorted(set(patterns) - set(found))
    if missing:
        raise SystemExit("ERROR: missing non-polarized markers: " + ", ".join(missing))

    record = {
        "schema": "cu3n_ts_yoltla.nonpolarized_reference_check.v1",
        "status": "PASS",
        "fdf": str(args.fdf.resolve()),
        "fdf_sha256": hashlib.sha256(args.fdf.read_bytes()).hexdigest(),
        "fdf_spin_line": fdf_line,
        "siesta_output": str(args.siesta_output.resolve()),
        "siesta_output_sha256": hashlib.sha256(args.siesta_output.read_bytes()).hexdigest(),
        "marker_lines": found,
    }
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    print("NONPOLARIZED_REFERENCE_PASS")
    print(f"FDF spin line: {fdf_line}")
    print(
        "Output marker lines: "
        f"spin={found['spin_configuration']}, "
        f"components={found['spin_components']}, "
        f"time-reversal={found['time_reversal']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
