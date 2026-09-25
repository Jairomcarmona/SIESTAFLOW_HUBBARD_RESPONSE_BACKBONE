"""Read the decimal precision attached to SIESTA's printed shell total."""
from __future__ import annotations

from dataclasses import dataclass
import math
import re

from .parser_models import HubbardPopulationEvent


_ATOM_RE = re.compile(r"hubbard_term:\s+atom,\s+species:\s+(\d+)\s+(\d+)")
_NUMBER_RE = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][-+]?\d+)?")


@dataclass(frozen=True)
class PrintedOccupation:
    atom_index: int
    total: float
    half_width: float
    decimal_places: int


def _half_step(token: str) -> tuple[float, int]:
    mantissa, separator, exponent_text = token.lower().partition("e")
    exponent = int(exponent_text) if separator else 0
    decimal_places = len(mantissa.split(".", 1)[1]) if "." in mantissa else 0
    return 0.5 * (10.0 ** (exponent - decimal_places)), decimal_places


def read_printed_occupation_precision(
    output_content: str,
    event: HubbardPopulationEvent,
) -> dict[int, PrintedOccupation]:
    """Map each event atom to SIESTA's summary total and its rounding interval.

    The event parser intentionally keeps its historical representation of the
    printed projector-matrix trace.  This adapter reads the corresponding raw
    ``Occupations:`` line without changing that parser or conflating the two
    observables.
    """
    start, end = event.source_start_line, event.source_end_line
    lines = output_content.splitlines()
    if (not isinstance(start, int) or not isinstance(end, int) or start < 0
            or end < start or end >= len(lines)):
        raise ValueError("selected population event has invalid source line bounds")
    found: dict[int, PrintedOccupation] = {}
    current_atom: int | None = None
    for line in lines[start:end + 1]:
        atom_match = _ATOM_RE.search(line)
        if atom_match:
            if current_atom is not None:
                raise ValueError("population event has an atom without an Occupations summary")
            current_atom = int(atom_match.group(1))
            continue
        if "Occupations:" not in line:
            continue
        if current_atom is None:
            raise ValueError("population event has an Occupations summary without an atom")
        tokens = _NUMBER_RE.findall(line.split("Occupations:", 1)[1])
        if len(tokens) == 3:
            total = float(tokens[2])
            half_width, decimal_places = _half_step(tokens[2])
        elif len(tokens) == 2:
            total = float(tokens[0]) + float(tokens[1])
            first_width, first_places = _half_step(tokens[0])
            second_width, second_places = _half_step(tokens[1])
            half_width = first_width + second_width
            decimal_places = min(first_places, second_places)
        else:
            raise ValueError(f"unsupported Occupations summary for atom {current_atom}")
        if current_atom in found:
            raise ValueError(f"duplicate Occupations summary for atom {current_atom}")
        found[current_atom] = PrintedOccupation(current_atom, total, half_width, decimal_places)
        current_atom = None
    expected = {atom.atom_index: atom for atom in event.atoms}
    if current_atom is not None or set(found) != set(expected):
        raise ValueError("raw Occupations summaries do not cover the selected event atoms exactly")
    for atom_index, measurement in found.items():
        parsed = expected[atom_index].printed_total_trace
        if not math.isclose(measurement.total, parsed, rel_tol=0.0, abs_tol=1e-12):
            raise ValueError(f"raw printed total disagrees with parsed event for atom {atom_index}")
    return found
