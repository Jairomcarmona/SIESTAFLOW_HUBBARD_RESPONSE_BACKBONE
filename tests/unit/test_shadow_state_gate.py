"""Strict I.5 qualification for directly measured translation-shadow columns."""

from __future__ import annotations

import json
import lzma
from pathlib import Path

from hubbardflow.domain.state_gate import PointState, StateGatePoint, qualify_state_gate
from hubbardflow.domain.state_gate_results import (
    AmplitudeGateResult,
    CheckOutcome,
    StateCheck,
    StateCheckResult,
    StateGateMode,
    StateGateResult,
    StateGateVerdict,
    StatePointResult,
)
from hubbardflow.execution.lr_dag import LRDag
from hubbardflow.execution.state_gate_step import shadow_state_gate_passed, state_gate_mapping
from hubbardflow.siesta_backend.point_state_evidence import build_point_state
from hubbardflow.siesta_backend.siesta542_bare_profile import Siesta542PotentialShiftHamiltonianProfile
from hubbardflow.siesta_backend.siesta542_screened_selection import select_converged_screened_event


def _result(
    column: str,
    mode: StateGateMode,
    *,
    g4: CheckOutcome = CheckOutcome.PASS,
    verdict: StateGateVerdict = StateGateVerdict.PASS,
    g2: CheckOutcome = CheckOutcome.PASS,
) -> dict[str, object]:
    checks = tuple(
        StateCheckResult(check, outcome).to_mapping()
        for check, outcome in (
            (StateCheck.G1, CheckOutcome.PASS),
            (StateCheck.G2, g2),
            (StateCheck.G3A, CheckOutcome.PASS),
            (StateCheck.G4, g4),
        )
    )
    amplitudes = tuple(
        AmplitudeGateResult(
            amplitude_ev=alpha,
            positive=StatePointResult(alpha, tuple(StateCheckResult.from_mapping(item) for item in checks)),
            negative=StatePointResult(-alpha, tuple(StateCheckResult.from_mapping(item) for item in checks)),
            admissible=True,
            excluded_by_monotone_rule=False,
        )
        for alpha in (0.02, 0.04)
    )
    result = StateGateResult(
        policy_id="i5-state-policy-v1",
        column_id=column,
        mode=mode,
        verdict=verdict,
        amplitudes=amplitudes,
        admissible_amplitudes_ev=(0.02, 0.04),
        excluded_amplitudes_ev=(),
        reasons=(),
        smoothness=StateCheckResult(StateCheck.G3, CheckOutcome.NOT_ESTABLISHED),
    )
    return result.to_mapping()


def _mapping(*pairs: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": "hubbardflow.i5_state_gate.v1",
        "policy_id": "i5-state-policy-v1",
        "pairs": list(pairs),
    }


def test_all_point_checks_pass_and_smoothness_not_established_are_allowed() -> None:
    state_gate = _mapping(*(_result(site, mode) for site in ("MnLR00", "MnLR02") for mode in StateGateMode))

    assert shadow_state_gate_passed(state_gate, ("MnLR00", "MnLR02"))


def test_g4_not_available_blocks_even_when_diagnostic_verdict_passes() -> None:
    state_gate = _mapping(
        *(
            _result(site, mode, g4=CheckOutcome.NOT_AVAILABLE)
            for site in ("MnLR00",)
            for mode in StateGateMode
        )
    )

    assert not shadow_state_gate_passed(state_gate, ("MnLR00",))


def test_any_failed_or_unestablished_point_check_blocks() -> None:
    for outcome in (CheckOutcome.FAIL, CheckOutcome.NOT_ESTABLISHED):
        state_gate = _mapping(*(_result("MnLR00", mode, g2=outcome) for mode in StateGateMode))
        assert not shadow_state_gate_passed(state_gate, ("MnLR00",))


