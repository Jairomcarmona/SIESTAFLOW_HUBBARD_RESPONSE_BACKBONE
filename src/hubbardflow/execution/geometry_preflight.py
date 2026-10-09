"""Build a record-only geometry diagnostic from the registered reference node."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from hubbardflow.domain.geometry_preflight import (
    GeometryAssessment,
    GeometryPreflightState,
    GeometryThresholdPolicy,
    assess_reference_geometry,
)
from hubbardflow.siesta_backend.fdf_model import FdfModel, parse_effective_fdf
from hubbardflow.siesta_backend.geometry_output_parser import parse_reference_geometry_output


def _json_object(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, Mapping) else {}


def _registered_reference_output(root: Path) -> tuple[Path | None, str | None]:
    """Resolve only the output registered for the canonical REFERENCE node."""
    evidence = _json_object(root / ".siestaflow" / "node-evidence.json")
    nodes = evidence.get("nodes")
    if not isinstance(nodes, Mapping):
        return None, None
    record = nodes.get("reference")
    if not isinstance(record, Mapping) or record.get("kind") != "siesta":
        return None, None
    provenance = record.get("provenance")
    provenance = provenance if isinstance(provenance, Mapping) else {}
    node = provenance.get("node")
    node = node if isinstance(node, Mapping) else {}
    if node.get("node_id") != "reference" or node.get("kind") != "REFERENCE":
        return None, None
    artifact_spec = record.get("artifact_spec")
    artifact_spec = artifact_spec if isinstance(artifact_spec, Mapping) else {}
    output_name = artifact_spec.get("output")
    command = record.get("command")
    command = command if isinstance(command, Mapping) else {}
    cwd_value = command.get("cwd")
    if not isinstance(output_name, str) or not output_name or not isinstance(cwd_value, str) or not cwd_value:
        return None, None
    output_rel = Path(output_name)
    if output_rel.is_absolute() or len(output_rel.parts) != 1 or output_name in {".", ".."}:
        return None, None

    def inside_campaign(path: Path) -> bool:
        try:
            path.resolve().relative_to(root.resolve())
        except (OSError, ValueError):
            return False
        return True

    cwd = Path(cwd_value)
    candidates: list[Path] = []
    if cwd.is_absolute():
        candidates.append(cwd / output_name)
    else:
        candidates.append(root / cwd / output_name)
    direct = next((path for path in candidates if path.is_file() and inside_campaign(path)), None)
    if direct is not None:
        return direct, str(direct)

    # Jobs can record a cluster-absolute working directory while their
    # registered attempt artifacts are staged under this campaign's
    # .siestaflow directory. Rebase only that explicit recorded suffix.
    normalized = cwd_value.replace("\\", "/")
    match = re.search(r"(?:^|/)(\.siestaflow/.*)$", normalized)
    if match is not None:
        local = root / Path(match.group(1)) / output_name
        if local.is_file() and inside_campaign(local):
            return local, str(local)
    return None, str(cwd / output_name)


def _top_level_value(text: str, key: str) -> str | None:
    active_block = False
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if line.casefold().startswith("%block "):
            active_block = True
        elif line.casefold().startswith("%endblock"):
            active_block = False
        elif not active_block:
            match = re.fullmatch(rf"{re.escape(key)}\s+(.+)", line, re.IGNORECASE)
            if match:
                return match.group(1).strip()
    return None


def _model(root: Path, campaign: Mapping[str, Any]) -> FdfModel | None:
    fdf_name = campaign.get("reference_fdf")
    if not isinstance(fdf_name, str) or not fdf_name:
        return None
    try:
        return parse_effective_fdf(root / fdf_name)
    except (OSError, ValueError, TypeError):
        return None


def build_geometry_preflight(
    campaign_root: str | Path,
    campaign: Mapping[str, Any],
    config: Mapping[str, Any],
) -> dict[str, Any]:
    """Return a JSON-ready advisory using only registered reference evidence.

    No perturbation output is searched or inspected. Missing or malformed
    reference evidence is visible as NOT_ASSESSED and has no campaign effect.
    """
    root = Path(campaign_root)
    raw_policy = config.get("geometry_preflight")
    policy = GeometryThresholdPolicy.from_mapping(raw_policy if "geometry_preflight" in config else None)
    model = _model(root, campaign)
    output_path, registered_path = _registered_reference_output(root)
    output_text: str | None = None
    output_sha256: str | None = None
    output_display = registered_path
    if output_path is not None:
        try:
            output_text = output_path.read_text(encoding="utf-8", errors="replace")
            output_sha256 = hashlib.sha256(output_path.read_bytes()).hexdigest()
            try:
                output_display = output_path.resolve().relative_to(root.resolve()).as_posix()
            except (OSError, ValueError):
                output_display = str(output_path)
        except OSError:
            output_text = None

    parsed = parse_reference_geometry_output(output_text) if output_text is not None else None
    unreliable_shift = bool(
        model is not None
        and model.dftu_potential_shift is True
        and any(record.u_ref_ev != 0.0 for record in model.dftu_records)
    )
    if parsed is None:
        assessment = GeometryAssessment(
            state=GeometryPreflightState.NOT_ASSESSED_NO_OUTPUT,
            additional_states=(),
            maximum_force_ev_ang=None,
            residual_ev_ang=None,
            maximum_constrained_force_ev_ang=None,
            stress_voigt_kbar=None,
            mean_pressure_kbar=None,
            maximum_shear_kbar=None,
            constraints_detected=False,
            source_lines=(),
            policy=policy,
        )
    else:
        assessment = assess_reference_geometry(
            maximum_force_ev_ang=parsed.maximum_force_ev_ang,
            residual_ev_ang=parsed.residual_ev_ang,
            maximum_constrained_force_ev_ang=parsed.maximum_constrained_force_ev_ang,
            stress_voigt_kbar=parsed.stress_voigt_kbar,
            source_lines=parsed.source_lines,
            policy=policy,
            unreliable_for_dftu_shift=unreliable_shift,
        )
    records = (
        []
        if model is None
        else [
            {
                "label": record.label,
                "u_ref_ev": record.u_ref_ev,
                "j_ref_ev": record.j_ref_ev,
                "potential_shift": model.dftu_potential_shift,
            }
            for record in model.dftu_records
        ]
    )
    fdf_name = campaign.get("reference_fdf")
    fdf_path = root / str(fdf_name) if isinstance(fdf_name, str) else None
    fdf_sha256 = None
    if fdf_path is not None and fdf_path.is_file():
        fdf_sha256 = hashlib.sha256(fdf_path.read_bytes()).hexdigest()
    return {
        **assessment.to_mapping(),
        "reference_node_id": "reference",
        "reference_output_path": output_display,
        "reference_output_sha256": output_sha256,
        "reference_fdf_path": str(fdf_name) if isinstance(fdf_name, str) else None,
        "reference_fdf_sha256": fdf_sha256,
        "xc_functional": None if model is None else _top_level_value(model.effective_text, "XC.Functional"),
        "xc_authors": None if model is None else _top_level_value(model.effective_text, "XC.Authors"),
        "hubbard_context": records,
        "unreliable_for_dftu_shift": unreliable_shift,
    }
