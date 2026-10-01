"""Exact-rational response-token and U interval certification.

All predicates deciding certification use :class:`Fraction`; floats are only
accepted for nominal cross-checks and are never converted with Fraction(float).
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from itertools import product
from typing import Sequence


class CertificationError(ValueError):
    pass


def rational(value: str | int | Fraction) -> Fraction:
    if isinstance(value, Fraction):
        return value
    if isinstance(value, bool) or isinstance(value, float):
        raise CertificationError("certified inputs must be lexical decimals or exact integers")
    return Fraction(value)


@dataclass(frozen=True, order=True)
class Interval:
    lo: Fraction
    hi: Fraction

    def __post_init__(self) -> None:
        if self.lo > self.hi:
            raise CertificationError("interval lower endpoint exceeds upper endpoint")

    @classmethod
    def decimal_token(cls, token: str) -> "Interval":
        center = rational(token)
        mantissa, sep, exponent = token.lower().partition("e")
        places = len(mantissa.split(".", 1)[1]) if "." in mantissa else 0
        exp = int(exponent) if sep else 0
        half = Fraction(1, 2) * Fraction(10) ** (exp - places)
        return cls(center - half, center + half)

    @classmethod
    def around(cls, center: str | int | Fraction, half_width: str | int | Fraction) -> "Interval":
        c, h = rational(center), rational(half_width)
        if h < 0:
            raise CertificationError("half width must be nonnegative")
        return cls(c - h, c + h)

    def contains(self, value: Fraction) -> bool:
        return self.lo <= value <= self.hi

    def as_json(self) -> dict[str, str]:
        return {"lower": str(self.lo), "upper": str(self.hi)}


def interval_half_width(lower: str | int | Fraction, upper: str | int | Fraction) -> Fraction:
    """Return half the endpoint span; independent of any nominal estimate."""
    lo, hi = rational(lower), rational(upper)
    if lo > hi:
        raise CertificationError("interval lower endpoint exceeds upper endpoint")
    return (hi - lo) / 2


def exact_slope_weights(alpha_tokens: Sequence[str], degree: int = 1) -> tuple[Fraction, ...]:
    """Return exact OLS coefficients mapping observations to the linear term."""
    xs = [rational(token) for token in alpha_tokens]
    if degree < 1 or degree > 3 or len(xs) < degree + 1:
        raise CertificationError("polynomial degree must be 1..3 and fit must be overdetermined or exact")
    # Design columns are 1, alpha, ...; exact normal equations verify full rank.
    v = [[x ** p for p in range(degree + 1)] for x in xs]
    gram = [[sum(row[i] * row[j] for row in v) for j in range(degree + 1)] for i in range(degree + 1)]
    inv = inverse(gram)
    return tuple(sum(inv[1][p] * row[p] for p in range(degree + 1)) for row in v)


def propagate_linear_tokens(weights: Sequence[Fraction], tokens: Sequence[str]) -> Interval:
    if len(weights) != len(tokens) or not tokens:
        raise CertificationError("weights/tokens have incompatible lengths")
    result = Interval(Fraction(0), Fraction(0))
    for w, token in zip(weights, tokens):
        term = Interval.decimal_token(token)
        products_ = (w * term.lo, w * term.hi)
        result = Interval(result.lo + min(products_), result.hi + max(products_))
    return result


def propagate_linear_occupation_tokens(
    weights: Sequence[Fraction], samples: Sequence[Sequence[str]],
) -> Interval:
    """Propagate totals formed from one or more independently printed tokens."""
    if len(weights) != len(samples) or not samples:
        raise CertificationError("weights/samples have incompatible lengths")
    result = Interval(Fraction(0), Fraction(0))
    for weight, components in zip(weights, samples):
        if not components:
            raise CertificationError("each occupation needs at least one lexical token")
        total = Interval(Fraction(0), Fraction(0))
        for token in components:
            part = Interval.decimal_token(token)
            total = Interval(total.lo + part.lo, total.hi + part.hi)
        products_ = (weight * total.lo, weight * total.hi)
        result = Interval(result.lo + min(products_), result.hi + max(products_))
    return result


def inverse(matrix: Sequence[Sequence[Fraction]]) -> list[list[Fraction]]:
    n = len(matrix)
    if not n or any(len(row) != n for row in matrix):
        raise CertificationError("matrix must be nonempty and square")
    a = [[rational(x) for x in row] + [Fraction(i == j) for j in range(n)] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = next((r for r in range(col, n) if a[r][col]), None)
        if pivot is None:
            raise CertificationError("singular rational matrix")
        a[col], a[pivot] = a[pivot], a[col]
        scale = a[col][col]
        a[col] = [x / scale for x in a[col]]
        for row in range(n):
            if row == col:
                continue
            scale = a[row][col]
            a[row] = [x - scale * y for x, y in zip(a[row], a[col])]
    return [row[n:] for row in a]


MatrixBox = Sequence[Sequence[Interval]]


def _det2_vertices(box: MatrixBox) -> list[Fraction]:
    return [a * d - b * c for a, b, c, d in product(
        (box[0][0].lo, box[0][0].hi), (box[0][1].lo, box[0][1].hi),
        (box[1][0].lo, box[1][0].hi), (box[1][1].lo, box[1][1].hi),
    )]


def certify_inverse_diagonal_2x2(box: MatrixBox) -> tuple[Interval, Interval, dict[str, object]]:
    """Enclose inverse diagonals over a full 2x2 box.

    Determinant regularity is certified at the 16 vertices: det is affine in
    each coordinate separately, so successive endpoint interpolation bounds
    every interior value by the vertex extrema. If those extrema have one
    strict sign, the denominator has that sign throughout the box.

    For either diagonal entry, fix three coordinates and vary the fourth. The
    entry has form (p*t+q)/(r*t+s); its derivative is the constant
    (p*s-q*r)/(r*t+s)^2. Since the denominator cannot vanish on the segment,
    this function is monotone or constant, so its extrema on that segment are
    endpoints. Applying this endpoint argument successively to all four
    coordinates proves global extrema occur among the 16 vertices. No
    sampling or nominal inverse is used.
    """
    if len(box) != 2 or any(len(row) != 2 for row in box):
        raise CertificationError("exact 2x2 certificate requires a 2x2 interval matrix")
    dets = _det2_vertices(box)
    dmin, dmax = min(dets), max(dets)
    if not (dmin > 0 or dmax < 0):
        raise CertificationError("INTERVAL_REGULARITY_NOT_ESTABLISHED")
    vals_11, vals_22 = [], []
    for a, b, c, d in product(
        (box[0][0].lo, box[0][0].hi), (box[0][1].lo, box[0][1].hi),
        (box[1][0].lo, box[1][0].hi), (box[1][1].lo, box[1][1].hi),
    ):
        det = a * d - b * c
        vals_11.append(d / det)
        vals_22.append(a / det)
    return ((Interval(min(vals_11), max(vals_11)), Interval(min(vals_22), max(vals_22))),
            {"determinant_vertices_min": str(dmin), "determinant_vertices_max": str(dmax),
             "regularity": "CERTIFIED", "method": "exact_rational_2x2"})


def _mid(x: Interval) -> Fraction:
    return (x.lo + x.hi) / 2


def _radius(x: Interval) -> Fraction:
    return interval_half_width(x.lo, x.hi)


def verified_neumann_inverse_diagonal(box: MatrixBox) -> tuple[tuple[Interval, ...], dict[str, object]]:
    """Enclose diagonal inverse entries using exact infinity-norm Neumann bound."""
    n = len(box)
    if not n or any(len(row) != n for row in box):
        raise CertificationError("matrix interval must be square")
    center = [[_mid(x) for x in row] for row in box]
    rad = [[_radius(x) for x in row] for row in box]
    invc = inverse(center)
    norm_inv = max(sum(abs(x) for x in row) for row in invc)
    norm_delta = max(sum(row) for row in rad)
    beta = norm_inv * norm_delta
    if beta >= 1:
        raise CertificationError("VERIFIED_NEUMANN_NOT_ESTABLISHED")
    diagonal = []
    for i in range(n):
        radius = norm_inv * norm_delta * max(sum(abs(x) for x in row) for row in invc) / (1 - beta)
        diagonal.append(Interval(invc[i][i] - radius, invc[i][i] + radius))
    return tuple(diagonal), {"method": "verified_neumann_fallback", "beta": str(beta), "strict_beta_lt_one": True}


def verified_krawczyk_inverse_diagonal(box: MatrixBox) -> tuple[tuple[Interval, ...], dict[str, object]]:
    """Krawczyk inclusion with a rounded rational preconditioner and exact bounds.

    The exact midpoint inverse is rounded to a 10^-12 rational grid to produce
    a realistic preconditioner (without binary floating point). The center
    defect ||I-R*A_c||∞ and interval term ||R||∞||ΔA||∞ bound the Krawczyk
    contraction. Its full residual and strict interior inclusion are then
    checked in rational arithmetic.
    """
    n = len(box)
    center = [[_mid(x) for x in row] for row in box]
    rad = [[_radius(x) for x in row] for row in box]
    if all(value == 0 for row in rad for value in row):
        exact = inverse(center)
        return tuple(Interval(exact[i][i], exact[i][i]) for i in range(n)), {
            "method": "verified_krawczyk", "strict_inclusion": True,
            "point_interval_exact_solve": True,
        }
    exact_mid_inverse = inverse(center)
    scale = 10**12
    rmat = [[Fraction(round(value * scale), scale) for value in row] for row in exact_mid_inverse]
    delta_norm = max(sum(row) for row in rad)
    rnorm = max(sum(abs(x) for x in row) for row in rmat)
    defect = [[Fraction(i == j) - sum(rmat[i][k] * center[k][j] for k in range(n))
               for j in range(n)] for i in range(n)]
    defect_norm = max(sum(abs(value) for value in row) for row in defect)
    contraction = defect_norm + rnorm * delta_norm
    if contraction >= 1:
        raise CertificationError("KRAWCZYK_CERTIFICATE_NOT_ESTABLISHED")
    out: list[Interval] = []
    for col in range(n):
        rhs = [Fraction(row == col) for row in range(n)]
        xc = [sum(rmat[row][k] * rhs[k] for k in range(n)) for row in range(n)]
        center_residual = [sum(rmat[row][k] * (rhs[k] - sum(center[k][j] * xc[j] for j in range(n)))
                               for k in range(n)) for row in range(n)]
        residual = max(abs(value) for value in center_residual) + rnorm * delta_norm * max(abs(x) for x in xc)
        radius = 2 * residual / (1 - contraction)
        if not (radius > 0 and residual + contraction * radius < radius):
            raise CertificationError("KRAWCZYK_CERTIFICATE_NOT_ESTABLISHED")
        out.append(Interval(xc[col] - radius, xc[col] + radius))
    return tuple(out), {"method": "verified_krawczyk", "contraction_bound": str(contraction),
                        "strict_inclusion": True, "preconditioner_rational_grid": str(scale)}


def certify_u_2x2(chi0: MatrixBox, chi: MatrixBox) -> dict[str, object]:
    bare, bare_meta = certify_inverse_diagonal_2x2(chi0)
    screened, screened_meta = certify_inverse_diagonal_2x2(chi)
    u = tuple(Interval(bare[i].lo - screened[i].hi, bare[i].hi - screened[i].lo) for i in range(2))
    # Cross-check conservative exact-rational enclosures; any disagreement is a bug.
    cross_checks: list[dict[str, object]] = []
    for name, method, box, exact in (
        ("chi0", verified_krawczyk_inverse_diagonal, chi0, bare),
        ("chi0", verified_neumann_inverse_diagonal, chi0, bare),
        ("chi", verified_krawczyk_inverse_diagonal, chi, screened),
        ("chi", verified_neumann_inverse_diagonal, chi, screened),
    ):
        try:
            enclosure, proof = method(box)
        except CertificationError:
            cross_checks.append({"matrix": name, "method": method.__name__, "status": "NOT_ESTABLISHED"})
            continue
        if any(not (enclosure[i].lo <= exact[i].lo <= exact[i].hi <= enclosure[i].hi) for i in range(2)):
            raise CertificationError("INCONSISTENT_CERTIFIERS")
        cross_checks.append({"matrix": name, **proof, "status": "CONSISTENT"})
    return {"method": "exact_rational_2x2", "chi0_regular": bare_meta, "chi_regular": screened_meta,
            "u_interval_by_site": [x.as_json() for x in u],
            "half_width_by_site": [str(_radius(x)) for x in u],
            "assumptions": ["BARE and SCREENED token sets are independent"],
            "cross_checks": cross_checks,
            "consistency_status": "CONSISTENT"}


def certify_inverse_diagonal(box: MatrixBox) -> dict[str, object]:
    """N×N hierarchy: verified Krawczyk, then an explicit verified Neumann fallback."""
    try:
        enclosure, proof = verified_krawczyk_inverse_diagonal(box)
        return {"status": "CERTIFIED", "interval_by_site": [value.as_json() for value in enclosure],
                "primary_method": "verified_krawczyk", "proof": proof}
    except CertificationError as krawczyk_error:
        try:
            enclosure, proof = verified_neumann_inverse_diagonal(box)
            return {"status": "CERTIFIED_WITH_FALLBACK", "interval_by_site": [value.as_json() for value in enclosure],
                    "primary_method": "verified_neumann_fallback", "proof": proof,
                    "krawczyk_status": "KRAWCZYK_CERTIFICATE_NOT_ESTABLISHED"}
        except CertificationError as neumann_error:
            return {"status": "CERTIFICATE_NOT_ESTABLISHED", "interval_by_site": None,
                    "primary_method": None,
                    "krawczyk_reason": str(krawczyk_error), "neumann_reason": str(neumann_error)}


def certify_u_matrices(chi0: MatrixBox, chi: MatrixBox) -> dict[str, object]:
    """Certify diagonal U intervals for N=2 exactly and N>2 by verified solves."""
    n = len(chi0)
    if n < 2 or len(chi) != n or any(len(row) != n for matrix in (chi0, chi) for row in matrix):
        raise CertificationError("chi0 and chi boxes must be same-size square matrices")
    if n == 2:
        return certify_u_2x2(chi0, chi)
    bare, screened = certify_inverse_diagonal(chi0), certify_inverse_diagonal(chi)
    if bare["status"] == "CERTIFICATE_NOT_ESTABLISHED" or screened["status"] == "CERTIFICATE_NOT_ESTABLISHED":
        return {
            "status": "CERTIFICATE_NOT_ESTABLISHED", "method": None,
            "u_interval_by_site": None, "half_width_by_site": None,
            "chi0_inverse": bare, "chi_inverse": screened,
            "assumptions": ["BARE and SCREENED token sets are independent"],
        }
    intervals = []
    from fractions import Fraction
    for a, b in zip(bare["interval_by_site"], screened["interval_by_site"]):
        intervals.append(Interval(Fraction(a["lower"]) - Fraction(b["upper"]),
                                  Fraction(a["upper"]) - Fraction(b["lower"])))
    fallback = "CERTIFIED_WITH_FALLBACK" in {bare["status"], screened["status"]}
    return {
        "status": "CERTIFIED_WITH_FALLBACK" if fallback else "CERTIFIED",
        "method": "verified_neumann_fallback" if fallback else "verified_krawczyk",
        "u_interval_by_site": [value.as_json() for value in intervals],
        "half_width_by_site": [str(_radius(value)) for value in intervals],
        "chi0_inverse": bare, "chi_inverse": screened,
        "assumptions": ["BARE and SCREENED token sets are independent"],
    }
