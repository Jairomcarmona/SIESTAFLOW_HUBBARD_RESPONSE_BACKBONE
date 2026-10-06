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

from hubbardflow.domain.hash_traceability import DigestWarning, digest_warning
from hubbardflow.domain.response_reuse import ResponseRunIdentity, ReuseStatus, qualify_response_reuse


class CampaignPilotReuseError(ValueError):
    """Pilot evidence cannot be associated with a valid structural receipt."""


@dataclass(frozen=True)
class PilotArtifact:
    identity: ResponseRunIdentity
    output: Path
    output_sha256: str | None
    validation_receipt_sha256: str | None
    validation_receipt: Path

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
            cast(str | None, row.get("output_sha256")),
            cast(str | None, row.get("validation_receipt_sha256")),
            Path(cast(str, row["validation_receipt"])),
        )


class PilotReuseReason(str, Enum):
    PHYSICAL_CONTEXT_NOT_ESTABLISHED = "PHYSICAL_CONTEXT_NOT_ESTABLISHED"
    PHYSICAL_IDENTITY_MISMATCH = "PHYSICAL_IDENTITY_MISMATCH"
    PILOT_EVIDENCE_UNREADABLE = "PILOT_EVIDENCE_UNREADABLE"
    PILOT_RECEIPT_NOT_VALIDATED = "PILOT_RECEIPT_NOT_VALIDATED"


@dataclass(frozen=True)
class PilotReuse:
    artifact: PilotArtifact | None
    traceability_warnings: tuple[DigestWarning, ...] = ()
    reason_codes: tuple[PilotReuseReason, ...] = ()

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
            "traceability_warnings": [x.to_mapping() for x in self.traceability_warnings],
            "reason_codes": [x.value for x in self.reason_codes],
        }

    @classmethod
    def from_mapping(cls, row: Mapping[str, object]) -> PilotReuse:
        raw = row["artifact"]
        result = cls(
            None if raw is None else PilotArtifact.from_mapping(cast(Mapping[str, object], raw)),
            tuple(
                DigestWarning.from_mapping(x)
                for x in cast(list[Mapping[str, object]], row.get("traceability_warnings", []))
            ),
            tuple(PilotReuseReason(x) for x in cast(list[str], row.get("reason_codes", []))),
        )
        if row["status"] != result.status.value:
            raise CampaignPilotReuseError("reuse status disagrees with the available pilot evidence")
        return result


class PilotReuseStatus(str, Enum):
    NOT_ESTABLISHED = "NOT_ESTABLISHED"
    VALIDATED_EXACT_MATCH = "VALIDATED_EXACT_MATCH"


def select_campaign_pilot(production: ResponseRunIdentity, pilots: Sequence[PilotArtifact]) -> PilotReuse:
    """Revalidate available receipt semantics; missing physical context means recalculate.

    Hash discrepancies are recorded only. This standalone v1 pilot format does
    not carry the physical SCF/projector/state/MPI values needed for reuse, and
    is not wired into init/runner. Equal digests do not supply those values.
    """
    warnings: list[DigestWarning] = []
    reasons = {PilotReuseReason.PHYSICAL_CONTEXT_NOT_ESTABLISHED}
    for pilot in sorted(pilots, key=lambda p: str(p.output)):
        qualification = qualify_response_reuse(pilot.identity, production)
        warnings.extend(qualification.traceability_warnings)
        if qualification.status is ReuseStatus.IDENTITY_MISMATCH:
            reasons.add(PilotReuseReason.PHYSICAL_IDENTITY_MISMATCH)
            continue
        try:
            output_hash = sha256(pilot.output.read_bytes()).hexdigest()
            content = pilot.validation_receipt.read_bytes()
            receipt = json.loads(content)
        except (OSError, ValueError, TypeError):
            reasons.add(PilotReuseReason.PILOT_EVIDENCE_UNREADABLE)
            continue
        for recorded, observed, field in (
            (pilot.output_sha256, output_hash, "pilot_output_sha256"),
            (pilot.validation_receipt_sha256, sha256(content).hexdigest(), "pilot_receipt_sha256"),
            (
                receipt.get("run_identity_digest") if isinstance(receipt, dict) else None,
                pilot.identity.digest,
                "run_identity_digest",
            ),
            (
                receipt.get("output_sha256") if isinstance(receipt, dict) else None,
                output_hash,
                "receipt_output_sha256",
            ),
        ):
            warning = digest_warning(recorded, observed, field)
            if warning is not None:
                warnings.append(warning)
        if (
            not isinstance(receipt, dict)
            or receipt.get("schema") != "hubbardflow.validated_pilot_response.v1"
            or receipt.get("state") != "VALIDATED"
        ):
            reasons.add(PilotReuseReason.PILOT_RECEIPT_NOT_VALIDATED)
    return PilotReuse(
        None,
        tuple(
            sorted(set(warnings), key=lambda x: (x.field, x.reason.value, x.recorded or "", x.observed or ""))
        ),
        tuple(sorted(reasons, key=lambda x: x.value)),
    )
