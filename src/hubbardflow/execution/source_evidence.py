"""Content addressed primary evidence for certified LR response tokens.

Small artifacts are read from one byte snapshot and parsed from those bytes.
OUT files are opened once and read through the same file descriptor that is
hashed, so a concurrent path replacement cannot make parsed bytes differ from
the bytes whose digest was checked. Resolved paths must stay below campaign root.
"""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Any, Mapping

from .u_release_gate import canonical_hash


class SourceEvidenceError(ValueError):
    pass


def _safe_relative_file(root: Path, value: str) -> tuple[Path, bytes]:
    """Read one campaign-relative file snapshot under the resolved root.

    A locator may be a symlink when its resolved target stays inside the
    campaign root. Symlinks that resolve outside are rejected. The opened
    target is read once, and inode/size/mtime checks detect replacement or
    mutation during that read; callers still compare the returned bytes with
    the previously committed content digest on every validation pass.
    """
    rel = Path(value)
    if rel.is_absolute() or ".." in rel.parts:
        raise SourceEvidenceError("INVALID_SOURCE_EVIDENCE: path must be campaign-relative")
    target = (root / rel).resolve(strict=True)
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise SourceEvidenceError("INVALID_SOURCE_EVIDENCE: evidence path escapes campaign root") from exc
    if not target.is_file():
        raise SourceEvidenceError("INVALID_SOURCE_EVIDENCE: evidence is not a regular file")
    with target.open("rb") as stream:
        before = os.fstat(stream.fileno())
        raw = stream.read()
        after = os.fstat(stream.fileno())
        try:
            current_path = target.resolve(strict=True)
            current_lstat = target.lstat()
        except OSError as exc:
            raise SourceEvidenceError("INVALID_SOURCE_EVIDENCE: evidence path changed while being read") from exc
    try:
        current_path.relative_to(root)
    except ValueError as exc:
        raise SourceEvidenceError("INVALID_SOURCE_EVIDENCE: evidence path escaped campaign root while being read") from exc
    if (current_lstat.st_ino != after.st_ino or current_lstat.st_dev != after.st_dev
            or (before.st_ino, before.st_dev, before.st_size, before.st_mtime_ns)
            != (after.st_ino, after.st_dev, after.st_size, after.st_mtime_ns)):
        raise SourceEvidenceError("INVALID_SOURCE_EVIDENCE: evidence changed while being read")
    return target, raw


def scientific_tokens_payload(dataset: Mapping[str, Any]) -> dict[str, Any]:
    """Return the deterministic scientific subset, independent of JSON formatting."""
    rows = []
    for row in dataset.get("observations", []):
        rows.append({
            "mode": str(row["mode"]),
            "perturbed_site_index": int(row["perturbed_site_index"]),
            "perturbed_site_id": str(row.get("perturbed_site_id", row["perturbed_site_index"])),
            "alpha_token": str(row["alpha_token"]),
            "occupation_tokens": [[str(token) for token in vector] for vector in row["occupation_tokens"]],
            "occupation_half_width_tokens": [
                [str(token) for token in vector]
                for vector in row.get("occupation_half_width_tokens", [])
            ],
            "occupation_source": str(dataset.get("occupation_source", "siesta_occupations_total")),
        })
    rows.sort(key=lambda row: (row["mode"], row["perturbed_site_index"], row["alpha_token"]))
    return {
        "schema_version": "response_tokens.scientific.v1",
        "campaign_uuid": str(dataset["campaign_uuid"]),
        "matrix_dimension": int(dataset["matrix_dimension"]),
        "polynomial_degree": int(dataset["polynomial_degree"]),
        "occupation_source": str(dataset.get("occupation_source", "siesta_occupations_total")),
        "observations": rows,
    }


def scientific_tokens_sha256(dataset: Mapping[str, Any]) -> str:
    return canonical_hash(scientific_tokens_payload(dataset))


