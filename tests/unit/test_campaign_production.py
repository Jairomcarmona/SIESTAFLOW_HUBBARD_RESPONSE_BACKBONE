import pytest
import numpy as np
from production_benchmarks.lr_arithmetic import central_3point, fit_5point, compute_U_matrix, build_chi_matrix_3point
from production_benchmarks.geometry_validator import verify_cuprite_cu2o, verify_rocksalt_afm, validate_no_duplicate_atoms, verify_cu3n_antireo3
from production_benchmarks.supercell_builder import get_afm_supercell_options, verify_stoichiometry
from production_benchmarks.campaign_schema import CalculationIdentity, LRMode

def test_3point_central_derivative_exact():
    n_minus, n_plus, delta = 9.9, 10.1, 0.2
    assert abs(central_3point(n_minus, n_plus, delta) - 0.5) < 1e-12

def test_5point_fit_exact_linear():
    alphas = [-0.02, -0.01, 0.00, 0.01, 0.02]
    true_slope = -0.15
    occs = [10.0 + true_slope * a for a in alphas]
    result = fit_5point(alphas, occs)
    assert abs(result['slope'] - true_slope) < 1e-10
    assert result['r2'] > 0.9999

def test_5point_fit_nonlinear_r2_low():
    alphas = [-0.02, -0.01, 0.00, 0.01, 0.02]
    occs = [10.0 + a**2 * 100 for a in alphas]
    result = fit_5point(alphas, occs)
    assert result['r2'] < 0.5

def test_chi_matrix_3point_correct_shape_2x2():
    chi_true = np.array([[-0.09, 0.01], [0.01, -0.09]])
    delta = 0.01
    obs = {}
    n_ref = [9.5, 9.5]
    for J in range(2):
        for alpha in [-delta, 0.0, delta]:
            mode = 'SCREENED'
            obs[(J, alpha, mode)] = [n_ref[I] + chi_true[I,J]*alpha for I in range(2)]
    mat = build_chi_matrix_3point(obs, n_sites=2, delta=delta)
    assert mat.shape == (2, 2)
    assert np.allclose(mat, chi_true, atol=1e-10)

def test_chi_matrix_3point_n4_shape():
    chi_true = np.full((4,4), 0.01); np.fill_diagonal(chi_true, -0.12)
    delta = 0.01
    obs = {}
    n_ref = [9.5]*4
    for J in range(4):
        for alpha in [-delta, 0.0, delta]:
            obs[(J, alpha, 'SCREENED')] = [n_ref[I] + chi_true[I,J]*alpha for I in range(4)]
    mat = build_chi_matrix_3point(obs, n_sites=4, delta=delta)
    assert mat.shape == (4, 4)
    assert np.allclose(mat, chi_true, atol=1e-10)

def test_compute_U_matrix_no_pinv():
    chi0 = np.array([[-0.25, 0.05],[0.05, -0.25]])
    chi  = np.array([[-0.09, 0.01],[0.01, -0.09]])
    res = compute_U_matrix(chi0, chi)
    assert res['chi0_rank'] == 2
    assert res['chi_rank'] == 2
    U = res['U']
    U_expected = np.linalg.inv(chi0) - np.linalg.inv(chi)
    assert np.allclose(U, U_expected, atol=1e-10)

def test_compute_U_matrix_rank_deficient_raises():
    chi0 = np.array([[-0.25, 0.05],[0.05, -0.25]])
    chi_singular = np.zeros((2,2))
    with pytest.raises(ValueError, match='rank'):
        compute_U_matrix(chi0, chi_singular)

