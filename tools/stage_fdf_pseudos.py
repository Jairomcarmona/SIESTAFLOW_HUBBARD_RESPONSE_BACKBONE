"""Stage PSML pseudopotentials under the species labels declared by an FDF."""

from __future__ import annotations

import argparse
import re
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path


def pseudo_atomic_number(path: Path) -> int:
    root = ET.parse(path).getroot()
    atom = next((node for node in root.iter() if node.tag.rsplit("}", 1)[-1] == "pseudo-atom-spec"), None)
    if atom is None or atom.get("atomic-number") is None:
        raise ValueError(f"cannot read atomic number from PSML: {path}")
    return int(atom.get("atomic-number"))


def fdf_species(path: Path) -> dict[str, int]:
    text = path.read_text(encoding="utf-8")
    match = re.search(r"%block\s+ChemicalSpeciesLabel\s*(.*?)%endblock\s+ChemicalSpeciesLabel", text, re.I | re.S)
    if not match:
        raise ValueError("FDF lacks ChemicalSpeciesLabel")
    result = {}
    for line in match.group(1).splitlines():
        fields = line.split()
        if fields and not line.lstrip().startswith("#"):
            result[fields[2]] = int(fields[1])
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fdf", type=Path, required=True)
    parser.add_argument("--pseudo-directory", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    sources = {pseudo_atomic_number(path): path for path in args.pseudo_directory.glob("*.psml")}
    staged = []
    for label, atomic_number in fdf_species(args.fdf).items():
        source = sources.get(atomic_number)
        if source is None:
            raise SystemExit(f"no PSML source for atomic number {atomic_number}, FDF species {label}")
        target = args.destination / f"{label}.psml"
        shutil.copy2(source, target)
        staged.append(target.name)
    print("STAGED_PSEUDOS: " + ",".join(staged))


if __name__ == "__main__":
    main()
