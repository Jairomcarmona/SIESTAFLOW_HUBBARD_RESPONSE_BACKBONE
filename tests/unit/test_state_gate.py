"""Synthetic state-gate regressions plus the real NiO P5 campaign."""

from __future__ import annotations

import lzma
from pathlib import Path

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from hubbardflow.domain.state_gate import (
    AtomPointState,
    BandEvidenceStatus,
    PointState,
    PrintedBandEnergy,
    StateGateError,
    StateGatePoint,
    qualify_state_gate,
)
from hubbardflow.domain.state_gate_results import (
    CheckOutcome,
    StateCheck,
    StateGateMode,
    StateGateReason,
    StateGateVerdict,
)
from hubbardflow.siesta_backend.point_state_evidence import build_point_state
from hubbardflow.siesta_backend.siesta542_bare_profile import (
    Siesta542PotentialShiftHamiltonianProfile,
)
from hubbardflow.siesta_backend.siesta542_screened_selection import (
    select_converged_screened_event,
)

FIXTURES = Path(__file__).parents[1] / "fixtures"
REAL_FIXTURES = FIXTURES / "i5_real_nio"
_NO_BANDS: tuple[PrintedBandEnergy, ...] = ()


def _atom(
    levels: tuple[float, float, float, float, float],
    *,
    atom_index: int = 1,
    sz_e: float = 0.8,
) -> AtomPointState:
    matrix = tuple(
        tuple(f"{levels[row]:.5f}" if row == column else "0.00000" for column in range(5)) for row in range(5)
    )
    return AtomPointState(
        atom_index=atom_index,
        matrix_up=matrix,
        matrix_down=matrix,
        matrix_print_quantum_e=1e-5,
        sz_e=sz_e,
        sz_half_width_e=5e-7,
    )


def _state(
    atom: AtomPointState,
    *,
    bands: tuple[PrintedBandEnergy, ...] = _NO_BANDS,
    band_status: BandEvidenceStatus = BandEvidenceStatus.NOT_AVAILABLE,
    fermi_token: str = "-0.450851397E+01",
    stdout_token: str = "-4.508514",
    fermi_quantum: float = 1e-8,
    stdout_half_width: float = 5e-7,
) -> PointState:
    fermi_ev = float(fermi_token)
    return PointState(
        atoms=(atom,),
        fermi_energy_ev=fermi_ev,
        fermi_energy_token=fermi_token,
        fermi_print_quantum_ev=fermi_quantum,
        fermi_stdout_energy_ev=float(stdout_token),
        fermi_stdout_token=stdout_token,
        fermi_stdout_half_width_ev=stdout_half_width,
        band_evidence_status=band_status,
        band_energies=bands,
    )


def _point(alpha: float, state: PointState, *, validated: bool = True) -> StateGatePoint:
    return StateGatePoint(alpha_ev=alpha, node_validated=validated, state=state)


def _check_for(report: object, signed_alpha: float, check: StateCheck, atom: int = 1, spin: int = 1):
    amplitudes = report.amplitudes  # type: ignore[attr-defined]
    amplitude = next(item for item in amplitudes if item.amplitude_ev == abs(signed_alpha))
    point = amplitude.positive if signed_alpha > 0 else amplitude.negative
    return next(
        result
        for result in point.checks
        if result.check is check and result.atom_index in (None, atom) and result.spin in (None, spin)
    )


def test_r11_reference_defined_k_and_point_margin_is_ambiguous() -> None:
    reference = _state(_atom((1.0, 0.9, 0.9, 0.9, 0.9)))
    point_state = _state(_atom((1.0, 0.99989, 0.99989, 0.99989, 0.99989)))

    report = qualify_state_gate(
        reference,
        "NiLR0",
        StateGateMode.BARE,
        (_point(0.06, point_state), _point(-0.06, point_state)),
    )

    result = _check_for(report, 0.06, StateCheck.G2)
    assert result.outcome is CheckOutcome.FAIL
    assert result.reasons == (StateGateReason.SUBSPACE_AMBIGUOUS,)
    assert dict(result.details)["epsilon"] == pytest.approx(0.83383358346)
    assert report.verdict is StateGateVerdict.FAIL
    assert report.excluded_amplitudes_ev == (0.06,)


