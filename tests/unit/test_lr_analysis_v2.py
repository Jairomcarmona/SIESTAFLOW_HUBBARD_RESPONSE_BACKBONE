import json

import numpy as np
import pytest

from hubbardflow.domain.lr_analysis_v2 import (
    LRAnalysisPolicy,
    _slope_rounding_bound,
    analyze_verified_lr,
)
from hubbardflow.domain.matrix_lr import ResponseObservation
from hubbardflow.reporting.lr_u_report import _matrix_table, render_lr_u_report


def _observations(alphas=(-0.15, -0.1, -0.05, 0.05, 0.1, 0.15)):
    chi0 = np.array([[-0.8, -0.1], [-0.06, -0.7]])
    chi = np.array([[-0.25, -0.04], [-0.03, -0.22]])
    quadratic0 = np.array([[0.8, -0.2], [0.1, 0.3]])
    quadratic = np.array([[0.4, 0.2], [-0.3, 0.1]])
    cubic0 = np.array([[2.0, -1.0], [0.5, 1.5]])
    cubic = np.array([[1.2, 0.8], [-0.7, 1.1]])
    reference = np.array([5.37, 4.82])
    result = []
    for j in range(2):
        for alpha in alphas:
            bare = reference + chi0[:, j] * alpha + quadratic0[:, j] * alpha**2 + cubic0[:, j] * alpha**3
            screened = reference + chi[:, j] * alpha + quadratic[:, j] * alpha**2 + cubic[:, j] * alpha**3
            result.append(ResponseObservation(
                perturbation_site=j,
                alpha=float(alpha),
                site_labels=[0, 1],
                occupations_ref=reference.tolist(),
                occupations_bare=bare.tolist(),
                occupations_screened=screened.tolist(),
                parent_dm_sha256="a" * 64,
                bare_fdf_sha256="b" * 64,
                bare_out_sha256="c" * 64,
                screened_fdf_sha256="d" * 64,
                screened_out_sha256="e" * 64,
                projector_fingerprints={0: "f" * 64, 1: "1" * 64},
            ))
    return result, chi0, chi


def test_auto_cubic_recovers_derivative_and_reports_sensitivity():
    observations, chi0, chi = _observations()
    result = analyze_verified_lr(
        observations,
        LRAnalysisPolicy(estimator="auto"),
        campaign={"campaign_id": "synthetic", "material": "fixture", "functional": "PBE"},
    )
    expected = np.linalg.inv(chi0) - np.linalg.inv(chi)
    assert result["selected_estimator"] == {"method": "polynomial", "degree": 3}
    assert result["primary"]["U_matrix_eV"] == pytest.approx(expected)
    assert result["numerical_status"] == "NUMERICAL_CANDIDATE_UNASSESSED"
    assert result["sensitivity_summary"]["assessment"] == "UNASSESSED_TOLERANCE_MISSING"
    assert result["physical_acceptance"] == "NOT_ESTABLISHED"
    assert result["model_sensitivity_eV"] is not None
    assert result["window_sensitivity_eV"] is not None
    assert "electronic_state_continuity_not_provided" in result["reasons"]


def test_auto_falls_back_to_linear_when_grid_cannot_support_cubic():
    observations, _, _ = _observations(alphas=(-0.1, 0.1))
    result = analyze_verified_lr(observations, LRAnalysisPolicy(estimator="auto"))
    assert result["selected_estimator"] == {"method": "linear", "degree": 1}
    assert "linear_fallback:insufficient_alpha_points" in result["reasons"]
    assert result["model_sensitivity_eV"] == {"0": None, "1": None}
    assert result["sensitivity_summary"]["max_abs_u_difference_eV"] is None
    assert result["printing_rounding_bound_eV"] is None
    assert result["primary"]["rounding_bound"]["status"] == "UNAVAILABLE"
    assert result["primary"]["rounding_bound"]["rounding_source"].startswith("printed Hubbard projector-matrix")


