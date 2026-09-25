#!/usr/bin/env python3
"""Extract fail-closed final magnetic evidence from a SIESTA reference output."""

from __future__ import annotations

import argparse
from pathlib import Path

from siestaflow_hubbard.siesta_backend.reference_magnetic_evidence import build_reference_magnetic_evidence


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fdf", type=Path)
    parser.add_argument("siesta_out", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    build_reference_magnetic_evidence(args.fdf, args.siesta_out, args.output)
    print(args.output.resolve())


if __name__ == "__main__":
    main()