def test_degenerate_reference_has_non_failing_not_defined_g2() -> None:
    state = _state(_atom((1.0, 1.0, 1.0, 1.0, 1.0)))

    report = qualify_state_gate(state, "NiLR0", "SCREENED", (_point(0.04, state), _point(-0.04, state)))

    assert _check_for(report, 0.04, StateCheck.G2).outcome is CheckOutcome.NOT_DEFINED
    assert report.verdict is StateGateVerdict.PASS


def test_changed_largest_gap_index_fails_as_occupation_count_change() -> None:
    reference = _state(_atom((1.0, 0.9, 0.9, 0.9, 0.9)))
    point_state = _state(_atom((1.0, 0.9, 0.7, 0.7, 0.7)))

    report = qualify_state_gate(
        reference, "NiLR0", "BARE", (_point(0.02, point_state), _point(-0.02, point_state))
    )

    result = _check_for(report, 0.02, StateCheck.G2)
    assert result.reasons == (StateGateReason.OCCUPATION_COUNT_CHANGED,)
    assert report.excluded_amplitudes_ev == (0.02,)


def test_r11_ambiguous_reference_index_margin_precedes_moved_gap_reason() -> None:
    reference = _state(_atom((1.0, 0.9, 0.9, 0.9, 0.9)))
    point_state = _state(_atom((1.0, 0.99999, 0.8, 0.7, 0.6)))

    report = qualify_state_gate(
        reference, "NiLR0", "BARE", (_point(0.02, point_state), _point(-0.02, point_state))
    )

    result = _check_for(report, 0.02, StateCheck.G2)
    assert result.reasons == (StateGateReason.SUBSPACE_AMBIGUOUS,)
    assert report.excluded_amplitudes_ev == (0.02,)


def test_full_occupied_unoccupied_rotation_fails_orbital_order() -> None:
    reference_atom = _atom((1.0, 0.9, 0.89, 0.88, 0.8))
    diagonal = np.diag([1.0, 0.9, 0.89, 0.88, 0.8])
    swap = np.eye(5)
    swap[[0, 4]] = swap[[4, 0]]
    rotated = swap @ diagonal @ swap.T
    rotated_tokens = tuple(tuple(f"{value:.5f}" for value in row) for row in rotated)
    point_atom = AtomPointState(1, rotated_tokens, rotated_tokens, 1e-5, 0.8, 5e-7)
    reference = _state(reference_atom)
    point_state = _state(point_atom)

    report = qualify_state_gate(
        reference, "NiLR0", "BARE", (_point(0.06, point_state), _point(-0.06, point_state))
    )

    assert _check_for(report, 0.06, StateCheck.G2).reasons == (StateGateReason.ORBITAL_ORDER_CHANGED,)
    assert report.excluded_amplitudes_ev == (0.06,)


@pytest.mark.parametrize("basis_angle", [0.0, 0.37])
def test_partial_leak_cosine_is_basis_independent_in_degenerate_clusters(
    basis_angle: float,
) -> None:
    reference_matrix = np.diag([1.2, 1.2, 0.9, 0.9, 0.9])
    theta = float(np.arccos(np.sqrt(0.4)))
    leak = np.eye(5)
    leak[1, 1] = np.cos(theta)
    leak[2, 2] = np.cos(theta)
    leak[1, 2] = -np.sin(theta)
    leak[2, 1] = np.sin(theta)
    occupied = np.eye(5)
    occupied[0, 0] = np.cos(basis_angle)
    occupied[1, 1] = np.cos(basis_angle)
    occupied[0, 1] = -np.sin(basis_angle)
    occupied[1, 0] = np.sin(basis_angle)
    rotation = occupied @ leak @ occupied.T
    point_matrix = rotation @ reference_matrix @ rotation.T
    reference_tokens = tuple(tuple(f"{value:.5f}" for value in row) for row in reference_matrix)
    point_tokens = tuple(tuple(f"{value:.5f}" for value in row) for row in point_matrix)
    reference_atom = AtomPointState(1, reference_tokens, reference_tokens, 1e-5, 0.8, 5e-7)
    point_atom = AtomPointState(1, point_tokens, point_tokens, 1e-5, 0.8, 5e-7)
    reference, point_state = _state(reference_atom), _state(point_atom)

    report = qualify_state_gate(
        reference, "NiLR0", "BARE", (_point(0.04, point_state), _point(-0.04, point_state))
    )

    result = _check_for(report, 0.04, StateCheck.G2, spin=1)
    assert result.outcome is CheckOutcome.FAIL
    assert result.reasons == (StateGateReason.ORBITAL_ORDER_CHANGED,)
    assert dict(result.details)["cosine_squared"] == pytest.approx(0.4, abs=2e-4)