def test_print_rounding_bounds_include_cubic_c1_and_use_raw_matrix_inversion():
    observations, _, _ = _observations()
    widths = {
        (item.perturbation_site, float(item.alpha), mode): [5e-6, 5e-6]
        for item in observations for mode in ("bare", "screened")
    }
    result = analyze_verified_lr(
        observations,
        LRAnalysisPolicy(estimator="polynomial", polynomial_degree=3, matrix_for_inversion="raw"),
        trace_half_widths_electron=widths,
    )
    primary_bound = result["primary"]["rounding_bound"]
    assert primary_bound["status"] == "BOUNDED"
    assert primary_bound["matrix_for_inversion"] == "raw"
    assert primary_bound["rounding_source"] == "printed Hubbard projector-matrix diagonal tokens summed as trace_total"
    assert primary_bound["chi0_slope_half_width_eV_inv"] is not None
    assert primary_bound["chi_slope_half_width_eV_inv"] is not None
    assert primary_bound["maximum_U_scalar_half_width_eV"] == pytest.approx(
        result["printing_rounding_bound_eV"]
    )
    alpha = np.asarray(result["analysis_alpha_grid_eV"], dtype=float)
    scale = float(np.max(np.abs(alpha)))
    design = np.polynomial.polynomial.polyvander(alpha / scale, 3)
    # Build the OLS c1 linear functional from unit-response least-squares
    # fits, independently of the production QR implementation.
    expected_weights = np.asarray([
        np.linalg.lstsq(design, np.eye(len(alpha))[:, index], rcond=None)[0][1] / scale
        for index in range(len(alpha))
    ])
    expected_c1_bound = np.abs(expected_weights).sum() * 5e-6
    assert primary_bound["chi0_slope_half_width_eV_inv"][0][0] == pytest.approx(expected_c1_bound)


def test_qr_slope_rounding_weights_match_ols_linear_functional():
    alpha = np.asarray((-0.15, -0.1, -0.05, 0.05, 0.1, 0.15))
    widths = np.asarray((2e-6, 3e-6, 4e-6, 5e-6, 6e-6, 7e-6))
    degree = 3
    scale = float(np.max(np.abs(alpha)))
    design = np.polynomial.polynomial.polyvander(alpha / scale, degree)
    expected_weights = np.asarray([
        np.linalg.lstsq(design, np.eye(len(alpha))[:, index], rcond=None)[0][1] / scale
        for index in range(len(alpha))
    ])

    half_width, weights = _slope_rounding_bound(alpha, widths, degree=degree)

    assert weights == pytest.approx(expected_weights)
    assert half_width == pytest.approx(np.abs(expected_weights) @ widths)


def test_occupations_primary_source_requires_v3_and_propagates_its_token_widths():
    observations, _, _ = _observations()
    widths = {
        (item.perturbation_site, float(item.alpha), mode): [5e-7, 5e-7]
        for item in observations for mode in ("bare", "screened")
    }
    result = analyze_verified_lr(
        observations,
        LRAnalysisPolicy(estimator="polynomial", polynomial_degree=3, matrix_for_inversion="raw"),
        trace_half_widths_electron=widths,
        occupation_source="siesta_occupations_total",
    )
    assert result["schema_version"] == "siestaflow.lr_u_analysis.v3"
    assert result["occupation_source"] == "siesta_occupations_total"
    bound = result["primary"]["rounding_bound"]
    assert bound["rounding_source"] == "siesta_occupations_total"
    assert bound["chi0_slope_half_width_eV_inv"][0][0] < 1e-3
    report = render_lr_u_report(result)
    assert "Fuente de ocupación ajustada: `siesta_occupations_total`" in report


