#!/usr/bin/env python
"""Create or extend an explicit SIESTA 5.4.2 BARE compatibility matrix.

This tool does not execute SIESTA, load modules, discover ``PATH`` or submit a
job.  Its caller supplies an executable path selected by a private backend
plugin and a text file containing that backend's already-captured version
banner.  ``--write`` is deliberately required for a persistent change.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Mapping

from siestaflow_hubbard.domain.backend_compatibility import (
    BackendCompatibilityRegistry,
    BackendIdentity,
    CompatibilityRecord,
    CompatibilityState,
    ScientificProfile,
)
from siestaflow_hubbard.siesta_backend.backend_identity import identify_backend
from siestaflow_hubbard.siesta_backend.siesta542_bare_profile import (
    Siesta542PotentialShiftHamiltonianProfile,
)


_F20_12_PATCH_SHA256 = "3539150217903b2665102a44396a9d84281fc91e1170819dc79e413af15d0116"


def _load_registry(path: Path) -> BackendCompatibilityRegistry:
    if not path.exists():
        return BackendCompatibilityRegistry()
    return BackendCompatibilityRegistry.from_json(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", required=True, type=Path, help="compatibility JSON to create or update")
    parser.add_argument("--executable", required=True, type=Path, help="explicit SIESTA executable")
    parser.add_argument("--version-text", required=True, type=Path, help="captured SIESTA version-banner text")
    parser.add_argument("--reason", required=True, help="review decision/reference authorizing this entry")
    parser.add_argument(
        "--occupation-output-format", choices=("stock-f12.6", "extended-f20.12"),
        default="stock-f12.6",
        help="verified Occupations summary format emitted by this exact executable",
    )
    parser.add_argument(
        "--occupation-patch", type=Path,
        help="canonical f20.12 patch declared for this executable",
    )
    parser.add_argument(
        "--occupation-build-receipt", type=Path,
        help="build-process JSON receipt linking the patch hash to this executable hash",
    )
    parser.add_argument("--write", action="store_true", help="persist the canonical registry JSON")
    args = parser.parse_args(argv)

    occupation_metadata = {
        "occupation_output_format": args.occupation_output_format,
        "occupation_decimal_places": 12 if args.occupation_output_format == "extended-f20.12" else 6,
    }
    if args.occupation_output_format == "extended-f20.12":
        if args.occupation_patch is None or not args.occupation_patch.is_file():
            parser.error("extended-f20.12 registration requires --occupation-patch")
        patch_digest = hashlib.sha256(args.occupation_patch.read_bytes()).hexdigest()
        if patch_digest != _F20_12_PATCH_SHA256:
            parser.error("--occupation-patch is not the reviewed canonical Occupations f20.12 patch")
        occupation_metadata["occupation_patch_sha256"] = patch_digest
        occupation_metadata["occupation_build_receipt_status"] = "DECLARED_UNVERIFIED"
        if args.occupation_build_receipt is not None and not args.occupation_build_receipt.is_file():
            parser.error("--occupation-build-receipt must name an existing build receipt JSON")
    elif args.occupation_patch is not None:
        parser.error("--occupation-patch is valid only with --occupation-output-format extended-f20.12")
    elif args.occupation_build_receipt is not None:
        parser.error("--occupation-build-receipt is valid only with --occupation-output-format extended-f20.12")

    observed = identify_backend(args.executable, args.version_text.read_text(encoding="utf-8"), backend="siesta")
    if observed.version != "5.4.2":
        parser.error("this tool only registers the source-audited SIESTA 5.4.2 profile")
    if args.occupation_build_receipt is not None:
        try:
            receipt_payload = json.loads(args.occupation_build_receipt.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            parser.error(f"occupation build receipt is unreadable JSON: {exc}")
        if not isinstance(receipt_payload, Mapping):
            parser.error("occupation build receipt must be a JSON object")
        required_receipt = {
            "schema": "siestaflow.siesta_occupation_build_receipt.v1",
            "occupation_output_format": "extended-f20.12",
            "occupation_decimal_places": 12,
            "source_patch_sha256": _F20_12_PATCH_SHA256,
            "executable_sha256": observed.executable_sha256,
        }
        if any(receipt_payload.get(key) != value for key, value in required_receipt.items()):
            parser.error("occupation build receipt does not bind the canonical patch and observed executable hash")
        if not isinstance(receipt_payload.get("build_id"), str) or not receipt_payload["build_id"].strip():
            parser.error("occupation build receipt must include a nonempty build_id")
        if not isinstance(receipt_payload.get("build_process"), Mapping) or not receipt_payload["build_process"]:
            parser.error("occupation build receipt must identify its build_process")
        canonical_receipt = json.dumps(receipt_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        occupation_metadata.update({
            "occupation_build_receipt_status": "BUILD_RECEIPT_LINKED",
            "occupation_build_receipt": dict(receipt_payload),
            "occupation_build_receipt_sha256": hashlib.sha256(canonical_receipt.encode("utf-8")).hexdigest(),
        })
    profile = Siesta542PotentialShiftHamiltonianProfile()
    scientific = ScientificProfile(profile.profile_id, profile.profile_version, {
        "source_revision": profile.source_revision,
        **occupation_metadata,
    })
    record = CompatibilityRecord(
        BackendIdentity("siesta", observed.version, observed.executable_sha256),
        scientific,
        CompatibilityState.COMPATIBLE,
        args.reason,
    )
    registry = _load_registry(args.registry).add(record)
    payload = registry.to_json() + "\n"
    print(payload, end="")
    if not args.write:
        print("DRY_RUN: matrix was not written; repeat with --write after review.", file=sys.stderr)
        return 0
    args.registry.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.registry.with_suffix(args.registry.suffix + ".tmp")
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(args.registry)
    print("WROTE: {0}".format(args.registry), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
