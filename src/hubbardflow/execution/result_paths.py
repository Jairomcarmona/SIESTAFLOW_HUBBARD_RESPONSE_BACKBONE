"""Canonical paths for campaign result artifacts and legacy reads."""

from __future__ import annotations

from pathlib import Path

_ANALYSIS_NAMES = ("lr_u_analysis.v3.json", "lr_u_analysis.v2.json")


def data_directory(results_directory: Path) -> Path:
    """Return the canonical directory for machine-readable campaign results."""
    return results_directory / "data"


def analysis_output_path(results_directory: Path, schema_version: str) -> Path:
    """Choose the canonical destination for a newly written analysis result."""
    name = (
        "lr_u_analysis.v3.json"
        if schema_version == "siestaflow.lr_u_analysis.v3"
        else "lr_u_analysis.v2.json"
    )
    return data_directory(results_directory) / name


def find_analysis_path(results_directory: Path) -> Path | None:
    """Read new results first and fall back to paths archived by older releases."""
    for name in _ANALYSIS_NAMES:
        for candidate in (data_directory(results_directory) / name, results_directory / name):
            if candidate.is_file():
                return candidate
    return None


def state_gate_output_path(results_directory: Path) -> Path:
    """Return the canonical destination for the state-gate JSON result."""
    return data_directory(results_directory) / "i5_state_gate.json"


def find_state_gate_path(results_directory: Path) -> Path | None:
    """Read the canonical state gate or its legacy archived location."""
    for candidate in (
        state_gate_output_path(results_directory),
        results_directory / "i5_state_gate.json",
    ):
        if candidate.is_file():
            return candidate
    return None