def test_two_point_window_is_reported_but_excluded_from_window_sensitivity():
    alphas = (-0.02, -0.01, -0.005, 0.005, 0.01, 0.02)
    observations, _, _ = _observations(alphas=alphas)
    widths = {
        (item.perturbation_site, float(item.alpha), mode): [5e-6, 5e-6]
        for item in observations for mode in ("bare", "screened")
    }
    result = analyze_verified_lr(
        observations,
        LRAnalysisPolicy(estimator="linear", minimum_residual_dof=1),
        active_window_ev=0.02,
        trace_half_widths_electron=widths,
    )
    central = next(item for item in result["window_results"] if item["alpha_window_ev"] == 0.005)
    assert central["window_diagnostic_type"] == "CENTRAL_DIFFERENCE"
    assert central["window_classification"] == "resolution_limited_two_point_central_difference"
    assert central["fit_window_stability_eligible"] is False
    assert central["rounding_bound"]["status"] == "BOUNDED"
    eligible = [item for item in result["window_results"] if item["fit_window_stability_eligible"]]
    expected_range = max(item["U_by_site_eV"]["0"] for item in eligible) - min(
        item["U_by_site_eV"]["0"] for item in eligible
    )
    assert result["window_sensitivity_eV"]["0"] == pytest.approx(expected_range)
    assert result["sensitivity_summary"]["excluded_resolution_limited_window_count"] == 1
    report = render_lr_u_report(result)
    assert "resolution_limited_two_point_central_difference" in report
    assert "Cota determinista por redondeo de tokens diagonales de la traza de matriz impresa" in report
    assert "UNASSESSED_TOLERANCE_MISSING" in report


def test_configured_tolerance_distinguishes_exceedance_from_missing_acceptance_limit():
    observations, _, _ = _observations()
    unassessed = analyze_verified_lr(observations, LRAnalysisPolicy(estimator="auto"))
    assert unassessed["numerical_status"] == "NUMERICAL_CANDIDATE_UNASSESSED"
    exceeded = analyze_verified_lr(
        observations,
        LRAnalysisPolicy(estimator="auto", sensitivity_tolerance_eV=0.0),
        magnetic_state_labels={alpha: "AFM" for alpha in (-0.15, -0.1, -0.05, 0.05, 0.1, 0.15)},
        scf_validated=True,
    )
    assert exceeded["numerical_status"] == "NUMERICAL_CANDIDATE_SENSITIVE"
    assert exceeded["sensitivity_summary"]["assessment"] == "MEASURED_EXCEEDS_TOLERANCE"
    assert exceeded["sensitivity_summary"]["state"] == "SENSITIVE"
    assert exceeded["sensitivity_summary"]["declared_by"] == "config"
    report = render_lr_u_report(exceeded)
    assert "declarado por: `config`" in report
    assert "vía: `config`" in report


def test_sensitivity_policy_has_four_explicit_assessment_states():
    observations, _, _ = _observations()
    alphas = (-0.15, -0.1, -0.05, 0.05, 0.1, 0.15)
    unassessed = analyze_verified_lr(observations, LRAnalysisPolicy(estimator="auto"))
    assert unassessed["sensitivity_summary"]["state"] == "UNASSESSED"

    incomplete = analyze_verified_lr(
        observations,
        LRAnalysisPolicy(estimator="auto", sensitivity_tolerance_eV=100.0),
    )
    assert incomplete["sensitivity_summary"]["state"] == "WITHIN_TOLERANCE_EVIDENCE_INCOMPLETE"

    complete = analyze_verified_lr(
        observations,
        LRAnalysisPolicy(estimator="auto", sensitivity_tolerance_eV=100.0),
        magnetic_state_labels={alpha: "AFM" for alpha in alphas},
        scf_validated=True,
    )
    assert complete["sensitivity_summary"]["state"] == "NUMERICAL_CANDIDATE"


