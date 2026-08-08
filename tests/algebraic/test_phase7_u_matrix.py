import pytest
import numpy as np
from siestaflow_hubbard.domain.provenance import ResponseMatrix
from siestaflow_hubbard.domain.u_matrix import NumericalPolicy, GaugeRankStatus
from siestaflow_hubbard.synthetic_backend.u_calculator import (
    compute_u_matrix, 
    InversionError, 
    LabelMismatchError, 
    ConventionSwapError
)

def test_U7A_1x1():
    """U7-A: 1x1 recovery"""
    chi0 = ResponseMatrix(np.array([[-1.0]]), ["Site0"], ["P0"], "eV", methodology_lock_hash="hash1")
    chi = ResponseMatrix(np.array([[-0.5]]), ["Site0"], ["P0"], "eV", methodology_lock_hash="hash2")
    policy = NumericalPolicy()
    
    u_mat = compute_u_matrix(chi0, chi, policy)
    
    assert u_mat.values.shape == (1, 1)
    assert u_mat.values[0, 0] == pytest.approx(1.0) # (-1) - (-2) = 1
    assert u_mat.rank_diagnostics == GaugeRankStatus.FULL_RANK
    assert u_mat.recommended_single_U_ev is None

def test_U7B_coupled_2x2():
    """U7-B: coupled 2x2 recovery"""
    chi0_val = np.array([[-2.0, -0.1], [-0.1, -2.0]])
    chi_val = np.array([[-1.0, -0.2], [-0.2, -1.0]])
    
    chi0 = ResponseMatrix(chi0_val, ["Site0", "Site1"], ["P0", "P1"], "eV", methodology_lock_hash="hash1")
    chi = ResponseMatrix(chi_val, ["Site0", "Site1"], ["P0", "P1"], "eV", methodology_lock_hash="hash2")
    policy = NumericalPolicy()
    
    u_mat = compute_u_matrix(chi0, chi, policy)
    
    expected_inv_chi0 = np.linalg.inv(chi0_val)
    expected_inv_chi = np.linalg.inv(chi_val)
    expected_u = expected_inv_chi0 - expected_inv_chi
    
    np.testing.assert_allclose(u_mat.values, expected_u)
    assert u_mat.values[0, 1] != 0.0

def test_U7C_label_permutation():
    """U7-C: label permutation"""
    chi0_val = np.array([[-2.0, -0.1], [-0.1, -3.0]])
    # Same values, but if we permute labels, it should map correctly
    chi_val = np.array([[-1.0, -0.2], [-0.2, -1.5]])
    
    chi0 = ResponseMatrix(chi0_val, ["Site0", "Site1"], ["P0", "P1"], "eV", methodology_lock_hash="hash1")
    
    # We provide chi with permuted labels and values
    chi_permuted = np.array([[-1.5, -0.2], [-0.2, -1.0]])
    chi = ResponseMatrix(chi_permuted, ["Site1", "Site0"], ["P1", "P0"], "eV", methodology_lock_hash="hash2")
    
    policy = NumericalPolicy()
    u_mat = compute_u_matrix(chi0, chi, policy)
    
    expected_inv_chi0 = np.linalg.inv(chi0_val)
    expected_inv_chi = np.linalg.inv(chi_val)
    expected_u = expected_inv_chi0 - expected_inv_chi
    
    np.testing.assert_allclose(u_mat.values, expected_u)

def test_U7D_singular_response():
    """U7-D: singular response"""
    chi0 = ResponseMatrix(np.array([[-2.0, -2.0], [-2.0, -2.0]]), ["Site0", "Site1"], ["P0", "P1"], "eV", methodology_lock_hash="hash1")
    chi = ResponseMatrix(np.array([[-1.0, -0.0], [-0.0, -1.0]]), ["Site0", "Site1"], ["P0", "P1"], "eV", methodology_lock_hash="hash2")
    policy = NumericalPolicy()
    
    with pytest.raises(InversionError, match="Singular matrix"):
        compute_u_matrix(chi0, chi, policy)

def test_U7E_ill_conditioned_response():
    """U7-E: ill-conditioned response"""
    chi0 = ResponseMatrix(np.array([[-2.0, -1.999999], [-1.999999, -2.0]]), ["Site0", "Site1"], ["P0", "P1"], "eV", methodology_lock_hash="hash1")
    chi = ResponseMatrix(np.array([[-1.0, -0.0], [-0.0, -1.0]]), ["Site0", "Site1"], ["P0", "P1"], "eV", methodology_lock_hash="hash2")
    policy = NumericalPolicy(max_condition_number=100) # strict policy
    
    with pytest.raises(InversionError, match="exceeds allowed"):
        compute_u_matrix(chi0, chi, policy)
        
    policy_fallback = NumericalPolicy(max_condition_number=100, allow_pinv_fallback=True)
    u_mat = compute_u_matrix(chi0, chi, policy_fallback)
    assert u_mat.rank_diagnostics == GaugeRankStatus.ILL_CONDITIONED

def test_U7F_chi0_chi_swap():
    """U7-F: chi0/chi swap"""
    # Physically, |chi0_diag| > |chi_diag|
    # If we swap them:
    chi_fake_0 = ResponseMatrix(np.array([[-0.5]]), ["Site0"], ["P0"], "eV", methodology_lock_hash="hash1")
    chi_fake_1 = ResponseMatrix(np.array([[-1.0]]), ["Site0"], ["P0"], "eV", methodology_lock_hash="hash2")
    policy = NumericalPolicy()
    
    with pytest.raises(ConventionSwapError, match="Did you swap chi and chi0"):
        compute_u_matrix(chi_fake_0, chi_fake_1, policy)
