"""A scalar response result must not silently become a physical FDF Ueff."""

import json
import runpy
import subprocess
import sys
from pathlib import Path

import pytest

from siestaflow_hubbard.domain.hubbard_parameter_semantics import (
    HubbardParameterSemanticsError,
    require_dudarev_evidence,
)
from siestaflow_hubbard.reporting.evidence_exporter import EvidenceExporter


ROOT = Path(__file__).resolve().parents[2]
PREPARE = ROOT / "campaigns/mno_afmii_strict_lr_v3r2/audits/uncertainty_assurance_20260923/prepare_physical_convergence.py"


def test_scalar_charge_result_cannot_feed_dudarev_input(tmp_path):
    scalar = {
        "parameter_kind": "U_scalar_charge",
        "source_parameter_kind": "U_scalar_charge",
        "value_eV": 11.5321,
        "interval_eV": [11.4721, 11.5920],
        "derivation": "charge response",
        "source_reference": "MnO response result",
    }
    with pytest.raises(HubbardParameterSemanticsError, match="Ueff_Dudarev"):
        require_dudarev_evidence(scalar)
    evidence = tmp_path / "scalar.json"
    evidence.write_text(json.dumps(scalar), encoding="utf-8")
    process = subprocess.run(
        [sys.executable, str(PREPARE), "--ueff-evidence", str(evidence)],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert process.returncode != 0
    assert "Ueff_Dudarev" in process.stderr


def test_explicit_dudarev_evidence_is_distinct_from_scalar_result():
    value, interval = require_dudarev_evidence({
        "parameter_kind": "Ueff_Dudarev",
        "source_parameter_kind": "spin_resolved_response",
        "value_eV": 5.0,
        "interval_eV": [4.8, 5.2],
        "derivation": "Documented independent spin response and functional mapping",
        "source_reference": "reviewed-evidence.json",
    })
    assert (value, interval) == (5.0, (4.8, 5.2))


def test_physical_fdf_replaces_the_saved_u_entry_with_explicit_ueff():
    module = runpy.run_path(str(PREPARE))
    source = ROOT / "campaigns/mno_afmii_strict_lr_v3r2/results/u1153_minimal_afmii_relaxation/afmii_single_point/siesta.fdf"
    rendered = module["fdf_for"](
        source.read_text(encoding="utf-8"), "semantic_gate_probe", 4, 400, 5.0, "AFMII", False
    )
    assert "  5.000000 0.00" in rendered
    assert "  11.53 0.00" not in rendered
    assert "DFTU.PotentialShift     false" in rendered


def test_evidence_report_does_not_call_inversion_ueff(tmp_path):
    exporter = EvidenceExporter(str(tmp_path))
    exporter.export({"susceptibility_inversion": {"value_eV": 11.5}})
    for name in ("EVIDENCE_REPORT.md", "EVIDENCE_REPORT.html"):
        report = (tmp_path / name).read_text(encoding="utf-8")
        assert "U_scalar_charge" in report
        assert "not an automatically validated Dudarev Ueff" in report
