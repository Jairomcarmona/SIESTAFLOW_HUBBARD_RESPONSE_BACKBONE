#!/usr/bin/env python3
"""Package one completed fixed-grid campaign as immutable replica evidence.

The tool is read-only with respect to the source campaign.  It writes a new
sidecar directory containing a dataset and a receipt fragment for a future
three-or-more-replica calibration result.
"""
from __future__ import annotations

import argparse
import json
from hashlib import sha256
from math import isclose, isfinite
from pathlib import Path
import re
import sys
from typing import Any, Mapping

from hubbardflow.domain.response_grid_reproducibility import (
    ResponseGridCalibrationError,
    _node_artifact_path,
    _execution_attempt,
    _validate_reference_execution,
    _verify_projector_shift,
    validate_response_grid_calibration,
    response_grid_source_campaign_context,
)
from hubbardflow.execution.campaign_v2 import (
    CampaignV2Error,
    load_campaign_v2,
)
from hubbardflow.domain.lr_analysis_v2 import (
    LRAnalysisPolicy,
    analyze_verified_lr,
    write_lr_analysis_v2,
)
from hubbardflow.domain.matrix_lr import ResponseObservation
from hubbardflow.siesta_backend.occupation_precision import read_printed_occupation_precision
from hubbardflow.siesta_backend.siesta542_bare_profile import Siesta542PotentialShiftHamiltonianProfile
from hubbardflow.siesta_backend.siesta542_screened_selection import select_converged_screened_event
from hubbardflow.reporting.lr_u_report import write_lr_u_report


class PackagingError(ValueError):
    """The source campaign cannot be packaged as verified replica evidence."""


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PackagingError(f"cannot read {label}: {path}") from exc
    if not isinstance(value, dict):
        raise PackagingError(f"{label} must contain a JSON object")
    return value


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _relative_path(root: Path, raw: Any, label: str) -> tuple[Path, str]:
    if not isinstance(raw, str) or not raw.strip():
        raise PackagingError(f"{label} path is missing")
    rel = Path(raw)
    if rel.is_absolute() or ".." in rel.parts:
        raise PackagingError(f"{label} path must be relative to source root and contain no '..'")
    try:
        path = (root / rel).resolve(strict=True)
        path.relative_to(root.resolve(strict=True))
    except (OSError, ValueError) as exc:
        raise PackagingError(f"{label} is missing or escapes the source campaign") from exc
    if not path.is_file():
        raise PackagingError(f"{label} is not a regular file")
    return path, rel.as_posix()


def _must_hash(path: Path, expected: Any, label: str) -> str:
    if not isinstance(expected, str) or re.fullmatch(r"[0-9a-f]{64}", expected) is None:
        raise PackagingError(f"{label} must declare a lowercase SHA-256")
    actual = _sha(path)
    if actual != expected:
        raise PackagingError(f"{label} hash differs from campaign analysis")
    return actual


