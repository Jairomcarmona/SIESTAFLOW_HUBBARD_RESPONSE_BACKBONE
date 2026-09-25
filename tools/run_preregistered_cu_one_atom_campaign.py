#!/usr/bin/env python3
"""Verify and bind the predeclared Cu one-atom noise-calibrated LR campaign.

This command deliberately has no mode that invents a noise value or changes a
response mesh.  ``bind-calibration`` accepts only the five independently
collected zero-shift control receipts; ``verify`` proves that the package and
any bound result can be admitted before Slurm response submission.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from hashlib import sha256
import json
from math import isclose
from pathlib import Path
import re
import shlex
import subprocess
import sys
from typing import Any

from siestaflow_hubbard.domain.occupation_noise_calibration import (
    OccupationNoiseCalibrationPolicy,
    derive_occupation_noise,
    load_strict_json,
    validate_calibration_result,
)
from siestaflow_hubbard.siesta_backend.event_parser import parse_hubbard_population_events
from siestaflow_hubbard.siesta_backend.output_validator import (
    SiestaOutputValidationError,
    _normal_and_converged,
)
from siestaflow_hubbard.siesta_backend.siesta542_bare_profile import Siesta542PotentialShiftHamiltonianProfile
from siestaflow_hubbard.siesta_backend.symmetry_materializer import _replace_key, _rewrite_projector_shifts


ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN = ROOT / "campaigns" / "cu_one_atom_noise_calibrated_lr_v1"
SOFTWARE_LOCK = "locks/software-lock.json"


def _load(relative: str) -> dict[str, Any]:
    return json.loads((CAMPAIGN / relative).read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _safe_relative(value: Any, label: str) -> str:
    _require(isinstance(value, str) and value and not Path(value).is_absolute(), f"{label} must be relative")
    _require(all(part not in {"", ".", ".."} for part in Path(value).parts), f"{label} escapes campaign")
    return value


def _load_strict(relative: str) -> dict[str, Any]:
    return load_strict_json(CAMPAIGN / relative)


def _validate_json_schema(value: dict[str, Any], schema_path: Path, label: str) -> None:
    """Validate locked JSON with the declared Draft 2020-12 schema."""
    try:
        from jsonschema import Draft202012Validator
        schema = load_strict_json(schema_path)
        Draft202012Validator.check_schema(schema)
        errors = sorted(Draft202012Validator(schema).iter_errors(value), key=lambda item: list(item.path))
    except ImportError as exc:
        raise ValueError("jsonschema is required to verify the preregistered campaign") from exc
    if errors:
        location = ".".join(str(part) for part in errors[0].path) or "<root>"
        raise ValueError(f"{label} violates its JSON schema at {location}: {errors[0].message}")


def _inside(path: Path, parent: Path, label: str) -> Path:
    resolved, root = path.resolve(), parent.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"{label} escapes its replica evidence directory") from exc
    _require(resolved.is_file(), f"{label} is missing")
    return resolved


def _dumped_fdf(output_text: str) -> str:
    start = "************************** Dump of input data file ****************************"
    end = "************************** End of input data file *****************************"
    _require(output_text.count(start) == 1 and output_text.count(end) == 1, "native output has ambiguous input dump")
    return output_text.split(start, 1)[1].split(end, 1)[0].strip() + "\n"


def _assert_zero_shift_native_output(output_text: str, node_id: str) -> str:
    """Bind each control to a native, normally completed alpha-zero input dump."""
    is_bare = node_id == "response:BARE_zero"
    try:
        _normal_and_converged(
            output_text,
            require_convergence=not is_bare,
            allow_bare_scf_marker=is_bare,
        )
    except SiestaOutputValidationError as exc:
        raise ValueError(f"calibration output failed canonical completion validation: {exc}") from exc
    fdf_text = _dumped_fdf(output_text)
    block = re.search(r"%block\s+DFTU\.Proj\s*(.*?)%endblock\s+DFTU\.Proj", fdf_text, re.I | re.S)
    _require(block is not None, "native output lacks DFTU.Proj input evidence")
    lines = [line.split("#", 1)[0].strip() for line in block.group(1).splitlines()
             if line.split("#", 1)[0].strip()]
    _require(len(lines) >= 4, "native DFTU.Proj block is incomplete")
    try:
        alpha = float(lines[2].split()[0])
    except (IndexError, ValueError) as exc:
        raise ValueError("native DFTU.Proj shift is not numeric") from exc
    _require(alpha == 0.0, "calibration native output is not an alpha-zero control")
    _require(re.search(r"^\s*DFTU\.PotentialShift\s+(?:true|t|yes)\s*$", fdf_text, re.I | re.M) is not None,
             "calibration native output lacks PotentialShift=true")
    if is_bare:
        Siesta542PotentialShiftHamiltonianProfile().validate_fdf(fdf_text)
    return fdf_text


def _canonical_fdf(text: str) -> list[str]:
    return [line.rstrip() for line in text.replace("\r\n", "\n").splitlines() if line.strip()]


def _expected_zero_control_fdf(node_id: str, reference_text: str) -> str:
    """Recreate the only two authorized alpha-zero child materializations."""
    _require(node_id in {"response:BARE_zero", "response:SCREENED_zero"},
             "unknown zero-control node")
    mode = "BARE" if "BARE" in node_id else "SCREENED"
    content = _rewrite_projector_shifts(reference_text, "Cu1", 0.0)
    content = _replace_key(content, "SystemLabel", f"{mode}_zero")
    content = _replace_key(content, "DFTU.FirstIteration", "true")
    content = _replace_key(content, "DM.UseSaveDM", "true")
    if mode == "BARE":
        return Siesta542PotentialShiftHamiltonianProfile().materialize(content)
    for key, value in {
        "MaxSCFIterations": "300", "SCF.MustConverge": "T", "SCF.Mix": "Hamiltonian",
        "SCF.Mixer.Method": "Pulay", "SCF.Mixer.Weight": "0.05", "SCF.Mixer.History": "8",
        "SCF.DM.Converge": "T", "SCF.H.Converge": "T", "SCF.DM.Tolerance": "1.0e-5",
        "SCF.H.Tolerance": "1.0e-4 eV",
    }.items():
        content = _replace_key(content, key, value)
    return content


def _verify_locks() -> dict[str, Any]:
    """Verify the manifest of every immutable campaign input before admission."""
    lock_manifest = CAMPAIGN / "LOCKS.sha256"
    _require(lock_manifest.is_file(), "LOCKS.sha256 is missing")
    entries: dict[str, str] = {}
    for line in lock_manifest.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        _require(match is not None, "LOCKS.sha256 has malformed line")
        digest, relative = match.groups()
        relative = _safe_relative(relative.replace("\\\\", "/"), "LOCKS entry")
        _require(relative not in entries, "LOCKS.sha256 has duplicate path")
        _require((CAMPAIGN / relative).is_file(), f"locked file is missing: {relative}")
        _require(_sha256(CAMPAIGN / relative) == digest, f"preregistration hash mismatch: {relative}")
        entries[relative] = digest
    required = {
        "campaign-manifest.json", "inputs/reference.fdf", "locks/calibration-methodology-lock.json",
        "locks/response-methodology-lock.json", SOFTWARE_LOCK, "plans/calibration-plan.json",
        "plans/response-plan.json",
    }
    _require(required.issubset(entries), "LOCKS.sha256 omits a required immutable campaign input")
    software = _load_strict(SOFTWARE_LOCK)
    _require(set(software) == {"schema", "campaign_id", "wheel", "files"}, "software lock has unexpected fields")
    _require(software["schema"] == "siestaflow-campaign-software-lock-v1", "unknown software lock schema")
    _require(software["campaign_id"] == _load_strict("campaign-manifest.json")["campaign_id"], "software lock campaign id mismatch")
    wheel = software["wheel"]
    _require(isinstance(wheel, dict) and set(wheel) == {"path", "sha256", "distribution", "version"}, "software wheel lock malformed")
    wheel_path = _safe_relative(wheel["path"], "software wheel")
    _require(_is_sha256(wheel["sha256"]) and _sha256(CAMPAIGN / wheel_path) == wheel["sha256"], "software wheel hash mismatch")
    _require(wheel_path in entries and entries[wheel_path] == wheel["sha256"], "software wheel is not protected by LOCKS.sha256")
    files = software["files"]
    _require(isinstance(files, dict) and files, "software lock file inventory is empty")
    # Software is fixed at the repository release, while tests may copy only
    # the campaign data to exercise a fresh evidence directory.
    project_root = ROOT
    for relative, digest in files.items():
        relative = _safe_relative(relative, "software lock file")
        _require(_is_sha256(digest) and (project_root / relative).is_file(), "software lock file is malformed")
        _require(_sha256(project_root / relative) == digest, f"software hash mismatch: {relative}")
    required_software = {
        "tools/run_preregistered_cu_one_atom_campaign.py", "tools/run_cu_noise_calibration_replica.py",
        "tools/run_siesta542_openmpi_slurm_full_campaign.py",
        "src/siestaflow_hubbard/domain/occupation_noise_calibration.py",
        "src/siestaflow_hubbard/execution/campaign_software_lock.py",
        "src/siestaflow_hubbard/siesta_backend/output_validator.py",
        "schemas/campaign/occupation_noise_calibration_lock.schema.json",
        "schemas/campaign/occupation_noise_calibration_result.schema.json",
        "campaigns/cu_one_atom_noise_calibrated_lr_v1/inputs/reference.fdf",
        "examples/tmo_campaigns/Cu1.psml",
        "campaigns/cu_one_atom_noise_calibrated_lr_v1/locks/calibration-methodology-lock.json",
        "campaigns/cu_one_atom_noise_calibrated_lr_v1/locks/response-methodology-lock.json",
        "pyproject.toml",
    }
    _require(required_software.issubset(files), "software lock omits a required runner, module, schema, or physical input")
    return software


def _numeric_noise_keys(value: Any, path: str = "") -> list[str]:
    """Find illicit numeric occupation_noise declarations in response material."""
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{path}.{key}" if path else key
            if key == "occupation_noise" and isinstance(item, (int, float)) and not isinstance(item, bool):
                found.append(child)
            found.extend(_numeric_noise_keys(item, child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(_numeric_noise_keys(item, f"{path}[{index}]"))
    return found


def verify_package(*, require_result: bool) -> dict[str, Any]:
    software = _verify_locks()
    manifest = _load_strict("campaign-manifest.json")
    calibration = _load_strict("locks/calibration-methodology-lock.json")
    response = _load_strict("locks/response-methodology-lock.json")
    calibration_plan = _load_strict("plans/calibration-plan.json")
    response_plan = _load_strict("plans/response-plan.json")
    _validate_json_schema(calibration, ROOT / "schemas/campaign/occupation_noise_calibration_lock.schema.json",
                          "calibration methodology lock")
    _require(manifest["campaign_id"] == response["campaign_id"], "manifest/response campaign id mismatch")
    _require(calibration["schema"] == "siestaflow-occupation-noise-calibration-lock-v1", "unknown calibration lock")
    recipe = calibration["calibration"]
    policy = OccupationNoiseCalibrationPolicy(
        replica_count=recipe["replica_count"], safety_factor=recipe["safety_factor"],
        deterministic_floor_e=recipe["deterministic_floor_e"], output_quantum_e=recipe["output_quantum_e"],
        required_modes=tuple(recipe["required_modes"]),
    )
    policy.validate()
    _require(len(calibration_plan["replicas"]) == policy.replica_count, "calibration replica count mismatch")
    job_kinds = {replica["allocation"] for replica in calibration_plan["replicas"]}
    _require(job_kinds == {"separate_slurm_job"}, "calibration replicas must have separate Slurm jobs")
    _require(all(all(control.endswith("alpha_0") or control == "reference" for control in replica["controls"])
                 for replica in calibration_plan["replicas"]), "calibration plan contains response-mesh data")
    expected_axis = [-0.1, -0.05, -0.025, 0.0, 0.025, 0.05, 0.1]
    _require(response["response_mesh"]["centered_alpha_grid_ev"] == expected_axis, "response lock has wrong centered alpha grid")
    actual = sorted((item["mode"], item["alpha_ev"]) for item in response_plan["responses"])
    expected = sorted((mode, alpha) for mode in ("BARE", "SCREENED") for alpha in expected_axis if alpha != 0.0)
    _require(actual == expected, "response plan must contain exactly six BARE and six SCREENED nonzero shifts")
    _require(response_plan["alpha_zero"] == "reference_only", "alpha zero must be the reference only")
    _require(not _numeric_noise_keys(response), "response lock contains a numeric occupation_noise literal")
    _require(not _numeric_noise_keys(response_plan), "response plan contains a numeric occupation_noise literal")
    fdf = CAMPAIGN / "inputs/reference.fdf"
    for lock in (calibration, response):
        _require(_sha256(fdf) == lock["input_provenance"]["reference_fdf_sha256"], "reference FDF hash mismatch")
        _require(_sha256(ROOT / "examples/tmo_campaigns/Cu1.psml") == lock["input_provenance"]["pseudo_sha256"], "pseudopotential hash mismatch")
    _require(calibration["runtime"]["siesta_sha256"] == response["runtime"]["siesta_sha256"], "calibration/response SIESTA binary lock mismatch")
    calibration_lock_path = CAMPAIGN / "locks/calibration-methodology-lock.json"
    result_path = CAMPAIGN / "results/calibration-result.json"
    result_status = "absent"
    if require_result or result_path.exists():
        _require(result_path.is_file(), "calibration result is required before response admission")
        result = _load_strict("results/calibration-result.json")
        _validate_json_schema(result, ROOT / "schemas/campaign/occupation_noise_calibration_result.schema.json",
                              "calibration result")
        validate_calibration_result(result_path, calibration_lock_path)
        _require(result["calibration_lock_sha256"] == _sha256(calibration_lock_path), "calibration result lock hash mismatch")
        _require(isinstance(result["occupation_noise_e"], (int, float)) and result["occupation_noise_e"] >= policy.output_quantum_e,
                 "calibration occupation_noise is below observable output quantum")
        _require(len(result["replica_receipts"]) == policy.replica_count, "calibration result has wrong receipt count")
        ids = [receipt["slurm_job_id"] for receipt in result["replica_receipts"]]
        _require(len(ids) == len(set(ids)), "calibration replica Slurm job ids must be unique")
        _require(all(_is_sha256(receipt.get(field)) for receipt in result["replica_receipts"]
                     for field in ("receipts_sha256", "reference_dm_sha256", "replica_result_sha256")),
                 "calibration result has a missing or malformed receipt hash")
        evidence_paths: list[str] = []
        evidence_root = (CAMPAIGN / "results" / "calibration-replicas").resolve()
        for receipt in result["replica_receipts"]:
            relative = Path(receipt["replica_result_path"])
            _require(not relative.is_absolute(), "calibration evidence path must be campaign-relative")
            candidate = (CAMPAIGN / relative).resolve()
            _require(evidence_root in candidate.parents and candidate.name == "replica-result.json" and candidate.is_file(),
                     "calibration evidence path escapes or is missing")
            _require(_sha256(candidate) == receipt["replica_result_sha256"],
                     "calibration replica-result hash mismatch")
            evidence_paths.append(str(candidate))
        rederived = bind_calibration(
            None,
            _write_result=False,
            _verify_package_inputs=False,
            _replica_paths=evidence_paths,
        )
        _require(result == rederived,
                 "calibration result does not exactly match rederived physical evidence")
        occupations = {mode: result["by_mode"][mode]["occupations"] for mode in policy.required_modes}
        derived = derive_occupation_noise(occupations, policy)
        _require(isclose(result["occupation_noise_e"], derived.occupation_noise_e, rel_tol=0.0, abs_tol=0.0),
                 "calibration occupation_noise does not match the locked statistic")
        result_status = "bound"
    return {"status": "ADMITTED", "calibration_result": result_status,
            "calibration_lock_sha256": _sha256(calibration_lock_path),
            "response_lock_sha256": _sha256(CAMPAIGN / "locks/response-methodology-lock.json"),
            "software_lock_sha256": _sha256(CAMPAIGN / SOFTWARE_LOCK),
            "wheel_sha256": software["wheel"]["sha256"]}


def bind_calibration(
    raw_path: Path | None,
    *,
    _write_result: bool = True,
    _verify_package_inputs: bool = True,
    _replica_paths: list[str] | None = None,
) -> dict[str, Any]:
    """Derive the calibration result from the complete replica evidence.

    The private arguments let response admission rederive the result without
    rewriting it.  Public callers always use the default fail-closed path.
    """
    result_output = CAMPAIGN / "results/calibration-result.json"
    if _write_result:
        _require(not result_output.exists(), "refusing to overwrite calibration-result; restart requires explicit external removal of all calibration evidence")
    if _verify_package_inputs:
        verify_package(require_result=False)
    if _replica_paths is None:
        _require(raw_path is not None, "binder input path is required")
        raw = load_strict_json(raw_path)
    else:
        _require(raw_path is None, "internal evidence replay cannot also accept a binder input file")
        raw = {"replica_result_paths": _replica_paths}
    calibration = _load_strict("locks/calibration-methodology-lock.json")
    recipe = calibration["calibration"]
    policy = OccupationNoiseCalibrationPolicy(
        replica_count=recipe["replica_count"], safety_factor=recipe["safety_factor"],
        deterministic_floor_e=recipe["deterministic_floor_e"], output_quantum_e=recipe["output_quantum_e"],
        required_modes=tuple(recipe["required_modes"]),
    )
    _require(set(raw) == {"replica_result_paths"}, "binder input has unexpected fields")
    replica_paths = raw.get("replica_result_paths")
    _require(isinstance(replica_paths, list) and len(replica_paths) == policy.replica_count,
             "binder requires exactly five replica_result_paths, never declared scalar occupations")
    replicas = []
    for value in replica_paths:
        candidate = Path(value).resolve()
        allowed = (CAMPAIGN / "results" / "calibration-replicas").resolve()
        _require(allowed in candidate.parents and candidate.name == "replica-result.json" and candidate.is_file(),
                 "replica result must be a real calibration artifact under campaign results")
        replica = load_strict_json(candidate)
        replica["_replica_result_path"] = candidate.relative_to(CAMPAIGN.resolve()).as_posix()
        replica["_replica_result_sha256"] = _sha256(candidate)
        _require(set(replica) == {
            "schema", "replica_id", "slurm_job_id", "slurm_restart_count", "alpha_ev", "validated",
            "occupations", "receipts_path", "receipts_sha256", "reference_dm_sha256", "parent_dm_sha256",
            "commands", "execution_profile", "reference_fdf_sha256", "pseudo_sha256", "siesta_sha256",
            "reference_dm_path", "pseudo_path", "mpi_launcher", "mpi_launcher_sha256",
            "_replica_result_path", "_replica_result_sha256",
        }, "replica result has missing or unexpected fields")
        _require(replica.get("schema") == "siestaflow-calibration-replica-v2", "unknown replica-result schema")
        _require(replica.get("slurm_restart_count") in (None, "", "0", 0), "Slurm restart/retry is forbidden")
        _require(isinstance(replica.get("slurm_job_id"), str) and replica["slurm_job_id"].isdigit() and int(replica["slurm_job_id"]) > 0,
                 "replica Slurm job id is invalid")
        reference_dm = _inside(Path(str(replica.get("reference_dm_path", ""))), candidate.parent, "reference DM")
        pseudo = _inside(Path(str(replica.get("pseudo_path", ""))), candidate.parent, "staged pseudopotential")
        _require(_sha256(reference_dm) == replica.get("reference_dm_sha256"), "reference DM artifact hash mismatch")
        _require(_sha256(pseudo) == replica.get("pseudo_sha256"), "staged pseudopotential hash mismatch")
        receipt_path = candidate.parent / replica.get("receipts_path", "")
        _require(receipt_path.is_file() and _sha256(receipt_path) == replica.get("receipts_sha256"), "receipt file hash mismatch")
        receipt_value = json.loads(receipt_path.read_text(encoding="utf-8"), parse_constant=lambda item: (_ for _ in ()).throw(ValueError(item)))
        _require(isinstance(receipt_value, list), "receipt file is not a JSON list")
        receipts = receipt_value
        _require(len(receipts) == 3 and all(isinstance(item, dict) and set(item) == {"node_id", "state", "evidence_digest"} and item.get("state") == "VALIDATED" and _is_sha256(item.get("evidence_digest")) for item in receipts), "replica receipt is not fully VALIDATED")
        _require({item.get("node_id") for item in receipts} == {"reference", "response:BARE_zero", "response:SCREENED_zero"}, "unexpected calibration receipt topology")
        receipt_by_node = {item["node_id"]: item for item in receipts}
        provenance_paths = {"reference": candidate.parent / "provenance" / "reference.json",
                            "response:BARE_zero": candidate.parent / "provenance" / "response_BARE_zero.json",
                            "response:SCREENED_zero": candidate.parent / "provenance" / "response_SCREENED_zero.json"}
        _require(all(path.is_file() for path in provenance_paths.values()), "missing node provenance")
        commands, command_records = {}, {}
        for item in replica.get("commands", []):
            _require(isinstance(item, dict) and set(item) == {"node_id", "argv", "stdin_path", "stdout_path", "dm_path", "stdin_sha256_before_execution", "parent_reference_dm_sha256_before_execution"}, "command provenance has missing or unexpected fields")
            node_id = item.get("node_id")
            argv = item.get("argv")
            _require(isinstance(argv, list) and all(isinstance(value, str) and value for value in argv),
                     "command argv provenance is invalid")
            np_index = argv.index("-np") if "-np" in argv else -1
            _require(argv[0] == calibration["runtime"]["mpi_launcher"] and
                     calibration["runtime"]["siesta_executable"] in argv and
                     np_index >= 0 and np_index + 1 < len(argv) and argv[np_index + 1] == "4",
                     "command did not use the locked four-rank MPI/SIESTA route")
            node_output = _inside(Path(str(item.get("stdout_path", ""))), candidate.parent, "SIESTA output")
            fdf = _inside(Path(str(item.get("stdin_path", ""))), candidate.parent, "materialized FDF")
            dm_artifact = _inside(Path(str(item.get("dm_path", ""))), candidate.parent, "node DM")
            _require(node_id not in commands and _sha256(fdf) == item.get("stdin_sha256_before_execution"), "materialized FDF pre-execution hash mismatch")
            if node_id == "reference":
                _require(item["parent_reference_dm_sha256_before_execution"] is None, "reference cannot declare a parent DM")
            else:
                _require(item["parent_reference_dm_sha256_before_execution"] == replica.get("reference_dm_sha256"), "command parent DM lineage mismatch")
            commands[node_id], command_records[node_id] = node_output, {**item, "_fdf": fdf, "_dm": dm_artifact}
        _require(set(commands) == {"reference", "response:BARE_zero", "response:SCREENED_zero"}, "unexpected calibration command topology")
        for node_id, provenance_path in provenance_paths.items():
            provenance = load_strict_json(provenance_path)
            _require(set(provenance) == {"schema", "node_id", "node", "artifacts", "semantic", "evidence_digest"} and
                     provenance.get("schema") == "siestaflow-siesta-node-evidence-v1" and provenance.get("node_id") == node_id,
                     "node provenance identity or schema mismatch")
            _require(provenance.get("evidence_digest") == receipt_by_node[node_id]["evidence_digest"],
                     "receipt/provenance evidence digest mismatch")
            digest_payload = {key: value for key, value in provenance.items() if key != "evidence_digest"}
            recomputed_digest = sha256(json.dumps(
                {"node_id": node_id, "argv": command_records[node_id]["argv"], "payload": digest_payload},
                sort_keys=True, separators=(",", ":"), default=str,
            ).encode()).hexdigest()
            _require(provenance.get("evidence_digest") == recomputed_digest,
                     "node provenance evidence digest is not canonical")
            node = provenance.get("node")
            _require(isinstance(node, dict) and node.get("node_id") == node_id, "provenance node payload mismatch")
            expected_kind = "REFERENCE" if node_id == "reference" else "PERTURBATION"
            _require(node.get("kind") == expected_kind, "provenance node kind mismatch")
            if node_id == "reference":
                _require(node.get("dependencies") == [] and node.get("perturbation") is None,
                         "reference provenance topology mismatch")
            else:
                perturbation = node.get("perturbation")
                expected_mode = "BARE" if "BARE" in node_id else "SCREENED"
                _require(node.get("dependencies") == ["reference"] and isinstance(perturbation, dict) and
                         perturbation.get("mode") == expected_mode and perturbation.get("alpha_ev") == 0.0 and
                         perturbation.get("site_id") == "Cu1" and perturbation.get("site_index") == 0,
                         "control provenance perturbation mismatch")
            artifacts = provenance["artifacts"]
            _require(set(artifacts) == {"fdf", "output", "dm"} and
                     artifacts.get("output") == _sha256(commands[node_id]) and
                     artifacts.get("fdf") == _sha256(command_records[node_id]["_fdf"]) and
                     artifacts.get("dm") == _sha256(command_records[node_id]["_dm"]) and
                     all(_is_sha256(value) for value in artifacts.values()),
                     "node provenance artifact hash mismatch")
            semantic = provenance.get("semantic")
            _require(isinstance(semantic, dict) and semantic.get("node_kind") == expected_kind,
                     "node provenance semantic role mismatch")
            if node_id == "reference":
                _require(artifacts["fdf"] == calibration["input_provenance"]["reference_fdf_sha256"] and command_records[node_id]["stdin_sha256_before_execution"] == calibration["input_provenance"]["reference_fdf_sha256"], "reference FDF provenance mismatch")
                _require(artifacts["dm"] == replica.get("reference_dm_sha256"), "reference provenance DM mismatch")
            else:
                expected_mode = "BARE" if "BARE" in node_id else "SCREENED"
                _require(semantic.get("response_mode") == expected_mode and
                         semantic.get("reference_dm_sha256") == replica.get("reference_dm_sha256"),
                         "response provenance mode or parent DM mismatch")
            if node_id == "response:BARE_zero":
                _require(semantic.get("bare_profile") == Siesta542PotentialShiftHamiltonianProfile().profile_id,
                         "BARE provenance parent DM or profile mismatch")
        profile_data = replica.get("execution_profile", {})
        _require(profile_data.get("runtime", {}).get("launcher", {}).get("processes_per_node") == 4 and profile_data.get("allocation", {}).get("total_cpus") == 4, "replica is not four-rank OpenMPI")
        _require(replica.get("reference_fdf_sha256") == calibration["input_provenance"]["reference_fdf_sha256"] and replica.get("pseudo_sha256") == calibration["input_provenance"]["pseudo_sha256"] and replica.get("siesta_sha256") == calibration["runtime"]["siesta_sha256"] and replica.get("mpi_launcher") == calibration["runtime"]["mpi_launcher"] and replica.get("mpi_launcher_sha256") == calibration["runtime"]["mpi_launcher_sha256"], "replica FDF/pseudo/SIESTA/MPI hash mismatch")
        _require(replica.get("parent_dm_sha256", {}).get("BARE") == replica.get("reference_dm_sha256") == replica.get("parent_dm_sha256", {}).get("SCREENED"), "parent DM lineage mismatch")
        locked_reference_text = (CAMPAIGN / "inputs/reference.fdf").read_text(encoding="utf-8")
        for child_node in ("response:BARE_zero", "response:SCREENED_zero"):
            child_text = command_records[child_node]["_fdf"].read_text(encoding="utf-8", errors="replace")
            expected_child = _expected_zero_control_fdf(child_node, locked_reference_text)
            _require(_canonical_fdf(child_text) == _canonical_fdf(expected_child),
                     f"{child_node} FDF is not the locked reference materialization")
        profile_parser = Siesta542PotentialShiftHamiltonianProfile()
        def extract(node, bare_mode=False):
            text = commands[node].read_text(encoding="utf-8", errors="replace")
            dumped = _assert_zero_shift_native_output(text, node)
            _require(_sha256(command_records[node]["_fdf"]) == command_records[node]["stdin_sha256_before_execution"],
                     "materialized FDF changed after execution")
            _require(_canonical_fdf(dumped) == _canonical_fdf(command_records[node]["_fdf"].read_text(encoding="utf-8", errors="replace")),
                     "native input dump differs from the materialized FDF")
            event = profile_parser.select_response(text).response_event if bare_mode else parse_hubbard_population_events(text)[-1]
            _require(len(event.atoms) == 1 and event.atoms[0].atom_index == 1, "ambiguous parsed Cu occupation")
            return event.atoms[0].trace_total
        replica["_reparsed_occupations"] = {"REFERENCE": extract("reference"), "BARE": extract("response:BARE_zero", True), "SCREENED": extract("response:SCREENED_zero")}
        replicas.append(replica)
    job_ids = [replica.get("slurm_job_id") for replica in replicas]
    _require(all(isinstance(job_id, str) and job_id for job_id in job_ids) and len(set(job_ids)) == len(job_ids),
             "each calibration replica needs a unique Slurm job id")
    _require(all(replica.get("alpha_ev") == 0.0 and replica.get("validated") is True for replica in replicas),
             "only validated zero-shift controls are admissible")
    values = {mode: [replica["_reparsed_occupations"][mode] for replica in replicas] for mode in policy.required_modes}
    result = derive_occupation_noise(values, policy)
    policy_payload = asdict(policy)
    policy_payload["required_modes"] = list(policy.required_modes)
    payload = {
        "schema": "siestaflow-occupation-noise-calibration-result-v1",
        "calibration_lock_sha256": _sha256(CAMPAIGN / "locks/calibration-methodology-lock.json"),
        "occupation_noise_e": result.occupation_noise_e,
        "by_mode": result.by_mode,
        "policy": policy_payload,
        "replica_receipts": [
            {"replica_id": replica.get("replica_id"), "slurm_job_id": replica["slurm_job_id"],
             "receipts_sha256": replica["receipts_sha256"], "reference_dm_sha256": replica["reference_dm_sha256"],
             "replica_result_path": str(replica["_replica_result_path"]),
             "replica_result_sha256": replica["_replica_result_sha256"]}
            for replica in replicas
        ],
    }
    if _write_result:
        result_output.parent.mkdir(exist_ok=True)
        result_output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def _parse_sbatch_job_id(stdout: str) -> str:
    """Accept only the numeric job id returned by ``sbatch --parsable``."""
    job_id = stdout.strip().split(";", 1)[0]
    _require(job_id.isdigit() and int(job_id) > 0, "sbatch did not return a numeric parsable job id")
    return job_id


def _frozen_wheel_wrapper(*, runtime: Path, script: Path, arguments: list[str], software: dict[str, Any]) -> str:
    """Install the exact wheel in an isolated venv, then run with no PYTHONPATH."""
    wheel = CAMPAIGN / software["wheel"]["path"]
    python = Path(sys.executable)
    command = [
        "set -eu",
        f"test ! -e {shlex.quote(str(runtime))}",
        f"{shlex.quote(str(python))} -m venv --system-site-packages {shlex.quote(str(runtime))}",
        f"{shlex.quote(str(runtime / 'bin' / 'python'))} -m pip install --no-index --no-deps --force-reinstall {shlex.quote(str(wheel))}",
        "env -u PYTHONPATH " + " ".join(shlex.quote(str(item)) for item in [runtime / "bin" / "python", script, *arguments]),
    ]
    return "; ".join(command)


def submit_calibration(*, dry_run: bool) -> dict[str, Any]:
    """Submit the five fixed controls separately, then bind only their receipts."""
    verify_package(require_result=False)
    software = _verify_locks()
    worker = ROOT / "tools/run_cu_noise_calibration_replica.py"
    result_root = CAMPAIGN / "results/calibration-replicas"
    commands = []
    for index in range(1, 6):
        replica = f"replica-{index:02d}"
        runtime = result_root / f".{replica}-runtime"
        invocation = _frozen_wheel_wrapper(
            runtime=runtime, script=worker,
            arguments=[replica, "--output-root", str(result_root), "--software-lock", str(CAMPAIGN / SOFTWARE_LOCK),
                       "--expected-software-lock-sha256", _sha256(CAMPAIGN / SOFTWARE_LOCK)],
            software=software,
        )
        commands.append(["sbatch", "--wait", "--parsable", "-p", "local", "-N", "1", "-n", "4", "-c", "1", "--exclusive",
                         "--export=NONE,OMP_NUM_THREADS=1", "--wrap", invocation])
    if dry_run:
        return {"status": "DRY_RUN", "commands": commands, "result_root": str(result_root)}
    submitted: dict[str, str] = {}
    for index, command in enumerate(commands, start=1):
        completed = subprocess.run(command, cwd=ROOT, check=True, text=True, capture_output=True)
        submitted[f"replica-{index:02d}"] = _parse_sbatch_job_id(completed.stdout)
    raw = {"replica_result_paths": []}
    for index in range(1, 6):
        replica = result_root / f"replica-{index:02d}/replica-result.json"
        _require(replica.is_file(), f"missing calibration replica result: {replica}")
        _require(load_strict_json(replica)["slurm_job_id"] == submitted[f"replica-{index:02d}"], "sbatch job id and replica SLURM_JOB_ID differ")
        raw["replica_result_paths"].append(str(replica.resolve()))
    raw_path = CAMPAIGN / "results/raw-calibration-receipts.json"
    raw_path.write_text(json.dumps(raw, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return bind_calibration(raw_path)


def submit_response(*, dry_run: bool) -> dict[str, Any]:
    """Submit the immutable 1+6+6 response DAG only after calibration admission."""
    admitted = verify_package(require_result=True)
    evidence = CAMPAIGN / "results/response-campaign"
    if evidence.exists():
        raise ValueError("refusing to reuse response evidence directory")
    runner = ROOT / "tools/run_siesta542_openmpi_slurm_full_campaign.py"
    software = _verify_locks()
    result_path, lock_path, software_lock = (CAMPAIGN / "results/calibration-result.json",
                                              CAMPAIGN / "locks/calibration-methodology-lock.json",
                                              CAMPAIGN / SOFTWARE_LOCK)
    runtime = evidence.with_name(evidence.name + ".runtime")
    invocation = _frozen_wheel_wrapper(
        runtime=runtime, script=runner,
        arguments=["--evidence-dir", str(evidence), "--reference-fdf", str(CAMPAIGN / "inputs/reference.fdf"),
                   "--reference-label", "CU_NOISE_LR_REFERENCE", "--reference-dm-name", "CU_NOISE_LR_REFERENCE.DM",
                   "--calibration-result", str(result_path), "--calibration-lock", str(lock_path),
                   "--expected-calibration-result-sha256", _sha256(result_path),
                   "--expected-calibration-lock-sha256", _sha256(lock_path),
                   "--software-lock", str(software_lock),
                   "--expected-software-lock-sha256", _sha256(software_lock)],
        software=software,
    )
    command = ["sbatch", "--wait", "--parsable", "-p", "local", "-N", "1", "-n", "4", "-c", "1", "--exclusive",
               "--export=NONE,OMP_NUM_THREADS=1", "--wrap", invocation]
    if dry_run:
        return {"status": "DRY_RUN", "admission": admitted, "command": command}
    completed = subprocess.run(command, cwd=ROOT, check=True, text=True, capture_output=True)
    submitted = _parse_sbatch_job_id(completed.stdout)
    _require((evidence / "result.json").is_file(), "response job created no result receipt")
    _require(load_strict_json(evidence / "result.json")["slurm_job_id"] == submitted, "sbatch job id and response SLURM_JOB_ID differ")
    return {"status": "SUBMITTED_AND_COMPLETED", "evidence": str(evidence), "result": str(evidence / "result.json")}


def main() -> int:
    parser = argparse.ArgumentParser()
    command = parser.add_subparsers(dest="command", required=True)
    command.add_parser("verify")
    command.add_parser("response-admission")
    bind = command.add_parser("bind-calibration")
    bind.add_argument("receipt_input", type=Path)
    submit = command.add_parser("submit-calibration")
    submit.add_argument("--dry-run", action="store_true")
    response = command.add_parser("submit-response")
    response.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.command == "bind-calibration":
        value = bind_calibration(args.receipt_input)
    elif args.command == "submit-calibration":
        value = submit_calibration(dry_run=args.dry_run)
    elif args.command == "submit-response":
        value = submit_response(dry_run=args.dry_run)
    else:
        value = verify_package(require_result=args.command == "response-admission")
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
