import numpy as np

from siestaflow_hubbard.domain.matrix_response_acceptance import MatrixResponseAcceptancePolicy, accept_response_matrices


POLICY = MatrixResponseAcceptancePolicy(0.05, 1e4, 0.1)


def test_accepts_small_cross_terms_when_matrix_is_stable():
    matrix = np.array([[2.0, 1e-8], [1e-8, 1.0]])
    report = accept_response_matrices(matrix, matrix * 0.8, np.full((2, 2), 1e-6), np.full((2, 2), 1e-6), POLICY)
    assert report["accepted"]


def test_rejects_rank_deficiency_even_when_cross_terms_are_small():
    matrix = np.array([[1.0, 0.0], [0.0, 0.0]])
    report = accept_response_matrices(matrix, matrix, np.zeros((2, 2)), np.zeros((2, 2)), POLICY)
    assert not report["accepted"]


def test_rejects_nonreciprocal_matrix_before_symmetrization():
    raw = np.array([[1.0, 0.5], [0.0, 1.0]])
    report = accept_response_matrices(raw, raw, np.zeros((2, 2)), np.zeros((2, 2)), POLICY)
    assert not report["accepted"]
