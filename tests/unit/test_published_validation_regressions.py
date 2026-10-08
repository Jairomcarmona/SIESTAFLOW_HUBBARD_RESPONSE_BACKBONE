from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from tests.unit.validation_tolerances import (
    CU3N_MATRIX_PERMUTATION_TOLERANCE,
    CU3N_U_SPREAD_RECOMPUTATION_TOLERANCE_EV,
    M1_PROBE_CAMPAIGN_DELTA_TOLERANCE_EV,
    M1_PROJECTOR_SCAN_U_TOLERANCE_EV,
    MNO_LAPTOP_U_TOLERANCE,
    SIGNAL_RESTART_TOLERANCE,
    ToleranceStatus,
)

ROOT = Path(__file__).resolve().parents[2]
M1_CURVE = ROOT / "tests" / "fixtures" / "projector_curve_m1.json"
CU3N_EVIDENCE = ROOT / "docs" / "evidence" / "cu3n_mathematical_20260812" / "CU3N_PBE_LRU_SC222_RC3p0_V1.json"


def _coordinate_key(values: list[float]) -> tuple[float, ...]:
    return tuple(round(float(value) % 1.0, 8) for value in values)


def _translation_permutations(site_map: list[dict[str, object]]) -> list[dict[int, int]]:
    coordinates = [cast(list[float], site["fractional_supercell"]) for site in site_map]
    orientations = [str(site["orientation"]) for site in site_map]
    indices = [cast(int, site["index"]) for site in site_map]
    lookup = {
        (orientations[position], _coordinate_key(coordinates[position])): indices[position]
        for position in range(len(site_map))
    }
    representative_orientation = orientations[0]
    representative_coordinate = coordinates[0]
    shifts = {
        tuple(
            round((target - origin) % 1.0, 8)
            for origin, target in zip(representative_coordinate, coordinates[position], strict=True)
        )
        for position in range(len(site_map))
        if orientations[position] == representative_orientation
    }
    permutations: list[dict[int, int]] = []
    for shift in sorted(shifts):
        permutation = {
            indices[position]: lookup[
                (
                    orientations[position],
                    _coordinate_key(
                        [
                            coordinate + displacement
                            for coordinate, displacement in zip(coordinates[position], shift, strict=True)
                        ]
                    ),
                )
            ]
            for position in range(len(site_map))
        }
        assert len(set(permutation.values())) == len(site_map)
        permutations.append(permutation)
    return permutations


def test_cu3n_archived_translation_reconstruction_is_self_consistent() -> None:
    """Check the archived matrices under their eight certified pure translations.

    This is archive self-consistency. It does not replace the missing direct
    shadow response recorded as xfailed in test_cu3n_symmetry_shadow_package.
    """
    evidence = cast(dict[str, object], json.loads(CU3N_EVIDENCE.read_text(encoding="utf-8")))
    site_map = cast(list[dict[str, object]], evidence["site_map"])
    matrices = cast(dict[str, object], evidence["matrices"])
    permutations = _translation_permutations(site_map)

    assert len(site_map) == 24
    assert len(permutations) == 8
    assert evidence["status"] == "PASS"
    u_tolerance = CU3N_U_SPREAD_RECOMPUTATION_TOLERANCE_EV.value
    assert u_tolerance is not None
    assert evidence["U_Cu_eV"] == pytest.approx(12.673925610317943, abs=u_tolerance)

    matrix_tolerance = CU3N_MATRIX_PERMUTATION_TOLERANCE.value
    assert matrix_tolerance is not None
    for matrix_name in ("chi0_raw_electrons_per_eV", "chi_raw_electrons_per_eV"):
        matrix = cast(list[list[float]], matrices[matrix_name])
        for permutation in permutations:
            residual = max(
                abs(matrix[source][target] - matrix[permutation[source]][permutation[target]])
                for source in permutation
                for target in permutation
            )
            assert residual <= matrix_tolerance

    grouped_u: dict[str, list[float]] = {}
    site_u = cast(list[float], matrices["U_by_site_eV"])
    for site, value in zip(site_map, site_u, strict=True):
        grouped_u.setdefault(str(site["orientation"]), []).append(value)
    assert len(grouped_u) == 3
    assert sorted(len(values) for values in grouped_u.values()) == [8, 8, 8]
    orbit_spread = max(max(values) - min(values) for values in grouped_u.values())
    u_tolerance = CU3N_U_SPREAD_RECOMPUTATION_TOLERANCE_EV.value
    assert u_tolerance is not None
    assert orbit_spread <= u_tolerance


def test_m1_probe_vs_full_campaign_delta_matches_archived_control() -> None:
    fixture = cast(dict[str, object], json.loads(M1_CURVE.read_text(encoding="utf-8")))
    control = cast(dict[str, object], fixture["production_control"])
    probe_u = cast(float, control["one_column_u_ev"])
    campaign_range = cast(list[float], control["campaign_36x36_u_ev_range"])
    maximum_difference = cast(float, control["maximum_absolute_difference_ev"])
    delta_tolerance = M1_PROBE_CAMPAIGN_DELTA_TOLERANCE_EV.value
    assert delta_tolerance is not None

    assert probe_u - campaign_range[1] == pytest.approx(0.0036, abs=delta_tolerance)
    assert probe_u - campaign_range[0] == pytest.approx(maximum_difference, abs=delta_tolerance)
    assert maximum_difference == pytest.approx(0.0044, abs=delta_tolerance)


def test_nine_point_m1_projector_scan_matches_measured_values() -> None:
    fixture = cast(dict[str, object], json.loads(M1_CURVE.read_text(encoding="utf-8")))
    points = cast(list[dict[str, object]], fixture["points"])
    expected_cutoff_norm = [0.50, 0.60, 0.70, 0.80, 0.85, 0.90, 0.95, 0.98, 0.99]
    expected_u_ev = [25.0833, 19.0979, 15.4146, 13.0972, 12.0211, 10.6622, 8.2302, 6.2659, 5.5708]

    assert [cast(dict[str, object], point["projector"])["value"] for point in points] == expected_cutoff_norm
    measured_u = [cast(float, point["u_ev"]) for point in points]
    scan_tolerance = M1_PROJECTOR_SCAN_U_TOLERANCE_EV.value
    assert scan_tolerance is not None
    assert measured_u == pytest.approx(expected_u_ev, abs=scan_tolerance)
    assert fixture["verification"] == {
        "fdf_change": "DFTU.CutoffNorm line only",
        "diff_verified": True,
        "magnetic_moment_range_mu_b": [2.9183, 2.9207],
    }


@pytest.mark.xfail(
    run=False,
    strict=False,
    reason="PENDIENTE_MNO_LAPTOP_ARTIFACT: no paired laptop MnO campaign output/analysis is checked into the repository.",
)
def test_mno_yoltla_vs_laptop_regression() -> None:
    assert MNO_LAPTOP_U_TOLERANCE.status is ToleranceStatus.PENDING_ARTIFACT
    pytest.fail(
        "Add the matched laptop campaign artifact and reviewed tolerance before enabling this comparison."
    )


@pytest.mark.xfail(
    run=False,
    strict=False,
    reason="PENDIENTE_SIGNAL_RESTART_ARTIFACT: no archived campaign attempt terminated by signal and then resumed is present.",
)
def test_campaign_restart_after_signal_regression() -> None:
    assert SIGNAL_RESTART_TOLERANCE.status is ToleranceStatus.NOT_NUMERIC
    pytest.fail("Add the signal-interrupted campaign record before enabling this end-to-end regression.")
