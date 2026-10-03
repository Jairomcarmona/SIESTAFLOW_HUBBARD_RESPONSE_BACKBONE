"""Select verified pilot artifacts by full identity; paths are provenance only.

The selector is not consumed by init/runner: their current contract supplies no
pilot source or producer of the complete receipt. Missing identity evidence must
remain NOT_ESTABLISHED; directory or response-node names never authorize reuse.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from pathlib import Path
from typing import cast

from hubbardflow.domain.response_reuse import ResponseRunIdentity, ReuseStatus, qualify_response_reuse
from hubbardflow.domain.validation import require_sha256


class CampaignPilotReuseError(ValueError):
    """Pilot evidence was changed or cannot be associated with validated bytes."""


@dataclass(frozen=True)
class PilotArtifact:
    identity: ResponseRunIdentity
    output: Path
    output_sha256: str
    validation_receipt_sha256: str
    validation_receipt: Path

    def __post_init__(self) -> None:
        require_sha256(self.output_sha256, "output_sha256")
        require_sha256(self.validation_receipt_sha256, "validation_receipt_sha256")

    def to_mapping(self) -> dict[str, object]:
        return {
            "identity": self.identity.to_mapping(),
            "output": str(self.output),
            "output_sha256": self.output_sha256,
            "validation_receipt_sha256": self.validation_receipt_sha256,
            "validation_receipt": str(self.validation_receipt),
        }

    @classmethod
    def from_mapping(cls, row: Mapping[str, object]) -> PilotArtifact:
        return cls(
            ResponseRunIdentity.from_mapping(cast(Mapping[str, object], row["identity"])),
            Path(cast(str, row["output"])),
            cast(str, row["output_sha256"]),
            cast(str, row["validation_receipt_sha256"]),
            Path(cast(str, row["validation_receipt"])),
        )


@dataclass(frozen=True)
class PilotReuse:
    artifact: PilotArtifact | None

    @property
    def status(self) -> PilotReuseStatus:
        return (
            PilotReuseStatus.NOT_ESTABLISHED
            if self.artifact is None
            else PilotReuseStatus.VALIDATED_EXACT_MATCH
        )

    def to_mapping(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "artifact": None if self.artifact is None else self.artifact.to_mapping(),
        }

    @classmethod
    def from_mapping(cls, row: Mapping[str, object]) -> PilotReuse:
        raw = row["artifact"]
        result = cls(None if raw is None else PilotArtifact.from_mapping(cast(Mapping[str, object], raw)))
        if row["status"] != result.status.value:
            raise CampaignPilotReuseError("reuse status disagrees with the available pilot evidence")
        return result


class PilotReuseStatus(str, Enum):
    NOT_ESTABLISHED = "NOT_ESTABLISHED"
    VALIDATED_EXACT_MATCH = "VALIDATED_EXACT_MATCH"


def select_campaign_pilot(production: ResponseRunIdentity, pilots: Sequence[PilotArtifact]) -> PilotReuse:
    """Select deterministic receipt-bound artifacts, rejecting conflicting evidence.

    Every matching pilot must retain the bytes validated by its receipt. Distinct
    outputs for the same experiment cannot be resolved by choosing a filename.
    """
    matches = [
        p for p in pilots if qualify_response_reuse(p.identity, production).status is ReuseStatus.EXACT_MATCH
    ]
    for pilot in matches:
        if not pilot.output.is_file() or sha256(pilot.output.read_bytes()).hexdigest() != pilot.output_sha256:
            raise CampaignPilotReuseError("pilot output changed after validation")
        try:
            content = pilot.validation_receipt.read_bytes()
            receipt = json.loads(content)
            if (
                sha256(content).hexdigest() != pilot.validation_receipt_sha256
                or receipt["schema"] != "hubbardflow.validated_pilot_response.v1"
                or receipt["state"] != "VALIDATED"
                or receipt["run_identity_digest"] != pilot.identity.digest
                or receipt["output_sha256"] != pilot.output_sha256
            ):
                raise CampaignPilotReuseError("pilot validation receipt identity disagrees")
        except (OSError, ValueError, TypeError, KeyError) as exc:
            raise CampaignPilotReuseError(f"pilot receipt cannot establish reuse: {exc}") from exc
    if len({p.output_sha256 for p in matches}) > 1:
        raise CampaignPilotReuseError("conflicting validated pilots for the same scientific identity")
    ordered = sorted(matches, key=lambda p: (p.output_sha256, p.validation_receipt_sha256, str(p.output)))
    return PilotReuse(ordered[0] if ordered else None)
