"""Read-only recheck of frozen Stage U-A campaign artifacts in WSL."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


EVIDENCE = Path(
    "/mnt/c/Users/Jairo/Downloads/"
    "SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0/"
    "benchmarks/lr_u/forensic_audit/frozen_evidence.json"
)

payload = json.loads(EVIDENCE.read_text(encoding="utf-8"))
for material in payload["materials"]:
    root = Path(material["campaign_root"])
    results = []
    for key in (
        "source_evidence_manifest",
        "response_tokens",
        "matrix_analysis",
        "certificate",
        "adaptive_state",
    ):
        item = material[key]
        expected = item.get("file_sha256")
        if not expected:
            continue
        actual = hashlib.sha256((root / item["path"]).read_bytes()).hexdigest()
        results.append(f"{key}={'OK' if actual == expected else 'MISMATCH'}")
    analysis = material["matrix_analysis"]
    commitment_path = analysis.get("commitment_path")
    commitment_hash = analysis.get("commitment_file_sha256")
    if commitment_path and commitment_hash:
        actual = hashlib.sha256((root / commitment_path).read_bytes()).hexdigest()
        results.append(
            f"matrix_analysis_commitment={'OK' if actual == commitment_hash else 'MISMATCH'}"
        )
    print(f"{material['material']}: " + ", ".join(results))
