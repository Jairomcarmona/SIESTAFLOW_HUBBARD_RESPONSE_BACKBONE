from __future__ import annotations

import json
from pathlib import Path

import pytest

from hubbardflow.execution.campaign_runner import render_campaign_report
from hubbardflow.execution.campaign_v2 import CampaignV2Error
from hubbardflow.execution.wsl_campaign_init import initialize_campaign
from tests.unit.test_campaign_plan import inputs, normalized


def test_projector_electron_references_are_optional_validated_and_frozen(tmp_path: Path) -> None:
    fdf, raw, profile = inputs(tmp_path / "inputs")
    without_references = normalized(fdf, raw)
    assert "projector_diagnostic_references" not in without_references

    references = {"Co": {"formal_d_electrons": 7, "free_atom_d_electrons": 9}}
    with_references = normalized(fdf, {**raw, "projector_diagnostic_references": references})
    assert with_references["projector_diagnostic_references"] == {
        "Co": {"formal_d_electrons": 7.0, "free_atom_d_electrons": 9.0},
    }

    config_path = fdf.parent / "lr.json"
    config_path.write_text(
        json.dumps({**raw, "projector_diagnostic_references": references}), encoding="utf-8"
    )
    result = initialize_campaign(
        fdf_path=str(fdf),
        lr_config_path=str(config_path),
        profile_path=str(profile),
        name="projector-diagnostics",
        campaign_root=str(tmp_path / "campaigns"),
    )
    campaign_root = Path(result["manifest_path"]).parent
    stored = json.loads((campaign_root / "lr_config.json").read_text(encoding="utf-8"))
    assert stored["projector_diagnostic_references"] == with_references["projector_diagnostic_references"]
    preanalysis_report = render_campaign_report(result["manifest_path"])
    report_lines = preanalysis_report.splitlines()
    json_start = report_lines.index("```json") + 1
    json_end = report_lines.index("```", json_start)
    warning_report = json.loads("\n".join(report_lines[json_start:json_end]))
    assert warning_report["projector_diagnostics"]["method2_warning"]["code"] == (
        "SIESTA_METHOD_2_ATOMIC_NONORTHOGONALIZED_PROJECTOR"
    )
    assert "not comparable to U values from orthogonalized projector schemes" in preanalysis_report


@pytest.mark.parametrize(
    "references",
    [
        {"Ni": {"formal_d_electrons": 8}},
        {"Co": {"formal_d_electrons": float("nan")}},
        {"Co": {"other": 3}},
    ],
)
def test_projector_electron_references_reject_unknown_sites_and_invalid_counts(
    tmp_path: Path,
    references: dict[str, object],
) -> None:
    fdf, raw, _ = inputs(tmp_path)
    with pytest.raises(
        CampaignV2Error, match="projector_diagnostic_references|invalid projector diagnostic reference"
    ):
        normalized(fdf, {**raw, "projector_diagnostic_references": references})
