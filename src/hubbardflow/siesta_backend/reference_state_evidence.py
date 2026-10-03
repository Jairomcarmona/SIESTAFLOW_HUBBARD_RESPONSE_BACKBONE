"""Read-only extraction of reference magnetic, mesh, and local-state evidence.

The evidence is bound to the effective FDF and exact output bytes. Printed
occupation matrices are accepted only from complete parser events; missing
matrices remain unavailable and cannot support F7 equivalence.
"""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

import numpy as np

from hubbardflow.domain.exceptions import SemanticValidationFailure, SiestaParserError
from hubbardflow.domain.state_evidence import (
    CorrelatedSubspaceLike,
    EvidenceStatus,
    MomentEvidence,
    OccupationSpectraStatus,
    OccupationSpectrum,
    ReferenceStateEvidence,
    StateEvidenceReason,
    SubspaceOccupationEvidence,
)
from hubbardflow.siesta_backend.event_parser import parse_hubbard_population_events
from hubbardflow.siesta_backend.fdf_model import FdfModel, parse_effective_fdf
from hubbardflow.siesta_backend.occupation_precision import read_printed_matrix_trace_precision
from hubbardflow.siesta_backend.parser_models import HubbardPopulationEvent
from hubbardflow.siesta_backend.reference_magnetic_evidence import (
    ReferenceMagneticEvidenceError,
    parse_final_collinear_mulliken_sz,
)


class ReferenceStateEvidenceError(ValueError):
    """The FDF, output, or correlated inventory violates the evidence contract."""


@dataclass(frozen=True)
class _OutputSubspace:
    site_id: str
    atom_index: int


_MULLIKEN_START = re.compile(r"^\s*Mulliken Atomic Populations:\s*$", re.IGNORECASE)
_MULLIKEN_HEADER = re.compile(r"^\s*Atom\s+#.*\bSz\s*\[e\].*\bSpecies\s*$", re.IGNORECASE)
_MULLIKEN_ROW = re.compile(
    r"^\s*(?P<index>\d+)\s+[-+]?\d*\.?\d+(?:[EeDd][-+]?\d+)?\s+"
    r"[-+]?\d*\.?\d+(?:[EeDd][-+]?\d+)?\s+"
    r"(?P<sz>[-+]?\d*\.?\d+(?:[EeDd][-+]?\d+)?)\s+\S+\s*$"
)
_NUMBER_TOKEN = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][-+]?\d+)?")
_MESH = re.compile(r"InitMesh:\s*MESH\s*=\s*(\d+)\s*x\s*(\d+)\s*x\s*(\d+)", re.IGNORECASE)
_FAILURE = re.compile(r"SCF_NOT_CONV|SCF:\s*not\s+converged|ABNORMAL_TERMINATION|MPI_Abort", re.IGNORECASE)


def _completion(text: str) -> bool:
    return bool(
        re.search(r"siesta:\s*normal completion", text, re.IGNORECASE)
        or (
            re.search(r">>\s*End of run:", text, re.IGNORECASE)
            and re.search(r"^\s*Job completed\s*$", text, re.IGNORECASE | re.MULTILINE)
        )
    )


def _half_width(token: str) -> float:
    normalized = token.replace("D", "E").replace("d", "e")
    mantissa, marker, exponent = normalized.lower().partition("e")
    places = len(mantissa.split(".", 1)[1]) if "." in mantissa else 0
    return 0.5 * 10.0 ** ((int(exponent) if marker else 0) - places)


def _final_moments(text: str, atom_count: int) -> tuple[MomentEvidence, ...]:
    """Read the last complete Mulliken table without treating it as convergence proof."""
    if _completion(text) and not _FAILURE.search(text):
        # Preserve the existing audited parser as the admission check for ordinary
        # completed outputs; the local reader below also retains evidence from
        # diagnostic outputs whose SCF did not converge. Some archived references
        # intentionally disable Mulliken printing, which means moments are absent.
        try:
            parse_final_collinear_mulliken_sz(text, atom_count)
        except ReferenceMagneticEvidenceError:
            pass
    lines = text.splitlines()
    tables: list[dict[int, tuple[float, float]]] = []
    for start, line in enumerate(lines):
        if not _MULLIKEN_START.match(line):
            continue
        cursor = start + 1
        while cursor < len(lines) and not _MULLIKEN_HEADER.match(lines[cursor]):
            if _MULLIKEN_START.match(lines[cursor]):
                break
            cursor += 1
        if cursor == len(lines) or not _MULLIKEN_HEADER.match(lines[cursor]):
            continue
        cursor += 1
        rows: dict[int, tuple[float, float]] = {}
        while cursor < len(lines) and not re.match(r"^\s*-{5,}\s*$", lines[cursor]):
            if lines[cursor].strip():
                match = _MULLIKEN_ROW.match(lines[cursor])
                if match is None:
                    rows.clear()
                    break
                index = int(match.group("index"))
                row_tokens = lines[cursor].split()
                if len(row_tokens) < 5 or index in rows:
                    rows.clear()
                    break
                rows[index] = (
                    float(match.group("sz").replace("D", "E").replace("d", "e")),
                    _half_width(row_tokens[3]),
                )
            cursor += 1
        if set(rows) == set(range(1, atom_count + 1)):
            tables.append(rows)
    if not tables:
        return ()
    return tuple(MomentEvidence(i - 1, *tables[-1][i]) for i in range(1, atom_count + 1))


