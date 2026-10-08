from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from hubbardflow.domain.projector_compatibility_models import (
    ProjectorCompatibilityStatus,
    ProjectorIncompleteReason,
)
from hubbardflow.reporting.projector_compatibility_report import render_projector_compatibility_report
from hubbardflow.siesta_backend.projector_compatibility import check_campaign_projectors


def _run_cli(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    command = "from hubbardflow.cli import main; raise SystemExit(main())"
    return subprocess.run(
        [sys.executable, "-c", command, *arguments],
        capture_output=True,
        check=False,
        text=True,
    )


def _fdf(
    labels: tuple[str, ...],
    *,
    cutoff_norm: str | None,
    projector_method: int = 2,
    u_ev: str = "0.0",
    j_ev: str = "0.0",
    lambda_values: tuple[str, ...] = (),
) -> str:
    species_lines = "\n".join(
        f"{index} {25 if label.startswith('Mn') else 8} {label}" for index, label in enumerate(labels, 1)
    )
    atoms = "\n".join(f"0.0 0.0 0.0 {index}" for index in range(1, len(labels) + 1))
    projectors: list[str] = []
    basis: list[str] = []
    for label in labels:
        n, angular = (3, 2) if label.startswith("Mn") else (2, 1)
        values = " ".join((u_ev, j_ev, *lambda_values))
        projectors.extend((label + " 1", f"{n} {angular}", values, "0.0 0.05"))
        basis.extend((label, f"n={n} {angular}", "3.5 3.5"))
    cutoff = "" if cutoff_norm is None else f"DFTU.CutoffNorm {cutoff_norm}\n"
    projector_text = "\n".join(projectors)
    basis_text = "\n".join(basis)
    return f"""NumberOfAtoms {len(labels)}
NumberOfSpecies {len(labels)}
%block ChemicalSpeciesLabel
{species_lines}
%endblock ChemicalSpeciesLabel
LatticeConstant 1 Ang
%block LatticeVectors
1 0 0
0 1 0
0 0 1
%endblock LatticeVectors
AtomicCoordinatesFormat Fractional
%block AtomicCoordinatesAndAtomicSpecies
{atoms}
%endblock AtomicCoordinatesAndAtomicSpecies
DFTU.ProjectorGenerationMethod {projector_method}
{cutoff}PAO.BasisSize DZP
PAO.EnergyShift 0.005 Ry
PAO.SplitNorm 0.15
%block DFTU.Proj
{projector_text}
%endblock DFTU.Proj
%block PAO.Basis
{basis_text}
%endblock PAO.Basis
"""


def _record(label: str = "MnLR00") -> dict[str, object]:
    return {
        "label": label,
        "projector_header_value": "1",
        "n": 3,
        "l": 2,
        "u_ref_ev": 0.0,
        "j_ref_ev": 0.0,
        "rc_bohr": 0.0,
        "omega": 0.05,
        "lambda_values": [],
        "canonical_text": f"{label} 1\n3 2\n0.0 0.0\n0.0 0.05",
    }


def _write_campaign(root: Path, source_fdf: str, *, plan_record: dict[str, object] | None = None) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "reference.fdf").write_text(source_fdf, encoding="utf-8")
    (root / "resolved_perturbation_plan.json").write_text(
        json.dumps(
            {
                "schema": "hubbardflow.resolved_perturbation_plan.v1",
                "inventory": {
                    "subspaces": [
                        {
                            "species_label": "MnLR00",
                            "dftu_record": _record() if plan_record is None else plan_record,
                        },
                    ]
                },
            }
        ),
        encoding="utf-8",
    )
    campaign_path = root / "campaign.v2.json"
    campaign_path.write_text(
        json.dumps(
            {
                "schema": "siestaflow.campaign.v2",
                "reference_fdf": "reference.fdf",
                "resolved_perturbation_plan_file": "resolved_perturbation_plan.json",
            }
        ),
        encoding="utf-8",
    )
    return campaign_path


