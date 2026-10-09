#!/usr/bin/env python3
"""Build a one-site FDF by removing only non-representative DFTU.Proj rows."""

import difflib
import json
import os
import re
import sys
from pathlib import Path

root = Path(os.environ["ROOT"])
plan_dir = Path(sys.argv[1])
plan = json.loads(
    (plan_dir / "resolved_perturbation_plan.json").read_text(encoding="utf-8")
)
classes = plan["coverage"]["classes"]
if not classes:
    raise SystemExit("ERROR: TS plan has no coverage classes")
representative = str(classes[0]["representative"]).split("@", 1)[0]
source = root / "inputs/reference.fdf"
lines = source.read_text(encoding="utf-8").splitlines()
start = next(
    (i for i, line in enumerate(lines) if line.strip().casefold() == "%block dftu.proj"),
    None,
)
if start is None:
    raise SystemExit("ERROR: DFTU.Proj block is missing")
end = next(
    (
        i
        for i in range(start + 1, len(lines))
        if lines[i].strip().casefold() == "%endblock dftu.proj"
    ),
    None,
)
if end is None:
    raise SystemExit("ERROR: DFTU.Proj block is not closed")

record_start = re.compile(r"^\s*(CuLR\d{2})\s+1\s*$")
records: dict[str, tuple[int, int]] = {}
cursor = start + 1
while cursor < end:
    if not lines[cursor].strip():
        cursor += 1
        continue
    match = record_start.fullmatch(lines[cursor])
    if match is None:
        raise SystemExit(f"ERROR: unexpected projector record at line {cursor + 1}")
    label = match.group(1)
    if cursor + 3 >= end or label in records:
        raise SystemExit(f"ERROR: malformed or duplicate projector record {label}")
    if any(not lines[cursor + offset].strip() for offset in (1, 2, 3)):
        raise SystemExit(f"ERROR: incomplete four-line projector record {label}")
    records[label] = (cursor, cursor + 4)
    cursor += 4
if set(records) != {f"CuLR{i:02d}" for i in range(24)}:
    raise SystemExit("ERROR: expected exactly CuLR00 through CuLR23 projector records")
if representative not in records:
    raise SystemExit(f"ERROR: representative {representative} has no projector record")

removed = {
    index
    for label, (first, last) in records.items()
    if label != representative
    for index in range(first, last)
}
output_lines = [line for index, line in enumerate(lines) if index not in removed]
diff = list(
    difflib.unified_diff(
        lines, output_lines, fromfile="reference.fdf", tofile="probe.fdf", lineterm=""
    )
)
if any(line.startswith("+") and not line.startswith("+++") for line in diff):
    raise SystemExit("ERROR: probe generation added FDF lines")
allowed_removed = {
    line
    for label, (first, last) in records.items()
    if label != representative
    for line in lines[first:last]
}
deleted = [line[1:] for line in diff if line.startswith("-") and not line.startswith("---")]
if any(line not in allowed_removed for line in deleted):
    raise SystemExit("ERROR: probe diff changes content outside DFTU.Proj records")

probe_dir = root / "probe"
probe_dir.mkdir(exist_ok=True)
(probe_dir / "probe.fdf").write_text("\n".join(output_lines) + "\n", encoding="utf-8")
(probe_dir / "probe.diff").write_text("\n".join(diff) + "\n", encoding="utf-8")
config = json.loads((root / "config/lr-config.json").read_text(encoding="utf-8"))
config["sites"] = [site for site in config["sites"] if site["site_id"] == representative]
if len(config["sites"]) != 1:
    raise SystemExit("ERROR: failed to reduce the LR config to one site")
config["material"] = "Cu3N-PBE-SC222-one-column-probe-yoltla"
(probe_dir / "probe-lr-config.json").write_text(
    json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
print("PROBE_INPUTS_WRITTEN", representative, "removed_projector_records=23")