def _k_mesh(text: str) -> tuple[tuple[int, int, int, float], ...] | None:
    lines = text.splitlines()
    blocks: list[tuple[tuple[int, int, int, float], ...]] = []
    for index, line in enumerate(lines):
        if re.match(r"^\s*%block\s+kgrid_monkhorst_pack\s*$", line, re.IGNORECASE):
            rows: list[tuple[int, int, int, float]] = []
            cursor = index + 1
            while cursor < len(lines) and not re.match(r"^\s*%endblock", lines[cursor], re.IGNORECASE):
                tokens = lines[cursor].split("#", 1)[0].split()
                if tokens:
                    if len(tokens) != 4:
                        return None
                    try:
                        first = tuple(int(token) for token in tokens[:3])
                        shift = float(tokens[3].replace("D", "E").replace("d", "e"))
                    except ValueError:
                        return None
                    if len(first) != 3 or not math.isfinite(shift):
                        return None
                    rows.append((first[0], first[1], first[2], shift))
                cursor += 1
            if len(rows) == 3 and cursor < len(lines):
                blocks.append(tuple(rows))
    return blocks[-1] if blocks else None


def _spectrum_evidence(
    text: str,
    event: HubbardPopulationEvent,
    subspaces: Sequence[CorrelatedSubspaceLike],
    species_by_atom: dict[int, int],
) -> tuple[SubspaceOccupationEvidence, ...]:
    if not subspaces:
        return ()
    read_printed_matrix_trace_precision(text, event)
    by_atom = {atom.atom_index: atom for atom in event.atoms}
    output: list[SubspaceOccupationEvidence] = []
    lines = text.splitlines()
    for subspace in sorted(subspaces, key=lambda item: (item.atom_index, item.site_id)):
        output_atom_index = subspace.atom_index + 1
        atom = by_atom.get(output_atom_index)
        if atom is None:
            raise ReferenceStateEvidenceError(
                f"la población local no contiene el átomo correlacionado {output_atom_index}"
            )
        if atom.species_index != species_by_atom[subspace.atom_index]:
            raise ReferenceStateEvidenceError(
                f"el índice de especie de salida no coincide para el átomo {output_atom_index}"
            )
        if event.source_start_line is None or event.source_end_line is None:
            raise ReferenceStateEvidenceError("evento de ocupaciones sin límites de líneas")
        matrices: dict[str, list[list[str]]] = {"up": []}
        if atom.raw_matrix_down is not None:
            matrices["down"] = []
        current_atom: int | None = None
        for line in lines[event.source_start_line : event.source_end_line + 1]:
            match_atom = re.search(r"hubbard_term:\s+atom,\s+species:\s+(\d+)\s+(\d+)", line)
            if match_atom:
                current_atom = int(match_atom.group(1))
                continue
            if current_atom != output_atom_index:
                continue
            matrix_pattern = (
                r"^\s*([1-9]\d*)\s+([1-9]\d*)\s+("
                + _NUMBER_TOKEN.pattern
                + r")(?:\s+("
                + _NUMBER_TOKEN.pattern
                + r"))?\s*$"
            )
            matrix_match = re.match(matrix_pattern, line)
            if matrix_match:
                row, col = int(matrix_match.group(1)), int(matrix_match.group(2))
                if row > len(atom.raw_matrix_up) or col > len(atom.raw_matrix_up):
                    raise ReferenceStateEvidenceError("índice de matriz local fuera de dimensión")
                while len(matrices["up"]) < row:
                    matrices["up"].append([""] * len(atom.raw_matrix_up))
                    if "down" in matrices:
                        matrices["down"].append([""] * len(atom.raw_matrix_up))
                matrices["up"][row - 1][col - 1] = matrix_match.group(3)
                if "down" in matrices:
                    if matrix_match.group(4) is None:
                        raise ReferenceStateEvidenceError("entrada down-spin ausente en la matriz local")
                    matrices["down"][row - 1][col - 1] = matrix_match.group(4)
        spectra: list[OccupationSpectrum] = []
        for spin, tokens_by_row in matrices.items():
            if len(tokens_by_row) != atom.raw_matrix_up.shape[0] or any(
                not value for row in tokens_by_row for value in row
            ):
                raise ReferenceStateEvidenceError(f"matriz local {spin} incompleta para {subspace.site_id}")
            array = np.asarray(
                [
                    [float(token.replace("D", "E").replace("d", "e")) for token in row]
                    for row in tokens_by_row
                ],
                dtype=float,
            )
            if not np.isfinite(array).all():
                raise ReferenceStateEvidenceError("matriz local contiene valores no finitos")
            radii = tuple(tuple(_half_width(token) for token in row) for row in tokens_by_row)
            spectra.append(
                OccupationSpectrum(spin, tuple(float(x) for x in np.linalg.eigvalsh(array)), radii)
            )
        output.append(SubspaceOccupationEvidence(subspace.site_id, subspace.atom_index, tuple(spectra)))
    return tuple(output)


