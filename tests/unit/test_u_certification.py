from fractions import Fraction
from itertools import product

import pytest

from siestaflow_hubbard.domain.u_certification import (
    CertificationError, Interval, certify_inverse_diagonal_2x2,
    certify_u_2x2, exact_slope_weights, propagate_linear_tokens,
    interval_half_width, verified_krawczyk_inverse_diagonal, verified_neumann_inverse_diagonal,
    certify_inverse_diagonal,
)


def test_decimal_tokens_and_exact_ols_weights():
    weights = exact_slope_weights(["-0.1", "0", "0.1"], 1)
    assert weights == (Fraction(-5), Fraction(0), Fraction(5))
    interval = propagate_linear_tokens(weights, ["1.00", "2.000", "3.00"])
    assert interval.lo == Fraction(199, 20)
    assert interval.hi == Fraction(201, 20)


def test_half_width_regression_uses_endpoints_and_not_nominal_position():
    lower, upper = Fraction("6.857300307"), Fraction("6.870129237")
    nominal, tolerance = Fraction("6.861874364188249"), Fraction("0.020")
    half_width = interval_half_width(lower, upper)
    assert half_width == Fraction("0.006414465")
    assert tolerance - half_width == Fraction("0.013585535")
    assert nominal - lower != half_width
    assert upper - nominal != half_width


def test_2x2_exact_inverse_diagonal_point_and_regular_box():
    point = [[Interval(Fraction(2), Fraction(2)), Interval(Fraction(0), Fraction(0))],
             [Interval(Fraction(0), Fraction(0)), Interval(Fraction(4), Fraction(4))]]
    diagonal, meta = certify_inverse_diagonal_2x2(point)
    assert diagonal == (Interval(Fraction(1, 2), Fraction(1, 2)), Interval(Fraction(1, 4), Fraction(1, 4)))
    assert meta["regularity"] == "CERTIFIED"


def test_2x2_refuses_box_containing_singular_matrix():
    box = [[Interval(Fraction(0), Fraction(2)), Interval(Fraction(0), Fraction(0))],
           [Interval(Fraction(0), Fraction(0)), Interval(Fraction(1), Fraction(1))]]
    with pytest.raises(CertificationError, match="INTERVAL_REGULARITY"):
        certify_inverse_diagonal_2x2(box)


def test_krawczyk_and_neumann_verify_same_box_enclosing_exact_diagonal():
    box = [[Interval(Fraction(19, 10), Fraction(21, 10)), Interval(Fraction(0), Fraction(1, 100))],
           [Interval(Fraction(0), Fraction(1, 100)), Interval(Fraction(29, 10), Fraction(31, 10))]]
    exact, _ = certify_inverse_diagonal_2x2(box)
    kraw, _ = verified_krawczyk_inverse_diagonal(box)
    neum, _ = verified_neumann_inverse_diagonal(box)
    for i in range(2):
        assert kraw[i].lo <= exact[i].lo <= exact[i].hi <= kraw[i].hi
        assert neum[i].lo <= exact[i].lo <= exact[i].hi <= neum[i].hi


def test_uncertainty_increase_does_not_narrow_certificate():
    narrow = [[Interval(Fraction(199, 100), Fraction(201, 100)), Interval(Fraction(0), Fraction(1, 1000))],
              [Interval(Fraction(0), Fraction(1, 1000)), Interval(Fraction(299, 100), Fraction(301, 100))]]
    wide = [[Interval(Fraction(19, 10), Fraction(21, 10)), Interval(Fraction(0), Fraction(1, 100))],
            [Interval(Fraction(0), Fraction(1, 100)), Interval(Fraction(29, 10), Fraction(31, 10))]]
    small, _ = certify_inverse_diagonal_2x2(narrow)
    large, _ = certify_inverse_diagonal_2x2(wide)
    for inner, outer in zip(small, large):
        assert outer.lo <= inner.lo <= inner.hi <= outer.hi


def test_u_2x2_keeps_independent_bare_screened_contract():
    bare = [[Interval(Fraction(2), Fraction(2)), Interval(Fraction(0), Fraction(0))],
            [Interval(Fraction(0), Fraction(0)), Interval(Fraction(4), Fraction(4))]]
    screened = [[Interval(Fraction(4), Fraction(4)), Interval(Fraction(0), Fraction(0))],
                [Interval(Fraction(0), Fraction(0)), Interval(Fraction(8), Fraction(8))]]
    result = certify_u_2x2(bare, screened)
    assert result["u_interval_by_site"] == [{"lower": "1/4", "upper": "1/4"},
                                          {"lower": "1/8", "upper": "1/8"}]


