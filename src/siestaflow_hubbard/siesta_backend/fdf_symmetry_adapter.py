"""Fail-closed bridge from a SIESTA FDF to the conservative symmetry detector.

This module deliberately separates a site identifier (for example ``MnLR03``)
from its physical equivalence class.  Campaign FDFs commonly assign a unique
chemical-species label to every Hubbard site so that each can be perturbed;
that naming convention is *not* physical symmetry breaking.

No magnetic symmetry is inferred from ``DM.InitSpin``.  A caller must provide
an accepted-reference magnetic-evidence JSON, bound to the exact FDF hash and
containing one three-component moment for every atom.  Without it the adapter
reports only geometric candidates and disables reduction.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any

import numpy as np

from symmetry_reduction_proposal import SymmetryCertificate, detect_symmetry
from siestaflow_hubbard.domain.symmetry_reduction import (
    SymmetryReductionPlan,
    SymmetryReductionPolicy,
    build_symmetry_reduction_plan,
)


_BOHR_TO_ANGSTROM = 0.529177210903


class FdfSymmetryError(ValueError):
    """Raised when the narrow, auditable FDF subset cannot be interpreted."""


@dataclass(frozen=True)
class FdfSymmetryInput:
    fdf_sha256: str
    lattice_angstrom: tuple[tuple[float, float, float], ...]
    fractional_coordinates: tuple[tuple[float, float, float], ...]
    atom_ids: tuple[str, ...]
    physical_species: tuple[str, ...]
    equivalence_classes: tuple[str, ...]
    subspaces: tuple[dict[str, Any], ...]
    projectors: tuple[dict[str, Any], ...]
    correlated_atom_ids: tuple[str, ...]


@dataclass(frozen=True)
class FdfSymmetryAudit:
    input: FdfSymmetryInput
    geometric_candidate_count: int
    reduction_enabled: bool
    reasons: tuple[str, ...]
    certificate: SymmetryCertificate | None = None


def _clean_lines(text: str) -> list[str]:
    return [line.split("#", 1)[0].strip() for line in text.splitlines()]


def _block(lines: list[str], name: str) -> list[str]:
    start = f"%block {name}".lower()
    end = f"%endblock {name}".lower()
    inside = False
    values: list[str] = []
    for line in lines:
        lowered = line.lower()
        if lowered == start:
            if inside:
                raise FdfSymmetryError(f"Bloque FDF duplicado: {name}")
            inside = True
            continue
        if lowered == end:
            if not inside:
                raise FdfSymmetryError(f"Fin de bloque sin inicio: {name}")
            return values
        if inside and line:
            values.append(line)
    raise FdfSymmetryError(f"Bloque FDF ausente o sin cierre: {name}")


def _scalar(lines: list[str], key: str) -> list[str]:
    pattern = re.compile(rf"^\s*{re.escape(key)}\s+(.+?)\s*$", re.IGNORECASE)
    matches = [match.group(1) for line in lines if (match := pattern.match(line))]
    if len(matches) != 1:
        raise FdfSymmetryError(f"Se requiere exactamente una directiva {key}")
    return matches[0].split()


def _lattice_scale(lines: list[str]) -> float:
    values = _scalar(lines, "LatticeConstant")
    if len(values) != 2:
        raise FdfSymmetryError("LatticeConstant debe declarar valor y unidad")
    try:
        magnitude = float(values[0])
    except ValueError as exc:
        raise FdfSymmetryError("LatticeConstant no numérico") from exc
    unit = values[1].lower()
    if unit in {"ang", "angstrom", "angstroms"}:
        return magnitude
    if unit in {"bohr", "bohrs"}:
        return magnitude * _BOHR_TO_ANGSTROM
    raise FdfSymmetryError(f"Unidad LatticeConstant no admitida: {values[1]}")


def _parse_dftu(lines: list[str]) -> dict[str, dict[str, Any]]:
    entries = _block(lines, "DFTU.Proj")
    if len(entries) % 4:
        raise FdfSymmetryError("DFTU.Proj debe contener grupos de cuatro líneas")
    result: dict[str, dict[str, Any]] = {}
    for offset in range(0, len(entries), 4):
        header, shell, shift, radial = entries[offset:offset + 4]
        header_fields, shell_fields = header.split(), shell.split()
        radial_fields = radial.split()
        if len(header_fields) != 2 or len(shell_fields) != 2 or len(radial_fields) != 2:
            raise FdfSymmetryError("Entrada DFTU.Proj incompleta")
        label = header_fields[0]
        try:
            result[label] = {
                "n": int(shell_fields[0]),
                "l": int(shell_fields[1]),
                "u_j_line": tuple(float(value) for value in shift.split()),
                "rc_bohr": float(radial_fields[0]),
                "omega": float(radial_fields[1]),
            }
        except ValueError as exc:
            raise FdfSymmetryError(f"Entrada DFTU.Proj no numérica para {label}") from exc
    if len(result) != len(entries) // 4:
        raise FdfSymmetryError("Etiquetas DFTU.Proj duplicadas")
    return result


def parse_fdf_symmetry_input(fdf_path: str | Path) -> FdfSymmetryInput:
    """Parse the FDF fields needed for a symmetry *pre-audit*.

    The parser intentionally supports only explicit lattice vectors, fractional
    coordinates, ChemicalSpeciesLabel and DFTU.Proj.  An unfamiliar geometry
    form must be rejected rather than silently transformed.
    """
    path = Path(fdf_path)
    raw = path.read_bytes()
    lines = _clean_lines(raw.decode("utf-8"))
    coordinate_format = " ".join(_scalar(lines, "AtomicCoordinatesFormat")).lower()
    if coordinate_format != "fractional":
        raise FdfSymmetryError("Sólo AtomicCoordinatesFormat Fractional es auditable actualmente")

    scale = _lattice_scale(lines)
    vectors = _block(lines, "LatticeVectors")
    if len(vectors) != 3:
        raise FdfSymmetryError("LatticeVectors debe tener tres filas")
    try:
        lattice = tuple(tuple(scale * float(value) for value in line.split()) for line in vectors)
    except ValueError as exc:
        raise FdfSymmetryError("LatticeVectors no numérico") from exc
    if any(len(row) != 3 for row in lattice):
        raise FdfSymmetryError("LatticeVectors debe ser 3x3")

    species_map: dict[int, tuple[int, str]] = {}
    for line in _block(lines, "ChemicalSpeciesLabel"):
        fields = line.split()
        if len(fields) != 3:
            raise FdfSymmetryError("ChemicalSpeciesLabel inválido")
        try:
            index, atomic_number = int(fields[0]), int(fields[1])
        except ValueError as exc:
            raise FdfSymmetryError("ChemicalSpeciesLabel no numérico") from exc
        if index in species_map:
            raise FdfSymmetryError("Índice ChemicalSpeciesLabel duplicado")
        species_map[index] = (atomic_number, fields[2])

    dftu = _parse_dftu(lines)
    coordinates: list[tuple[float, float, float]] = []
    atom_ids: list[str] = []
    physical_species: list[str] = []
    classes: list[str] = []
    subspaces: list[dict[str, Any]] = []
    projectors: list[dict[str, Any]] = []
    correlated: list[str] = []
    label_seen: set[str] = set()
    for atom_index, line in enumerate(_block(lines, "AtomicCoordinatesAndAtomicSpecies"), start=1):
        fields = line.split()
        if len(fields) < 4:
            raise FdfSymmetryError("AtomicCoordinatesAndAtomicSpecies inválido")
        try:
            coordinate = tuple(float(value) for value in fields[:3])
            species_index = int(fields[3])
        except ValueError as exc:
            raise FdfSymmetryError("Coordenada o especie atómica no numérica") from exc
        if species_index not in species_map or len(coordinate) != 3:
            raise FdfSymmetryError("Especie atómica no declarada")
        atomic_number, label = species_map[species_index]
        atom_id = label if label not in label_seen else f"{label}@{atom_index}"
        label_seen.add(label)
        coordinates.append(coordinate)
        atom_ids.append(atom_id)
        physical_species.append(f"Z:{atomic_number}")
        if label in dftu:
            definition = dftu[label]
            classes.append(
                "correlated:Z={}:n={}:l={}:U={:.12g}:J={:.12g}:rc={:.12g}:omega={:.12g}".format(
                    atomic_number, definition["n"], definition["l"], definition["u_j_line"][0],
                    definition["u_j_line"][1], definition["rc_bohr"], definition["omega"]
                )
            )
            # An FDF declares a shell but does not, by itself, prove that an
            # arbitrary orbital rotation preserves the measured occupation.
            subspaces.append({"kind": "correlated", **definition,
                              "complete_l_shell": False, "scalar_occupation": False})
            projectors.append({"kind": "siesta_dftu", "generation_method": "declared",
                               "rotationally_invariant": False})
            correlated.append(atom_id)
        else:
            classes.append(f"spectator:Z={atomic_number}")
            subspaces.append({"kind": "spectator", "complete_l_shell": False,
                              "scalar_occupation": False})
            projectors.append({"kind": "spectator", "rotationally_invariant": False})
    if not coordinates or not correlated:
        raise FdfSymmetryError("No se hallaron átomos o subespacios DFTU correlacionados")
    return FdfSymmetryInput(
        fdf_sha256=sha256(raw).hexdigest(), lattice_angstrom=lattice,
        fractional_coordinates=tuple(coordinates), atom_ids=tuple(atom_ids),
        physical_species=tuple(physical_species), equivalence_classes=tuple(classes),
        subspaces=tuple(subspaces), projectors=tuple(projectors),
        correlated_atom_ids=tuple(correlated),
    )


def _load_verified_moments(path: str | Path, input_data: FdfSymmetryInput) -> np.ndarray:
    """Read the minimal accepted-reference magnetic evidence contract.

    Expected JSON schema: ``schema_version=1``, exact ``input_fdf_sha256`` and
    ``moments_by_atom_index`` containing indices 1..N, each a finite 3-vector.
    This is intentionally stricter than accepting an initial-spin card.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or data.get("input_fdf_sha256") != input_data.fdf_sha256:
        raise FdfSymmetryError("La evidencia magnética no está ligada a esta FDF")
    moments = data.get("moments_by_atom_index")
    expected = {str(index) for index in range(1, len(input_data.atom_ids) + 1)}
    if not isinstance(moments, dict) or set(moments) != expected:
        raise FdfSymmetryError("La evidencia magnética debe cubrir exactamente todos los átomos")
    try:
        values = np.asarray([moments[str(index)] for index in range(1, len(expected) + 1)], dtype=float)
    except (TypeError, ValueError) as exc:
        raise FdfSymmetryError("Momentos magnéticos no numéricos") from exc
    if values.shape != (len(expected), 3) or not np.all(np.isfinite(values)):
        raise FdfSymmetryError("Momentos magnéticos incompletos o no finitos")
    return values


