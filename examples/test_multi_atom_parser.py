import os
import sys
import pytest
import numpy as np

# Ensure examples directory is on sys.path
sys.path.insert(0, os.path.dirname(__file__))

from siesta_adapter import SiestaAdapter, ChecksumFailure

REAL_OUTPUT_PATH = r"C:\Users\Jairo\.gemini\antigravity\brain\2b84ddef-8494-4411-bfef-c3cc4d2870ea\scratch\full_output.txt"

def test_parse_real_output_multi_atom():
    adapter = SiestaAdapter()
    parsed = adapter.parse_converged_hubbard_occupations(REAL_OUTPUT_PATH)
    
    atoms = {k: v for k, v in parsed.items() if isinstance(k, int)}
    
    # 1. Verify it returns > 1 atom
    assert len(atoms) > 1, f"Expected >1 atom, but found {len(atoms)}"
    
    # 2. Verify max_change field is present
    assert "max_change" in parsed, "Expected 'max_change' field in parsed results"
    assert isinstance(parsed["max_change"], float)
    
    # 3. Verify each atom has checksums passing (traces match printed values within 1e-4)
    for atom_idx, data in atoms.items():
        assert "species" in data
        assert "matrix_up" in data
        assert "matrix_down" in data
        assert "trace_up" in data
        assert "trace_down" in data
        assert "trace_total" in data
        
        computed_up = float(np.trace(data["matrix_up"]))
        computed_down = float(np.trace(data["matrix_down"]))
        
        assert abs(computed_up - data["trace_up"]) < 1e-4, f"Atom {atom_idx} spin-up trace mismatch"
        assert abs(computed_down - data["trace_down"]) < 1e-4, f"Atom {atom_idx} spin-down trace mismatch"
        assert abs((computed_up + computed_down) - data["trace_total"]) < 1e-4, f"Atom {atom_idx} total trace mismatch"

def test_parse_returns_5x5_matrices():
    adapter = SiestaAdapter()
    parsed = adapter.parse_converged_hubbard_occupations(REAL_OUTPUT_PATH)
    atoms = {k: v for k, v in parsed.items() if isinstance(k, int)}
    
    for atom_idx, data in atoms.items():
        assert data["matrix_up"].shape == (5, 5), f"Atom {atom_idx} spin-up matrix shape is {data['matrix_up'].shape}"
        assert data["matrix_down"].shape == (5, 5), f"Atom {atom_idx} spin-down matrix shape is {data['matrix_down'].shape}"

def test_diagonal_elements_positive():
    adapter = SiestaAdapter()
    parsed = adapter.parse_converged_hubbard_occupations(REAL_OUTPUT_PATH)
    atoms = {k: v for k, v in parsed.items() if isinstance(k, int)}
    
    for atom_idx, data in atoms.items():
        diag_up = np.diagonal(data["matrix_up"])
        diag_down = np.diagonal(data["matrix_down"])
        
        assert np.all(diag_up > 0), f"Atom {atom_idx} spin-up diagonal elements not all positive: {diag_up}"
        assert np.all(diag_down > 0), f"Atom {atom_idx} spin-down diagonal elements not all positive: {diag_down}"
