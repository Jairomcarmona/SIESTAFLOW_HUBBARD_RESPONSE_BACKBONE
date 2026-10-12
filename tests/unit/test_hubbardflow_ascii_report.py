from __future__ import annotations

import csv
import json
import re
from copy import deepcopy
from pathlib import Path

from hubbardflow.execution.campaign_report_artifacts import write_campaign_report_artifacts
from hubbardflow.execution.report_csv_exports import export_report_csv
from hubbardflow.reporting.hubbardflow_ascii_formatting import wrap_lines
from hubbardflow.reporting.hubbardflow_ascii_report import render_hubbardflow_out
from hubbardflow.siesta_backend.fdf_model import parse_effective_fdf

ROOT = Path(__file__).resolve().parents[2]
ANALYSIS_FIXTURE = ROOT / "tests" / "fixtures" / "replay_nio_p5" / "replay_analysis.v3.json"
STATE_GATE_FIXTURE = ROOT / "tests" / "fixtures" / "replay_nio_p5" / "replay_i5_state_gate.json"
REFERENCE_FDF = ROOT / "tests" / "fixtures" / "real_nio_p5_rerun" / "inputs" / "reference.fdf"
PROJECTOR_CURVE = ROOT / "tests" / "fixtures" / "projector_curve_m1.json"


def _assert_report_shape(report: str) -> None:
    raw = report.encode("ascii")
    assert all(byte <= 127 for byte in raw)
    assert all(len(line) <= 80 for line in report.splitlines())
    headings = []
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
        title = f"[{index:02d}] {heading}"
        assert title in report
        headings.append(title)
    assert report.index("RESULT SUMMARY") < report.index("[01] HEADER")
    headings.extend(
        (
            "RESULT SUMMARY",
            "QUALITY CHECKS",
            "HOW TO USE THIS U",
            "APPLICABILITY",
            "NOT ASSESSED / NOT CLAIMED",
            "REPRODUCIBILITY",
            "CONVENTIONS",
            "REFERENCES AND CITATION",
        )
    )
    report_lines = report.splitlines()
    for heading in headings:
        index = report_lines.index(heading)
        assert report_lines[index + 1] == "-" * len(heading)


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
    projector_curve = json.loads(PROJECTOR_CURVE.read_text(encoding="utf-8"))
    points = {float(row["projector"]["value"]): float(row["u_ev"]) for row in projector_curve["points"]}
    delta_u_ev = abs(points[0.85] - points[0.90])
    projector_section = report.split("[03] PROJECTOR", 1)[1].split("[04] PROTOCOL", 1)[0]
    assert f"M1 changed by {delta_u_ev:.4f} eV" in projector_section
    assert "tests/fixtures/projector_curve_m1.json" in projector_section


def test_inventory_paths_wrap_only_at_slashes_and_keep_node_fields_together() -> None:
    analysis = deepcopy(json.loads(ANALYSIS_FIXTURE.read_text(encoding="utf-8")))
    dataset = analysis["response_observation_dataset"]
    long_component = "campaign-" + "x" * 45
    dataset["reference_source"] = {
        "node_id": "reference-long-path",
        "out_path": f"C:\\validation\\{long_component}\\attempts\\reference-run\\outputs\\siesta.out",
        "state": "COMPLETED",
    }
    source = {"analysis": analysis, "occupation_provenance": {"records": []}}

    report = render_hubbardflow_out(source)
    lines = report.splitlines()
    node_line = next(i for i, line in enumerate(lines) if line.startswith("  reference-long-path |"))
    assert lines[node_line] == "  reference-long-path | REFERENCE_SCREENED | NOT_APPLICABLE | COMPLETED"
    assert lines[node_line + 1].startswith("    PATH: ")
    assert all(len(line) <= 80 for line in lines)

    path_lines = [lines[node_line + 1]]
    index = node_line + 2
    while index < len(lines) and lines[index].startswith("          "):
        path_lines.append(lines[index])
        index += 1
    assert len(path_lines) >= 2
    rendered_folder = "".join(line.strip().removeprefix("PATH: ") for line in path_lines)
    assert rendered_folder == f"C:/validation/{long_component}/attempts/reference-run/outputs"
    assert long_component in rendered_folder
    assert any(long_component in line for line in path_lines)
    assert "reference-run" in rendered_folder


def test_wrapping_preserves_indivisible_tokens_and_matrix_precision_is_uniform() -> None:
    token = "node_" + "x" * 68
    wrapped = wrap_lines(["  PREFIX " + token + " suffix"])
    assert all(len(line) <= 80 for line in wrapped)
    assert any(token in line for line in wrapped)

    analysis = json.loads(ANALYSIS_FIXTURE.read_text(encoding="utf-8"))
    state_gate = json.loads(STATE_GATE_FIXTURE.read_text(encoding="utf-8"))
    report = render_hubbardflow_out(
        {
            "analysis": analysis,
            "context": {},
            "state_gate": state_gate,
            "occupation_provenance": {"records": []},
            "quality_checks": {},
            "file_map": {},
        }
    )
    lines = report.splitlines()
    matrix_start = lines.index("[09] MATRICES")
    inversion_start = lines.index("[10] INVERSION")
    matrix_values = []
    for line in lines[matrix_start:inversion_start]:
        if "|" in line and line.lstrip().startswith(tuple(str(i) for i in range(10))):
            matrix_values.extend(re.findall(r"-?\d+\.\d+", line.split("|", 1)[1]))
    assert matrix_values
    assert all(re.fullmatch(r"-?\d+\.\d{8}", value) for value in matrix_values)
    assert "[inverse(CHI0)]_ii =" in report
    assert "[inverse(CHI)]_ii =" in report
    assert "U_i =" in report
    assert any(
        re.fullmatch(r"    U_i =\s+-?\d+\.\d{8} -\s+-?\d+\.\d{8} =\s+-?\d+\.\d{8} eV", line)
        for line in lines[inversion_start:]
    )
    assert all(re.search(r"-?\d+\.\d{8}", line) for line in lines[inversion_start:] if "[inverse(" in line)


def test_diagnostics_has_only_one_not_assessed_line_without_projector_sites() -> None:
    analysis = json.loads(ANALYSIS_FIXTURE.read_text(encoding="utf-8"))
    analysis["projector_diagnostics"] = {"sites": []}
    report = render_hubbardflow_out({"analysis": analysis})
    diagnostics = report.split("[12] DIAGNOSTICS", 1)[1].split("[13] FILE MAP", 1)[0]
    assert diagnostics.count("Occupation/formal/free-atom and U*abs(CHI0):") == 1
    assert "Occupation/formal/free-atom and U*abs(CHI0): NOT_ASSESSED" in diagnostics


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
