from __future__ import annotations

import re
from pathlib import Path

import pytest

from hubbardflow.execution.occupation_provenance import reconstruct_occupation_provenance
from hubbardflow.reporting.hubbardflow_ascii_report import render_hubbardflow_out
from hubbardflow.siesta_backend.event_parser import parse_hubbard_population_events
from hubbardflow.siesta_backend.occupation_precision import read_printed_occupation_precision
from hubbardflow.siesta_backend.parser_models import HubbardPopulationEvent
from hubbardflow.siesta_backend.point_state_evidence import parse_point_state_matrix_blocks
from hubbardflow.siesta_backend.reference_magnetic_evidence import (
    PopulationSpinEvidenceError,
    require_verified_population_spin_mode,
)
from hubbardflow.siesta_backend.siesta542_bare_profile import (
    Siesta542PotentialShiftHamiltonianProfile,
)

ROOT = Path(__file__).resolve().parents[2]
TESTS = Path(__file__).resolve().parents[1]
FIXTURE = TESTS / "fixtures" / "cu3n_nonpol_excerpt.txt"
NONPOLARIZED_FDF = "Spin non-polarized\n"


def _fixture() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def _source_line(lines: list[str], physical_index: int) -> int:
    excerpt_header = next(index for index, line in enumerate(lines) if line == "# EXCERPT 6385-6500")
    return 6385 + physical_index - excerpt_header - 1


def _response_event_from_excerpt(text: str) -> tuple[HubbardPopulationEvent, list[str], int, int]:
    lines = text.splitlines()
    stepf = next(
        index
        for index, line in enumerate(lines)
        if re.match(r"^\s*stepf:\s+Fermi-Dirac step function\s*$", line)
    )
    first_scf = next(
        index for index, line in enumerate(lines) if index > stepf and re.match(r"^\s*scf:\s+1\b", line)
    )
    candidates = [
        event
        for event in parse_hubbard_population_events(text)
        if event.source_start_line is not None
        and event.source_end_line is not None
        and stepf < event.source_start_line
        and event.source_end_line < first_scf
    ]
    assert len(candidates) == 1
    return candidates[0], lines, stepf, first_scf


def test_real_excerpt_selects_only_the_population_between_stepf_and_first_scf() -> None:
    text = _fixture()
    event, lines, stepf, first_scf = _response_event_from_excerpt(text)
    occupation_lines = [index for index, line in enumerate(lines) if "Occupations:" in line]

    assert len(lines) == 124
    assert [_source_line(lines, index) for index in occupation_lines] == [6389, 6423, 6488]
    assert _source_line(lines, stepf) < 6423 < _source_line(lines, first_scf)
    assert event.source_start_line is not None and event.source_end_line is not None
    assert all(
        event.source_start_line <= index <= event.source_end_line
        for index in occupation_lines
        if _source_line(lines, index) == 6423
    )
    assert all(
        not event.source_start_line <= index <= event.source_end_line
        for index in occupation_lines
        if _source_line(lines, index) in {6389, 6488}
    )
    assert "SCF_NOT_CONV" in text


def test_bare_profile_accepts_the_real_one_column_block_when_both_spin_sources_are_verified() -> None:
    text = _fixture()
    event, lines, _, _ = _response_event_from_excerpt(text)
    assert event.source_start_line is not None and event.source_end_line is not None
    actual_population_block = lines[event.source_start_line : event.source_end_line + 2]
    spin_attestation = [
        line
        for line in lines
        if re.search(r"redata:\s*(Spin configuration|Number of spin components|Time-Reversal Symmetry)", line)
    ]
    scf_summary = next(
        line.split(":", 1)[1].strip() for line in lines if re.match(r"^\d+:\s+scf:\s+1\b", line)
    )
    scf_not_converged = next(line for line in lines if line.startswith("SCF_NOT_CONV"))
    complete_profile_output = "\n".join(
        [
            "redata: SCF mix quantity = Hamiltonian",
            *spin_attestation,
            *actual_population_block,
            "recalculating Hamiltonian",
            "stepf: Fermi-Dirac step function",
            *actual_population_block,
            "recalculating Hamiltonian",
            scf_summary,
            scf_not_converged,
        ]
    )

    selection = Siesta542PotentialShiftHamiltonianProfile().select_response(
        complete_profile_output,
        fdf_text=NONPOLARIZED_FDF,
    )

    assert selection.response_event.atoms[0].channel_count == 1
    assert selection.response_event.atoms[0].printed_total_trace == 9.584734


