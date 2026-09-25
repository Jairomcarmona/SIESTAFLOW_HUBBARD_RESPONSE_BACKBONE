"""Select the PSML matching an FDF species label by exact label and atomic number."""

from __future__ import annotations

import argparse
from pathlib import Path

from psml_selection import read_fdf_species, select_psml_sources


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fdf", type=Path, required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--pseudo-directory", type=Path, required=True)
    args = parser.parse_args()
    try:
        species = read_fdf_species(args.fdf)
        if args.label not in species:
            raise ValueError(f"FDF label not found: {args.label}")
        selected = select_psml_sources(species, sorted(args.pseudo_directory.glob("*.psml")))
    except (OSError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    print(selected[args.label])


if __name__ == "__main__":
    main()
