import pytest
from siestaflow_hubbard.siesta_backend.fdf_builder import FdfBuilder
from siestaflow_hubbard.siesta_backend.dftu_models import DftuProjector, DftuProjectorBlock

@pytest.fixture
def dummy_base_fdf(tmp_path):
    fdf = tmp_path / "base.fdf"
    fdf.write_text("SystemLabel  test\nMaxSCFIterations 100\nDFTU.PotentialShift false\n%block DFTU.proj\n  Old format\n%endblock DFTU.proj")
    return str(fdf)

def test_dftu_projector_fingerprint_invariance():
    """Proves projector fingerprint remains invariant across alpha scan (U changes)."""
    p1 = DftuProjector(n=3, l=2, U=0.01, J=0.0, rc=3.0, omega=0.05)
    p2 = DftuProjector(n=3, l=2, U=0.10, J=0.0, rc=3.0, omega=0.05)
    
    assert p1.get_fingerprint() == p2.get_fingerprint(), "Fingerprint must be invariant with respect to U"
    
    p3 = DftuProjector(n=3, l=2, U=0.10, J=0.0, rc=3.5, omega=0.05)
    assert p1.get_fingerprint() != p3.get_fingerprint(), "Fingerprint must change if rc changes"

def test_fdf_builder_safe_materialization(dummy_base_fdf, tmp_path):
    """Tests the round-trip materialization, bool replacement, and preflight verification."""
    builder = FdfBuilder()
    target_fdf = str(tmp_path / "target.fdf")
    
    alpha_val = 0.05
    modified_content = builder.prepare_fdf(
        base_fdf_path=dummy_base_fdf,
        target_fdf_path=target_fdf,
        alpha=alpha_val,
        run_name="safe_run",
        response_mode="SCREENED",
        species="Fe",
        rc=4.2,
        omega=0.07,
        lambda_factor=1.1
    )
    
    # Assert Booleans are correctly written (by value override)
    assert "DFTU.PotentialShift true" in modified_content
    assert "DFTU.FirstIteration true" in modified_content
    # The old false must be gone
    assert "DFTU.PotentialShift false" not in modified_content
    
    # Create the expected block for verification
    expected_proj = DftuProjector(n=3, l=2, U=alpha_val, J=0.0, rc=4.2, omega=0.07, lambda_factor=1.1)
    expected_block = DftuProjectorBlock(species="Fe", projectors=[expected_proj])
    
    # Assert preflight verifies the correct physical values
    assert builder.preflight_verify(modified_content, expected_alpha=alpha_val, expected_block=expected_block) == True
    
    # Assert wrong alpha fails
    assert builder.preflight_verify(modified_content, expected_alpha=0.10, expected_block=expected_block) == False

def test_adversarial_old_serializer_rejected():
    """
    Simulates the old serializer output and proves the semantic preflight catches it.
    Old serializer format:
      n l
      rc width
      u_val alpha
      j_val
    """
    old_broken_format = """
SystemLabel         test
DFTU.PotentialShift true
DFTU.FirstIteration true
%block DFTU.proj
  Mn   1
  3  2
  3.0000  0.0500
  0.0000  0.0100
  0.0000
%endblock DFTU.proj
"""
    # preflight expects U on the 3rd line. 
    # In the old format, the 3rd line is `rc width` (e.g. 3.0 0.05).
    # expected_alpha is 0.01.
    builder = FdfBuilder()
    
    expected_proj = DftuProjector(n=3, l=2, U=0.01, J=0.0, rc=3.0, omega=0.05)
    expected_block = DftuProjectorBlock(species="Mn", projectors=[expected_proj])
    
    # Preflight should fail because it expects U=0.01, J=0 on line 3, 
    # but finds 3.0 0.05 instead.
    assert builder.preflight_verify(old_broken_format, expected_alpha=0.01, expected_block=expected_block) == False

def test_bare_mode_overrides(dummy_base_fdf, tmp_path):
    """Tests that BARE mode correctly limits SCF iterations."""
    builder = FdfBuilder()
    target_fdf = str(tmp_path / "bare.fdf")
    
    content = builder.prepare_fdf_bare(
        base_fdf_path=dummy_base_fdf,
        target_fdf_path=target_fdf,
        alpha=0.05
    )
    
    assert "MaxSCFIterations 2" in content
    assert "SCF.Mixer.Weight 1.0" in content
