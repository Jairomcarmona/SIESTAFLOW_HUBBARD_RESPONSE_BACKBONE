"""Software checks for the versioned NiO linear/cubic analysis path."""
from __future__ import annotations

import copy
import ast
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN = ROOT / "campaigns/nio_afmii_four_atom_lru_v2_20260926"
ANALYZER_PATH = CAMPAIGN / "scripts/analyze_nio_lru_v3.py"
SPEC = importlib.util.spec_from_file_location("nio_lru_v3_analyzer", ANALYZER_PATH)
assert SPEC is not None and SPEC.loader is not None
ANALYZER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ANALYZER)
from siestaflow_hubbard.domain.matrix_lr import fit_polynomial_response  # noqa: E402


def test_cubic_fit_default_accepts_five_points_with_one_residual_degree_of_freedom():
    alpha = [-0.1, -0.05, 0.0, 0.05, 0.1]
    occupations = [1.0 + 2.0 * x + 3.0 * x**2 + 4.0 * x**3 for x in alpha]

    fit = fit_polynomial_response(alpha, occupations, degree=3)

    assert fit.residual_dof == 1
    assert fit.slope == pytest.approx(2.0, abs=1e-12)


def _inputs():
    lock = ANALYZER.validate_lock()
    policy = ANALYZER.load_policy()
    source = json.loads(ANALYZER.SOURCE_PATH.read_text(encoding="utf-8"))
    events = ANALYZER.validate_events(source, policy)
    return lock, policy, source, events


def test_policy_pins_degree_three_and_same_grid_linear_comparison():
    _, policy, _, _ = _inputs()

    assert policy["primary_candidate_estimator"]["method"] == "polynomial"
    assert policy["primary_candidate_estimator"]["degree"] == 3
    assert policy["primary_candidate_estimator"]["minimum_residual_dof"] == 3
    assert policy["same_grid_comparison_estimator"] == {
        "method": "linear", "degree": 1, "alpha_window_ev": None,
    }
    assert policy["reportability_policy"]["polynomial_fit_can_change_reportability"] is False


def test_integrated_analysis_preserves_v2_unresolved_gates_and_fit_evidence():
    lock, policy, source, events = _inputs()
    result = ANALYZER.analyze(source, events, policy, lock)

    assert result["response_run_count"] == 26
    assert result["status"] == "UNRESOLVED_NO_REPORTABLE_U"
    assert result["reportability_status_inherited_from_frozen_v2"] == source["status"]
    assert result["polynomial_changes_reportability"] is False
    assert result["reportable_u"] is False
    assert result["frozen_v2_acceptance"]["u_interval_by_site_eV"] == source["u_interval_by_site_eV"]

    cubic = result["estimators"]["primary_candidate"]
    linear = result["estimators"]["same_grid_linear_comparison"]
    assert cubic["method"] == "polynomial" and cubic["degree"] == 3
    assert linear["method"] == "linear" and linear["degree"] == 1
    assert cubic["u_diagonal_by_site_eV"] == pytest.approx([7.5380404953, 7.5400793801], abs=1e-9)
    prior_independent_fit = json.loads(
        (CAMPAIGN / "results/posthoc-global-alpha-regression-v1.json").read_text(encoding="utf-8")
    )
    prior_cubic = next(model for model in prior_independent_fit["fit_models"] if model["degree"] == 3)
    assert cubic["u_diagonal_by_site_eV"] == pytest.approx(prior_cubic["u_diagonal_eV"], abs=1e-10)
    assert linear["u_diagonal_by_site_eV"] == pytest.approx(
        result["estimators"]["frozen_v2_widest_window_linear_reference"]["u_diagonal_by_site_eV"],
        abs=1e-12,
    )

    for mode in ("BARE", "SCREENED"):
        for curve in cubic["fit_diagnostics_by_mode"][mode].values():
            assert curve["degree"] == 3
            assert curve["n_points"] == 7
            assert curve["residual_dof"] == 3
            assert len(curve["coefficients_alpha_units"]) == 4
            assert len(curve["residuals_e_in_alpha_order"]) == 7
        for curve in linear["fit_diagnostics_by_mode"][mode].values():
            assert curve["degree"] == 1
            assert curve["n_points"] == 7
            assert curve["residual_dof"] == 5
            assert len(curve["coefficients_alpha_units"]) == 2
            assert len(curve["residuals_e_in_alpha_order"]) == 7


