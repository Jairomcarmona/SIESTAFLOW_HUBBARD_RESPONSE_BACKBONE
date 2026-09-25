"""Resolve the PSML selected by each FDF chemical-species label."""

from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from pathlib import Path


def parse_fdf_species(text: str, source: str = "FDF") -> dict[str, int]:
    """Return unique label-to-Z entries from ChemicalSpeciesLabel."""
    lines = text.splitlines()
    blocks: list[list[str]] = []
    index = 0
    while index < len(lines):
        clean = lines[index].split("#", 1)[0].strip()
        start = re.fullmatch(r"%block\s+ChemicalSpeciesLabel", clean, re.I)
        if not start:
            index += 1
            continue
        body: list[str] = []
        index += 1
        while index < len(lines):
            clean = lines[index].split("#", 1)[0].strip()
            end = re.fullmatch(r"%endblock\s+ChemicalSpeciesLabel", clean, re.I)
            if end:
                blocks.append(body)
                break
            if re.match(r"%endblock\b", clean, re.I):
                raise ValueError(f"{source}: ChemicalSpeciesLabel block has a mismatched end")
            body.append(lines[index])
            index += 1
        else:
            raise ValueError(f"{source}: unterminated ChemicalSpeciesLabel block")
        index += 1
    if len(blocks) != 1:
        raise ValueError(f"{source}: expected one ChemicalSpeciesLabel block, found {len(blocks)}")
    species: dict[str, int] = {}
    indices: set[int] = set()
    for line_number, raw in enumerate(blocks[0], start=1):
        fields = raw.split("#", 1)[0].split()
        if not fields:
            continue
        if len(fields) != 3:
            raise ValueError(f"{source}: malformed ChemicalSpeciesLabel row {line_number}")
        try:
            index, atomic_number = int(fields[0]), int(fields[1])
        except ValueError as exc:
            raise ValueError(f"{source}: malformed ChemicalSpeciesLabel row {line_number}") from exc
        label = fields[2]
        if not re.fullmatch(r"[A-Za-z0-9_.+-]+", label) or label in {".", ".."}:
            raise ValueError(f"{source}: unsafe or unsupported species label {label!r}")
        if index <= 0 or atomic_number <= 0 or label in species or index in indices:
            raise ValueError(f"{source}: duplicate or invalid species row {line_number}")
        species[label] = atomic_number
        indices.add(index)
    if not species:
        raise ValueError(f"{source}: ChemicalSpeciesLabel block is empty")
    return species


def read_fdf_species(path: Path) -> dict[str, int]:
    return parse_fdf_species(path.read_text(encoding="utf-8"), str(path))


def pseudo_atomic_number(path: Path) -> int:
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as exc:
        raise ValueError(f"cannot parse PSML: {path}") from exc
    atom = next(
        (node for node in root.iter() if node.tag.rsplit("}", 1)[-1] == "pseudo-atom-spec"),
        None,
    )
    if atom is None or atom.get("atomic-number") is None:
        raise ValueError(f"cannot read atomic number from PSML: {path}")
    try:
        value = int(atom.get("atomic-number", ""))
    except ValueError as exc:
        raise ValueError(f"invalid atomic number in PSML: {path}") from exc
    if value <= 0:
        raise ValueError(f"invalid atomic number in PSML: {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def select_psml_sources(species: dict[str, int], candidates: list[Path]) -> dict[str, Path]:
    """Select one exact-label PSML or one unique-by-content PSML for every label.

    An exact ``LABEL.psml`` has priority. Without one, multiple distinct PSML
    files for the same Z are rejected even if their filenames look plausible.
    """
    existing: list[tuple[Path, int, str]] = []
    for path in candidates:
        if not path.is_file():
            raise ValueError(f"PSML source does not exist: {path}")
        existing.append((path, pseudo_atomic_number(path), _sha256(path)))

    selected: dict[str, Path] = {}
    for label, expected_z in species.items():
        exact = [(path, z, digest) for path, z, digest in existing if path.name == f"{label}.psml"]
        if exact:
            if len({digest for _, _, digest in exact}) != 1:
                raise ValueError(f"ambiguous exact PSML for FDF label {label}")
            path, actual_z, _ = exact[0]
            if actual_z != expected_z:
                raise ValueError(f"exact PSML has Z={actual_z}, expected Z={expected_z} for FDF label {label}: {path}")
            selected[label] = path
            continue

        matching = [(path, digest) for path, z, digest in existing if z == expected_z]
        by_hash: dict[str, Path] = {}
        for path, digest in matching:
            by_hash.setdefault(digest, path)
        if not by_hash:
            raise ValueError(f"no PSML source for FDF label {label} with Z={expected_z}")
        if len(by_hash) != 1:
            raise ValueError(f"ambiguous PSML sources for FDF label {label} with Z={expected_z}; provide {label}.psml")
        selected[label] = next(iter(by_hash.values()))
    return selected


def resolve_explicit_psmls(species: dict[str, int], mappings: list[tuple[str, Path]]) -> dict[str, Path]:
    selected: dict[str, Path] = {}
    for label, path in mappings:
        if label not in species:
            raise ValueError(f"explicit PSML mapping label is absent from FDF: {label}")
        if label in selected:
            raise ValueError(f"duplicate explicit PSML mapping for FDF label {label}")
        actual_z = pseudo_atomic_number(path)
        if actual_z != species[label]:
            raise ValueError(f"PSML has Z={actual_z}, expected Z={species[label]} for FDF label {label}: {path}")
        selected[label] = path
    missing = sorted(set(species) - set(selected))
    extra = sorted(set(selected) - set(species))
    if missing or extra:
        details = []
        if missing:
            details.append("missing labels: " + ", ".join(missing))
        if extra:
            details.append("unexpected labels: " + ", ".join(extra))
        raise ValueError("explicit PSML mappings must cover every FDF species (" + "; ".join(details) + ")")
    return selected
