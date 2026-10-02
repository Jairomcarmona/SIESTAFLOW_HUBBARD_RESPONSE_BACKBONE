"""Safety, schema, and reproducibility tests for the FD-EBQ sidecar tool."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from tools import fdebq_diagnose


def _analysis_input(path: Path) -> Path:
    alphas = (-0.04, -0.02, 0.02, 0.04)
    rows: list[dict[str, object]] = []
    references = {"site-a": 5.2, "site-b": 5.7}
    for perturbed in ("site-b", "site-a"):
        for alpha in reversed(alphas):
            observed: list[dict[str, object]] = []
            for observed_site in ("site-b", "site-a"):
                reference = references[observed_site]
                bare_slope = 1.0 if observed_site == perturbed else 0.2
                screened_slope = 0.3 if observed_site == perturbed else 0.1
                observed.append(
                    {
                        "observed_site_id": observed_site,
                        "occupations_electron": {
                            "bare": reference + bare_slope * alpha + 0.7 * alpha**3,
                            "screened": reference + screened_slope * alpha + 0.02 * alpha**3,
                            "reference": reference,
                        },
                        "occupation_half_widths_electron": {
                            "bare": 0.0000005,
                            "screened": 0.0000005,
                            "reference": 0.0000005,
                        },
                    }
                )
            rows.append(
                {
                    "alpha_eV": alpha,
                    "perturbed_site_id": perturbed,
                    "observed_sites": observed,
                }
            )
    analysis = {
        "schema_version": "siestaflow.lr_u_analysis.v3",
        "alpha_grid_eV": list(alphas),
        "estimator_policy": {"estimator": "linear", "polynomial_degree": 3},
        "selected_estimator": {"method": "linear", "degree": 1},
        "response_observation_dataset": {
            "matrix_index_to_site_id": {"0": "site-a", "1": "site-b"},
            "occupation_source": "siesta_occupations_total",
            "reference_source": {"node_id": "reference-0"},
            "rows": rows,
        },
    }
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(analysis), encoding="utf-8")
    return path


def test_refuses_protected_repository_output(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setattr(fdebq_diagnose, "REPO_ROOT", repo)
    input_path = _analysis_input(tmp_path / "source" / "analysis.json")
    for folder in ("results", "benchmarks", "validation_observables_v6"):
        output = repo / folder / "diagnostic"
        with pytest.raises(fdebq_diagnose.DiagnosticToolError, match="protected directory"):
            fdebq_diagnose.run_diagnostic(input_path, output, 1.0)
        assert not output.exists()


def test_refuses_direct_and_symlink_output_under_protected_feo_export(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repo = tmp_path / "repo"
    protected = repo / "FEO_SCF_DIAGNOSTIC_EXPORT_20261001"
    repo.mkdir()
    monkeypatch.setattr(fdebq_diagnose, "REPO_ROOT", repo)
    input_path = _analysis_input(tmp_path / "source" / "analysis.json")

    direct_output = protected / "diagnostic"
    with pytest.raises(fdebq_diagnose.DiagnosticToolError, match="protected directory"):
        fdebq_diagnose._reject_unsafe_output(input_path.resolve(), direct_output.resolve())
    assert not direct_output.exists()

    symlink = tmp_path / "output-link"
    try:
        symlink.symlink_to(protected, target_is_directory=True)
    except OSError as exc:
        if os.name != "nt":
            pytest.skip(f"directory symlinks are unavailable in this environment: {exc}")
        protected.mkdir(parents=True)
        junction = subprocess.run(
            ["cmd.exe", "/c", "mklink", "/J", str(symlink), str(protected)],
            capture_output=True,
            text=True,
            check=False,
        )
        if junction.returncode != 0:
            pytest.skip(f"directory links are unavailable in this environment: {exc}; {junction.stderr}")
    assert (symlink / "diagnostic").resolve() == (protected / "diagnostic").resolve()
    with pytest.raises(fdebq_diagnose.DiagnosticToolError, match="protected directory"):
        fdebq_diagnose._reject_unsafe_output(
            input_path.resolve(), (symlink / "diagnostic").resolve(strict=False)
        )
    assert not direct_output.exists()


def test_refuses_campaign_results_and_input_containing_directories(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setattr(fdebq_diagnose, "REPO_ROOT", repo)
    input_path = _analysis_input(tmp_path / "source" / "analysis.json")
    campaign_output = repo / "campaigns" / "sample" / "results" / "diagnostic"
    with pytest.raises(fdebq_diagnose.DiagnosticToolError, match=r"campaigns/\*/results"):
        fdebq_diagnose.run_diagnostic(input_path, campaign_output, 1.0)
    with pytest.raises(fdebq_diagnose.DiagnosticToolError, match="separate from the input"):
        fdebq_diagnose.run_diagnostic(input_path, input_path.parent / "diagnostic", 1.0)
    assert not campaign_output.exists()
    assert not (input_path.parent / "diagnostic").exists()


def test_refuses_nonempty_output_directory(tmp_path: Path) -> None:
    input_path = _analysis_input(tmp_path / "source" / "analysis.json")
    output = tmp_path / "output"
    output.mkdir()
    existing_file = output / "keep.txt"
    existing_file.write_text("leave unchanged", encoding="utf-8")
    with pytest.raises(fdebq_diagnose.DiagnosticToolError, match="not empty"):
        fdebq_diagnose.run_diagnostic(input_path, output, 1.0)
    assert existing_file.read_text(encoding="utf-8") == "leave unchanged"


def test_output_schema_scope_and_deterministic_bytes(tmp_path: Path) -> None:
    input_path = _analysis_input(tmp_path / "source" / "analysis.json")
    output_a = tmp_path / "output-a"
    output_b = tmp_path / "output-b"
    fdebq_diagnose.run_diagnostic(input_path, output_a, 1.0)
    fdebq_diagnose.run_diagnostic(input_path, output_b, 1.0)

    json_a = (output_a / fdebq_diagnose.OUTPUT_JSON).read_bytes()
    markdown_a = (output_a / fdebq_diagnose.OUTPUT_MARKDOWN).read_bytes()
    assert json_a == (output_b / fdebq_diagnose.OUTPUT_JSON).read_bytes()
    assert markdown_a == (output_b / fdebq_diagnose.OUTPUT_MARKDOWN).read_bytes()
    payload = json.loads(json_a)
    assert payload["schema"] == "hubbardflow.fdebq_diagnostic.v1"
    assert payload["scope"] == ("diagnostic, print-quantization bounds only; SCF component not assessed")
    assert len(payload["input_sha256"]) == 64
    assert len(payload["protocol_digest"]) == 64
    assert payload["kappa"] == 1.0
    assert payload["package_version"]
    assert len(payload["series"]) == 8
    assert "timestamp" not in payload
    assert b"SCF component not assessed" in markdown_a


def test_auto_estimator_uses_reported_selected_method() -> None:
    analysis: dict[str, object] = {
        "estimator_policy": {"estimator": "auto", "polynomial_degree": 3},
        "selected_estimator": {"method": "linear"},
    }
    kind, degree = fdebq_diagnose._estimator_policy(analysis)
    assert kind.value == "LINEAR_LSQ"
    assert degree is None