def test_cu2o_geometry_valid():
    a = 4.27
    fracs = np.array([
        [0.00, 0.00, 0.00], [0.50, 0.50, 0.50],
        [0.25, 0.25, 0.25], [0.25, 0.75, 0.75],
        [0.75, 0.25, 0.75], [0.75, 0.75, 0.25]
    ])
    labels = ['O','O','Cu','Cu','Cu','Cu']
    result = verify_cuprite_cu2o(fracs, labels, a)
    assert result['geometry_valid']
    assert abs(result['cu_o_nearest_ang'] - 1.849) < 0.01
    assert result['cu_coordination'] == 2
    assert result['o_coordination'] == 4
    assert result['all_cu_equivalent']

def test_rocksalt_afm_feo_geometry_valid():
    a = 4.334
    fracs = np.array([
        [0.0, 0.0, 0.0],[0.5, 0.5, 0.0],[0.5, 0.0, 0.5],[0.0, 0.5, 0.5],
        [0.5, 0.0, 0.0],[0.0, 0.5, 0.0],[0.0, 0.0, 0.5],[0.5, 0.5, 0.5]
    ])
    labels = ['Fe','Fe','Fe','Fe','O','O','O','O']
    result = verify_rocksalt_afm(fracs, labels, a)
    assert result['geometry_valid']
    assert result['n_fe'] == 4
    assert result['n_o'] == 4

def test_no_duplicate_atoms():
    fracs = np.array([[0.0,0.0,0.0],[0.5,0.5,0.5],[0.25,0.25,0.25]])
    assert validate_no_duplicate_atoms(fracs)
    fracs_dup = np.array([[0.0,0.0,0.0],[0.0,0.0,0.0],[0.25,0.25,0.25]])
    assert not validate_no_duplicate_atoms(fracs_dup)

def test_calculation_identity_key_unique():
    from production_benchmarks.campaign_schema import CalculationIdentity
    base = dict(geometry_sha256='abc', species_map='Fe:Fe,O:O', pseudopotential_sha256s='xxx',
                siesta_version='5.4.2', spin_mode='polarized', basis='DZP',
                energy_shift_ry=0.005, mesh_cutoff_ry=200, kgrid='2x2x2',
                supercell='1x1x1', projector_method=2, projector_nl='3d',
                projector_rc=3.0, projector_omega=0.05, alpha=0.01,
                perturbed_site=0, mode='BARE', reference_dm_sha256='deadbeef')
    id1 = CalculationIdentity(**base)
    id2 = CalculationIdentity(**{**base, 'alpha': 0.02})
    assert id1.compute_key() != id2.compute_key()

def test_calculation_identity_same_inputs_same_key():
    from production_benchmarks.campaign_schema import CalculationIdentity
    params = dict(geometry_sha256='abc', species_map='Fe:Fe', pseudopotential_sha256s='xxx',
                  siesta_version='5.4.2', spin_mode='polarized', basis='DZP',
                  energy_shift_ry=0.005, mesh_cutoff_ry=200, kgrid='4x4x4',
                  supercell='2x2x2', projector_method=2, projector_nl='3d',
                  projector_rc=3.0, projector_omega=0.05, alpha=0.01,
                  perturbed_site=1, mode='SCREENED', reference_dm_sha256='deadbeef')
    assert CalculationIdentity(**params).compute_key() == CalculationIdentity(**params).compute_key()

def test_feo_afm_species_split_preserves_spins():
    import sys, os
    sys.path.insert(0, os.path.abspath('.'))
    from siestaflow_hubbard.siesta_backend.fdf_builder import materialize_split_species_fdf
    base_fdf = """
NumberOfAtoms 8
NumberOfSpecies 2
%block ChemicalSpeciesLabel
 1 26 Fe
 2  8 O
%endblock ChemicalSpeciesLabel
%block AtomicCoordinatesAndAtomicSpecies
 0.0 0.0 0.0 1
 0.5 0.5 0.0 1
 0.5 0.0 0.5 1
 0.0 0.5 0.5 1
 0.5 0.0 0.0 2
 0.0 0.5 0.0 2
 0.0 0.0 0.5 2
 0.5 0.5 0.5 2
%endblock AtomicCoordinatesAndAtomicSpecies
Spin polarized
%block DM.InitSpin
 1 +4.0
 2 -4.0
 3 +4.0
 4 -4.0
 5  0.0
 6  0.0
 7  0.0
 8  0.0
%endblock DM.InitSpin
"""
    new_fdf, labels = materialize_split_species_fdf(base_fdf, target_species='Fe', new_prefix='FeLR')
    assert labels == ['FeLR0','FeLR1','FeLR2','FeLR3']
    assert '+4.0' in new_fdf
    assert '-4.0' in new_fdf
    for lbl in labels:
        assert lbl in new_fdf
    import re
    m = re.search(r'NumberOfSpecies\s+(\d+)', new_fdf)
    assert m and int(m.group(1)) == 5

