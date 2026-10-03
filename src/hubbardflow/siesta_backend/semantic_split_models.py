"""Versioned opt-in and pending evidence records for species materialization."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum

from hubbardflow.domain.validation import ValidationError, require_sha256


class SemanticSplitCode(str, Enum):
    SHARED_LABEL_NEEDS_SPLIT = "SHARED_LABEL_NEEDS_SPLIT"
    SPECIES_IDENTITY_NOT_ESTABLISHED = "SPECIES_IDENTITY_NOT_ESTABLISHED"
    INVALID_SPLIT_INPUT = "INVALID_SPLIT_INPUT"


class SemanticSplitStatus(str, Enum):
    STAGED_PENDING_GENERATED_IDENTITY = "STAGED_PENDING_GENERATED_IDENTITY"


class SemanticSpeciesSplitError(ValueError):
    def __init__(self, code: SemanticSplitCode, message: str) -> None:
        self.code = code
        super().__init__(f"{code.value}: {message}")


@dataclass(frozen=True)
class SemanticSpeciesSplitPolicy:
    """The versioned opt-in must enter the eventual production plan digest."""

    auto_split_species: bool = False
    version: str = "semantic-species-split-v1"

    def __post_init__(self) -> None:
        if type(self.auto_split_species) is not bool or self.version != "semantic-species-split-v1":
            raise SemanticSpeciesSplitError(SemanticSplitCode.INVALID_SPLIT_INPUT, "invalid split policy")

    def to_mapping(self) -> dict[str, object]:
        return {"version": self.version, "auto_split_species": self.auto_split_species}

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> SemanticSpeciesSplitPolicy:
        if (
            set(value) != {"version", "auto_split_species"}
            or type(value["auto_split_species"]) is not bool
            or not isinstance(value["version"], str)
        ):
            raise SemanticSpeciesSplitError(SemanticSplitCode.INVALID_SPLIT_INPUT, "invalid policy mapping")
        return cls(value["auto_split_species"] is True, str(value["version"]))

    @property
    def digest(self) -> str:
        return hashlib.sha256(json.dumps(self.to_mapping(), sort_keys=True).encode()).hexdigest()


DISABLED_SEMANTIC_SPLIT_POLICY = SemanticSpeciesSplitPolicy()


@dataclass(frozen=True)
class SemanticSpeciesIdentityEvidence:
    """File-content identity only; no assertion about execution or convergence."""

    identity_digest: str
    labels: tuple[str, ...]

    def __post_init__(self) -> None:
        try:
            require_sha256(self.identity_digest, "semantic identity")
        except ValidationError as exc:
            raise SemanticSpeciesSplitError(SemanticSplitCode.INVALID_SPLIT_INPUT, str(exc)) from exc
        if (
            not self.labels
            or len(set(self.labels)) != len(self.labels)
            or any(not isinstance(label, str) or not label for label in self.labels)
        ):
            raise SemanticSpeciesSplitError(
                SemanticSplitCode.INVALID_SPLIT_INPUT, "invalid comparison labels"
            )

    @property
    def identities(self) -> tuple[tuple[str, str], ...]:
        return tuple((label, self.identity_digest) for label in self.labels)

    def to_mapping(self) -> dict[str, object]:
        return {"identity_digest": self.identity_digest, "labels": list(self.labels)}

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> SemanticSpeciesIdentityEvidence:
        labels = value.get("labels")
        digest = value.get("identity_digest")
        if (
            set(value) != {"identity_digest", "labels"}
            or not isinstance(digest, str)
            or not isinstance(labels, list)
            or any(not isinstance(label, str) for label in labels)
        ):
            raise SemanticSpeciesSplitError(
                SemanticSplitCode.INVALID_SPLIT_INPUT, "invalid comparison mapping"
            )
        return cls(digest, tuple(labels))


@dataclass(frozen=True)
class SemanticSpeciesSplitResult:
    content: str
    labels: tuple[str, ...]
    source_identity_digest: str
    split_identity_digests: tuple[tuple[str, str], ...]
    source_fdf_sha256: str
    materialized_fdf_sha256: str
    policy_digest: str
    status: SemanticSplitStatus = SemanticSplitStatus.STAGED_PENDING_GENERATED_IDENTITY

    def __post_init__(self) -> None:
        if (
            not isinstance(self.content, str)
            or not self.labels
            or len(set(self.labels)) != len(self.labels)
            or not isinstance(self.status, SemanticSplitStatus)
            or self.status != SemanticSplitStatus.STAGED_PENDING_GENERATED_IDENTITY
        ):
            raise SemanticSpeciesSplitError(
                SemanticSplitCode.INVALID_SPLIT_INPUT, "invalid pending split result"
            )
        try:
            for name in (
                "source_identity_digest",
                "source_fdf_sha256",
                "materialized_fdf_sha256",
                "policy_digest",
            ):
                require_sha256(getattr(self, name), name)
            for _, digest in self.split_identity_digests:
                require_sha256(digest, "split identity")
        except ValidationError as exc:
            raise SemanticSpeciesSplitError(SemanticSplitCode.INVALID_SPLIT_INPUT, str(exc)) from exc
        if tuple(label for label, _ in self.split_identity_digests) != self.labels or any(
            digest != self.source_identity_digest for _, digest in self.split_identity_digests
        ):
            raise SemanticSpeciesSplitError(
                SemanticSplitCode.INVALID_SPLIT_INPUT, "split identities do not match reference"
            )
        if self.materialized_fdf_sha256 != hashlib.sha256(self.content.encode()).hexdigest():
            raise SemanticSpeciesSplitError(
                SemanticSplitCode.INVALID_SPLIT_INPUT, "result content digest mismatch"
            )

    def to_mapping(self) -> dict[str, object]:
        return {
            "content": self.content,
            "labels": list(self.labels),
            "source_identity_digest": self.source_identity_digest,
            "split_identity_digests": [list(item) for item in self.split_identity_digests],
            "source_fdf_sha256": self.source_fdf_sha256,
            "materialized_fdf_sha256": self.materialized_fdf_sha256,
            "policy_digest": self.policy_digest,
            "status": self.status.value,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> SemanticSpeciesSplitResult:
        keys = {
            "content",
            "labels",
            "source_identity_digest",
            "split_identity_digests",
            "source_fdf_sha256",
            "materialized_fdf_sha256",
            "policy_digest",
            "status",
        }
        if set(value) != keys or any(
            not isinstance(value[key], str) for key in keys - {"labels", "split_identity_digests"}
        ):
            raise SemanticSpeciesSplitError(SemanticSplitCode.INVALID_SPLIT_INPUT, "invalid result mapping")
        labels = value["labels"]
        pairs = value["split_identity_digests"]
        if (
            not isinstance(labels, list)
            or any(not isinstance(label, str) for label in labels)
            or not isinstance(pairs, list)
        ):
            raise SemanticSpeciesSplitError(
                SemanticSplitCode.INVALID_SPLIT_INPUT, "invalid labels/identities"
            )
        parsed_pairs: list[tuple[str, str]] = []
        for pair in pairs:
            if (
                not isinstance(pair, list)
                or len(pair) != 2
                or any(not isinstance(item, str) for item in pair)
            ):
                raise SemanticSpeciesSplitError(
                    SemanticSplitCode.INVALID_SPLIT_INPUT, "invalid identity pair"
                )
            parsed_pairs.append((pair[0], pair[1]))
        try:
            status = SemanticSplitStatus(str(value["status"]))
        except ValueError as exc:
            raise SemanticSpeciesSplitError(
                SemanticSplitCode.INVALID_SPLIT_INPUT, "unknown split status"
            ) from exc
        return cls(
            str(value["content"]),
            tuple(labels),
            str(value["source_identity_digest"]),
            tuple(parsed_pairs),
            str(value["source_fdf_sha256"]),
            str(value["materialized_fdf_sha256"]),
            str(value["policy_digest"]),
            status,
        )
