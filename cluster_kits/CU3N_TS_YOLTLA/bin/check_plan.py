#!/usr/bin/env python3
"""Check expected direct, TS, or one-column plan dimensions."""

import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("mode", choices=("direct", "ts", "probe"))
parser.add_argument("plan_dir", type=Path)
args = parser.parse_args()
plan = json.loads(
    (args.plan_dir / "resolved_perturbation_plan.json").read_text(encoding="utf-8")
)
coverage = plan.get("coverage", {})
classes = coverage.get("classes", [])
reduced = [group for group in classes if len(group.get("members", [])) > 1]
summary = {
    "mode": args.mode,
    "status": plan.get("status"),
    "reason_codes": plan.get("reason_codes", []),
    "inventory_status": plan.get("inventory", {}).get("status"),
    "orbit_count": len(classes),
    "reduced_orbits": [
        {
            "representative": group.get("representative"),
            "members": len(group.get("members", [])),
            "shadow": group.get("shadow"),
        }
        for group in reduced
    ],
    "computed_columns": len(plan.get("computed_columns", [])),
    "response_run_specs": len(plan.get("run_specs", [])),
    "planner_version": plan.get("planner_version"),
}
problems: list[str] = []
if summary["inventory_status"] != "OK":
    problems.append("inventory status is not OK")
if args.mode == "direct":
    if summary["computed_columns"] != 24 or summary["response_run_specs"] != 288:
        problems.append("expected 24 columns and 288 response run specs")
    if reduced:
        problems.append("direct plan contains reduced orbits")
elif args.mode == "probe":
    if summary["computed_columns"] != 1 or summary["response_run_specs"] != 12:
        problems.append("expected one column and 12 response run specs")
    if reduced:
        problems.append("one-column probe contains reduced orbits")
elif args.mode == "ts":
    if summary["computed_columns"] != 6 or summary["response_run_specs"] != 72:
        problems.append("expected six columns and 72 response run specs")
    if len(reduced) != 3 or any(len(group.get("members", [])) != 8 for group in reduced):
        problems.append("expected three reduced orbits with eight members each")
    if any(not group.get("shadow") for group in reduced):
        problems.append("each reduced orbit must have a shadow site")
    if not set(summary["reason_codes"]) <= {"SHADOW_PENDING"}:
        problems.append("unexpected TS plan reason codes")

print(json.dumps(summary, indent=2, sort_keys=True))
if problems:
    raise SystemExit("PLAN_CHECK_FAIL: " + "; ".join(problems))
print("PLAN_CHECK_PASS", args.mode)
