"""Typed, non-decisional records for stored artifact digest discrepancies.

A digest identifies bytes, never an electronic state. Missing, malformed or
different digest metadata is retained here without asserting physical validity.
Callers must assess parsing, convergence and semantic identities separately.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import cast

from .validation import ValidationError, require_sha256


class HashTraceabilityError(ValueError):
    """A warning record has an invalid structural schema."""


class DigestWarningReason(str, Enum):
    ABSENT = "ARTIFACT_DIGEST_ABSENT"
    MALFORMED = "ARTIFACT_DIGEST_MALFORMED"
    MISMATCH = "ARTIFACT_DIGEST_MISMATCH"


@dataclass(frozen=True)
class DigestWarning:
    field: str
    reason: DigestWarningReason
    recorded: str | None
    observed: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.field, str) or not self.field:
            raise HashTraceabilityError("digest warning field must be a non-empty string")
        if not isinstance(self.reason, DigestWarningReason):
            raise HashTraceabilityError("digest warning reason must be a DigestWarningReason")
        if any(value is not None and not isinstance(value, str) for value in (self.recorded, self.observed)):
            raise HashTraceabilityError("digest warning values must be strings or null")

    def to_mapping(self) -> dict[str, str | None]:
        return {
            "field": self.field,
            "reason": self.reason.value,
            "recorded": self.recorded,
            "observed": self.observed,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> DigestWarning:
        try:
            return cls(
                cast(str, value["field"]),
                DigestWarningReason(value["reason"]),
                cast(str | None, value["recorded"]),
                cast(str | None, value["observed"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise HashTraceabilityError(f"invalid digest warning: {exc}") from exc


def digest_warning(recorded: object, observed: str | None, field: str) -> DigestWarning | None:
    """Record metadata discrepancies without making an acceptance decision."""
    retained = recorded if isinstance(recorded, str) or recorded is None else repr(recorded)
    if recorded is None or isinstance(recorded, str) and not recorded:
        return DigestWarning(field, DigestWarningReason.ABSENT, retained, observed)
    try:
        require_sha256(recorded, field)
    except ValidationError:
        return DigestWarning(field, DigestWarningReason.MALFORMED, retained, observed)
    if observed is not None and recorded != observed:
        return DigestWarning(field, DigestWarningReason.MISMATCH, retained, observed)
    return None


@dataclass(frozen=True)
class TraceableComparison:
    """Exact semantic equality with digest fields excluded and discrepancies retained."""

    equivalent: bool
    warnings: tuple[DigestWarning, ...]


def compare_traceable_mappings(
    left: Mapping[str, object], right: Mapping[str, object]
) -> TraceableComparison:
    """Compare stored semantic values, never using hash metadata as a proxy.

    This is structural equality of already parsed values, not a numerical
    equivalence rule. Physical tolerances remain the responsibility of the
    scientific decision consuming those values.
    """
    warnings: list[DigestWarning] = []

    def project(value: object, other: object, path: str) -> object:
        if isinstance(value, Mapping):
            peer = other if isinstance(other, Mapping) else {}
            result: dict[str, object] = {}
            for key in sorted(set(value) | set(peer)):
                field = f"{path}.{key}" if path else str(key)
                if str(key).endswith(("sha256", "digest", "digests")) and key not in {
                    "identity_digest",
                    "species_identity_digests",
                }:
                    recorded = value.get(key)
                    observed = peer.get(key)
                    if isinstance(recorded, (tuple, list)):
                        for i, item in enumerate(recorded):
                            warning = digest_warning(item, None, f"{field}[{i}]")
                            if warning is not None:
                                warnings.append(warning)
                    else:
                        warning = digest_warning(
                            recorded, observed if isinstance(observed, str) else None, field
                        )
                        if warning is not None:
                            warnings.append(warning)
                elif key != "traceability_warnings":
                    if key in value:
                        result[str(key)] = project(value[key], peer.get(key), field)
            return result
        if isinstance(value, (list, tuple)):
            peer_rows = other if isinstance(other, (list, tuple)) else ()
            return tuple(
                project(x, peer_rows[i] if i < len(peer_rows) else None, f"{path}[{i}]")
                for i, x in enumerate(value)
            )
        return value

    left_semantic = project(left, right, "")
    right_semantic = project(right, left, "")
    return TraceableComparison(
        left_semantic == right_semantic,
        tuple(
            sorted(set(warnings), key=lambda x: (x.field, x.reason.value, x.recorded or "", x.observed or ""))
        ),
    )
