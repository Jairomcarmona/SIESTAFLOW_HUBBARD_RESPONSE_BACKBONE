"""Independent, hash-bound repeatability evidence for every LR response cell.

This contract reports observed replica spread.  It is not a probabilistic
confidence interval, a deterministic error bound, or a guarantee of truth.
"""
from __future__ import annotations

from hashlib import sha256
from dataclasses import dataclass, field
from math import isclose, isfinite
from pathlib import Path
import json
import re
from typing import Any, Mapping

from hubbardflow.siesta_backend.occupation_precision import read_printed_occupation_precision
from hubbardflow.siesta_backend.siesta542_bare_profile import Siesta542PotentialShiftHamiltonianProfile
from hubbardflow.siesta_backend.siesta542_screened_selection import select_converged_screened_event

class ResponseGridCalibrationError(ValueError):
    """A response-grid repeatability calibration is incomplete or unbound."""


def response_grid_campaign_context_sha256(
    *,
    material: Any,
    functional: str,
    reference_fdf_sha256: str,
    execution_profile_sha256: str,
    pseudopotentials: Mapping[str, str],
    sites: list[Mapping[str, Any]],
    alpha_grid_eV: list[float],
    analysis_policy: Mapping[str, Any],
    adaptive_alpha_policy: Mapping[str, Any] | None,
    magnetic_moment_tolerance_muB: float | None,
) -> str:
    """Canonical response context shared by campaign admission and packager."""
    context = {
        "material": material,
        "functional": functional,
        "reference_fdf_sha256": reference_fdf_sha256,
        "execution_profile_sha256": execution_profile_sha256,
        "pseudopotentials": dict(sorted(pseudopotentials.items())),
        "sites": [
            {key: site.get(key) for key in ("index", "site_id", "atom_index", "orbit_id")}
            for site in sites
        ],
        "alpha_grid_eV": alpha_grid_eV,
        "analysis_policy": dict(analysis_policy),
        "adaptive_alpha_policy": adaptive_alpha_policy,
        "magnetic_moment_tolerance_muB": magnetic_moment_tolerance_muB,
        "response_observable": "Hubbard projector population, BARE first-Hamiltonian / SCREENED converged",
    }
    return sha256(json.dumps(context, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def response_grid_source_campaign_context(
    manifest_path: Path,
) -> tuple[dict[str, Any], str]:
    """Reconstruct a source campaign's response context from its pinned inputs."""
    # Imports are local to avoid a domain/execution import cycle at module load.
    from hubbardflow.domain.adaptive_alpha_control import AdaptiveAlphaPolicy
    from hubbardflow.domain.lr_analysis_v2 import LRAnalysisPolicy
    from hubbardflow.execution.campaign_v2 import (
        load_campaign_v2, sha256_file, verify_campaign_inventory,
    )

    campaign = load_campaign_v2(manifest_path)
    verify_campaign_inventory(campaign)
    root = Path(str(campaign["_campaign_root"])).resolve(strict=True)
    config_relative = Path(str(campaign["lr_config_file"]))
    if config_relative.is_absolute() or ".." in config_relative.parts:
        raise ResponseGridCalibrationError("source LR config path is not campaign-relative")
    config_path = (root / config_relative).resolve(strict=True)
    try:
        config_path.relative_to(root)
    except ValueError as exc:
        raise ResponseGridCalibrationError("source LR config escapes campaign root") from exc
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ResponseGridCalibrationError("source LR config is unreadable") from exc
    if not isinstance(config, Mapping):
        raise ResponseGridCalibrationError("source LR config must be an object")
    pseudopotentials = config.get("pseudopotentials")
    if not isinstance(pseudopotentials, Mapping) or not pseudopotentials:
        raise ResponseGridCalibrationError("source LR config lacks pseudopotential paths")
    pseudo_hashes: dict[str, str] = {}
    for label, raw in sorted(pseudopotentials.items()):
        if not isinstance(raw, str):
            raise ResponseGridCalibrationError(f"source pseudopotential path for {label} is invalid")
        pseudo = Path(raw)
        if not pseudo.is_absolute():
            pseudo = root / pseudo
        pseudo = pseudo.resolve(strict=True)
        if not pseudo.is_file():
            raise ResponseGridCalibrationError(f"source pseudopotential for {label} is not a file")
        pseudo_hashes[str(label)] = sha256_file(pseudo)
    analysis_raw = config.get("analysis_policy", {})
    if not isinstance(analysis_raw, Mapping):
        raise ResponseGridCalibrationError("source analysis_policy must be an object")
    try:
        analysis_context = LRAnalysisPolicy(**analysis_raw).response_context()
    except (TypeError, ValueError) as exc:
        raise ResponseGridCalibrationError(f"source analysis policy is invalid: {exc}") from exc
    adaptive_raw = config.get("adaptive_alpha_policy")
    if adaptive_raw is None:
        adaptive_context = None
    else:
        try:
            adaptive_context = AdaptiveAlphaPolicy.from_mapping(adaptive_raw).to_mapping()
        except (TypeError, ValueError) as exc:
            raise ResponseGridCalibrationError(f"source adaptive alpha policy is invalid: {exc}") from exc
    reference_fdf_rel = Path(str(campaign["reference_fdf"]))
    profile_rel = Path(str(campaign["execution_profile_file"]))
    if (reference_fdf_rel.is_absolute() or profile_rel.is_absolute()
            or ".." in reference_fdf_rel.parts or ".." in profile_rel.parts):
        raise ResponseGridCalibrationError("source FDF/profile path is not campaign-relative")
    reference_fdf = (root / reference_fdf_rel).resolve(strict=True)
    profile = (root / profile_rel).resolve(strict=True)
    for path in (reference_fdf, profile):
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise ResponseGridCalibrationError("source FDF/profile path escapes campaign root") from exc
    context_hash = response_grid_campaign_context_sha256(
        material=campaign.get("material"),
        functional=str(campaign["functional"]),
        reference_fdf_sha256=sha256_file(reference_fdf),
        execution_profile_sha256=sha256_file(profile),
        pseudopotentials=pseudo_hashes,
        sites=campaign["sites"],
        alpha_grid_eV=[float(value) for value in campaign["alpha_grid_ev"]],
        analysis_policy=analysis_context,
        adaptive_alpha_policy=adaptive_context,
        magnetic_moment_tolerance_muB=campaign.get("magnetic_moment_tolerance_muB"),
    )
    return campaign, context_hash


_HASH = re.compile(r"[0-9a-f]{64}\Z")
_MODES = {"BARE", "SCREENED"}
_VALIDATION_TOKEN = object()


@dataclass(frozen=True)
class ValidatedResponseGridCalibration:
    """Non-serializable admission object emitted only by the validator."""

    campaign_context_sha256: str
    lock_sha256: str
    result_sha256: str
    replica_count: int
    replica_campaign_ids: tuple[str, ...]
    reference_dm_sha256s: tuple[str, ...]
    replica_source_roots: tuple[str, ...]
    reference_execution_attempt_ids: tuple[str, ...]
    execution_attempt_ids: tuple[str, ...]
    safety_factor: float
    deterministic_floor_e: float
    observed_replicas_by_coordinate: Mapping[tuple[int, float, str, int], list[float]]
    replica_print_half_widths_by_coordinate: Mapping[tuple[int, float, str, int], list[float]]
    scope: str
    _token: object = field(repr=False, compare=False, default=None)

    def __post_init__(self) -> None:
        if self._token is not _VALIDATION_TOKEN:
            raise ResponseGridCalibrationError("validated calibration objects must come from the evidence validator")


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"), parse_constant=lambda item: (_ for _ in ()).throw(
            ResponseGridCalibrationError(f"non-finite JSON constant: {item}")))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ResponseGridCalibrationError(f"cannot read calibration JSON: {path}") from exc
    if not isinstance(value, dict):
        raise ResponseGridCalibrationError(f"calibration JSON must be an object: {path}")
    return value