def test_moment_sign_flip_excludes_that_and_larger_amplitudes() -> None:
    reference = _state(_atom((1.0, 0.9, 0.9, 0.9, 0.9), sz_e=0.8))
    same = _state(_atom((1.0, 0.9, 0.9, 0.9, 0.9), sz_e=0.8))
    flipped = _state(_atom((1.0, 0.9, 0.9, 0.9, 0.9), sz_e=-0.8))
    points = tuple(
        _point(alpha, flipped if alpha == 0.04 else same) for alpha in (-0.06, -0.04, -0.02, 0.02, 0.04, 0.06)
    )

    report = qualify_state_gate(reference, "NiLR0", "SCREENED", points)

    assert _check_for(report, 0.04, StateCheck.G3A).reasons == (StateGateReason.MOMENT_SIGN_CHANGED,)
    assert report.admissible_amplitudes_ev == (0.02,)
    assert report.excluded_amplitudes_ev == (0.04, 0.06)


def _band(token: str, *, spin: int = 1, kpoint: int = 1) -> PrintedBandEnergy:
    energy = float(token.replace("D", "E").replace("d", "e"))
    mantissa, _, exponent_text = token.lower().replace("d", "e").partition("e")
    places = len(mantissa.partition(".")[2]) if "." in mantissa else 0
    exponent = int(exponent_text) if exponent_text else 0
    quantum = 10.0 ** (exponent - places)
    return PrintedBandEnergy(
        kpoint=kpoint,
        spin=spin,
        energy_ev=energy,
        energy_token=token,
        distance_to_fermi_ev=0.0,
        print_quantum_ev=quantum,
    )


def test_r12_inclusive_eig_precision_boundary_is_band_count_ambiguous() -> None:
    reference_atom = _atom((1.0, 0.9, 0.9, 0.9, 0.9))
    ef = "-0.450851397E+01"
    ref_bands = (_band("-0.500000000E+01"), _band("-0.400000000E+01", spin=1, kpoint=2))
    reference = _state(
        reference_atom,
        bands=ref_bands,
        band_status=BandEvidenceStatus.AVAILABLE,
        fermi_token=ef,
        stdout_token="-4.508514",
    )
    point_band = _band("-0.450851396E+01")
    assert point_band.energy_ev == pytest.approx(-4.50851396)
    point_bands = (point_band, _band("-0.400000000E+01", kpoint=2))
    point_state = _state(
        reference_atom,
        bands=point_bands,
        band_status=BandEvidenceStatus.AVAILABLE,
        fermi_token=ef,
        stdout_token="-4.508514",
    )

    report = qualify_state_gate(
        reference, "NiLR0", "BARE", (_point(0.02, point_state), _point(-0.02, point_state))
    )

    assert _check_for(report, 0.02, StateCheck.G4).reasons == (StateGateReason.BAND_COUNT_AMBIGUOUS,)


def test_r12_ambiguous_reference_makes_g4_not_applicable() -> None:
    atom = _atom((1.0, 0.9, 0.9, 0.9, 0.9))
    ef = "-0.450851397E+01"
    ambiguous_reference = _state(
        atom,
        bands=(_band("-0.450851396E+01"), _band("-0.400000000E+01", kpoint=2)),
        band_status=BandEvidenceStatus.AVAILABLE,
        fermi_token=ef,
        stdout_token="-4.508514",
    )
    point = _state(
        atom,
        bands=(_band("-0.500000000E+01"), _band("-0.400000000E+01", kpoint=2)),
        band_status=BandEvidenceStatus.AVAILABLE,
        fermi_token=ef,
        stdout_token="-4.508514",
    )

    report = qualify_state_gate(
        ambiguous_reference, "NiLR0", "BARE", (_point(0.02, point), _point(-0.02, point))
    )

    assert _check_for(report, 0.02, StateCheck.G4).outcome is CheckOutcome.NOT_APPLICABLE


