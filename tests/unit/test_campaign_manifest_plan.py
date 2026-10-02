"""Manifest execution inputs must agree with the frozen configuration on resume."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from hubbardflow.execution.campaign_v2 import CampaignV2Error, load_campaign_v2
from hubbardflow.execution.wsl_campaign_init import initialize_campaign
from tests.unit.test_campaign_plan import inputs


def adaptive_test_policy() -> dict[str, Any]:
    """Explicit legacy test profile, independent of scientific production defaults."""
    fit = {
        "active_window_eV": 0.15,
        "estimator": "polynomial",
        "polynomial_degree": 3,
        "minimum_residual_dof": 1,
        "matrix_for_inversion": "raw",
    }
    return {
        "schema": "siestaflow.adaptive_alpha_policy.v1",
        "h_eV": 0.05,
        "alpha_seed_span_eV": 0.15,
        "alpha_ceiling_eV": None,
        "max_refinement_rounds": 2,
        "max_alpha_points": 11,
        "total_siesta_node_budget": 40,
        "round_analysis": {
            "initial": fit,
            "shrink": [{**fit, "active_window_eV": 0.10}, {**fit, "active_window_eV": 0.05}],
            "expand": [fit, fit],
        },
        "probe_trigger_ratio": None,
        "tol_abs_eV": None,
        "tol_rel": None,
        "truncation_threshold_eV": None,
        "sensitivity_delta_tolerance_eV": None,
        "scf_materiality_ratio": None,
        "rho_min": None,
        "scf_probe_level": None,
    }


@pytest.mark.parametrize(
    "field",
    [
        "adaptive_alpha_policy",
        "magnetic_moment_tolerance_muB",
        "observables",
        "material",
        "alpha_selection_policy",
        "fixed_grid",
        "automatic_alpha_refinement",
        "campaign_id",
        "contract_file",
        "lr_config_file",
        "execution_profile_file",
    ],
)
def test_resume_rejects_each_mutable_execution_field(tmp_path: Path, field: str) -> None:
    from hubbardflow.domain.adaptive_alpha_control import AdaptiveAlphaPolicy

    fdf, raw, profile = inputs(tmp_path / "inputs")
    adaptive = AdaptiveAlphaPolicy.from_mapping(adaptive_test_policy())
    raw.update(
        {
            "adaptive_alpha_policy": adaptive.to_mapping(),
            # The authoritative JSON grid uses exactly representable decimal
            # amplitudes; multiplying binary 0.05 by 3 is not such an input.
            "alpha_grid_ev": [-0.15, -0.10, -0.05, 0.05, 0.10, 0.15],
            "magnetic_moment_tolerance_muB": 0.05,
            "observables": ["shell_trace"],
            "material": "synthetic",
        }
    )
    config_path = fdf.parent / "lr.json"
    config_path.write_text(json.dumps(raw), encoding="utf-8")
    result = initialize_campaign(
        fdf_path=str(fdf),
        lr_config_path=str(config_path),
        profile_path=str(profile),
        name="execution-inputs",
        campaign_root=str(tmp_path / "campaigns"),
    )
    path = Path(result["manifest_path"])
    manifest = load_campaign_v2(path)
    assert manifest["_adaptive_alpha_policy"] == adaptive
    assert manifest["magnetic_moment_tolerance_muB"] == 0.05
    # Only one manifest field changes; frozen config/plan/lock/input bytes remain
    # untouched, so startup/resume must reject the new execution request.
    row = json.loads(path.read_text(encoding="utf-8"))
    if field == "adaptive_alpha_policy":
        row[field]["total_siesta_node_budget"] = 41
    elif field == "magnetic_moment_tolerance_muB":
        row[field] = 0.10
    elif field == "observables":
        row[field] = ["other_observable"]
    elif field == "material":
        row[field] = "other_material"
    elif field == "alpha_selection_policy":
        row[field] = {"unknown_policy": "request"}
    elif field in {"fixed_grid", "automatic_alpha_refinement"}:
        row[field] = not row[field]
    elif field == "campaign_id":
        row[field] = "different-campaign"
    else:
        original = path.parent / row[field]
        alternate = path.parent / ("alternate_" + original.name)
        shutil.copy2(original, alternate)
        row[field] = alternate.name
    path.write_text(json.dumps(row), encoding="utf-8")
    with pytest.raises(CampaignV2Error):
        load_campaign_v2(path)


@pytest.mark.parametrize(
    "field",
    ["magnetic_moment_tolerance_muB", "observables", "material", "alpha_selection_policy", "fixed_grid"],
)
def test_resume_rejects_missing_execution_fields(tmp_path: Path, field: str) -> None:
    fdf, raw, profile = inputs(tmp_path / "inputs")
    config_path = fdf.parent / "lr.json"
    config_path.write_text(json.dumps(raw), encoding="utf-8")
    result = initialize_campaign(
        fdf_path=str(fdf),
        lr_config_path=str(config_path),
        profile_path=str(profile),
        name="missing-field",
        campaign_root=str(tmp_path / "campaigns"),
    )
    path = Path(result["manifest_path"])
    row = json.loads(path.read_text(encoding="utf-8"))
    del row[field]
    path.write_text(json.dumps(row), encoding="utf-8")
    with pytest.raises(CampaignV2Error, match=field):
        load_campaign_v2(path)


@pytest.mark.parametrize(
    "field",
    [
        "functional",
        "xc_profile",
        "sites",
        "alpha_grid_ev",
        "analysis_policy",
        "adaptive_alpha_policy",
        "automatic_alpha_refinement",
        "coverage",
        "reference_fdf",
        "contract_file",
        "lr_config_file",
        "execution_profile_file",
        "resolved_perturbation_plan_file",
        "campaign_lock_file",
        "resolved_perturbation_plan_digest",
        "campaign_id",
    ],
)
def test_resume_rejects_each_missing_frozen_manifest_field(tmp_path: Path, field: str) -> None:
    from hubbardflow.domain.adaptive_alpha_control import AdaptiveAlphaPolicy

    fdf, raw, profile = inputs(tmp_path / "inputs")
    adaptive = AdaptiveAlphaPolicy.from_mapping(adaptive_test_policy())
    raw.update(
        {
            "adaptive_alpha_policy": adaptive.to_mapping(),
            "alpha_grid_ev": [-0.15, -0.10, -0.05, 0.05, 0.10, 0.15],
        }
    )
    config_path = fdf.parent / "lr.json"
    config_path.write_text(json.dumps(raw), encoding="utf-8")
    result = initialize_campaign(
        fdf_path=str(fdf),
        lr_config_path=str(config_path),
        profile_path=str(profile),
        name="missing-frozen-field",
        campaign_root=str(tmp_path / "campaigns"),
    )
    path = Path(result["manifest_path"])
    manifest = load_campaign_v2(path)
    assert manifest["_adaptive_alpha_policy"] == adaptive
    assert manifest["automatic_alpha_refinement"] is True
    row = json.loads(path.read_text(encoding="utf-8"))
    frozen_files = {
        path.parent / row[pointer]: (path.parent / row[pointer]).read_bytes()
        for pointer in (
            "reference_fdf",
            "contract_file",
            "lr_config_file",
            "execution_profile_file",
            "resolved_perturbation_plan_file",
            "campaign_lock_file",
        )
    }
    del row[field]
    path.write_text(json.dumps(row), encoding="utf-8")
    with pytest.raises(CampaignV2Error):
        load_campaign_v2(path)
    assert all(frozen.read_bytes() == original for frozen, original in frozen_files.items())


@pytest.mark.parametrize(
    "field,value",
    [
        ("magnetic_moment_tolerance_muB", float("nan")),
        ("observables", [float("inf")]),
        ("fixed_grid", 1),
    ],
)
def test_resume_rejects_nonfinite_metadata_and_boolean_type_confusion(
    tmp_path: Path, field: str, value: object
) -> None:
    fdf, raw, profile = inputs(tmp_path / "inputs")
    config_path = fdf.parent / "lr.json"
    config_path.write_text(json.dumps(raw), encoding="utf-8")
    result = initialize_campaign(
        fdf_path=str(fdf),
        lr_config_path=str(config_path),
        profile_path=str(profile),
        name="invalid-value",
        campaign_root=str(tmp_path / "campaigns"),
    )
    path = Path(result["manifest_path"])
    row = json.loads(path.read_text(encoding="utf-8"))
    row[field] = value
    path.write_text(json.dumps(row), encoding="utf-8")
    with pytest.raises(CampaignV2Error, match=field):
        load_campaign_v2(path)