def _fields(value: Any, expected: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        raise ResponseGridCalibrationError(f"{label} has missing or unexpected fields")
    return value


def _number(value: Any, label: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ResponseGridCalibrationError(f"{label} must be a finite number")
    number = float(value)
    if positive and number <= 0.0:
        raise ResponseGridCalibrationError(f"{label} must be positive")
    return number


def _digest(value: Any, label: str) -> str:
    if not isinstance(value, str) or _HASH.fullmatch(value) is None:
        raise ResponseGridCalibrationError(f"{label} must be a lowercase SHA-256")
    return value


def _relative_evidence(root: Path, raw_path: Any, expected_hash: Any, label: str) -> Path:
    if not isinstance(raw_path, str):
        raise ResponseGridCalibrationError(f"{label} path must be campaign-relative")
    rel = Path(raw_path)
    if rel.is_absolute() or ".." in rel.parts:
        raise ResponseGridCalibrationError(f"{label} path escapes the campaign")
    digest = _digest(expected_hash, f"{label} SHA-256")
    path = (root / rel).resolve(strict=True)
    try:
        path.relative_to(root.resolve(strict=True))
    except ValueError as exc:
        raise ResponseGridCalibrationError(f"{label} path escapes the campaign") from exc
    if not path.is_file() or sha256(path.read_bytes()).hexdigest() != digest:
        raise ResponseGridCalibrationError(f"{label} is missing or its hash does not match")
    return path


def _node_artifact_path(root: Path, raw_path: Any, label: str, *, directory: bool = False) -> Path:
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise ResponseGridCalibrationError(f"{label} path is missing")
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root.resolve(strict=True))
    except (OSError, ValueError) as exc:
        raise ResponseGridCalibrationError(f"{label} is missing or escapes the campaign") from exc
    if directory != resolved.is_dir():
        raise ResponseGridCalibrationError(f"{label} has the wrong filesystem type")
    return resolved


_ATTEMPT_DIRECTORY = re.compile(r"attempt-\d+-[0-9a-f]{8}\Z")


def _execution_attempt(root: Path, cwd: Path) -> tuple[str, Path]:
    """Extract and validate the runner's unique attempt directory from node cwd."""
    try:
        relative = cwd.resolve(strict=True).relative_to(root.resolve(strict=True))
    except (OSError, ValueError) as exc:
        raise ResponseGridCalibrationError("node cwd is outside its campaign root") from exc
    matches = [index for index, part in enumerate(relative.parts) if _ATTEMPT_DIRECTORY.fullmatch(part)]
    if len(matches) != 1:
        raise ResponseGridCalibrationError("node cwd must identify exactly one runner attempt directory")
    index = matches[0]
    attempt_root = root.joinpath(*relative.parts[:index + 1]).resolve(strict=True)
    try:
        cwd.resolve(strict=True).relative_to(attempt_root)
    except (OSError, ValueError) as exc:
        raise ResponseGridCalibrationError("node cwd is not contained in its attempt directory") from exc
    return relative.parts[index], attempt_root


def _validate_reference_execution(
    root: Path, reference: Mapping[str, Any], nodes: Mapping[str, Any],
) -> tuple[str, str]:
    """Bind the reference DM to a validated, campaign-local SIESTA attempt."""
    if reference.get("state") != "VALIDATED":
        raise ResponseGridCalibrationError("reference source is not validated")
    node_id = reference.get("node_id")
    node = nodes.get(node_id) if isinstance(node_id, str) else None
    evidence_digest = reference.get("evidence_digest")
    if (not isinstance(node, Mapping) or node.get("state") != "VALIDATED"
            or node.get("kind") != "siesta"
            or node.get("evidence_digest") != evidence_digest):
        raise ResponseGridCalibrationError("reference source is not linked to a validated SIESTA node receipt")
    provenance = node.get("provenance")
    node_meta = provenance.get("node") if isinstance(provenance, Mapping) else None
    hashes = provenance.get("artifacts") if isinstance(provenance, Mapping) else None
    command, artifact_spec = node.get("command"), node.get("artifact_spec")
    if (not isinstance(node_meta, Mapping) or node_meta.get("node_id") != node_id
            or not isinstance(hashes, Mapping) or not isinstance(command, Mapping)
            or not isinstance(artifact_spec, Mapping)):
        raise ResponseGridCalibrationError("reference node receipt lacks identity, command, spec, or hashes")
    cwd = _node_artifact_path(root, command.get("cwd"), "reference command cwd", directory=True)
    attempt_id, attempt_root = _execution_attempt(root, cwd)
    paths: dict[str, Path] = {}
    for key, source_key in (("fdf", "fdf"), ("output", "out"), ("dm", "dm")):
        raw_spec = artifact_spec.get(key)
        if not isinstance(raw_spec, str):
            raise ResponseGridCalibrationError(f"reference node artifact path {key} is missing")
        relative = Path(raw_spec)
        if relative.is_absolute() or ".." in relative.parts:
            raise ResponseGridCalibrationError(f"reference node artifact path {key} is unsafe")
        path = _node_artifact_path(root, str(cwd / relative), f"reference node {key}")
        try:
            path.relative_to(attempt_root)
        except ValueError as exc:
            raise ResponseGridCalibrationError(f"reference node {key} artifact is outside its attempt") from exc
        expected_hash = reference.get(f"{source_key}_sha256")
        declared_hash = _digest(hashes.get(key), f"reference node {key} SHA-256")
        if declared_hash != expected_hash or sha256(path.read_bytes()).hexdigest() != declared_hash:
            raise ResponseGridCalibrationError(f"reference {key} bytes differ from analysis/node receipt")
        paths[key] = path
    source_path_fields = {"fdf": "fdf_path", "output": "out_path", "dm": "dm_path"}
    for key, field_name in source_path_fields.items():
        declared_path = _relative_evidence(root, reference.get(field_name), reference.get(
            "out_sha256" if key == "output" else f"{key}_sha256"
        ), f"reference {key}")
        if declared_path != paths[key]:
            raise ResponseGridCalibrationError(f"reference {key} path differs from node command/artifact spec")
    if (_node_artifact_path(root, command.get("stdin_path"), "reference stdin FDF") != paths["fdf"]
            or _node_artifact_path(root, command.get("stdout_path"), "reference stdout OUT") != paths["output"]):
        raise ResponseGridCalibrationError("reference command stdin/stdout do not match its artifact spec")
    reference_dm_hash = str(reference["dm_sha256"])
    return reference_dm_hash, attempt_id


def _validate_independent_execution_identities(
    campaigns: list[Mapping[str, Any]], *,
    primary_campaign_id: str | None = None,
    primary_source_root: Path | None = None,
    primary_attempt_ids: set[str] | None = None,
) -> None:
    """Reject reused campaign roots/runner attempts, independent of output bytes."""
    seen_campaigns: set[str] = set()
    seen_roots: set[str] = set()
    seen_attempts: set[str] = set(primary_attempt_ids or ())
    if primary_campaign_id:
        seen_campaigns.add(primary_campaign_id)
    if primary_source_root is not None:
        seen_roots.add(str(primary_source_root.resolve(strict=True)))
    for item in campaigns:
        campaign_id = item.get("campaign_id")
        source_root = item.get("source_root")
        attempts = item.get("attempt_ids")
        if not isinstance(campaign_id, str) or not campaign_id.strip():
            raise ResponseGridCalibrationError("campaign execution identity lacks campaign UUID")
        if not isinstance(source_root, Path):
            raise ResponseGridCalibrationError("campaign execution identity lacks source root")
        if not isinstance(attempts, (list, tuple, set)) or not attempts:
            raise ResponseGridCalibrationError("campaign execution identity lacks attempt IDs")
        root_key = str(source_root.resolve(strict=True))
        if campaign_id in seen_campaigns or root_key in seen_roots:
            raise ResponseGridCalibrationError("independent campaigns must have distinct UUIDs and source roots")
        seen_campaigns.add(campaign_id)
        seen_roots.add(root_key)
        local_attempts: set[str] = set()
        for attempt in attempts:
            if not isinstance(attempt, str) or not attempt:
                raise ResponseGridCalibrationError("campaign execution identity contains an invalid attempt ID")
            if attempt in local_attempts or attempt in seen_attempts:
                raise ResponseGridCalibrationError("independent campaign evidence reuses a runner attempt ID")
            local_attempts.add(attempt)
        seen_attempts.update(local_attempts)


def _explicit_source_root(raw_path: Any) -> Path:
    """Resolve the explicitly named root for one independent source campaign."""
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise ResponseGridCalibrationError("replica source_root must be an explicit absolute path")
    candidate = Path(raw_path)
    if not candidate.is_absolute() or ".." in candidate.parts:
        raise ResponseGridCalibrationError("replica source_root must be absolute and contain no parent traversal")
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise ResponseGridCalibrationError("replica source_root is missing") from exc
    if not resolved.is_dir():
        raise ResponseGridCalibrationError("replica source_root must be a directory")
    return resolved


def _verify_projector_shift(fdf_text: str, site_id: str, alpha_ev: float) -> None:
    lines = fdf_text.splitlines()
    starts = [i for i, line in enumerate(lines) if re.match(r"^\s*%block\s+DFTU\.Proj\s*$", line, re.I)]
    if len(starts) != 1:
        raise ResponseGridCalibrationError("node FDF must contain exactly one DFTU.Proj block")
    start = starts[0]
    ends = [i for i in range(start + 1, len(lines))
            if re.match(r"^\s*%endblock\s+DFTU\.Proj\s*$", lines[i], re.I)]
    if len(ends) != 1:
        raise ResponseGridCalibrationError("node FDF has an incomplete or ambiguous DFTU.Proj block")
    body = lines[start + 1:ends[0]]
    if not body or len(body) % 4:
        raise ResponseGridCalibrationError("node FDF DFTU.Proj records are not complete four-line site records")
    matched = 0
    for offset in range(0, len(body), 4):
        header, shell, shift_line, radial = body[offset:offset + 4]
        header_fields, shell_fields = header.split(), shell.split()
        shift_fields, radial_fields = shift_line.split(), radial.split()
        if len(header_fields) != 2 or len(shell_fields) != 2 or len(shift_fields) != 2 or len(radial_fields) < 2:
            raise ResponseGridCalibrationError("node FDF contains an unsupported DFTU.Proj site record")
        try:
            alpha = float(shift_fields[0])
            other_shift = float(shift_fields[1])
            int(header_fields[1]); int(shell_fields[0]); int(shell_fields[1])
            float(radial_fields[0]); float(radial_fields[1])
        except ValueError as exc:
            raise ResponseGridCalibrationError("node FDF contains a nonnumeric DFTU.Proj record") from exc
        if header_fields[0] == site_id:
            matched += 1
            if not isclose(alpha, alpha_ev, rel_tol=0.0, abs_tol=5.1e-5):
                raise ResponseGridCalibrationError("FDF projector shift does not match the node alpha")
        elif not isclose(alpha, 0.0, rel_tol=0.0, abs_tol=1e-12):
            raise ResponseGridCalibrationError("FDF applies a nonzero shift to an unexpected site")
        if not isclose(other_shift, 0.0, rel_tol=0.0, abs_tol=1e-12):
            raise ResponseGridCalibrationError("FDF applies an unexpected second-channel projector shift")
    if matched != 1:
        raise ResponseGridCalibrationError("node FDF does not identify exactly one perturbed site")


def validate_response_grid_calibration(
    root: Path,
    lock_path: Path,
    result_path: Path,
    *,
    expected_context_sha256: str,
    expected_sites: list[int],
    expected_site_ids: Mapping[int, str],
    expected_atom_indices: Mapping[int, int],
    expected_alphas_eV: list[float],
    expected_primary_campaign_id: str | None = None,
    expected_primary_source_root: Path | None = None,
) -> ValidatedResponseGridCalibration:
    """Validate immutable independent replicas and return per-cell samples.

    Result/dataset schema v2/v4:
      * lock pins campaign-context hash, exact site/alpha grid, replica count,
        safety factor, and deterministic floor;
      * result binds the lock, a bundle-relative dataset, and an explicit root
        for each source campaign; dataset paths remain bundle-relative;
      * each source analysis, node-evidence JSON, reference DM, and response
        FDF/OUT/DM are hash-bound within that source campaign root;
      * reference and response SIESTA nodes are tied to unique runner attempt
        directories, while identical artifact bytes remain admissible;
      * each measurement names the
        validated node, receipt digest, FDF and OUT paths/hashes, and occupation;
      * the node receipt and artifacts are rehashed, and the DFTU.Proj shift is
        re-read from the FDF before the selected OUT event is parsed.
    """
    root = root.resolve(strict=True)
    lock_path = lock_path.resolve(strict=True)
    result_path = result_path.resolve(strict=True)
    lock_hash = sha256(lock_path.read_bytes()).hexdigest()
    result = _json(result_path)
    lock = _json(lock_path)
    lock = _fields(lock, {
        "schema", "campaign_context_sha256", "site_labels", "alpha_grid_eV",
        "modes", "replica_count", "independence", "safety_factor",
        "deterministic_floor_e",
    }, "response-grid calibration lock")
    if lock["schema"] != "siestaflow-response-grid-reproducibility-lock-v1":
        raise ResponseGridCalibrationError("response-grid calibration lock schema is invalid")
    context_hash = _digest(lock["campaign_context_sha256"], "campaign context SHA-256")
    if context_hash != expected_context_sha256:
        raise ResponseGridCalibrationError("calibration campaign/material/functional/projector/SCF context differs")
    sites = lock["site_labels"]
    alphas = lock["alpha_grid_eV"]
    modes = lock["modes"]
    if sites != expected_sites or alphas != expected_alphas_eV or modes != ["BARE", "SCREENED"]:
        raise ResponseGridCalibrationError("calibration does not cover the exact active site/alpha/mode grid")
    if (set(expected_site_ids) != set(expected_sites)
            or any(not isinstance(expected_site_ids[site], str) or not expected_site_ids[site].strip()
                   for site in expected_sites)):
        raise ResponseGridCalibrationError("expected site index-to-ID map is incomplete")
    replica_count = lock["replica_count"]
    if isinstance(replica_count, bool) or not isinstance(replica_count, int) or replica_count < 3:
        raise ResponseGridCalibrationError("at least three independent response-grid replicas are required")
    if not isinstance(lock["independence"], str) or not lock["independence"].strip():
        raise ResponseGridCalibrationError("replica independence protocol is missing")
    safety = _number(lock["safety_factor"], "safety_factor", positive=True)
    floor = _number(lock["deterministic_floor_e"], "deterministic_floor_e", positive=True)
    bundle_root = result_path.parent.resolve(strict=True)
    expected_result_fields = {"schema", "calibration_lock_sha256", "replica_receipts"}
    result = _fields(result, expected_result_fields, "response-grid calibration result")
    if result["schema"] != "siestaflow-response-grid-reproducibility-result-v2" or result["calibration_lock_sha256"] != lock_hash:
        raise ResponseGridCalibrationError("calibration result is not bound to this lock")
    receipts = result["replica_receipts"]
    if not isinstance(receipts, list) or len(receipts) != replica_count:
        raise ResponseGridCalibrationError("calibration replica count differs from the lock")
    seen_ids: set[str] = set()
    seen_campaigns: set[str] = set()
    seen_roots: set[str] = set()
    seen_attempt_ids: set[str] = set()
    replica_source_roots: list[str] = []
    reference_attempt_ids: list[str] = []
    all_attempt_ids: list[str] = []
    execution_identity_records: list[dict[str, Any]] = []
    samples: dict[tuple[int, float, str, int], list[float]] = {}
    quantization_by_coordinate: dict[tuple[int, float, str, int], list[float]] = {}
    expected_cells = {
        (perturbed, float(alpha), mode, observed)
        for perturbed in expected_sites for alpha in expected_alphas_eV
        for mode in ("BARE", "SCREENED") for observed in expected_sites
    }
    for receipt_raw in receipts:
        receipt = _fields(receipt_raw, {
            "replica_id", "campaign_id", "reference_dm_sha256", "source_root",
            "campaign_manifest_path", "campaign_manifest_sha256",
            "analysis_path", "analysis_sha256", "dataset_path", "dataset_sha256",
            "node_evidence_path", "node_evidence_sha256",
        }, "replica receipt")
        replica_id, campaign_id = receipt["replica_id"], receipt["campaign_id"]
        if not isinstance(replica_id, str) or not replica_id or replica_id in seen_ids:
            raise ResponseGridCalibrationError("replica IDs must be non-empty and unique")
        if (not isinstance(campaign_id, str) or not campaign_id.strip()
                or campaign_id in seen_campaigns):
            raise ResponseGridCalibrationError("replicas must have distinct verified campaign UUIDs")
        if expected_primary_campaign_id is not None and campaign_id == expected_primary_campaign_id:
            raise ResponseGridCalibrationError("primary campaign cannot also be counted as an independent replica")
        dm_hash = _digest(receipt["reference_dm_sha256"], "reference DM SHA-256")
        source_root = _explicit_source_root(receipt["source_root"])
        source_root_key = str(source_root)
        if source_root_key in seen_roots:
            raise ResponseGridCalibrationError("independent replicas must have distinct source campaign roots")
        if expected_primary_source_root is not None and source_root == expected_primary_source_root.resolve(strict=True):
            raise ResponseGridCalibrationError("primary campaign root cannot also be used as a replica source")
        seen_ids.add(replica_id); seen_campaigns.add(campaign_id); seen_roots.add(source_root_key)
        replica_source_roots.append(source_root_key)
        manifest_path = _relative_evidence(
            source_root, receipt["campaign_manifest_path"], receipt["campaign_manifest_sha256"],
            "source campaign manifest",
        )
        source_campaign, source_context_hash = response_grid_source_campaign_context(manifest_path)
        if (source_campaign.get("campaign_id") != campaign_id
                or source_context_hash != context_hash):
            raise ResponseGridCalibrationError("source manifest/context differs from the locked response context")
        dataset_rel = Path(receipt["dataset_path"]) if isinstance(receipt["dataset_path"], str) else None
        if dataset_rel is None or dataset_rel.is_absolute() or ".." in dataset_rel.parts:
            raise ResponseGridCalibrationError("replica dataset path must be bundle-relative")
        dataset_path = _relative_evidence(
            bundle_root, str(dataset_rel), receipt["dataset_sha256"], "replica dataset",
        )
        analysis_path = _relative_evidence(
            source_root, receipt["analysis_path"], receipt["analysis_sha256"], "replica analysis",
        )
        analysis = _json(analysis_path)
        analysis_campaign = analysis.get("campaign")
        analysis_dataset = analysis.get("response_observation_dataset")
        if (analysis.get("schema_version") != "siestaflow.lr_u_analysis.v3"
                or not isinstance(analysis_campaign, Mapping)
                or analysis_campaign.get("campaign_id") != campaign_id
                or not isinstance(analysis_dataset, Mapping)):
            raise ResponseGridCalibrationError("source analysis is not a matching v3 campaign report")
        analysis_provenance = analysis.get("provenance")
        if (not isinstance(analysis_provenance, Mapping)
                or analysis_provenance.get("input_identity") != source_campaign.get("input_identity")
                or analysis.get("alpha_grid_eV") != expected_alphas_eV):
            raise ResponseGridCalibrationError("source analysis does not match its manifest input identity or response grid")
        dataset = _json(dataset_path)
        dataset = _fields(dataset, {
            "schema", "replica_id", "campaign_id", "reference_dm_sha256",
            "campaign_context_sha256", "campaign_manifest_path", "campaign_manifest_sha256",
            "analysis_path", "analysis_sha256",
            "node_evidence_path", "node_evidence_sha256", "reference_dm_path",
            "reference_node_id", "reference_evidence_digest", "reference_attempt_id",
            "measurements",
        }, "replica dataset")
        if (dataset["schema"] != "siestaflow-response-grid-replica-v4"
                or dataset["replica_id"] != replica_id or dataset["campaign_id"] != campaign_id
                or dataset["reference_dm_sha256"] != dm_hash
                or dataset["campaign_context_sha256"] != context_hash
                or dataset["campaign_manifest_path"] != receipt["campaign_manifest_path"]
                or dataset["campaign_manifest_sha256"] != receipt["campaign_manifest_sha256"]
                or dataset["analysis_path"] != receipt["analysis_path"]
                or dataset["analysis_sha256"] != receipt["analysis_sha256"]
                or dataset["node_evidence_path"] != receipt["node_evidence_path"]
                or dataset["node_evidence_sha256"] != receipt["node_evidence_sha256"]):
            raise ResponseGridCalibrationError("replica dataset provenance differs from its receipt or target context")
        reference_dm_path = _relative_evidence(
            source_root, dataset["reference_dm_path"], dm_hash, "replica reference DM",
        )
        source_reference = analysis_dataset.get("reference_source")
        if (not isinstance(source_reference, Mapping)
                or source_reference.get("dm_sha256") != dm_hash
                or source_reference.get("dm_path") != dataset["reference_dm_path"]):
            raise ResponseGridCalibrationError("analysis reference DM identity does not match the replica receipt")
        node_evidence_path = _relative_evidence(
            source_root, dataset["node_evidence_path"], dataset["node_evidence_sha256"], "node-evidence receipt",
        )
        node_evidence = _json(node_evidence_path)
        nodes = node_evidence.get("nodes")
        identity = node_evidence.get("identity")
        if (not isinstance(nodes, dict) or not isinstance(identity, dict)
                or not isinstance(identity.get("campaign_id"), str) or not identity["campaign_id"].strip()
                or not isinstance(identity.get("input_identity"), str) or not identity["input_identity"].strip()):
            raise ResponseGridCalibrationError("node-evidence receipt lacks its campaign identity or node map")
        if (identity.get("campaign_id") != campaign_id
                or identity.get("input_identity") != source_campaign.get("input_identity")):
            raise ResponseGridCalibrationError("node-evidence identity differs from the source manifest/analysis")
        reference_dm_hash, reference_attempt_id = _validate_reference_execution(
            source_root, source_reference, nodes,
        )
        if (reference_dm_hash != dm_hash
                or dataset.get("reference_node_id") != source_reference.get("node_id")
                or dataset.get("reference_evidence_digest") != source_reference.get("evidence_digest")
                or dataset.get("reference_attempt_id") != reference_attempt_id):
            raise ResponseGridCalibrationError("reference execution identity differs from the dataset")
        if reference_attempt_id in seen_attempt_ids:
            raise ResponseGridCalibrationError("replicas must have distinct validated execution attempts")
        seen_attempt_ids.add(reference_attempt_id)
        reference_attempt_ids.append(reference_attempt_id)
        all_attempt_ids.append(reference_attempt_id)
        campaign_attempts = {reference_attempt_id}
        analysis_cells: dict[tuple[int, float, str, int], tuple[float, float, Mapping[str, Any]]] = {}
        analysis_rows = analysis_dataset.get("rows")
        if not isinstance(analysis_rows, list):
            raise ResponseGridCalibrationError("source analysis lacks response dataset rows")
        for analysis_row in analysis_rows:
            if not isinstance(analysis_row, Mapping):
                raise ResponseGridCalibrationError("source analysis response row is malformed")
            try:
                row_perturbed = int(analysis_row["perturbed_site_index"])
                row_alpha = _number(analysis_row["alpha_eV"], "analysis alpha")
                row_site_id = analysis_row["perturbed_site_id"]
            except (KeyError, TypeError, ValueError) as exc:
                raise ResponseGridCalibrationError("source analysis response coordinate is malformed") from exc
            observed_rows = analysis_row.get("observed_sites")
            if not isinstance(observed_rows, list):
                raise ResponseGridCalibrationError("source analysis observed-site rows are malformed")
            for observed_row in observed_rows:
                if not isinstance(observed_row, Mapping):
                    raise ResponseGridCalibrationError("source analysis observed-site entry is malformed")
                try:
                    row_observed = int(observed_row["observed_site_index"])
                    row_values = observed_row["occupations_electron"]
                    row_widths = observed_row["occupation_half_widths_electron"]
                    row_sources = observed_row["sources"]
                except (KeyError, TypeError, ValueError) as exc:
                    raise ResponseGridCalibrationError("source analysis measurement is incomplete") from exc
                if not all(isinstance(value, Mapping) for value in (row_values, row_widths, row_sources)):
                    raise ResponseGridCalibrationError("source analysis measurement has invalid values or sources")
                for mode in ("BARE", "SCREENED"):
                    mode_key = mode.lower()
                    source = row_sources.get(mode_key)
                    if not isinstance(source, Mapping) or source.get("state") != "VALIDATED":
                        raise ResponseGridCalibrationError("source analysis contains an unvalidated response source")
                    coordinate = (row_perturbed, row_alpha, mode, row_observed)
                    if coordinate in analysis_cells:
                        raise ResponseGridCalibrationError("source analysis contains duplicate response coordinates")
                    if row_site_id != expected_site_ids.get(row_perturbed):
                        raise ResponseGridCalibrationError("source analysis perturbed site differs from its manifest")
                    analysis_cells[coordinate] = (
                        _number(row_values.get(mode_key), "analysis occupation"),
                        _number(row_widths.get(mode_key), "analysis occupation half-width"),
                        source,
                    )
        if set(analysis_cells) != expected_cells:
            raise ResponseGridCalibrationError("source analysis does not cover the exact locked response grid")
        measurements = dataset["measurements"]
        if not isinstance(measurements, list) or len(measurements) != len(expected_cells):
            raise ResponseGridCalibrationError("each replica must contain every response-grid coordinate exactly once")
        seen_cells: set[tuple[int, float, str, int]] = set()
        response_nodes: dict[tuple[int, float, str], str] = {}
        response_attempts: dict[tuple[int, float, str], str] = {}
        for raw in measurements:
            cell = _fields(raw, {
                "perturbed_site", "alpha_eV", "mode", "observed_site", "occupation_e",
                "perturbed_site_id", "observed_atom_index", "occupation_half_width_e",
                "node_id", "evidence_digest", "attempt_id", "fdf_path", "fdf_sha256", "out_path", "out_sha256",
                "dm_path", "dm_sha256",
            }, "replica measurement")
            if any(
                isinstance(cell[name], bool) or not isinstance(cell[name], int)
                for name in ("perturbed_site", "observed_site")
            ):
                raise ResponseGridCalibrationError("replica site coordinates must be integer indices")
            coordinate = (
                cell["perturbed_site"], _number(cell["alpha_eV"], "alpha_eV"),
                cell["mode"], cell["observed_site"],
            )
            if coordinate not in expected_cells or coordinate in seen_cells or coordinate[2] not in _MODES:
                raise ResponseGridCalibrationError("replica measurement has an unexpected or duplicate coordinate")
            value = _number(cell["occupation_e"], "occupation_e")
            print_half_width = _number(cell["occupation_half_width_e"], "occupation_half_width_e")
            if print_half_width < 0.0:
                raise ResponseGridCalibrationError("occupation_half_width_e cannot be negative")
            perturbed_site = coordinate[0]
            expected_site_id = expected_site_ids.get(perturbed_site)
            if cell["perturbed_site_id"] != expected_site_id:
                raise ResponseGridCalibrationError("measurement site ID does not match the campaign site map")
            observed_site = coordinate[3]
            expected_atom = expected_atom_indices.get(observed_site)
            if (isinstance(cell["observed_atom_index"], bool)
                    or not isinstance(cell["observed_atom_index"], int)
                    or cell["observed_atom_index"] != expected_atom):
                raise ResponseGridCalibrationError("measurement atom index does not match the campaign site map")
            node_id = cell["node_id"]
            if not isinstance(node_id, str) or not node_id or node_id not in nodes:
                raise ResponseGridCalibrationError("measurement node_id is absent from the pinned node-evidence receipt")
            response_key = (perturbed_site, coordinate[1], coordinate[2])
            previous_node_id = response_nodes.setdefault(response_key, node_id)
            if previous_node_id != node_id:
                raise ResponseGridCalibrationError("one response coordinate is bound to multiple execution nodes")
            node_record = nodes[node_id]
            if not isinstance(node_record, dict):
                raise ResponseGridCalibrationError("node-evidence entry is malformed")
            evidence_digest = _digest(cell["evidence_digest"], "node evidence digest")
            if (node_record.get("state") != "VALIDATED"
                    or node_record.get("evidence_digest") != evidence_digest
                    or node_record.get("kind") != "siesta"):
                raise ResponseGridCalibrationError("measurement does not match a validated SIESTA node receipt")
            provenance = node_record.get("provenance")
            node_metadata = provenance.get("node") if isinstance(provenance, Mapping) else None
            if (not isinstance(node_metadata, Mapping)
                    or node_metadata.get("node_id") != node_id):
                raise ResponseGridCalibrationError(
                    "node-evidence provenance.node.node_id does not match its node-map key"
                )
            perturbation = node_metadata.get("perturbation")
            if not isinstance(perturbation, Mapping):
                raise ResponseGridCalibrationError("validated node receipt lacks its perturbation coordinate")
            if (isinstance(perturbation.get("site_index"), bool)
                    or not isinstance(perturbation.get("site_index"), int)
                    or perturbation.get("site_index") != perturbed_site
                    or perturbation.get("site_id") != expected_site_id
                    or perturbation.get("mode") != coordinate[2]
                    or not isclose(_number(perturbation.get("alpha_ev"), "node perturbation alpha"),
                                   coordinate[1], rel_tol=0.0, abs_tol=1e-14)):
                raise ResponseGridCalibrationError("node receipt perturbation does not match the measurement coordinate")

            command = node_record.get("command")
            artifact_spec = node_record.get("artifact_spec")
            artifact_hashes = provenance.get("artifacts") if isinstance(provenance, Mapping) else None
            if (not isinstance(command, Mapping) or not isinstance(artifact_spec, Mapping)
                    or not isinstance(artifact_hashes, Mapping)):
                raise ResponseGridCalibrationError("node receipt lacks command, artifact specification, or hashes")
            cwd = _node_artifact_path(source_root, command.get("cwd"), "node command cwd", directory=True)
            attempt_id, attempt_root = _execution_attempt(source_root, cwd)
            if cell.get("attempt_id") != attempt_id:
                raise ResponseGridCalibrationError("measurement attempt ID differs from its node command receipt")
            response_attempt_key = (perturbed_site, coordinate[1], coordinate[2])
            previous_attempt_id = response_attempts.get(response_attempt_key)
            if previous_attempt_id is not None and previous_attempt_id != attempt_id:
                raise ResponseGridCalibrationError("one response coordinate is bound to multiple execution attempts")
            if previous_attempt_id is None:
                if attempt_id in seen_attempt_ids:
                    raise ResponseGridCalibrationError("independent response nodes reuse a validated execution attempt")
                response_attempts[response_attempt_key] = attempt_id
                campaign_attempts.add(attempt_id)
                seen_attempt_ids.add(attempt_id)
                all_attempt_ids.append(attempt_id)
            if any(not isinstance(artifact_spec.get(key), str) for key in ("fdf", "output", "dm")):
                raise ResponseGridCalibrationError("node artifact specification lacks FDF/OUT/DM paths")
            spec_paths = {}
            for key in ("fdf", "output", "dm"):
                relative = Path(artifact_spec[key])
                if relative.is_absolute() or ".." in relative.parts:
                    raise ResponseGridCalibrationError(f"node artifact {key} path is not safely relative")
                spec_paths[key] = _node_artifact_path(source_root, str(cwd / relative), f"node {key}")
                try:
                    spec_paths[key].relative_to(attempt_root)
                except ValueError as exc:
                    raise ResponseGridCalibrationError(f"node {key} artifact is outside its attempt") from exc
            fdf_path = _relative_evidence(source_root, cell["fdf_path"], cell["fdf_sha256"], "measurement FDF")
            out_path = _relative_evidence(source_root, cell["out_path"], cell["out_sha256"], "measurement OUT")
            declared_dm_path = _relative_evidence(source_root, cell["dm_path"], cell["dm_sha256"], "measurement DM")
            command_fdf = _node_artifact_path(source_root, command.get("stdin_path"), "node stdin FDF")
            command_out = _node_artifact_path(source_root, command.get("stdout_path"), "node stdout OUT")
            if (fdf_path != command_fdf or fdf_path != spec_paths["fdf"]
                    or out_path != command_out or out_path != spec_paths["output"]
                    or declared_dm_path != spec_paths["dm"]):
                raise ResponseGridCalibrationError("dataset FDF/OUT paths differ from the pinned node receipt")
            for artifact_name, path in (("fdf", fdf_path), ("output", out_path), ("dm", spec_paths["dm"])):
                declared_hash = _digest(artifact_hashes.get(artifact_name), f"node {artifact_name} SHA-256")
                if sha256(path.read_bytes()).hexdigest() != declared_hash:
                    raise ResponseGridCalibrationError(f"node {artifact_name} bytes do not match node-evidence hash")
                if artifact_name == "fdf" and declared_hash != cell["fdf_sha256"]:
                    raise ResponseGridCalibrationError("measurement FDF hash differs from node-evidence hash")
                if artifact_name == "output" and declared_hash != cell["out_sha256"]:
                    raise ResponseGridCalibrationError("measurement OUT hash differs from node-evidence hash")
                if artifact_name == "dm" and declared_hash != cell["dm_sha256"]:
                    raise ResponseGridCalibrationError("measurement DM hash differs from node-evidence hash")
            fdf_text = fdf_path.read_text(encoding="utf-8", errors="replace")
            _verify_projector_shift(fdf_text, expected_site_id, coordinate[1])
            output_text = out_path.read_text(encoding="utf-8", errors="replace")
            try:
                event = (
                    Siesta542PotentialShiftHamiltonianProfile().select_response(output_text).response_event
                    if coordinate[2] == "BARE"
                    else select_converged_screened_event(output_text)
                )
                parsed = read_printed_occupation_precision(output_text, event)[expected_atom]
            except (ValueError, KeyError, IndexError) as exc:
                raise ResponseGridCalibrationError(
                    f"cannot semantically re-extract measurement from its output: {coordinate}: {exc}"
                ) from exc
            if (not isclose(value, parsed.total, rel_tol=0.0, abs_tol=1e-12)
                    or not isclose(print_half_width, parsed.half_width, rel_tol=0.0, abs_tol=1e-12)):
                raise ResponseGridCalibrationError(
                    f"replica occupation or quantization disagrees with parser output at {coordinate}"
                )
            report_value, report_width, report_source = analysis_cells[coordinate]
            if (not isclose(value, report_value, rel_tol=0.0, abs_tol=1e-12)
                    or not isclose(print_half_width, report_width, rel_tol=0.0, abs_tol=1e-12)
                    or report_source.get("node_id") != node_id
                    or report_source.get("evidence_digest") != evidence_digest
                    or report_source.get("fdf_path") != cell["fdf_path"]
                    or report_source.get("fdf_sha256") != cell["fdf_sha256"]
                    or report_source.get("out_path") != cell["out_path"]
                    or report_source.get("out_sha256") != cell["out_sha256"]
                    or report_source.get("dm_path") != cell["dm_path"]
                    or report_source.get("dm_sha256") != cell["dm_sha256"]):
                raise ResponseGridCalibrationError(
                    f"replica dataset differs from its hash-bound source analysis at {coordinate}"
                )
            seen_cells.add(coordinate)
            samples.setdefault(coordinate, []).append(value)
            quantization_by_coordinate.setdefault(coordinate, []).append(print_half_width)
        if seen_cells != expected_cells:
            raise ResponseGridCalibrationError("replica omits one or more response-grid coordinates")
        execution_identity_records.append({
            "campaign_id": campaign_id,
            "source_root": source_root,
            "attempt_ids": campaign_attempts,
        })
    if set(samples) != expected_cells or any(len(values) != replica_count for values in samples.values()):
        raise ResponseGridCalibrationError("response-grid replica coverage is incomplete")
    _validate_independent_execution_identities(
        execution_identity_records,
        primary_campaign_id=expected_primary_campaign_id,
        primary_source_root=expected_primary_source_root,
    )
    return ValidatedResponseGridCalibration(
        campaign_context_sha256=context_hash,
        lock_sha256=lock_hash,
        result_sha256=sha256(result_path.read_bytes()).hexdigest(),
        replica_count=replica_count,
        replica_campaign_ids=tuple(sorted(seen_campaigns)),
        reference_dm_sha256s=tuple(sorted(
            _digest(item["reference_dm_sha256"], "reference DM SHA-256") for item in receipts
        )),
        replica_source_roots=tuple(sorted(replica_source_roots)),
        reference_execution_attempt_ids=tuple(sorted(reference_attempt_ids)),
        execution_attempt_ids=tuple(sorted(all_attempt_ids)),
        safety_factor=safety,
        deterministic_floor_e=floor,
        observed_replicas_by_coordinate=samples,
        replica_print_half_widths_by_coordinate=quantization_by_coordinate,
        scope="EMPIRICAL_RESPONSE_GRID_REPRODUCIBILITY_CONDITIONAL_ON_VERIFIED_NODE_EVIDENCE",
        _token=_VALIDATION_TOKEN,
    )
