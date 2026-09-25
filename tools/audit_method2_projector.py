"""Audit a SIESTA Method-2 Hubbard projector before an LR-U campaign.

The tool deliberately does not choose U or alter an FDF.  It combines:
the calculation geometry, an optional PSML identity check, and the *actual*
``.dftu_proj`` written by SIESTA during initialization.  Its recommendation is
only a compact, geometrically local sensitivity window for human review.
"""

from __future__ import annotations

import argparse
import json
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from siesta_dftu_fdf import projector_specs_from_text

BOHR_TO_ANG = 0.529177210903


def _block(text: str, name: str) -> list[str]:
    match = re.search(rf"%block\s+{re.escape(name)}\s*(.*?)%endblock\s+{re.escape(name)}", text, re.I | re.S)
    if not match:
        raise ValueError(f"missing %block {name}")
    return [line.split("#", 1)[0].strip() for line in match.group(1).splitlines() if line.split("#", 1)[0].strip()]


def _unit_factor(unit: str) -> float:
    if unit.lower().startswith("bohr"):
        return BOHR_TO_ANG
    if unit.lower().startswith("ang"):
        return 1.0
    raise ValueError(f"unsupported length unit {unit!r}; use Ang or Bohr explicitly")


def parse_fdf(path: Path, central_label: str) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    species: dict[int, dict[str, Any]] = {}
    for line in _block(text, "ChemicalSpeciesLabel"):
        fields = line.split()
        species[int(fields[0])] = {"atomic_number": int(fields[1]), "label": fields[2]}

    lattice_constant = re.search(r"^\s*LatticeConstant\s+([\d.eEdD+-]+)\s+(\w+)", text, re.I | re.M)
    if not lattice_constant:
        raise ValueError("LatticeConstant with explicit unit is required")
    constant = float(lattice_constant.group(1).replace("D", "E")) * _unit_factor(lattice_constant.group(2))
    lattice = np.array([[float(x) for x in line.split()[:3]] for line in _block(text, "LatticeVectors")]) * constant

    coordinate_format = re.search(r"^\s*AtomicCoordinatesFormat\s+(\w+)", text, re.I | re.M)
    if not coordinate_format:
        raise ValueError("AtomicCoordinatesFormat is required")
    coord_format = coordinate_format.group(1).lower()
    coordinates, labels, atomic_numbers = [], [], []
    for line in _block(text, "AtomicCoordinatesAndAtomicSpecies"):
        fields = line.split()
        atom_species = species[int(fields[3])]
        coordinates.append([float(x) for x in fields[:3]])
        labels.append(atom_species["label"])
        atomic_numbers.append(atom_species["atomic_number"])
    coordinates_array = np.array(coordinates)
    if coord_format.startswith("frac"):
        cartesian = coordinates_array @ lattice
    elif coord_format.startswith("ang"):
        cartesian = coordinates_array
    elif coord_format.startswith("bohr"):
        cartesian = coordinates_array * BOHR_TO_ANG
    else:
        raise ValueError(f"unsupported AtomicCoordinatesFormat {coord_format!r}")

    if central_label not in labels:
        raise ValueError(f"central label {central_label!r} is absent from FDF")
    return {
        "text": text,
        "lattice_A": lattice,
        "cartesian_A": cartesian,
        "labels": labels,
        "atomic_numbers": atomic_numbers,
        "species": species,
    }


def parse_method2_parameters(fdf_text: str, central_label: str) -> dict[str, float | int] | None:
    specs = projector_specs_from_text(fdf_text)
    spec = specs.get(central_label)
    if spec is None:
        return None
    return {
        "n": spec["n"],
        "l": spec["l"],
        "rc_bohr": spec["rc_bohr"],
        "omega_bohr": spec["omega_bohr"],
        "cutoff_mode": spec["cutoff_mode"],
        "cutoff_norm": spec["cutoff_norm"],
        "lambda": spec["lambda"],
    }


def parse_psml(path: Path) -> dict[str, Any]:
    root = ET.parse(path).getroot()
    atom = next((node for node in root.iter() if node.tag.rsplit("}", 1)[-1] == "pseudo-atom-spec"), None)
    if atom is None:
        raise ValueError("PSML does not contain pseudo-atom-spec")
    result: dict[str, Any] = {"path": str(path), "atomic_label": atom.get("atomic-label"), "atomic_number": int(atom.get("atomic-number"))}
    valence = next((node for node in root.iter() if node.tag.rsplit("}", 1)[-1] == "valence-configuration"), None)
    if valence is not None:
        result["valence_configuration"] = " ".join("".join(valence.itertext()).split())
    return result


