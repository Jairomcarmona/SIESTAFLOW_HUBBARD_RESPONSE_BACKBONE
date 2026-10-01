"""Verify a frozen campaign wheel and every source artifact it governs."""
from __future__ import annotations

from hashlib import sha256
from importlib import metadata
from pathlib import Path
import json
import os
import re


class CampaignSoftwareLockError(ValueError):
    """The execution software is not the preregistered immutable release."""


_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_PACKAGE_PATHS = (
    ("src/hubbardflow/", "hubbardflow"),
    # This path is part of immutable v3r2 campaign locks. Keep resolving it
    # through the exact legacy wheel instead of rewriting those lock records.
    ("src/siestaflow_hubbard/", "siestaflow_hubbard"),
)


def _digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _strict_json(path: Path) -> dict:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=lambda item: (_ for _ in ()).throw(ValueError(item)),
        )
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        raise CampaignSoftwareLockError("software lock is not strict JSON") from exc
    if not isinstance(value, dict):
        raise CampaignSoftwareLockError("software lock is not a JSON object")
    return value


def _locked_file_path(
    project_root: Path,
    relative: str,
    installed_distribution: metadata.Distribution | None,
    *,
    require_installed_wheel: bool,
) -> Path:
    """Resolve package paths in current locks and immutable legacy locks."""
    for source_prefix, package_directory in _PACKAGE_PATHS:
        if not relative.startswith(source_prefix):
            continue
        suffix = Path(relative).relative_to(source_prefix)
        if require_installed_wheel:
            if installed_distribution is None:
                raise CampaignSoftwareLockError("frozen wheel is not installed")
            return Path(installed_distribution.locate_file(package_directory)) / suffix
        if package_directory == "siestaflow_hubbard":
            # Historical lock paths resolve to the renamed active source tree
            # only for source-mode verification. The frozen wheel remains the
            # required route for exact historical campaign execution.
            return project_root / "src" / "hubbardflow" / suffix
        return project_root / Path(source_prefix) / suffix
    return project_root / relative


def verify_locked_software(
    campaign_root: Path,
    lock_path: Path,
    *,
    expected_lock_sha256: str,
    require_installed_wheel: bool,
) -> dict[str, str]:
    """Fail closed unless scripts, data, package code, and wheel match one lock."""
    campaign_root = campaign_root.resolve()
    project_root = campaign_root.parents[1]
    if not _SHA256.fullmatch(expected_lock_sha256) or _digest(lock_path) != expected_lock_sha256:
        raise CampaignSoftwareLockError("software lock differs from frozen submission hash")
    lock = _strict_json(lock_path)
    if set(lock) != {"schema", "campaign_id", "wheel", "files"} or lock.get("schema") != "siestaflow-campaign-software-lock-v1":
        raise CampaignSoftwareLockError("software lock schema is invalid")
    wheel = lock.get("wheel")
    if not isinstance(wheel, dict) or set(wheel) != {"path", "sha256", "distribution", "version"}:
        raise CampaignSoftwareLockError("software wheel declaration is invalid")
    wheel_path = campaign_root / wheel["path"]
    if not isinstance(wheel["sha256"], str) or _SHA256.fullmatch(wheel["sha256"]) is None or not wheel_path.is_file() or _digest(wheel_path) != wheel["sha256"]:
        raise CampaignSoftwareLockError("frozen wheel hash is invalid")
    installed_distribution: metadata.Distribution | None = None
    if require_installed_wheel:
        if os.environ.get("PYTHONPATH"):
            raise CampaignSoftwareLockError("PYTHONPATH is forbidden for frozen campaign execution")
        try:
            installed_distribution = metadata.distribution(str(wheel["distribution"]))
        except metadata.PackageNotFoundError as exc:
            raise CampaignSoftwareLockError("frozen wheel is not installed") from exc
        if installed_distribution.version != str(wheel["version"]):
            raise CampaignSoftwareLockError("installed package version differs from frozen wheel")
    files = lock.get("files")
    if not isinstance(files, dict) or not files:
        raise CampaignSoftwareLockError("software lock file inventory is invalid")
    for relative, expected in files.items():
        if not isinstance(relative, str) or not isinstance(expected, str) or _SHA256.fullmatch(expected) is None:
            raise CampaignSoftwareLockError("software lock file entry is invalid")
        candidate = Path(relative)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise CampaignSoftwareLockError("software lock file path escapes project")
        target = _locked_file_path(
            project_root,
            relative,
            installed_distribution,
            require_installed_wheel=require_installed_wheel,
        )
        if not target.is_file() or _digest(target) != expected:
            raise CampaignSoftwareLockError(f"software hash mismatch: {relative}")
    return {"software_lock_sha256": expected_lock_sha256, "wheel_sha256": wheel["sha256"]}