def test_event_grid_rejects_missing_or_mutated_population_results():
    _, policy, source, _ = _inputs()

    missing = copy.deepcopy(source)
    missing["selected_population_events"].pop("NiLR0_BARE_m0p025")
    with pytest.raises(ValueError, match="SELECTED_EVENT_COUNT_NOT_26"):
        ANALYZER.validate_events(missing, policy)

    mutated = copy.deepcopy(source)
    mutated["selected_population_events"]["NiLR0_BARE_m0p025"]["alpha_ev"] = -0.05
    with pytest.raises(ValueError, match="EVENT_ID_METADATA_MISMATCH"):
        ANALYZER.validate_events(mutated, policy)


def test_lock_tampering_and_locked_source_mismatch_are_rejected(monkeypatch):
    original = json.loads(ANALYZER.LOCK_PATH.read_text(encoding="utf-8"))
    analyzer_relative = "campaigns/nio_afmii_four_atom_lru_v2_20260926/scripts/analyze_nio_lru_v3.py"
    source_relative = "campaigns/nio_afmii_four_atom_lru_v2_20260926/results/analysis-v2.json"

    tampered_script_lock = copy.deepcopy(original)
    tampered_script_lock["sha256"][analyzer_relative] = "0" * 64
    tampered_source_lock = copy.deepcopy(original)
    tampered_source_lock["sha256"][source_relative] = "0" * 64
    for tampered in (tampered_script_lock, tampered_source_lock):
        with monkeypatch.context() as scoped:
            scoped.setattr(ANALYZER.json, "loads", lambda _text, value=tampered: copy.deepcopy(value))
            with pytest.raises(ValueError, match="LOCKED_FILE_HASH_MISMATCH"):
                ANALYZER.validate_lock()


def test_source_status_mismatch_is_rejected():
    _, policy, source, _ = _inputs()
    mutated = copy.deepcopy(source)
    mutated["status"] = "REPORTABLE_NUMERICAL_U_INTERVAL"

    with pytest.raises(ValueError, match="SOURCE_STATUS_CHANGED_FROM_FROZEN_UNRESOLVED"):
        ANALYZER.validate_events(mutated, policy)


def test_analysis_path_has_no_siesta_executor_or_backend_imports():
    tree = ast.parse(ANALYZER_PATH.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)

    assert "subprocess" not in imported
    assert not any(name.startswith("siestaflow_hubbard.siesta_backend") for name in imported)
    result = json.loads((CAMPAIGN / "results/analysis-v3.json").read_text(encoding="utf-8"))
    assert result["workflow_integration"]["automatic_dag_node"] is False
    assert "postprocessing_step_after_frozen_v2_analysis" in result["workflow_integration"]["kind"]


def test_persisted_v3_outputs_match_analysis_and_keep_unresolved_status():
    result = json.loads((CAMPAIGN / "results/analysis-v3.json").read_text(encoding="utf-8"))
    report = (CAMPAIGN / "results/report-v3.md").read_text(encoding="utf-8")

    assert result["status"] == "UNRESOLVED_NO_REPORTABLE_U"
    assert result["reportable_u"] is False
    assert result["response_run_count"] == 26
    assert result["provenance"]["estimator_policy_sha256"] == ANALYZER.digest(ANALYZER.POLICY_PATH)
    assert "UNRESOLVED_NO_REPORTABLE_U" in report
    assert "no puede promover automáticamente" in report
    assert "results/analysis-v2.json" in report
