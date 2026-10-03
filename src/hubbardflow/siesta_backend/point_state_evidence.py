"""Parse run-local state evidence while retaining SIESTA's printed precision.

The occupation event is supplied by the same BARE or SCREENED selector used by
the response analysis.  This module therefore parses printed detail only; it
does not choose a population event or decide whether two states are consistent.
"""

from __future__ import annotations

import math
import re

from hubbardflow.domain.state_gate_types import (
    AtomPointState,
    BandEvidenceStatus,
    PointState,
    PrintedBandEnergy,
)
from hubbardflow.siesta_backend.parser_models import HubbardPopulationEvent


class PointStateEvidenceError(ValueError):
    """The selected event or run output lacks complete printed state evidence."""


_NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][-+]?\d+)?"
_MATRIX_ROW = re.compile(
    rf"^\s*(?P<i>[1-9]\d*)\s+(?P<j>[1-9]\d*)\s+(?P<up>{_NUMBER})\s+(?P<down>{_NUMBER})\s*$"
)
_ATOM_START = re.compile(r"^\s*hubbard_term:\s+atom,\s+species:\s+(\d+)\s+(\d+)\s*$", re.IGNORECASE)
_FERMI = re.compile(rf"^\s*siesta:\s*Fermi\s*=\s*(?P<value>{_NUMBER})\s*$", re.IGNORECASE)
_MULLIKEN_START = re.compile(r"^\s*Mulliken Atomic Populations:\s*$", re.IGNORECASE)
_MULLIKEN_HEADER = re.compile(r"^\s*Atom\s+#.*\bSz\s*\[e\].*\bSpecies\s*$", re.IGNORECASE)
_MULLIKEN_ROW = re.compile(rf"^\s*(?P<index>\d+)\s+{_NUMBER}\s+{_NUMBER}\s+(?P<sz>{_NUMBER})\s+\S+\s*$")
_EIG_NUMBER = re.compile(rf"^{_NUMBER}$")


def _normal_number(token: str) -> float:
    try:
        value = float(token.replace("D", "E").replace("d", "e"))
    except ValueError as exc:
        raise PointStateEvidenceError(f"invalid printed number {token!r}") from exc
    if not math.isfinite(value):
        raise PointStateEvidenceError(f"non-finite printed number {token!r}")
    return value


def _quantum(token: str) -> float:
    normalized = token.replace("D", "E").replace("d", "e")
    mantissa, marker, exponent_text = normalized.lower().partition("e")
    decimal_places = len(mantissa.partition(".")[2]) if "." in mantissa else 0
    exponent = int(exponent_text) if marker else 0
    return 10.0 ** (exponent - decimal_places)


