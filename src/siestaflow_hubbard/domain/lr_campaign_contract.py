"""Declarative, fail-closed contract for a new linear-response BARE campaign.

The contract contains no scheduler or backend-discovery logic.  It records the
scientific profile and the provenance inputs that a launcher must use later.
An unknown backend is never inferred to be compatible: admission is delegated
to the explicit :class:`BackendCompatibilityRegistry`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from .backend_compatibility import (
    BackendCompatibilityRegistry,
    BackendIdentity,
    CompatibilityRecord,
    ScientificProfile,
)


class LinearResponseContractError(ValueError):
    """Raised when a campaign contract is incomplete or unsafe to resolve."""


def _require_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LinearResponseContractError(f"{field} must be a non-empty string")
    return value.strip()


def _relative_path(value: Any, field: str) -> str:
    """Validate a portable POSIX-relative artifact path.

    Paths are kept relative so a contract cannot silently encode a user's
    home directory, a cluster mount, or an absolute executable location.
    """

    text = _require_text(value, field).replace("\\", "/")
    path = PurePosixPath(text)
    if path.is_absolute() or text.startswith("//") or ".." in path.parts:
        raise LinearResponseContractError(f"{field} must be a safe relative path")
    if not path.parts or any(part in {"", "."} for part in path.parts):
        raise LinearResponseContractError(f"{field} must be a normalized relative path")
    return str(path)


def _declared_executable(value: Any) -> str:
    text = _require_text(value, "declared_executable").replace("\\", "/")
    if text.startswith("-") or "\x00" in text:
        raise LinearResponseContractError("declared_executable is invalid")
    path = PurePosixPath(text)
    if path.is_absolute() or ".." in path.parts:
        raise LinearResponseContractError(
            "declared_executable must be a logical executable name or safe relative path"
        )
    return text


@dataclass(frozen=True)
class LinearResponseBareCampaignContract:
    """Portable declaration required before admitting a new BARE campaign."""

    campaign_id: str
    scientific_profile: ScientificProfile
    compatibility_registry: str
    declared_executable: str
    version_text_source: str
    backend_id: str = "siesta"
    schema: str = "lr_bare_campaign_contract_v1"

    def __post_init__(self) -> None:
        if self.schema != "lr_bare_campaign_contract_v1":
            raise LinearResponseContractError("unknown campaign contract schema")
        if not isinstance(self.scientific_profile, ScientificProfile):
            raise LinearResponseContractError("scientific_profile is required")
        object.__setattr__(self, "campaign_id", _require_text(self.campaign_id, "campaign_id"))
        object.__setattr__(self, "backend_id", _require_text(self.backend_id, "backend_id"))
        object.__setattr__(self, "compatibility_registry", _relative_path(
            self.compatibility_registry, "compatibility_registry"
        ))
        object.__setattr__(self, "version_text_source", _relative_path(
            self.version_text_source, "version_text_source"
        ))
        object.__setattr__(self, "declared_executable", _declared_executable(
            self.declared_executable
        ))
        if self.scientific_profile.key == ("", ""):
            raise LinearResponseContractError("scientific_profile is required")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "campaign_id": self.campaign_id,
            "backend_id": self.backend_id,
            "scientific_profile": {
                "profile_id": self.scientific_profile.profile_id,
                "version": self.scientific_profile.version,
            },
            "compatibility_registry": self.compatibility_registry,
            "declared_executable": self.declared_executable,
            "version_text_source": self.version_text_source,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "LinearResponseBareCampaignContract":
        if not isinstance(payload, Mapping):
            raise LinearResponseContractError("campaign contract must be a mapping")
        if payload.get("schema") != "lr_bare_campaign_contract_v1":
            raise LinearResponseContractError("unknown campaign contract schema")
        profile = payload.get("scientific_profile")
        if not isinstance(profile, Mapping):
            raise LinearResponseContractError("scientific_profile must be a mapping")
        if "profile_id" not in profile or "version" not in profile:
            raise LinearResponseContractError(
                "scientific_profile requires profile_id and version"
            )
        required = {
            "campaign_id", "scientific_profile", "compatibility_registry",
            "declared_executable", "version_text_source",
        }
        missing = sorted(required - payload.keys())
        if missing:
            raise LinearResponseContractError("missing contract fields: " + ", ".join(missing))
        return cls(
            campaign_id=payload["campaign_id"],
            backend_id=payload.get("backend_id", "siesta"),
            scientific_profile=ScientificProfile(
                profile["profile_id"], profile["version"], profile.get("metadata", {})
            ),
            compatibility_registry=payload["compatibility_registry"],
            declared_executable=payload["declared_executable"],
            version_text_source=payload["version_text_source"],
        )

    @classmethod
    def from_json(cls, text: str) -> "LinearResponseBareCampaignContract":
        try:
            payload = json.loads(text)
        except (TypeError, json.JSONDecodeError) as exc:
            raise LinearResponseContractError("invalid campaign contract JSON") from exc
        return cls.from_dict(payload)

    def registry_path(self, root: str | Path) -> Path:
        base = Path(root).resolve()
        candidate = (base / self.compatibility_registry).resolve()
        try:
            candidate.relative_to(base)
        except ValueError as exc:
            raise LinearResponseContractError("compatibility registry escapes campaign root") from exc
        return candidate

    def version_text_path(self, root: str | Path) -> Path:
        base = Path(root).resolve()
        candidate = (base / self.version_text_source).resolve()
        try:
            candidate.relative_to(base)
        except ValueError as exc:
            raise LinearResponseContractError("version source escapes campaign root") from exc
        return candidate

    def load_registry(self, root: str | Path) -> BackendCompatibilityRegistry:
        path = self.registry_path(root)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise LinearResponseContractError(
                "declared compatibility registry cannot be read"
            ) from exc
        try:
            return BackendCompatibilityRegistry.from_dict(payload)
        except ValueError as exc:
            raise LinearResponseContractError("declared compatibility registry is invalid") from exc

    def admit(self, root: str | Path, identity: BackendIdentity) -> CompatibilityRecord:
        """Require exact backend/profile authorization; unknown means failure."""

        if identity.backend_id != self.backend_id:
            raise LinearResponseContractError("backend identity does not match contract")
        try:
            return self.load_registry(root).require_compatible(identity, self.scientific_profile)
        except ValueError as exc:
            raise LinearResponseContractError(str(exc)) from exc


__all__ = [
    "LinearResponseBareCampaignContract",
    "LinearResponseContractError",
]