def test_cli_declaration_source_is_report_provenance_not_estimator_policy():
    observations, _, _ = _observations()
    policy = LRAnalysisPolicy(
        estimator="auto",
        sensitivity_tolerance_eV=100.0,
        sensitivity_tolerance_provided_via="cli",
    )
    result = analyze_verified_lr(
        observations,
        policy,
        magnetic_state_labels={alpha: "AFM" for alpha in (-0.15, -0.1, -0.05, 0.05, 0.1, 0.15)},
        scf_validated=True,
    )
    assert result["sensitivity_summary"]["declared_by"] == "config"
    assert result["sensitivity_summary"]["provided_via"] == "cli"
    assert "sensitivity_tolerance_provided_via" not in result["estimator_policy"]
    assert "sensitivity_tolerance_provided_via" not in policy.response_context()


def test_active_window_controls_primary_fit_and_full_grid_is_diagnostic():
    observations, _, _ = _observations()
    policy = LRAnalysisPolicy(
        estimator="linear", polynomial_degree=3, minimum_residual_dof=1,
        matrix_for_inversion="raw",
    )
    result = analyze_verified_lr(observations, policy, active_window_ev=0.1)
    assert result["analysis_active_window_eV"] == 0.1
    assert result["analysis_alpha_grid_eV"] == [-0.1, -0.05, 0.05, 0.1]
    assert result["alpha_grid_eV"] == [-0.15, -0.1, -0.05, 0.05, 0.1, 0.15]
    assert result["full_grid_diagnostic"]["method"] == "linear"

    with pytest.raises(ValueError, match="active alpha window has"):
        analyze_verified_lr(observations, policy, active_window_ev=0.05)


def test_changed_state_prevents_combined_site_u_and_json_has_no_nan():
    observations, _, _ = _observations()
    result = analyze_verified_lr(
        observations,
        LRAnalysisPolicy(estimator="auto"),
        magnetic_state_labels={
            -0.15: "AFM", -0.1: "AFM", -0.05: "AFM",
            0.05: "FM", 0.1: "FM", 0.15: "FM",
        },
    )
    assert result["numerical_status"] == "NO_SINGLE_STATE_U"
    assert result["primary"]["U_matrix_eV"] is None
    assert result["same_grid_linear"]["U_matrix_eV"] is None
    assert all(item["U_matrix_eV"] is None for item in result["window_results"])
    serialized = json.dumps(result, allow_nan=False)
    parsed = json.loads(serialized, parse_constant=lambda value: pytest.fail(value))
    assert parsed["numerical_status"] == "NO_SINGLE_STATE_U"


def test_markdown_report_is_per_site_and_keeps_scalar_u_semantics():
    observations, _, _ = _observations()
    result = analyze_verified_lr(
        observations,
        LRAnalysisPolicy(estimator="auto"),
        campaign={"sites": [{"site_id": "NiLR0"}, {"site_id": "NiLR1"}]},
    )
    report = render_lr_u_report(result)
    assert render_lr_u_report(result) == report
    assert "U_scalar_charge" in report
    assert "Ueff_Dudarev" in report
    assert "| U_scalar_charge | NiLR0 |" in report
    assert "Acción DAG registrada" in report
    assert "NO_DECLARADA" not in report
    assert "NOT_ESTABLISHED" in report


