import json
from hashlib import sha256
import os
from pathlib import Path
import re

import pytest

from hubbardflow.execution.source_evidence import (
    SourceEvidenceError, extract_verified_response_tokens, scientific_tokens_sha256,
    source_manifest_identity_sha256, validate_source_manifest,
)
from hubbardflow.siesta_backend.siesta542_bare_profile import Siesta542PotentialShiftHamiltonianProfile


def _manifest(root: Path) -> dict:
    out = Path(__file__).resolve().parents[2] / "examples" / "MnO_BARE_+0.05.out"
    target = root / "response.out"
    target.write_bytes(out.read_bytes())
    parent = root / "reference.DM"
    parent.write_bytes(b"reference dm fixture\n")
    text = target.read_text(encoding="utf-8", errors="replace")
    event = Siesta542PotentialShiftHamiltonianProfile().select_response(text).response_event
    from hubbardflow.siesta_backend.occupation_precision import read_printed_occupation_precision
    atom_indices = sorted(read_printed_occupation_precision(text, event))
    out_hash = sha256(target.read_bytes()).hexdigest()
    parent_hash = sha256(parent.read_bytes()).hexdigest()
    node_hash = "a" * 64
    backend = "b" * 64
    parser = "siesta-5.4.2-bare-first-iteration-v1"
    profile = "siesta-5.4.2-potential-shift-hamiltonian-v1"
    receipt = {
        "campaign_uuid": "fixture", "node_id": "response:fixture", "state": "VALIDATED",
        "node_evidence_sha256": node_hash, "out_sha256": out_hash,
        "parent_dm_sha256": parent_hash, "parent_dm_loaded": True,
        "mode": "BARE", "perturbed_site_index": 0, "perturbed_site_id": "site0", "alpha_token": "0.05",
        "parser_id": parser, "scientific_profile_id": profile, "backend_identity": backend,
        "atom_indices": atom_indices,
    }
    receipt_path = root / "receipt.json"
    receipt_path.write_text(json.dumps(receipt, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    reference_receipt = {"campaign_uuid": "fixture", "node_id": "reference", "state": "VALIDATED",
                         "node_evidence_sha256": "d" * 64, "reference_dm_path": "reference.DM",
                         "reference_dm_sha256": parent_hash}
    reference_receipt_path = root / "reference-receipt.json"
    reference_receipt_path.write_text(json.dumps(reference_receipt, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    row = {
        "node_id": "response:fixture", "perturbed_site_index": 0, "perturbed_site_id": "site0",
        "alpha_token": "0.05", "mode": "BARE", "out_path": "response.out", "out_sha256": out_hash,
        "receipt_path": "receipt.json", "receipt_sha256": sha256(receipt_path.read_bytes()).hexdigest(),
        "node_evidence_sha256": node_hash, "node_state": "VALIDATED",
        "parent_dm_path": "reference.DM", "parent_dm_sha256": parent_hash,
        "backend_identity": backend, "scientific_profile_id": profile,
        "parser_id": parser, "atom_indices": atom_indices,
    }
    manifest = {
        "schema_version": "source_evidence_manifest.v1", "campaign_uuid": "fixture",
        "generation_version": "test-v1", "matrix_dimension": len(atom_indices), "polynomial_degree": 1,
        "analysis_policy_sha256": "c" * 64,
        "reference_calculation": {"campaign_uuid": "fixture", "node_id": "reference",
                                  "node_evidence_sha256": "d" * 64, "receipt_path": "reference-receipt.json",
                                  "receipt_sha256": sha256(reference_receipt_path.read_bytes()).hexdigest(),
                                  "reference_dm_path": "reference.DM", "reference_dm_sha256": parent_hash},
        "observations": [row],
    }
    manifest["source_manifest_identity_sha256"] = source_manifest_identity_sha256(manifest)
    return manifest


def _symlink_or_skip(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target)
    except (NotImplementedError, OSError) as exc:
        if os.name == "nt":
            pytest.skip(f"Windows symlink creation is unavailable in this environment: {exc}")
        raise


def test_out_reextraction_produces_stable_scientific_tokens(tmp_path):
    manifest = _manifest(tmp_path)
    first = extract_verified_response_tokens(manifest, tmp_path)
    second = extract_verified_response_tokens(manifest, tmp_path)
    assert first["observations"][0]["occupation_tokens"]
    assert scientific_tokens_sha256(first) == scientific_tokens_sha256(second)


def test_manifest_schema_and_semantic_identity_exclude_operational_paths(tmp_path):
    manifest = _manifest(tmp_path)
    validate_source_manifest(manifest)
    moved = json.loads(json.dumps(manifest))
    moved["reference_calculation"]["reference_dm_path"] = "relocated/reference.DM"
    moved["reference_calculation"]["receipt_path"] = "relocated/reference-receipt.json"
    moved["observations"][0]["out_path"] = "relocated/response.out"
    moved["observations"][0]["receipt_path"] = "relocated/receipt.json"
    assert source_manifest_identity_sha256(moved) == manifest["source_manifest_identity_sha256"]


def test_manifest_schema_requires_parent_dm_locator(tmp_path):
    manifest = _manifest(tmp_path)
    del manifest["observations"][0]["parent_dm_path"]
    manifest["source_manifest_identity_sha256"] = source_manifest_identity_sha256(manifest)
    with pytest.raises(SourceEvidenceError, match="JSON Schema validation failed"):
        validate_source_manifest(manifest)


def test_out_mutation_rejects_even_if_derived_dataset_would_be_rehashed(tmp_path):
    manifest = _manifest(tmp_path)
    out = tmp_path / "response.out"
    text = out.read_text(encoding="utf-8", errors="replace")
    changed, count = re.subn(r"(Occupations:[^\r\n]*?)([-+]?\d+\.\d+)", r"\g<1>9.999999", text, count=1)
    assert count == 1
    out.write_text(changed, encoding="utf-8")
    with pytest.raises(SourceEvidenceError, match="PROVENANCE_MISMATCH"):
        extract_verified_response_tokens(manifest, tmp_path)


@pytest.mark.parametrize("path", ["../outside.out", "/outside.out", "C:/outside.out"])
def test_manifest_rejects_paths_outside_campaign_root(tmp_path, path):
    manifest = _manifest(tmp_path)
    manifest["observations"][0]["out_path"] = path
    with pytest.raises(SourceEvidenceError, match="campaign-relative"):
        extract_verified_response_tokens(manifest, tmp_path)


def test_manifest_rejects_duplicate_node_ids(tmp_path):
    manifest = _manifest(tmp_path)
    duplicate = dict(manifest["observations"][0])
    duplicate["mode"] = "SCREENED"
    duplicate["parser_id"] = "siesta-5.4.2-screened-dmout-v1"
    duplicate["scientific_profile_id"] = "siesta-5.4.2-screened-dmout-v1"
    manifest["observations"].append(duplicate)
    manifest["source_manifest_identity_sha256"] = source_manifest_identity_sha256(manifest)
    with pytest.raises(SourceEvidenceError, match="duplicate node id"):
        extract_verified_response_tokens(manifest, tmp_path)


def test_receipt_mutation_rejects(tmp_path):
    manifest = _manifest(tmp_path)
    receipt = tmp_path / manifest["observations"][0]["receipt_path"]
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    payload["state"] = "FAILED_SCIENCE"
    receipt.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(SourceEvidenceError, match="receipt hash"):
        extract_verified_response_tokens(manifest, tmp_path)


def test_parent_dm_mutation_rejects(tmp_path):
    manifest = _manifest(tmp_path)
    parent = tmp_path / "reference.DM"
    parent.write_bytes(parent.read_bytes() + b"changed")
    with pytest.raises(SourceEvidenceError, match="DM hash"):
        extract_verified_response_tokens(manifest, tmp_path)


@pytest.mark.parametrize("role", ["out", "receipt", "parent_dm"])
def test_symlink_to_external_primary_evidence_is_rejected(tmp_path, role):
    manifest = _manifest(tmp_path)
    row = manifest["observations"][0]
    locator_key = {"out": "out_path", "receipt": "receipt_path", "parent_dm": "parent_dm_path"}[role]
    original = tmp_path / row[locator_key]
    outside_dir = tmp_path.parent / f"{tmp_path.name}-outside-{role}"
    outside_dir.mkdir(parents=True, exist_ok=True)
    outside = outside_dir / original.name
    outside.write_bytes(original.read_bytes())
    link = tmp_path / f"external-{role}{original.suffix}"
    _symlink_or_skip(link, outside)
    row[locator_key] = link.name

    with pytest.raises(SourceEvidenceError, match="evidence path escapes campaign root"):
        extract_verified_response_tokens(manifest, tmp_path)


def test_internal_symlink_is_accepted_and_revalidation_detects_target_replacement(tmp_path):
    manifest = _manifest(tmp_path)
    row = manifest["observations"][0]
    target = tmp_path / row["out_path"]
    link = tmp_path / "response-internal-link.out"
    _symlink_or_skip(link, target)
    row["out_path"] = link.name

    first = extract_verified_response_tokens(manifest, tmp_path)
    assert first["observations"][0]["occupation_tokens"]

    replacement = tmp_path / "replacement.out"
    replacement.write_bytes(target.read_bytes() + b"\nreplacement target\n")
    os.replace(replacement, target)
    with pytest.raises(SourceEvidenceError, match="OUT hash differs from source manifest"):
        extract_verified_response_tokens(manifest, tmp_path)