def _selected_matrix_blocks(
    event: HubbardPopulationEvent, output_text: str
) -> tuple[tuple[int, tuple[tuple[str, ...], ...], tuple[tuple[str, ...], ...], float], ...]:
    if event.source_start_line is None or event.source_end_line is None:
        raise PointStateEvidenceError("selected Hubbard event has no source line range")
    lines = output_text.splitlines()
    if event.source_start_line < 0 or event.source_end_line >= len(lines):
        raise PointStateEvidenceError("selected Hubbard event source range is outside output")

    blocks: list[tuple[int, tuple[tuple[str, ...], ...], tuple[tuple[str, ...], ...], float]] = []
    current_atom: int | None = None
    rows: list[tuple[int, int, str, str]] = []
    summary: tuple[float, float] | None = None

    def finish_atom() -> None:
        nonlocal current_atom, rows, summary
        if current_atom is None:
            return
        if summary is None:
            raise PointStateEvidenceError(f"atom {current_atom} has no Occupations summary")
        if len(rows) != 25:
            raise PointStateEvidenceError(
                f"atom {current_atom} matrix is truncated: expected 25 entries, found {len(rows)}"
            )
        indices = [(i, j) for i, j, _, _ in rows]
        if set(indices) != {(i, j) for i in range(1, 6) for j in range(1, 6)}:
            raise PointStateEvidenceError(f"atom {current_atom} matrix indices are incomplete or duplicated")
        up = [[""] * 5 for _ in range(5)]
        down = [[""] * 5 for _ in range(5)]
        quantum_values: set[float] = set()
        for i, j, up_token, down_token in rows:
            up[i - 1][j - 1] = up_token
            down[i - 1][j - 1] = down_token
            quantum_values.add(_quantum(up_token))
            quantum_values.add(_quantum(down_token))
        if quantum_values != {1e-5}:
            raise PointStateEvidenceError(f"atom {current_atom} matrix precision is not uniformly 5 decimals")
        for matrix in (up, down):
            for i in range(5):
                for j in range(i + 1, 5):
                    if _normal_number(matrix[i][j]) != _normal_number(matrix[j][i]):
                        raise PointStateEvidenceError(f"atom {current_atom} matrix is not symmetric")
        for channel, matrix in (("up", up), ("down", down)):
            trace = sum(_normal_number(matrix[i][i]) for i in range(5))
            printed = summary[0] if channel == "up" else summary[1]
            if abs(trace - printed) > 2.55e-5:
                raise PointStateEvidenceError(
                    f"atom {current_atom} {channel} trace differs from Occupations by more than 2.55e-5"
                )
        blocks.append(
            (current_atom, tuple(tuple(row) for row in up), tuple(tuple(row) for row in down), 1e-5)
        )
        current_atom = None
        rows = []
        summary = None

    for line in lines[event.source_start_line : event.source_end_line + 1]:
        atom_match = _ATOM_START.match(line)
        if atom_match:
            finish_atom()
            current_atom = int(atom_match.group(1))
            continue
        if current_atom is None:
            continue
        match = _MATRIX_ROW.match(line)
        if match:
            rows.append(
                (int(match.group("i")), int(match.group("j")), match.group("up"), match.group("down"))
            )
        elif "Occupations:" in line:
            values = re.findall(_NUMBER, line.split("Occupations:", 1)[1])
            if len(values) != 3:
                raise PointStateEvidenceError(f"atom {current_atom} has malformed Occupations summary")
            summary = (_normal_number(values[0]), _normal_number(values[1]))
    finish_atom()

    if len(blocks) != len(event.atoms) or not blocks:
        raise PointStateEvidenceError(
            f"selected event matrix blocks ({len(blocks)}) do not match parsed atoms ({len(event.atoms)})"
        )
    if tuple(block[0] for block in blocks) != tuple(atom.atom_index for atom in event.atoms):
        raise PointStateEvidenceError("selected event atom indices do not match its parsed matrices")
    return tuple(blocks)


def _final_mulliken_sz(output_text: str, atom_indices: tuple[int, ...]) -> dict[int, tuple[float, float]]:
    lines = output_text.splitlines()
    tables: list[tuple[int, dict[int, tuple[float, float]]]] = []
    last_table_start: int | None = None
    for start, line in enumerate(lines):
        if not _MULLIKEN_START.match(line):
            continue
        last_table_start = start
        cursor = start + 1
        while cursor < len(lines) and not _MULLIKEN_HEADER.match(lines[cursor]):
            if _MULLIKEN_START.match(lines[cursor]):
                break
            cursor += 1
        if cursor >= len(lines) or not _MULLIKEN_HEADER.match(lines[cursor]):
            continue
        cursor += 1
        rows: dict[int, tuple[float, float]] = {}
        terminated = False
        while cursor < len(lines):
            if re.match(r"^\s*-{5,}\s*$", lines[cursor]):
                terminated = True
                break
            if lines[cursor].strip():
                match = _MULLIKEN_ROW.match(lines[cursor])
                if match is None:
                    rows.clear()
                    break
                index = int(match.group("index"))
                sz_token = match.group("sz")
                if index in rows:
                    rows.clear()
                    break
                rows[index] = (_normal_number(sz_token), 0.5 * _quantum(sz_token))
            cursor += 1
        if terminated and set(rows) >= set(atom_indices):
            tables.append((start, rows))
    if not tables or tables[-1][0] != last_table_start:
        raise PointStateEvidenceError("no complete final Mulliken Atomic Populations table found")
    return tables[-1][1]