def test_nio_afm_species_split_preserves_spins():
    import sys, os
    sys.path.insert(0, os.path.abspath('.'))
    from siestaflow_hubbard.siesta_backend.fdf_builder import materialize_split_species_fdf
    base_fdf = """
NumberOfAtoms 8
NumberOfSpecies 2
%block ChemicalSpeciesLabel
 1 28 Ni
 2  8 O
%endblock ChemicalSpeciesLabel
%block AtomicCoordinatesAndAtomicSpecies
 0.0 0.0 0.0 1
 0.5 0.5 0.0 1
 0.5 0.0 0.5 1
 0.0 0.5 0.5 1
 0.5 0.0 0.0 2
 0.0 0.5 0.0 2
 0.0 0.0 0.5 2
 0.5 0.5 0.5 2
%endblock AtomicCoordinatesAndAtomicSpecies
Spin polarized
%block DM.InitSpin
 1 +2.0
 2 -2.0
 3 +2.0
 4 -2.0
 5  0.0
 6  0.0
 7  0.0
 8  0.0
%endblock DM.InitSpin
"""
    new_fdf, labels = materialize_split_species_fdf(base_fdf, target_species='Ni', new_prefix='NiLR')
    assert '+2.0' in new_fdf
    assert '-2.0' in new_fdf
    assert len(labels) == 4

def test_cu3n_geometry_valid():
    a = 3.84
    fracs = np.array([
        [0.0, 0.0, 0.0],
        [0.5, 0.0, 0.0],
        [0.0, 0.5, 0.0],
        [0.0, 0.0, 0.5],
    ])
    labels = ['N','Cu','Cu','Cu']
    result = verify_cu3n_antireo3(fracs, labels, a)
    assert result['geometry_valid']
    assert result['n_cu'] == 3
    assert result['n_n'] == 1

def test_supercell_stoichiometry_preserved():
    from production_benchmarks.supercell_builder import get_afm_supercell_options, verify_stoichiometry
    options = get_afm_supercell_options('FeO')
    assert len(options) == 3
    for opt in options:
        assert opt['n_fe'] > 0
        assert opt['n_fe'] == opt['n_o']

def test_resume_does_not_reuse_stale_dm(tmp_path):
    import hashlib
    from siestaflow_hubbard.siesta_backend.adapter import prepare_canonical_dm
    ref = tmp_path / 'ref.DM'
    child = tmp_path / 'child.DM'
    canonical = b'canonical_bytes_for_resume_test'
    stale = b'stale_bytes_from_failed_run'
    ref.write_bytes(canonical)
    child.write_bytes(stale)
    ref_sha = hashlib.sha256(canonical).hexdigest()
    prepare_canonical_dm(str(ref), str(child), ref_sha)
    assert child.read_bytes() == canonical

def test_slurm_unique_directories():
    from production_benchmarks.slurm_runner import calculate_ranks_per_run
    ranks = calculate_ranks_per_run(ntasks_total=100, max_concurrent=5)
    assert ranks == 20
    ranks2 = calculate_ranks_per_run(ntasks_total=100, max_concurrent=4)
    assert ranks2 == 25
