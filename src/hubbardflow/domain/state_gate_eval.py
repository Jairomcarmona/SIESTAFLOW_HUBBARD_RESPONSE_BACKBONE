"""Pure numerical evaluation of the I.5 printed-state checks."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any

import numpy as np

from hubbardflow.domain.state_gate_results import (
    AmplitudeGateResult,
    CheckOutcome,
    StateCheck,
    StateCheckResult,
    StateGateMode,
    StateGateReason,
    StateGateResult,
    StateGateVerdict,
    StatePointResult,
)
from hubbardflow.domain.state_gate_types import (
    AtomPointState,
    BandEvidenceStatus,
    PointState,
    StateGateError,
    StateGatePoint,
)

_I5_STATE_POLICY_ID = "i5-state-policy-v1"
_MAJORITY = 0.5
_DECIMAL_REPLACE = str.maketrans({"D": "E", "d": "e"})


class _Spectrum:
    def __init__(self, matrix: np.ndarray[Any, Any]) -> None:
        values_ascending, vectors_ascending = np.linalg.eigh(matrix)
        self.values = values_ascending[::-1].copy()
        self.vectors = vectors_ascending[:, ::-1].copy()
        gaps = self.values[:-1] - self.values[1:]
        order = np.argsort(gaps, kind="stable")[::-1]
        self.delta_1 = float(gaps[order[0]])
        self.delta_2 = float(gaps[order[1]])
        self.k = int(order[0]) + 1


def _matrix(atom: AtomPointState, spin: int) -> np.ndarray[Any, Any]:
    tokens = atom.matrix_up if spin == 1 else atom.matrix_down
    try:
        matrix = np.asarray([[float(token) for token in row] for row in tokens], dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise StateGateError(f"atom {atom.atom_index} spin {spin} matrix is invalid") from exc
    if matrix.shape != (5, 5) or not np.isfinite(matrix).all():
        raise StateGateError(f"atom {atom.atom_index} spin {spin} requires a finite 5x5 matrix")
    if not np.array_equal(matrix, matrix.T):
        raise StateGateError(f"atom {atom.atom_index} spin {spin} matrix is not symmetric")
    return matrix


def _decimal(token: str) -> Decimal:
    try:
        result = Decimal(token.translate(_DECIMAL_REPLACE))
    except InvalidOperation as exc:
        raise StateGateError(f"invalid printed decimal token {token!r}") from exc
    if not result.is_finite():
        raise StateGateError(f"printed decimal token must be finite: {token!r}")
    return result


def _quantum(token: str) -> Decimal:
    normalized = token.translate(_DECIMAL_REPLACE).lower()
    mantissa, marker, exponent_text = normalized.partition("e")
    places = len(mantissa.partition(".")[2]) if "." in mantissa else 0
    exponent = int(exponent_text) if marker else 0
    return Decimal(1).scaleb(exponent - places)


def _result(
    check: StateCheck,
    outcome: CheckOutcome,
    reasons: tuple[StateGateReason, ...] = (),
    *,
    atom: int | None = None,
    spin: int | None = None,
    details: Mapping[str, str | bool | int | float] | None = None,
) -> StateCheckResult:
    return StateCheckResult(
        check=check,
        outcome=outcome,
        reasons=tuple(sorted(set(reasons), key=lambda item: item.value)),
        atom_index=atom,
        spin=spin,
        details=tuple(sorted((details or {}).items())),
    )


def _reference_split(spectrum: _Spectrum, width: float) -> tuple[int | None, StateCheckResult]:
    if spectrum.delta_1 - spectrum.delta_2 <= 4.0 * width or spectrum.delta_1 <= 4.0 * width:
        return None, _result(
            StateCheck.G2,
            CheckOutcome.NOT_DEFINED,
            details={"delta_1_ev": spectrum.delta_1, "delta_2_ev": spectrum.delta_2},
        )
    epsilon_ref = 4.0 * width / (spectrum.delta_1 - 2.0 * width)
    if epsilon_ref >= _MAJORITY:
        return None, _result(
            StateCheck.G2,
            CheckOutcome.NOT_DEFINED,
            details={"epsilon_ref": epsilon_ref},
        )
    return spectrum.k, _result(
        StateCheck.G2,
        CheckOutcome.PASS,
        details={"k": spectrum.k, "epsilon_ref": epsilon_ref},
    )


def _g2_point(
    reference: _Spectrum,
    point: _Spectrum,
    k: int,
    width: float,
    atom_index: int,
    spin: int,
) -> StateCheckResult:
    if point.delta_1 - point.delta_2 <= 4.0 * width:
        return _result(
            StateCheck.G2,
            CheckOutcome.FAIL,
            (StateGateReason.SUBSPACE_AMBIGUOUS,),
            atom=atom_index,
            spin=spin,
            details={"delta_1_ev": point.delta_1, "delta_2_ev": point.delta_2},
        )
    delta_ref = reference.values[k - 1] - reference.values[k]
    delta_point = point.values[k - 1] - point.values[k]
    if delta_ref <= 2.0 * width or delta_point <= 2.0 * width:
        epsilon = float("inf")
    else:
        epsilon = 2.0 * (width / (delta_ref - 2.0 * width) + width / (delta_point - 2.0 * width))
    if epsilon >= _MAJORITY:
        return _result(
            StateCheck.G2,
            CheckOutcome.FAIL,
            (StateGateReason.SUBSPACE_AMBIGUOUS,),
            atom=atom_index,
            spin=spin,
            details={"epsilon": epsilon if np.isfinite(epsilon) else "unbounded"},
        )
    if point.k != k:
        return _result(
            StateCheck.G2,
            CheckOutcome.FAIL,
            (StateGateReason.OCCUPATION_COUNT_CHANGED,),
            atom=atom_index,
            spin=spin,
            details={"k_reference": k, "k_point": point.k, "epsilon": epsilon},
        )
    overlap = reference.vectors[:, :k].T @ point.vectors[:, :k]
    singular_values = np.linalg.svd(overlap, compute_uv=False)
    cosine_squared = float(min(1.0, max(0.0, singular_values[-1] ** 2)))
    metrics = {"cosine_squared": cosine_squared, "epsilon": epsilon, "k": k}
    if cosine_squared - epsilon > _MAJORITY:
        return _result(StateCheck.G2, CheckOutcome.PASS, atom=atom_index, spin=spin, details=metrics)
    if cosine_squared + epsilon < _MAJORITY:
        return _result(
            StateCheck.G2,
            CheckOutcome.FAIL,
            (StateGateReason.ORBITAL_ORDER_CHANGED,),
            atom=atom_index,
            spin=spin,
            details=metrics,
        )
    return _result(
        StateCheck.G2,
        CheckOutcome.FAIL,
        (StateGateReason.SUBSPACE_AMBIGUOUS,),
        atom=atom_index,
        spin=spin,
        details=metrics,
    )


def _g3a(reference: AtomPointState, point: AtomPointState) -> StateCheckResult:
    if abs(reference.sz_e) <= reference.sz_half_width_e:
        return _result(StateCheck.G3A, CheckOutcome.NOT_DEFINED, atom=reference.atom_index)
    same_sign = (reference.sz_e > 0 and point.sz_e > 0) or (reference.sz_e < 0 and point.sz_e < 0)
    if same_sign and abs(point.sz_e) > point.sz_half_width_e:
        return _result(StateCheck.G3A, CheckOutcome.PASS, atom=reference.atom_index)
    return _result(
        StateCheck.G3A,
        CheckOutcome.FAIL,
        (StateGateReason.MOMENT_SIGN_CHANGED,),
        atom=reference.atom_index,
        details={"sz_reference_e": reference.sz_e, "sz_point_e": point.sz_e},
    )


def _fermi_consistent(state: PointState) -> bool:
    delta = abs(_decimal(state.fermi_stdout_token) - _decimal(state.fermi_energy_token))
    allowance = _quantum(state.fermi_stdout_token) / 2 + _quantum(state.fermi_energy_token) / 2
    return delta <= allowance


def _band_ambiguous(energy_token: str, fermi_token: str) -> bool:
    distance = abs(_decimal(energy_token) - _decimal(fermi_token))
    allowance = _quantum(energy_token) / 2 + _quantum(fermi_token) / 2
    return distance <= allowance


def _band_counts(state: PointState) -> dict[tuple[int, int], int]:
    fermi = _decimal(state.fermi_energy_token)
    counts: dict[tuple[int, int], int] = {}
    for band in state.band_energies:
        key = (band.kpoint, band.spin)
        counts[key] = counts.get(key, 0) + (_decimal(band.energy_token) < fermi)
    return counts


def _g4_reference(state: PointState) -> StateCheckResult:
    if state.band_evidence_status is BandEvidenceStatus.NOT_AVAILABLE:
        return _result(StateCheck.G4, CheckOutcome.NOT_AVAILABLE)
    if not _fermi_consistent(state):
        return _result(
            StateCheck.G4,
            CheckOutcome.NOT_ESTABLISHED,
            (StateGateReason.EIG_STDOUT_FERMI_MISMATCH,),
        )
    if any(_band_ambiguous(band.energy_token, state.fermi_energy_token) for band in state.band_energies):
        return _result(StateCheck.G4, CheckOutcome.NOT_APPLICABLE)
    return _result(StateCheck.G4, CheckOutcome.PASS)


def _g4_point(
    reference: PointState, point: PointState, reference_check: StateCheckResult
) -> StateCheckResult:
    if point.band_evidence_status is BandEvidenceStatus.AVAILABLE and not _fermi_consistent(point):
        return _result(
            StateCheck.G4,
            CheckOutcome.NOT_ESTABLISHED,
            (StateGateReason.EIG_STDOUT_FERMI_MISMATCH,),
        )
    if reference.band_evidence_status is BandEvidenceStatus.NOT_AVAILABLE:
        return _result(StateCheck.G4, CheckOutcome.NOT_AVAILABLE)
    if point.band_evidence_status is BandEvidenceStatus.NOT_AVAILABLE:
        return _result(StateCheck.G4, CheckOutcome.NOT_AVAILABLE)
    if reference_check.outcome is CheckOutcome.NOT_ESTABLISHED:
        return reference_check
    if reference_check.outcome is CheckOutcome.NOT_APPLICABLE:
        return _result(StateCheck.G4, CheckOutcome.NOT_APPLICABLE)
    ref_keys = {(band.kpoint, band.spin) for band in reference.band_energies}
    point_keys = {(band.kpoint, band.spin) for band in point.band_energies}
    if ref_keys != point_keys:
        return _result(
            StateCheck.G4,
            CheckOutcome.NOT_ESTABLISHED,
            (StateGateReason.MISSING_REQUIRED_EVIDENCE,),
        )
    if any(_band_ambiguous(band.energy_token, point.fermi_energy_token) for band in point.band_energies):
        return _result(
            StateCheck.G4,
            CheckOutcome.FAIL,
            (StateGateReason.BAND_COUNT_AMBIGUOUS,),
        )
    if _band_counts(reference) != _band_counts(point):
        return _result(StateCheck.G4, CheckOutcome.FAIL, (StateGateReason.BAND_COUNT_CHANGED,))
    return _result(StateCheck.G4, CheckOutcome.PASS)


def _point_result(
    reference: PointState,
    point: StateGatePoint,
    ref_spectra: dict[tuple[int, int], _Spectrum],
    ref_splits: dict[tuple[int, int], tuple[int | None, StateCheckResult]],
    ref_g4: StateCheckResult,
) -> StatePointResult:
    checks: list[StateCheckResult] = [
        _result(StateCheck.G1, CheckOutcome.PASS)
        if point.node_validated
        else _result(StateCheck.G1, CheckOutcome.FAIL, (StateGateReason.NODE_NOT_VALIDATED,))
    ]
    if point.state is None:
        for check in (StateCheck.G2, StateCheck.G3A, StateCheck.G4):
            checks.append(
                _result(check, CheckOutcome.NOT_ESTABLISHED, (StateGateReason.MISSING_REQUIRED_EVIDENCE,))
            )
        return StatePointResult(point.alpha_ev, tuple(checks))
    ref_atoms = {atom.atom_index: atom for atom in reference.atoms}
    point_atoms = {atom.atom_index: atom for atom in point.state.atoms}
    if set(ref_atoms) != set(point_atoms):
        for check in (StateCheck.G2, StateCheck.G3A, StateCheck.G4):
            checks.append(
                _result(check, CheckOutcome.NOT_ESTABLISHED, (StateGateReason.MISSING_REQUIRED_EVIDENCE,))
            )
        return StatePointResult(point.alpha_ev, tuple(checks))

    for atom_index in sorted(ref_atoms):
        ref_atom, point_atom = ref_atoms[atom_index], point_atoms[atom_index]
        for spin in (1, 2):
            key = (atom_index, spin)
            k, ref_check = ref_splits[key]
            if k is None:
                checks.append(
                    _result(
                        StateCheck.G2,
                        CheckOutcome.NOT_DEFINED,
                        atom=atom_index,
                        spin=spin,
                        details=dict(ref_check.details),
                    )
                )
            else:
                width = 5 * ref_atom.matrix_print_quantum_e / 2
                point_spectrum = _Spectrum(_matrix(point_atom, spin))
                checks.append(_g2_point(ref_spectra[key], point_spectrum, k, width, atom_index, spin))
            checks.append(_g3a(ref_atom, point_atom))
    checks.append(_g4_point(reference, point.state, ref_g4))
    return StatePointResult(point.alpha_ev, tuple(checks))


def _point_failure_reasons(points: tuple[StatePointResult | None, ...]) -> set[StateGateReason]:
    return {
        reason
        for point in points
        if point is not None
        for check in point.checks
        if check.outcome is CheckOutcome.FAIL
        for reason in check.reasons
    }


def _empty_result(column_id: str, mode: StateGateMode, reason: StateGateReason) -> StateGateResult:
    smoothness = _result(
        StateCheck.G3,
        CheckOutcome.NOT_ESTABLISHED,
        (StateGateReason.SMOOTHNESS_REQUIRES_SCF_LADDER,),
    )
    return StateGateResult(
        _I5_STATE_POLICY_ID,
        column_id,
        mode,
        StateGateVerdict.NOT_ESTABLISHED,
        (),
        (),
        (),
        (reason,),
        smoothness,
    )


def qualify_state_gate(
    reference: PointState,
    column_id: str,
    mode: StateGateMode | str,
    points: tuple[StateGatePoint, ...],
) -> StateGateResult:
    """Evaluate the diagnostic state checks for one column and mode."""
    try:
        state_mode = StateGateMode(mode)
    except ValueError as exc:
        raise StateGateError(f"unsupported I.5 mode: {mode!r}") from exc
    if not column_id.strip():
        raise StateGateError("column_id must be non-empty")
    if not points:
        return _empty_result(column_id, state_mode, StateGateReason.MISSING_REQUIRED_EVIDENCE)
    ref_indices = tuple(atom.atom_index for atom in reference.atoms)
    if any(
        point.state is not None and tuple(atom.atom_index for atom in point.state.atoms) != ref_indices
        for point in points
    ):
        raise StateGateError("reference and point correlated atom inventories differ")
    if len({point.alpha_ev for point in points}) != len(points):
        raise StateGateError("duplicate signed alpha points are not permitted")

    ref_spectra: dict[tuple[int, int], _Spectrum] = {}
    ref_splits: dict[tuple[int, int], tuple[int | None, StateCheckResult]] = {}
    for atom in reference.atoms:
        for spin in (1, 2):
            key = (atom.atom_index, spin)
            spectrum = _Spectrum(_matrix(atom, spin))
            ref_spectra[key] = spectrum
            ref_splits[key] = _reference_split(spectrum, 5 * atom.matrix_print_quantum_e / 2)
    ref_g4 = _g4_reference(reference)
    point_results = {
        point.alpha_ev: _point_result(reference, point, ref_spectra, ref_splits, ref_g4)
        for point in sorted(points, key=lambda item: item.alpha_ev)
    }
    groups: dict[float, dict[int, StatePointResult]] = {}
    for alpha, result in point_results.items():
        groups.setdefault(abs(alpha), {})[1 if alpha > 0 else -1] = result

    first_failure: float | None = None
    failures_seen: set[StateGateReason] = set()
    missing_evidence = False
    amplitudes: list[AmplitudeGateResult] = []
    for amplitude in sorted(groups):
        signs = groups[amplitude]
        positive, negative = signs.get(1), signs.get(-1)
        pair = (positive, negative)
        current_failures = _point_failure_reasons(pair)
        if current_failures and first_failure is None:
            first_failure = amplitude
        failures_seen.update(current_failures)
        incomplete = positive is None or negative is None
        not_established = any(
            check.outcome is CheckOutcome.NOT_ESTABLISHED
            for result in pair
            if result is not None
            for check in result.checks
        )
        if incomplete or not_established:
            missing_evidence = True
        point_reasons = {
            reason
            for result in pair
            if result is not None
            for check in result.checks
            if check.outcome is CheckOutcome.NOT_ESTABLISHED
            for reason in check.reasons
        }
        if incomplete:
            point_reasons.add(StateGateReason.MISSING_REQUIRED_EVIDENCE)
        admissible = (
            positive is not None and negative is not None and first_failure is None and not not_established
        )
        amplitudes.append(
            AmplitudeGateResult(
                amplitude_ev=amplitude,
                positive=positive,
                negative=negative,
                admissible=admissible,
                excluded_by_monotone_rule=first_failure is not None and amplitude >= first_failure,
                reasons=tuple(sorted(failures_seen | point_reasons, key=lambda item: item.value)),
            )
        )

    verdict = (
        StateGateVerdict.FAIL
        if first_failure is not None
        else StateGateVerdict.NOT_ESTABLISHED
        if missing_evidence
        else StateGateVerdict.PASS
    )
    reasons = failures_seen | {
        reason
        for amplitude in amplitudes
        for result in (amplitude.positive, amplitude.negative)
        if result is not None
        for check in result.checks
        if check.outcome is CheckOutcome.NOT_ESTABLISHED
        for reason in check.reasons
    }
    if any(amplitude.positive is None or amplitude.negative is None for amplitude in amplitudes):
        reasons.add(StateGateReason.MISSING_REQUIRED_EVIDENCE)
    smoothness = _result(
        StateCheck.G3,
        CheckOutcome.NOT_ESTABLISHED,
        (StateGateReason.SMOOTHNESS_REQUIRES_SCF_LADDER,),
    )
    return StateGateResult(
        policy_id=_I5_STATE_POLICY_ID,
        column_id=column_id,
        mode=state_mode,
        verdict=verdict,
        amplitudes=tuple(amplitudes),
        admissible_amplitudes_ev=tuple(item.amplitude_ev for item in amplitudes if item.admissible),
        excluded_amplitudes_ev=tuple(
            item.amplitude_ev for item in amplitudes if item.excluded_by_monotone_rule
        ),
        reasons=tuple(sorted(reasons, key=lambda item: item.value)),
        smoothness=smoothness,
    )
