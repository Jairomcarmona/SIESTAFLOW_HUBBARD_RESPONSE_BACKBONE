"""Extract versioned collinear magnetic evidence from a completed SIESTA output.

Only the final ``Mulliken Atomic Populations`` summary used by SIESTA 5.4.2 is
accepted.  Initial spins, intermediate tables, incomplete tables, non-normal
termination, and SCF non-convergence are not evidence of the reference state.
"""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any

import numpy as np


class ReferenceMagneticEvidenceError(ValueError):
    """The output cannot certify a collinear converged reference state."""


_TABLE_HEADER = re.compile(r"^\s*Atom\s+#.*\bSz\s*\[e\].*\bSpecies\s*$", re.IGNORECASE)
_ROW = re.compile(
    r"^\s*(?P<index>\d+)\s+"
    r"(?P<charge>[-+]?\d*\.?\d+(?:[EeDd][-+]?\d+)?)\s+"
    r"(?P<valence>[-+]?\d*\.?\d+(?:[EeDd][-+]?\d+)?)\s+"
    r"(?P<sz>[-+]?\d*\.?\d+(?:[EeDd][-+]?\d+)?)\s+"
    r"(?P<species>\S+)\s*$"
)
_TABLE_START = re.compile(r"^\s*Mulliken Atomic Populations:\s*$", re.IGNORECASE)
_TABLE_END = re.compile(r"^\s*-{5,}\s*$")
_FAILURE = re.compile(r"SCF_NOT_CONV|SCF:\s*not\s+converged|ABNORMAL_TERMINATION|MPI_Abort", re.IGNORECASE)


def _as_float(value: str) -> float:
    return float(value.replace("D", "E").replace("d", "e"))


def _require_normal_completion(text: str) -> None:
    if _FAILURE.search(text):
        raise ReferenceMagneticEvidenceError("SIESTA reporta fallo o SCF no convergida")
    normal = re.search(r"siesta:\s*normal completion", text, re.IGNORECASE)
    end_of_run = re.search(r">>\s*End of run:", text, re.IGNORECASE)
    job_completed = re.search(r"^\s*Job completed\s*$", text, re.IGNORECASE | re.MULTILINE)
    if not normal and not (end_of_run and job_completed):
        raise ReferenceMagneticEvidenceError("La salida no acredita terminación normal de SIESTA")


def parse_final_collinear_mulliken_sz(output_text: str, atom_count: int) -> np.ndarray:
    """Return final per-atom collinear moments (Bohr magnetons) from SIESTA 5.4.

    The accepted table contains atom index, charge, valence, ``Sz`` and species.
    The last *complete* table is used because SIESTA can print previous analysis
    stages.  All atoms 1..N must occur exactly once; otherwise the result is
    unusable for a symmetry operation on the full cell.
    """
    if not isinstance(atom_count, int) or atom_count <= 0:
        raise ReferenceMagneticEvidenceError("Número de átomos inválido")
    _require_normal_completion(output_text)
    lines = output_text.splitlines()
    candidates: list[dict[int, float]] = []
    for start, line in enumerate(lines):
        if not _TABLE_START.match(line):
            continue
        cursor = start + 1
        while cursor < len(lines) and not _TABLE_HEADER.match(lines[cursor]):
            if _TABLE_START.match(lines[cursor]):
                break
            cursor += 1
        if cursor == len(lines) or not _TABLE_HEADER.match(lines[cursor]):
            continue
        cursor += 1
        rows: dict[int, float] = {}
        malformed = False
        while cursor < len(lines) and not _TABLE_END.match(lines[cursor]):
            current = lines[cursor]
            if current.strip():
                match = _ROW.match(current)
                if not match:
                    malformed = True
                    break
                index = int(match.group("index"))
                if index in rows:
                    malformed = True
                    break
                rows[index] = _as_float(match.group("sz"))
            cursor += 1
        if cursor == len(lines) or malformed:
            continue
        expected = set(range(1, atom_count + 1))
        if set(rows) == expected and all(np.isfinite(value) for value in rows.values()):
            candidates.append(rows)
    if not candidates:
        raise ReferenceMagneticEvidenceError(
            "No hay tabla Mulliken final, completa y colineal para todos los átomos"
        )
    return np.asarray([[0.0, 0.0, candidates[-1][index]] for index in range(1, atom_count + 1)], dtype=float)


def _is_explicitly_nonpolarized(fdf_text: str, output_text: str) -> bool:
    """Verify the non-magnetic mode in both declared input and executed output."""
    fdf_nonpolarized = re.search(
        r"^\s*Spin\s+non-polarized\s*$", fdf_text, re.IGNORECASE | re.MULTILINE
    )
    reported_none = re.search(
        r"^\s*redata:\s*Spin configuration\s*=\s*none\s*$",
        output_text, re.IGNORECASE | re.MULTILINE,
    )
    one_component = re.search(
        r"^\s*redata:\s*Number of spin components\s*=\s*1\s*$",
        output_text, re.IGNORECASE | re.MULTILINE,
    )
    time_reversal = re.search(
        r"^\s*redata:\s*Time-Reversal Symmetry\s*=\s*T\s*$",
        output_text, re.IGNORECASE | re.MULTILINE,
    )
    return bool(fdf_nonpolarized and reported_none and one_component and time_reversal)


def reference_moments_from_fdf_and_output(fdf_text: str, output_text: str) -> tuple[np.ndarray, str]:
    """Return moments only for a verified collinear or explicitly nonpolarized run."""
    match = re.search(r"^\s*NumberOfAtoms\s+(\d+)\s*$", fdf_text, re.IGNORECASE | re.MULTILINE)
    if not match:
        raise ReferenceMagneticEvidenceError("La FDF no declara NumberOfAtoms")
    atom_count = int(match.group(1))
    _require_normal_completion(output_text)
    if _is_explicitly_nonpolarized(fdf_text, output_text):
        return np.zeros((atom_count, 3), dtype=float), "siesta_5_4_explicit_nonpolarized_v1"
    return parse_final_collinear_mulliken_sz(output_text, atom_count), "siesta_5_4_final_collinear_mulliken_sz_v1"


def build_reference_magnetic_evidence(
    fdf_path: str | Path, output_path: str | Path, destination: str | Path | None = None
) -> dict[str, Any]:
    """Bind final Mulliken moments to the exact reference FDF and output bytes."""
    fdf = Path(fdf_path)
    output = Path(output_path)
    fdf_bytes, output_bytes = fdf.read_bytes(), output.read_bytes()
    try:
        text = output_bytes.decode("utf-8")
    except UnicodeDecodeError:
        text = output_bytes.decode("latin-1")
    fdf_text = fdf_bytes.decode("utf-8")
    moments, parser_name = reference_moments_from_fdf_and_output(fdf_text, text)
    evidence = {
        "schema_version": 1,
        "parser": parser_name,
        "input_fdf_sha256": sha256(fdf_bytes).hexdigest(),
        "siesta_output_sha256": sha256(output_bytes).hexdigest(),
        "normal_completion_verified": True,
        "atom_count": len(moments),
        "moments_by_atom_index": {str(index): row.tolist() for index, row in enumerate(moments, start=1)},
    }
    if destination is not None:
        Path(destination).write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return evidence
