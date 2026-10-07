# mypy: disable-error-code=import-untyped
import re
from pathlib import Path

from hubbardflow.siesta_backend.siesta542_bare_profile import (
    Siesta542PotentialShiftHamiltonianProfile,
)

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "lr06_siesta542_yoltla_extract.txt"


def _mapped_native_line(
    lines: list[str], source_line_index: int, section_header: str, native_start_line: int
) -> int:
    section_start = lines.index(section_header) + 1
    return native_start_line + source_line_index - section_start


def test_real_yoltla_trace_selects_population_between_stepf_and_first_scf() -> None:
    """The production profile selects the real perturbed block, not its precursor."""
    lines = FIXTURE.read_text(encoding="utf-8").splitlines()
    output = "\n".join(lines)
    selection = Siesta542PotentialShiftHamiltonianProfile().select_response(output)

    assert selection.pre_perturbation_event.occurrence_index == 0
    assert selection.response_event.occurrence_index == 1
    assert selection.response_event.dftu_population_iteration == 1
    assert len(selection.response_event.atoms) == 1
    atom = selection.response_event.atoms[0]
    assert atom.printed_up_trace == 3.731167
    assert atom.printed_down_trace == 0.965385
    assert atom.printed_total_trace == 4.696552

    old_summary = "Occupations:     3.721022    0.952897    4.673919"
    response_summary = "Occupations:     3.731167    0.965385    4.696552"
    old_summary_index = lines.index(old_summary)
    response_summary_index = lines.index(response_summary)
    assert old_summary_index < selection.stepf_line
    assert selection.response_event.source_start_line is not None
    assert selection.response_event.source_end_line is not None
    assert selection.response_event.source_start_line < response_summary_index
    assert response_summary_index <= selection.response_event.source_end_line

    response_section = "# Native output lines 4515-4579; verbatim trace lines 70-134:"
    stepf_native_line = _mapped_native_line(
        lines, selection.stepf_line, response_section, native_start_line=4515
    )
    scf_native_line = _mapped_native_line(
        lines, selection.first_scf_line, response_section, native_start_line=4515
    )
    summary_native_line = _mapped_native_line(
        lines, response_summary_index, response_section, native_start_line=4515
    )
    old_summary_native_line = _mapped_native_line(
        lines,
        old_summary_index,
        "# Native output lines 4483-4514; complete pre-perturbation population event:",
        native_start_line=4483,
    )

    assert stepf_native_line == 4516
    assert scf_native_line == 4575
    assert summary_native_line == 4546
    # In the supplied 142-line evidence trace, native line N maps to trace line N-4445.
    assert old_summary_native_line - 4445 == 67
    assert stepf_native_line - 4445 == 71
    assert summary_native_line - 4445 == 101
    assert scf_native_line - 4445 == 130
    assert re.match(r"^\s+scf:\s+1\b", lines[selection.first_scf_line])

    not_converged_index = next(index for index, line in enumerate(lines) if line.startswith("SCF_NOT_CONV:"))
    assert not_converged_index > selection.first_scf_line
    assert "maximum number of steps" in lines[not_converged_index]
    not_converged_native_line = _mapped_native_line(
        lines, not_converged_index, response_section, native_start_line=4515
    )
    assert not_converged_native_line - 4445 == 133
