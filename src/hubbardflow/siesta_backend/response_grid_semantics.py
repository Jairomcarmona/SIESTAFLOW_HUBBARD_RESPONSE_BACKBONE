"""SIESTA-specific semantic extraction for response-grid evidence.

The generic evidence validator verifies paths, receipts and hashes. This
adapter owns DFTU.Proj FDF syntax, SIESTA event selection and printed
occupation precision.
"""
from __future__ import annotations

from math import isclose
from pathlib import Path
import re

from .occupation_precision import read_printed_occupation_precision
from .siesta542_bare_profile import Siesta542PotentialShiftHamiltonianProfile
from .siesta542_screened_selection import select_converged_screened_event


def _verify_projector_shift(fdf_text: str, site_id: str, alpha_ev: float) -> None:
    lines = fdf_text.splitlines()
    starts = [i for i, line in enumerate(lines) if re.match(r"^\s*%block\s+DFTU\.Proj\s*$", line, re.I)]
    if len(starts) != 1:
        raise ValueError("node FDF must contain exactly one DFTU.Proj block")
    start = starts[0]
    ends = [i for i in range(start + 1, len(lines))
            if re.match(r"^\s*%endblock\s+DFTU\.Proj\s*$", lines[i], re.I)]
    if len(ends) != 1:
        raise ValueError("node FDF has an incomplete or ambiguous DFTU.Proj block")
    body = lines[start + 1:ends[0]]
    if not body or len(body) % 4:
        raise ValueError("node FDF DFTU.Proj records are not complete four-line site records")
    matched = 0
    for offset in range(0, len(body), 4):
        header, shell, shift_line, radial = body[offset:offset + 4]
        header_fields, shell_fields = header.split(), shell.split()
        shift_fields, radial_fields = shift_line.split(), radial.split()
        if len(header_fields) != 2 or len(shell_fields) != 2 or len(shift_fields) != 2 or len(radial_fields) < 2:
            raise ValueError("node FDF contains an unsupported DFTU.Proj site record")
        try:
            alpha = float(shift_fields[0])
            other_shift = float(shift_fields[1])
            int(header_fields[1]); int(shell_fields[0]); int(shell_fields[1])
            float(radial_fields[0]); float(radial_fields[1])
        except ValueError as exc:
            raise ValueError("node FDF contains a nonnumeric DFTU.Proj record") from exc
        if header_fields[0] == site_id:
            matched += 1
            if not isclose(alpha, alpha_ev, rel_tol=0.0, abs_tol=5.1e-5):
                raise ValueError("FDF projector shift does not match the node alpha")
        elif not isclose(alpha, 0.0, rel_tol=0.0, abs_tol=1e-12):
            raise ValueError("FDF applies a nonzero shift to an unexpected site")
        if not isclose(other_shift, 0.0, rel_tol=0.0, abs_tol=1e-12):
            raise ValueError("FDF applies an unexpected second-channel projector shift")
    if matched != 1:
        raise ValueError("node FDF does not identify exactly one perturbed site")


def extract_siesta_response_cell(
    fdf_path: Path,
    out_path: Path,
    *,
    mode: str,
    site_id: str,
    alpha_ev: float,
    atom_index: int,
) -> tuple[float, float]:
    """Re-read one SIESTA cell and return occupation plus print half-width."""
    fdf_text = fdf_path.read_text(encoding="utf-8", errors="replace")
    _verify_projector_shift(fdf_text, site_id, alpha_ev)
    output_text = out_path.read_text(encoding="utf-8", errors="replace")
    if mode == "BARE":
        event = Siesta542PotentialShiftHamiltonianProfile().select_response(output_text).response_event
    elif mode == "SCREENED":
        event = select_converged_screened_event(output_text)
    else:
        raise ValueError(f"unsupported SIESTA response mode {mode!r}")
    parsed = read_printed_occupation_precision(output_text, event)[atom_index]
    return float(parsed.total), float(parsed.half_width)
