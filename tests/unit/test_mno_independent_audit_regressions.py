"""Regressions found by the independent MnO response audit of 2026-09-25.

Each test reproduces a software defect with a concrete input.  The archived
MnO campaign is only read; truncated or relabelled copies are written to
``tmp_path``.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys

import numpy as np
import pytest

from siestaflow_hubbard.domain.hubbard_parameter_semantics import (
    HubbardParameterSemanticsError,
    require_dudarev_evidence,
)
from siestaflow_hubbard.siesta_backend.fdf_builder import FdfBuilder
from siestaflow_hubbard.siesta_backend.event_parser import parse_hubbard_population_events


ROOT = Path(__file__).resolve().parents[2]
RESULTS_NAME = "response-matrix-foreground-recovery-v4"
RESULTS = ROOT / "campaigns/mno_afmii_strict_lr_v3r2/results" / RESULTS_NAME
ANALYZER = ROOT / "tools/run_mno_afmii_response_quantized_v1.py"
MNO_ATOM_INDICES = [1, 2, 5, 6, 9, 10, 13, 14, 17, 18, 21, 22, 25, 26, 29, 30]


def _load_analyzer(monkeypatch):
    monkeypatch.setenv("SIESTAFLOW_MNO_RESPONSE_RESULTS", RESULTS_NAME)
    spec = importlib.util.spec_from_file_location("mno_quantized_analyzer_under_test", ANALYZER)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.syspath_prepend(str(ROOT / "tools"))
    spec.loader.exec_module(module)
    return module


# --- FDF builder: explicit per-projector shifts must not inherit a Mn target ---

def _nio_projections(alpha: float) -> list[dict]:
    return [
        {"species": "NiLR0", "n": 3, "l": 2, "rc": 3.0, "omega": 0.05, "alpha": alpha},
        {"species": "NiLR1", "n": 3, "l": 2, "rc": 3.0, "omega": 0.05, "alpha": 0.0},
    ]


def test_explicit_projection_shifts_do_not_inherit_default_mn_target():
    """A NiO SCREENED FDF with one explicit shifted projector must materialize.

    Before the fix, ``modify_fdf_content`` passed its default ``species='Mn'``
    as the target even when every projector already carried an explicit
    alpha, so every non-Mn campaign raised ``found 0``.
    """
    base = "SystemLabel nio\nNumberOfAtoms 4\nSpin polarized\n"
    text = FdfBuilder().modify_fdf_content(base, alpha=0.01, projections=_nio_projections(0.01))
    block = text.split("%block DFTU.proj", 1)[1].split("%endblock DFTU.proj", 1)[0]
    shifted = [line for line in block.splitlines() if line.strip().startswith("0.0100")]
    assert len(shifted) == 1
    assert "NiLR0" in block and "NiLR1" in block and "Mn" not in block


def test_explicit_projection_shifts_still_require_a_single_perturbed_site():
    projections = _nio_projections(0.01)
    projections[1]["alpha"] = 0.01
    with pytest.raises(ValueError, match="exactly one projector"):
        FdfBuilder().modify_fdf_content("SystemLabel nio\n", alpha=0.01, projections=projections)


def test_implicit_projection_still_uses_the_declared_species_target():
    text = FdfBuilder().modify_fdf_content("SystemLabel feo\n", alpha=0.02, species="Fe")
    block = text.split("%block DFTU.proj", 1)[1]
    assert block.split()[0:2] == ["Fe", "1"] and "0.0200" in block


# --- SCREENED observation must come from a converged SCF, fail closed otherwise ---

def _truncate_before_convergence(source: Path, destination: Path) -> None:
    """Keep five in-loop population blocks and drop every convergence marker."""
    lines = source.read_text(encoding="utf-8").splitlines(keepends=True)
    starts = [i for i, line in enumerate(lines) if line.startswith("hubbard_term: recalculating local occupations")]
    cut = starts[5]
    kept = "".join(lines[:cut])
    assert "SCF Convergence" not in kept and "Using DM_out" not in kept
    destination.write_text(kept + "\nJob completed\n", encoding="utf-8")


def test_screened_reanalysis_rejects_an_unconverged_trace(monkeypatch, tmp_path):
    analyzer = _load_analyzer(monkeypatch)
    truncated = tmp_path / "siesta.out"
    _truncate_before_convergence(RESULTS / "A_SCREENED_p0d050/siesta.out", truncated)
    with pytest.raises(RuntimeError, match="SCREENED"):
        analyzer._occupations(truncated, "SCREENED", MNO_ATOM_INDICES)


def test_screened_reanalysis_rejects_an_explicit_nonconvergence(monkeypatch, tmp_path):
    analyzer = _load_analyzer(monkeypatch)
    text = (RESULTS / "A_SCREENED_p0d050/siesta.out").read_text(encoding="utf-8")
    forged = tmp_path / "siesta.out"
    forged.write_text(text.replace("SCF Convergence by DM+H criterion",
                                   "SCF_NOT_CONV: SCF did not converge  in maximum number of steps."),
                      encoding="utf-8")
    with pytest.raises(RuntimeError, match="SCREENED"):
        analyzer._occupations(forged, "SCREENED", MNO_ATOM_INDICES)


def test_screened_reanalysis_rejects_a_population_block_after_completion(monkeypatch, tmp_path):
    analyzer = _load_analyzer(monkeypatch)
    source = RESULTS / "A_SCREENED_p0d050/siesta.out"
    text = source.read_text(encoding="utf-8")
    events = [event for event in parse_hubbard_population_events(text) if event.atoms]
    assert events
    lines = text.splitlines()
    event = events[-1]
    appended_block = lines[event.source_start_line : event.source_end_line + 1]
    assert appended_block and not any("Job completed" in line for line in appended_block)
    assert "Using DM_out to compute the final energy and forces" in lines
    del lines[event.source_start_line : event.source_end_line + 1]
    forged = tmp_path / "siesta.out"
    forged.write_text("\n".join(lines).rstrip() + "\n" + "\n".join(appended_block) + "\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="SCREENED"):
        analyzer._occupations(forged, "SCREENED", MNO_ATOM_INDICES)


def test_screened_reanalysis_keeps_archived_converged_values(monkeypatch):
    analyzer = _load_analyzer(monkeypatch)
    measured = analyzer._occupations(RESULTS / "A_SCREENED_p0d050/siesta.out", "SCREENED", MNO_ATOM_INDICES)
    assert measured["printed_totals_e"][0] == pytest.approx(4.831381, abs=0.0)
    assert len(measured["printed_totals_e"]) == 16


# --- The scalar charge result must never pass a relabelled Dudarev guard ---

@pytest.mark.parametrize("kind", [" U_scalar_charge", "u_scalar_charge", "U_SCALAR_CHARGE\n"])
def test_scalar_kind_spelling_variants_cannot_bypass_dudarev_guard(kind):
    with pytest.raises(HubbardParameterSemanticsError, match="U_scalar_charge"):
        require_dudarev_evidence({
            "parameter_kind": "Ueff_Dudarev",
            "source_parameter_kind": kind,
            "value_eV": 11.5321,
            "derivation": "relabelled scalar response",
            "source_reference": "analysis-result-corrected-v1.json",
        })


def test_dudarev_kind_itself_is_still_matched_strictly():
    """Normalisation is used only to recognise the forbidden source kind."""
    with pytest.raises(HubbardParameterSemanticsError, match="parameter_kind=Ueff_Dudarev"):
        require_dudarev_evidence({
            "parameter_kind": " ueff_dudarev ",
            "source_parameter_kind": "spin_resolved_response",
            "value_eV": 5.0,
            "derivation": "documented",
            "source_reference": "reviewed.json",
        })


# --- The quantized analysis must declare what its number is -------------------

def test_quantized_analysis_declares_scalar_charge_and_keeps_estimate(monkeypatch, tmp_path):
    analyzer = _load_analyzer(monkeypatch)
    result = analyzer.analyze(tmp_path / "reanalysis.json")
    assert result["parameter_kind"] == "U_scalar_charge"
    mapping = result["dftu_functional_parameter"]
    assert mapping["kind"] == "Ueff_Dudarev"
    assert mapping["status"] == "NOT_IDENTIFIED_BY_THIS_DATA"
    # The estimator and print-rounding interval are unchanged by the audit.
    assert result["U_Mn_eV"] == pytest.approx(11.532055666425126, abs=1e-9)
    assert result["U_Mn_eV_interval"] == pytest.approx([11.472088914581676, 11.592022418268577], abs=1e-9)
    assert result["outputs_verified"] == 28