def package_replica(
    *, source_root: Path, manifest_rel: str, analysis_rel: str,
    node_evidence_rel: str, output_dir: Path, replica_id: str | None,
) -> dict[str, Any]:
    root = source_root.resolve(strict=True)
    if not root.is_dir():
        raise PackagingError("source_root must be a campaign directory")
    output = output_dir.resolve(strict=False)
    if output.exists():
        raise PackagingError(f"sidecar output already exists: {output}")
    try:
        output.relative_to(root)
    except ValueError:
        pass
    else:
        raise PackagingError("sidecar output must be outside the source campaign")
    if not output.parent.is_dir():
        raise PackagingError("sidecar parent directory must already exist")

    manifest_path, manifest_relative = _relative_path(root, manifest_rel, "campaign manifest")
    manifest_hash = _sha(manifest_path)
    campaign, context_hash = response_grid_source_campaign_context(manifest_path)
    root = Path(str(campaign["_campaign_root"])).resolve(strict=True)
    analysis_path, analysis_relative = _relative_path(root, analysis_rel, "analysis JSON")
    evidence_path, evidence_relative = _relative_path(root, node_evidence_rel, "node-evidence JSON")
    analysis_hash, evidence_hash = _sha(analysis_path), _sha(evidence_path)
    analysis = _read_json(analysis_path, "analysis JSON")
    node_evidence = _read_json(evidence_path, "node-evidence JSON")
    if analysis.get("schema_version") != "siestaflow.lr_u_analysis.v3":
        raise PackagingError("only a v3 LR-U analysis can be packaged")
    analysis_campaign = analysis.get("campaign")
    if (not isinstance(analysis_campaign, Mapping)
            or analysis_campaign.get("campaign_id") != campaign.get("campaign_id")
            or analysis_campaign.get("fixed_grid") is not True
            or analysis_campaign.get("automatic_alpha_refinement") is not False):
        raise PackagingError("source analysis must belong to this campaign and declare a completed fixed grid")
    provenance = analysis.get("provenance")
    if not isinstance(provenance, Mapping) or provenance.get("input_identity") != campaign.get("input_identity"):
        raise PackagingError("analysis input identity differs from the immutable campaign manifest")
    identity = node_evidence.get("identity")
    nodes = node_evidence.get("nodes")
    if (not isinstance(identity, Mapping) or not isinstance(nodes, Mapping)
            or identity.get("campaign_id") != campaign.get("campaign_id")
            or identity.get("input_identity") != campaign.get("input_identity")):
        raise PackagingError("node-evidence receipt does not identify this completed campaign input")
    campaign_id = str(campaign["campaign_id"])
    chosen_replica_id = replica_id or campaign_id
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", chosen_replica_id) is None:
        raise PackagingError("replica_id must use 1-64 safe ASCII letters, digits, dots, '_' or '-'")

    # Adaptive runs may have refined their response mesh; this package contract
    # admits a complete fixed grid only, so an adaptive run fails closed.
    if campaign.get("automatic_alpha_refinement") is True or campaign.get("adaptive_alpha_policy") is not None:
        raise PackagingError("adaptive campaigns are not admitted by the fixed-grid replica packager")
    if analysis.get("alpha_grid_eV") != [float(value) for value in campaign["alpha_grid_ev"]]:
        raise PackagingError("analysis alpha grid differs from the campaign's fixed grid")

    response_dataset = analysis.get("response_observation_dataset")
    if not isinstance(response_dataset, Mapping) or response_dataset.get("occupation_source") != "siesta_occupations_total":
        raise PackagingError("analysis lacks the verified total-occupation response dataset")
    reference = response_dataset.get("reference_source")
    if not isinstance(reference, Mapping):
        raise PackagingError("campaign reference node is not validated")
    reference_dm, reference_dm_rel = _relative_path(root, reference.get("dm_path"), "reference DM")
    reference_dm_hash = _must_hash(reference_dm, reference.get("dm_sha256"), "reference DM")
    validated_reference_hash, reference_attempt_id = _validate_reference_execution(root, reference, nodes)
    if validated_reference_hash != reference_dm_hash:
        raise PackagingError("reference source DM differs from the validated reference-node receipt")
    reference_out, _ = _relative_path(root, reference.get("out_path"), "reference OUT")
    _must_hash(reference_out, reference.get("out_sha256"), "reference OUT")
    reference_output_text = reference_out.read_text(encoding="utf-8", errors="replace")
    reference_event = select_converged_screened_event(reference_output_text)
    reference_occupations = read_printed_occupation_precision(reference_output_text, reference_event)
    expected_reference_dm = reference_dm_hash

    expected_sites = [int(site["index"]) for site in campaign["sites"]]
    site_by_index = {int(site["index"]): site for site in campaign["sites"]}
    expected_alphas = [float(value) for value in campaign["alpha_grid_ev"]]
    expected_cells = {
        (perturbed, alpha, mode, observed)
        for perturbed in expected_sites for alpha in expected_alphas
        for mode in ("BARE", "SCREENED") for observed in expected_sites
    }
    measurements: list[dict[str, Any]] = []
    seen_cells: set[tuple[int, float, str, int]] = set()
    rows = response_dataset.get("rows")
    if not isinstance(rows, list):
        raise PackagingError("verified response dataset rows are missing")
    for row in rows:
        if not isinstance(row, Mapping):
            raise PackagingError("response dataset row is malformed")
        alpha = float(row.get("alpha_eV"))
        perturbed = int(row.get("perturbed_site_index"))
        site_id = str(row.get("perturbed_site_id"))
        if perturbed not in site_by_index or site_id != str(site_by_index[perturbed]["site_id"]):
            raise PackagingError("response row site identity differs from the campaign")
        observed_rows = row.get("observed_sites")
        if not isinstance(observed_rows, list):
            raise PackagingError("response row observed_sites are missing")
        for observed_row in observed_rows:
            if not isinstance(observed_row, Mapping):
                raise PackagingError("observed-site record is malformed")
            observed = int(observed_row.get("observed_site_index"))
            if observed not in site_by_index or observed_row.get("observed_site_id") != site_by_index[observed]["site_id"]:
                raise PackagingError("observed site identity differs from campaign site map")
            values = observed_row.get("occupations_electron")
            widths = observed_row.get("occupation_half_widths_electron")
            sources = observed_row.get("sources")
            if not all(isinstance(value, Mapping) for value in (values, widths, sources)):
                raise PackagingError("response cell lacks values, quantization, or sources")
            for mode in ("BARE", "SCREENED"):
                key = mode.lower()
                source = sources.get(key)
                coordinate = (perturbed, alpha, mode, observed)
                if coordinate not in expected_cells or coordinate in seen_cells:
                    raise PackagingError("analysis contains duplicate or unexpected response coordinates")
                if not isinstance(source, Mapping) or source.get("state") != "VALIDATED" or source.get("mode") != mode:
                    raise PackagingError(f"source receipt is not validated for {coordinate}")
                fdf_path, fdf_rel = _relative_path(root, source.get("fdf_path"), f"{mode} FDF")
                out_path, out_rel = _relative_path(root, source.get("out_path"), f"{mode} OUT")
                dm_path, dm_rel = _relative_path(root, source.get("dm_path"), f"{mode} DM")
                fdf_hash = _must_hash(fdf_path, source.get("fdf_sha256"), f"{mode} FDF")
                out_hash = _must_hash(out_path, source.get("out_sha256"), f"{mode} OUT")
                dm_hash = _must_hash(dm_path, source.get("dm_sha256"), f"{mode} DM")
                node_id = source.get("node_id")
                node_record = nodes.get(node_id) if isinstance(node_id, str) else None
                node_meta = node_record.get("provenance", {}).get("node") if isinstance(node_record, Mapping) else None
                node_hashes = node_record.get("provenance", {}).get("artifacts") if isinstance(node_record, Mapping) else None
                if (not isinstance(node_record, Mapping) or node_record.get("state") != "VALIDATED"
                        or node_record.get("kind") != "siesta"
                        or node_record.get("evidence_digest") != source.get("evidence_digest")
                        or not isinstance(node_meta, Mapping) or node_meta.get("node_id") != node_id
                        or not isinstance(node_hashes, Mapping)
                        or node_hashes.get("fdf") != fdf_hash
                        or node_hashes.get("output") != out_hash
                        or node_hashes.get("dm") != dm_hash):
                    raise PackagingError(f"source node evidence does not bind analysis artifacts for {coordinate}")
                command = node_record.get("command")
                artifact_spec = node_record.get("artifact_spec")
                if not isinstance(command, Mapping) or not isinstance(artifact_spec, Mapping):
                    raise PackagingError(f"source node receipt lacks command/artifact paths for {coordinate}")
                cwd = _node_artifact_path(root, command.get("cwd"), "node command cwd", directory=True)
                attempt_id, attempt_root = _execution_attempt(root, cwd)
                spec_paths: dict[str, Path] = {}
                for name in ("fdf", "output", "dm"):
                    raw_spec_path = artifact_spec.get(name)
                    if not isinstance(raw_spec_path, str):
                        raise PackagingError(f"source node artifact path {name} is missing")
                    spec_rel = Path(raw_spec_path)
                    if spec_rel.is_absolute() or ".." in spec_rel.parts:
                        raise PackagingError(f"source node artifact path {name} is unsafe")
                    spec_paths[name] = _node_artifact_path(root, str(cwd / spec_rel), f"node {name}")
                    try:
                        spec_paths[name].relative_to(attempt_root)
                    except ValueError as exc:
                        raise PackagingError(f"{mode} {name} artifact is outside its execution attempt") from exc
                if (spec_paths["fdf"] != fdf_path or spec_paths["output"] != out_path
                        or spec_paths["dm"] != dm_path
                        or _node_artifact_path(root, command.get("stdin_path"), "node stdin FDF") != fdf_path
                        or _node_artifact_path(root, command.get("stdout_path"), "node stdout OUT") != out_path):
                    raise PackagingError(f"analysis paths differ from node command/artifact receipt for {coordinate}")
                perturbation = node_meta.get("perturbation")
                if (not isinstance(perturbation, Mapping)
                        or perturbation.get("site_index") != perturbed
                        or perturbation.get("site_id") != site_id
                        or perturbation.get("mode") != mode
                        or not isclose(float(perturbation.get("alpha_ev")), alpha, rel_tol=0.0, abs_tol=1e-14)):
                    raise PackagingError(f"node perturbation differs from analysis coordinate {coordinate}")
                site_fdf_text = fdf_path.read_text(encoding="utf-8", errors="replace")
                _verify_projector_shift(site_fdf_text, site_id, alpha)
                output_text = out_path.read_text(encoding="utf-8", errors="replace")
                event = (
                    Siesta542PotentialShiftHamiltonianProfile().select_response(output_text).response_event
                    if mode == "BARE" else select_converged_screened_event(output_text)
                )
                atom_index = int(site_by_index[observed]["atom_index"])
                parsed = read_printed_occupation_precision(output_text, event)[atom_index]
                try:
                    declared_value = float(values[key])
                    declared_width = float(widths[key])
                    declared_reference = float(values["reference"])
                    declared_reference_width = float(widths["reference"])
                except (KeyError, TypeError, ValueError) as exc:
                    raise PackagingError(f"analysis occupation/width is invalid for {coordinate}") from exc
                if (not isclose(parsed.total, declared_value, rel_tol=0.0, abs_tol=1e-12)
                        or not isclose(parsed.half_width, declared_width, rel_tol=0.0, abs_tol=1e-12)):
                    raise PackagingError(f"reparsed output disagrees with analysis occupation for {coordinate}")
                parsed_reference = reference_occupations[atom_index]
                if (not isclose(parsed_reference.total, declared_reference, rel_tol=0.0, abs_tol=1e-12)
                        or not isclose(parsed_reference.half_width, declared_reference_width,
                                       rel_tol=0.0, abs_tol=1e-12)):
                    raise PackagingError(f"reparsed reference output disagrees with analysis for {coordinate}")
                measurements.append({
                    "perturbed_site": perturbed, "alpha_eV": alpha, "mode": mode,
                    "observed_site": observed, "occupation_e": declared_value,
                    "perturbed_site_id": site_id, "observed_atom_index": atom_index,
                    "occupation_half_width_e": declared_width,
                    "node_id": node_id, "evidence_digest": source["evidence_digest"],
                    "attempt_id": attempt_id,
                    "fdf_path": fdf_rel, "fdf_sha256": fdf_hash,
                    "out_path": out_rel, "out_sha256": out_hash,
                    "dm_path": dm_rel, "dm_sha256": dm_hash,
                })
                seen_cells.add(coordinate)
    if seen_cells != expected_cells:
        raise PackagingError("analysis does not cover every fixed-grid site/alpha/mode/observed-site coordinate")

    dataset = {
        "schema": "siestaflow-response-grid-replica-v4",
        "replica_id": chosen_replica_id,
        "campaign_id": campaign_id,
        "reference_dm_sha256": expected_reference_dm,
        "campaign_context_sha256": context_hash,
        "campaign_manifest_path": manifest_relative,
        "campaign_manifest_sha256": manifest_hash,
        "analysis_path": analysis_relative,
        "analysis_sha256": analysis_hash,
        "node_evidence_path": evidence_relative,
        "node_evidence_sha256": evidence_hash,
        "reference_dm_path": reference_dm_rel,
        "reference_node_id": reference["node_id"],
        "reference_evidence_digest": reference["evidence_digest"],
        "reference_attempt_id": reference_attempt_id,
        "measurements": measurements,
    }
    output.mkdir(parents=False, exist_ok=False)
    dataset_path = output / "dataset.json"
    dataset_bytes = (json.dumps(dataset, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")
    dataset_path.write_bytes(dataset_bytes)
    receipt = {
        "replica_id": chosen_replica_id,
        "campaign_id": campaign_id,
        "reference_dm_sha256": expected_reference_dm,
        "source_root": str(root),
        "campaign_manifest_path": manifest_relative,
        "campaign_manifest_sha256": manifest_hash,
        "analysis_path": analysis_relative,
        "analysis_sha256": analysis_hash,
        "dataset_path": (Path(output.name) / "dataset.json").as_posix(),
        "dataset_sha256": sha256(dataset_bytes).hexdigest(),
        "node_evidence_path": evidence_relative,
        "node_evidence_sha256": evidence_hash,
    }
    receipt_path = output / "replica-receipt.json"
    receipt_path.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return {"dataset": str(dataset_path), "receipt": str(receipt_path), "receipt_fields": receipt}


def reanalyze_primary_offline(
    *, source_root: Path, manifest_rel: str, analysis_rel: str,
    node_evidence_rel: str, calibration_lock: Path, calibration_result: Path,
    output_dir: Path, target_tolerance_eV: float,
) -> dict[str, Any]:
    """Reanalyze a completed fixed-grid primary without running SIESTA."""
    root = source_root.resolve(strict=True)
    output = output_dir.resolve(strict=False)
    if output.exists():
        raise PackagingError(f"sidecar output already exists: {output}")
    try:
        output.relative_to(root)
    except ValueError:
        pass
    else:
        raise PackagingError("offline reanalysis output must be outside the primary campaign")
    if not output.parent.is_dir():
        raise PackagingError("sidecar parent directory must already exist")

    manifest_path, _ = _relative_path(root, manifest_rel, "primary campaign manifest")
    campaign, context_hash = response_grid_source_campaign_context(manifest_path)
    root = Path(str(campaign["_campaign_root"])).resolve(strict=True)
    analysis_path, _ = _relative_path(root, analysis_rel, "primary analysis JSON")
    evidence_path, _ = _relative_path(root, node_evidence_rel, "primary node-evidence JSON")
    analysis = _read_json(analysis_path, "primary analysis JSON")
    primary_analysis_campaign = analysis.get("campaign")
    if (analysis.get("schema_version") != "siestaflow.lr_u_analysis.v3"
            or not isinstance(primary_analysis_campaign, Mapping)
            or primary_analysis_campaign.get("campaign_id") != campaign.get("campaign_id")
            or primary_analysis_campaign.get("fixed_grid") is not True
            or primary_analysis_campaign.get("automatic_alpha_refinement") is not False):
        raise PackagingError("primary analysis must be a completed fixed-grid v3 result for this manifest")

    site_indices = [int(site["index"]) for site in campaign["sites"]]
    site_ids = {int(site["index"]): str(site["site_id"]) for site in campaign["sites"]}
    atom_indices = {int(site["index"]): int(site["atom_index"]) for site in campaign["sites"]}
    alpha_grid = [float(value) for value in campaign["alpha_grid_ev"]]
    calibration = validate_response_grid_calibration(
        root, calibration_lock, calibration_result,
        expected_context_sha256=context_hash,
        expected_sites=site_indices,
        expected_site_ids=site_ids,
        expected_atom_indices=atom_indices,
        expected_alphas_eV=alpha_grid,
        expected_primary_campaign_id=str(campaign["campaign_id"]),
        expected_primary_source_root=root,
    )

    # This sidecar audit parses every response OUT and verifies each FDF/node/DM
    # link. The primary audit dataset is deliberately never included in the
    # calibration result's replica_receipts.
    output.mkdir(parents=False, exist_ok=False)
    primary_input_dir = output / "primary-input-audit"
    package_replica(
        source_root=root,
        manifest_rel=manifest_rel,
        analysis_rel=analysis_rel,
        node_evidence_rel=node_evidence_rel,
        output_dir=primary_input_dir,
        replica_id=str(campaign["campaign_id"]),
    )
    primary_dataset_path = primary_input_dir / "dataset.json"
    primary_dataset = _read_json(primary_dataset_path, "validated primary audit dataset")
    primary_dm_hash = str(primary_dataset["reference_dm_sha256"])
    primary_attempt_ids = {primary_dataset.get("reference_attempt_id")}
    primary_measurements = primary_dataset.get("measurements")
    if not isinstance(primary_measurements, list):
        raise PackagingError("primary audit dataset lacks execution-attempt identities")
    primary_attempt_ids.update(
        item.get("attempt_id") for item in primary_measurements if isinstance(item, Mapping)
    )
    if (str(root.resolve(strict=True)) in calibration.replica_source_roots
            or primary_attempt_ids.intersection(calibration.execution_attempt_ids)):
        raise PackagingError("primary and replica evidence share a campaign root or execution attempt")

    analysis_dataset = analysis["response_observation_dataset"]
    reference = analysis_dataset["reference_source"]
    reference_dm, _ = _relative_path(root, reference.get("dm_path"), "primary reference DM")
    _must_hash(reference_dm, reference.get("dm_sha256"), "primary reference DM")
    nodes = _read_json(evidence_path, "primary node-evidence JSON").get("nodes")
    if not isinstance(nodes, Mapping):
        raise PackagingError("primary node-evidence JSON lacks the node map")
    ref_node_id = reference.get("node_id")
    ref_node = nodes.get(ref_node_id) if isinstance(ref_node_id, str) else None
    if (not isinstance(ref_node, Mapping) or ref_node.get("state") != "VALIDATED"
            or ref_node.get("kind") != "siesta"
            or ref_node.get("evidence_digest") != reference.get("evidence_digest")):
        raise PackagingError("primary reference node is not linked to validated node evidence")
    node_identity = _read_json(evidence_path, "primary node-evidence JSON").get("identity")
    node_meta = ref_node.get("provenance", {}).get("node")
    if (not isinstance(node_identity, Mapping)
            or node_identity.get("campaign_id") != campaign.get("campaign_id")
            or node_identity.get("input_identity") != campaign.get("input_identity")
            or not isinstance(node_meta, Mapping)
            or node_meta.get("node_id") != ref_node_id):
        raise PackagingError("primary reference node identity differs from campaign node evidence")
    ref_hashes = ref_node.get("provenance", {}).get("artifacts")
    ref_command = ref_node.get("command")
    ref_spec = ref_node.get("artifact_spec")
    if not isinstance(ref_hashes, Mapping) or not isinstance(ref_command, Mapping) or not isinstance(ref_spec, Mapping):
        raise PackagingError("primary reference node receipt lacks artifact paths or hashes")
    ref_fdf, _ = _relative_path(root, reference.get("fdf_path"), "primary reference FDF")
    ref_out, _ = _relative_path(root, reference.get("out_path"), "primary reference OUT")
    _must_hash(ref_fdf, reference.get("fdf_sha256"), "primary reference FDF")
    _must_hash(ref_out, reference.get("out_sha256"), "primary reference OUT")
    if (ref_hashes.get("fdf") != reference.get("fdf_sha256")
            or ref_hashes.get("output") != reference.get("out_sha256")
            or ref_hashes.get("dm") != reference.get("dm_sha256")):
        raise PackagingError("primary reference analysis hashes differ from node-evidence hashes")
    ref_cwd = _node_artifact_path(root, ref_command.get("cwd"), "primary reference cwd", directory=True)
    ref_paths: dict[str, Path] = {}
    for name in ("fdf", "output", "dm"):
        item = ref_spec.get(name)
        if not isinstance(item, str) or Path(item).is_absolute() or ".." in Path(item).parts:
            raise PackagingError(f"primary reference artifact path {name} is unsafe")
        ref_paths[name] = _node_artifact_path(root, str(ref_cwd / Path(item)), f"primary reference {name}")
    if (ref_paths["fdf"] != ref_fdf or ref_paths["output"] != ref_out
            or ref_paths["dm"] != reference_dm
            or _node_artifact_path(root, ref_command.get("stdin_path"), "primary reference stdin") != ref_fdf
            or _node_artifact_path(root, ref_command.get("stdout_path"), "primary reference stdout") != ref_out):
        raise PackagingError("primary reference paths differ from node-evidence command/artifact receipt")
    reference_text = ref_out.read_text(encoding="utf-8", errors="replace")
    reference_event = select_converged_screened_event(reference_text)
    reference_occupations = read_printed_occupation_precision(reference_text, reference_event)
    reference_values = [reference_occupations[atom_indices[index]].total for index in site_indices]
    reference_widths = [reference_occupations[atom_indices[index]].half_width for index in site_indices]

    source_rows = analysis_dataset.get("rows")
    if not isinstance(source_rows, list):
        raise PackagingError("primary analysis response rows are missing")
    observations_by_key: dict[tuple[int, float], dict[str, Any]] = {}
    trace_widths: dict[tuple[int, float, str], list[float]] = {}
    for row in source_rows:
        perturbed = int(row["perturbed_site_index"])
        alpha = float(row["alpha_eV"])
        key = (perturbed, alpha)
        observation = observations_by_key.setdefault(key, {
            "bare": [None] * len(site_indices),
            "screened": [None] * len(site_indices),
            "reference": [None] * len(site_indices),
            "width_bare": [None] * len(site_indices),
            "width_screened": [None] * len(site_indices),
            "bare_sources": [None] * len(site_indices),
            "screened_sources": [None] * len(site_indices),
        })
        for observed_row in row["observed_sites"]:
            observed = int(observed_row["observed_site_index"])
            position = site_indices.index(observed)
            reference_value = float(observed_row["occupations_electron"]["reference"])
            reference_width = float(observed_row["occupation_half_widths_electron"]["reference"])
            if (not isclose(reference_value, reference_values[position], rel_tol=0.0, abs_tol=1e-12)
                    or not isclose(reference_width, reference_widths[position], rel_tol=0.0, abs_tol=1e-12)):
                raise PackagingError("primary analysis reference occupations differ from re-parsed reference OUT")
            observation["reference"][position] = reference_value
            for mode in ("bare", "screened"):
                observation[mode][position] = float(observed_row["occupations_electron"][mode])
                observation[f"width_{mode}"][position] = float(observed_row["occupation_half_widths_electron"][mode])
                observation[f"{mode}_sources"][position] = observed_row["sources"][mode]
        for mode in ("bare", "screened"):
            trace_widths[(perturbed, alpha, mode)] = list(observation[f"width_{mode}"])

    primary_observations: list[ResponseObservation] = []
    for (perturbed, alpha), values in sorted(observations_by_key.items()):
        if any(any(value is None for value in values[key]) for key in (
                "bare", "screened", "reference", "width_bare", "width_screened")):
            raise PackagingError(f"primary response grid has an incomplete observation at {(perturbed, alpha)}")
        bare_source = values["bare_sources"][0]
        screened_source = values["screened_sources"][0]
        primary_observations.append(ResponseObservation(
            perturbation_site=perturbed,
            alpha=alpha,
            site_labels=list(site_indices),
            occupations_ref=[float(item) for item in values["reference"]],
            occupations_bare=[float(item) for item in values["bare"]],
            occupations_screened=[float(item) for item in values["screened"]],
            parent_dm_sha256=primary_dm_hash,
            bare_fdf_sha256=str(bare_source["fdf_sha256"]),
            bare_out_sha256=str(bare_source["out_sha256"]),
            screened_fdf_sha256=str(screened_source["fdf_sha256"]),
            screened_out_sha256=str(screened_source["out_sha256"]),
        ))

    config_path, _ = _relative_path(root, str(campaign["lr_config_file"]), "primary LR config")
    config = _read_json(config_path, "primary LR config")
    raw_policy = config.get("analysis_policy", {})
    if not isinstance(raw_policy, Mapping):
        raise PackagingError("primary analysis policy is invalid")
    if isinstance(target_tolerance_eV, bool):
        raise PackagingError("target tolerance must be a finite positive number")
    try:
        target_tolerance = float(target_tolerance_eV)
    except (TypeError, ValueError) as exc:
        raise PackagingError("target tolerance must be a finite positive number") from exc
    if not isfinite(target_tolerance) or target_tolerance <= 0.0:
        raise PackagingError("target tolerance must be a finite positive number")
    def _configured_tolerance_matches(field: str) -> bool:
        value = raw_policy.get(field)
        if isinstance(value, bool):
            return False
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return False
        return isfinite(parsed) and parsed == target_tolerance

    preregistered = (
        _configured_tolerance_matches("sensitivity_tolerance_eV")
        and _configured_tolerance_matches("u_precision_tolerance_eV")
    )
    # Retrospective sidecar policy: do not edit or imply preregistration in the
    # historical campaign. These thresholds affect evaluation only, not the
    # response context bound to independent replicas.
    sidecar_policy = dict(raw_policy)
    sidecar_policy["sensitivity_tolerance_eV"] = target_tolerance
    sidecar_policy["u_precision_tolerance_eV"] = target_tolerance
    policy = LRAnalysisPolicy(**sidecar_policy)
    policy.validate()
    source_provenance = analysis.get("provenance", {})
    result = analyze_verified_lr(
        primary_observations,
        policy,
        campaign={
            "campaign_id": str(campaign["campaign_id"]),
            "reference_dm_sha256": primary_dm_hash,
            "source_root": str(root.resolve(strict=True)),
            "execution_attempt_ids": sorted(item for item in primary_attempt_ids if isinstance(item, str)),
            "name": campaign.get("campaign_name", campaign.get("name")),
            "material": campaign.get("material"),
            "functional": campaign["functional"],
            "sites": campaign["sites"],
            "observables": campaign.get("observables", []),
            "fixed_grid": True,
            "automatic_alpha_refinement": False,
        },
        magnetic_state_labels=None,
        scf_validated=True,
        trace_half_widths_electron=trace_widths,
        occupation_source="siesta_occupations_total",
        response_grid_reproducibility_calibration=calibration,
    )
    precision_assessment = result.get("u_precision_assessment")
    if not isinstance(precision_assessment, dict):
        raise PackagingError("offline analysis omitted its precision assessment")
    analyzer_precision_status = precision_assessment.get("status")
    if preregistered:
        tolerance_origin = "MATCHES_PRIMARY_CAMPAIGN_ANALYSIS_POLICY"
        precision_assessment["preregistration_status"] = "PRIMARY_POLICY_MATCHES_EXPLICIT_TARGET"
        precision_assessment["gate_eligible"] = (
            analyzer_precision_status == "CONDITIONALLY_REPRODUCIBLE_WITHIN_TOTAL_TOLERANCE"
        )
    else:
        tolerance_origin = "USER_DECLARED_FOR_RETROSPECTIVE_EVALUATION"
        precision_assessment["diagnostic_status"] = analyzer_precision_status
        precision_assessment["status"] = "RETROSPECTIVE_THRESHOLD_NOT_PREREGISTERED"
        precision_assessment["assessment_type"] = "retrospective_conditional_reproducibility_diagnostic_only"
        precision_assessment["preregistration_status"] = "PRIMARY_POLICY_DOES_NOT_MATCH_EXPLICIT_TARGET"
        precision_assessment["gate_eligible"] = False
    result["offline_reanalysis"] = {
        "status": "REANALYZED_FROM_HASH_VERIFIED_EXISTING_OUTPUTS",
        "primary_campaign_id": str(campaign["campaign_id"]),
        "primary_manifest_sha256": _sha(manifest_path),
        "primary_analysis_sha256": _sha(analysis_path),
        "primary_node_evidence_sha256": _sha(evidence_path),
        "primary_reference_dm_sha256": primary_dm_hash,
        "primary_included_in_replica_set": False,
        "replica_campaign_ids": list(calibration.replica_campaign_ids),
        "replica_reference_dm_sha256s": list(calibration.reference_dm_sha256s),
        "primary_execution_attempt_ids": sorted(item for item in primary_attempt_ids if isinstance(item, str)),
        "replica_execution_attempt_ids": list(calibration.execution_attempt_ids),
        "response_grid_scope": calibration.scope,
        "interpretation": "conditional empirical reproducibility; not a mathematical error bound or physical acceptance",
        "target_tolerance_eV": target_tolerance,
        "tolerance_origin": tolerance_origin,
        "primary_campaign_preregistered_with_this_tolerance": preregistered,
        "precision_gate_eligible": precision_assessment["gate_eligible"],
        "siesta_executed": False,
        "source_analysis_input_identity": source_provenance.get("input_identity"),
    }
    json_path = write_lr_analysis_v2(output / "lr_u_analysis.offline.v3.json", result)
    report_path = write_lr_u_report(output / "LR_U_REPORT.offline.v3.md", result)
    sidecar_manifest = {
        "schema": "siestaflow.lr_u_offline_reanalysis_receipt.v1",
        "primary_campaign_id": str(campaign["campaign_id"]),
        "primary_analysis_sha256": _sha(analysis_path),
        "primary_node_evidence_sha256": _sha(evidence_path),
        "calibration_lock_sha256": calibration.lock_sha256,
        "calibration_result_sha256": calibration.result_sha256,
        "analysis_sha256": _sha(json_path),
        "report_sha256": _sha(report_path),
        "primary_dataset_audit_path": "primary-input-audit/dataset.json",
        "primary_dataset_audit_sha256": _sha(primary_dataset_path),
        "primary_is_not_a_replica": True,
        "target_tolerance_eV": target_tolerance,
        "tolerance_origin": tolerance_origin,
        "primary_campaign_preregistered_with_this_tolerance": preregistered,
        "precision_gate_eligible": precision_assessment["gate_eligible"],
        "siesta_executed": False,
    }
    (output / "offline-reanalysis-receipt.json").write_text(
        json.dumps(sidecar_manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8",
    )
    return {"analysis": str(json_path), "report": str(report_path), "receipt": str(output / "offline-reanalysis-receipt.json")}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode", choices=("package-replica", "reanalyze-primary"),
        default="package-replica",
        help="package one independent replica or reanalyze a completed primary offline",
    )
    parser.add_argument("--source-root", type=Path, required=True, help="Explicit completed source campaign root")
    parser.add_argument("--manifest", default="campaign.v2.json", help="Campaign manifest, relative to source root")
    parser.add_argument("--analysis", default="results/lr_u_analysis.v3.json", help="Completed fixed-grid analysis, relative to source root")
    parser.add_argument("--node-evidence", default=".siestaflow/node-evidence.json", help="Node-evidence receipt, relative to source root")
    parser.add_argument("--output", type=Path, required=True, help="New sidecar directory outside source root")
    parser.add_argument("--replica-id", help="Optional safe label; defaults to the verified campaign UUID")
    parser.add_argument("--calibration-lock", type=Path, help="Predeclared response-grid calibration lock (reanalyze-primary)")
    parser.add_argument("--calibration-result", type=Path, help="Hash-bound result for the lock (reanalyze-primary)")
    parser.add_argument(
        "--target-tolerance-eV", type=float,
        help="Explicit user-declared retrospective numerical evaluation tolerance (reanalyze-primary)",
    )
    args = parser.parse_args()
    try:
        if args.mode == "package-replica":
            if (args.calibration_lock is not None or args.calibration_result is not None
                    or args.target_tolerance_eV is not None):
                raise PackagingError("calibration lock/result/tolerance are only valid for reanalyze-primary")
            result = package_replica(
                source_root=args.source_root, manifest_rel=args.manifest,
                analysis_rel=args.analysis, node_evidence_rel=args.node_evidence,
                output_dir=args.output, replica_id=args.replica_id,
            )
        else:
            if args.replica_id is not None:
                raise PackagingError("reanalyze-primary uses the manifest campaign UUID; replica-id is not allowed")
            if args.calibration_lock is None or args.calibration_result is None:
                raise PackagingError("reanalyze-primary requires both --calibration-lock and --calibration-result")
            if args.target_tolerance_eV is None:
                raise PackagingError("reanalyze-primary requires explicit --target-tolerance-eV")
            result = reanalyze_primary_offline(
                source_root=args.source_root, manifest_rel=args.manifest,
                analysis_rel=args.analysis, node_evidence_rel=args.node_evidence,
                calibration_lock=args.calibration_lock,
                calibration_result=args.calibration_result,
                output_dir=args.output,
                target_tolerance_eV=args.target_tolerance_eV,
            )
    except (PackagingError, CampaignV2Error, ResponseGridCalibrationError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
