"""Native file evidence used to construct B.2 check-resume requests."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from hubbardflow.domain.perturbation_plan import ResolvedPerturbationPlan

from .controller_contracts import ControllerContractError, load_strict_json
from .controller_resume import ResumeVerdict


@dataclass(frozen=True)
class ResumeBaselineFile:
    """One file identity and its expected/observed content digests."""

    artifact_id: str
    expected_sha256: str
    observed_sha256: str | None

    def to_mapping(self) -> dict[str, object]:
        return {
            "artifact_id": self.artifact_id,
            "expected_sha256": self.expected_sha256,
            "observed_sha256": self.observed_sha256,
        }


@dataclass(frozen=True)
class ResumeRequest:
    """Typed B.2 request projection; serialization preserves the native mapping."""

    expected_plan: Mapping[str, object]
    observed_plan: Mapping[str, object]
    expected_policies: Mapping[str, object]
    observed_policies: Mapping[str, object]
    files: tuple[ResumeBaselineFile, ...]

    def to_mapping(self) -> dict[str, object]:
        return {
            "expected_plan": dict(self.expected_plan),
            "observed_plan": dict(self.observed_plan),
            "expected_policies": dict(self.expected_policies),
            "observed_policies": dict(self.observed_policies),
            "files": [item.to_mapping() for item in self.files],
            "responses": [],
        }


def create_resume_baseline(
    manifest_path: Path, raw_campaign: Mapping[str, object], plan: ResolvedPerturbationPlan | None
) -> ResumeRequest | None:
    """Create B.2's complete native request before the first internal launch."""
    if plan is None:
        return None
    root = manifest_path.resolve().parent
    expected_plan = _resolved_plan_mapping(root, raw_campaign)
    files: list[ResumeBaselineFile] = []
    input_files = raw_campaign.get("input_files")
    if not isinstance(input_files, list):
        raise ControllerContractError("campaign input_files is malformed for resume baseline")
    for item in input_files:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise ControllerContractError("campaign input_files is malformed for resume baseline")
        relative = Path(item["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ControllerContractError("campaign input path is not safe for resume baseline")
        candidate = (root / relative).resolve(strict=True)
        candidate.relative_to(root)
        files.append(_baseline_file(f"input:{item['path']}", candidate))
    files.append(_baseline_file(f"manifest:{manifest_path.name}", manifest_path.resolve(strict=True)))
    files.sort(key=lambda item: item.artifact_id)
    policies = {"campaign": dict(raw_campaign)}
    return ResumeRequest(expected_plan, expected_plan, policies, policies, tuple(files))


def load_resume_request(
    baseline_path: Path,
    manifest_path: Path,
    raw_campaign: Mapping[str, object],
    plan: ResolvedPerturbationPlan | None,
) -> ResumeRequest:
    """Refresh only observed evidence in the baseline request for public check_resume."""
    try:
        baseline = load_strict_json(baseline_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ControllerContractError(f"resume baseline is unreadable: {exc}") from exc
    if not isinstance(baseline, dict) or baseline.get("responses") != []:
        raise ControllerContractError("resume baseline is absent, malformed, or contains responses")
    if plan is None:
        raise ControllerContractError("campaign lacks a frozen perturbation plan required for continuation")
    observed_plan = _resolved_plan_mapping(manifest_path.resolve().parent, raw_campaign)
    observed_policies = {"campaign": dict(raw_campaign)}
    baseline_files = baseline.get("files")
    if not isinstance(baseline_files, list):
        raise ControllerContractError("resume baseline files are malformed")
    observed_by_id: dict[str, str | None] = {}
    root = manifest_path.resolve().parent
    input_files = raw_campaign.get("input_files")
    if not isinstance(input_files, list):
        raise ControllerContractError("campaign input_files is malformed for resume")
    for item in input_files:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise ControllerContractError("campaign input_files is malformed for resume")
        relative = Path(item["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ControllerContractError("campaign input path is not safe for resume")
        candidate = (root / relative).resolve()
        candidate.relative_to(root)
        observed_by_id[f"input:{item['path']}"] = (
            sha256(candidate.read_bytes()).hexdigest() if candidate.is_file() else None
        )
    manifest = manifest_path.resolve(strict=True)
    observed_by_id[f"manifest:{manifest_path.name}"] = sha256(manifest.read_bytes()).hexdigest()
    files: list[ResumeBaselineFile] = []
    for item in baseline_files:
        if not isinstance(item, dict):
            raise ControllerContractError("resume baseline file row is malformed")
        identity, expected = item.get("artifact_id"), item.get("expected_sha256")
        if not isinstance(identity, str) or not isinstance(expected, str) or identity not in observed_by_id:
            raise ControllerContractError("resume baseline file identity is invalid")
        observed = observed_by_id[identity]
        files.append(ResumeBaselineFile(identity, expected, observed))
    if set(observed_by_id) != {item.artifact_id for item in files}:
        raise ControllerContractError("resume baseline input inventory changed")
    expected_plan = baseline.get("expected_plan")
    expected_policies = baseline.get("expected_policies")
    if not isinstance(expected_plan, dict) or not isinstance(expected_policies, dict):
        raise ControllerContractError("resume baseline plan or policies are malformed")
    return ResumeRequest(expected_plan, observed_plan, expected_policies, observed_policies, tuple(files))


def _resolved_plan_mapping(root: Path, campaign: Mapping[str, object]) -> dict[str, object]:
    relative_name = campaign.get("resolved_perturbation_plan_file")
    if not isinstance(relative_name, str) or not relative_name:
        raise ControllerContractError("campaign lacks a resolved perturbation plan file")
    relative = Path(relative_name)
    if relative.is_absolute() or ".." in relative.parts:
        raise ControllerContractError("resolved perturbation plan path is not safe")
    path = (root / relative).resolve(strict=True)
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise ControllerContractError("resolved perturbation plan escapes campaign root") from exc
    try:
        value = load_strict_json(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ControllerContractError(f"resolved perturbation plan is unreadable: {exc}") from exc
    if not isinstance(value, dict):
        raise ControllerContractError("resolved perturbation plan must be a mapping")
    return value


def _baseline_file(artifact_id: str, path: Path) -> ResumeBaselineFile:
    digest = sha256(path.read_bytes()).hexdigest()
    return ResumeBaselineFile(artifact_id, digest, digest)


def write_resume_baseline(path: Path, request: ResumeRequest) -> None:
    """Durably write the first-attempt request before any child can launch."""
    _write_json(path, request.to_mapping())


def write_resume_verdict(path: Path, verdict: ResumeVerdict) -> None:
    """Durably write one schema-validated typed continuation verdict."""
    _write_json(path, verdict.to_mapping())


def _write_json(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    encoded = json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2) + "\n"
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