def _parse_eig(eig_text: str) -> tuple[str, float, tuple[PrintedBandEnergy, ...]]:
    lines = eig_text.splitlines()
    if len(lines) < 3:
        raise PointStateEvidenceError(".EIG file is truncated before its spectrum")
    fermi_token = lines[0].strip()
    if not _EIG_NUMBER.fullmatch(fermi_token):
        raise PointStateEvidenceError(".EIG first line is not a Fermi energy")
    fermi_energy_ev = _normal_number(fermi_token)
    fermi_quantum_ev = _quantum(fermi_token)
    header = lines[1].split()
    if len(header) != 3 or not all(token.isdigit() for token in header):
        raise PointStateEvidenceError(".EIG second line must contain k-point, spin, and band counts")
    band_count, spin_count, kpoint_count = (int(token) for token in header)
    if min(kpoint_count, spin_count, band_count) < 1:
        raise PointStateEvidenceError(".EIG dimensions must be positive")

    spectra: list[tuple[int, list[str]]] = []
    current_k: int | None = None
    current_tokens: list[str] = []
    for line in lines[2:]:
        tokens = line.split()
        if not tokens:
            continue
        if tokens[0].isdigit() and len(tokens) > 1 and _EIG_NUMBER.fullmatch(tokens[1]):
            if current_k is not None:
                spectra.append((current_k, current_tokens))
            current_k = int(tokens[0])
            current_tokens = tokens[1:]
        elif current_k is not None and all(_EIG_NUMBER.fullmatch(token) for token in tokens):
            current_tokens.extend(tokens)
        else:
            raise PointStateEvidenceError(f"malformed .EIG spectrum row: {line!r}")
    if current_k is not None:
        spectra.append((current_k, current_tokens))
    if tuple(index for index, _ in spectra) != tuple(range(1, kpoint_count + 1)):
        raise PointStateEvidenceError(".EIG k-point rows are incomplete or out of order")

    result: list[PrintedBandEnergy] = []
    for kpoint, tokens in spectra:
        if len(tokens) != spin_count * band_count:
            raise PointStateEvidenceError(
                f".EIG k-point {kpoint} has {len(tokens)} energies; expected {spin_count * band_count}"
            )
        for spin in range(spin_count):
            for token in tokens[spin * band_count : (spin + 1) * band_count]:
                energy_ev = _normal_number(token)
                result.append(
                    PrintedBandEnergy(
                        kpoint=kpoint,
                        spin=spin + 1,
                        energy_ev=energy_ev,
                        energy_token=token,
                        distance_to_fermi_ev=abs(energy_ev - fermi_energy_ev),
                        print_quantum_ev=_quantum(token),
                    )
                )
    return fermi_token, fermi_quantum_ev, tuple(result)


def build_point_state(
    event: HubbardPopulationEvent, output_text: str, eig_text: str | None = None
) -> PointState:
    """Build a typed state record from one already-selected population event."""
    if not output_text.strip():
        raise PointStateEvidenceError("SIESTA output is empty")
    fermi_tokens = [
        match.group("value") for line in output_text.splitlines() if (match := _FERMI.match(line))
    ]
    if not fermi_tokens:
        raise PointStateEvidenceError("SIESTA output has no printed Fermi line")
    fermi_stdout_token = fermi_tokens[-1]
    fermi_stdout_energy_ev = _normal_number(fermi_stdout_token)
    fermi_stdout_half_width_ev = 0.5 * _quantum(fermi_stdout_token)

    blocks = _selected_matrix_blocks(event, output_text)
    mulliken = _final_mulliken_sz(output_text, tuple(block[0] for block in blocks))
    atoms = tuple(
        AtomPointState(
            atom_index=atom_index,
            matrix_up=matrix_up,
            matrix_down=matrix_down,
            matrix_print_quantum_e=quantum,
            sz_e=mulliken[atom_index][0],
            sz_half_width_e=mulliken[atom_index][1],
        )
        for atom_index, matrix_up, matrix_down, quantum in blocks
    )
    if eig_text is None:
        fermi_token = fermi_stdout_token
        fermi_energy_ev = fermi_stdout_energy_ev
        fermi_quantum_ev = _quantum(fermi_stdout_token)
        bands: tuple[PrintedBandEnergy, ...] = ()
    else:
        fermi_token, fermi_quantum_ev, bands = _parse_eig(eig_text)
        fermi_energy_ev = _normal_number(fermi_token)
    return PointState(
        atoms=atoms,
        fermi_energy_ev=fermi_energy_ev,
        fermi_energy_token=fermi_token,
        fermi_print_quantum_ev=fermi_quantum_ev,
        fermi_stdout_energy_ev=fermi_stdout_energy_ev,
        fermi_stdout_token=fermi_stdout_token,
        fermi_stdout_half_width_ev=fermi_stdout_half_width_ev,
        band_evidence_status=BandEvidenceStatus.NOT_AVAILABLE
        if eig_text is None
        else BandEvidenceStatus.AVAILABLE,
        band_energies=bands,
    )
