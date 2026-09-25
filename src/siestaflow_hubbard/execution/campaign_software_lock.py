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
    if require_installed_wheel:
        if os.environ.get("PYTHONPATH"):
            raise CampaignSoftwareLockError("PYTHONPATH is forbidden for frozen campaign execution")
        try:
            distribution = metadata.distribution(str(wheel["distribution"]))
        except metadata.PackageNotFoundError as exc:
            raise CampaignSoftwareLockError("frozen wheel is not installed") from exc
        if distribution.version != str(wheel["version"]):
            raise CampaignSoftwareLockError("installed package version differs from frozen wheel")
    files = lock.get("files")
    if not isinstance(files, dict) or not files:
        raise CampaignSoftwareLockError("software lock file inventory is invalid")
    package_root: Path | None = None
    for relative, expected in files.items():
        if not isinstance(relative, str) or not isinstance(expected, str) or _SHA256.fullmatch(expected) is None:
            raise CampaignSoftwareLockError("software lock file entry is invalid")
        candidate = Path(relative)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise CampaignSoftwareLockError("software lock file path escapes project")
        if relative.startswith("src/siestaflow_hubbard/") and require_installed_wheel:
            if package_root is None:
                import siestaflow_hubbard
                package_root = Path(siestaflow_hubbard.__file__).resolve().parent
            target = package_root / candidate.relative_to("src/siestaflow_hubbard")
        else:
            target = project_root / candidate
        if not target.is_file() or _digest(target) != expected:
            raise CampaignSoftwareLockError(f"software hash mismatch: {relative}")
    return {"software_lock_sha256": expected_lock_sha256, "wheel_sha256": wheel["sha256"]}