def source_manifest_identity_payload(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Path-independent identity: semantic roles plus committed content hashes."""
    reference = manifest["reference_calculation"]
    observations = [{
        "node_id": row["node_id"], "node_evidence_sha256": row.get("node_evidence_sha256"),
        "mode": row["mode"], "perturbed_site_index": int(row["perturbed_site_index"]),
        "perturbed_site_id": row["perturbed_site_id"], "alpha_token": str(row["alpha_token"]),
        "out_sha256": row.get("out_sha256"), "parent_dm_sha256": row.get("parent_dm_sha256"),
        "receipt_sha256": row.get("receipt_sha256"), "backend_identity": row["backend_identity"],
        "scientific_profile_id": row["scientific_profile_id"], "parser_id": row["parser_id"],
        "atom_indices": [int(value) for value in row["atom_indices"]],
    } for row in manifest["observations"]]
    observations.sort(key=lambda row: (row["mode"], row["perturbed_site_index"], row["alpha_token"], row["node_id"]))
    return {
        "schema_version": "source_evidence_identity.v1",
        "campaign_uuid": str(manifest["campaign_uuid"]),
        "generation_version": str(manifest["generation_version"]),
        "matrix_dimension": int(manifest["matrix_dimension"]),
        "polynomial_degree": int(manifest["polynomial_degree"]),
        "analysis_policy_sha256": str(manifest.get("analysis_policy_sha256")),
        "reference_calculation": {
            "campaign_uuid": str(reference["campaign_uuid"]),
            "node_id": str(reference["node_id"]),
            "node_evidence_sha256": str(reference.get("node_evidence_sha256")),
            "reference_dm_sha256": str(reference.get("reference_dm_sha256")),
            "receipt_sha256": str(reference.get("receipt_sha256")),
        },
        "observations": observations,
    }


def source_manifest_identity_sha256(manifest: Mapping[str, Any]) -> str:
    return canonical_hash(source_manifest_identity_payload(manifest))


def validate_source_manifest(manifest: Mapping[str, Any]) -> None:
    # Keep the boundary error stable and actionable before JSON Schema rejects
    # the same locator through its relativePath definition.
    for item in (manifest.get("observations", []) if isinstance(manifest, Mapping) else []):
        if not isinstance(item, Mapping):
            continue
        for key in ("out_path", "receipt_path", "parent_dm_path"):
            value = item.get(key)
            if isinstance(value, str):
                normalized = value.replace("\\", "/")
                path = Path(value)
                if (path.is_absolute() or normalized.startswith("/")
                        or (len(normalized) >= 2 and normalized[1] == ":")
                        or ".." in normalized.split("/")):
                    raise SourceEvidenceError("INVALID_SOURCE_EVIDENCE: path must be campaign-relative")
    try:
        json.dumps(manifest, allow_nan=False)
        import jsonschema
        schema_path = Path(__file__).resolve().parents[3] / "schemas" / "source_evidence_manifest.v1.schema.json"
        schema = json.loads(schema_path.read_bytes())
        jsonschema.validate(instance=dict(manifest), schema=schema)
    except ImportError as exc:
        raise SourceEvidenceError("JSON_SCHEMA_VALIDATOR_UNAVAILABLE: install the declared jsonschema dependency") from exc
    except Exception as exc:
        raise SourceEvidenceError(f"INVALID_SOURCE_EVIDENCE: manifest JSON Schema validation failed: {exc}") from exc
    # The identity digest is traceability only; semantic structure and parsed
    # physical evidence remain independently validated below.
    if manifest.get("schema_version") != "source_evidence_manifest.v1":
        raise SourceEvidenceError("INVALID_SOURCE_EVIDENCE: unknown source manifest schema")
    observations = manifest.get("observations")
    if not isinstance(observations, list) or not observations:
        raise SourceEvidenceError("INVALID_SOURCE_EVIDENCE: source manifest has no observations")
    seen: set[tuple[str, int, str]] = set()
    seen_nodes: set[str] = set()
    try:
        dimension = int(manifest["matrix_dimension"])
        if dimension < 1:
            raise ValueError
        reference = manifest["reference_calculation"]
        if reference.get("campaign_uuid") != manifest.get("campaign_uuid"):
            raise SourceEvidenceError("INVALID_SOURCE_EVIDENCE: inconsistent reference campaign UUID")
    except (KeyError, TypeError, ValueError) as exc:
        raise SourceEvidenceError("INVALID_SOURCE_EVIDENCE: malformed source manifest identity") from exc
    for row in observations:
        if not isinstance(row, Mapping) or row.get("mode") not in {"BARE", "SCREENED"}:
            raise SourceEvidenceError("INVALID_SOURCE_EVIDENCE: unknown source role")
        for key in ("out_path", "receipt_path", "parent_dm_path", "node_id", "parser_id", "scientific_profile_id", "backend_identity", "perturbed_site_id"):
            if not isinstance(row.get(key), str) or not row[key]:
                raise SourceEvidenceError(f"INVALID_SOURCE_EVIDENCE: missing {key}")
        identity = (row["mode"], int(row["perturbed_site_index"]), str(row["alpha_token"]))
        if row.get("node_state") != "VALIDATED":
            raise SourceEvidenceError("INVALID_SOURCE_EVIDENCE: node state is not VALIDATED")
        if row["parser_id"] == "siesta-5.4.2-bare-first-iteration-v1" and row["mode"] != "BARE":
            raise SourceEvidenceError("INVALID_SOURCE_EVIDENCE: parser and mode disagree")
        if row["parser_id"] == "siesta-5.4.2-screened-dmout-v1" and row["mode"] != "SCREENED":
            raise SourceEvidenceError("INVALID_SOURCE_EVIDENCE: parser and mode disagree")
        if identity in seen:
            raise SourceEvidenceError("INVALID_SOURCE_EVIDENCE: duplicate observation node")
        if row["node_id"] in seen_nodes:
            raise SourceEvidenceError("INVALID_SOURCE_EVIDENCE: duplicate node id")
        if not 0 <= int(row["perturbed_site_index"]) < dimension or len(row.get("atom_indices", [])) != dimension:
            raise SourceEvidenceError("INVALID_SOURCE_EVIDENCE: inconsistent response dimensions")
        seen.add(identity)
        seen_nodes.add(row["node_id"])


def extract_verified_response_tokens(
    source_manifest: Mapping[str, Any], campaign_root: str | Path,
) -> dict[str, Any]:
    """Rebuild tokens from parsed primary OUT files, retaining hash warnings."""
    validate_source_manifest(source_manifest)
    root = Path(campaign_root).resolve(strict=True)
    campaign_uuid = str(source_manifest.get("campaign_uuid", ""))
    dimension = int(source_manifest["matrix_dimension"])
    degree = int(source_manifest["polynomial_degree"])
    reference = source_manifest.get("reference_calculation", {})
    if reference.get("campaign_uuid") != campaign_uuid or not reference.get("node_id"):
        raise SourceEvidenceError("INVALID_SOURCE_EVIDENCE: reference calculation identity is missing")
    traceability_warnings: list[dict[str, str]] = []
    from hubbardflow.domain.hash_traceability import compare_traceable_mappings
    for warning in compare_traceable_mappings(source_manifest, source_manifest).warnings:
        traceability_warnings.append({"reason_code": warning.reason.value, "detail": warning.field})
    if source_manifest.get("source_manifest_identity_sha256") != source_manifest_identity_sha256(source_manifest):
        traceability_warnings.append({"reason_code": "SOURCE_MANIFEST_DIGEST_MISMATCH", "detail": "manifest identity digest differs"})
    reference_path, reference_bytes = _safe_relative_file(root, str(reference.get("reference_dm_path", "")))
    if sha256(reference_bytes).hexdigest() != reference.get("reference_dm_sha256"):
        traceability_warnings.append({"reason_code": "REFERENCE_DM_DIGEST_MISMATCH", "detail": str(reference_path)})
    reference_receipt_path, reference_receipt_bytes = _safe_relative_file(root, str(reference.get("receipt_path", "")))
    if sha256(reference_receipt_bytes).hexdigest() != reference.get("receipt_sha256"):
        traceability_warnings.append({"reason_code": "REFERENCE_RECEIPT_DIGEST_MISMATCH", "detail": str(reference_receipt_path)})
    try:
        reference_receipt = json.loads(reference_receipt_bytes)
    except json.JSONDecodeError as exc:
        raise SourceEvidenceError("INVALID_SOURCE_EVIDENCE: reference receipt is unreadable") from exc
    if (reference_receipt.get("state") != "VALIDATED"
            or reference_receipt.get("campaign_uuid") != campaign_uuid
            or reference_receipt.get("node_id") != reference.get("node_id")):
        raise SourceEvidenceError("INVALID_SOURCE_EVIDENCE: reference receipt does not bind the declared reference DM")
    for key in ("node_evidence_sha256", "reference_dm_sha256"):
        if reference_receipt.get(key) != reference.get(key):
            traceability_warnings.append({"reason_code": "REFERENCE_RECEIPT_IDENTITY_MISMATCH", "detail": key})
    output_rows: list[dict[str, Any]] = []
    for row in source_manifest["observations"]:
        out_path, out_bytes = _safe_relative_file(root, str(row["out_path"]))
        if sha256(out_bytes).hexdigest() != row.get("out_sha256"):
            traceability_warnings.append({"reason_code": "OUT_DIGEST_MISMATCH", "detail": str(out_path)})
        receipt_path, receipt_bytes = _safe_relative_file(root, str(row["receipt_path"]))
        if sha256(receipt_bytes).hexdigest() != row.get("receipt_sha256"):
            traceability_warnings.append({"reason_code": "NODE_RECEIPT_DIGEST_MISMATCH", "detail": str(receipt_path)})
        try:
            receipt = json.loads(receipt_bytes)
            out_text = out_bytes.decode("utf-8", errors="replace")
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise SourceEvidenceError("INVALID_SOURCE_EVIDENCE: source artifact is unreadable") from exc
        if (receipt.get("node_id") != row["node_id"] or receipt.get("state") != "VALIDATED"
                or receipt.get("campaign_uuid") != campaign_uuid
                or receipt.get("parent_dm_loaded") is not True
                or receipt.get("mode") != row["mode"]
                or receipt.get("perturbed_site_index") != row["perturbed_site_index"]
                or receipt.get("perturbed_site_id") != row["perturbed_site_id"]
                or receipt.get("alpha_token") != row["alpha_token"]
                or receipt.get("parser_id") != row["parser_id"]
                or receipt.get("backend_identity") != row["backend_identity"]
                or receipt.get("scientific_profile_id") != row["scientific_profile_id"]
                or receipt.get("atom_indices") != row["atom_indices"]):
            raise SourceEvidenceError("INVALID_SOURCE_EVIDENCE: receipt does not bind the declared OUT")
        for key in ("node_evidence_sha256", "out_sha256", "parent_dm_sha256"):
            if receipt.get(key) != row.get(key):
                traceability_warnings.append({"reason_code": "NODE_RECEIPT_IDENTITY_MISMATCH", "detail": f"{row['node_id']}:{key}"})
        parent_path, parent_bytes = _safe_relative_file(root, str(row["parent_dm_path"]))
        if sha256(parent_bytes).hexdigest() != row.get("parent_dm_sha256"):
            traceability_warnings.append({"reason_code": "PARENT_DM_DIGEST_MISMATCH", "detail": str(parent_path)})
        parser_id = row["parser_id"]
        try:
            if parser_id == "siesta-5.4.2-bare-first-iteration-v1":
                from hubbardflow.siesta_backend.siesta542_bare_profile import Siesta542PotentialShiftHamiltonianProfile
                event = Siesta542PotentialShiftHamiltonianProfile().select_response(out_text).response_event
            elif parser_id == "siesta-5.4.2-screened-dmout-v1":
                from hubbardflow.siesta_backend.siesta542_screened_selection import select_converged_screened_event
                event = select_converged_screened_event(out_text)
            else:
                raise SourceEvidenceError("INVALID_SOURCE_EVIDENCE: undeclared response parser")
            from hubbardflow.siesta_backend.occupation_precision import read_printed_occupation_precision
            parsed = read_printed_occupation_precision(out_text, event)
            sites = [int(value) for value in row["atom_indices"]]
            tokens = [[parsed[index].certification_tokens[k] for k in range(len(parsed[index].certification_tokens))]
                      for index in sites]
            half_widths = [[parsed[index].half_width_exact] for index in sites]
        except SourceEvidenceError:
            raise
        except Exception as exc:
            raise SourceEvidenceError("INVALID_SOURCE_EVIDENCE: OUT response could not be re-extracted") from exc
        output_rows.append({
            "mode": row["mode"], "perturbed_site_index": int(row["perturbed_site_index"]),
            "perturbed_site_id": str(row["perturbed_site_id"]), "alpha_token": str(row["alpha_token"]),
            "occupation_tokens": tokens, "occupation_half_width_tokens": half_widths,
            "source_out_path": out_path.relative_to(root).as_posix(),
            "source_out_sha256": row.get("out_sha256"), "node_id": row["node_id"],
            "node_evidence_sha256": row.get("node_evidence_sha256"),
        })
    output_rows.sort(key=lambda row: (row["mode"], row["perturbed_site_index"], row["alpha_token"]))
    return {
        "schema_version": "response_tokens.v1", "campaign_uuid": campaign_uuid,
        "matrix_dimension": dimension, "polynomial_degree": degree, "status": "AVAILABLE",
        "occupation_source": "siesta_occupations_total", "observations": output_rows,
        "traceability_warnings": traceability_warnings,
    }