def test_markdown_report_renders_verified_dataset_math_and_source_lineage():
    observations, _, _ = _observations()
    result = analyze_verified_lr(
        observations,
        LRAnalysisPolicy(estimator="auto"),
        campaign={
            "campaign_id": "synthetic-report",
            "material": "NiO fixture",
            "functional": "PBE",
            "sites": [{"site_id": "NiA"}, {"site_id": "NiB"}],
        },
    )
    result["response_observation_dataset"] = {
        "schema_version": "siestaflow.lr_u_verified_dataset.v1",
        "status": "AVAILABLE",
        "units": {"alpha": "eV", "occupations": "electron"},
        "matrix_index_to_site_id": {"0": "NiA", "1": "NiB"},
        "site_id_to_matrix_index": {"NiA": 0, "NiB": 1},
        "reference_source": {"node_id": "reference", "mode": "REFERENCE_SCREENED", "fdf_path": "inputs/ref.fdf", "out_path": "runs/ref.out", "fdf_sha256": "a" * 64, "out_sha256": "b" * 64, "evidence_digest": "c" * 64},
        "rows": [{
            "perturbed_site_index": 0,
            "perturbed_site_id": "NiA",
            "alpha_eV": -0.1,
            "observed_sites": [{
                "observed_site_index": 0,
                "observed_site_id": "NiA",
                "occupations_electron": {"reference": 5.0, "bare": 5.1, "screened": 5.2},
                "matrix_trace_half_widths_electron": {
                    "reference": 0.00005, "bare": 0.00005, "screened": 0.00005,
                },
            }],
            "sources": {
                "bare": {"node_id": "bare-1", "mode": "BARE", "fdf_path": "runs/bare.fdf", "out_path": "runs/bare.out", "fdf_sha256": "d" * 64, "out_sha256": "e" * 64, "evidence_digest": "f" * 64},
                "screened": {"node_id": "screened-1", "mode": "SCREENED", "fdf_path": "runs/screened.fdf", "out_path": "runs/screened.out", "fdf_sha256": "1" * 64, "out_sha256": "2" * 64, "evidence_digest": "3" * 64},
            },
        }],
    }
    result["provenance"]["campaign_inputs"] = {
        "siesta_runtime": {
            "version": "5.4.2",
            "version_text_path": "software/siesta_version.txt",
            "version_text_sha256": "4" * 64,
        },
        "analysis_implementation": {
            "package": "hubbardflow",
            "package_version": "0.1.2",
            "schema": "siestaflow.lr_u_analysis.v2",
        },
    }

    report = render_lr_u_report(result)
    assert "n referencia (e)" in report
    assert "5.1" in report and "5.2" in report
    assert "½ ancho de traza por impresión" in report
    assert "5e-05 / 5e-05 / 5e-05" in report
    assert "χ⁰ raw (BARE)" in report
    assert "(χ⁰)⁻¹" in report and "U_matrix" in report
    assert "Coeficientes con unidades" in report
    assert "e·eV⁻¹" in report
    assert "runs/bare.fdf" in report
    assert "Versión SIESTA:** 5.4.2" in report
    assert "software/siesta_version.txt" in report
    assert "0.1.2" in report
    assert "Digest de evidencia del recibo" in report
    assert "NiA" in report and "NiB" in report
    linear_fit = next(
        item for item in result["primary"]["fit_diagnostics"] if item["mode"] == "BARE"
    )["same_grid_linear"]
    assert linear_fit["degree"] == 1
    assert linear_fit["residual_dof"] == linear_fit["n_points"] - 2
    assert linear_fit["residual_rms"] is not None



def test_markdown_report_accepts_legacy_v2_without_occupation_dataset():
    observations, _, _ = _observations()
    result = analyze_verified_lr(observations, LRAnalysisPolicy(estimator="auto"))
    result.pop("response_observation_dataset", None)
    report = render_lr_u_report(result)
    assert "análisis v2 anterior no guardaba las ocupaciones verificadas" in report
    assert "χ⁰ raw (BARE)" in report


