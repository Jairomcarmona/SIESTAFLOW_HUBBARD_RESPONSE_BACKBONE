"""Extract R10 manifest-space identities and recorded hashes without simulation.

Only the archived manifest, lr-config and node-evidence are read. The golden is therefore
independent of current planner/materializer implementations and never invents
missing historical evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, cast


def _load(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise TypeError(f"archive must be a JSON object: {path}")
    return cast(dict[str, Any], raw)


def _sha(value: object) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError("archive does not supply a valid SHA256")
    return value


def _archive_golden(manifest_path: Path, evidence_path: Path, lr_config_path: Path) -> dict[str, Any]:
    manifest, evidence = _load(manifest_path), _load(evidence_path)
    if manifest["campaign_id"] != evidence["identity"]["campaign_id"]:
        raise ValueError("archive manifest and node evidence belong to different campaigns")
    if manifest["input_identity"] != evidence["identity"]["input_identity"]:
        raise ValueError("archive input identities disagree")
    sites = manifest["sites"]
    by_label = {s["site_id"]: s for s in sites}
    if len(by_label) != len(sites) or any(
        type(s["atom_index"]) is not int or s["atom_index"] < 1 for s in sites
    ):
        raise ValueError("archive requires distinct manifest labels and one-based atom indices")
    rows, fdf_hashes = [], {}
    for node_id, record in sorted(evidence["nodes"].items()):
        provenance = record.get("provenance")
        if provenance is None:
            continue
        fdf_hashes[node_id] = _sha(provenance["artifacts"]["fdf"])
        node = provenance["node"]
        spec = node["perturbation"]
        if spec is None:
            continue
        site = by_label[spec["site_id"]]
        alpha = spec["alpha_ev"]
        if (
            type(alpha) not in (int, float)
            or not math.isfinite(alpha)
            or alpha == 0
            or spec["mode"] not in {"BARE", "SCREENED"}
            or spec["site_index"] != site["index"]
            or node["node_id"] != node_id
        ):
            raise ValueError(f"inconsistent archived response identity: {node_id}")
        rows.append(
            {
                "label": site["site_id"],
                "atom_index": site["atom_index"],
                "mode": spec["mode"],
                "alpha_ev": alpha,
            }
        )
    identities = {(r["label"], r["atom_index"], r["mode"], r["alpha_ev"]) for r in rows}
    expected = {
        (s["site_id"], s["atom_index"], mode, alpha)
        for s in sites
        for mode in ("BARE", "SCREENED")
        for alpha in manifest["alpha_grid_ev"]
    }
    if len(identities) != len(rows) or identities != expected:
        raise ValueError("archived node-evidence does not exactly cover the declared manifest grid")
    inputs = {r["path"]: _sha(r["sha256"]) for r in manifest["input_files"]}
    config_bytes = lr_config_path.read_bytes()
    if hashlib.sha256(config_bytes).hexdigest() != inputs[manifest["lr_config_file"]]:
        raise ValueError("archived lr-config SHA256 differs from the manifest input inventory")
    config = _load(lr_config_path)
    if fdf_hashes.get("reference") != inputs[manifest["reference_fdf"]]:
        raise ValueError("archive reference materialization differs from its declared input")
    return {
        "schema": "hubbardflow.phase2_golden.v1",
        "system": "NiO-P5",
        "archive": {
            "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            "node_evidence_sha256": hashlib.sha256(evidence_path.read_bytes()).hexdigest(),
            "reference_fdf": manifest["reference_fdf"],
            "lr_config_file": manifest["lr_config_file"],
            "input_files_sha256": inputs,
        },
        "sites": sites,
        "archived_lr_config": config,
        # Preserve source bytes as UTF-8 text so portable regeneration tests
        # can verify the archived SHA without access to the original WSL tree.
        "archived_lr_config_source_text": config_bytes.decode("utf-8"),
        "scientific_values": {
            key: manifest[key]
            for key in (
                "material",
                "functional",
                "alpha_grid_ev",
                "analysis_policy",
                "adaptive_alpha_policy",
                "magnetic_moment_tolerance_muB",
            )
        },
        "response_identities": sorted(
            rows, key=lambda r: (r["label"], r["atom_index"], r["mode"], r["alpha_ev"])
        ),
        "materialized_fdf_sha256": fdf_hashes,
    }


def _main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--node-evidence", type=Path, required=True)
    parser.add_argument("--lr-config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source_paths = {args.manifest.resolve(), args.node_evidence.resolve(), args.lr_config.resolve()}
    if args.output.resolve() in source_paths:
        parser.error("output must not overwrite archived input evidence")
    if any(args.output.resolve().is_relative_to(source.parent) for source in source_paths):
        parser.error("output must be outside the read-only archived campaign")
    golden = _archive_golden(args.manifest, args.node_evidence, args.lr_config)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(golden, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8", newline="\n"
    )
    print(
        f"{len(golden['response_identities'])} response identities; {len(golden['materialized_fdf_sha256'])} recorded FDF hashes"
    )


if __name__ == "__main__":
    _main()
