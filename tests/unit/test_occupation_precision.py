import pytest

from siestaflow_hubbard.siesta_backend.event_parser import parse_hubbard_population_events
from siestaflow_hubbard.siesta_backend.occupation_precision import read_printed_occupation_precision


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
