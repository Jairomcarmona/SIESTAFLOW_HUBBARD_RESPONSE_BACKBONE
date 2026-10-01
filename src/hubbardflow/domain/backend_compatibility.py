"""Versioned scientific-backend compatibility registry.

This module contains only domain data.  It intentionally knows nothing about
Slurm, module names, filesystem paths, or executable discovery.  A backend is
accepted only when its exact versioned identity is present in an explicit
registry entry; unknown identities never inherit a nearby entry.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping


class BackendCompatibilityError(ValueError):
    """Raised when a compatibility decision cannot safely authorize a run."""


class CompatibilityState(str, Enum):
    COMPATIBLE = "compatible"
    UNKNOWN = "unknown"
    BLOCKED = "blocked"


def _freeze(value: Any) -> Any:
    """Recursively freeze JSON-like metadata for a truly immutable record."""
    if isinstance(value, Mapping):
        return MappingProxyType({str(k): _freeze(v) for k, v in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(v) for v in value)
    if isinstance(value, tuple):
        return tuple(_freeze(v) for v in value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise TypeError(f"unsupported metadata value: {type(value).__name__}")


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _thaw(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [_thaw(v) for v in value]
    return value


@dataclass(frozen=True)
class BackendIdentity:
    """Identity of a backend implementation, independent of its location."""

    backend_id: str
    version: str
    executable_sha256: str | None = None

    def __post_init__(self) -> None:
        if not self.backend_id.strip() or not self.version.strip():
            raise BackendCompatibilityError("backend_id and version are required")
        if self.executable_sha256 is not None:
            digest = self.executable_sha256.lower()
            if not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise BackendCompatibilityError(
                    "executable_sha256 must be a 64-character hexadecimal SHA-256"
                )
            object.__setattr__(self, "executable_sha256", digest)

    @property
    def key(self) -> tuple[str, str, str | None]:
        return (self.backend_id, self.version, self.executable_sha256)


@dataclass(frozen=True)
class ScientificProfile:
    """Versioned meaning of the physics a backend entry is allowed to claim."""

    profile_id: str
    version: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.profile_id.strip() or not self.version.strip():
            raise BackendCompatibilityError("profile_id and version are required")
        object.__setattr__(self, "metadata", _freeze(self.metadata))

    @property
    def key(self) -> tuple[str, str]:
        return (self.profile_id, self.version)


@dataclass(frozen=True)
class CompatibilityRecord:
    identity: BackendIdentity
    profile: ScientificProfile
    state: CompatibilityState
    reason: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.state, CompatibilityState):
            try:
                object.__setattr__(self, "state", CompatibilityState(self.state))
            except ValueError as exc:
                raise BackendCompatibilityError("invalid compatibility state") from exc
        if self.state is CompatibilityState.COMPATIBLE and not self.reason:
            object.__setattr__(self, "reason", "explicitly registered")

    def to_dict(self) -> dict[str, Any]:
        return {
            "backend": {
                "backend_id": self.identity.backend_id,
                "version": self.identity.version,
                "executable_sha256": self.identity.executable_sha256,
            },
            "profile": {
                "profile_id": self.profile.profile_id,
                "version": self.profile.version,
                "metadata": _thaw(self.profile.metadata),
            },
            "state": self.state.value,
            "reason": self.reason,
        }


def _record_sort_key(record: CompatibilityRecord) -> tuple[str, str, str, str, str, str]:
    identity = record.identity
    profile = record.profile
    return (
        identity.backend_id,
        identity.version,
        identity.executable_sha256 or "",
        profile.profile_id,
        profile.version,
        record.state.value,
    )


@dataclass(frozen=True)
class BackendCompatibilityRegistry:
    """Immutable allowlist with fail-closed resolution."""

    records: tuple[CompatibilityRecord, ...] = ()

    def __post_init__(self) -> None:
        records = tuple(self.records)
        keys = [(r.identity.key, r.profile.key) for r in records]
        if len(set(keys)) != len(keys):
            raise BackendCompatibilityError("duplicate backend/profile registry entry")
        object.__setattr__(self, "records", records)

    def add(self, record: CompatibilityRecord) -> "BackendCompatibilityRegistry":
        """Return a new registry; the current registry is never mutated."""
        return BackendCompatibilityRegistry(self.records + (record,))

    def resolve(
        self,
        identity: BackendIdentity,
        profile: ScientificProfile | tuple[str, str] | None = None,
    ) -> CompatibilityRecord:
        """Resolve exact identity/profile, returning UNKNOWN when absent.

        No version, hash, or profile is inferred.  A hashless identity matches
        only an explicitly hashless record; it cannot match a hashed record.
        """
        profile_key = profile.key if isinstance(profile, ScientificProfile) else profile
        matches = [
            record for record in self.records
            if record.identity.key == identity.key
            and (profile_key is None or record.profile.key == profile_key)
        ]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise BackendCompatibilityError("ambiguous compatibility registry resolution")
        requested_profile = profile_key or ("unspecified", "unspecified")
        return CompatibilityRecord(
            identity=identity,
            profile=ScientificProfile(*requested_profile),
            state=CompatibilityState.UNKNOWN,
            reason="backend identity/profile is not explicitly registered",
        )

    def require_compatible(
        self,
        identity: BackendIdentity,
        profile: ScientificProfile | tuple[str, str] | None = None,
    ) -> CompatibilityRecord:
        record = self.resolve(identity, profile)
        if record.state is not CompatibilityState.COMPATIBLE:
            raise BackendCompatibilityError(
                f"backend is not authorized: {record.state.value}: {record.reason}"
            )
        return record

    def to_dict(self) -> dict[str, Any]:
        ordered = sorted(self.records, key=_record_sort_key)
        return {"schema": "backend_compatibility_v1", "records": [r.to_dict() for r in ordered]}

    def to_json(self) -> str:
        """Canonical JSON suitable for hashing and reproducibility records."""
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=True)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "BackendCompatibilityRegistry":
        """Load the explicit compatibility matrix; malformed data never defaults open."""
        if not isinstance(payload, Mapping) or payload.get("schema") != "backend_compatibility_v1":
            raise BackendCompatibilityError("unknown backend compatibility registry schema")
        entries = payload.get("records")
        if not isinstance(entries, list):
            raise BackendCompatibilityError("registry records must be a list")
        records = []
        for entry in entries:
            try:
                backend, profile = entry["backend"], entry["profile"]
                if not isinstance(backend, Mapping) or not isinstance(profile, Mapping):
                    raise TypeError("record fields are not mappings")
                identity = BackendIdentity(
                    backend["backend_id"], backend["version"], backend.get("executable_sha256")
                )
                scientific = ScientificProfile(
                    profile["profile_id"], profile["version"], profile.get("metadata", {})
                )
                records.append(CompatibilityRecord(
                    identity, scientific, CompatibilityState(entry["state"]), entry.get("reason", "")
                ))
            except (KeyError, TypeError, ValueError) as exc:
                raise BackendCompatibilityError("malformed compatibility registry record") from exc
        return cls(tuple(records))

    @classmethod
    def from_json(cls, text: str) -> "BackendCompatibilityRegistry":
        try:
            payload = json.loads(text)
        except (TypeError, json.JSONDecodeError) as exc:
            raise BackendCompatibilityError("invalid compatibility registry JSON") from exc
        return cls.from_dict(payload)

    def sha256(self) -> str:
        return hashlib.sha256(self.to_json().encode("utf-8")).hexdigest()