def test_campaign_usage_values_are_informational_in_comparison_and_report(tmp_path: Path) -> None:
    campaign_dir = tmp_path / "campaign"
    target_dir = tmp_path / "target"
    plan_record = _record()
    plan_record.update(u_ref_ev=11.117477, j_ref_ev=0.4, lambda_values=[0.1])
    campaign = _write_campaign(
        campaign_dir,
        _fdf(("MnLR00",), cutoff_norm=None),
        plan_record=plan_record,
    )
    plan_path = campaign_dir / "resolved_perturbation_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    second_record = _record()
    second_record.update(u_ref_ev=11.117477, j_ref_ev=0.4, lambda_values=[0.05])
    plan["inventory"]["subspaces"].append({"species_label": "MnLR00", "dftu_record": second_record})
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    target_dir.mkdir()
    target_fdf = target_dir / "dftu.fdf"
    target_fdf.write_text(
        _fdf(
            ("Mn",),
            cutoff_norm="0.90",
            u_ev="11.5325",
            j_ev="0.2",
            lambda_values=("0.25",),
        ),
        encoding="utf-8",
    )

    report = check_campaign_projectors(campaign, target_fdf, [("MnLR00", "Mn")])
    comparison = report.results[0]
    rendered = render_projector_compatibility_report(report)

    assert report.status is ProjectorCompatibilityStatus.MATCH
    assert len(comparison.lr_informational_values) == 2
    assert len(comparison.dftu_informational_values) == 1
    assert [item.u_ref_ev for item in comparison.lr_informational_values] == [11.117477, 11.117477]
    assert comparison.dftu_informational_values[0].u_ref_ev == 11.5325
    assert [item.lambda_values for item in comparison.lr_informational_values] == [(0.05,), (0.1,)]
    assert comparison.dftu_informational_values[0].lambda_values == (0.25,)
    assert "11.117477" in rendered
    assert "11.5325" in rendered
    assert "do not affect status" in rendered

    plan["inventory"]["subspaces"].reverse()
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    reordered = check_campaign_projectors(campaign, target_fdf, [("MnLR00", "Mn")])
    assert reordered.results[0] == comparison


def test_mixed_projector_definitions_remain_incomplete_in_any_inventory_order(tmp_path: Path) -> None:
    campaign_dir = tmp_path / "campaign"
    target_dir = tmp_path / "target"
    inconsistent_record = _record()
    inconsistent_record.update(n=4, u_ref_ev=11.0)
    campaign = _write_campaign(
        campaign_dir,
        _fdf(("MnLR00",), cutoff_norm=None),
        plan_record=inconsistent_record,
    )
    plan_path = campaign_dir / "resolved_perturbation_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    consistent_record = _record()
    consistent_record.update(u_ref_ev=10.0)
    plan["inventory"]["subspaces"].append({"species_label": "MnLR00", "dftu_record": consistent_record})
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    target_dir.mkdir()
    target_fdf = target_dir / "dftu.fdf"
    target_fdf.write_text(_fdf(("Mn",), cutoff_norm="0.90"), encoding="utf-8")

    forward = check_campaign_projectors(campaign, target_fdf, [("MnLR00", "Mn")])
    plan["inventory"]["subspaces"].reverse()
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    reversed_report = check_campaign_projectors(campaign, target_fdf, [("MnLR00", "Mn")])

    for report in (forward, reversed_report):
        assert report.status is ProjectorCompatibilityStatus.INCOMPLETE
        assert (
            ProjectorIncompleteReason.SOURCE_DEFINITION_INCONSISTENT in report.results[0].incomplete_reasons
        )
    assert forward.results[0] == reversed_report.results[0]