def test_verified_krawczyk_handles_well_conditioned_three_by_three():
    box = [[Interval(Fraction(4), Fraction(4)), Interval(Fraction(0), Fraction(0)), Interval(Fraction(0), Fraction(0))],
           [Interval(Fraction(0), Fraction(0)), Interval(Fraction(5), Fraction(5)), Interval(Fraction(0), Fraction(0))],
           [Interval(Fraction(0), Fraction(0)), Interval(Fraction(0), Fraction(0)), Interval(Fraction(6), Fraction(6))]]
    diagonal, _ = verified_krawczyk_inverse_diagonal(box)
    assert diagonal == (Interval(Fraction(1, 4), Fraction(1, 4)),
                        Interval(Fraction(1, 5), Fraction(1, 5)),
                        Interval(Fraction(1, 6), Fraction(1, 6)))


@pytest.mark.parametrize("width", [Fraction(1), Fraction(2)])
def test_verified_neumann_fallback_requires_strict_beta_less_than_one(width):
    box = [[Interval(Fraction(1) - width, Fraction(1) + width)]]
    with pytest.raises(CertificationError, match="VERIFIED_NEUMANN"):
        verified_neumann_inverse_diagonal(box)


def test_site_permutation_permutes_certified_inverse_diagonal():
    matrix = [[Fraction(3), Fraction(1, 4)], [Fraction(1, 2), Fraction(2)]]
    permuted = [[matrix[1][1], matrix[1][0]], [matrix[0][1], matrix[0][0]]]
    box = [[Interval(x, x) for x in row] for row in matrix]
    box_p = [[Interval(x, x) for x in row] for row in permuted]
    d, _ = certify_inverse_diagonal_2x2(box)
    d_p, _ = certify_inverse_diagonal_2x2(box_p)
    assert d_p == (d[1], d[0])


def test_alpha_design_exact_rank_failure_is_rejected():
    with pytest.raises(CertificationError, match="singular|distinct"):
        exact_slope_weights(["0.1", "0.1", "0.1"], degree=1)


def test_two_by_two_extrema_match_exhaustive_rational_vertex_properties():
    for seed in range(12):
        base = [Fraction(3 + seed, 2), Fraction(seed % 3, 10),
                Fraction((seed + 1) % 4, 10), Fraction(2 + seed, 3)]
        widths = [Fraction(1, 100 + seed), Fraction(1, 200 + seed),
                  Fraction(1, 250 + seed), Fraction(1, 120 + seed)]
        box = [[Interval(base[0] - widths[0], base[0] + widths[0]),
                Interval(base[1] - widths[1], base[1] + widths[1])],
               [Interval(base[2] - widths[2], base[2] + widths[2]),
                Interval(base[3] - widths[3], base[3] + widths[3])]]
        exact, proof = certify_inverse_diagonal_2x2(box)
        vertices = []
        for a, b, c, d in product(
            (box[0][0].lo, box[0][0].hi), (box[0][1].lo, box[0][1].hi),
            (box[1][0].lo, box[1][0].hi), (box[1][1].lo, box[1][1].hi),
        ):
            det = a * d - b * c
            assert det != 0
            vertices.append((d / det, a / det))
        assert proof["regularity"] == "CERTIFIED"
        assert exact[0] == Interval(min(x[0] for x in vertices), max(x[0] for x in vertices))
        assert exact[1] == Interval(min(x[1] for x in vertices), max(x[1] for x in vertices))


def test_general_neumann_fallback_runs_when_krawczyk_rounded_preconditioner_fails():
    center = Fraction(17)
    radius = center * (1 - Fraction(1, 10**12))
    box = [[Interval(center - radius, center + radius) if i == j
            else Interval(Fraction(0), Fraction(0)) for j in range(3)] for i in range(3)]
    result = certify_inverse_diagonal(box)
    assert result["status"] == "CERTIFIED_WITH_FALLBACK"
    assert result["primary_method"] == "verified_neumann_fallback"
    assert result["krawczyk_status"] == "KRAWCZYK_CERTIFICATE_NOT_ESTABLISHED"
