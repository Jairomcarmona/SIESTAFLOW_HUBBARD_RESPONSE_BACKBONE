"""Stage PSML pseudopotentials under the species labels declared by an FDF."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from psml_selection import pseudo_atomic_number, read_fdf_species, select_psml_sources


def fdf_species(path: Path) -> dict[str, int]:
    return read_fdf_species(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fdf", type=Path, required=True)
    parser.add_argument("--pseudo-directory", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    try:
        species = fdf_species(args.fdf)
        selected = select_psml_sources(species, sorted(args.pseudo_directory.glob("*.psml")))
    except (OSError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc

    # Resolve every species before writing any staged file, so a semantic
    # selection error never leaves a half-staged set.
    args.destination.mkdir(parents=True, exist_ok=True)
    staged = []
    for label, source in selected.items():
        target = args.destination / f"{label}.psml"
        shutil.copy2(source, target)
        staged.append(target.name)
    print("STAGED_PSEUDOS: " + ",".join(staged))


if __name__ == "__main__":
    main()