def audit_fdf_symmetry(fdf_path: str | Path, magnetic_evidence_path: str | Path | None = None) -> FdfSymmetryAudit:
    """Return a reduction certificate only when accepted magnetic evidence exists."""
    input_data = parse_fdf_symmetry_input(fdf_path)
    common = dict(
        lattice=input_data.lattice_angstrom,
        coordinates=input_data.fractional_coordinates,
        species=input_data.physical_species,
        labels=input_data.equivalence_classes,
        subspaces=input_data.subspaces,
        projectors=input_data.projectors,
    )
    if magnetic_evidence_path is None:
        # Zero vectors here are a geometry-only probe, never a certificate.
        candidate = detect_symmetry(moments=np.zeros((len(input_data.atom_ids), 3)), **common)
        return FdfSymmetryAudit(
            input=input_data, geometric_candidate_count=len(candidate.crystal_operations),
            reduction_enabled=False,
            reasons=("reference_magnetic_evidence_missing", "reduction_fail_closed"),
        )
    moments = _load_verified_moments(magnetic_evidence_path, input_data)
    certificate = detect_symmetry(moments=moments, **common)
    return FdfSymmetryAudit(
        input=input_data, geometric_candidate_count=len(certificate.crystal_operations),
        reduction_enabled=certificate.reduction_enabled, reasons=certificate.reasons,
        certificate=certificate,
    )


def plan_fdf_symmetry_reduction(
    fdf_path: str | Path,
    magnetic_evidence_path: str | Path | None,
    policy: SymmetryReductionPolicy,
) -> tuple[FdfSymmetryAudit, SymmetryReductionPlan]:
    """Build a backend-neutral perturbation plan from an FDF audit.

    This bridge performs no FDF mutation and does not submit a calculation.
    A missing/invalid reference magnetic evidence path produces an explicit
    plan rather than treating geometric candidates as permission to reduce.
    """
    audit = audit_fdf_symmetry(fdf_path, magnetic_evidence_path)
    return audit, build_symmetry_reduction_plan(
        audit.input.atom_ids, audit.input.correlated_atom_ids, audit.certificate, policy
    )


def audit_to_json(audit: FdfSymmetryAudit) -> str:
    """Serialize a read-only audit record without turning candidates into permission."""
    payload = asdict(audit)
    return json.dumps(payload, sort_keys=True, indent=2)
