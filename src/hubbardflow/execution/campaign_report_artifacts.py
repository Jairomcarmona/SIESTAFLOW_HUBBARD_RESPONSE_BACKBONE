"""Persist report inputs and render user-facing campaign artifacts from JSON."""

from __future__ import annotations

import json
import os
import platform
import re
import shlex
import subprocess
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from hubbardflow.domain.projector_diagnostics import METHOD2_PROJECTOR_WARNING
from hubbardflow.execution.campaign_store import atomic_json
from hubbardflow.execution.geometry_preflight import build_geometry_preflight
from hubbardflow.execution.report_csv_exports import export_report_csv
from hubbardflow.reporting.hubbardflow_ascii_report import render_hubbardflow_out
from hubbardflow.siesta_backend.fdf_model import FdfModel, parse_effective_fdf

_SOURCE_NAME = "hubbardflow_report_source.v1.json"


def _read_json(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, Mapping) else {}


def _relative_or_absolute(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except (OSError, ValueError):
        return str(path)


def _commit_identity(root: Path) -> str | None:
    declared = os.environ.get("HUBBARDFLOW_COMMIT") or os.environ.get("GITHUB_SHA")
    if declared:
        return declared
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    commit = result.stdout.strip()
    return commit or None


def _directive(text: str, label: str) -> str | None:
    active_block = False
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if line.casefold().startswith("%block "):
            active_block = True
        elif line.casefold().startswith("%endblock"):
            active_block = False
        elif not active_block:
            match = re.fullmatch(rf"{re.escape(label)}\s+(.+)", line, re.IGNORECASE)
            if match:
                return match.group(1).strip()
    return None


def _projector_record(record: Any) -> dict[str, Any]:
    if not hasattr(record, "canonical_text"):
        return {}
    return {
        "label": record.label,
        "projector_header_value": record.projector_header_value,
        "n": record.n,
        "l": record.l,
        "u_ref_ev": record.u_ref_ev,
        "j_ref_ev": record.j_ref_ev,
        "rc_bohr": record.rc_bohr,
        "omega": record.omega,
        "lambda_values": list(record.lambda_values),
        "canonical_text": record.canonical_text,
    }


def _system_context(
    root: Path,
    campaign: Mapping[str, Any],
    config: Mapping[str, Any],
    input_provenance: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    model: FdfModel | None = None
    fdf_path = root / str(campaign.get("reference_fdf", ""))
    try:
        model = parse_effective_fdf(fdf_path)
    except (OSError, ValueError, TypeError):
        pass

    system: dict[str, Any] = {
        "functional": campaign.get("functional", config.get("functional")),
        "mesh_cutoff": model.mesh_cutoff if model else None,
        "pseudopotentials": {},
    }
    geometry: dict[str, Any] = {}
    basis: dict[str, Any] = {}
    projector: dict[str, Any] = {}
    k_grid: dict[str, Any] = {}
    if model is not None:
        species = [
            {"label": item.label, "atomic_number": item.atomic_number}
            for item in model.chemical_species_labels
        ]
        geometry = {
            "number_of_atoms": model.number_of_atoms,
            "number_of_species": model.number_of_species,
            "species": species,
            "coordinate_format": model.coordinate_format.value,
            "lattice_constant_angstrom": model.lattice_constant_angstrom,
            "lattice_vectors_angstrom": [list(row) for row in model.lattice_vectors_angstrom],
            "summary": (
                f"{model.number_of_atoms} atoms; species "
                + ", ".join(item.label for item in model.chemical_species_labels)
                + "; lattice vectors listed in angstrom"
            ),
        }
        basis = {
            "pao_basis_size": model.pao_basis_size,
            "pao_basis_type": model.pao_basis_type,
            "pao_energy_shift": _directive(model.effective_text, "PAO.EnergyShift"),
            "pao_split_norm": _directive(model.effective_text, "PAO.SplitNorm"),
            "blocks": {label: list(rows) for label, rows in model.pao_basis_blocks},
            "summary": (
                f"PAO.BasisSize={model.pao_basis_size or 'NOT_ASSESSED'}; "
                f"PAO.BasisType={model.pao_basis_type or 'NOT_ASSESSED'}; "
                f"PAO.EnergyShift={_directive(model.effective_text, 'PAO.EnergyShift') or 'NOT_ASSESSED'}; "
                f"PAO.SplitNorm={_directive(model.effective_text, 'PAO.SplitNorm') or 'NOT_ASSESSED'}"
            ),
        }
        k_grid = {
            "block": list(model.kgrid_block),
            "cutoff": model.kgrid_cutoff,
        }
        projector = {
            "method": model.dftu_method,
            "cutoff_norm": _directive(model.effective_text, "DFTU.CutoffNorm"),
            "records": [_projector_record(item) for item in model.dftu_records],
            "warning": METHOD2_PROJECTOR_WARNING.to_mapping(),
        }
    input_pseudos = input_provenance.get("pseudopotentials")
    if isinstance(input_pseudos, Mapping):
        for label, item in sorted(input_pseudos.items()):
            if isinstance(item, Mapping):
                system["pseudopotentials"][str(label)] = {
                    "path": item.get("path"),
                    "sha256": item.get("sha256"),
                }
    config_pseudos = config.get("pseudopotentials")
    if not system["pseudopotentials"] and isinstance(config_pseudos, Mapping):
        for label, raw_path in sorted(config_pseudos.items()):
            path = Path(str(raw_path))
            system["pseudopotentials"][str(label)] = {
                "path": _relative_or_absolute(path, root),
                "sha256": None,
            }
    labels = list(system["pseudopotentials"])
    system["pseudopotential_summary"] = ", ".join(labels) if labels else None
    system["geometry"] = geometry
    system["basis"] = basis
    system["k_grid"] = k_grid
    return system, projector, {"geometry": geometry, "basis": basis, "k_grid": k_grid}


def _context(
    root: Path,
    manifest_path: Path,
    campaign: Mapping[str, Any],
    analysis: Mapping[str, Any],
    runtime: Mapping[str, Any] | None,
) -> dict[str, Any]:
    config = _read_json(root / str(campaign.get("lr_config_file", "")))
    analysis_provenance = analysis.get("provenance")
    analysis_provenance = analysis_provenance if isinstance(analysis_provenance, Mapping) else {}
    input_provenance = analysis_provenance.get("campaign_inputs")
    input_provenance = input_provenance if isinstance(input_provenance, Mapping) else {}
    system, projector, pieces = _system_context(root, campaign, config, input_provenance)
    siesta_inputs = input_provenance.get("siesta_runtime")
    siesta_inputs = siesta_inputs if isinstance(siesta_inputs, Mapping) else {}
    implementation = input_provenance.get("analysis_implementation")
    implementation = implementation if isinstance(implementation, Mapping) else {}
    declared_runtime = runtime if isinstance(runtime, Mapping) else {}
    siesta = {
        "version": declared_runtime.get("version", siesta_inputs.get("version")),
        "binary_sha256": declared_runtime.get("binary_sha256"),
        "bare_profile": declared_runtime.get("bare_profile"),
    }
    protocol_config = analysis.get("estimator_policy") or config.get("analysis_policy")
    protocol_config = protocol_config if isinstance(protocol_config, Mapping) else {}
    campaign_sites = campaign.get("sites")
    sites = campaign_sites if isinstance(campaign_sites, list) else []
    profile_path = root / str(campaign.get("execution_profile_file", ""))
    profile = _read_json(profile_path)
    modules_value = os.environ.get("LOADEDMODULES")
    command = f"hubbardflow run {shlex.quote(str(manifest_path))}"
    return {
        "generated_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "host": platform.node() or None,
        "hubbardflow": {
            "version": implementation.get("package_version"),
            "commit": _commit_identity(root),
        },
        "siesta": siesta,
        "system": system,
        "projector": projector,
        "protocol": {
            "sites": [
                {
                    "index": item.get("index"),
                    "site_id": item.get("site_id"),
                    "atom_index": item.get("atom_index"),
                }
                for item in sites
                if isinstance(item, Mapping)
            ],
            "estimator": dict(protocol_config),
        },
        "reproducibility": {
            "modules": modules_value,
            "command": command,
            "execution_target": profile.get("target"),
            "execution_profile": _relative_or_absolute(profile_path, root),
        },
        "report_parser": {
            "fdf_available": bool(pieces["geometry"]),
            "fdf_path": _relative_or_absolute(root / str(campaign.get("reference_fdf", "")), root),
        },
    }


def _file_map(
    root: Path,
    manifest_path: Path,
    analysis_path: Path,
    analysis: Mapping[str, Any],
) -> dict[str, Any]:
    data = "results/data"
    results_root = root / "results"
    runs_directory = results_root / "runs"
    state_gate_candidates = (
        results_root / "data" / "i5_state_gate.json",
        results_root / "i5_state_gate.json",
    )
    state_gate_path = next((path for path in state_gate_candidates if path.is_file()), None)
    dataset = analysis.get("response_observation_dataset")
    dataset = dataset if isinstance(dataset, Mapping) else {}
    runs: set[str] = set()
    reference = dataset.get("reference_source")
    if isinstance(reference, Mapping) and reference.get("out_path"):
        runs.add(str(Path(str(reference["out_path"])).parent.as_posix()))
    rows = dataset.get("rows")
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            sources = row.get("sources")
            if not isinstance(sources, Mapping):
                continue
            for item in sources.values():
                if isinstance(item, Mapping) and item.get("out_path"):
                    runs.add(str(Path(str(item["out_path"])).parent.as_posix()))
    return {
        "campaign_manifest": _relative_or_absolute(manifest_path, root),
        "analysis_json": _relative_or_absolute(analysis_path, root) if analysis_path.is_file() else None,
        "report_source_json": f"{data}/{_SOURCE_NAME}",
        "occupation_provenance_json": f"{data}/occupation_provenance.v1.json",
        "state_gate_json": _relative_or_absolute(state_gate_path, root) if state_gate_path else None,
        "runs_directory": _relative_or_absolute(runs_directory, root) if runs_directory.is_dir() else None,
        "report": "results/HUBBARDFLOW.out",
        "u_by_site_csv": f"{data}/u_by_site.csv",
        "chi0_matrix_csv": f"{data}/chi0_matrix.csv",
        "chi_matrix_csv": f"{data}/chi_matrix.csv",
        "original_run_folders": sorted(runs) if runs else ["NOT_ASSESSED"],
    }


def _quality_checks(analysis: Mapping[str, Any]) -> dict[str, Any]:
    primary = analysis.get("primary")
    primary = primary if isinstance(primary, Mapping) else {}
    dataset = analysis.get("response_observation_dataset")
    dataset = dataset if isinstance(dataset, Mapping) else {}
    reference = dataset.get("reference_reproduction")
    reference = reference if isinstance(reference, Mapping) else {}
    diagnostics = analysis.get("scf_and_magnetic_diagnostics")
    diagnostics = diagnostics if isinstance(diagnostics, Mapping) else {}
    fit_rows = primary.get("fit_diagnostics")
    residuals = (
        [
            float(row["primary"]["max_abs_residual"])
            for row in fit_rows
            if isinstance(row, Mapping)
            and isinstance(row.get("primary"), Mapping)
            and isinstance(row["primary"].get("max_abs_residual"), (int, float))
        ]
        if isinstance(fit_rows, list)
        else []
    )
    chi0 = primary.get("chi0_diagnostics")
    chi0 = chi0 if isinstance(chi0, Mapping) else {}
    chi = primary.get("chi_diagnostics")
    chi = chi if isinstance(chi, Mapping) else {}
    return {
        "linearity": {
            "value": max(residuals) if residuals else None,
            "units": "electron",
            "status": "RECORDED_ONLY" if residuals else "NOT_ASSESSED",
        },
        "chi0_rank_condition": {
            "value": {"rank": chi0.get("rank"), "condition_number": chi0.get("condition_number")},
            "status": chi0.get("matrix_status", "NOT_ASSESSED"),
        },
        "chi_rank_condition": {
            "value": {"rank": chi.get("rank"), "condition_number": chi.get("condition_number")},
            "status": chi.get("matrix_status", "NOT_ASSESSED"),
        },
        "common_parent_state": {
            "value": reference.get("occupation_equivalence"),
            "status": reference.get("occupation_equivalence", "NOT_ASSESSED"),
        },
        "charge_conservation": {"value": None, "status": "NOT_ASSESSED"},
        "intra_orbit_symmetry_dispersion": {"value": None, "status": "NOT_ASSESSED"},
        "scf_convergence": {
            "value": diagnostics.get("scf_validated"),
            "status": "RECORDED_ONLY" if diagnostics.get("scf_validated") is not None else "NOT_ASSESSED",
        },
        "magnetic_moment_consistency": {
            "value": diagnostics.get("state_continuity_confirmed"),
            "status": "RECORDED_ONLY"
            if diagnostics.get("state_continuity_confirmed") is not None
            else "NOT_ASSESSED",
        },
    }


def write_campaign_report_artifacts(
    *,
    campaign_root: str | Path,
    manifest_path: str | Path,
    campaign: Mapping[str, Any],
    analysis_path: str | Path,
    analysis: Mapping[str, Any],
    state_gate: Mapping[str, Any] | None,
    occupation_provenance_path: str | Path,
    runtime: Mapping[str, Any] | None = None,
    traceability_warnings: list[Any] | None = None,
    workflow_state: Mapping[str, Any] | None = None,
) -> str:
    """Save one JSON source, then render the text report and matrix CSV exports."""
    root = Path(campaign_root)
    manifest = Path(manifest_path)
    analysis_file = Path(analysis_path)
    (root / "results" / "runs").mkdir(parents=True, exist_ok=True)
    data_dir = root / "results" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    source_path = data_dir / _SOURCE_NAME
    previous_source = _read_json(source_path)
    previous_context = previous_source.get("context")
    context = (
        dict(previous_context)
        if runtime is None and isinstance(previous_context, Mapping)
        else _context(root, manifest, campaign, analysis, runtime)
    )
    saved_warnings = previous_source.get("traceability_warnings")
    warnings = (
        saved_warnings
        if traceability_warnings is None and isinstance(saved_warnings, list)
        else list(traceability_warnings or [])
    )
    source: dict[str, Any] = {
        "schema_version": "hubbardflow.report_source.v1",
        "analysis": dict(analysis),
        "context": context,
        "state_gate": dict(state_gate) if isinstance(state_gate, Mapping) else None,
        "occupation_provenance": dict(_read_json(Path(occupation_provenance_path))),
        "traceability_warnings": warnings,
        "campaign_state": dict(workflow_state) if isinstance(workflow_state, Mapping) else None,
        "quality_checks": _quality_checks(analysis),
        "geometry_preflight": build_geometry_preflight(
            root, campaign, _read_json(root / str(campaign.get("lr_config_file", "")))
        ),
        "not_assessed_or_not_claimed": [
            "Cell-size, vacuum, and k-grid sensitivity: NOT_ASSESSED unless measured separately.",
            "This is not a self-consistent DFT+U result.",
            "This is not a structure relaxed with the reported U.",
        ],
        "file_map": _file_map(root, manifest, analysis_file, analysis),
    }
    atomic_json(source_path, source)
    saved_source = _read_json(source_path)
    report = render_hubbardflow_out(saved_source)
    report_path = root / "results" / "HUBBARDFLOW.out"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="ascii", newline="\n")
    export_report_csv(saved_source, data_dir)
    return report


def read_report_source(path: str | Path) -> Mapping[str, Any]:
    """Read the saved presentation JSON; invalid/missing input yields an empty mapping."""
    return _read_json(Path(path))
