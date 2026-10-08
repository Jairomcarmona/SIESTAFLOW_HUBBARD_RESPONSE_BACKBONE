from __future__ import annotations

import json
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from hubbardflow.domain.projector_diagnostics import (
    ComparisonStatus,
    LigandChargeCaptureStatus,
    ProjectorDiagnosticError,
    ProjectorDiagnosticInput,
    ProjectorDiagnostics,
    SiteElectronReference,
    build_projector_diagnostics,
)
from hubbardflow.reporting.lr_u_report import render_lr_u_report

ROOT = Path(__file__).resolve().parents[2]


def test_per_site_electron_comparisons_and_regime_indicator_are_record_only() -> None:
    result = build_projector_diagnostics(
        [
            ProjectorDiagnosticInput(
                site_id="MnLR00",
                reference_occupation_e=5.2,
                u_ev=12.0,
                chi0_diagonal_per_ev=-0.25,
                electron_reference=SiteElectronReference(
                    formal_d_electrons=3.0,
                    free_atom_d_electrons=5.0,
                ),
            )
        ],
        projector_generation_method=2,
    )

    site = result.sites[0]
    assert result.status.value == "RECORD_ONLY"
    assert result.decision_role.value == "RECORD_ONLY"
    assert site.difference_from_formal_d_e == pytest.approx(2.2)
    assert site.difference_from_free_atom_d_e == pytest.approx(0.2)
    assert site.formal_comparison is ComparisonStatus.RECORDED
    assert site.ligand_charge_capture is LigandChargeCaptureStatus.CAPTURE_INDICATED
    assert site.u_times_abs_chi0 == pytest.approx(3.0)
    assert site.regime_indicator_status is ComparisonStatus.RECORDED
    assert result.method2_warning.to_mapping() == {
        "code": "SIESTA_METHOD_2_ATOMIC_NONORTHOGONALIZED_PROJECTOR",
        "severity": "WARNING",
        "decision_role": "RECORD_ONLY",
        "projector_generation_method": 2,
        "atomic": True,
        "orthogonalized": False,
        "comparable_to_orthogonalized_projector_u": False,
        "message": (
            "SIESTA Method 2 uses atomic, non-orthogonalized projectors; its U is not comparable "
            "to U values from orthogonalized projector schemes."
        ),
    }


def test_missing_references_and_response_values_remain_unassessed() -> None:
    result = build_projector_diagnostics(
        [
            ProjectorDiagnosticInput(
                site_id="Co",
                reference_occupation_e=4.0,
                u_ev=None,
                chi0_diagonal_per_ev=None,
            )
        ],
        projector_generation_method=2,
    )
    site = result.sites[0]
    assert site.formal_comparison is ComparisonStatus.NOT_ASSESSED
    assert site.ligand_charge_capture is LigandChargeCaptureStatus.NOT_ASSESSED
    assert site.regime_indicator_status is ComparisonStatus.NOT_ASSESSED
    assert site.u_times_abs_chi0 is None


@given(
    st.permutations(
        (
            ProjectorDiagnosticInput("MnLR01", 4.4, 9.5, -0.2, SiteElectronReference(3.0, 5.0)),
            ProjectorDiagnosticInput("MnLR00", 4.3, 9.0, -0.3, SiteElectronReference(3.0, 5.0)),
            ProjectorDiagnosticInput("MnLR02", 4.5, 8.5, -0.4, SiteElectronReference(3.0, 5.0)),
        )
    )
)
def test_site_input_order_does_not_change_diagnostic_mapping(
    permuted: tuple[ProjectorDiagnosticInput, ...],
) -> None:
    baseline = (
        ProjectorDiagnosticInput("MnLR00", 4.3, 9.0, -0.3, SiteElectronReference(3.0, 5.0)),
        ProjectorDiagnosticInput("MnLR01", 4.4, 9.5, -0.2, SiteElectronReference(3.0, 5.0)),
        ProjectorDiagnosticInput("MnLR02", 4.5, 8.5, -0.4, SiteElectronReference(3.0, 5.0)),
    )
    assert build_projector_diagnostics(permuted, projector_generation_method=2).to_mapping() == (
        build_projector_diagnostics(baseline, projector_generation_method=2).to_mapping()
    )


def test_nine_point_m1_recorded_regime_indicators_match_the_supplied_fixture() -> None:
    fixture = json.loads((ROOT / "tests/fixtures/projector_curve_m1.json").read_text(encoding="utf-8"))
    site_inputs = [
        ProjectorDiagnosticInput(
            site_id=f"MnLR00-{point['projector']['value']}",
            reference_occupation_e=point["n_ref_e"],
            u_ev=point["u_ev"],
            chi0_diagonal_per_ev=point["u_times_abs_chi0"] / point["u_ev"],
            electron_reference=SiteElectronReference(
                formal_d_electrons=fixture["formal_d_electrons"],
                free_atom_d_electrons=fixture["free_atom_d_electrons"],
            ),
        )
        for point in fixture["points"]
    ]
    result = build_projector_diagnostics(site_inputs, projector_generation_method=2)

    assert [item.u_times_abs_chi0 for item in result.sites] == pytest.approx(
        [point["u_times_abs_chi0"] for point in fixture["points"]]
    )
    assert [item.ligand_charge_capture for item in result.sites] == [
        LigandChargeCaptureStatus.NOT_INDICATED,
        LigandChargeCaptureStatus.NOT_INDICATED,
        LigandChargeCaptureStatus.NOT_INDICATED,
        LigandChargeCaptureStatus.NOT_INDICATED,
        LigandChargeCaptureStatus.NOT_INDICATED,
        LigandChargeCaptureStatus.NOT_INDICATED,
        LigandChargeCaptureStatus.CAPTURE_INDICATED,
        LigandChargeCaptureStatus.CAPTURE_INDICATED,
        LigandChargeCaptureStatus.CAPTURE_INDICATED,
    ]


def test_method2_warning_is_in_the_rendered_report_and_diagnostics_roundtrip() -> None:
    diagnostics = build_projector_diagnostics([], projector_generation_method=2)
    mapping = diagnostics.to_mapping()
    assert ProjectorDiagnostics.from_mapping(mapping) == diagnostics
    report = render_lr_u_report(
        {
            "schema_version": "siestaflow.lr_u_analysis.v3",
            "occupation_source": "siesta_occupations_total",
            "campaign": {},
            "primary": {},
            "provenance": {},
            "response_observation_dataset": {"status": "UNAVAILABLE"},
            "numerical_status": "NO_NUMERICAL_U",
            "alpha_grid_eV": [],
            "site_labels": [],
            "projector_diagnostics": mapping,
        }
    )
    assert "SIESTA_METHOD_2_ATOMIC_NONORTHOGONALIZED_PROJECTOR" in report
    assert "not comparable to U values from orthogonalized projector schemes" in report
    assert "Projector diagnostics (record-only)" in report


@pytest.mark.parametrize("value", [True, -0.1, float("nan"), float("inf"), "3"])
def test_nonfinite_or_invalid_declared_references_fail_closed(value: object) -> None:
    with pytest.raises(ProjectorDiagnosticError):
        SiteElectronReference(formal_d_electrons=value).validate()  # type: ignore[arg-type]


def test_method_other_than_two_is_rejected_by_method2_diagnostic_builder() -> None:
    with pytest.raises(ProjectorDiagnosticError, match="Method 2"):
        build_projector_diagnostics([], projector_generation_method=1)