def test_nonpolarized_total_is_twice_the_printed_per_spin_value_and_is_marked_derived() -> None:
    text = _fixture()
    event, _, _, _ = _response_event_from_excerpt(text)
    assert require_verified_population_spin_mode(event, NONPOLARIZED_FDF, text) is True

    measured = read_printed_occupation_precision(text, event, fdf_text=NONPOLARIZED_FDF)[1]
    matrix = parse_point_state_matrix_blocks(event, text, fdf_text=NONPOLARIZED_FDF)[0]

    assert measured.printed_tokens == ("4.792367", "4.792367")
    assert measured.per_spin_occupation_e == 4.792367
    assert measured.total == 9.584734
    assert measured.total == 2 * measured.per_spin_occupation_e
    assert measured.total_derived is True
    assert matrix.total_occupation_e == 9.584734
    assert matrix.total_derived is True
    assert tuple(float(matrix.matrix_up[index][index]) for index in range(5)) == (
        0.97839,
        0.97583,
        0.94950,
        0.97839,
        0.91026,
    )
    assert matrix.matrix_down == matrix.matrix_up
    assert (
        abs(sum(float(matrix.matrix_up[i][i]) for i in range(5)) - measured.per_spin_occupation_e) <= 2.55e-5
    )


def test_provenance_record_persists_the_derived_total_from_the_real_excerpt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    text = _fixture()
    event, _, _, _ = _response_event_from_excerpt(text)

    class Selection:
        response_event = event

    monkeypatch.setattr(
        Siesta542PotentialShiftHamiltonianProfile,
        "select_response",
        lambda self, output_text, *, fdf_text=None: Selection(),
    )
    fdf_path = tmp_path / "input.fdf"
    fdf_path.write_text(NONPOLARIZED_FDF, encoding="utf-8")
    result = reconstruct_occupation_provenance(
        {
            "rows": [
                {
                    "perturbed_site_id": "Cu1",
                    "alpha_eV": 0.1,
                    "observed_sites": [
                        {
                            "observed_site_index": 0,
                            "observed_site_id": "Cu1",
                            "occupations_electron": {"bare": 9.584734},
                        }
                    ],
                    "sources": {
                        "bare": {
                            "mode": "BARE",
                            "out_path": str(FIXTURE),
                            "fdf_path": str(fdf_path),
                        }
                    },
                }
            ],
            "site_index_map": [{"index": 0, "site_id": "Cu1", "atom_index": 1}],
            "reference_source": {},
        },
        campaign_root=tmp_path,
    )

    record = next(item for item in result.records if item.mode == "BARE")
    assert record.occupation_at_selected_block_electron == 9.584734
    assert record.per_spin_occupation_e == 4.792367
    assert record.total_derived is True
    assert record.to_mapping()["total_derived"] is True


@pytest.mark.parametrize("fdf_text", [None, "Spin polarized\n"])
def test_one_column_population_fails_closed_without_verified_fdf(fdf_text: str | None) -> None:
    text = _fixture()
    event, _, _, _ = _response_event_from_excerpt(text)
    with pytest.raises(PopulationSpinEvidenceError, match="one-column population matrix requires"):
        read_printed_occupation_precision(text, event, fdf_text=fdf_text)
    with pytest.raises(PopulationSpinEvidenceError, match="one-column population matrix requires"):
        parse_point_state_matrix_blocks(event, text, fdf_text=fdf_text)


def test_one_column_population_fails_closed_when_output_spin_markers_are_incomplete() -> None:
    text = _fixture().replace(
        "Time-Reversal Symmetry                      = T",
        "Time-Reversal Symmetry                      = F",
        1,
    )
    event, _, _, _ = _response_event_from_excerpt(text)
    with pytest.raises(PopulationSpinEvidenceError, match="one-column population matrix requires"):
        parse_point_state_matrix_blocks(event, text, fdf_text=NONPOLARIZED_FDF)


def test_polarized_population_precision_keeps_existing_explicit_total_behavior() -> None:
    text = (ROOT / "examples" / "MnO_BARE_+0.05.out").read_text(encoding="utf-8")
    event = Siesta542PotentialShiftHamiltonianProfile().select_response(text).response_event
    measurement = read_printed_occupation_precision(text, event)[1]

    assert measurement.total_derived is False
    assert measurement.per_spin_occupation_e is None


def test_report_discloses_nonpolarized_total_and_reference_d_shell_occupation() -> None:
    report = render_hubbardflow_out(
        {
            "analysis": {
                "projector_diagnostics": {
                    "sites": [
                        {
                            "site_id": "Cu1",
                            "reference_occupation_e": 9.584734,
                            "formal_d_electrons": 10.0,
                            "free_atom_d_electrons": 9.0,
                            "u_times_abs_chi0": 0.1,
                            "regime_indicator_status": "RECORDED",
                        }
                    ],
                },
            },
            "occupation_provenance": {"records": [{"total_derived": True}]},
        }
    )

    assert "spin treatment: non-polarized; occupation = 2 x printed per-spin value" in report
    assert "Reference total d-shell occupation (derived from printed per-spin values):" in report
    assert "Cu1: 9.584734 e" in report
