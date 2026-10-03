"""Audited, read-only parser for the FDF subset used by perturbation planning.

Coordinates are normalized to fractional cell coordinates at this boundary so
the pure inventory and later geometry code never has to guess input units.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from fractions import Fraction
from pathlib import Path
from typing import cast

from hubbardflow.siesta_backend.fdf_includes import FdfIncludeError, resolve_fdf_includes
from hubbardflow.siesta_backend.fdf_labels import MANAGED_FDF_LABELS, canonical_fdf_label

_BOHR_TO_ANGSTROM = 0.529177210903


class FdfErrorCode(str, Enum):
    """Stable outcomes for syntax and evidence that the parser cannot accept."""

    UNSUPPORTED_SYNTAX = "UNSUPPORTED_SYNTAX"
    NONCANONICAL_MANAGED_LABEL = "NONCANONICAL_MANAGED_LABEL"
    AMBIGUOUS_DFTU_LABEL = "AMBIGUOUS_DFTU_LABEL"
    DFTU_LABEL_MULTIPLE_ATOMS = "DFTU_LABEL_MULTIPLE_ATOMS"
    DFTU_LABEL_NO_ATOM = "DFTU_LABEL_NO_ATOM"
    SPECIES_IDENTITY_NOT_ESTABLISHED = "SPECIES_IDENTITY_NOT_ESTABLISHED"
    NONCOLLINEAR_OR_SOC_NOT_SUPPORTED = "NONCOLLINEAR_OR_SOC_NOT_SUPPORTED"
    INVALID_FDF = "INVALID_FDF"


class FdfModelError(ValueError):
    """Raised when an FDF falls outside the explicitly supported subset."""

    def __init__(self, code: FdfErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code


class CoordinateFormat(str, Enum):
    """Supported coordinate encodings, as declared in the source FDF."""

    FRACTIONAL = "Fractional"
    ANG = "Ang"
    BOHR = "Bohr"
    SCALED_CARTESIAN = "ScaledCartesian"


@dataclass(frozen=True)
class SpeciesLabel:
    species_index: int
    atomic_number: int
    label: str


@dataclass(frozen=True)
class AtomicSite:
    """One coordinate row with its normalized coordinate and source label."""

    atom_index: int
    species_index: int
    species_label: str
    coordinates_fractional: tuple[float, float, float]
    source_coordinates: tuple[float, float, float]
    source_coordinate_tokens: tuple[str, str, str]
    coordinates_fractional_rational: tuple[str, str, str] | None
    coordinate_format: CoordinateFormat
    trailing_label: str | None


@dataclass(frozen=True)
class DftuRecord:
    """One SIESTA four-line DFTU.Proj record, retaining its declared header."""

    label: str
    projector_header_value: str
    n: int
    l: int
    u_ref_ev: float
    j_ref_ev: float
    rc_bohr: float
    omega: float
    lambda_values: tuple[float, ...]
    canonical_text: str


@dataclass(frozen=True)
class FdfModel:
    effective_fdf_sha256: str
    effective_text: str
    block_sha256: tuple[tuple[str, str], ...]
    lattice_constant_angstrom: float
    lattice_vectors_angstrom: tuple[tuple[float, float, float], ...]
    number_of_atoms: int
    number_of_species: int
    chemical_species_labels: tuple[SpeciesLabel, ...]
    coordinate_format: CoordinateFormat
    atoms: tuple[AtomicSite, ...]
    dftu_records: tuple[DftuRecord, ...]
    # Canonical DFTU method, from DFTU.Method or the legacy SIESTA
    # DFTU.ProjectorGenerationMethod spelling. Later F4 logic reads this field.
    dftu_method: int | None
    dftu_potential_shift: bool | None
    spin: str | None
    spin_polarized: bool
    noncollinear: bool
    spin_orbit: bool
    dm_init_spin: tuple[str, ...]
    mesh_cutoff: str | None
    kgrid_block: tuple[str, ...]
    kgrid_cutoff: str | None
    pao_basis_blocks: tuple[tuple[str, tuple[str, ...]], ...]
    pao_basis_size: str | None
    pao_basis_type: str | None

    @property
    def species_by_index(self) -> dict[int, SpeciesLabel]:
        """Return a fresh lookup table; the stored tuple remains immutable."""
        return {item.species_index: item for item in self.chemical_species_labels}


class SpeciesIdentityStatus(str, Enum):
    ESTABLISHED = "ESTABLISHED"
    NOT_ESTABLISHED = "SPECIES_IDENTITY_NOT_ESTABLISHED"


@dataclass(frozen=True)
class SpeciesIdentity:
    label: str
    atomic_number: int
    pseudopotential_sha256: str | None
    pao_basis_sha256: str | None
    ion_sha256: str | None
    digest: str
    status: SpeciesIdentityStatus


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _clean(line: str) -> tuple[str, str | None]:
    body, marker, comment = line.partition("#")
    return body.strip(), comment.strip() if marker and comment.strip() else None


def _directives(text: str, key: str) -> list[str]:
    return [
        value
        for label, value in _directive_rows(text)
        if canonical_fdf_label(label) == canonical_fdf_label(key)
    ]


def _directive_rows(text: str) -> list[tuple[str, str]]:
    """Read only top-level labels; block payload is scientific data, not directives."""
    rows: list[tuple[str, str]] = []
    active = False
    for raw in text.splitlines():
        line, _ = _clean(raw)
        if re.match(r"%block\s", line, re.IGNORECASE):
            active = True
        elif re.match(r"%endblock(?:\s|$)", line, re.IGNORECASE):
            active = False
        elif not active and line and not line.startswith("%"):
            fields = line.split(maxsplit=1)
            rows.append((fields[0], fields[1] if len(fields) > 1 else ""))
    return rows


def _validate_labels(text: str) -> None:
    """Reject ambiguous canonical identities before checking writer spellings.

    A spelling alias is recognized, but must not reach punctuation-sensitive
    writers. Separate whole-input passes make duplicate precedence independent
    of declaration order.
    """
    directives = _directive_rows(text)
    block_names: list[str] = []
    end_names: list[str] = []
    for raw in text.splitlines():
        line, _ = _clean(raw)
        start = re.fullmatch(r"%block\s+(\S+)", line, re.IGNORECASE)
        end = re.fullmatch(r"%endblock\s+(\S+)", line, re.IGNORECASE)
        if start:
            block_names.append(start.group(1))
        elif end:
            end_names.append(end.group(1))
    for kind, labels in (("directive", [label for label, _ in directives]), ("block", block_names)):
        seen: set[str] = set()
        for label in labels:
            key = canonical_fdf_label(label)
            if key in seen:
                raise FdfModelError(FdfErrorCode.UNSUPPORTED_SYNTAX, f"duplicate FDF {kind} {key}")
            seen.add(key)
    managed = {canonical_fdf_label(label): label for label in MANAGED_FDF_LABELS}
    for label in sorted([label for label, _ in directives] + block_names + end_names):
        expected = managed.get(canonical_fdf_label(label))
        if expected is not None and label.casefold() != expected.casefold():
            raise FdfModelError(
                FdfErrorCode.NONCANONICAL_MANAGED_LABEL,
                f"noncanonical managed FDF label {label!r}; use {expected}",
            )


def _one(text: str, key: str, *, required: bool = False) -> str | None:
    values = _directives(text, key)
    if len(values) > 1:
        raise FdfModelError(FdfErrorCode.UNSUPPORTED_SYNTAX, f"duplicate FDF directive {key}")
    if required and not values:
        raise FdfModelError(FdfErrorCode.UNSUPPORTED_SYNTAX, f"required FDF directive {key} is missing")
    return values[0] if values else None


def _blocks(text: str) -> dict[str, tuple[str, ...]]:
    result: dict[str, tuple[str, ...]] = {}
    active_name: str | None = None
    active_lines: list[str] = []
    for raw in text.splitlines():
        line, _ = _clean(raw)
        start = re.fullmatch(r"%block\s+(.+?)\s*", line, re.IGNORECASE)
        end = re.fullmatch(r"%endblock(?:\s+(.+?))?\s*", line, re.IGNORECASE)
        if start:
            if active_name is not None:
                raise FdfModelError(FdfErrorCode.UNSUPPORTED_SYNTAX, "nested FDF blocks are unsupported")
            active_name = canonical_fdf_label(start.group(1))
            if active_name in result:
                raise FdfModelError(FdfErrorCode.UNSUPPORTED_SYNTAX, f"duplicate FDF block {active_name}")
            active_lines = []
            continue
        if end:
            if active_name is None:
                raise FdfModelError(FdfErrorCode.UNSUPPORTED_SYNTAX, "FDF block end without a block start")
            if end.group(1) is not None and canonical_fdf_label(end.group(1)) != active_name:
                raise FdfModelError(
                    FdfErrorCode.UNSUPPORTED_SYNTAX, f"mismatched end of FDF block {active_name}"
                )
            result[active_name] = tuple(active_lines)
            active_name = None
            continue
        if active_name is not None and line:
            active_lines.append(line)
    if active_name is not None:
        raise FdfModelError(FdfErrorCode.UNSUPPORTED_SYNTAX, f"unterminated FDF block {active_name}")
    return result


def _block_rows_with_comments(text: str, name: str) -> tuple[tuple[str, str | None], ...]:
    active = False
    rows: list[tuple[str, str | None]] = []
    for raw in text.splitlines():
        body, comment = _clean(raw)
        start = re.fullmatch(r"%block\s+(\S+)", body, re.IGNORECASE)
        end = re.fullmatch(r"%endblock(?:\s+(\S+))?", body, re.IGNORECASE)
        if start and canonical_fdf_label(start.group(1)) == canonical_fdf_label(name):
            active = True
            continue
        if (
            active
            and end
            and (end.group(1) is None or canonical_fdf_label(end.group(1)) == canonical_fdf_label(name))
        ):
            return tuple(rows)
        if active and body:
            rows.append((body, comment))
    return tuple(rows)


def _number(value: str, description: str) -> float:
    try:
        result = float(value.replace("D", "E").replace("d", "e"))
    except ValueError as exc:
        raise FdfModelError(FdfErrorCode.UNSUPPORTED_SYNTAX, f"{description} is not numeric") from exc
    if not math.isfinite(result):
        raise FdfModelError(FdfErrorCode.UNSUPPORTED_SYNTAX, f"{description} must be finite")
    return result


def _float_rows(rows: Iterable[str], count: int, description: str) -> tuple[tuple[float, ...], ...]:
    parsed: list[tuple[float, ...]] = []
    for row in rows:
        values = tuple(_number(value, description) for value in row.split())
        if len(values) != count:
            raise FdfModelError(
                FdfErrorCode.UNSUPPORTED_SYNTAX, f"{description} must have {count} values per row"
            )
        parsed.append(values)
    return tuple(parsed)


def _to_fractional(
    coordinate: tuple[float, float, float],
    fmt: CoordinateFormat,
    lattice_constant: float,
    lattice_vectors: tuple[tuple[float, float, float], ...],
) -> tuple[float, float, float]:
    if fmt is CoordinateFormat.FRACTIONAL:
        return coordinate
    scale = _BOHR_TO_ANGSTROM if fmt is CoordinateFormat.BOHR else 1.0
    if fmt is CoordinateFormat.SCALED_CARTESIAN:
        scale = lattice_constant
    cart = tuple(value * scale for value in coordinate)
    # The three lattice vectors are stored as rows; solve V^T f = r.
    a, b, c = lattice_vectors
    matrix = (
        (a[0], b[0], c[0]),
        (a[1], b[1], c[1]),
        (a[2], b[2], c[2]),
    )
    det = (
        matrix[0][0] * (matrix[1][1] * matrix[2][2] - matrix[1][2] * matrix[2][1])
        - matrix[0][1] * (matrix[1][0] * matrix[2][2] - matrix[1][2] * matrix[2][0])
        + matrix[0][2] * (matrix[1][0] * matrix[2][1] - matrix[1][1] * matrix[2][0])
    )
    if det == 0.0:
        raise FdfModelError(FdfErrorCode.UNSUPPORTED_SYNTAX, "lattice vectors are singular")
    inv = (
        (
            (matrix[1][1] * matrix[2][2] - matrix[1][2] * matrix[2][1]) / det,
            (matrix[0][2] * matrix[2][1] - matrix[0][1] * matrix[2][2]) / det,
            (matrix[0][1] * matrix[1][2] - matrix[0][2] * matrix[1][1]) / det,
        ),
        (
            (matrix[1][2] * matrix[2][0] - matrix[1][0] * matrix[2][2]) / det,
            (matrix[0][0] * matrix[2][2] - matrix[0][2] * matrix[2][0]) / det,
            (matrix[0][2] * matrix[1][0] - matrix[0][0] * matrix[1][2]) / det,
        ),
        (
            (matrix[1][0] * matrix[2][1] - matrix[1][1] * matrix[2][0]) / det,
            (matrix[0][1] * matrix[2][0] - matrix[0][0] * matrix[2][1]) / det,
            (matrix[0][0] * matrix[1][1] - matrix[0][1] * matrix[1][0]) / det,
        ),
    )
    return (
        sum(inv[0][col] * cart[col] for col in range(3)),
        sum(inv[1][col] * cart[col] for col in range(3)),
        sum(inv[2][col] * cart[col] for col in range(3)),
    )


def _fraction(value: str) -> Fraction:
    try:
        return Fraction(value.replace("D", "E").replace("d", "e"))
    except (ValueError, ZeroDivisionError) as exc:
        raise FdfModelError(
            FdfErrorCode.UNSUPPORTED_SYNTAX, "coordinate token is not an exact decimal"
        ) from exc


def _rational_coordinates(
    tokens: tuple[str, str, str],
    fmt: CoordinateFormat,
    lattice_tokens: tuple[tuple[str, str, str], ...],
    lattice_constant_token: str,
    lattice_unit: str,
) -> tuple[str, str, str] | None:
    """Derive exact fractional coordinates only when decimal units are compatible."""
    coordinate = tuple(_fraction(token) for token in tokens)
    if fmt is CoordinateFormat.FRACTIONAL:
        return cast(tuple[str, str, str], tuple(str(value) for value in coordinate))
    if fmt is CoordinateFormat.SCALED_CARTESIAN:
        cart = coordinate
    elif (fmt is CoordinateFormat.ANG and lattice_unit in {"ang", "angstrom", "angstroms"}) or (
        fmt is CoordinateFormat.BOHR and lattice_unit in {"bohr", "bohrs"}
    ):
        cart = tuple(value / _fraction(lattice_constant_token) for value in coordinate)
    else:
        return None

    rows = tuple(tuple(_fraction(value) for value in row) for row in lattice_tokens)
    matrix = tuple(tuple(rows[column][row] for column in range(3)) for row in range(3))
    a, b, c = matrix
    determinant = (
        a[0] * (b[1] * c[2] - b[2] * c[1])
        - a[1] * (b[0] * c[2] - b[2] * c[0])
        + a[2] * (b[0] * c[1] - b[1] * c[0])
    )
    if determinant == 0:
        raise FdfModelError(FdfErrorCode.UNSUPPORTED_SYNTAX, "lattice vectors are singular")
    inverse = (
        (
            (b[1] * c[2] - b[2] * c[1]) / determinant,
            (a[2] * c[1] - a[1] * c[2]) / determinant,
            (a[1] * b[2] - a[2] * b[1]) / determinant,
        ),
        (
            (b[2] * c[0] - b[0] * c[2]) / determinant,
            (a[0] * c[2] - a[2] * c[0]) / determinant,
            (a[2] * b[0] - a[0] * b[2]) / determinant,
        ),
        (
            (b[0] * c[1] - b[1] * c[0]) / determinant,
            (a[1] * c[0] - a[0] * c[1]) / determinant,
            (a[0] * b[1] - a[1] * b[0]) / determinant,
        ),
    )
    return cast(
        tuple[str, str, str], tuple(str(sum(inverse[i][j] * cart[j] for j in range(3))) for i in range(3))
    )


def parse_effective_fdf(path: str | Path) -> FdfModel:
    """Parse one effective FDF, recording exact source normalization and digests.

    `%include` expansion is delegated to the shared SIESTA resolver so include
    semantics remain identical. LatticeParameters and unrecognized coordinate
    formats are rejected because interpreting them would add an unaudited
    geometry conversion.
    """
    source = Path(path)
    try:
        effective, _ = resolve_fdf_includes(source)
    except (OSError, UnicodeError, FdfIncludeError) as exc:
        raise FdfModelError(
            FdfErrorCode.UNSUPPORTED_SYNTAX, f"could not resolve effective FDF: {exc}"
        ) from exc
    _validate_labels(effective)
    if _directives(effective, "LatticeParameters"):
        raise FdfModelError(
            FdfErrorCode.UNSUPPORTED_SYNTAX,
            "LatticeParameters is unsupported; use LatticeConstant and LatticeVectors",
        )
    blocks = _blocks(effective)
    if canonical_fdf_label("LatticeParameters") in blocks:
        raise FdfModelError(
            FdfErrorCode.UNSUPPORTED_SYNTAX,
            "LatticeParameters is unsupported; use LatticeConstant and LatticeVectors",
        )
    lattice_value = _one(effective, "LatticeConstant", required=True)
    assert lattice_value is not None
    lattice_fields = lattice_value.split()
    if len(lattice_fields) != 2:
        raise FdfModelError(
            FdfErrorCode.UNSUPPORTED_SYNTAX, "LatticeConstant must contain a value and Ang/Bohr unit"
        )
    lattice_constant = _number(lattice_fields[0], "LatticeConstant")
    unit = lattice_fields[1].casefold()
    if unit in {"ang", "angstrom", "angstroms"}:
        pass
    elif unit in {"bohr", "bohrs"}:
        lattice_constant *= _BOHR_TO_ANGSTROM
    else:
        raise FdfModelError(
            FdfErrorCode.UNSUPPORTED_SYNTAX, f"unsupported LatticeConstant unit {lattice_fields[1]}"
        )
    if lattice_constant <= 0:
        raise FdfModelError(FdfErrorCode.UNSUPPORTED_SYNTAX, "LatticeConstant must be positive")
    lattice_row_tokens = tuple(
        tuple(row.split()) for row in blocks.get(canonical_fdf_label("LatticeVectors"), ())
    )
    lattice_rows = _float_rows(blocks.get(canonical_fdf_label("LatticeVectors"), ()), 3, "LatticeVectors")
    if len(lattice_rows) != 3:
        raise FdfModelError(FdfErrorCode.UNSUPPORTED_SYNTAX, "LatticeVectors must contain exactly three rows")
    lattice = tuple(
        (lattice_constant * row[0], lattice_constant * row[1], lattice_constant * row[2])
        for row in lattice_rows
    )
    n_atoms_text = _one(effective, "NumberOfAtoms", required=True)
    n_species_text = _one(effective, "NumberOfSpecies", required=True)
    assert n_atoms_text is not None and n_species_text is not None
    try:
        number_atoms, number_species = int(n_atoms_text), int(n_species_text)
    except ValueError as exc:
        raise FdfModelError(
            FdfErrorCode.UNSUPPORTED_SYNTAX, "NumberOfAtoms/NumberOfSpecies must be integers"
        ) from exc
    if number_atoms <= 0 or number_species <= 0:
        raise FdfModelError(FdfErrorCode.UNSUPPORTED_SYNTAX, "NumberOfAtoms/NumberOfSpecies must be positive")
    species: list[SpeciesLabel] = []
    seen_species_indices: set[int] = set()
    seen_labels: set[str] = set()
    for row in blocks.get(canonical_fdf_label("ChemicalSpeciesLabel"), ()):
        fields = row.split()
        if len(fields) != 3:
            raise FdfModelError(
                FdfErrorCode.UNSUPPORTED_SYNTAX, "ChemicalSpeciesLabel rows require index, Z and label"
            )
        try:
            species_index, atomic_number = int(fields[0]), int(fields[1])
        except ValueError as exc:
            raise FdfModelError(
                FdfErrorCode.UNSUPPORTED_SYNTAX, "ChemicalSpeciesLabel index and Z must be integers"
            ) from exc
        if (
            species_index <= 0
            or atomic_number <= 0
            or species_index in seen_species_indices
            or fields[2] in seen_labels
        ):
            raise FdfModelError(
                FdfErrorCode.UNSUPPORTED_SYNTAX,
                "ChemicalSpeciesLabel contains duplicate or nonpositive values",
            )
        species.append(SpeciesLabel(species_index, atomic_number, fields[2]))
        seen_species_indices.add(species_index)
        seen_labels.add(fields[2])
    if len(species) != number_species:
        raise FdfModelError(
            FdfErrorCode.UNSUPPORTED_SYNTAX, "ChemicalSpeciesLabel count differs from NumberOfSpecies"
        )
    species_by_index = {entry.species_index: entry for entry in species}
    fmt_text = _one(effective, "AtomicCoordinatesFormat", required=True)
    assert fmt_text is not None
    format_map = {item.value.casefold(): item for item in CoordinateFormat}
    fmt = format_map.get(fmt_text.casefold())
    if fmt is None:
        raise FdfModelError(
            FdfErrorCode.UNSUPPORTED_SYNTAX, f"unsupported AtomicCoordinatesFormat {fmt_text}"
        )
    atoms: list[AtomicSite] = []
    atom_rows = _block_rows_with_comments(effective, "AtomicCoordinatesAndAtomicSpecies")
    for atom_index, (row, comment) in enumerate(atom_rows):
        fields = row.split()
        if len(fields) < 4:
            raise FdfModelError(
                FdfErrorCode.UNSUPPORTED_SYNTAX, "AtomicCoordinatesAndAtomicSpecies row is incomplete"
            )
        source_coord = (
            _number(fields[0], "atomic coordinate"),
            _number(fields[1], "atomic coordinate"),
            _number(fields[2], "atomic coordinate"),
        )
        source_coordinate_tokens = (fields[0], fields[1], fields[2])
        try:
            species_index = int(fields[3])
        except ValueError as exc:
            raise FdfModelError(
                FdfErrorCode.UNSUPPORTED_SYNTAX, "atomic species index must be an integer"
            ) from exc
        if species_index not in species_by_index:
            raise FdfModelError(
                FdfErrorCode.UNSUPPORTED_SYNTAX, "atomic coordinate references an unknown species index"
            )
        trailing = " ".join(fields[4:]) or comment
        rational_coordinates = _rational_coordinates(
            source_coordinate_tokens,
            fmt,
            cast(tuple[tuple[str, str, str], ...], lattice_row_tokens),
            lattice_fields[0],
            unit,
        )
        fractional = _to_fractional(source_coord, fmt, lattice_constant, lattice)
        atoms.append(
            AtomicSite(
                atom_index,
                species_index,
                species_by_index[species_index].label,
                fractional,
                source_coord,
                source_coordinate_tokens,
                rational_coordinates,
                fmt,
                trailing,
            )
        )
    if len(atoms) != number_atoms:
        raise FdfModelError(
            FdfErrorCode.UNSUPPORTED_SYNTAX, "coordinate row count differs from NumberOfAtoms"
        )
    dftu_rows = blocks.get(canonical_fdf_label("DFTU.proj"), ())
    if len(dftu_rows) % 4:
        raise FdfModelError(
            FdfErrorCode.UNSUPPORTED_SYNTAX, "DFTU.Proj must contain complete four-line records"
        )
    dftu: list[DftuRecord] = []
    seen_dftu: set[str] = set()
    for offset in range(0, len(dftu_rows), 4):
        rows = dftu_rows[offset : offset + 4]
        head, shell, values, radial = (item.split() for item in rows)
        if len(head) != 2 or len(shell) != 2 or len(values) < 2 or len(radial) < 2:
            raise FdfModelError(FdfErrorCode.UNSUPPORTED_SYNTAX, "DFTU.Proj record shape is unsupported")
        label = head[0]
        if label in seen_dftu:
            raise FdfModelError(
                FdfErrorCode.AMBIGUOUS_DFTU_LABEL, f"DFTU.Proj declares label {label} more than once"
            )
        try:
            n, angular_momentum = int(shell[0]), int(shell[1])
        except ValueError as exc:
            raise FdfModelError(FdfErrorCode.UNSUPPORTED_SYNTAX, f"invalid DFTU shell for {label}") from exc
        valnums = tuple(_number(value, f"DFTU.Proj values for {label}") for value in values)
        radialnums = tuple(_number(value, f"DFTU.Proj radial values for {label}") for value in radial)
        dftu.append(
            DftuRecord(
                label,
                head[1],
                n,
                angular_momentum,
                valnums[0],
                valnums[1],
                radialnums[0],
                radialnums[1],
                valnums[2:] + radialnums[2:],
                "\n".join(rows),
            )
        )
        seen_dftu.add(label)
    method_text = _one(effective, "DFTU.Method")
    legacy_method_text = _one(effective, "DFTU.ProjectorGenerationMethod")
    try:
        method = int(method_text) if method_text is not None else None
        legacy_method = int(legacy_method_text) if legacy_method_text is not None else None
    except ValueError as exc:
        raise FdfModelError(
            FdfErrorCode.UNSUPPORTED_SYNTAX, "DFTU method declarations must be integers"
        ) from exc
    if method is not None and legacy_method is not None and method != legacy_method:
        raise FdfModelError(
            FdfErrorCode.UNSUPPORTED_SYNTAX,
            "DFTU.Method conflicts with DFTU.ProjectorGenerationMethod",
        )
    dftu_method = method if method is not None else legacy_method
    potential = _one(effective, "DFTU.PotentialShift")
    if potential is not None and potential.casefold() not in {"true", "t", "false", "f"}:
        raise FdfModelError(FdfErrorCode.UNSUPPORTED_SYNTAX, "DFTU.PotentialShift must be boolean")
    spin = _one(effective, "Spin")
    spin_polarized_text = _one(effective, "SpinPolarized")
    spin_choices = {
        "unpolarized": "unpolarized",
        "non-polarized": "unpolarized",
        "nonpolarized": "unpolarized",
        "polarized": "polarized",
        "collinear": "polarized",
        "noncollinear": "noncollinear",
        "non-collinear": "noncollinear",
    }
    spin_choice = None if spin is None else spin_choices.get(spin.casefold())
    if spin is not None and spin_choice is None:
        raise FdfModelError(FdfErrorCode.UNSUPPORTED_SYNTAX, f"unsupported Spin value {spin!r}")

    def parse_bool_directive(value: str | None, key: str) -> bool | None:
        if value is None:
            return None
        normalized = value.casefold()
        if normalized in {"true", "t"}:
            return True
        if normalized in {"false", "f"}:
            return False
        raise FdfModelError(FdfErrorCode.UNSUPPORTED_SYNTAX, f"{key} must be true/false or T/F")

    spin_polarized_declared = parse_bool_directive(spin_polarized_text, "SpinPolarized")
    spin_polarized_from_spin = spin_choice in {"polarized", "noncollinear"}
    if (
        spin_polarized_declared is not None
        and spin is not None
        and spin_polarized_declared != spin_polarized_from_spin
    ):
        raise FdfModelError(FdfErrorCode.UNSUPPORTED_SYNTAX, "Spin and SpinPolarized declarations conflict")
    spin_polarized = (
        spin_polarized_declared if spin_polarized_declared is not None else spin_polarized_from_spin
    )
    noncollinear_flag = parse_bool_directive(_one(effective, "NonCollinearSpin"), "NonCollinearSpin")
    noncollinear = spin_choice == "noncollinear" or noncollinear_flag is True
    spin_orbit = parse_bool_directive(_one(effective, "SpinOrbit"), "SpinOrbit") is True
    relevant_names = {
        "chemicalspecieslabel",
        "latticevectors",
        "atomiccoordinatesandatomicspecies",
        "dftu.proj",
        "dm.initspin",
        "kgrid_monkhorst_pack",
        "pao.basis",
    }
    block_hashes = tuple(
        sorted(
            (name, _sha256_text("\n".join(blocks[canonical_fdf_label(name)])))
            for name in relevant_names
            if canonical_fdf_label(name) in blocks
        )
    )
    basis_rows: list[tuple[str, tuple[str, ...]]] = []
    basis_lines = blocks.get(canonical_fdf_label("PAO.Basis"), ())
    species_labels = {entry.label for entry in species}
    current_label: str | None = None
    current_basis: list[str] = []
    for row in basis_lines:
        first = row.split()[0]
        if first in species_labels:
            if current_label is not None:
                basis_rows.append((current_label, tuple(current_basis)))
            current_label, current_basis = first, []
        elif current_label is None:
            raise FdfModelError(
                FdfErrorCode.UNSUPPORTED_SYNTAX,
                "PAO.Basis data must be grouped under a declared species label",
            )
        else:
            current_basis.append(row)
    if current_label is not None:
        basis_rows.append((current_label, tuple(current_basis)))
    return FdfModel(
        effective_fdf_sha256=_sha256_text(effective),
        effective_text=effective,
        block_sha256=block_hashes,
        lattice_constant_angstrom=lattice_constant,
        lattice_vectors_angstrom=lattice,
        number_of_atoms=number_atoms,
        number_of_species=number_species,
        chemical_species_labels=tuple(species),
        coordinate_format=fmt,
        atoms=tuple(atoms),
        dftu_records=tuple(dftu),
        dftu_method=dftu_method,
        dftu_potential_shift=None if potential is None else potential.casefold() in {"true", "t"},
        spin=spin,
        spin_polarized=spin_polarized,
        noncollinear=noncollinear,
        spin_orbit=spin_orbit,
        dm_init_spin=blocks.get(canonical_fdf_label("DM.InitSpin"), ()),
        mesh_cutoff=_one(effective, "MeshCutoff"),
        kgrid_block=blocks.get(canonical_fdf_label("kgrid_Monkhorst_Pack"), ()),
        kgrid_cutoff=_one(effective, "kgrid_cutoff"),
        pao_basis_blocks=tuple(sorted(basis_rows)),
        pao_basis_size=_one(effective, "PAO.BasisSize"),
        pao_basis_type=_one(effective, "PAO.BasisType"),
    )


def species_identity(model: FdfModel, search_dirs: Iterable[str | Path]) -> dict[str, SpeciesIdentity]:
    """Hash label-specific pseudopotential, basis and optional generated ion.

    A missing pseudopotential keeps the identity digest explicit but marks it
    not established, so a caller cannot use absence as evidence of equivalence.
    """
    directories = tuple(Path(directory) for directory in search_dirs)
    basis_by_label = dict(model.pao_basis_blocks)
    result: dict[str, SpeciesIdentity] = {}
    for species in sorted(model.chemical_species_labels, key=lambda value: value.label):
        pseudo: Path | None = None
        for suffix in (".psml", ".psf", ".vps"):
            pseudo = next(
                (
                    directory / f"{species.label}{suffix}"
                    for directory in directories
                    if (directory / f"{species.label}{suffix}").is_file()
                ),
                None,
            )
            if pseudo is not None:
                break
        ion = next(
            (
                directory / f"{species.label}.ion"
                for directory in directories
                if (directory / f"{species.label}.ion").is_file()
            ),
            None,
        )
        has_basis = species.label in basis_by_label
        basis_text = "\n".join(basis_by_label.get(species.label, ()))
        basis_digest = _sha256_text(basis_text) if has_basis else None
        pseudo_digest = hashlib.sha256(pseudo.read_bytes()).hexdigest() if pseudo is not None else None
        ion_digest = hashlib.sha256(ion.read_bytes()).hexdigest() if ion is not None else None
        identity_payload = "\n".join(
            (
                str(species.atomic_number),
                pseudo_digest or "MISSING",
                basis_digest or "PAO_BASIS_NOT_DECLARED",
                ion_digest or "ABSENT",
            )
        )
        result[species.label] = SpeciesIdentity(
            species.label,
            species.atomic_number,
            pseudo_digest,
            basis_digest,
            ion_digest,
            _sha256_text(identity_payload),
            SpeciesIdentityStatus.ESTABLISHED
            if pseudo_digest is not None and basis_digest is not None
            else SpeciesIdentityStatus.NOT_ESTABLISHED,
        )
    return result
