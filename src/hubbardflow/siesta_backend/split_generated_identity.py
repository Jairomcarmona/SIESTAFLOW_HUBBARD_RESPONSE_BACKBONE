"""Exact file identity receipts for user-run SIESTA alias generation.

This comparison proves only byte identity of the supplied ion files. It cannot
prove that SIESTA generated them, that SCF converged, or that a campaign is READY.
Normalized label hashes are diagnostic; only exact raw SHA256 equality passes.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from pathlib import Path
from typing import cast

from hubbardflow.domain.validation import require_sha256
from hubbardflow.siesta_backend.semantic_ion_identity import IonIdentityError, canonical_ion_bytes


class SplitIdentityError(ValueError):
    """Requested labels or receipt data cannot identify unique generated files."""


class SplitIdentityStatus(str, Enum):
    EXACT_ION_BYTES_MATCH = "EXACT_ION_BYTES_MATCH"
    SPECIES_IDENTITY_NOT_ESTABLISHED = "SPECIES_IDENTITY_NOT_ESTABLISHED"


class SplitIdentityReason(str, Enum):
    ION_MISSING = "ION_MISSING"
    ION_DUPLICATE = "ION_DUPLICATE"
    ION_UNREADABLE = "ION_UNREADABLE"
    ION_BYTES_DIFFER = "ION_BYTES_DIFFER"


def _label(value: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", value):
        raise SplitIdentityError("original and alias labels must be safe ASCII species labels")


@dataclass(frozen=True)
class GeneratedIonDigest:
    label: str
    raw_sha256: str | None
    diagnostic_canonical_sha256: str | None
    relative_paths: tuple[str, ...]
    reason: SplitIdentityReason | None

    def __post_init__(self) -> None:
        _label(self.label)
        try:
            for digest in (self.raw_sha256, self.diagnostic_canonical_sha256):
                if digest is not None:
                    require_sha256(digest, "generated ion")
        except ValueError as exc:
            raise SplitIdentityError(str(exc)) from exc
        if self.reason is not None and not isinstance(self.reason, SplitIdentityReason):
            raise SplitIdentityError("ion reason must be an enum")
        if any(not isinstance(path, str) or not path for path in self.relative_paths):
            raise SplitIdentityError("ion paths must be nonempty strings")
        if tuple(sorted(set(self.relative_paths))) != self.relative_paths:
            raise SplitIdentityError("ion paths must be unique and sorted")
        if self.reason is None and (self.raw_sha256 is None or len(self.relative_paths) != 1):
            raise SplitIdentityError("a readable ion digest requires one unique file")
        if self.reason is not None and self.raw_sha256 is not None:
            raise SplitIdentityError("missing, duplicate or unreadable ions cannot carry a digest")

    def to_mapping(self) -> dict[str, object]:
        return {
            "label": self.label,
            "raw_sha256": self.raw_sha256,
            "diagnostic_canonical_sha256": self.diagnostic_canonical_sha256,
            "relative_paths": list(self.relative_paths),
            "reason": None if self.reason is None else self.reason.value,
        }

    @classmethod
    def from_mapping(cls, row: Mapping[str, object]) -> GeneratedIonDigest:
        try:
            if set(row) != {"label", "raw_sha256", "diagnostic_canonical_sha256", "relative_paths", "reason"}:
                raise SplitIdentityError("unexpected ion digest fields")
            return cls(
                cast(str, row["label"]),
                cast(str | None, row["raw_sha256"]),
                cast(str | None, row["diagnostic_canonical_sha256"]),
                tuple(cast(Sequence[str], row["relative_paths"])),
                None if row["reason"] is None else SplitIdentityReason(cast(str, row["reason"])),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise SplitIdentityError(f"invalid ion digest mapping: {exc}") from exc


@dataclass(frozen=True)
class GeneratedSplitIdentity:
    original: GeneratedIonDigest
    aliases: tuple[GeneratedIonDigest, ...]
    status: SplitIdentityStatus
    reasons: tuple[SplitIdentityReason, ...]
    version: str = "hubbardflow.generated_split_identity.v1"

    def __post_init__(self) -> None:
        if not isinstance(self.original, GeneratedIonDigest) or not isinstance(self.aliases, tuple):
            raise SplitIdentityError("receipt needs a typed original and immutable alias records")
        if any(not isinstance(item, GeneratedIonDigest) for item in self.aliases):
            raise SplitIdentityError("alias records must be GeneratedIonDigest values")
        labels = tuple(item.label for item in self.aliases)
        if (
            self.version != "hubbardflow.generated_split_identity.v1"
            or not labels
            or labels != tuple(sorted(set(labels)))
            or self.original.label in labels
            or not isinstance(self.status, SplitIdentityStatus)
        ):
            raise SplitIdentityError("invalid generated identity version, status or alias labels")
        expected = {item.reason for item in (self.original, *self.aliases) if item.reason is not None}
        if self.original.raw_sha256 is not None and any(
            item.raw_sha256 is not None and item.raw_sha256 != self.original.raw_sha256
            for item in self.aliases
        ):
            expected.add(SplitIdentityReason.ION_BYTES_DIFFER)
        if self.reasons != tuple(sorted(expected, key=lambda reason: reason.value)):
            raise SplitIdentityError("receipt reasons disagree with file digests")
        status = (
            SplitIdentityStatus.SPECIES_IDENTITY_NOT_ESTABLISHED
            if expected
            else SplitIdentityStatus.EXACT_ION_BYTES_MATCH
        )
        if self.status is not status:
            raise SplitIdentityError("receipt verdict disagrees with exact raw SHA256 identity")

    def to_mapping(self) -> dict[str, object]:
        return {
            "version": self.version,
            "original": self.original.to_mapping(),
            "aliases": [item.to_mapping() for item in self.aliases],
            "status": self.status.value,
            "reason_codes": [reason.value for reason in self.reasons],
        }

    @classmethod
    def from_mapping(cls, row: Mapping[str, object]) -> GeneratedSplitIdentity:
        try:
            if set(row) != {"version", "original", "aliases", "status", "reason_codes"}:
                raise SplitIdentityError("unexpected generated receipt fields")
            return cls(
                GeneratedIonDigest.from_mapping(cast(Mapping[str, object], row["original"])),
                tuple(
                    GeneratedIonDigest.from_mapping(item)
                    for item in cast(Sequence[Mapping[str, object]], row["aliases"])
                ),
                SplitIdentityStatus(cast(str, row["status"])),
                tuple(SplitIdentityReason(item) for item in cast(Sequence[str], row["reason_codes"])),
                cast(str, row["version"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise SplitIdentityError(f"invalid generated identity receipt: {exc}") from exc

    @property
    def digest(self) -> str:
        return sha256(
            json.dumps(self.to_mapping(), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        ).hexdigest()


def _digest(directory: Path, label: str) -> GeneratedIonDigest:
    try:
        # Multiple matching files are ambiguous even if their bytes agree.
        files = tuple(sorted(directory.rglob(f"{label}.ion"), key=str)) if directory.is_dir() else ()
        paths = tuple(sorted(path.relative_to(directory).as_posix() for path in files))
        if not files:
            return GeneratedIonDigest(label, None, None, (), SplitIdentityReason.ION_MISSING)
        if len(files) != 1:
            return GeneratedIonDigest(label, None, None, paths, SplitIdentityReason.ION_DUPLICATE)
        data = files[0].read_bytes()
    except OSError:
        return GeneratedIonDigest(label, None, None, (), SplitIdentityReason.ION_UNREADABLE)
    try:
        canonical = sha256(canonical_ion_bytes(data, label)).hexdigest()
    except IonIdentityError:
        canonical = None
    return GeneratedIonDigest(label, sha256(data).hexdigest(), canonical, paths, None)


def verify_generated_split_identity(
    run_directory: Path,
    original_label: str,
    alias_labels: Sequence[str],
    *,
    reference_directory: Path | None = None,
) -> GeneratedSplitIdentity:
    """Compare one unique original ion and each alias without writing or running SIESTA.

    The optional reference directory holds the original run's ion. The caller
    must ensure aliases are actual generated outputs, not staged reference copies.
    """
    _label(original_label)
    aliases = tuple(alias_labels)
    for alias in aliases:
        _label(alias)
    if not aliases or len(set(aliases)) != len(aliases) or original_label in aliases:
        raise SplitIdentityError("supply unique aliases distinct from the original label")
    original = _digest(run_directory if reference_directory is None else reference_directory, original_label)
    records = tuple(_digest(run_directory, label) for label in sorted(aliases))
    reasons = {item.reason for item in (original, *records) if item.reason is not None}
    if original.raw_sha256 is not None and any(
        item.raw_sha256 is not None and item.raw_sha256 != original.raw_sha256 for item in records
    ):
        reasons.add(SplitIdentityReason.ION_BYTES_DIFFER)
    return GeneratedSplitIdentity(
        original,
        records,
        SplitIdentityStatus.SPECIES_IDENTITY_NOT_ESTABLISHED
        if reasons
        else SplitIdentityStatus.EXACT_ION_BYTES_MATCH,
        tuple(sorted(reasons, key=lambda reason: reason.value)),
    )
