"""Initialize a fixed-grid v2 campaign from explicit inputs.

The only files copied are declared scientific inputs and profile metadata.
The resulting manifest records their hashes once; the worker rechecks that
inventory once when ``run``/``resume`` starts.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from .campaign_v2 import (
    CampaignV2Error, CONFIG_SCHEMA, POINTER_SCHEMA, SCHEMA, _safe_relative,
    new_campaign_id, resolve_fdf_includes, sha256_file,
    validate_lr_config, validate_psml, validate_reference_fdf,
)
from .execution_profile import ExecutionProfile, ProfileValidationError
from .campaign_plan import campaign_inventory, freeze_campaign_plan, resolve_campaign_planning


def _source_file(value: Any, base: Path, label: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise CampaignV2Error(f"{label} must name an input file")
    raw = value.strip()
    candidate = Path(raw)
    if candidate.is_absolute() and candidate.is_file():
        return candidate.resolve(strict=True)
    if not candidate.is_absolute() and (base / candidate).is_file():
        return (base / candidate).resolve(strict=True)
    # WSL can resolve drive-letter input paths through its configured mounts.
    try:
        converted = subprocess.run(
            ["wslpath", "-u", raw], capture_output=True, text=True, check=False, shell=False,
        )
    except OSError as exc:
        raise CampaignV2Error(f"cannot resolve {label}: {raw}") from exc
    if converted.returncode == 0:
        result = Path(converted.stdout.strip())
        if result.is_file():
            return result.resolve(strict=True)
    raise CampaignV2Error(f"{label} is not a readable file: {raw}")


def _copy(source: Path, root: Path, relative: str) -> Path:
    rel = PurePosixPath(_safe_relative(relative, "campaign input destination"))
    target = root.joinpath(*rel.parts)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return target


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def initialize_campaign(
    *, fdf_path: str, lr_config_path: str, profile_path: str,
    name: str, pointer_path: str | None = None, campaign_root: str | None = None,
) -> dict[str, Any]:
    """Create a manifest directly, plus the legacy pointer when target is WSL."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", name):
        raise CampaignV2Error("campaign name must be one safe path component (letters, digits, . _ -)")
    input_fdf = Path(fdf_path).resolve(strict=True)
    input_config = Path(lr_config_path).resolve(strict=True)
    input_profile = Path(profile_path).resolve(strict=True)
    try:
        profile_payload = json.loads(input_profile.read_text(encoding="utf-8"))
        raw_config = json.loads(input_config.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CampaignV2Error("lr-config/profile JSON cannot be read") from exc
    if not isinstance(raw_config, dict) or raw_config.get("schema") != CONFIG_SCHEMA:
        raise CampaignV2Error(f"lr-config must use schema {CONFIG_SCHEMA!r}")
    try:
        profile = ExecutionProfile.from_mapping(profile_payload)
    except (ProfileValidationError, TypeError) as exc:
        raise CampaignV2Error(f"execution profile is invalid: {exc}") from exc
    if profile.target == "local_wsl" and profile.wsl is None:
        raise CampaignV2Error("local_wsl init requires WSL execution settings")
    profile.require_submission_evidence()
    if profile.target == "local_wsl" and profile.runtime.module_commands:
        raise CampaignV2Error("local_wsl profile cannot depend on interactive module commands")
    requested_ranks = profile.runtime.launcher.processes_per_node
    visible_cpus = len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else os.cpu_count()
    if profile.target == "local_wsl" and visible_cpus is not None and requested_ranks > visible_cpus:
        raise CampaignV2Error(
            f"profile requests {requested_ranks} MPI ranks, but this runtime exposes only {visible_cpus} CPUs"
        )

    if profile.target == "local_wsl":
        assert profile.wsl is not None
        workspace = Path(profile.wsl.workspace_root)
    else:
        workspace = Path(campaign_root).resolve() if campaign_root else Path.cwd().resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    root = workspace / name
    try:
        root.mkdir()
    except FileExistsError as exc:
        raise CampaignV2Error(f"campaign directory already exists: {root}") from exc
    try:
        fdf_text, fdf_includes = resolve_fdf_includes(input_fdf)
        functional, fdf_species, projector_sites = validate_reference_fdf(fdf_text, raw_config.get("functional"))
        atoms_value = re.search(r"^\s*NumberOfAtoms\s+(\d+)\s*$", fdf_text, re.IGNORECASE | re.MULTILINE)
        if atoms_value is None:
            raise CampaignV2Error("reference FDF must declare NumberOfAtoms")
        atom_count = int(atoms_value.group(1))

        config_base = input_config.parent
        declared_sources: dict[str, Path] = {}
        for label, value in raw_config.get("pseudopotentials", {}).items():
            if not isinstance(label, str) or not re.fullmatch(r"[A-Za-z0-9_.+-]+", label):
                raise CampaignV2Error(f"unsafe pseudopotential species label: {label!r}")
            declared_sources[f"pseudopotentials.{label}"] = _source_file(value, config_base, f"pseudopotentials.{label}")
        registry_source = _source_file(raw_config.get("compatibility_registry"), config_base, "compatibility_registry")
        version_source = _source_file(raw_config.get("version_text_source"), config_base, "version_text_source")
        static_sources: dict[str, Path] = {}
        static_raw = raw_config.get("static_artifacts", {})
        if not isinstance(static_raw, Mapping):
            raise CampaignV2Error("static_artifacts must be an object")
        for destination, source in static_raw.items():
            relative = _safe_relative(destination, "static_artifacts destination")
            if relative in {f"{label}.psml" for label in fdf_species}:
                raise CampaignV2Error(f"static_artifacts destination collides with pseudopotential {relative}")
            static_sources[relative] = _source_file(source, config_base, f"static_artifacts.{destination}")

        # D6 admits opt-in staging only. This manifest cannot be loaded by the
        # production campaign runner and carries no executable plan or DAG.
        from .campaign_split import stage_campaign_split
        from hubbardflow.siesta_backend.semantic_split_models import SemanticSpeciesSplitError
        pending_config = {
            **raw_config,
            "pseudopotentials": {key.split(".", 1)[1]: str(source) for key, source in declared_sources.items()},
            "static_artifacts": {key: str(source) for key, source in static_sources.items()},
        }
        try:
            staged = stage_campaign_split(input_fdf, pending_config, root)
        except SemanticSpeciesSplitError as exc:
            raise CampaignV2Error(str(exc)) from exc
        if staged is not None:
            return {
                "status": staged.status.value,
                "staging_manifest_path": str(root / "species_split/species_split_staging.json"),
                "staging_digest": staged.digest,
                "auto_split_species": True,
            }

        # Copy the source inventory into Linux ext4; the response factory then
        # stages only the referenced assets into each node's private directory.
        reference_path = root / "reference.fdf"
        reference_path.write_text(fdf_text, encoding="utf-8", newline="\n")
        original_fdf_relative = "provenance/source_reference.fdf"
        copied_sources: list[tuple[str, Path]] = [(original_fdf_relative, _copy(input_fdf, root, original_fdf_relative))]
        for index, source in enumerate(fdf_includes):
            rel = f"provenance/fdf_includes/{index:03d}_{source.name}"
            copied_sources.append((rel, _copy(source, root, rel)))

        config_payload = dict(raw_config)
        for field in ("planning_reference_output", "planning_reference_dm"):
            if raw_config.get(field) is not None:
                config_payload[field] = str(_source_file(raw_config[field], config_base, field))
        normalized_pseudopotentials: dict[str, str] = {}
        static_node_paths: dict[str, str] = {}
        all_inputs: dict[str, Path] = {"reference.fdf": reference_path}
        all_inputs[original_fdf_relative] = root / original_fdf_relative
        for index, source in enumerate(fdf_includes):
            all_inputs[f"provenance/fdf_includes/{index:03d}_{source.name}"] = root / f"provenance/fdf_includes/{index:03d}_{source.name}"
        for key, source in declared_sources.items():
            label = key.split(".", 1)[1]
            rel = f"pseudopotentials/{label}.psml"
            target = _copy(source, root, rel)
            normalized_pseudopotentials[label] = str(target)
            all_inputs[rel] = target
            validate_psml(target, label, fdf_species[label], functional)
        for destination, source in static_sources.items():
            target = _copy(source, root, f"static/{destination}")
            static_node_paths[destination] = str(target)
            all_inputs[f"static/{destination}"] = target
        registry_target = _copy(registry_source, root, "software/backend_compatibility.json")
        version_target = _copy(version_source, root, "software/siesta_version.txt")
        all_inputs["software/backend_compatibility.json"] = registry_target
        all_inputs["software/siesta_version.txt"] = version_target
        source_config_target = _copy(input_config, root, "provenance/source_lr_config.json")
        all_inputs["provenance/source_lr_config.json"] = source_config_target
        profile_target = _copy(input_profile, root, "execution_profile.json")
        all_inputs["execution_profile.json"] = profile_target

        config_payload.update({
            "functional": functional,
            "pseudopotentials": normalized_pseudopotentials,
            "static_artifacts": static_node_paths,
            "compatibility_registry": str(registry_target),
            "version_text_source": str(version_target),
        })
        inventory = campaign_inventory(reference_path, (root / "pseudopotentials",))
        normalized = validate_lr_config(config_payload, fdf_species, projector_sites, atom_count, inventory=inventory)
        if normalized["functional"] != functional:
            raise CampaignV2Error("lr-config and reference FDF functionals differ")
        if normalized["alpha_selection_policy"] is not None:
            raise CampaignV2Error(
                "legacy alpha_selection_policy is not an adaptive campaign contract; "
                "use the versioned adaptive_alpha_policy object"
            )
        adaptive_policy = normalized["adaptive_alpha_policy"]
        if Path(profile.runtime.siesta_executable).name != Path(normalized["declared_executable"]).name:
            raise CampaignV2Error("declared_executable does not match the execution profile executable basename")
        policy = dict(normalized["analysis_policy"])
        allowed_policy = {
            "estimator", "polynomial_degree", "minimum_residual_dof", "matrix_for_inversion",
            "sensitivity_tolerance_eV", "u_precision_tolerance_eV",
        }
        if set(policy) - allowed_policy:
            raise CampaignV2Error(f"unsupported analysis_policy fields: {sorted(set(policy) - allowed_policy)}")
        alpha_grid = normalized["alpha_grid_ev"]
        tolerance = raw_config.get("magnetic_moment_tolerance_muB")
        if tolerance is not None and (
            isinstance(tolerance, bool) or not isinstance(tolerance, (int, float))
            or not math.isfinite(float(tolerance)) or float(tolerance) <= 0
        ):
            raise CampaignV2Error("magnetic_moment_tolerance_muB must be finite and positive when supplied")
        contract = {
            "schema": "lr_bare_campaign_contract_v1",
            "campaign_id": new_campaign_id(),
            "backend_id": "siesta",
            "scientific_profile": {
                "profile_id": "siesta-5.4.2-potential-shift-hamiltonian-v1", "version": "1",
            },
            "compatibility_registry": "software/backend_compatibility.json",
            "declared_executable": normalized["declared_executable"],
            "version_text_source": "software/siesta_version.txt",
        }
        contract_path = root / "backend_contract.json"
        _write_json(contract_path, contract)
        all_inputs["backend_contract.json"] = contract_path
        lr_config = {
            **config_payload,
            "schema": CONFIG_SCHEMA,
            "functional": functional,
            "xc_profile": normalized["xc_profile"],
            "sites": normalized["sites"],
            "alpha_grid_ev": alpha_grid,
            "pseudopotentials": normalized_pseudopotentials,
            "static_artifacts": static_node_paths,
            "analysis_policy": policy,
            "adaptive_alpha_policy": adaptive_policy,
            "reference_dm_name": normalized["reference_dm_name"],
            "compatibility_registry": str(registry_target),
            "version_text_source": str(version_target),
            "declared_executable": normalized["declared_executable"],
            "magnetic_moment_tolerance_muB": tolerance,
            "coverage": normalized["coverage"],
            "coverage_policy": normalized["coverage_policy"],
            "alpha_strategy": normalized["alpha_strategy"],
            "auto_split_species": normalized["auto_split_species"],
        }
        for field in ("planning_reference_output", "planning_reference_dm"):
            if raw_config.get(field) is not None:
                source = _source_file(raw_config[field], config_base, field)
                rel = f"planning/{field}"
                target = _copy(source, root, rel)
                all_inputs[rel] = target
                lr_config[field] = str(target)
        if "parent_reproduction" in normalized:
            lr_config["parent_reproduction"] = normalized["parent_reproduction"]
        normalized = validate_lr_config(lr_config, fdf_species, projector_sites, atom_count, inventory=inventory)
        planning = resolve_campaign_planning(reference_path, normalized)
        resolved_plan = planning.plan
        freeze_campaign_plan(root, planning, normalized)
        all_inputs["resolved_perturbation_plan.json"] = root / "resolved_perturbation_plan.json"
        all_inputs["campaign.lock"] = root / "campaign.lock"
        config_target = root / "lr_config.json"
        _write_json(config_target, lr_config)
        all_inputs["lr_config.json"] = config_target

        # Match site matrix order to the explicit DFTU.Proj order.
        by_id = {item["site_id"]: item for item in normalized["sites"]}
        ordered_sites = [
            {"index": index, **by_id[site_id]}
            for index, site_id in enumerate(projector_sites)
        ]
        input_files = [
            {"path": rel, "sha256": sha256_file(file_path)}
            for rel, file_path in sorted(all_inputs.items())
        ]
        identity = hashlib.sha256(json.dumps(
            input_files, sort_keys=True, separators=(",", ":"),
        ).encode()).hexdigest()
        manifest = {
            "schema": SCHEMA,
            "campaign_id": contract["campaign_id"],
            "name": name,
            "material": normalized["material"],
            "functional": functional,
            "xc_profile": normalized["xc_profile"],
            "reference_fdf": "reference.fdf",
            "resolved_perturbation_plan_file": "resolved_perturbation_plan.json",
            "resolved_perturbation_plan_digest": resolved_plan.digest,
            "campaign_lock_file": "campaign.lock",
            "coverage": normalized["coverage"],
            "contract_file": "backend_contract.json",
            "lr_config_file": "lr_config.json",
            "execution_profile_file": "execution_profile.json",
            "sites": ordered_sites,
            "alpha_grid_ev": alpha_grid,
            "analysis_policy": policy,
            "adaptive_alpha_policy": adaptive_policy,
            "alpha_selection_policy": None,
            "fixed_grid": adaptive_policy is None,
            "automatic_alpha_refinement": adaptive_policy is not None,
            "magnetic_moment_tolerance_muB": tolerance,
            "observables": normalized["observables"],
            "input_files": input_files,
            "input_identity": identity,
        }
        manifest_path = root / "campaign.v2.json"
        _write_json(manifest_path, manifest)
        result = {"campaign_id": contract["campaign_id"], "manifest_path": str(manifest_path)}
        if profile.target == "local_wsl":
            assert profile.wsl is not None
            if pointer_path is None:
                raise CampaignV2Error("local_wsl init requires a pointer path")
            pointer = {
                "schema": POINTER_SCHEMA,
                "campaign_id": contract["campaign_id"],
                "campaign_name": name,
                "distribution": profile.wsl.distribution,
                "python_executable": profile.wsl.python_executable,
                "manifest_path": str(manifest_path),
            }
            pointer_target = Path(pointer_path)
            pointer_target.parent.mkdir(parents=True, exist_ok=True)
            _write_json(pointer_target, pointer)
            result["pointer_path"] = str(pointer_target)
        return result
    except Exception:
        # A rejected init must not leave a half-created campaign that looks ready.
        shutil.rmtree(root, ignore_errors=True)
        raise


# Backward-compatible private WSL worker entrypoint.
initialize_wsl_campaign = initialize_campaign

__all__ = ["initialize_campaign", "initialize_wsl_campaign"]
