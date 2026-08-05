import pytest
import numpy as np
from siestaflow_hubbard.siesta_backend.fdf_validator import FdfValidator, FdfParser
from siestaflow_hubbard.domain.kgrid_builder import generate_kgrid, KGridBuilder
from siestaflow_hubbard.siesta_backend.fdf_builder import FdfBuilder

def test_unit_conversion():
    parser = FdfParser("")
    validator = FdfValidator(parser)
    assert validator.check_unit("10.0 Ang") == 10.0
    assert np.isclose(validator.check_unit("10.0 Bohr"), 5.29177)
    assert validator.check_unit("1.0 nm") == 10.0
    assert validator.check_unit("10.0") == 10.0

def test_spin_mode_detection():
    fdf = "SpinPolarized true\nNonCollinearSpin false\nSpinOrbit false"
    parser = FdfParser(fdf)
    validator = FdfValidator(parser)
    assert validator.detect_spin_mode() == "spin-polarized"

    fdf2 = "SpinPolarized false\nNonCollinearSpin true\nSpinOrbit false"
    assert FdfValidator(FdfParser(fdf2)).detect_spin_mode() == "non-collinear"
    
    fdf3 = "SpinOrbit true"
    assert FdfValidator(FdfParser(fdf3)).detect_spin_mode() == "spin-orbit"
    
    fdf4 = "SpinPolarized false"
    assert FdfValidator(FdfParser(fdf4)).detect_spin_mode() == "non-polarized"

def test_geometry_enforcement():
    fdf = "MD.TypeOfRun CG\nMD.NumCGsteps 50\nSystemLabel test\n"
    parser = FdfParser(fdf)
    validator = FdfValidator(parser)
    res = validator.enforce_fixed_geometry(fdf)
    assert "MD.NumCGsteps       0" in res
    assert "MD.TypeOfRun" not in res
    
def test_kgrid_generation():
    # Cubic
    lattice = np.array([[5.0, 0, 0], [0, 5.0, 0], [0, 0, 5.0]])
    grid = generate_kgrid(lattice, k_cutoff_ang=30.0)
    assert grid == [6, 6, 6]
    
    # Tetragonal
    lattice2 = np.array([[5.0, 0, 0], [0, 5.0, 0], [0, 0, 10.0]])
    grid2 = generate_kgrid(lattice2, k_cutoff_ang=30.0)
    assert grid2 == [6, 6, 3]
    
    # 2D slab
    grid3 = generate_kgrid(lattice2, k_cutoff_ang=30.0, is_2d=True)
    assert grid3 == [6, 6, 1]

def test_fdf_builder_integration():
    fdf = "MD.TypeOfRun CG\nMD.NumCGsteps 50\n"
    builder = FdfBuilder()
    mod = builder.modify_fdf_content(fdf, alpha=0.1)
    # Check that validator logic applies (builder should call validator)
    assert "MD.NumCGsteps       0" in mod
    assert "MD.TypeOfRun" not in mod
