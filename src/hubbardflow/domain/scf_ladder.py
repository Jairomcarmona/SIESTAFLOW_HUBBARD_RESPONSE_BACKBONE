"""Pure D5 SCF estimates from differences of paired nonzero perturbations.

Print uncertainty is added exactly before contraction is tested. The ladder
estimates a conditional SCF model; it cannot establish a rigorous error bound,
the production state gate, or T0–T4 validation.
"""

from __future__ import annotations

from collections.abc import Sequence
from fractions import Fraction

from .response_budget_models import BoundKind, _derived_finite
from .scf_ladder_models import (
    LadderEvidence,
    ScfAmplitudeEstimate,
    ScfEnvelope,
    ScfLadderError,
    ScfLadderProtocol,
    ScfStatus,
)


def estimate_ladder(evidence: Sequence[LadderEvidence], protocol: ScfLadderProtocol) -> ScfEnvelope:
    """Measure the two endpoints and split eta1+ according to amendment D5.

    The max of the two measured rho estimates scales both fitted components.
    This conservative aggregation avoids claiming an unmeasured contraction
    ratio at intermediate amplitudes. All evidence is retained in the result.
    """
    try:
        # Preserve the named algebraic test protocol, whose 1e-7 tolerances are
        # not assertions about SIESTA's six-decimal production echo.
        if protocol.version != "synthetic-v1":
            protocol.require_evidence_v2()
        return _estimate_ladder(evidence, protocol)
    except ValueError as exc:
        raise ScfLadderError(f"cannot estimate SCF ladder: {exc}") from exc


def _estimate_ladder(evidence: Sequence[LadderEvidence], protocol: ScfLadderProtocol) -> ScfEnvelope:
    if not protocol.enabled:
        raise ScfLadderError("SCF_LADDER_DISABLED: explicitly enable the versioned protocol")
    by_level = {item.level_id: item.series for item in evidence}
    if len(by_level) != 3 or len(evidence) != 3 or set(by_level) != {l.level_id for l in protocol.levels}:
        raise ScfLadderError("evidence must contain exactly the three declared SCF levels")
    rows = tuple(by_level[level.level_id] for level in protocol.levels)
    key = (rows[0].site_perturbed, rows[0].mode, rows[0].site_observed)
    if any((r.site_perturbed, r.mode, r.site_observed) != key for r in rows):
        raise ScfLadderError("all SCF levels must measure the same column, mode and row")
    grids = {tuple(p.alpha_ev for p in row.points) for row in rows}
    if len(grids) != 1 or len(rows[0].points) != 4:
        raise ScfLadderError("ladder requires the same two symmetric nonzero amplitudes at every level")
    points = tuple({p.alpha_ev: p for p in row.points} for row in rows)
    theta, rho_max = Fraction(str(protocol.theta)), Fraction(str(protocol.rho_max))
    estimates = []
    for a in sorted(alpha for alpha in points[0] if alpha > 0):
        delta = tuple(Fraction(str(p[a].occupation_e)) - Fraction(str(p[-a].occupation_e)) for p in points)
        radius = tuple(Fraction(str(p[a].half_width_e)) + Fraction(str(p[-a].half_width_e)) for p in points)
        eta1, eta2 = abs(delta[0] - delta[1]), abs(delta[1] - delta[2])
        r1, r2 = radius[0] + radius[1], radius[1] + radius[2]
        plus1, minus1 = eta1 + r1, max(eta1 - r1, Fraction())
        plus2, minus2 = eta2 + r2, max(eta2 - r2, Fraction())
        rho = plus2 / minus1 if minus1 > 0 else rho_max
        status = (
            ScfStatus.NOISE_FLOOR_NOT_ESTABLISHED
            if rho > rho_max
            else ScfStatus.SCF_UNDER_RESOLVED
            if minus1 == 0
            else ScfStatus.ESTABLISHED
        )
        estimate = None if status is ScfStatus.NOISE_FLOOR_NOT_ESTABLISHED else theta * plus1 / (1 - rho)
        estimates.append(
            ScfAmplitudeEstimate(
                a,
                _derived_finite(abs(delta[0]) / 2, "response magnitude"),
                _derived_finite(plus1, "eta1_plus"),
                _derived_finite(minus1, "eta1_minus"),
                _derived_finite(plus2, "eta2_plus"),
                _derived_finite(minus2, "eta2_minus"),
                _derived_finite(rho, "rho_hat"),
                None if estimate is None else _derived_finite(estimate, "delta estimate"),
                status,
                BoundKind.ESTIMATE,
            )
        )
    small, large = estimates
    status = (
        ScfStatus.NOISE_FLOOR_NOT_ESTABLISHED
        if any(e.status is ScfStatus.NOISE_FLOOR_NOT_ESTABLISHED for e in estimates)
        else ScfStatus.SCF_UNDER_RESOLVED
        if any(e.status is ScfStatus.SCF_UNDER_RESOLVED for e in estimates)
        else ScfStatus.ESTABLISHED
    )
    abs_eps = rel_eps = rho_hat = None
    if status is not ScfStatus.NOISE_FLOOR_NOT_ESTABLISHED:
        es, el = Fraction(str(small.eta1_plus_e)), Fraction(str(large.eta1_plus_e))
        gs, gl = Fraction(str(small.response_magnitude_e)), Fraction(str(large.response_magnitude_e))
        rel_eta = max(Fraction(), (el - es) / (gl - gs)) if gl > gs else Fraction()
        abs_eta = max(Fraction(), es - rel_eta * gs) if gl > gs else max(es, el)
        rho = max(Fraction(str(e.rho_hat)) for e in estimates)
        factor = theta / (2 * (1 - rho))
        abs_eps = _derived_finite(abs_eta * factor, "eps_abs_e")
        rel_eps = _derived_finite(rel_eta * factor, "eps_rel")
        rho_hat = _derived_finite(rho, "rho_hat")
    return ScfEnvelope(
        *key,
        protocol,
        tuple(LadderEvidence(l.level_id, by_level[l.level_id]) for l in protocol.levels),
        tuple(estimates),
        abs_eps,
        rel_eps,
        rho_hat,
        status,
        BoundKind.ESTIMATE,
    )


def validate_envelope(envelope: ScfEnvelope) -> None:
    """Recompute derived evidence before trusting an injected model or mapping."""
    if estimate_ladder(envelope.evidence, envelope.protocol) != envelope:
        raise ScfLadderError("SCF envelope does not match its bound protocol and ladder evidence")