def test_markdown_report_separates_adaptive_campaign_and_candidate_status():
    observations, _, _ = _observations()
    result = analyze_verified_lr(observations, LRAnalysisPolicy(estimator="auto"))
    result.update({
        "campaign_status": "STOP_LIMIT_SENSITIVE",
        "candidate_status": "NUMERICAL_CANDIDATE_SENSITIVE",
        "alpha_rounds": [{
            "round_index": 0, "direction": "initial", "alpha_grid_ev": [-0.15, -0.1, -0.05, 0.05, 0.1, 0.15],
            "active_window_eV": 0.15, "scf_level_id": "base", "candidate_status": "NUMERICAL_CANDIDATE_SENSITIVE",
            "status": "DECIDED",
        }],
        "refinement_policy": {
            "truncation_threshold_eV": 0.001,
            "sensitivity_delta_tolerance_eV": 0.05,
        },
        "refinement_decision": {
            "decision": "STOP_LIMIT_SENSITIVE", "reason": "predicate_not_configured",
            "truncation_metric_eV": 0.0048,
            "truncation_metric_basis": "range_of_eligible_linear_fit_windows",
        },
        "adaptive_budget": {"reserved_nodes": 25, "total_siesta_node_budget": 40, "remaining_nodes": 15},
    })
    report = render_lr_u_report(result)
    assert "Decisión de campaña: **STOP_LIMIT_SENSITIVE**" in report
    assert "Estado del candidato: **NUMERICAL_CANDIDATE_SENSITIVE**" in report
    assert "Ventana activa" in report
    assert "25/40 nodos SIESTA" in report
    assert "Umbral de truncación declarado: 0.001 eV" in report
    assert "se propone `shrink`, sujeto a la precedencia de otras decisiones y a los límites de rondas y presupuesto" in report
    assert "Tolerancia de aumento de sensibilidad entre rondas: 0.05 eV" in report
    assert "Solo compara el aumento frente a la ronda previa" in report
    assert "no es un umbral absoluto de aceptación ni una cota de error" in report


def test_large_matrix_report_is_split_into_column_blocks():
    matrix = [[float(row * 10 + column) for column in range(10)] for row in range(10)]
    names = {str(index): f"Site{index}" for index in range(10)}
    report = "\n".join(_matrix_table("χ", matrix, names, unit="eV⁻¹"))
    assert "sitios perturbados 1–8" in report
    assert "sitios perturbados 9–10" in report
    assert report.count("Sitio observado \\ Sitio perturbado") == 2


def test_v3_report_renders_occupation_token_half_widths_and_v2_uses_trace_widths():
    observations, _, _ = _observations()
    result = analyze_verified_lr(
        observations,
        LRAnalysisPolicy(estimator="auto"),
        occupation_source="siesta_occupations_total",
    )
    result["response_observation_dataset"] = {
        "schema_version": "siestaflow.lr_u_verified_dataset.v2",
        "status": "AVAILABLE",
        "units": {"alpha": "eV", "occupations": "electron"},
        "rows": [{
            "perturbed_site_id": "NiA", "alpha_eV": -0.1,
            "observed_sites": [{
                "observed_site_id": "NiA",
                "occupations_electron": {"reference": 5.0, "bare": 5.1, "screened": 5.2},
                "occupation_half_widths_electron": {
                    "reference": 5e-7, "bare": 6e-7, "screened": 7e-7,
                },
                "matrix_trace_half_widths_electron": {
                    "reference": 5e-5, "bare": 5e-5, "screened": 5e-5,
                },
            }],
        }],
    }
    report = render_lr_u_report(result)
    assert "½ ancho del observable impreso (ref/BARE/SCREENED, e)" in report
    assert "5e-07 / 6e-07 / 7e-07" in report
    assert "5e-05 / 5e-05 / 5e-05" not in report


def test_rounding_footer_attributes_the_bound_to_each_schema_source():
    observations, _, _ = _observations()
    v3 = analyze_verified_lr(
        observations, LRAnalysisPolicy(estimator="auto"),
        occupation_source="siesta_occupations_total",
    )
    v2 = analyze_verified_lr(observations, LRAnalysisPolicy(estimator="auto"))
    report_v3 = render_lr_u_report(v3)
    report_v2 = render_lr_u_report(v2)
    assert "tokens del total `Occupations:` impreso" in report_v3
    assert "tokens diagonales impresos de la traza de matriz" not in report_v3
    assert "tokens diagonales impresos de la traza de matriz" in report_v2
    assert "tokens del total `Occupations:` impreso" not in report_v2
