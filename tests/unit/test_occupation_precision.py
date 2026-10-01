import pytest

from hubbardflow.siesta_backend.event_parser import parse_hubbard_population_events
from hubbardflow.siesta_backend.occupation_precision import (
    read_printed_matrix_trace_precision,
    read_printed_occupation_precision,
)
from hubbardflow.execution.campaign_runner import CampaignRunner


def _matrix_event(diagonal_token="0.10000", *, down_spin=True):
    places = len(diagonal_token.split(".", 1)[1])
    zero = "0." + "0" * places
    lines = ["hubbard_term: recalculating local occupations 1", "  hubbard_term: atom, species: 1 1"]
    for row in range(1, 6):
        for column in range(1, 6):
            up = diagonal_token if row == column else zero
            down = diagonal_token if row == column else zero
            lines.append(f"    {row} {column} {up}" + (f" {down}" if down_spin else ""))
    one_channel = 5 * float(diagonal_token)
    if down_spin:
        lines.append(f"    Occupations: {one_channel:.{places}f} {one_channel:.{places}f} {2 * one_channel:.{places}f}")
    else:
        lines.append(f"    Occupations: {one_channel:.{places}f} {one_channel:.{places}f}")
    lines.append("recalculating Hamiltonian")
    return "\n".join(lines)


def test_precision_adapter_reads_explicit_total_field_and_decimal_half_step():
    output = """
hubbard_term: recalculating local occupations 1
  hubbard_term: atom, species:    1    1
    1    1    0.20000   0.10000
    Occupations:   0.200000   0.100000   0.300001
recalculating Hamiltonian
"""
    event = parse_hubbard_population_events(output)[0]
    measured = read_printed_occupation_precision(output, event)[1]
    assert measured.total == pytest.approx(0.300001)
    assert measured.half_width == pytest.approx(5e-7)
    assert measured.decimal_places == 6


def test_campaign_observable_uses_occupations_total_not_matrix_trace():
    output = _matrix_event("0.10000", down_spin=True).replace(
        "Occupations: 0.50000 0.50000 1.00000",
        "Occupations: 0.500000 0.500000 1.000020",
    )
    event = parse_hubbard_population_events(output)[0]
    measured = read_printed_occupation_precision(output, event)[1]
    runner = object.__new__(CampaignRunner)
    runner._minimum_occupation_decimal_places = None
    selected = runner._event_occupations(output, event, [{"atom_index": 1}])
    assert selected == [1.000020]
    assert selected[0] != event.atoms[0].trace_total
    assert measured.half_width == pytest.approx(5e-7)


def test_precision_adapter_bounds_a_total_summed_from_two_printed_channels():
    output = """
hubbard_term: recalculating local occupations 1
  hubbard_term: atom, species:    1    1
    1    1    0.45679
    Occupations:   0.456789   0.456789
"""
    event = parse_hubbard_population_events(output)[0]
    measured = read_printed_occupation_precision(output, event)[1]
    assert measured.total == pytest.approx(0.913578)
    assert measured.half_width == pytest.approx(1e-6)


def test_matrix_trace_precision_sums_five_diagonals_across_two_spin_channels():
    output = _matrix_event("0.10000", down_spin=True)
    event = parse_hubbard_population_events(output)[0]
    measured = read_printed_matrix_trace_precision(output, event)[1]
    assert measured.total == pytest.approx(event.atoms[0].trace_total)
    assert measured.half_width == pytest.approx(5e-5)
    assert measured.decimal_places == 5
    assert measured.diagonal_term_count == 10


def test_matrix_trace_precision_does_not_substitute_a_higher_precision_summary():
    output = _matrix_event("0.10000", down_spin=True).replace(
        "Occupations: 0.50000 0.50000 1.00000",
        "Occupations: 0.500000 0.500000 1.000000",
    )
    event = parse_hubbard_population_events(output)[0]
    trace_width = read_printed_matrix_trace_precision(output, event)[1].half_width
    summary_width = read_printed_occupation_precision(output, event)[1].half_width
    assert trace_width == pytest.approx(5e-5)
    assert summary_width == pytest.approx(5e-7)
    assert trace_width != summary_width


def test_matrix_trace_precision_duplicates_up_channel_when_down_channel_is_absent():
    output = _matrix_event("0.10000", down_spin=False)
    event = parse_hubbard_population_events(output)[0]
    measured = read_printed_matrix_trace_precision(output, event)[1]
    assert event.atoms[0].raw_matrix_down is None
    assert measured.total == pytest.approx(event.atoms[0].trace_total)
    assert measured.half_width == pytest.approx(5e-5)
    assert measured.diagonal_term_count == 10


def test_matrix_trace_precision_uses_the_selected_event_token_precision():
    output = _matrix_event("0.10000") + "\n" + _matrix_event("0.1000")
    events = parse_hubbard_population_events(output)
    first = read_printed_matrix_trace_precision(output, events[0])[1]
    second = read_printed_matrix_trace_precision(output, events[1])[1]
    assert first.half_width == pytest.approx(5e-5)
    assert second.half_width == pytest.approx(5e-4)
