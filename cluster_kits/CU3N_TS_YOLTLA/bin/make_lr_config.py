#!/usr/bin/env python3
"""Build the local Cu3N LR configuration from the frozen FDF."""

import json
import os
from pathlib import Path

root = Path(os.environ["ROOT"])
fdf_path = root / "inputs/reference.fdf"
text = fdf_path.read_text(encoding="utf-8")


def read_block(source: str, name: str) -> list[list[str]]:
    rows: list[list[str]] = []
    active = False
    for line in source.splitlines():
        content = line.split("#", 1)[0].strip()
        fields = content.split()
        if len(fields) >= 2 and fields[0].casefold() == "%block":
            active = fields[1].replace("_", "").replace(".", "").casefold() == name.casefold()
            continue
        if fields and fields[0].casefold() == "%endblock":
            if active:
                return rows
            active = False
            continue
        if active and fields:
            rows.append(fields)
    raise SystemExit(f"ERROR: missing FDF block {name}")


labels = {int(row[0]): row[2] for row in read_block(text, "ChemicalSpeciesLabel")}
coordinates = read_block(text, "AtomicCoordinatesAndAtomicSpecies")
if len(coordinates) != 32:
    raise SystemExit(f"ERROR: expected 32 atoms, found {len(coordinates)}")
sites: list[tuple[str, int]] = []
for atom_index, row in enumerate(coordinates, start=1):
    label = labels[int(row[3])]
    if label.startswith("CuLR"):
        sites.append((label, atom_index))
if len(sites) != 24:
    raise SystemExit(f"ERROR: expected 24 Cu sites, found {len(sites)}")
for label, atom_index in sites:
    if label != f"CuLR{atom_index - 1:02d}":
        raise SystemExit(f"ERROR: atom {atom_index} carries unexpected label {label}")

nitrogen = str((root / "inputs/N.psml").resolve())
payload = {
    "schema": "siestaflow.lr_config.v2",
    "material": "Cu3N-PBE-SC222-translation-shadow-yoltla",
    "functional": "PBE",
    "sites": [
        {"site_id": label, "atom_index": index, "orbit_id": label}
        for label, index in sites
    ],
    "alpha_grid_ev": [-0.1, -0.05, -0.025, 0.025, 0.05, 0.1],
    "pseudopotentials": {
        **{label: str((root / "inputs" / f"{label}.psml").resolve()) for label, _ in sites},
        "N": nitrogen,
    },
    "static_artifacts": {},
    "compatibility_registry": str(
        (root / "config/backend_compatibility.json").resolve()
    ),
    "version_text_source": str((root / "config/siesta-version.txt").resolve()),
    "declared_executable": "siesta",
    "reference_dm_name": "00_REFERENCE.DM",
    "analysis_policy": {
        "estimator": "polynomial",
        "polynomial_degree": 3,
        "minimum_residual_dof": 1,
        "matrix_for_inversion": "raw",
    },
    "magnetic_moment_tolerance_muB": 0.1,
    "adaptive_alpha_policy": None,
}
out = root / "config/lr-config.json"
out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
print("LR_CONFIG_WRITTEN config/lr-config.json")
