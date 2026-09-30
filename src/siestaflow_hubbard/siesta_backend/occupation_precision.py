"""Read decimal precision from SIESTA population events and summaries."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction
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
    printed_tokens: tuple[str, ...]
    value_decimal: str
    half_width_exact: str
    certification_tokens: tuple[str, ...]


@dataclass(frozen=True)
class PrintedMatrixTrace:
    atom_index: int
    total: float
    half_width: float
    decimal_places: int
    diagonal_term_count: int


def _half_step(token: str) -> tuple[float, int]:
    mantissa, separator, exponent_text = token.lower().partition("e")
    exponent = int(exponent_text) if separator else 0
    decimal_places = len(mantissa.split(".", 1)[1]) if "." in mantissa else 0
    return 0.5 * (10.0 ** (exponent - decimal_places)), decimal_places


def read_printed_occupation_precision(
    output_content: str,
    event: HubbardPopulationEvent,
    *,
    minimum_decimal_places: int | None = None,
) -> dict[int, PrintedOccupation]:
    """Map each event atom to SIESTA's summary total and its rounding interval.

    The event parser intentionally keeps its historical representation of the
    printed projector-matrix trace.  This adapter reads the corresponding raw
    ``Occupations:`` line without changing that parser or conflating the two
    observables.
    """
    if minimum_decimal_places is not None and (
        isinstance(minimum_decimal_places, bool)
        or not isinstance(minimum_decimal_places, int)
        or minimum_decimal_places < 0
    ):
        raise ValueError("minimum_decimal_places must be a nonnegative integer when supplied")
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
            value_decimal = tokens[2]
            certification_tokens = (tokens[2],)
            mantissa, sep, exponent = tokens[2].lower().partition("e")
            places = len(mantissa.split(".", 1)[1]) if "." in mantissa else 0
            exact_half_width = Fraction(1, 2) * Fraction(10) ** ((int(exponent) if sep else 0) - places)
        elif len(tokens) == 2:
            total = float(tokens[0]) + float(tokens[1])
            first_width, first_places = _half_step(tokens[0])
            second_width, second_places = _half_step(tokens[1])
            half_width = first_width + second_width
            decimal_places = min(first_places, second_places)
            value_decimal = format(sum((Decimal(token) for token in tokens), Decimal(0)), "f")
            certification_tokens = tuple(tokens)
            exact_half_width = Fraction(0)
            for token in tokens:
                mantissa, sep, exponent = token.lower().partition("e")
                places = len(mantissa.split(".", 1)[1]) if "." in mantissa else 0
                exact_half_width += Fraction(1, 2) * Fraction(10) ** ((int(exponent) if sep else 0) - places)
        else:
            raise ValueError(f"unsupported Occupations summary for atom {current_atom}")
        if minimum_decimal_places is not None and decimal_places < minimum_decimal_places:
            raise ValueError(
                f"Occupations summary for atom {current_atom} has {decimal_places} decimal places; "
                f"at least {minimum_decimal_places} are required by the declared U precision policy"
            )
        if current_atom in found:
            raise ValueError(f"duplicate Occupations summary for atom {current_atom}")
        found[current_atom] = PrintedOccupation(
            current_atom, total, half_width, decimal_places, tuple(tokens),
            value_decimal, str(exact_half_width),
            certification_tokens,
        )
        current_atom = None
    expected = {atom.atom_index: atom for atom in event.atoms}
    if current_atom is not None or set(found) != set(expected):
        raise ValueError("raw Occupations summaries do not cover the selected event atoms exactly")
    for atom_index, measurement in found.items():
        parsed = expected[atom_index].printed_total_trace
        if not math.isclose(measurement.total, parsed, rel_tol=0.0, abs_tol=1e-12):
            raise ValueError(f"raw printed total disagrees with parsed event for atom {atom_index}")
    return found


def read_printed_matrix_trace_precision(
    output_content: str,
    event: HubbardPopulationEvent,
) -> dict[int, PrintedMatrixTrace]:
    """Bound rounding in the matrix diagonal tokens used by ``trace_total``.

    The event parser computes each spin trace from the diagonal elements of
    the printed projector matrix.  When there is no down-spin matrix,
    ``trace_total`` duplicates the up trace, so its interval also duplicates
    every up-channel half-step.  ``Occupations:`` summaries are deliberately
    not used here because they are a different printed observable.
    """
    start, end = event.source_start_line, event.source_end_line
    lines = output_content.splitlines()
    if (not isinstance(start, int) or not isinstance(end, int) or start < 0
            or end < start or end >= len(lines)):
        raise ValueError("selected population event has invalid source line bounds")

    matrix_line = re.compile(
        r"^\s*([1-9]\d*)\s+([1-9]\d*)\s+("
        + _NUMBER_RE.pattern
        + r")(?:\s+("
        + _NUMBER_RE.pattern
        + r"))?\s*$"
    )
    expected = {int(atom.atom_index): atom for atom in event.atoms}
    found: dict[int, PrintedMatrixTrace] = {}
    current_atom: int | None = None
    diagonal_tokens: dict[int, tuple[str, str | None]] = {}

    def finish_atom() -> None:
        nonlocal current_atom, diagonal_tokens
        if current_atom is None:
            return
        atom = expected.get(current_atom)
        if atom is None:
            raise ValueError(f"matrix event contains undeclared atom {current_atom}")
        dimension = int(atom.raw_matrix_up.shape[0])
        if set(diagonal_tokens) != set(range(1, dimension + 1)):
            raise ValueError(f"matrix diagonal tokens do not cover atom {current_atom} exactly")
        up_tokens = [diagonal_tokens[index][0] for index in range(1, dimension + 1)]
        down_tokens = [diagonal_tokens[index][1] for index in range(1, dimension + 1)]
        has_down = atom.raw_matrix_down is not None
        if has_down != all(token is not None for token in down_tokens):
            raise ValueError(f"matrix spin channels do not match the selected event for atom {current_atom}")
        if not has_down and any(token is not None for token in down_tokens):
            raise ValueError(f"unexpected down-spin diagonal tokens for atom {current_atom}")
        up_values = [float(token) for token in up_tokens]
        if not all(math.isclose(value, float(atom.raw_matrix_up[i, i]), rel_tol=0.0, abs_tol=1e-12)
                   for i, value in enumerate(up_values)):
            raise ValueError(f"raw up-spin diagonal tokens disagree with event matrix for atom {current_atom}")
        up_total = math.fsum(up_values)
        terms = list(up_tokens)
        if has_down:
            down_values = [float(token) for token in down_tokens if token is not None]
            assert atom.raw_matrix_down is not None
            if not all(math.isclose(value, float(atom.raw_matrix_down[i, i]), rel_tol=0.0, abs_tol=1e-12)
                       for i, value in enumerate(down_values)):
                raise ValueError(f"raw down-spin diagonal tokens disagree with event matrix for atom {current_atom}")
            total = up_total + math.fsum(down_values)
            terms.extend(token for token in down_tokens if token is not None)
        else:
            total = up_total + up_total
            terms.extend(up_tokens)
        if not math.isclose(total, float(atom.trace_total), rel_tol=0.0, abs_tol=1e-12):
            raise ValueError(f"diagonal token sum disagrees with trace_total for atom {current_atom}")
        steps = [_half_step(token) for token in terms]
        found[current_atom] = PrintedMatrixTrace(
            atom_index=current_atom,
            total=total,
            half_width=math.fsum(width for width, _ in steps),
            decimal_places=min(places for _, places in steps),
            diagonal_term_count=len(terms),
        )
        current_atom = None
        diagonal_tokens = {}

    for line in lines[start:end + 1]:
        atom_match = _ATOM_RE.search(line)
        if atom_match:
            finish_atom()
            current_atom = int(atom_match.group(1))
            if current_atom in found:
                raise ValueError(f"duplicate matrix atom {current_atom} in selected event")
            diagonal_tokens = {}
            continue
        if current_atom is None:
            continue
        matrix_match = matrix_line.match(line)
        if matrix_match is None:
            continue
        row, column = int(matrix_match.group(1)), int(matrix_match.group(2))
        up_token, down_token = matrix_match.group(3), matrix_match.group(4)
        if row != column:
            continue
        if row in diagonal_tokens:
            raise ValueError(f"duplicate matrix diagonal token for atom {current_atom}, m={row}")
        diagonal_tokens[row] = (up_token, down_token)
    finish_atom()
    if set(found) != set(expected):
        raise ValueError("raw matrix diagonal tokens do not cover selected event atoms exactly")
    return found
