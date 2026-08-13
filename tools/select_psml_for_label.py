"""Select the PSML matching an FDF species label by atomic number."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from stage_fdf_pseudos import fdf_species, pseudo_atomic_number


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fdf", type=Path, required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--pseudo-directory", type=Path, required=True)
    args = parser.parse_args()
    species = fdf_species(args.fdf)
    if args.label not in species:
        raise SystemExit(f"FDF label not found: {args.label}")
    matching = [path for path in args.pseudo_directory.glob("*.psml") if pseudo_atomic_number(path) == species[args.label]]
    if len(matching) != 1:
        raise SystemExit(f"expected exactly one PSML for {args.label}; found {len(matching)}")
    print(matching[0])


if __name__ == "__main__":
    main()
