import pytest
import numpy as np
from siestaflow_hubbard.domain.cardinals import Cardinals
from siestaflow_hubbard.domain.alpha_grid import AlphaGrid
from siestaflow_hubbard.domain.provenance import PerturbationIdentity, ObservableIdentity, ResponseMatrix
from siestaflow_hubbard.synthetic_backend.matrix_assembler import assemble_provenance_matrix, transform_to_chi
from siestaflow_hubbard.synthetic_backend.fit_engine import RegressionRecord

def test_S6A_1x1_recovery():
    """Test S6-A: 1x1 scalar recovery test."""
    grid = AlphaGrid([-0.1, 0.0, 0.1], 3, True, 1, 1, 1)
    cardinals = Cardinals(P=1, O=1, N=1, alpha_grids={"P0": grid}, A=np.array([[1.0]]))
    
    p_id = PerturbationIdentity("P0", "Ni_3d", "Projector_1", "hash_abc")
    o_id = ObservableIdentity("O0", "Ni_3d", "BARE")
    
    record = RegressionRecord(
        observable_index=0,
        channel_index=0,
        slope=0.5,
        intercept=5.0,
        residual_norm=0.0,
        r_squared=1.0,
        n_points=3,
        design_condition_number=1.0,
        design_rank=2,
        design_singular_values=[1.0, 1.0],
        residuals=np.array([0., 0., 0.]),
        max_abs_residual=0.0,
        asymmetry=0.0,
        asymmetry_available=True,
        slope_std_err=0.0,
        diagnostic_status="FIT_VALID"
    )
    
    R = assemble_provenance_matrix([record], cardinals, [p_id], [o_id])
    assert R.shape == (1, 1)
    assert R.row_ids == ["O0"]
    assert R.column_ids == ["P0"]
    assert np.isclose(R.matrix[0, 0], 0.5)
    
    chi = transform_to_chi(R, cardinals, ["Ni_3d"])
    assert chi.shape == (1, 1)
    assert chi.row_ids == ["Ni_3d"]
    assert chi.column_ids == ["P0"]
    assert np.isclose(chi.matrix[0, 0], 0.5)

def test_S6B_2x2_recovery():
    """Test S6-B: 2x2 multi-site recovery test."""
    grid = AlphaGrid([-0.1, 0.0, 0.1], 3, True, 1, 1, 1)
    cardinals = Cardinals(P=2, O=2, N=2, alpha_grids={"P0": grid, "P1": grid}, A=np.eye(2))
    
    p_ids = [
        PerturbationIdentity(f"P{i}", f"Site{i}", f"Proj{i}", "h") for i in range(2)
    ]
    o_ids = [
        ObservableIdentity(f"O{i}", f"Site{i}", "BARE") for i in range(2)
    ]
    
    records = []
    for o in range(2):
        for p in range(2):
            records.append(RegressionRecord(
                observable_index=o,
                channel_index=p,
                slope=1.0 if o == p else 0.1,
                intercept=5.0,
                residual_norm=0.0,
                r_squared=1.0,
                n_points=3,
                design_condition_number=1.0,
                design_rank=2,
                design_singular_values=[1.0, 1.0],
                residuals=np.array([0., 0., 0.]),
                max_abs_residual=0.0,
                asymmetry=0.0,
                asymmetry_available=True,
                slope_std_err=0.0,
                diagnostic_status="FIT_VALID"
            ))
            
    R = assemble_provenance_matrix(records, cardinals, p_ids, o_ids)
    assert R.shape == (2, 2)
    assert np.isclose(R.matrix[0, 0], 1.0)
    assert np.isclose(R.matrix[0, 1], 0.1)
    
    chi = transform_to_chi(R, cardinals, ["Site0", "Site1"])
    assert chi.shape == (2, 2)
    assert np.allclose(chi.matrix, [[1.0, 0.1], [0.1, 1.0]])

def test_S6C_rectangular_matrix(A_2x4):
    """Test S6-C: 4 observables, 2 perturbations, aggregation down to 2x2."""
    grid = AlphaGrid([-0.1, 0.0, 0.1], 3, True, 1, 1, 1)
    cardinals = Cardinals(P=2, O=4, N=2, alpha_grids={"P0": grid, "P1": grid}, A=A_2x4)
    
    p_ids = [PerturbationIdentity(f"P{i}", f"Site{i}", f"Proj{i}", "h") for i in range(2)]
    o_ids = [ObservableIdentity(f"O{i}", f"Site{i//2}", "BARE") for i in range(4)]
    
    records = []
    for o in range(4):
        for p in range(2):
            records.append(RegressionRecord(
                observable_index=o,
                channel_index=p,
                slope=1.0,
                intercept=5.0,
                residual_norm=0.0,
                r_squared=1.0,
                n_points=3,
                design_condition_number=1.0,
                design_rank=2,
                design_singular_values=[1.0, 1.0],
                residuals=np.array([0., 0., 0.]),
                max_abs_residual=0.0,
                asymmetry=0.0,
                asymmetry_available=True,
                slope_std_err=0.0,
                diagnostic_status="FIT_VALID"
            ))
            
    R = assemble_provenance_matrix(records, cardinals, p_ids, o_ids)
    assert R.shape == (4, 2)
    
    chi = transform_to_chi(R, cardinals, ["Site0", "Site1"])
    assert chi.shape == (2, 2)

