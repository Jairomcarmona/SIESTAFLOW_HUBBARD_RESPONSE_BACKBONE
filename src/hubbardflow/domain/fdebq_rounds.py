"""Pure deterministic FD-EBQ rounds implementing author amendments D3/D4.

Input evidence is cumulative and sorted; each completed round adds one lattice
level to one column. Round limits derive from that set, never from U stability
or historical success counters. State/SCF gaps conservatively cap REVIEW.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import replace
from fractions import Fraction

import numpy as np

from .fdebq_matrix import LABEL, column_influences, qualify_matrices
from .fdebq_models import (
    CalibrationProtocol,
    CalibrationQualification,
    ColumnEvidence,
    ColumnSelection,
    ColumnStatus,
    FdebqRoundsError,
    RoundDecision,
    RoundReason,
    RoundRequest,
    RoundStatus,
    SelectedElement,
)
from .response_budget_models import BoundKind, NoiseModel
from .response_error_budget import element_report
from .response_protocol import ColumnPlan, EstimatorKind, EstimatorSpec
from .scf_budget_adapter import scf_element_report
from .scf_ladder_models import ScfLadderError, ScfStatus
from .symmetry_reduction import ResponseMode


def _total(element: SelectedElement) -> Fraction:
    return (
        Fraction(str(element.candidate.noise_e_per_ev))
        + Fraction(str(element.candidate.truncation_e_per_ev))
        + (Fraction(str(element.scf_estimate_e_per_ev)) if element.scf_estimate_e_per_ev is not None else 0)
    )


def _estimator_key(spec: EstimatorSpec) -> tuple[float, int, tuple[float, ...], int]:
    return (
        max(spec.amplitudes_ev),
        tuple(EstimatorKind).index(spec.kind),
        spec.amplitudes_ev,
        spec.polynomial_degree or 0,
    )


def select_column(evidence: ColumnEvidence, protocol: CalibrationProtocol) -> ColumnSelection:
    """One TASK2 candidate must be admissible in every observed row (D3).

    Minimize max-I of the full additive absolute budget. The per-row TASK2 best
    estimator is retained strictly as a diagnostic and never supplies a matrix.
    """
    try:
        return _select_column(evidence, protocol)
    except ValueError as exc:
        raise FdebqRoundsError(f"cannot select column: {exc}") from exc


def _select_column(evidence: ColumnEvidence, protocol: CalibrationProtocol) -> ColumnSelection:
    observed = tuple(p.alpha_ev for p in evidence.series[0].points if p.alpha_ev > 0)
    if not set(observed + evidence.failed_amplitudes_ev) <= set(protocol.candidate_lattice_ev):
        raise FdebqRoundsError("observed and failed amplitudes must belong to declared lattice")
    cutoff = min(evidence.failed_amplitudes_ev) if evidence.failed_amplitudes_ev else None
    usable = tuple(a for a in observed if cutoff is None or a < cutoff)
    empty = ColumnSelection(evidence.site_id, evidence.mode, ColumnStatus.UNRESOLVED, observed, None, (), ())
    if len(usable) < 4:
        return empty
    reports = []
    scf_estimates = list(evidence.scf_estimates)
    envelopes = {e.site_observed: e for e in evidence.scf_envelopes}
    for series in evidence.series:
        filtered = replace(series, points=tuple(p for p in series.points if abs(p.alpha_ev) in usable))
        if envelopes:
            try:
                adapted = scf_element_report(
                    filtered, envelopes[series.site_observed], protocol_estimator=None, kappa=protocol.kappa
                )
            except ScfLadderError as exc:
                if "SCF_ENVELOPE_NOT_COVERED" in str(exc) or "NOISE_FLOOR_NOT_ESTABLISHED" in str(exc):
                    return empty
                raise
            reports.append(adapted.report)
            scf_estimates.extend(adapted.estimates)
        else:
            reports.append(
                element_report(
                    filtered,
                    NoiseModel(0.0, 0.0, BoundKind.BOUND),
                    protocol_estimator=None,
                    kappa=protocol.kappa,
                )
            )
    scf = {(e.site_observed, e.estimator): e for e in scf_estimates}
    candidates: dict[EstimatorSpec, list[SelectedElement]] = {}
    for row, report in zip(evidence.series, reports, strict=True):
        for candidate in report.candidates:
            estimate = scf.get((row.site_observed, candidate.estimator))
            if candidate.admissible and (not scf_estimates or (estimate is not None and estimate.admissible)):
                candidates.setdefault(candidate.estimator, []).append(
                    SelectedElement(
                        row.site_observed,
                        candidate,
                        None if estimate is None else estimate.radius_e_per_ev,
                        estimate is not None and estimate.qualified,
                    )
                )
    shared = {spec: elements for spec, elements in candidates.items() if len(elements) == len(reports)}
    best = (
        min(shared, key=lambda s: (max(_total(e) for e in shared[s]), *_estimator_key(s))) if shared else None
    )
    return ColumnSelection(
        evidence.site_id,
        evidence.mode,
        ColumnStatus.RESOLVED if best is not None else ColumnStatus.UNRESOLVED,
        observed,
        best,
        tuple(shared[best]) if best is not None else (),
        tuple(
            (series.site_observed, report.best)
            for series, report in zip(evidence.series, reports, strict=True)
        ),
    )


def production_column_plan(selection: ColumnSelection, protocol: CalibrationProtocol) -> ColumnPlan | None:
    """Production applies this same functional to every row; diagnostic best is ignored."""
    if selection.estimator is None:
        return None
    return ColumnPlan(
        selection.site_id,
        selection.mode,
        selection.estimator.amplitudes_ev,
        selection.estimator,
        protocol.scf_level_id,
    )


def seed_requests(sites: Sequence[str], protocol: CalibrationProtocol) -> tuple[RoundRequest, ...]:
    """Request the explicit four-or-more-scale seed for every site and mode."""
    if not sites or len(set(sites)) != len(sites) or any(not s or s != s.strip() for s in sites):
        raise FdebqRoundsError("seed sites must be distinct nonempty identifiers")
    return tuple(
        RoundRequest(s, mode, signed)
        for s in sorted(sites)
        for mode in ResponseMode
        for a in protocol.seed(mode)
        for signed in (-a, a)
    )


def _next(evidence: ColumnEvidence, protocol: CalibrationProtocol) -> float | None:
    known = {p.alpha_ev for p in evidence.series[0].points if p.alpha_ev > 0}
    failed = set(evidence.failed_amplitudes_ev)
    allowed = [
        a
        for a in protocol.candidate_lattice_ev
        if a not in known | failed and (not failed or a < min(failed))
    ]
    return allowed[0] if allowed else None


def decide_round(
    columns: Sequence[ColumnEvidence],
    protocol: CalibrationProtocol,
    *,
    requested: Sequence[RoundRequest],
    terminal: Sequence[RoundRequest],
) -> RoundDecision:
    """Analyze only after the round barrier; request one new scale in D3 order.

    If an unresolved column prevents matrix construction, its influence is not
    identifiable: fixed site/mode order supplies a conservative request, with
    NO_COMMON_ESTIMATOR. Exhaustion means NOT_ESTABLISHED, never qualification.
    """
    try:
        return _decide_round(columns, protocol, requested=requested, terminal=terminal)
    except (ValueError, KeyError, TypeError) as exc:
        raise FdebqRoundsError(f"cannot decide calibration round: {exc}") from exc


def _decide_round(
    columns: Sequence[ColumnEvidence],
    protocol: CalibrationProtocol,
    *,
    requested: Sequence[RoundRequest],
    terminal: Sequence[RoundRequest],
) -> RoundDecision:
    ordered = tuple(sorted(columns, key=lambda c: (c.site_id, c.mode.value)))
    keys = {(c.site_id, c.mode) for c in ordered}
    if len(keys) != len(ordered) or not ordered:
        raise FdebqRoundsError("round requires distinct site/mode columns")
    sites = tuple(sorted({c.site_id for c in ordered}))
    if keys != {(s, m) for s in sites for m in ResponseMode} or any(
        tuple(s.site_observed for s in c.series) != sites for c in ordered
    ):
        raise FdebqRoundsError("round requires both modes and all matrix rows for every column")
    req, done = set(requested), set(terminal)
    if len(req) != len(requested) or len(done) != len(terminal) or not done <= req or not req:
        raise FdebqRoundsError("round requests must be distinct and terminal records must be requested")
    if any(
        (r.site_id, r.mode) not in keys or abs(r.alpha_ev) not in protocol.candidate_lattice_ev for r in req
    ):
        raise FdebqRoundsError("requests must target declared columns and lattice amplitudes")
    if any(RoundRequest(r.site_id, r.mode, -r.alpha_ev) not in req for r in req):
        raise FdebqRoundsError("round requests require symmetric partners")
    by_key = {(c.site_id, c.mode): c for c in ordered}
    for r in done:
        c = by_key[(r.site_id, r.mode)]
        if abs(r.alpha_ev) not in c.failed_amplitudes_ev and any(
            r.alpha_ev not in {p.alpha_ev for p in s.points} for s in c.series
        ):
            raise FdebqRoundsError("terminal request lacks observations in every row or a recorded failure")
    raw_evidence = [c.to_mapping() for c in ordered]
    evidence_digest = hashlib.sha256(
        json.dumps(
            raw_evidence,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()
    selections: tuple[ColumnSelection, ...] = ()
    matrix = None

    def decision(
        status: RoundStatus, reasons: Sequence[RoundReason], requests: tuple[RoundRequest, ...] = ()
    ) -> RoundDecision:
        return RoundDecision(
            CalibrationQualification(
                status,
                selections,
                matrix,
                tuple(sorted(set(reasons), key=lambda r: r.value)),
                protocol.digest,
                evidence_digest,
                LABEL,
            ),
            requests,
        )

    if req != done:
        return decision(RoundStatus.WAITING, (RoundReason.ROUND_BARRIER,))
    round_count = 1
    for c in ordered:
        known = {p.alpha_ev for p in c.series[0].points if p.alpha_ev > 0} | set(c.failed_amplitudes_ev)
        if not set(protocol.seed(c.mode)) <= known:
            raise FdebqRoundsError("completed evidence lacks the declared seed")
        round_count += len(known - set(protocol.seed(c.mode)))
    selections = tuple(select_column(c, protocol) for c in ordered)
    unresolved = [c for c, s in zip(ordered, selections, strict=True) if s.estimator is None]
    reasons = [RoundReason.NO_COMMON_ESTIMATOR] if unresolved else []
    for c in ordered:
        for envelope in c.scf_envelopes:
            if envelope.status is ScfStatus.SCF_UNDER_RESOLVED:
                reasons.append(RoundReason.SCF_UNDER_RESOLVED)
            elif envelope.status is ScfStatus.NOISE_FLOOR_NOT_ESTABLISHED:
                reasons.append(RoundReason.NOISE_FLOOR_NOT_ESTABLISHED)
            observed = tuple(p.alpha_ev for p in c.series[0].points if p.alpha_ev > 0)
            if not envelope.covers(observed):
                reasons.append(RoundReason.SCF_ENVELOPE_NOT_COVERED)
    if protocol.t0_t4_result_sha256 is None:
        reasons.append(RoundReason.VALIDATION_NOT_ESTABLISHED)
    if any(not c.state_gate_established for c in ordered):
        reasons.append(RoundReason.SCIENTIFIC_STATE_NOT_ESTABLISHED)
    if any(not e.scf_qualified for s in selections for e in s.elements):
        reasons.append(RoundReason.SCF_ESTIMATE_MISSING)
    if any(
        reason in reasons
        for reason in (
            RoundReason.SCF_UNDER_RESOLVED,
            RoundReason.NOISE_FLOOR_NOT_ESTABLISHED,
            RoundReason.SCF_ENVELOPE_NOT_COVERED,
        )
    ):
        return decision(RoundStatus.REVIEW, reasons)
    scores: dict[tuple[str, ResponseMode], float] = {}
    if not unresolved:
        centers = {m: [[0.0 for _ in sites] for _ in sites] for m in ResponseMode}
        budgets = {m: [[Fraction() for _ in sites] for _ in sites] for m in ResponseMode}
        for selection in selections:
            j = sites.index(selection.site_id)
            for e in selection.elements:
                i = sites.index(e.site_observed)
                centers[selection.mode][i][j] = e.candidate.estimate_e_per_ev
                budgets[selection.mode][i][j] = _total(e)
        # Reciprocal residuals falsify the full selected budgets; they never
        # select a different row estimator or symmetrize the raw matrix.
        for mode in ResponseMode:
            for i in range(len(sites)):
                for j in range(i + 1, len(sites)):
                    residual = abs(Fraction(str(centers[mode][i][j])) - Fraction(str(centers[mode][j][i])))
                    allowed = Fraction(str(protocol.kappa)) * (budgets[mode][i][j] + budgets[mode][j][i])
                    if residual > allowed:
                        reasons.append(RoundReason.BUDGET_FALSIFIED)
        matrix = qualify_matrices(
            centers[ResponseMode.BARE],
            centers[ResponseMode.SCREENED],
            budgets[ResponseMode.BARE],
            budgets[ResponseMode.SCREENED],
            tau_u_ev=protocol.tau_u_ev,
        )
        reasons.extend(matrix.reasons)
        if matrix.passed and not reasons:
            return decision(RoundStatus.QUALIFIED, ())
        if matrix.passed:
            return decision(RoundStatus.REVIEW, reasons)
        influences = column_influences(
            np.asarray(centers[ResponseMode.BARE]),
            np.asarray(centers[ResponseMode.SCREENED]),
            np.asarray(budgets[ResponseMode.BARE], dtype=float),
            np.asarray(budgets[ResponseMode.SCREENED], dtype=float),
        )
        for mode, values in zip(ResponseMode, influences, strict=True):
            scores.update({(s, mode): value for s, value in zip(sites, values, strict=True)})
    eligible = [c for c in (unresolved or list(ordered)) if _next(c, protocol) is not None]
    if not eligible:
        return decision(RoundStatus.NOT_ESTABLISHED, reasons + [RoundReason.LATTICE_EXHAUSTED])
    if round_count >= protocol.max_rounds:
        return decision(RoundStatus.REVIEW, reasons + [RoundReason.MAX_ROUNDS])
    target = min(eligible, key=lambda c: (-scores.get((c.site_id, c.mode), 0.0), c.site_id, c.mode.value))
    amplitude = _next(target, protocol)
    assert amplitude is not None
    return decision(
        RoundStatus.CONTINUE,
        reasons,
        (
            RoundRequest(target.site_id, target.mode, -amplitude),
            RoundRequest(target.site_id, target.mode, amplitude),
        ),
    )
