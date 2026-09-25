#!/usr/bin/env python3
"""Create a fail-closed symmetry pre-audit from an explicit SIESTA FDF."""

from __future__ import annotations

import argparse
from pathlib import Path

from siestaflow_hubbard.siesta_backend.fdf_symmetry_adapter import audit_fdf_symmetry, audit_to_json


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fdf", type=Path, help="Reference SIESTA FDF with explicit fractional coordinates")
    parser.add_argument("--reference-moments", type=Path,
                        help="Accepted-reference magnetic evidence JSON; omission disables reduction")
    parser.add_argument("--output", type=Path, help="Write audit JSON to this path instead of stdout")
    args = parser.parse_args()
    rendered = audit_to_json(audit_fdf_symmetry(args.fdf, args.reference_moments)) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
