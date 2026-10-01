"""Inspect read-only certificate reconstruction inputs in the frozen campaigns."""
from __future__ import annotations

import json
from pathlib import Path

ROOTS = {
    "MnO": "/home/jmc/.local/state/siestaflow/campaigns/lr-u-mno-afmii-stage-u-a-20260930",
    "CoO": "/home/jmc/.local/state/siestaflow/campaigns/lr-u-coo-ideal-afmii-stage-u-a-20260930",
}
for material, raw_root in ROOTS.items():
    root = Path(raw_root)
    cert = json.loads((root / "u_certificate.v1.json").read_text())
    checkpoint = json.loads((root / ".siestaflow/dag-checkpoint.json").read_text())
    print(material, "cert keys", sorted(cert))
    print(material, "checkpoint type", type(checkpoint).__name__)
    print(material, "checkpoint keys", sorted(checkpoint) if isinstance(checkpoint, dict) else len(checkpoint))
    print(material, "cert state", cert.get("certificate_status"), cert.get("implementation_version"))
    print(material, "cert analysis", cert.get("analysis_artifact_path"))
    print(material, "checkpoint snippet", json.dumps(checkpoint, sort_keys=True)[:1600])
