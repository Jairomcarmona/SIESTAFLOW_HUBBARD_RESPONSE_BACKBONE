"""D1 admission from a single output and its exact echoed input.

TASK 8 partial evidence remains untouched. Input echoes are compared after
whitespace/comment normalization only; discrepancies never establish a parent
reference. PotentialShift U values are perturbations, not Hubbard fitting data.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from hashlib import sha256
from pathlib import Path

from hubbardflow.domain.coverage_models import CoverageReferenceEvidence
from hubbardflow.domain.state_evidence import CorrelatedSubspaceLike, EvidenceStatus, OccupationSpectraStatus
from hubbardflow.siesta_backend.fdf_model import parse_effective_fdf
from hubbardflow.siesta_backend.reference_magnetic_evidence import (
    ReferenceMagneticEvidenceError,
    _is_explicitly_nonpolarized,
    parse_final_collinear_mulliken_sz,
)
from hubbardflow.siesta_backend.reference_state_evidence import build_reference_state_evidence


def _canonical(text: str) -> str:
    return "\n".join(
        " ".join(line.partition("#")[0].split())
        for line in text.splitlines()
        if line.partition("#")[0].strip()
    )


def _echo(text: str) -> str | None:
    match = re.search(
        r"\*+ Dump of input data file \*+\s*\n(.*?)\*+ End of input data file \*+", text, re.DOTALL
    )
    return None if match is None else match.group(1)


def _perturbed(text: str) -> bool:
    if not re.search(
        r"^\s*DFTU\.PotentialShift\s+(?:true|t|yes)\s*(?:#.*)?$", text, re.IGNORECASE | re.MULTILINE
    ):
        return False
    block = re.search(r"%block\s+DFTU\.proj\s*\n(.*?)%endblock", text, re.IGNORECASE | re.DOTALL)
    if block is None:
        return True
    lines = [
        line.partition("#")[0].strip()
        for line in block.group(1).splitlines()
        if line.partition("#")[0].strip()
    ]
    records = 0
    for index, line in enumerate(lines):
        if re.fullmatch(r"\S*[A-Za-z]\S*\s+\d+", line):
            records += 1
            try:
                values = [
                    float(token.replace("D", "E").replace("d", "e")) for token in lines[index + 2].split()
                ]
            except (ValueError, IndexError):
                return True
            if len(values) != 2 or any(value != 0 for value in values):
                return True
    return records == 0


def build_coverage_reference_evidence(
    fdf_path: str | Path,
    output_path: str | Path,
    subspaces: Sequence[CorrelatedSubspaceLike],
) -> CoverageReferenceEvidence:
    """Retain hashes and incomplete fields; reject mismatched or perturbed input.

    Non-polarized status requires both an explicit FDF declaration and the output's
    effective spin configuration. Moments are then inapplicable, never fabricated.
    Missing parent-DM bytes are recorded as absent rather than inferred.
    """
    fdf, output = Path(fdf_path), Path(output_path)
    model = parse_effective_fdf(fdf)
    text = output.read_text(encoding="utf-8", errors="replace")
    evidence = build_reference_state_evidence(fdf, output, subspaces)
    echo = _echo(text)
    consistent = echo is not None and _canonical(model.effective_text) == _canonical(echo)
    nonpolarized = _is_explicitly_nonpolarized(model.effective_text, text)
    moments_verified = False
    last_table = re.split(r"^\s*Mulliken Atomic Populations:\s*$", text, flags=re.MULTILINE | re.IGNORECASE)
    if len(last_table) > 1:
        try:
            parse_final_collinear_mulliken_sz(
                "Mulliken Atomic Populations:\n" + last_table[-1], model.number_of_atoms
            )
            moments_verified = True
        except ReferenceMagneticEvidenceError:
            pass
    perturbed = (
        model.dftu_potential_shift is True
        and any(record.u_ref_ev != 0 or record.j_ref_ev != 0 for record in model.dftu_records)
    ) or (echo is not None and _perturbed(echo))
    complete = (
        consistent
        and not perturbed
        and evidence.normal_completion_verified
        and evidence.scf_converged
        and (nonpolarized or moments_verified)
        and evidence.occupation_spectra_status is OccupationSpectraStatus.AVAILABLE
        and bool(evidence.occupation_spectra_by_subspace)
    )
    return CoverageReferenceEvidence(
        evidence,
        sha256(fdf.read_bytes()).hexdigest(),
        None if echo is None else sha256(echo.encode()).hexdigest(),
        consistent,
        nonpolarized,
        perturbed,
        EvidenceStatus.ADMISSIBLE if complete else EvidenceStatus.REFERENCE_NOT_ADMISSIBLE,
        None,
    )