def parse_projector(path: Path) -> tuple[int, int, np.ndarray, np.ndarray, float]:
    rows = [line.split() for line in path.read_text(encoding="utf-8").splitlines() if line.strip() and not line.lstrip().startswith("#")]
    def is_grid_header(row: list[str]) -> bool:
        try:
            int(row[0]); float(row[1]); float(row[2])
            return True
        except (IndexError, ValueError):
            return False
    header_index = next((i for i, row in enumerate(rows) if is_grid_header(row)), None)
    if header_index is None:
        raise ValueError("cannot find dftu_proj grid header")
    if header_index == 0:
        raise ValueError("dftu_proj is missing its l,n header")
    quantum = rows[header_index - 1]
    if len(quantum) < 2:
        raise ValueError("invalid dftu_proj l,n header")
    l_value, n_value = int(quantum[0]), int(quantum[1])
    if l_value < 0:
        raise ValueError("dftu_proj angular momentum l must be non-negative")
    npts, delta, cutoff = int(rows[header_index][0]), float(rows[header_index][1]), float(rows[header_index][2])
    if npts < 2 or header_index + 1 + npts > len(rows):
        raise ValueError("dftu_proj contains an incomplete radial grid")
    if header_index + 1 + npts < len(rows):
        raise ValueError("dftu_proj contains multiple projector blocks or trailing data; audit all shells explicitly")
    grid_rows = rows[header_index + 1 : header_index + 1 + npts]
    if any(len(row) < 2 for row in grid_rows):
        raise ValueError("dftu_proj contains a malformed radial row")
    data = np.array([[float(x) for x in row[:2]] for row in grid_rows])
    if len(data) != npts or not np.all(np.isfinite(data)):
        raise ValueError(f"projector declares {npts} points but has incomplete/non-finite data ({len(data)} rows)")
    if not np.isfinite(delta) or delta <= 0 or not np.isfinite(cutoff) or cutoff <= 0:
        raise ValueError("projector grid spacing/cutoff must be finite and positive")
    if data[0, 0] < 0 or np.any(np.diff(data[:, 0]) <= 0):
        raise ValueError("projector grid/cutoff is invalid")
    return l_value, n_value, data[:, 0], data[:, 1], cutoff


def cumulative_norm(r: np.ndarray, radial_value: np.ndarray, l_value: int) -> np.ndarray:
    # SIESTA writes f_l=R_l/r^l; the 3-D radial measure is r^(2l+2)|f_l|² dr.
    density = np.power(r, 2 * l_value + 2) * np.square(radial_value)
    cumulative = np.concatenate(([0.0], np.cumsum((density[1:] + density[:-1]) * np.diff(r) / 2.0)))
    if not np.all(np.isfinite(cumulative)) or cumulative[-1] <= 0:
        raise ValueError("projector radial norm must be finite and positive")
    return cumulative / cumulative[-1]


def neighbour_distances(data: dict[str, Any], central_label: str) -> dict[str, Any]:
    labels: list[str] = data["labels"]
    positions: np.ndarray = data["cartesian_A"]
    lattice: np.ndarray = data["lattice_A"]
    central_index = labels.index(central_label)
    # Convert Cartesian deltas to fractional then apply the minimum image convention.
    inverse_lattice = np.linalg.inv(lattice)
    grouped: dict[str, list[float]] = defaultdict(list)
    for index, label in enumerate(labels):
        if index == central_index:
            continue
        fractional_delta = (positions[index] - positions[central_index]) @ inverse_lattice
        fractional_delta -= np.round(fractional_delta)
        grouped[label].append(float(np.linalg.norm(fractional_delta @ lattice)))
    nearest = {label: min(values) for label, values in grouped.items()}
    nearest_other = min(nearest.values())
    return {
        "nearest_by_species_label_A": dict(sorted(nearest.items())),
        "nearest_any_neighbour_A": nearest_other,
        "nearest_any_neighbour_bohr": nearest_other / BOHR_TO_ANG,
    }


def recommendation(method2: dict[str, Any] | None, cutoff: float, nearest_bohr: float) -> dict[str, Any]:
    rc = method2.get("rc_bohr") if method2 else None
    mode = method2.get("cutoff_mode") if method2 else None
    if mode == "cutoff_norm":
        return {
            "cutoff_mode": mode,
            "cutoff_norm": method2.get("cutoff_norm"),
            "soft_projector_cutoff_bohr": cutoff,
            "nearest_neighbour_bohr": nearest_bohr,
            "locality_ratio_cutoff_to_neighbour": cutoff / nearest_bohr,
            "rule": "The FDF delegates the radius to the effective LDAU/DFTU.CutoffNorm (DFTU overrides LDAU). Review nearby retained-norm values rather than an explicit rc.",
            "review_cutoff_norm_candidates": [0.85, 0.90, 0.95],
            "status": "LOCALITY_WINDOW_AVAILABLE" if cutoff <= 0.85 * nearest_bohr else "REVIEW_REQUIRED",
            "warning": "This is a physical locality screen, not a convergence claim and not an automatic U selection.",
        }
    current = rc if rc is not None else cutoff
    safe_upper = 0.85 * nearest_bohr
    candidates = sorted({round(value, 3) for value in (current - 0.5, current, current + 0.5) if value > 0.0 and value <= safe_upper})
    return {
        "cutoff_mode": mode,
        "current_rc_bohr": rc,
        "soft_projector_cutoff_bohr": cutoff,
        "nearest_neighbour_bohr": nearest_bohr,
        "locality_ratio_rc_to_neighbour": current / nearest_bohr,
        "rule": "Candidates are rc ± 0.5 Bohr retained only when rc is at most 85% of the nearest-neighbour distance.",
        "review_candidates_bohr": candidates,
        "status": "REVIEW_REQUIRED" if not candidates or current > safe_upper else "LOCALITY_WINDOW_AVAILABLE",
        "warning": "This is a physical locality screen, not a convergence claim and not an automatic U selection.",
    }


