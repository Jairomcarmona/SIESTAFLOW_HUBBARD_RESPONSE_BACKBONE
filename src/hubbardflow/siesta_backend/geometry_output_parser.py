"""Parse final force and stress observables from a SIESTA output file."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

_NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][-+]?\d+)?"
_MAXIMUM = re.compile(rf"^\s*Max\s+({_NUMBER})\s*$", re.IGNORECASE)
_CONSTRAINED_MAXIMUM = re.compile(rf"^\s*Max\s+({_NUMBER})\s+constrained\b", re.IGNORECASE)
_RESIDUAL = re.compile(rf"^\s*Res\s+({_NUMBER})\b", re.IGNORECASE)
_STRESS = re.compile(
    rf"Stress tensor Voigt\[x,y,z,yz,xz,xy\] \(kbar\):\s*"
    rf"({_NUMBER})\s+({_NUMBER})\s+({_NUMBER})\s+({_NUMBER})\s+({_NUMBER})\s+({_NUMBER})",
    re.IGNORECASE,
)


class GeometryOutputParseError(ValueError):
    """Raised when a present SIESTA observable contains malformed numbers."""


@dataclass(frozen=True)
class ParsedReferenceGeometryOutput:
    """Printed final reference observables with one-based source line numbers."""

    maximum_force_ev_ang: float | None
    residual_ev_ang: float | None
    maximum_constrained_force_ev_ang: float | None
    stress_voigt_kbar: tuple[float, float, float, float, float, float] | None
    source_lines: tuple[tuple[str, int], ...]

    def to_mapping(self) -> dict[str, object]:
        """Serialize parser output for report JSON."""
        return {
            "maximum_force_ev_ang": self.maximum_force_ev_ang,
            "residual_ev_ang": self.residual_ev_ang,
            "maximum_constrained_force_ev_ang": self.maximum_constrained_force_ev_ang,
            "stress_voigt_kbar": None if self.stress_voigt_kbar is None else list(self.stress_voigt_kbar),
            "source_lines": {name: line for name, line in self.source_lines},
        }


def _as_float(token: str, name: str) -> float:
    try:
        value = float(token.replace("D", "E").replace("d", "e"))
    except ValueError as exc:
        raise GeometryOutputParseError(f"invalid {name} value {token!r}") from exc
    if not math.isfinite(value):
        raise GeometryOutputParseError(f"non-finite {name} value {token!r}")
    return value


def parse_reference_geometry_output(text: str) -> ParsedReferenceGeometryOutput | None:
    """Parse the last complete atomic-force section and its following stress.

    SIESTA can print force sections during multiple geometry steps. The last
    section is the state represented by the final reference output. A bare
    ``Max`` line is the unrestricted maximum; the separate ``constrained``
    line is retained to detect constrained geometries.
    """
    lines = text.splitlines()
    headers = [index for index, line in enumerate(lines) if "siesta: Atomic forces (eV/Ang):" in line]
    if not headers:
        return None
    start = headers[-1]
    stop = next((index for index in headers if index > start), len(lines))
    maximum: float | None = None
    residual: float | None = None
    constrained: float | None = None
    stress: tuple[float, float, float, float, float, float] | None = None
    source_lines: list[tuple[str, int]] = []
    for index in range(start + 1, stop):
        line = lines[index]
        match = _MAXIMUM.fullmatch(line)
        if match is not None:
            maximum = _as_float(match.group(1), "maximum force")
            source_lines.append(("maximum_force", index + 1))
            continue
        match = _CONSTRAINED_MAXIMUM.fullmatch(line)
        if match is not None:
            constrained = _as_float(match.group(1), "constrained maximum force")
            source_lines.append(("maximum_constrained_force", index + 1))
            continue
        match = _RESIDUAL.match(line)
        if match is not None:
            residual = _as_float(match.group(1), "residual force")
            source_lines.append(("residual_force", index + 1))
            continue
        match = _STRESS.search(line)
        if match is not None:
            stress = tuple(_as_float(match.group(i), "stress") for i in range(1, 7))  # type: ignore[assignment]
            source_lines.append(("stress", index + 1))
    return ParsedReferenceGeometryOutput(maximum, residual, constrained, stress, tuple(source_lines))
