#!/usr/bin/env python3
"""Verify and record the expected Yoltla SIESTA runtime identity."""

import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

root = Path(os.environ["ROOT"])
executable = shutil.which("siesta")
if executable is None:
    sys.exit("ERROR: siesta is not on PATH; load module siesta/5.4.2")
executable_path = Path(executable).resolve()
actual_hash = hashlib.sha256(executable_path.read_bytes()).hexdigest()
expected = None
for line in (root / "config/expected.env").read_text().splitlines():
    if line.startswith("EXPECTED_SIESTA_SHA256="):
        expected = line.split("=", 1)[1].strip()
if actual_hash != expected:
    sys.exit(f"ERROR: SIESTA hash {actual_hash} differs from expected {expected}")

registry_path = root / "config/backend_compatibility.json"
registry = json.loads(registry_path.read_text(encoding="utf-8"))["records"]
matches = [
    row
    for row in registry
    if row["backend"]["backend_id"] == "siesta"
    and row["backend"]["version"] == "5.4.2"
    and row["backend"]["executable_sha256"] == actual_hash
    and row["state"] == "compatible"
]
if len(matches) != 1:
    sys.exit("ERROR: no unique compatible SIESTA registry entry")

(root / "config/siesta-executable.path").write_text(str(executable_path) + "\n")
identity = {
    "schema": "cu3n_ts_yoltla.backend_identity.v1",
    "siesta_executable": str(executable_path),
    "siesta_sha256": actual_hash,
    "registry_sha256": hashlib.sha256(registry_path.read_bytes()).hexdigest(),
    "registry_reason": matches[0]["reason"],
}
results = root / "results"
results.mkdir(exist_ok=True)
(results / "backend_identity.json").write_text(
    json.dumps(identity, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
print("BACKEND_IDENTITY_PASS", actual_hash)
