#!/usr/bin/env python
"""Create or extend an explicit SIESTA 5.4.2 BARE compatibility matrix.

This tool does not execute SIESTA, load modules, discover ``PATH`` or submit a
job.  Its caller supplies an executable path selected by a private backend
plugin and a text file containing that backend's already-captured version
banner.  ``--write`` is deliberately required for a persistent change.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

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
    parser.add_argument("--write", action="store_true", help="persist the canonical registry JSON")
    args = parser.parse_args(argv)

    observed = identify_backend(args.executable, args.version_text.read_text(encoding="utf-8"), backend="siesta")
    if observed.version != "5.4.2":
        parser.error("this tool only registers the source-audited SIESTA 5.4.2 profile")
    profile = Siesta542PotentialShiftHamiltonianProfile()
    scientific = ScientificProfile(profile.profile_id, profile.profile_version, {
        "source_revision": profile.source_revision,
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
