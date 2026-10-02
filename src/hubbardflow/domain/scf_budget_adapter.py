"""D5 adapter into the unchanged TASK2 API, preserving print BOUND separately.

TASK2 order, tail and neighbour checks see the additive print+SCF intervals.
Its resulting noise radius is split back into the pure print BOUND and the
independent SCF ESTIMATE before it enters D3/D4 or a shadow comparison.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from fractions import Fraction

from .fdebq_models import ScfCandidateEstimate, _RoundRecord
from .response_budget_models import (
    BoundKind,
    ElementBudgetReport,
    ElementSeries,
    NoiseModel,
    _derived_finite,
)
from .response_budget_moments import estimator_moments
from .response_error_budget import (
    candidate_budgets,
    decompose,
    element_report,
    printed_response_budget,
    verify_order,
)
from .response_protocol import EstimatorKind, EstimatorSpec
from .scf_ladder import validate_envelope
from .scf_ladder_models import ScfEnvelope, ScfLadderError, ScfResponseEstimate


@dataclass(frozen=True)
class ScfElementReport(_RoundRecord):
    report: ElementBudgetReport
    estimates: tuple[ScfCandidateEstimate, ...]
    envelope: ScfEnvelope


def scf_response_estimate(
    series: ElementSeries, estimator: EstimatorSpec, envelope: ScfEnvelope
) -> ScfResponseEstimate:
    """Separate conditional slope radius for TASK14's additive shadow budgets."""
    validate_envelope(envelope)
    if (series.site_perturbed, series.mode, series.site_observed) != (
        envelope.site_perturbed,
        envelope.mode,
        envelope.site_observed,
    ):
        raise ScfLadderError("SCF envelope key disagrees with response series")
    measured = {p.alpha_ev: p for p in envelope.evidence[0].series.points}
    if any(p.alpha_ev in measured and p != measured[p.alpha_ev] for p in series.points):
        raise ScfLadderError("SCF envelope L0 measurements disagree with production response points")
    if not envelope.covers(estimator.amplitudes_ev):
        raise ScfLadderError("SCF_ENVELOPE_NOT_COVERED: estimator lies outside measured interval")
    if envelope.eps_abs_e is None or envelope.eps_rel is None:
        raise ScfLadderError("NOISE_FLOOR_NOT_ESTABLISHED: no response ESTIMATE is available")
    dec = decompose(series, NoiseModel(0.0, 0.0, BoundKind.BOUND))
    magnitudes = dict(zip(dec.amplitudes_ev, dec.odd_e, strict=True))
    moments = estimator_moments(estimator)
    if not set(estimator.amplitudes_ev) <= magnitudes.keys():
        raise ScfLadderError("estimator amplitudes are absent from response series")
    radius = sum(
        (
            abs(w)
            * (
                Fraction(str(envelope.eps_abs_e))
                + Fraction(str(envelope.eps_rel)) * abs(Fraction(str(magnitudes[float(a)])))
            )
            / a
            for w, a in zip(moments.weights, moments.amplitudes_ev, strict=True)
        ),
        Fraction(),
    )
    return ScfResponseEstimate(
        series.site_perturbed,
        series.mode,
        series.site_observed,
        estimator,
        _derived_finite(radius, "SCF response radius"),
        envelope.status,
        BoundKind.ESTIMATE,
    )


def scf_element_report(
    series: ElementSeries, envelope: ScfEnvelope, *, protocol_estimator: EstimatorSpec | None, kappa: float
) -> ScfElementReport:
    """Map D5 eps_abs/eps_rel to per-point radii; never extrapolate coverage.

    Per-point SCF error is eps_abs + eps_rel*g(a), so paired differences have
    error 2*eps and slope error eps/a. R0/R1/R2 use these full intervals.
    Uncovered observed scales cannot enter the tail or order calculations.
    """
    validate_envelope(envelope)
    if (series.site_perturbed, series.mode, series.site_observed) != (
        envelope.site_perturbed,
        envelope.mode,
        envelope.site_observed,
    ):
        raise ScfLadderError("SCF envelope key disagrees with element series")
    production = envelope.evidence[0].series
    by_alpha = {p.alpha_ev: p for p in series.points}
    if any(by_alpha.get(p.alpha_ev) != p for p in production.points):
        raise ScfLadderError("SCF envelope L0 measurements must match the production element points")
    amplitudes = tuple(p.alpha_ev for p in series.points if p.alpha_ev > 0)
    if not envelope.covers(amplitudes):
        raise ScfLadderError(
            "SCF_ENVELOPE_NOT_COVERED: order/tail evidence extends outside measured endpoints"
        )
    if envelope.eps_abs_e is None or envelope.eps_rel is None:
        raise ScfLadderError("NOISE_FLOOR_NOT_ESTABLISHED: no SCF model is available")
    dec = decompose(series, NoiseModel(0.0, 0.0, BoundKind.BOUND))
    scf_radii = tuple(
        (Fraction(str(envelope.eps_abs_e)) + Fraction(str(envelope.eps_rel)) * abs(Fraction(str(g))))
        / Fraction(str(a))
        for a, g in zip(dec.amplitudes_ev, dec.odd_e, strict=True)
    )
    full_radii = tuple(p + s for p, s in zip(dec.noise_fractions, scf_radii, strict=True))
    full = replace(
        dec,
        noise_fractions=full_radii,
        slope_noise_e_per_ev=tuple(_derived_finite(r, "full slope radius") for r in full_radii),
    )
    candidates = candidate_budgets(
        full, verify_order(full), protocol_estimator=protocol_estimator, kappa=kappa
    )
    estimates = []
    split_candidates = []
    for candidate in candidates:
        printed = printed_response_budget(series, candidate.estimator)
        moments = estimator_moments(candidate.estimator)
        by_amplitude = dict(zip(dec.amplitudes_ev, scf_radii, strict=True))
        scf_radius = sum(
            (
                abs(w) * by_amplitude[float(a)]
                for w, a in zip(moments.weights, moments.amplitudes_ev, strict=True)
            ),
            Fraction(),
        )
        estimates.append(
            ScfCandidateEstimate(
                series.site_observed,
                candidate.estimator,
                _derived_finite(scf_radius, "SCF slope radius"),
                BoundKind.ESTIMATE,
                candidate.admissible,
                envelope.qualified,
            )
        )
        split_candidates.append(replace(candidate, noise_e_per_ev=printed.print_bound_e_per_ev))
    # TASK2 diagnostics computed with full radii are retained. Production D3
    # performs its own minimax with the separated additive SCF term.
    baseline = element_report(
        series, NoiseModel(0.0, 0.0, BoundKind.BOUND), protocol_estimator=protocol_estimator, kappa=kappa
    )
    admissible = [c for c in candidates if c.admissible]
    best_full = (
        min(
            admissible,
            key=lambda c: (
                c.total_e_per_ev,
                max(c.estimator.amplitudes_ev),
                tuple(EstimatorKind).index(c.estimator.kind),
                c.estimator.amplitudes_ev,
                c.estimator.polynomial_degree or 0,
            ),
        )
        if admissible
        else None
    )
    best = next(
        (c for c in split_candidates if best_full is not None and c.estimator == best_full.estimator), None
    )
    report = replace(baseline, decomposition=full, candidates=tuple(split_candidates), best=best)
    return ScfElementReport(report, tuple(estimates), envelope)
