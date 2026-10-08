from __future__ import annotations

import json
import re
from csv import DictReader
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest

from tests.unit.validation_tolerances import TOL_SENSIBILIDAD_EV, ToleranceStatus

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "lr14_supercell_series_m1.json"
QUICKLOOK = ROOT / "tests" / "fixtures" / "lr14" / "lr14_quicklook.txt"
STEPS = ROOT / "tests" / "fixtures" / "lr14" / "supercell_steps.tsv"
PointKey = tuple[str, int, tuple[int, ...], int]


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


def _parse_k_grid(value: str) -> tuple[int, ...]:
    return tuple(int(component) for component in value.split("x"))


def _quicklook_u_points() -> dict[PointKey, Decimal]:
    text = QUICKLOOK.read_text(encoding="utf-8")
    table_rows = list(DictReader(text.splitlines()[:5], delimiter="\t"))
    assert len(table_rows) == 4
    points: dict[PointKey, Decimal] = {}
    for raw_row in table_rows:
        row = cast(dict[str, str], raw_row)
        key = (
            row["cell"],
            int(row["atoms"]),
            _parse_k_grid(row["kgrid"]),
            int(row["vacuum_A"]),
        )
        points[key] = Decimal(row["U_eV"])

    anchor_match = re.search(
        r"anchor: (?P<cell>\d+x\d+) production, kgrid (?P<kgrid>\d+x\d+x\d+) "
        r"\(k\*N=\d+\), vacuum (?P<vacuum>\d+) A, U = (?P<u>\d+\.\d+) eV",
        text,
    )
    assert anchor_match is not None
    anchor = next(point for point in _points() if point.get("role") == "anchor")
    anchor_key = (
        anchor_match.group("cell"),
        cast(int, anchor["atoms"]),
        _parse_k_grid(anchor_match.group("kgrid")),
        int(anchor_match.group("vacuum")),
    )
    points[anchor_key] = Decimal(anchor_match.group("u"))
    return points


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

    # Rounded fixture values give zero; the signed full-precision effect is retained from quicklook.
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


def test_quicklook_is_source_of_all_five_fixture_u_values_at_printed_precision() -> None:
    evidence_points = _quicklook_u_points()
    fixture_points = _points()
    assert len(evidence_points) == len(fixture_points) == 5

    for point in fixture_points:
        key = (
            cast(str, point["cell"]),
            cast(int, point["atoms"]),
            tuple(cast(list[int], point["k_grid"])),
            cast(int, point["vacuum_angstrom"]),
        )
        fixture_u = Decimal(f"{cast(float, point['u_ev']):.4f}")
        assert evidence_points[key].quantize(Decimal("0.0001")) == fixture_u

    quicklook_text = QUICKLOOK.read_text(encoding="utf-8")
    k_effect = re.search(
        r"k-sampling, 4x4 at fixed cell/vacuum:.*?dU=(?P<effect>[+-]\d+\.\d{4}) eV",
        quicklook_text,
    )
    assert k_effect is not None
    reported_effects = cast(dict[str, object], json.loads(FIXTURE.read_text(encoding="utf-8")))[
        "reported_effects"
    ]
    assert cast(dict[str, object], reported_effects)["k_grid_effect_ev"] == k_effect.group("effect")


def test_m1_fixture_records_source_roles_and_hashes_without_hash_gating() -> None:
    evidence = cast(dict[str, object], json.loads(FIXTURE.read_text(encoding="utf-8")))
    source = cast(dict[str, object], evidence["source"])
    quicklook = cast(dict[str, str], source["quicklook_file"])
    assert quicklook["path"] == "tests/fixtures/lr14/lr14_quicklook.txt"
    assert "source of the five U values" in quicklook["role"]
    steps = cast(dict[str, str], source["steps_file"])
    assert steps["path"] == "tests/fixtures/lr14/supercell_steps.tsv"
    assert "contains no U values" in steps["role"]
    assert len(quicklook["sha256"]) == 64
    assert len(steps["sha256"]) == 64
    assert QUICKLOOK.is_file()
    assert STEPS.is_file()

    archive = cast(dict[str, object], source["eight_by_eight_input_archive"])
    members = cast(dict[str, str], archive["members"])
    assert len(cast(str, archive["sha256"])) == 64
    assert set(members) == {
        "cells/n8_k3x3_v35/probe.fdf",
        "cells/n8_k3x3_v35/probe-lr-config.json",
    }
    assert all(len(digest) == 64 for digest in members.values())


def test_lr14_source_step_log_records_state_and_time_without_u_values() -> None:
    lines = STEPS.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 4
    assert all(len(line.split("\t")) == 3 for line in lines)
    assert all("U" not in line for line in lines)
    assert all("COMPLETED" in line for line in lines)
