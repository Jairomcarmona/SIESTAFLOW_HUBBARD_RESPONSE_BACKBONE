import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parents[2] / "tools"))
from audit_method2_projector import (  # noqa: E402
    cumulative_norm,
    neighbour_distances,
    parse_fdf,
    parse_method2_parameters,
    parse_projector,
)


def test_method2_auditor_parses_fractional_geometry_and_radial_norm(tmp_path):
    fdf = tmp_path / "case.fdf"
    fdf.write_text(
        """LatticeConstant 1.0 Ang
%block LatticeVectors
 10 0 0
 0 10 0
 0 0 10
%endblock LatticeVectors
AtomicCoordinatesFormat Fractional
%block ChemicalSpeciesLabel
 1 25 MnLR00
 2 8 O
%endblock ChemicalSpeciesLabel
%block AtomicCoordinatesAndAtomicSpecies
 0 0 0 1
 0.2 0 0 2
%endblock AtomicCoordinatesAndAtomicSpecies
%block DFTU.Proj
 MnLR00 1
 3 2
 0.0 0.0
 3.0 0.05
%endblock DFTU.Proj
"""
    )
    projector = tmp_path / "MnLR00.dftu_proj"
    projector.write_text(
        """# DFT+U projectors
2 1 # l,n
4 1.0 3.0
0.0 1.0
1.0 1.0
2.0 0.0
3.0 0.0
"""
    )

    parsed = parse_fdf(fdf, "MnLR00")
    method2 = parse_method2_parameters(parsed["text"], "MnLR00")
    assert method2["n"] == 3
    assert method2["l"] == 2
    assert method2["rc_bohr"] == 3.0
    assert method2["cutoff_mode"] == "explicit_rc"
    assert neighbour_distances(parsed, "MnLR00")["nearest_any_neighbour_A"] == 2.0
    r, values, cutoff = parse_projector(projector)
    assert cutoff == 3.0
    norm = cumulative_norm(r, values)
    assert np.isclose(norm[-1], 1.0)
    assert np.all(np.diff(norm) >= 0.0)
