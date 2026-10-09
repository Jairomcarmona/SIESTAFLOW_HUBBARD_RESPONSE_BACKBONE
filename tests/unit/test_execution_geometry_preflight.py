import json
import shutil
from pathlib import Path

import pytest

from hubbardflow.domain.geometry_preflight import GeometryPreflightState
from hubbardflow.execution.geometry_preflight import build_geometry_preflight
from hubbardflow.reporting.hubbardflow_ascii_report import render_hubbardflow_out

FIXTURES = Path(__file__).parents[1] / "fixtures"


def _reference_record(cwd: Path | str) -> dict[str, object]:
    return {
        "kind": "siesta",
        "state": "VALIDATED",
        "artifact_spec": {"output": "siesta.out", "fdf": "siesta.fdf"},
        "command": {"cwd": str(cwd)},
        "provenance": {
            "node": {"node_id": "reference", "kind": "REFERENCE"},
        },
    }


def test_build_uses_registered_reference_node_only(tmp_path: Path) -> None:
    root = tmp_path
    ref_cwd = root / ".siestaflow" / "attempts" / "ref-node"
    ref_cwd.mkdir(parents=True)
    shutil.copyfile(FIXTURES / "cu3n_probe_reference_siesta.out", ref_cwd / "siesta.out")
    shutil.copyfile(FIXTURES / "cu3n_probe_reference.fdf", root / "reference.fdf")
    # A perturbation output with very different geometry evidence must be ignored.
    perturbation = root / ".siestaflow" / "attempts" / "perturbation-node"
    perturbation.mkdir()
    (perturbation / "siesta.out").write_text(
        "siesta: Atomic forces (eV/Ang):\nMax 99.0\nRes 1.0\n"
        "Stress tensor Voigt[x,y,z,yz,xz,xy] (kbar): 99 99 99 0 0 0\n",
        encoding="utf-8",
    )
    evidence = {
        "nodes": {
            "reference": _reference_record("/cluster/job/runs/cu3n_probe/.siestaflow/attempts/ref-node"),
            "response:bare": {
                **_reference_record(perturbation),
                "provenance": {"node": {"node_id": "response:bare", "kind": "RESPONSE"}},
            },
        }
    }
    node_dir = root / ".siestaflow"
    node_dir.mkdir(exist_ok=True)
    (node_dir / "node-evidence.json").write_text(json.dumps(evidence), encoding="utf-8")

    result = build_geometry_preflight(
        root,
        {"reference_fdf": "reference.fdf"},
        {},
    )

    assert result["state"] == GeometryPreflightState.ABOVE_REFERENCE_THRESHOLDS.value
    assert result["maximum_force_ev_ang"] == 0.0
    assert result["mean_pressure_kbar"] == pytest.approx(-7.4)
    assert result["source_lines"] == {
        "maximum_force": 7081,
        "residual_force": 7082,
        "maximum_constrained_force": 7084,
        "stress": 7086,
    }
    assert result["xc_functional"] == "GGA"
    assert result["xc_authors"] == "PBE"
    assert result["hubbard_context"] == [
        {"label": "CuLR00", "u_ref_ev": 0.0, "j_ref_ev": 0.0, "potential_shift": True}
    ]
    assert result["reference_output_sha256"] == (
        "7dff41fa8e58798042c250803a007033776979a81d06002573de872507e49248"
    )


def test_configured_threshold_is_visible_in_record_only_report(tmp_path: Path) -> None:
    root = tmp_path
    ref_cwd = root / ".siestaflow" / "attempts" / "registered-reference"
    ref_cwd.mkdir(parents=True)
    shutil.copyfile(FIXTURES / "cu3n_probe_reference_siesta.out", ref_cwd / "siesta.out")
    shutil.copyfile(FIXTURES / "cu3n_probe_reference.fdf", root / "reference.fdf")
    (root / ".siestaflow" / "node-evidence.json").write_text(
        json.dumps({"nodes": {"reference": _reference_record(ref_cwd)}}), encoding="utf-8"
    )
    result = build_geometry_preflight(
        root,
        {"reference_fdf": "reference.fdf"},
        {"geometry_preflight": {"max_abs_mean_pressure_kbar": 8.0}},
    )
    report = render_hubbardflow_out({"geometry_preflight": result})

    assert result["state"] == GeometryPreflightState.NEAR_EQUILIBRIUM.value
    assert "[14] REFERENCE GEOMETRY PREFLIGHT" in report
    assert "U computed for the geometry as supplied; no relaxation performed by HubbardFlow." in report
    assert "A geometry relaxed with another functional (e.g. PBE+U) may appear unrelaxed." in report
    assert "max shear:" in report
    assert all(len(line) <= 80 for line in report.splitlines())
    assert report.isascii()


def test_missing_reference_registration_does_not_search_other_outputs(tmp_path: Path) -> None:
    other = tmp_path / ".siestaflow" / "attempts" / "perturbation"
    other.mkdir(parents=True)
    (other / "siesta.out").write_text("Max 99.0\n", encoding="utf-8")
    (tmp_path / ".siestaflow" / "node-evidence.json").write_text(
        json.dumps({"nodes": {"response:bare": _reference_record(other)}}), encoding="utf-8"
    )

    result = build_geometry_preflight(tmp_path, {}, {})

    assert result["state"] == GeometryPreflightState.NOT_ASSESSED_NO_OUTPUT.value


def test_registered_path_cannot_escape_campaign_root(tmp_path: Path) -> None:
    root = tmp_path / "campaign"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "siesta.out").write_text("Max 0.0\n", encoding="utf-8")
    node_dir = root / ".siestaflow"
    node_dir.mkdir()
    (node_dir / "node-evidence.json").write_text(
        json.dumps({"nodes": {"reference": _reference_record(outside)}}), encoding="utf-8"
    )

    result = build_geometry_preflight(root, {}, {})

    assert result["state"] == GeometryPreflightState.NOT_ASSESSED_NO_OUTPUT.value