def test_S6D_missing_records():
    """Test S6-D: Missing records should raise RecordCompletenessError."""
    from siestaflow_hubbard.domain.exceptions import RecordCompletenessError
    grid = AlphaGrid([-0.1, 0.0, 0.1], 3, True, 1, 1, 1)
    cardinals = Cardinals(P=2, O=2, N=2, alpha_grids={"P0": grid, "P1": grid}, A=np.eye(2))
    
    p_ids = [PerturbationIdentity(f"P{i}", f"Site{i}", f"Proj{i}", "h") for i in range(2)]
    o_ids = [ObservableIdentity(f"O{i}", f"Site{i}", "BARE") for i in range(2)]
    
    # Missing the (1, 1) record
    records = []
    for o in range(2):
        for p in range(2):
            if o == 1 and p == 1:
                continue
            records.append(RegressionRecord(
                observable_index=o, channel_index=p, slope=1.0, intercept=5.0,
                residual_norm=0.0, r_squared=1.0, n_points=3, design_condition_number=1.0,
                design_rank=2, design_singular_values=[1.0, 1.0], residuals=np.array([0., 0., 0.]),
                max_abs_residual=0.0, asymmetry=0.0, asymmetry_available=True, slope_std_err=0.0,
                diagnostic_status="FIT_VALID"
            ))
            
    with pytest.raises(RecordCompletenessError):
        assemble_provenance_matrix(records, cardinals, p_ids, o_ids)

def test_S6E_duplicate_records():
    """Test S6-E: Duplicate records should raise RecordCompletenessError."""
    from siestaflow_hubbard.domain.exceptions import RecordCompletenessError
    grid = AlphaGrid([-0.1, 0.0, 0.1], 3, True, 1, 1, 1)
    cardinals = Cardinals(P=1, O=1, N=1, alpha_grids={"P0": grid}, A=np.eye(1))
    
    p_ids = [PerturbationIdentity("P0", "Site0", "Proj0", "h")]
    o_ids = [ObservableIdentity("O0", "Site0", "BARE")]
    
    records = [
        RegressionRecord(observable_index=0, channel_index=0, slope=1.0, intercept=5.0,
            residual_norm=0.0, r_squared=1.0, n_points=3, design_condition_number=1.0,
            design_rank=2, design_singular_values=[1.0, 1.0], residuals=np.array([0., 0., 0.]),
            max_abs_residual=0.0, asymmetry=0.0, asymmetry_available=True, slope_std_err=0.0,
            diagnostic_status="FIT_VALID"),
        RegressionRecord(observable_index=0, channel_index=0, slope=2.0, intercept=5.0,
            residual_norm=0.0, r_squared=1.0, n_points=3, design_condition_number=1.0,
            design_rank=2, design_singular_values=[1.0, 1.0], residuals=np.array([0., 0., 0.]),
            max_abs_residual=0.0, asymmetry=0.0, asymmetry_available=True, slope_std_err=0.0,
            diagnostic_status="FIT_VALID")
    ]
    
    with pytest.raises(RecordCompletenessError):
        assemble_provenance_matrix(records, cardinals, p_ids, o_ids)

def test_S6F_identity_length_mismatch():
    """Test S6-F: Identity list lengths don't match Cardinals."""
    grid = AlphaGrid([-0.1, 0.0, 0.1], 3, True, 1, 1, 1)
    cardinals = Cardinals(P=2, O=2, N=2, alpha_grids={"P0": grid, "P1": grid}, A=np.eye(2))
    
    p_ids = [PerturbationIdentity("P0", "Site0", "Proj0", "h")]
    o_ids = [ObservableIdentity(f"O{i}", f"Site{i}", "BARE") for i in range(2)]
    
    records = [] # Not reached, fails earlier
    
    with pytest.raises(ValueError, match="Expected 2 perturbation identities, got 1"):
        assemble_provenance_matrix(records, cardinals, p_ids, o_ids)

