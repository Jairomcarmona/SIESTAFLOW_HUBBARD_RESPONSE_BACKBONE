from __future__ import annotations

import csv
import json
from pathlib import Path

from hubbardflow.execution.campaign_report_artifacts import write_campaign_report_artifacts
from hubbardflow.execution.report_csv_exports import export_report_csv
from hubbardflow.reporting.hubbardflow_ascii_report import render_hubbardflow_out
from hubbardflow.siesta_backend.fdf_model import parse_effective_fdf

ROOT = Path(__file__).resolve().parents[2]
ANALYSIS_FIXTURE = ROOT / "tests" / "fixtures" / "replay_nio_p5" / "replay_analysis.v3.json"
STATE_GATE_FIXTURE = ROOT / "tests" / "fixtures" / "replay_nio_p5" / "replay_i5_state_gate.json"
REFERENCE_FDF = ROOT / "tests" / "fixtures" / "real_nio_p5_rerun" / "inputs" / "reference.fdf"


def _assert_report_shape(report: str) -> None:
    raw = report.encode("ascii")
    assert all(byte <= 127 for byte in raw)
    assert all(len(line) <= 80 for line in report.splitlines())
    for index, heading in enumerate(
        (
            "HEADER",
            "SYSTEM",
            "PROJECTOR",
            "PROTOCOL",
            "RUN INVENTORY",
            "REFERENCE STATE",
            "RESPONSE DATA",
            "FITS",
            "MATRICES",
            "INVERSION",
            "SYMMETRY",
            "DIAGNOSTICS",
            "FILE MAP",
        ),
        start=1,
    ):
        assert f"[{index:02d}] {heading}" in report
    assert report.index("RESULT SUMMARY") < report.index("[01] HEADER")


def test_report_is_ascii_fixed_width_and_has_all_numbered_sections() -> None:
    analysis = json.loads(ANALYSIS_FIXTURE.read_text(encoding="utf-8"))
    state_gate = json.loads(STATE_GATE_FIXTURE.read_text(encoding="utf-8"))
    source = {
        "analysis": analysis,
        "context": {},
        "state_gate": state_gate,
        "occupation_provenance": {"records": []},
        "traceability_warnings": [],
        "quality_checks": {},
        "file_map": {},
    }

    report = render_hubbardflow_out(source)

    _assert_report_shape(report)
    assert "CHI0 RAW (e/eV)" in report
    assert "CHI RAW (e/eV)" in report
    assert "NOT_ASSESSED" in report
    assert "Pointwise state gate" in report


def test_saved_json_is_the_only_report_and_csv_source(tmp_path: Path) -> None:
    analysis = json.loads(ANALYSIS_FIXTURE.read_text(encoding="utf-8"))
    state_gate = json.loads(STATE_GATE_FIXTURE.read_text(encoding="utf-8"))
    results = tmp_path / "results"
    analysis_path = results / "lr_u_analysis.v3.json"
    analysis_path.parent.mkdir(parents=True)
    analysis_path.write_text(json.dumps(analysis), encoding="utf-8")
    occupation_path = results / "data" / "occupation_provenance.v1.json"
    occupation_path.parent.mkdir(parents=True)
    occupation_path.write_text(json.dumps({"records": []}), encoding="utf-8")
    campaign = {
        "campaign_id": "report-test",
        "name": "report-test",
        "functional": "PBE",
        "reference_fdf": "missing-reference.fdf",
        "lr_config_file": "missing-config.json",
        "execution_profile_file": "missing-profile.json",
        "sites": [],
    }
    warnings = [{"code": "HASH_TRACEABILITY_WARNING"}]

    report = write_campaign_report_artifacts(
        campaign_root=tmp_path,
        manifest_path=tmp_path / "campaign.v2.json",
        campaign=campaign,
        analysis_path=analysis_path,
        analysis=analysis,
        state_gate=state_gate,
        occupation_provenance_path=occupation_path,
        traceability_warnings=warnings,
    )

    _assert_report_shape(report)
    data_dir = results / "data"
    saved_source = json.loads((data_dir / "hubbardflow_report_source.v1.json").read_text(encoding="utf-8"))
    assert saved_source["analysis"] == analysis
    assert saved_source["traceability_warnings"] == warnings
    assert render_hubbardflow_out(saved_source) == report
    assert (results / "HUBBARDFLOW.out").read_text(encoding="ascii") == report

    with (data_dir / "u_by_site.csv").open(encoding="ascii", newline="") as stream:
        u_rows = list(csv.reader(stream))
    with (data_dir / "chi0_matrix.csv").open(encoding="ascii", newline="") as stream:
        chi0_rows = list(csv.reader(stream))
    with (data_dir / "chi_matrix.csv").open(encoding="ascii", newline="") as stream:
        chi_rows = list(csv.reader(stream))
    assert len(u_rows) == len(analysis["primary"]["U_by_site_eV"]) + 1
    assert len(chi0_rows) == len(analysis["primary"]["chi0_raw"]) + 1
    assert len(chi_rows) == len(analysis["primary"]["chi_raw"]) + 1


