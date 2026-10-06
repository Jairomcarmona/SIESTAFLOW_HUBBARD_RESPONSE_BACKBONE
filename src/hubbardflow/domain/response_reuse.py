"""Declared scientific run identity and hash traceability for pilot reuse.

MPI layout and observable identity remain part of the key until independent
path validation proves equivalence. A strict-level run cannot stand in for base.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from enum import Enum
from hashlib import sha256
from typing import cast

from .hash_traceability import DigestWarning, digest_warning
from .perturbation_plan_evidence import identifier
from .symmetry_reduction import ResponseMode
from .validation import require_fdf_representable_ev


class ResponseReuseError(ValueError):
    """A reusable run must declare every scientific identity component."""


@dataclass(frozen=True)
class ResponseRunIdentity:
    schema: str
    effective_fdf_sha256: str | None
    parent_dm_sha256: str | None
    reference_node_digest: str | None
    target: str
    alpha_ev: float
    mode: ResponseMode
    dftu_record_sha256: str | None
    species_identity_sha256: str | None
    backend_identity: str
    backend_version: str
    scf_profile_sha256: str | None
    observable_id: str
    parser_version: str
    magnetic_state_sha256: str | None
    scientific_profile_sha256: str | None
    mpi_layout_sha256: str | None

    def __post_init__(self) -> None:
        try:
            if self.schema != "hubbardflow.response_run_identity.v1":
                raise ResponseReuseError("unsupported run identity schema")
            for key, value in asdict(self).items():
                if (
                    (key.endswith("sha256") or key == "reference_node_digest")
                    and value is not None
                    and not isinstance(value, str)
                ):
                    object.__setattr__(self, key, repr(value))
            for key in ("target", "backend_identity", "backend_version", "observable_id", "parser_version"):
                identifier(getattr(self, key), key)
            if not isinstance(self.mode, ResponseMode):
                raise ResponseReuseError("mode must be a ResponseMode")
            alpha = require_fdf_representable_ev(self.alpha_ev, "alpha_ev")
            if alpha == 0:
                raise ResponseReuseError("pilot reuse targets a nonzero response")
            object.__setattr__(self, "alpha_ev", alpha)
        except (ValueError, TypeError) as exc:
            raise ResponseReuseError(f"incomplete response identity: {exc}") from exc

    def to_mapping(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> ResponseRunIdentity:
        hashes = {
            name
            for name in cls.__dataclass_fields__
            if name.endswith("sha256") or name == "reference_node_digest"
        }
        if set(raw) - set(cls.__dataclass_fields__) or not set(cls.__dataclass_fields__) - hashes <= set(raw):
            raise ResponseReuseError("run identity needs the complete non-hash versioned fields")
        return cls(
            cast(str, raw["schema"]),
            cast(str | None, raw.get("effective_fdf_sha256")),
            cast(str | None, raw.get("parent_dm_sha256")),
            cast(str | None, raw.get("reference_node_digest")),
            cast(str, raw["target"]),
            cast(float, raw["alpha_ev"]),
            ResponseMode(cast(str, raw["mode"])),
            cast(str | None, raw.get("dftu_record_sha256")),
            cast(str | None, raw.get("species_identity_sha256")),
            cast(str, raw["backend_identity"]),
            cast(str, raw["backend_version"]),
            cast(str | None, raw.get("scf_profile_sha256")),
            cast(str, raw["observable_id"]),
            cast(str, raw["parser_version"]),
            cast(str | None, raw.get("magnetic_state_sha256")),
            cast(str | None, raw.get("scientific_profile_sha256")),
            cast(str | None, raw.get("mpi_layout_sha256")),
        )

    @property
    def traceability_warnings(self) -> tuple[DigestWarning, ...]:
        return tuple(
            warning
            for name, value in sorted(asdict(self).items())
            if name.endswith("sha256") or name == "reference_node_digest"
            if (warning := digest_warning(value, None, name)) is not None
        )

    @property
    def digest(self) -> str:
        return sha256(
            json.dumps(self.to_mapping(), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        ).hexdigest()


class ReuseStatus(str, Enum):
    EXACT_MATCH = "EXACT_MATCH"  # Historical serialized status; hashes cannot emit it.
    NOT_ESTABLISHED = "NOT_ESTABLISHED"
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"


class ReuseReason(str, Enum):
    PHYSICAL_CONTEXT_NOT_ESTABLISHED = "PHYSICAL_CONTEXT_NOT_ESTABLISHED"
    PHYSICAL_IDENTITY_MISMATCH = "PHYSICAL_IDENTITY_MISMATCH"
    HISTORICAL_IDENTITY_RECORD = "HISTORICAL_IDENTITY_RECORD"


@dataclass(frozen=True)
class ReuseQualification:
    status: ReuseStatus
    mismatched_fields: tuple[str, ...]
    traceability_warnings: tuple[DigestWarning, ...] = ()

    @property
    def reason(self) -> ReuseReason:
        if self.status is ReuseStatus.NOT_ESTABLISHED:
            return ReuseReason.PHYSICAL_CONTEXT_NOT_ESTABLISHED
        if self.status is ReuseStatus.IDENTITY_MISMATCH:
            return ReuseReason.PHYSICAL_IDENTITY_MISMATCH
        return ReuseReason.HISTORICAL_IDENTITY_RECORD

    def to_mapping(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "mismatched_fields": list(self.mismatched_fields),
            "reason": self.reason.value,
            "traceability_warnings": [x.to_mapping() for x in self.traceability_warnings],
        }

    @classmethod
    def from_mapping(cls, row: Mapping[str, object]) -> ReuseQualification:
        return cls(
            ReuseStatus(cast(str, row["status"])),
            tuple(cast(list[str], row["mismatched_fields"])),
            tuple(
                DigestWarning.from_mapping(x)
                for x in cast(list[Mapping[str, object]], row.get("traceability_warnings", []))
            ),
        )


def qualify_response_reuse(pilot: ResponseRunIdentity, production: ResponseRunIdentity) -> ReuseQualification:
    """Assess declared non-hash identity; absent physical values prevent reuse.

    SCF settings, projector definitions, magnetic state and MPI layout are only
    represented by digests in this v1 record. Their physical equivalence cannot
    be established by either matching or differing hashes. The conservative
    result is NOT_ESTABLISHED and a direct recalculation, never a campaign block.
    """
    if not isinstance(pilot, ResponseRunIdentity) or not isinstance(production, ResponseRunIdentity):
        raise ResponseReuseError("reuse requires complete typed identities")
    hash_fields = {
        name
        for name in pilot.__dataclass_fields__
        if name.endswith("sha256") or name == "reference_node_digest"
    }
    mismatches = tuple(
        sorted(
            name
            for name in set(pilot.__dataclass_fields__) - hash_fields
            if getattr(pilot, name) != getattr(production, name)
        )
    )
    warnings = [*pilot.traceability_warnings, *production.traceability_warnings]
    for name in sorted(hash_fields):
        warning = digest_warning(getattr(pilot, name), getattr(production, name), name)
        if warning is not None and warning not in warnings:
            warnings.append(warning)
    return ReuseQualification(
        ReuseStatus.IDENTITY_MISMATCH if mismatches else ReuseStatus.NOT_ESTABLISHED,
        mismatches,
        tuple(
            sorted(set(warnings), key=lambda x: (x.field, x.reason.value, x.recorded or "", x.observed or ""))
        ),
    )