def markdown(report: dict[str, Any]) -> str:
    radial = report["radial_projector"]
    geometry = report["geometry"]
    suggested = report["recommendation"]
    lines = [
        "# Method-2 Hubbard Projector Preflight",
        "",
        f"Status: **{report['status']}**",
        "",
        "## Actual SIESTA projector",
        "",
        f"- Radial cutoff: {radial['cutoff_bohr']:.4f} Bohr ({radial['cutoff_A']:.4f} Å)",
        f"- 90% radial norm: {radial['quantile_bohr']['0.9']:.4f} Bohr",
        f"- 99% radial norm: {radial['quantile_bohr']['0.99']:.4f} Bohr",
        "",
        "## Geometry and review window",
        "",
        f"- Nearest neighbour: {geometry['nearest_any_neighbour_bohr']:.4f} Bohr",
        f"- Locality ratio: {suggested.get('locality_ratio_rc_to_neighbour', suggested.get('locality_ratio_cutoff_to_neighbour')):.3f}",
        f"- Human-review candidates: {suggested.get('review_candidates_bohr', suggested.get('review_cutoff_norm_candidates'))}",
        "",
        "This report does not select a Hubbard U or certify convergence. It only filters physically non-local projector choices before an LR-U sensitivity calculation.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fdf", type=Path, required=True)
    parser.add_argument("--projector", type=Path, required=True, help="Materialized SIESTA *.dftu_proj")
    parser.add_argument("--central-label", required=True)
    parser.add_argument("--psml", type=Path, help="Source PSML; used only for identity validation")
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    args = parser.parse_args()

    fdf = parse_fdf(args.fdf, args.central_label)
    method2 = parse_method2_parameters(fdf["text"], args.central_label)
    l_value, n_value, r, values, cutoff = parse_projector(args.projector)
    cumulative = cumulative_norm(r, values, l_value)
    if method2 is None or method2["l"] != l_value:
        raise ValueError(f"projector l={l_value} does not match FDF DFTU.Proj l={method2.get('l') if method2 else 'missing'}")
    geometry = neighbour_distances(fdf, args.central_label)
    central_atomic_number = fdf["atomic_numbers"][fdf["labels"].index(args.central_label)]
    psml = parse_psml(args.psml) if args.psml else None
    psml_matches = psml is None or psml["atomic_number"] == central_atomic_number
    rc = method2["rc_bohr"] if method2 and method2.get("cutoff_mode") == "explicit_rc" else None
    report: dict[str, Any] = {
        "status": "PASS_PRELIGHT_REVIEW_REQUIRED" if psml_matches and method2 else "BLOCK_CONFIGURATION_MISMATCH",
        "inputs": {"fdf": str(args.fdf), "projector": str(args.projector), "central_label": args.central_label, "psml": str(args.psml) if args.psml else None},
        "method2_fdf_configuration": method2,
        "psml_identity": psml,
        "psml_atomic_number_matches_fdf": psml_matches,
        "radial_projector": {
            "radial_measure": f"integral r^(2l+2) |f_l(r)|^2 dr; f_l=R_l/r^l; l={l_value}",
            "l": l_value, "n": n_value,
            "n_points": len(r), "grid_delta_bohr": float(r[1] - r[0]), "cutoff_bohr": cutoff, "cutoff_A": cutoff * BOHR_TO_ANG,
            "quantile_bohr": {str(q): float(np.interp(q, cumulative, r)) for q in (0.85, 0.90, 0.95, 0.99)},
            "norm_inside_rc": float(np.interp(rc, r, cumulative)) if rc else None,
        },
        "geometry": geometry,
        "recommendation": recommendation(method2, cutoff, geometry["nearest_any_neighbour_bohr"]),
        "limitations": ["A local projector is necessary but does not prove LR linearity, SCF convergence, matrix rank, or transferability of U.", "Do not choose rc by targeting a desired U value."],
    }
    rendered = json.dumps(report, indent=2)
    if args.json_out:
        args.json_out.write_text(rendered + "\n", encoding="utf-8")
    if args.markdown_out:
        args.markdown_out.write_text(markdown(report), encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