def test_raw_csv_does_not_fall_back_to_matrices_used_for_inversion(tmp_path: Path) -> None:
    source = {
        "analysis": {
            "primary": {
                "matrix_used_chi0": [[1.0]],
                "matrix_used_chi": [[2.0]],
            }
        }
    }

    export_report_csv(source, tmp_path)

    for filename in ("chi0_matrix.csv", "chi_matrix.csv"):
        with (tmp_path / filename).open(encoding="ascii", newline="") as stream:
            rows = list(csv.reader(stream))
        assert rows == [["site_id", "NOT_ASSESSED"], ["NOT_ASSESSED", "NOT_ASSESSED"]]


def test_how_to_use_block_preserves_projector_rows_and_replaces_only_u() -> None:
    analysis = json.loads(ANALYSIS_FIXTURE.read_text(encoding="utf-8"))
    model = parse_effective_fdf(REFERENCE_FDF)
    records = [
        {
            "label": item.label,
            "projector_header_value": item.projector_header_value,
            "n": item.n,
            "l": item.l,
            "u_ref_ev": item.u_ref_ev,
            "j_ref_ev": item.j_ref_ev,
            "rc_bohr": item.rc_bohr,
            "omega": item.omega,
            "lambda_values": list(item.lambda_values),
            "canonical_text": item.canonical_text,
        }
        for item in model.dftu_records
    ]
    source = {
        "analysis": analysis,
        "context": {
            "projector": {"method": model.dftu_method, "records": records},
            "reproducibility": {"command": "hubbardflow run campaign.v2.json"},
        },
        "occupation_provenance": {"records": []},
        "quality_checks": {},
        "file_map": {},
    }

    report = render_hubbardflow_out(source)

    site_indices = {
        item["site_id"]: item["index"] for item in analysis["response_observation_dataset"]["site_index_map"]
    }
    assert "%block DFTU.Proj" in report
    assert "%endblock DFTU.Proj" in report
    for record in model.dftu_records:
        site_index = site_indices[record.label]
        u_value = analysis["primary"]["U_by_site_eV"][str(site_index)]
        rows = record.canonical_text.splitlines()
        fields = rows[2].split()
        fields[0] = format(float(u_value), ".17g")
        expected_u_row = "    " + " ".join(fields)
        assert expected_u_row in report
    assert "hubbardflow check-projector" in report


def test_report_rebuild_uses_saved_context_without_changing_rendered_bytes(tmp_path: Path) -> None:
    analysis = json.loads(ANALYSIS_FIXTURE.read_text(encoding="utf-8"))
    results = tmp_path / "results"
    analysis_path = results / "lr_u_analysis.v3.json"
    analysis_path.parent.mkdir(parents=True)
    analysis_path.write_text(json.dumps(analysis), encoding="utf-8")
    occupation_path = results / "data" / "occupation_provenance.v1.json"
    occupation_path.parent.mkdir(parents=True)
    occupation_path.write_text(json.dumps({"records": []}), encoding="utf-8")
    campaign = {
        "campaign_id": "report-test",
        "functional": "PBE",
        "reference_fdf": "missing-reference.fdf",
        "lr_config_file": "missing-config.json",
        "execution_profile_file": "missing-profile.json",
        "sites": [],
    }
    arguments = {
        "campaign_root": tmp_path,
        "manifest_path": tmp_path / "campaign.v2.json",
        "campaign": campaign,
        "analysis_path": analysis_path,
        "analysis": analysis,
        "state_gate": None,
        "occupation_provenance_path": occupation_path,
    }

    first = write_campaign_report_artifacts(**arguments)
    second = write_campaign_report_artifacts(**arguments)

    assert second == first
