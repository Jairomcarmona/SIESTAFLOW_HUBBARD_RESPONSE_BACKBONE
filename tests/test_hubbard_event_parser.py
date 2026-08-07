import pytest
import numpy as np
from siestaflow_hubbard.siesta_backend.event_parser import (
    parse_hubbard_population_events,
    ParseSemanticMismatch,
    UnsupportedSpinFormat
)
from siestaflow_hubbard.domain.exceptions import SiestaParserError

def test_single_atom_single_event():
    out = """
hubbard_term: recalculating local occupations 1
  hubbard_term: projector occupations
  hubbard_term: atom, species:    1    1
    1    1    0.1234
    Occupations:   0.1234   0.1234
siesta: iscf = 2
"""
    events = parse_hubbard_population_events(out)
    assert len(events) == 1
    assert events[0].occurrence_index == 0
    assert events[0].dftu_population_iteration == 1
    assert len(events[0].atoms) == 1
    
    atom = events[0].atoms[0]
    assert atom.atom_index == 1
    assert atom.species_index == 1
    assert atom.channel_count == 1
    assert atom.raw_matrix_up.shape == (1, 1)
    assert np.isclose(atom.trace_total, 0.2468) # 0.1234 * 2 (because non-pol occupations are printed twice and total is sum of both per our generic logic, wait. If non pol it prints 0.1234 0.1234. Our logic says trace_up + trace_up. 0.1234 + 0.1234 = 0.2468)
    assert np.isclose(atom.printed_total_trace, 0.2468)

def test_multiple_atoms_single_event():
    out = """
hubbard_term: recalculating local occupations 1
  hubbard_term: atom, species:    1    1
    1    1    0.5
    Occupations:   0.5   0.5
  hubbard_term: atom, species:    2    1
    1    1    0.3
    Occupations:   0.3   0.3
recalculating Hamiltonian
"""
    events = parse_hubbard_population_events(out)
    assert len(events) == 1
    assert len(events[0].atoms) == 2
    assert events[0].atoms[0].atom_index == 1
    assert events[0].atoms[1].atom_index == 2

def test_multiple_atoms_multiple_events():
    out = """
siesta: iscf = 1
hubbard_term: recalculating local occupations 1
  hubbard_term: atom, species:    1    1
    1    1    0.5
    Occupations:   0.5   0.5
recalculating Hamiltonian

siesta: iscf = 2
hubbard_term: recalculating local occupations 2
  hubbard_term: atom, species:    1    1
    1    1    0.6
    Occupations:   0.6   0.6
"""
    events = parse_hubbard_population_events(out)
    assert len(events) == 2
    assert events[0].scf_iteration == 1
    assert events[1].scf_iteration == 2

def test_spin_polarized_collinear():
    out = """
hubbard_term: recalculating local occupations 1
  hubbard_term: atom, species:    1    1
    1    1    0.5   0.2
    2    2    0.1   0.1
    1    2    0.0   0.0
    2    1    0.0   0.0
    Occupations:   0.60000   0.30000   0.90000
recalculating Hamiltonian
"""
    events = parse_hubbard_population_events(out)
    assert len(events) == 1
    atom = events[0].atoms[0]
    assert atom.channel_count == 2
    assert np.isclose(atom.trace_up, 0.6)
    assert np.isclose(atom.trace_down, 0.3)
    assert np.isclose(atom.trace_total, 0.9)

def test_corruption_missing_element():
    out = """
hubbard_term: recalculating local occupations 1
  hubbard_term: atom, species:    1    1
    1    1    0.5
    2    2    0.1
    1    2    0.0
    Occupations:   0.6   0.6
"""
    # 3 elements provided but max index is 2 -> requires 4 elements
    with pytest.raises(SiestaParserError, match="Matrix incomplete or truncated"):
        parse_hubbard_population_events(out)

def test_corruption_duplicate_element():
    out = """
hubbard_term: recalculating local occupations 1
  hubbard_term: atom, species:    1    1
    1    1    0.5
    1    1    0.5
    Occupations:   1.0   1.0
"""
    with pytest.raises(SiestaParserError, match="Duplicate matrix index"):
        parse_hubbard_population_events(out)

def test_corruption_trace_mismatch():
    out = """
hubbard_term: recalculating local occupations 1
  hubbard_term: atom, species:    1    1
    1    1    0.5
    Occupations:   0.9   0.9
"""
    with pytest.raises(ParseSemanticMismatch, match="Trace mismatch"):
        parse_hubbard_population_events(out)

def test_adversarial_old_parser_reproduction():
    """
    Simulates blocks[-1] logic failure. The old parser splits by 'recalculating local occupations'
    and takes blocks[-1]. Here, event 1 and 2 are present. The old parser would ONLY see event 2.
    The new parser must see both.
    """
    out = """
hubbard_term: recalculating local occupations 1
  hubbard_term: atom, species:    1    1
    1    1    0.1
    Occupations:   0.1   0.1
recalculating Hamiltonian
hubbard_term: recalculating local occupations 2
  hubbard_term: atom, species:    1    1
    1    1    0.2
    Occupations:   0.2   0.2
recalculating Hamiltonian
"""
    # Old parser logic
    blocks = out.split('hubbard_term: recalculating local occupations')
    last_block = blocks[-1]
    assert "0.2" in last_block
    assert "0.1" not in last_block # Proves it loses event 1
    
    # New parser logic
    events = parse_hubbard_population_events(out)
    assert len(events) == 2
    assert events[0].atoms[0].raw_matrix_up[0, 0] == 0.1
    assert events[1].atoms[0].raw_matrix_up[0, 0] == 0.2