def test_check_projector_uses_explicit_mapping_and_ignores_other_species(tmp_path: Path) -> None:
    campaign_dir = tmp_path / "campaign"
    target_dir = tmp_path / "target"
    campaign = _write_campaign(campaign_dir, _fdf(("MnLR00",), cutoff_norm=None))
    target_dir.mkdir()
    target_fdf = target_dir / "dftu.fdf"
    target_fdf.write_text(_fdf(("Mn", "O"), cutoff_norm="0.90"), encoding="utf-8")
    source_pseudos = campaign_dir / "pseudopotentials"
    target_pseudos = target_dir / "pseudopotentials"
    source_pseudos.mkdir()
    target_pseudos.mkdir()
    (source_pseudos / "MnLR00.psml").write_text("LR bytes", encoding="utf-8")
    (target_pseudos / "Mn.psml").write_text("DFT+U bytes", encoding="utf-8")

    report_path = tmp_path / "report.json"
    completed = _run_cli(
        [
            "check-projector",
            "--campaign",
            str(campaign),
            "--target-fdf",
            str(target_fdf),
            "--map",
            "MnLR00=Mn",
            "--json-out",
            str(report_path),
        ]
    )

    screen = completed.stdout
    assert not completed.stderr
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert completed.returncode == 0
    assert screen.startswith("HUBBARDFLOW  |  PROJECTOR APPLICABILITY")
    assert "[MATCH]" in screen
    assert "sha256=" in screen
    assert not screen.lstrip().startswith("{")
    assert report["status"] == "MATCH"
    assert report["comparisons"][0]["lr_label"] == "MnLR00"
    assert report["comparisons"][0]["dftu_label"] == "Mn"
    assert report["comparisons"][0]["digest_warnings"][0]["role"] == "psml"
    assert "Informational DFTU.Proj values" in screen
    assert "DFT+U applied" in screen
    assert report["comparisons"][0]["lr_informational_values"][0]["u_ref_ev"] == 0.0
    assert report["comparisons"][0]["dftu_informational_values"][0]["lambda_values"] == []


def test_check_projector_records_force_and_keeps_mismatch_status(tmp_path: Path) -> None:
    campaign_dir = tmp_path / "campaign"
    target_dir = tmp_path / "target"
    campaign = _write_campaign(campaign_dir, _fdf(("MnLR00",), cutoff_norm=None))
    target_dir.mkdir()
    target_fdf = target_dir / "dftu.fdf"
    target_fdf.write_text(_fdf(("Mn",), cutoff_norm="0.95"), encoding="utf-8")

    report_path = tmp_path / "report.json"
    completed = _run_cli(
        [
            "check-projector",
            "--campaign",
            str(campaign),
            "--target-fdf",
            str(target_fdf),
            "--map",
            "MnLR00=Mn",
            "--force",
            "--json-out",
            str(report_path),
        ]
    )

    screen = completed.stdout
    assert not completed.stderr
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert completed.returncode == 0
    assert "[MISMATCH]" in screen
    assert "--force was explicitly requested" in screen
    assert report["status"] == "MISMATCH"
    assert report["force_requested"] is True
    assert report["application_permitted"] is True


def test_unreadable_artifact_digest_is_reported_without_changing_match(tmp_path: Path) -> None:
    campaign_dir = tmp_path / "campaign"
    target_dir = tmp_path / "target"
    campaign = _write_campaign(campaign_dir, _fdf(("MnLR00",), cutoff_norm=None))
    target_dir.mkdir()
    target_fdf = target_dir / "dftu.fdf"
    target_fdf.write_text(_fdf(("Mn",), cutoff_norm="0.90"), encoding="utf-8")
    source_pseudos = campaign_dir / "pseudopotentials"
    source_pseudos.mkdir()
    (source_pseudos / "MnLR00.psml").write_text("LR bytes", encoding="utf-8")
    original_read_bytes = Path.read_bytes

    def read_bytes_with_failure(path: Path) -> bytes:
        if path.name == "MnLR00.psml":
            raise OSError("permission denied")
        return original_read_bytes(path)

    with patch.object(Path, "read_bytes", read_bytes_with_failure):
        report = check_campaign_projectors(campaign, target_fdf, [("MnLR00", "Mn")])

    assert report.status is ProjectorCompatibilityStatus.MATCH
    assert report.results[0].lr_artifact_digest_issues[0].endswith("permission denied")
    assert "digest unavailable (traceability only)" in render_projector_compatibility_report(report)
