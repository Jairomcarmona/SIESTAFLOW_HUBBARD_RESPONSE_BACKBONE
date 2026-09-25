"""Subgrupo conservador, no buscador completo de grupos espaciales.

Entrada: red en Å y coordenadas FDF ya normalizadas. No se requiere CIF.
No certifica orbitales orientados ni operaciones con inversión temporal.
"""

from dataclasses import asdict, dataclass
from hashlib import sha256
from itertools import permutations, product
import json

import numpy as np


def _digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                             allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class Operation:
    rotation: tuple
    translation: tuple
    permutation: tuple
    geometric_residual: float
    magnetic_residual: float


@dataclass(frozen=True)
class SymmetryCertificate:
    input_hash: str
    site_count: int
    crystal_operations: tuple
    magnetic_operations: tuple
    orbits: tuple
    reduction_enabled: bool
    ambiguous: bool
    reasons: tuple
    tolerance: float
    digest: str = ""

    def verify(self):
        payload = asdict(self)
        digest = payload.pop("digest")
        if digest != _digest(payload) or self.ambiguous:
            raise ValueError("Certificado alterado o ambiguo")


def detect_symmetry(lattice, coordinates, species, labels, moments,
                    subspaces, projectors, coordinate_format="fractional",
                    geometric_tolerance=1e-7, magnetic_tolerance=1e-6):
    """Preserva etiquetas de especie/clase, no permuta IDs arbitrarios.

Las definiciones se comparan exactamente. Rotaciones no triviales requieren
complete_l_shell y scalar_occupation en cada subespacio, y rotationally_invariant
en cada proyector. Los valores ausentes desactivan toda reducción.
"""
    lattice = np.asarray(lattice, dtype=float)
    positions = np.asarray(coordinates, dtype=float)
    moments = np.asarray(moments, dtype=float)
    count = len(species)
    if (lattice.shape != (3, 3) or positions.shape != (count, 3)
            or moments.shape != (count, 3) or count == 0
            or any(len(items) != count for items in (labels, subspaces, projectors))):
        raise ValueError("Dimensiones incompatibles")
    if not all(np.all(np.isfinite(array)) for array in (lattice, positions, moments)):
        raise ValueError("Geometría o magnetismo no finitos")
    if not all(np.isfinite(value) and value > 0
               for value in (geometric_tolerance, magnetic_tolerance)):
        raise ValueError("Tolerancias inválidas")
    singular_values = np.linalg.svd(lattice, compute_uv=False)
    if singular_values[-1] <= 0 or singular_values[0] / singular_values[-1] > 1e8:
        raise ValueError("Red singular o demasiado mal condicionada")
    if geometric_tolerance / singular_values[-1] >= 0.1:
        raise ValueError("Tolerancia geométrica demasiado grande para esta red")
    if coordinate_format == "cartesian_angstrom":
        positions = positions @ np.linalg.inv(lattice)
    elif coordinate_format != "fractional":
        raise ValueError("Normalizar unidades FDF antes de detectar simetrías")
    positions = positions % 1.0
    definitions = list(zip(species, labels, subspaces, projectors))
    input_hash = _digest({"lattice": lattice.tolist(), "positions": positions.tolist(),
                          "moments": moments.tolist(), "definitions": definitions,
                          "geometric_tolerance": geometric_tolerance,
                          "magnetic_tolerance": magnetic_tolerance})
    metadata_complete = all(isinstance(value, dict) and bool(value)
                            for value in (*subspaces, *projectors)) and all(species) and all(labels)
    scalar_shells = metadata_complete and all(
        subspace.get("complete_l_shell") is True
        and subspace.get("scalar_occupation") is True
        and projector.get("rotationally_invariant") is True
        for subspace, projector in zip(subspaces, projectors))
    crystal, magnetic = [], []
    ambiguous = False
    inverse_transpose = np.linalg.inv(lattice.T)
    for axis_order in permutations(range(3)):
        for signs in product((-1, 1), repeat=3):
            rotation = np.eye(3, dtype=int)[list(axis_order)] * np.array(signs)[:, None]
            cartesian_rotation = lattice.T @ rotation @ inverse_transpose
            if not np.allclose(cartesian_rotation.T @ cartesian_rotation, np.eye(3),
                               rtol=0, atol=1e-10):
                continue
            rotated = positions @ rotation.T
            for target in range(count):
                if (species[0], labels[0]) != (species[target], labels[target]):
                    continue
                translation = (positions[target] - rotated[0]) % 1.0
                mapped = rotated + translation
                site_permutation, distances = [], []
                valid = True
                for site in range(count):
                    candidates = []
                    for destination in range(count):
                        if (species[site], labels[site]) != (species[destination], labels[destination]):
                            continue
                        delta = mapped[site] - positions[destination]
                        integer_center = np.rint(delta)
                        distance = float(np.linalg.norm((delta - integer_center) @ lattice))
                        if distance <= geometric_tolerance:
                            candidates.append((destination, distance))
                    if len(candidates) > 1:
                        ambiguous = True
                    if len(candidates) != 1:
                        valid = False
                        break
                    destination, distance = candidates[0]
                    site_permutation.append(destination)
                    distances.append(distance)
                if not valid or len(set(site_permutation)) != count:
                    continue
                transformed_moments = np.linalg.det(cartesian_rotation) * moments @ cartesian_rotation.T
                magnetic_residual = float(np.max(np.linalg.norm(
                    transformed_moments - moments[site_permutation], axis=1)))
                operation = Operation(tuple(map(tuple, rotation.tolist())), tuple(translation.tolist()),
                                      tuple(site_permutation), max(distances), magnetic_residual)
                if operation in crystal:
                    continue
                crystal.append(operation)
                preserves_definitions = all(definitions[site] == definitions[destination]
                                            for site, destination in enumerate(site_permutation))
                scalar_compatible = scalar_shells or np.array_equal(rotation, np.eye(3))
                if (metadata_complete and preserves_definitions and scalar_compatible
                        and magnetic_residual <= magnetic_tolerance):
                    magnetic.append(operation)
    reasons = ["subgrupo_de_rotaciones_enteras_con_signo; sin_inversion_temporal"]
    if not metadata_complete:
        reasons.append("definiciones_incompletas")
    if not scalar_shells:
        reasons.append("rotaciones_orbitales_no_certificadas")
    if ambiguous:
        reasons.append("correspondencia_geometrica_ambigua")
    permitted = magnetic if metadata_complete and not ambiguous else []
    orbits, remaining = [], set(range(count))
    while remaining:
        orbit = {min(remaining)}
        while True:
            expanded = orbit | {operation.permutation[site]
                                for operation in permitted for site in orbit}
            if expanded == orbit:
                break
            orbit = expanded
        orbits.append(tuple(sorted(orbit)))
        remaining -= orbit
    enabled = any(len(orbit) > 1 for orbit in orbits) and not ambiguous
    certificate = SymmetryCertificate(input_hash, count, tuple(crystal), tuple(magnetic),
                                      tuple(orbits), enabled, ambiguous, tuple(reasons),
                                      geometric_tolerance)
    payload = asdict(certificate)
    payload.pop("digest")
    return SymmetryCertificate(**{**vars(certificate), "digest": _digest(payload)})