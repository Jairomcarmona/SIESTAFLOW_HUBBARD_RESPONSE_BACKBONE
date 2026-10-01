"""Rebuild MnO/CoO certificates from existing evidence, writing only here."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from siestaflow_hubbard.execution.u_certification_node import (
    canonical_hash,
    certify_campaign,
    verify_certificate_source_chain,
)


ROOTS = {
    "MnO": Path("/home/jmc/.local/state/siestaflow/campaigns/lr-u-mno-afmii-stage-u-a-20260930"),
    "CoO": Path("/home/jmc/.local/state/siestaflow/campaigns/lr-u-coo-ideal-afmii-stage-u-a-20260930"),
}
OUTPUT = Path(
    "/mnt/c/Users/Jairo/Downloads/"
    "SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0/"
    "benchmarks/lr_u/forensic_audit"
)
CODE = Path(
    "/mnt/c/Users/Jairo/Downloads/"
    "SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0/"
    "src/siestaflow_hubbard/execution/u_certification_node.py"
)
code_sha = hashlib.sha256(CODE.read_bytes()).hexdigest()
revision = subprocess.check_output(
    ["git", "-C", str(CODE.parents[3]), "rev-parse", "HEAD"], text=True
).strip()

for material, root in ROOTS.items():
    old = json.loads((root / "u_certificate.v1.json").read_text(encoding="utf-8"))
    analysis_payload = json.loads(
        (root / old["analysis_artifact_path"]).read_text(encoding="utf-8")
    )
    manifest = json.loads(
        (root / old["source_evidence_manifest_path"]).read_text(encoding="utf-8")
    )
    primary = analysis_payload["primary"]
    labels = analysis_payload["site_labels"]
    normalized_analysis = {
        "state": "VALIDATED",
        "campaign_uuid": old["campaign_uuid"],
        "chi0_nominal": primary["matrix_used_chi0"],
        "chi_nominal": primary["matrix_used_chi"],
        "nominal_u_by_site_eV": [primary["U_by_site_eV"][str(label)] for label in labels],
    }
    nodes = [
        {
            "path": row["receipt_path"],
            "sha256": row["receipt_sha256"],
            "state": "VALIDATED",
            "evidence_digest": row["node_evidence_sha256"],
            "parent_dm_loaded": True,
        }
        for row in manifest["observations"]
    ]
    certificate, digest = certify_campaign(
        root,
        analysis=normalized_analysis,
        response_dataset_path=old["response_tokens_path"],
        response_dataset_sha256=old["response_tokens_file_sha256"],
        analysis_path=old["analysis_artifact_path"],
        analysis_sha256=old["analysis_artifact_sha256"],
        node_evidence=nodes,
        analysis_policy=analysis_payload["estimator_policy"],
        source_manifest_path=old["source_evidence_manifest_path"],
        source_manifest_sha256=old["source_evidence_manifest_canonical_sha256"],
        source_manifest_file_sha256=old["source_evidence_manifest_sha256"],
        source_manifest_identity_sha256=old["source_manifest_identity_sha256"],
        response_tokens_scientific_sha256=old["response_tokens_scientific_sha256"],
        matrix_analysis_receipt_sha256=old["matrix_analysis_receipt_sha256"],
        matrix_analysis_commitment_path=old["matrix_analysis_commitment_path"],
        matrix_analysis_commitment_file_sha256=old["matrix_analysis_commitment_file_sha256"],
    )
    scientific_digest = certificate["certificate_scientific_sha256"]
    assert scientific_digest == canonical_hash(
        {key: value for key, value in certificate.items() if key != "certificate_scientific_sha256"}
    )
    assert certificate["certificate_status"] == "CERTIFIED"
    verify_certificate_source_chain(certificate, root)
    artifact = {
        "artifact_type": "superseding_u_certificate",
        "supersedes": old["certificate_scientific_sha256"],
        "reason": (
            "Reconstructed certified boxes from the six MATRIX_ANALYSIS active-grid alphas; "
            "the prior implementation incorrectly fitted every alpha in the full token dataset."
        ),
        "old_scientific_digest": old["certificate_scientific_sha256"],
        "new_scientific_digest": scientific_digest,
        "code_identity": {
            "git_head": revision,
            "working_tree_file": "src/siestaflow_hubbard/execution/u_certification_node.py",
            "working_tree_file_sha256": code_sha,
        },
        "certificate": certificate,
    }
    target = OUTPUT / f"{material}_u_certificate.superseding.v2.json"
    target.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        material,
        certificate["certificate_status"],
        "old=" + old["certificate_scientific_sha256"],
        "new=" + scientific_digest,
        "U=" + json.dumps(certificate["nominal_u_by_site_eV"]),
        "intervals=" + json.dumps(certificate["u_interval_by_site"], sort_keys=True),
        "path=" + str(target),
    )
