"""Tests for exact-precision state evidence from real NiO P5 runs."""

from __future__ import annotations

import lzma
from pathlib import Path

import pytest

from hubbardflow.domain.state_gate import BandEvidenceStatus
from hubbardflow.siesta_backend.point_state_evidence import (
    PointStateEvidenceError,
    build_point_state,
)
from hubbardflow.siesta_backend.siesta542_bare_profile import (
    Siesta542PotentialShiftHamiltonianProfile,
)
from hubbardflow.siesta_backend.siesta542_screened_selection import (
    select_converged_screened_event,
)

FIXTURES = Path(__file__).parents[1] / "fixtures" / "i5_eig"


def _read(name: str) -> str:
    return lzma.decompress((FIXTURES / name).read_bytes()).decode("utf-8")


@pytest.mark.parametrize(
    ("prefix", "selection"),
    [
        ("reference", "screened"),
        ("bare_p0p04", "bare"),
        ("screened_s1_p0p04", "screened"),
    ],
)
def test_real_reference_and_runs_preserve_print_precision(prefix: str, selection: str) -> None:
    output = _read(f"{prefix}.out.xz")
    if selection == "bare":
        event = Siesta542PotentialShiftHamiltonianProfile().select_response(output).response_event
    else:
        event = select_converged_screened_event(output)

    state = build_point_state(event, output, _read(f"{prefix}.EIG.xz"))

    assert len(state.atoms) == 2
    assert state.band_evidence_status is BandEvidenceStatus.AVAILABLE
    assert all(len(atom.matrix_up) == len(atom.matrix_down) == 5 for atom in state.atoms)
    assert all(atom.matrix_print_quantum_e == 1e-5 for atom in state.atoms)
    assert len(state.band_energies) == 64 * 2 * 23


def test_missing_eig_is_explicitly_not_available() -> None:
    output = _read("bare_p0p04.out.xz")
    event = Siesta542PotentialShiftHamiltonianProfile().select_response(output).response_event

    state = build_point_state(event, output)

    assert state.band_evidence_status is BandEvidenceStatus.NOT_AVAILABLE
    assert state.band_energies == ()


def test_truncated_selected_matrix_block_raises_typed_error() -> None:
    output = _read("bare_p0p04.out.xz")
    event = Siesta542PotentialShiftHamiltonianProfile().select_response(output).response_event
    selected_lines = output.splitlines()
    assert event.source_start_line is not None
    del selected_lines[event.source_start_line + 5]
    truncated = "\n".join(selected_lines)

    with pytest.raises(PointStateEvidenceError, match="truncated|indices"):
        build_point_state(event, truncated)


def test_unterminated_final_mulliken_table_raises_typed_error() -> None:
    output = _read("bare_p0p04.out.xz")
    event = Siesta542PotentialShiftHamiltonianProfile().select_response(output).response_event
    lines = output.splitlines()
    starts = [index for index, line in enumerate(lines) if line.strip() == "Mulliken Atomic Populations:"]
    assert starts
    terminator = next(
        index for index in range(starts[-1] + 1, len(lines)) if lines[index].strip().startswith("-----")
    )
    del lines[terminator]

    with pytest.raises(PointStateEvidenceError, match="no complete final Mulliken"):
        build_point_state(event, "\n".join(lines))
