from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from tests.unit.validation_tolerances import TOL_SENSIBILIDAD_EV, ToleranceStatus

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "lr14_supercell_series_m1.json"


def _points() -> list[dict[str, object]]:
    evidence = cast(dict[str, object], json.loads(FIXTURE.read_text(encoding="utf-8")))
    return cast(list[dict[str, object]], evidence["points"])


def _u_ev(cell: str, k_grid: list[int], vacuum_angstrom: int) -> float:
    matches = [
        point
        for point in _points()
        if point["cell"] == cell and point["k_grid"] == k_grid and point["vacuum_angstrom"] == vacuum_angstrom
    ]
    assert len(matches) == 1
    return cast(float, matches[0]["u_ev"])


def test_m1_supercell_series_recalculates_controlled_effects_from_fixture() -> None:
    """Recompute the reported increments instead of copying derived values."""
    tolerance = TOL_SENSIBILIDAD_EV
    assert tolerance.value == 0.01
    assert tolerance.unit == "eV"
    assert tolerance.status is ToleranceStatus.DECLARED_BY_OWNER
    assert tolerance.declaration_date == "2026-10-07"
    assert tolerance.scope is not None
    assert "does not cover projector dependence" in tolerance.scope.lower()

    reference_4x4 = _u_ev("4x4", [4, 4, 1], 35)
    u_4x4_vacuum_45 = _u_ev("4x4", [4, 4, 1], 45)
    u_4x4_k5 = _u_ev("4x4", [5, 5, 1], 35)
    u_6x6 = _u_ev("6x6", [3, 3, 1], 33)
    u_8x8 = _u_ev("8x8", [3, 3, 1], 35)

    k_grid_effect_ev = u_4x4_k5 - reference_4x4
    vacuum_effect_ev = u_4x4_vacuum_45 - reference_4x4
    delta_4x4_to_6x6_ev = u_6x6 - reference_4x4
    delta_6x6_to_8x8_ev = u_8x8 - u_6x6
    all_u_values = [cast(float, point["u_ev"]) for point in _points()]
    dispersion_ev = max(all_u_values) - min(all_u_values)

    # The four-decimal fixture cannot recover the sign of the reported -0.0000 k-grid effect.
    assert k_grid_effect_ev == pytest.approx(0.0, abs=1e-12)
    assert vacuum_effect_ev == pytest.approx(-0.0001, abs=1e-12)
    assert delta_4x4_to_6x6_ev == pytest.approx(-0.0059, abs=1e-12)
    assert delta_6x6_to_8x8_ev == pytest.approx(0.0053, abs=1e-12)
    assert dispersion_ev == pytest.approx(0.0059, abs=1e-12)

    assert tolerance.value is not None
    effects = (
        abs(k_grid_effect_ev),
        abs(vacuum_effect_ev),
        abs(delta_4x4_to_6x6_ev),
        abs(delta_6x6_to_8x8_ev),
        dispersion_ev,
    )
    state = (
        "PASS_WITHIN_DECLARED_TOLERANCE"
        if all(value <= tolerance.value for value in effects)
        else "OUTSIDE_DECLARED_TOLERANCE"
    )
    assert state == "PASS_WITHIN_DECLARED_TOLERANCE"


def test_m1_supercell_fixture_records_hashed_inputs_and_pending_steps_tsv() -> None:
    evidence = cast(dict[str, object], json.loads(FIXTURE.read_text(encoding="utf-8")))
    source = cast(dict[str, object], evidence["source"])
    archive = cast(dict[str, object], source["eight_by_eight_input_archive"])
    members = cast(dict[str, str], archive["members"])
    assert archive["sha256"] == "f429dd1d5f2cd104d5e5ef1264a726b9d40f425a5419069fda2f1719522a57bb"
    assert set(members) == {
        "cells/n8_k3x3_v35/probe.fdf",
        "cells/n8_k3x3_v35/probe-lr-config.json",
    }
    steps_file = cast(dict[str, str], source["steps_file"])
    assert steps_file["status"] == "PENDING_ARTIFACT"
    assert steps_file["name"] == "supercell_steps.tsv"
    assert steps_file["k_grid_effect_sign_status"] == "PENDING_ARTIFACT"