def test_g4_crossing_changes_band_count_when_clear_of_quantum_interval() -> None:
    atom = _atom((1.0, 0.9, 0.9, 0.9, 0.9))
    ef = "-0.450851397E+01"
    ref_bands = (_band("-0.500000000E+01"), _band("-0.400000000E+01", kpoint=2))
    ref = _state(atom, bands=ref_bands, band_status=BandEvidenceStatus.AVAILABLE, fermi_token=ef)
    crossed = _state(
        atom,
        bands=(_band("-0.400000000E+01"), _band("-0.300000000E+01", kpoint=2)),
        band_status=BandEvidenceStatus.AVAILABLE,
        fermi_token=ef,
    )

    report = qualify_state_gate(ref, "NiLR0", "BARE", (_point(0.02, crossed), _point(-0.02, crossed)))

    assert _check_for(report, 0.02, StateCheck.G4).reasons == (StateGateReason.BAND_COUNT_CHANGED,)


def test_g4_stdout_eig_mismatch_is_not_established() -> None:
    atom = _atom((1.0, 0.9, 0.9, 0.9, 0.9))
    bands = (_band("-0.500000000E+01"), _band("-0.400000000E+01", kpoint=2))
    ref = _state(atom, bands=bands, band_status=BandEvidenceStatus.AVAILABLE, stdout_token="-4.507")

    report = qualify_state_gate(ref, "NiLR0", "BARE", (_point(0.02, ref), _point(-0.02, ref)))

    assert report.verdict is StateGateVerdict.NOT_ESTABLISHED
    assert _check_for(report, 0.02, StateCheck.G4).outcome is CheckOutcome.NOT_ESTABLISHED
    assert StateGateReason.EIG_STDOUT_FERMI_MISMATCH in report.reasons


@given(st.permutations((-0.02, 0.02)))
def test_point_input_order_does_not_change_gate_result(alphas: tuple[float, ...]) -> None:
    state = _state(_atom((1.0, 0.9, 0.9, 0.9, 0.9)))
    points = tuple(_point(alpha, state) for alpha in alphas)

    report = qualify_state_gate(state, "NiLR0", "BARE", points)

    assert report.verdict is StateGateVerdict.PASS
    assert report.admissible_amplitudes_ev == (0.02,)


@pytest.mark.parametrize("alpha", [float("nan"), float("inf"), float("-inf"), 0.0])
def test_non_finite_or_zero_amplitude_is_rejected(alpha: float) -> None:
    with pytest.raises(StateGateError, match="alpha_ev"):
        StateGatePoint(alpha_ev=alpha, node_validated=True, state=None)


def _real_state(stem: str) -> PointState:
    output = lzma.decompress((REAL_FIXTURES / f"{stem}.out.xz").read_bytes()).decode("utf-8")
    eig = lzma.decompress((REAL_FIXTURES / f"{stem}.EIG.xz").read_bytes()).decode("utf-8")
    if stem == "NIO_PBE_REFERENCE":
        event = select_converged_screened_event(output)
    elif stem.endswith("_bare"):
        event = Siesta542PotentialShiftHamiltonianProfile().select_response(output).response_event
    else:
        event = select_converged_screened_event(output)
    return build_point_state(event, output, eig)


def test_all_four_real_nio_p5_column_mode_pairs_pass() -> None:
    reference = _real_state("NIO_PBE_REFERENCE")
    for site in (0, 1):
        for mode in ("bare", "screened"):
            points: list[StateGatePoint] = []
            for sign in ("m", "p"):
                for amplitude in ("0p02", "0p04", "0p06"):
                    stem = f"lr_s{site:03}_{sign}{amplitude}_{mode}"
                    alpha = (-1.0 if sign == "m" else 1.0) * float(amplitude.replace("p", "."))
                    point_state = _real_state(stem)
                    if stem == "lr_s000_p0p04_bare":
                        assert abs(
                            point_state.fermi_stdout_energy_ev - point_state.fermi_energy_ev
                        ) == pytest.approx(3e-8)
                        assert point_state.fermi_stdout_half_width_ev == pytest.approx(5e-7)
                        assert point_state.fermi_print_quantum_ev / 2 == pytest.approx(5e-9)
                    points.append(_point(alpha, point_state))
            report = qualify_state_gate(reference, f"NiLR{site}", mode.upper(), tuple(points))
            assert report.verdict is StateGateVerdict.PASS, report.to_mapping()
            assert len(report.admissible_amplitudes_ev) == 3