def _subspaces_from_population_event(
    event: HubbardPopulationEvent,
    model: FdfModel,
) -> tuple[_OutputSubspace, ...]:
    """Map printed Hubbard projector blocks to FDF atoms without inferring sites.

    Some archived reference FDFs omit the DFTU block while their SIESTA output
    explicitly prints a local projector occupation event. In that case the
    event's atom/species pair is the source evidence for the local subspace.
    """
    by_index = {atom.atom_index: atom for atom in model.atoms}
    observed: list[_OutputSubspace] = []
    for item in event.atoms:
        atom_index = item.atom_index - 1
        fdf_atom = by_index.get(atom_index)
        if fdf_atom is None or fdf_atom.species_index != item.species_index:
            raise ReferenceStateEvidenceError(
                f"el índice de especie de salida no coincide para el átomo {item.atom_index}"
            )
        observed.append(_OutputSubspace(f"{fdf_atom.species_label}@{atom_index}", atom_index))
    return tuple(observed)


def build_reference_state_evidence(
    fdf_path: str | Path,
    output_path: str | Path,
    subspaces: Sequence[CorrelatedSubspaceLike],
) -> ReferenceStateEvidence:
    """Extract reference evidence; retain partial fields but fail admissibility closed."""
    fdf_file, output_file = Path(fdf_path), Path(output_path)
    output_bytes = output_file.read_bytes()
    output_text = output_bytes.decode("utf-8", errors="replace")
    model = parse_effective_fdf(fdf_file)
    if any(space.atom_index < 0 or space.atom_index >= model.number_of_atoms for space in subspaces):
        raise ReferenceStateEvidenceError("inventory contiene atom_index fuera del FDF")

    normal = _completion(output_text)
    converged = bool(
        re.search(r"^\s*SCF Convergence by .*criterion\s*$", output_text, re.IGNORECASE | re.MULTILINE)
    )
    if _FAILURE.search(output_text):
        converged = False
    moments = _final_moments(output_text, model.number_of_atoms)
    mesh_matches = _MESH.findall(output_text)
    mesh = (
        (int(mesh_matches[-1][0]), int(mesh_matches[-1][1]), int(mesh_matches[-1][2]))
        if mesh_matches
        else None
    )
    k_mesh = _k_mesh(output_text)

    occupation_evidence: tuple[SubspaceOccupationEvidence, ...] = ()
    occupation_status = OccupationSpectraStatus.NOT_AVAILABLE
    occupation_failure = StateEvidenceReason.OCCUPATION_SPECTRA_NOT_AVAILABLE
    events: list[HubbardPopulationEvent] = []
    selected_event: HubbardPopulationEvent | None = None
    try:
        events = parse_hubbard_population_events(output_text)
        complete_events = [event for event in events if event.atoms]
        if complete_events:
            selected_event = complete_events[-1]
            active_subspaces = subspaces or _subspaces_from_population_event(selected_event, model)
        else:
            active_subspaces = ()
        if active_subspaces:
            assert selected_event is not None
            species_by_atom = {atom.atom_index: atom.species_index for atom in model.atoms}
            occupation_evidence = _spectrum_evidence(
                output_text, selected_event, active_subspaces, species_by_atom
            )
            occupation_status = OccupationSpectraStatus.AVAILABLE
    except (ValueError, IndexError, SiestaParserError, SemanticValidationFailure):
        occupation_failure = StateEvidenceReason.OCCUPATION_SPECTRA_INCOMPLETE

    reasons: set[StateEvidenceReason] = set()
    if not normal:
        reasons.add(StateEvidenceReason.NORMAL_COMPLETION_MISSING)
    if not converged:
        reasons.add(StateEvidenceReason.SCF_NOT_CONVERGED)
    if not moments:
        reasons.add(StateEvidenceReason.MOMENTS_MISSING)
    if mesh is None:
        reasons.add(StateEvidenceReason.INIT_MESH_MISSING)
    if k_mesh is None:
        reasons.add(StateEvidenceReason.K_MESH_MISSING)
    if (subspaces or events) and occupation_status is OccupationSpectraStatus.NOT_AVAILABLE:
        reasons.add(occupation_failure)
    status = EvidenceStatus.REFERENCE_NOT_ADMISSIBLE if reasons else EvidenceStatus.ADMISSIBLE
    return ReferenceStateEvidence(
        model.effective_fdf_sha256,
        sha256(output_bytes).hexdigest(),
        normal,
        converged,
        moments,
        mesh,
        k_mesh,
        occupation_status,
        occupation_evidence,
        status,
        tuple(sorted(reasons, key=lambda item: item.value)),
    )