def test_missing_pair_blocks_and_not_defined_g2_is_allowed() -> None:
    missing = _mapping(_result("MnLR00", StateGateMode.BARE))
    assert not shadow_state_gate_passed(missing, ("MnLR00",))

    allowed = _mapping(*(_result("MnLR00", mode, g2=CheckOutcome.NOT_DEFINED) for mode in StateGateMode))
    assert shadow_state_gate_passed(allowed, ("MnLR00",))


def test_duplicate_pairs_and_missing_requested_columns_fail_closed() -> None:
    pair = _result("MnLR00", StateGateMode.BARE)
    duplicate = _mapping(pair, pair, _result("MnLR00", StateGateMode.SCREENED))
    assert not shadow_state_gate_passed(duplicate, ("MnLR00",))
    assert not shadow_state_gate_passed(_mapping(pair), ("MnLR01",))


def test_real_nio_replay_gate_is_rejected_when_g4_is_unavailable() -> None:
    fixture = Path(__file__).parents[1] / "fixtures" / "replay_nio_p5" / "replay_i5_state_gate.json"
    state_gate = json.loads(fixture.read_text(encoding="utf-8"))
    pairs = state_gate["pairs"]
    measured_columns = sorted({pair["column_id"] for pair in pairs})

    assert len(measured_columns) == 2
    assert all(pair["verdict"] == "PASS" for pair in pairs)
    assert not shadow_state_gate_passed(state_gate, measured_columns)


def _real_nio_state(stem: str) -> PointState:
    fixture_dir = Path(__file__).parents[1] / "fixtures" / "i5_real_nio"
    output = lzma.decompress((fixture_dir / f"{stem}.out.xz").read_bytes()).decode("utf-8")
    eig = lzma.decompress((fixture_dir / f"{stem}.EIG.xz").read_bytes()).decode("utf-8")
    if stem == "NIO_PBE_REFERENCE" or stem.endswith("_screened"):
        event = select_converged_screened_event(output)
    else:
        event = Siesta542PotentialShiftHamiltonianProfile().select_response(output).response_event
    return build_point_state(event, output, eig)


def test_real_nio_fixtures_with_eig_satisfy_shadow_state_gate() -> None:
    reference = _real_nio_state("NIO_PBE_REFERENCE")
    pairs = []
    for site in (0, 1):
        for mode in ("bare", "screened"):
            points = []
            for sign in ("m", "p"):
                for amplitude in ("0p02", "0p04", "0p06"):
                    stem = f"lr_s{site:03}_{sign}{amplitude}_{mode}"
                    alpha = (-1.0 if sign == "m" else 1.0) * float(amplitude.replace("p", "."))
                    points.append(StateGatePoint(alpha, True, _real_nio_state(stem)))
            pairs.append(
                qualify_state_gate(reference, f"NiLR{site}", mode.upper(), tuple(points)).to_mapping()
            )

    state_gate = _mapping(*pairs)

    assert all(pair["verdict"] == "PASS" for pair in pairs)
    assert shadow_state_gate_passed(state_gate, ("NiLR0", "NiLR1"))


def test_site_index_filter_marks_reconstructed_columns_without_evaluating_them() -> None:
    mapping = state_gate_mapping(
        dag=LRDag((), False),
        specs={},
        records={},
        checkpoint={},
        sites=({"site_id": "MnLR00"}, {"site_id": "MnLR01"}),
        alpha_grid_ev=(0.02,),
        bare_profile=None,
        covered=False,
        site_indices=(0,),
    )
    pairs = mapping["pairs"]
    assert isinstance(pairs, list)
    first = [pair for pair in pairs if pair["column_id"] == "MnLR00"]
    second = [pair for pair in pairs if pair["column_id"] == "MnLR01"]
    assert {pair["reasons"][0] for pair in first} == {"PATH_NOT_COVERED"}
    assert {pair["reasons"][0] for pair in second} == {"RECONSTRUCTED_FROM_REPRESENTATIVE"}
