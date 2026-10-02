"""Strict, portable manifest helpers for WSL and direct Linux LR-U campaigns."""
from __future__ import annotations

import hashlib
import json
import math
import re
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from ..domain.adaptive_alpha_control import AdaptiveAlphaControlError, AdaptiveAlphaPolicy
from ..domain.scientific_profile import (
    ScientificProfileError, profile_from_explicit_functional, require_lr_qualified,
    resolve_scientific_profile, validate_xc_text,
)
from .execution_profile import ExecutionProfile, ProfileValidationError


SCHEMA = "siestaflow.campaign.v2"
CONFIG_SCHEMA = "siestaflow.lr_config.v2"
POINTER_SCHEMA = "siestaflow.windows_campaign_pointer.v1"


class CampaignV2Error(ValueError):
    """A v2 campaign is malformed or its declared inputs do not agree."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_relative(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CampaignV2Error(f"{label} must be a non-empty relative path")
    path = PurePosixPath(value.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts or any(part in {"", "."} for part in path.parts):
        raise CampaignV2Error(f"{label} must be a safe relative path")
    return str(path)


def resolve_fdf_includes(source: Path) -> tuple[str, list[Path]]:
    """Inline nested FDF includes at their original location, rejecting cycles."""
    included: list[Path] = []
    stack: list[Path] = []
    include_re = re.compile(r"^\s*(?:%include|#include)\s+[\"']?([^\"'\s]+)", re.IGNORECASE)

    def expand(path: Path) -> str:
        resolved = path.resolve(strict=True)
        if resolved in stack:
            raise CampaignV2Error(f"FDF include cycle detected at {resolved}")
        if not resolved.is_file():
            raise CampaignV2Error(f"FDF include is not a file: {resolved}")
        stack.append(resolved)
        output: list[str] = []
        for line in resolved.read_text(encoding="utf-8").splitlines():
            match = include_re.match(line)
            if match:
                child = (resolved.parent / match.group(1)).resolve(strict=True)
                included.append(child)
                output.append(expand(child))
            else:
                output.append(line)
        stack.pop()
        return "\n".join(output) + "\n"

    text = expand(source)
    if re.search(r"^\s*(?:%include|#include)\b", text, re.IGNORECASE | re.MULTILINE):
        raise CampaignV2Error("unsupported or unresolved FDF include directive")
    return text, list(dict.fromkeys(included))


def _fdf_block(text: str, name: str) -> list[str]:
    match = re.search(
        rf"^\s*%block\s+{re.escape(name)}\s*$([\s\S]*?)^\s*%endblock(?:\s+{re.escape(name)})?\s*$",
        text, re.IGNORECASE | re.MULTILINE,
    )
    if not match:
        return []
    return [line.split("#", 1)[0].strip() for line in match.group(1).splitlines() if line.split("#", 1)[0].strip()]


def _fdf_values(text: str, name: str) -> list[str]:
    return [
        match.group(1).strip()
        for line in text.splitlines()
        if (match := re.match(rf"^\s*{re.escape(name)}\s+([^\s#]+)", line, re.IGNORECASE))
    ]


def _single_fdf_value(text: str, name: str) -> str | None:
    values = _fdf_values(text, name)
    if len(values) > 1:
        raise CampaignV2Error(f"reference FDF contains ambiguous duplicate definitions of {name}")
    return values[0] if values else None


def _functional_key(value: Any) -> str:
    try:
        return profile_from_explicit_functional(value).xc_functional
    except ScientificProfileError as exc:
        raise CampaignV2Error(str(exc)) from exc


def _check_functional_text(text: str, functional: str, source: str) -> None:
    try:
        validate_xc_text(text, functional, source)
    except ScientificProfileError as exc:
        raise CampaignV2Error(str(exc)) from exc


def validate_reference_fdf(text: str, declared_functional: str) -> tuple[str, dict[str, int], list[str]]:
    """Require explicit declared XC, complete species mapping, and method-2 projectors."""
    functional = _functional_key(declared_functional)
    try:
        require_lr_qualified(profile_from_explicit_functional(functional))
    except ScientificProfileError as exc:
        raise CampaignV2Error(str(exc)) from exc
    fdf_xc = f"{_single_fdf_value(text, 'XC.functional') or ''} {_single_fdf_value(text, 'XC.authors') or ''}"
    _check_functional_text(fdf_xc, functional, "reference FDF")
    atoms = _single_fdf_value(text, "NumberOfAtoms")
    if atoms is None or not atoms.isdigit() or int(atoms) <= 0:
        raise CampaignV2Error("reference FDF must declare a positive NumberOfAtoms")
    species: dict[str, int] = {}
    for row in _fdf_block(text, "ChemicalSpeciesLabel"):
        fields = row.split()
        if len(fields) < 3:
            raise CampaignV2Error("malformed ChemicalSpeciesLabel row")
        try:
            species_index, atomic_number = int(fields[0]), int(fields[1])
        except ValueError as exc:
            raise CampaignV2Error("non-numeric ChemicalSpeciesLabel index/Z") from exc
        label = fields[2]
        if species_index <= 0 or atomic_number <= 0 or label in species:
            raise CampaignV2Error("duplicate or invalid ChemicalSpeciesLabel")
        species[label] = atomic_number
    if not species:
        raise CampaignV2Error("reference FDF lacks a usable ChemicalSpeciesLabel block")
    if _single_fdf_value(text, "DFTU.ProjectorGenerationMethod") != "2":
        raise CampaignV2Error("reference FDF must declare DFTU.ProjectorGenerationMethod 2")
    if (_single_fdf_value(text, "DFTU.PotentialShift") or "").casefold() not in {"true", "t"}:
        raise CampaignV2Error("reference FDF must declare DFTU.PotentialShift true")
    projectors = _fdf_block(text, "DFTU.Proj")
    site_ids: list[str] = []
    if len(projectors) % 4:
        raise CampaignV2Error("DFTU.Proj must contain complete four-line site records")
    for offset in range(0, len(projectors), 4):
        fields = projectors[offset].split()
        if len(fields) != 2 or fields[1] != "1":
            raise CampaignV2Error("DFTU.Proj uses an unsupported or ambiguous site record")
        site_ids.append(fields[0])
        try:
            if float(projectors[offset + 2].split()[0]) != 0.0:
                raise CampaignV2Error("reference DFTU.Proj potential shifts must be zero before LR")
        except (ValueError, IndexError) as exc:
            raise CampaignV2Error("invalid reference DFTU.Proj shift") from exc
    if not site_ids or len(set(site_ids)) != len(site_ids):
        raise CampaignV2Error("DFTU.Proj must declare unique correlated site labels")
    return functional, species, site_ids


def validate_psml(path: Path, expected_label: str, expected_z: int, functional: str) -> None:
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as exc:
        raise CampaignV2Error(f"pseudopotential is not readable PSML: {path}") from exc
    if not root.tag.endswith("psml"):
        raise CampaignV2Error(f"pseudopotential is not PSML: {path}")
    xc_text = " ".join((element.text or "") for element in root.iter() if element.tag.endswith("functional"))
    annotations = " ".join(
        " ".join(str(value) for value in element.attrib.values())
        for element in root.iter() if element.tag.endswith("annotation")
    )
    xc_text = f"{xc_text} {annotations}"
    _check_functional_text(xc_text, functional, f"pseudopotential {path.name}")
    source = next((element for element in root.iter() if element.tag.endswith("input-file")), None)
    if source is None or not source.text:
        raise CampaignV2Error(f"pseudopotential {path.name} lacks its source element/Z declaration")
    source_rows = [line.split() for line in source.text.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    if not source_rows:
        raise CampaignV2Error(f"pseudopotential {path.name} lacks its source element/Z declaration")
    try:
        element, atomic_number = source_rows[0][0], int(source_rows[0][1])
    except (IndexError, ValueError) as exc:
        raise CampaignV2Error(f"pseudopotential {path.name} has an invalid source element/Z declaration") from exc
    # FDF labels may intentionally distinguish inequivalent atoms (for
    # example NiLR0/NiLR1); atomic number is the species identity here.
    if atomic_number != expected_z:
        raise CampaignV2Error(
            f"pseudopotential {path.name} identifies {element}/{atomic_number}, expected Z={expected_z} for {expected_label}"
        )


def validate_lr_config(payload: Mapping[str, Any], fdf_species: Mapping[str, int], projector_sites: list[str], atom_count: int) -> dict[str, Any]:
    if payload.get("schema") != CONFIG_SCHEMA:
        raise CampaignV2Error(f"lr-config schema must be {CONFIG_SCHEMA!r}")
    sites = payload.get("sites")
    if not isinstance(sites, list) or not sites:
        raise CampaignV2Error("lr-config requires a non-empty sites array")
    normalized_sites = []
    seen_ids: set[str] = set()
    seen_indices: set[int] = set()
    for item in sites:
        if not isinstance(item, Mapping):
            raise CampaignV2Error("each site must be an object")
        site_id, atom_index = item.get("site_id"), item.get("atom_index")
        if not isinstance(site_id, str) or not site_id.strip() or site_id in seen_ids:
            raise CampaignV2Error("site_id values must be non-empty and unique")
        if isinstance(atom_index, bool) or not isinstance(atom_index, int) or not 1 <= atom_index <= atom_count or atom_index in seen_indices:
            raise CampaignV2Error("site atom_index values must be unique, 1-based and inside the cell")
        if site_id not in projector_sites:
            raise CampaignV2Error(f"site {site_id} is not declared by DFTU.Proj")
        if site_id not in fdf_species:
            raise CampaignV2Error(f"site {site_id} is absent from ChemicalSpeciesLabel")
        seen_ids.add(site_id); seen_indices.add(atom_index)
        normalized_sites.append({"site_id": site_id, "atom_index": atom_index, "orbit_id": str(item.get("orbit_id", site_id))})
    if seen_ids != set(projector_sites):
        raise CampaignV2Error("lr-config sites must enumerate every DFTU.Proj site exactly once")
    alpha = payload.get("alpha_grid_ev")
    if not isinstance(alpha, list) or not alpha:
        raise CampaignV2Error("alpha_grid_ev must be a non-empty array of non-zero amplitudes")
    values = []
    for value in alpha:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) or float(value) == 0:
            raise CampaignV2Error("alpha_grid_ev values must be finite, non-zero numbers")
        values.append(float(value))
    if len(values) != len(set(values)) or len(values) < 2 or min(values) >= 0 or max(values) <= 0:
        raise CampaignV2Error("alpha_grid_ev must contain distinct negative and positive amplitudes")
    negative, positive = sorted(-v for v in values if v < 0), sorted(v for v in values if v > 0)
    if len(negative) != len(positive) or any(not math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-14) for a, b in zip(negative, positive)):
        raise CampaignV2Error("alpha_grid_ev must be symmetric about zero")
    pseudopotentials = payload.get("pseudopotentials")
    if not isinstance(pseudopotentials, Mapping) or set(pseudopotentials) != set(fdf_species):
        raise CampaignV2Error("pseudopotentials must map every FDF species label to one PSML file")
    for label, source in pseudopotentials.items():
        if not isinstance(source, str) or not Path(source).is_file():
            raise CampaignV2Error(f"pseudopotentials.{label} must name an existing PSML file")
    static = payload.get("static_artifacts", {})
    if not isinstance(static, Mapping):
        raise CampaignV2Error("static_artifacts must be an object")
    normalized_static = {}
    for destination, source in static.items():
        rel = _safe_relative(destination, "static_artifacts destination")
        if not isinstance(source, str) or not Path(source).is_file():
            raise CampaignV2Error(f"static_artifacts.{destination} must name an existing input file")
        normalized_static[rel] = str(Path(source).resolve())
    grid_calibration = payload.get("response_grid_reproducibility_calibration")
    if grid_calibration is not None:
        if not isinstance(grid_calibration, Mapping) or set(grid_calibration) != {
            "lock_static_artifact", "result_static_artifact",
        }:
            raise CampaignV2Error(
                "response_grid_reproducibility_calibration must name lock_static_artifact and result_static_artifact"
            )
        lock_key = grid_calibration["lock_static_artifact"]
        result_key = grid_calibration["result_static_artifact"]
        if (not isinstance(lock_key, str) or not isinstance(result_key, str)
                or lock_key not in normalized_static or result_key not in normalized_static
                or lock_key == result_key):
            raise CampaignV2Error(
                "response-grid calibration lock/result must be distinct entries in static_artifacts"
            )
        grid_calibration = {"lock_static_artifact": lock_key, "result_static_artifact": result_key}
    analysis = payload.get("analysis_policy", {})
    if not isinstance(analysis, Mapping):
        raise CampaignV2Error("analysis_policy must be an object")
    precision_tolerance = analysis.get("u_precision_tolerance_eV")
    if precision_tolerance is not None and (
        isinstance(precision_tolerance, bool)
        or not isinstance(precision_tolerance, (int, float))
        or not math.isfinite(float(precision_tolerance))
        or float(precision_tolerance) <= 0.0
    ):
        raise CampaignV2Error("analysis_policy.u_precision_tolerance_eV must be finite and positive when supplied")
    occupation_precision_requirement = analysis.get("occupation_precision_requirement")
    if occupation_precision_requirement not in {None, "f20.12"}:
        raise CampaignV2Error(
            "analysis_policy.occupation_precision_requirement must be omitted or f20.12"
        )
    alpha_policy = payload.get("alpha_selection_policy")
    if alpha_policy is not None and not isinstance(alpha_policy, Mapping):
        raise CampaignV2Error("alpha_selection_policy must be an object or null")
    adaptive_policy_payload = payload.get("adaptive_alpha_policy")
    adaptive_policy = None
    if adaptive_policy_payload is not None:
        if not isinstance(adaptive_policy_payload, Mapping):
            raise CampaignV2Error("adaptive_alpha_policy must be an object or null")
        try:
            adaptive_policy = AdaptiveAlphaPolicy.from_mapping(adaptive_policy_payload)
        except AdaptiveAlphaControlError as exc:
            raise CampaignV2Error(str(exc)) from exc
        if len(values) != len(adaptive_policy.seed_grid_ev) or any(
            not math.isclose(value, expected, rel_tol=1e-12, abs_tol=1e-14)
            for value, expected in zip(sorted(values), adaptive_policy.seed_grid_ev)
        ):
            raise CampaignV2Error("alpha_grid_ev must match the adaptive policy's symmetric seven-point seed (excluding the shared alpha=0 reference)")
        initial_node_cost = 1 + 2 * len(normalized_sites) * len(values)
        if adaptive_policy.total_siesta_node_budget < initial_node_cost:
            raise CampaignV2Error(
                "total_siesta_node_budget cannot hold the initial grid: one shared reference plus "
                "one BARE and one SCREENED node per site and non-zero alpha"
            )
    compatibility_registry = payload.get("compatibility_registry")
    version_text_source = payload.get("version_text_source")
    if not isinstance(compatibility_registry, str) or not Path(compatibility_registry).is_file():
        raise CampaignV2Error("compatibility_registry must name an existing registry JSON")
    if not isinstance(version_text_source, str) or not Path(version_text_source).is_file():
        raise CampaignV2Error("version_text_source must name an existing SIESTA version text file")
    declared_executable = payload.get("declared_executable")
    if not isinstance(declared_executable, str) or not declared_executable.strip():
        raise CampaignV2Error("declared_executable must match the execution profile SIESTA executable basename")
    magnetic_tolerance = payload.get("magnetic_moment_tolerance_muB")
    if magnetic_tolerance is not None and (
        isinstance(magnetic_tolerance, bool) or not isinstance(magnetic_tolerance, (int, float))
        or not math.isfinite(float(magnetic_tolerance)) or float(magnetic_tolerance) <= 0
    ):
        raise CampaignV2Error("magnetic_moment_tolerance_muB must be finite and positive when supplied")
    try:
        xc_profile = require_lr_qualified(resolve_scientific_profile(
            payload.get("functional"), payload.get("xc_profile"),
        ))
    except ScientificProfileError as exc:
        raise CampaignV2Error(str(exc)) from exc
    return {
        "functional": xc_profile.xc_functional,
        "xc_profile": xc_profile.to_mapping(),
        "sites": normalized_sites,
        "alpha_grid_ev": sorted(values),
        "pseudopotentials": {str(key): str(Path(value).resolve()) for key, value in pseudopotentials.items()},
        "static_artifacts": normalized_static,
        "response_grid_reproducibility_calibration": grid_calibration,
        "analysis_policy": dict(analysis),
        "alpha_selection_policy": None if alpha_policy is None else dict(alpha_policy),
        "adaptive_alpha_policy": None if adaptive_policy is None else adaptive_policy.to_mapping(),
        "reference_dm_name": _safe_relative(payload.get("reference_dm_name", "reference.DM"), "reference_dm_name"),
        "compatibility_registry_source": str(Path(compatibility_registry).resolve()),
        "version_text_source": str(Path(version_text_source).resolve()),
        "declared_executable": declared_executable.strip(),
        "material": str(payload.get("material", "")),
        "observables": payload.get("observables", []),
        "magnetic_moment_tolerance_muB": magnetic_tolerance,
    }


def load_campaign_v2(path: str | Path) -> dict[str, Any]:
    candidate = Path(path).resolve(strict=True)
    try:
        payload = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CampaignV2Error("campaign manifest cannot be read") from exc
    if not isinstance(payload, dict) or payload.get("schema") != SCHEMA:
        raise CampaignV2Error(f"campaign manifest must use schema {SCHEMA!r}")
    if not isinstance(payload.get("campaign_id"), str) or not payload["campaign_id"].strip():
        raise CampaignV2Error("campaign_id is required")
    for field in ("reference_fdf", "contract_file", "lr_config_file", "execution_profile_file"):
        rel = _safe_relative(payload.get(field), field)
        artifact = (candidate.parent / rel).resolve(strict=True)
        try:
            artifact.relative_to(candidate.parent.resolve())
        except ValueError as exc:
            raise CampaignV2Error(f"{field} escapes campaign root") from exc
        if not artifact.is_file():
            raise CampaignV2Error(f"{field} is not a file")
    profile_payload = json.loads((candidate.parent / payload["execution_profile_file"]).read_text(encoding="utf-8"))
    try:
        profile = ExecutionProfile.from_mapping(profile_payload)
    except (ProfileValidationError, TypeError) as exc:
        raise CampaignV2Error(f"execution profile is invalid: {exc}") from exc
    if profile.target == "local_wsl" and profile.wsl is None:
        raise CampaignV2Error("local_wsl campaign requires its WSL execution settings")
    sites = payload.get("sites")
    if not isinstance(sites, list) or not sites:
        raise CampaignV2Error("campaign v2 requires sites")
    for index, site in enumerate(sites):
        if not isinstance(site, dict) or site.get("index") != index or not isinstance(site.get("site_id"), str):
            raise CampaignV2Error("campaign site entries must have stable zero-based indices and site ids")
    if len({site["site_id"] for site in sites}) != len(sites):
        raise CampaignV2Error("campaign site ids must be unique")
    alpha = payload.get("alpha_grid_ev")
    if not isinstance(alpha, list) or not alpha or any(
        isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(float(item)) or float(item) == 0
        for item in alpha
    ):
        raise CampaignV2Error("campaign alpha_grid_ev must contain finite non-zero amplitudes")
    if len(alpha) != len(set(alpha)):
        raise CampaignV2Error("campaign alpha_grid_ev contains duplicate amplitudes")
    adaptive_policy_payload = payload.get("adaptive_alpha_policy")
    adaptive_policy = None
    if adaptive_policy_payload is not None:
        if not isinstance(adaptive_policy_payload, Mapping):
            raise CampaignV2Error("campaign adaptive_alpha_policy must be an object")
        try:
            adaptive_policy = AdaptiveAlphaPolicy.from_mapping(adaptive_policy_payload)
        except AdaptiveAlphaControlError as exc:
            raise CampaignV2Error(str(exc)) from exc
        if len(alpha) != len(adaptive_policy.seed_grid_ev) or any(
            not math.isclose(float(value), expected, rel_tol=1e-12, abs_tol=1e-14)
            for value, expected in zip(sorted(float(value) for value in alpha), adaptive_policy.seed_grid_ev)
        ):
            raise CampaignV2Error("campaign alpha grid does not match its adaptive policy seed")
        if payload.get("automatic_alpha_refinement") is not True:
            raise CampaignV2Error("adaptive policy requires automatic_alpha_refinement=true")
    elif payload.get("automatic_alpha_refinement") is True:
        raise CampaignV2Error("automatic_alpha_refinement requires an explicit versioned adaptive_alpha_policy")
    try:
        xc_profile = require_lr_qualified(resolve_scientific_profile(
            payload.get("functional"), payload.get("xc_profile"),
        ))
    except ScientificProfileError as exc:
        raise CampaignV2Error(str(exc)) from exc
    if payload.get("functional") != xc_profile.xc_functional:
        raise CampaignV2Error("campaign functional must use its canonical declared family name")
    input_files = payload.get("input_files")
    if not isinstance(input_files, list) or not input_files:
        raise CampaignV2Error("campaign v2 requires an input_files identity inventory")
    seen_input_paths: set[str] = set()
    for item in input_files:
        if not isinstance(item, dict):
            raise CampaignV2Error("input_files entries must be objects")
        rel = _safe_relative(item.get("path"), "input_files.path")
        if rel in seen_input_paths:
            raise CampaignV2Error("input_files contains duplicate paths")
        seen_input_paths.add(rel)
        digest = item.get("sha256")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise CampaignV2Error("input_files sha256 must be lowercase SHA-256")
        source = (candidate.parent / rel).resolve(strict=True)
        try:
            source.relative_to(candidate.parent.resolve())
        except ValueError as exc:
            raise CampaignV2Error("input_files path escapes campaign root") from exc
        if not source.is_file():
            raise CampaignV2Error("input_files path is not a file")
    calculated_identity = hashlib.sha256(json.dumps(
        [{"path": item["path"], "sha256": item["sha256"]} for item in sorted(input_files, key=lambda row: row["path"])],
        sort_keys=True, separators=(",", ":"),
    ).encode()).hexdigest()
    if payload.get("input_identity") != calculated_identity:
        raise CampaignV2Error("campaign input identity does not match its declared inventory")
    return {
        **payload, "_manifest_path": str(candidate), "_campaign_root": str(candidate.parent.resolve()),
        "_profile": profile, "_xc_profile": xc_profile.to_mapping(),
        "_adaptive_alpha_policy": adaptive_policy,
    }


def verify_campaign_inventory(campaign: Mapping[str, Any]) -> None:
    """Rehash only the declared campaign inputs once at run/resume startup."""
    root = Path(str(campaign["_campaign_root"])).resolve(strict=True)
    for item in campaign["input_files"]:
        rel = _safe_relative(item["path"], "input_files.path")
        path = (root / rel).resolve(strict=True)
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise CampaignV2Error(f"input file escapes campaign root: {rel}") from exc
        if sha256_file(path) != item["sha256"]:
            raise CampaignV2Error(f"campaign input changed since init: {rel}")


def new_campaign_id() -> str:
    return str(uuid.uuid4())
