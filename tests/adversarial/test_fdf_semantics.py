import pytest
import re
from siestaflow_hubbard.siesta_backend.fdf_builder import FdfBuilder
from siestaflow_hubbard.siesta_backend.dftu_models import DftuProjectorBlock, DftuProjector

@pytest.fixture
def valid_block():
    return DftuProjectorBlock(
        species="Mn",
        projectors=[
            DftuProjector(n=3, l=2, U=0.0, J=0.0, rc=4.5, omega=0.11, lambda_factor=None)
        ]
    )

@pytest.fixture
def base_builder():
    # We no longer pass block to FdfBuilder, since we removed it from __init__ earlier.
    # The actual implementation of FdfBuilder in fdf_builder.py doesn't take block in __init__
    return FdfBuilder(base_fdf_path=None)

@pytest.fixture
def valid_fdf(base_builder):
    fdf = base_builder.prepare_fdf_bare(
        base_fdf_path="mock_path.fdf",
        target_fdf_path="out.fdf",
        alpha=0.05
    )
    # the prepare method requires a real file.
    # Instead, let's manually generate a valid FDF snippet for bare mode.
    # Wait, prepare_fdf_bare reads from base_fdf_path.
    return None

def generate_mock_fdf(species="Mn", n=3, l=2, u=0.05, j=0.0, rc=4.5, omega=0.11, lam=None, 
                      proj_method="pseudo", potential_shift=True, first_iter=True,
                      response_mode="SCREENED"):
    lines = []
    lines.append("%block DFTU.proj")
    lines.append(f"  {species}  1")
    lines.append(f"  {n}  {l}")
    lines.append(f"  {u:.4f}  {j:.4f}")
    lines.append(f"  {rc:.4f}  {omega:.4f}")
    if lam is not None:
        lines.append(f"  {lam:.4f}")
    lines.append("%endblock DFTU.proj")
    
    if proj_method: lines.append(f"DFTU.ProjectorGenerationMethod {proj_method}")
    if potential_shift: lines.append("DFTU.PotentialShift true")
    if first_iter: lines.append("DFTU.FirstIteration true")
    
    if response_mode == "BARE":
        lines.append("MaxSCFIterations 2")
        lines.append("SCF.MustConverge false")
        lines.append("DM.UseSaveDM true")
        lines.append("SCF.Mix density")
        lines.append("SCF.Mixer.Method linear")
        lines.append("SCF.Mixer.Weight 1.0")
        
    return "\n".join(lines)


def test_FDF_A_change_rc(base_builder, valid_block):
    fdf = generate_mock_fdf(rc=9.99)
    assert not base_builder.preflight_verify(fdf, expected_alpha=0.05, expected_block=valid_block, expected_response_mode="SCREENED")

def test_FDF_B_change_omega(base_builder, valid_block):
    fdf = generate_mock_fdf(omega=9.99)
    assert not base_builder.preflight_verify(fdf, expected_alpha=0.05, expected_block=valid_block, expected_response_mode="SCREENED")

def test_FDF_C_change_lambda(base_builder, valid_block):
    fdf = generate_mock_fdf(lam=2.5) # The base builder expects effective lambda = 1.0
    assert not base_builder.preflight_verify(fdf, expected_alpha=0.05, expected_block=valid_block, expected_response_mode="SCREENED")

def test_FDF_D_omit_lambda_vs_explicit_default(base_builder, valid_block):
    # Provide explicit lam=1.0 in FDF
    fdf_explicit = generate_mock_fdf(lam=1.0)
    assert base_builder.preflight_verify(fdf_explicit, expected_alpha=0.05, expected_block=valid_block, expected_response_mode="SCREENED")
    
    # Omit lambda in FDF
    fdf_omitted = generate_mock_fdf(lam=None)
    assert base_builder.preflight_verify(fdf_omitted, expected_alpha=0.05, expected_block=valid_block, expected_response_mode="SCREENED")

def test_FDF_E_place_alpha_in_omega(base_builder, valid_block):
    # Historical bug: alpha goes into omega spot, U is 0
    fdf = generate_mock_fdf(u=0.0, omega=0.05)
    assert not base_builder.preflight_verify(fdf, expected_alpha=0.05, expected_block=valid_block, expected_response_mode="SCREENED")

def test_FDF_F_change_projector_method(base_builder, valid_block):
    fdf = generate_mock_fdf(proj_method="other")
    assert not base_builder.preflight_verify(fdf, expected_alpha=0.05, expected_block=valid_block, expected_response_mode="SCREENED")

def test_bare_strict_requirements(base_builder, valid_block):
    fdf = generate_mock_fdf(response_mode="BARE")
    assert base_builder.preflight_verify(fdf, expected_alpha=0.05, expected_block=valid_block, expected_response_mode="BARE")
    
    # Missing SCF.Mix density
    fdf_bad = generate_mock_fdf(response_mode="SCREENED") # lacks the bare config
    assert not base_builder.preflight_verify(fdf_bad, expected_alpha=0.05, expected_block=valid_block, expected_response_mode="BARE")

# Mandatory Release Gate Tests: LAMBDA-01 through LAMBDA-04

def test_LAMBDA_01_omitted_lambda():
    p = DftuProjector(n=3, l=2, U=0.05, J=0.0, rc=4.5, omega=0.11, lambda_factor=None)
    assert p.effective_lambda == 1.0

def test_LAMBDA_02_explicit_default_fingerprint():
    p_omitted = DftuProjector(n=3, l=2, U=0.05, J=0.0, rc=4.5, omega=0.11, lambda_factor=None)
    p_explicit = DftuProjector(n=3, l=2, U=0.05, J=0.0, rc=4.5, omega=0.11, lambda_factor=1.0)
    assert p_omitted.get_fingerprint() == p_explicit.get_fingerprint()

def test_LAMBDA_03_different_lambda_fingerprint():
    p_default = DftuProjector(n=3, l=2, U=0.05, J=0.0, rc=4.5, omega=0.11, lambda_factor=None)
    p_custom = DftuProjector(n=3, l=2, U=0.05, J=0.0, rc=4.5, omega=0.11, lambda_factor=0.8)
    assert p_default.get_fingerprint() != p_custom.get_fingerprint()

def test_LAMBDA_04_tampered_lambda_preflight_fail(base_builder, valid_block):
    # valid_block has effective_lambda = 1.0 (lambda_factor=None)
    fdf_tampered = generate_mock_fdf(lam=0.8)
    assert not base_builder.preflight_verify(fdf_tampered, expected_alpha=0.05, expected_block=valid_block, expected_response_mode="SCREENED")

