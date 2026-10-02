"""Exact scientific run identity for pilot-to-production reuse (§I.9 / §Q).

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

from .perturbation_plan_evidence import identifier
from .symmetry_reduction import ResponseMode
from .validation import require_fdf_representable_ev, require_sha256


class ResponseReuseError(ValueError):
    """A reusable run must declare every scientific identity component."""


@dataclass(frozen=True)
class ResponseRunIdentity:
    schema: str
    effective_fdf_sha256: str
    parent_dm_sha256: str
    reference_node_digest: str
    target: str
    alpha_ev: float
    mode: ResponseMode
    dftu_record_sha256: str
    species_identity_sha256: str
    backend_identity: str
    backend_version: str
    scf_profile_sha256: str
    observable_id: str
    parser_version: str
    magnetic_state_sha256: str
    scientific_profile_sha256: str
    mpi_layout_sha256: str

    def __post_init__(self) -> None:
        try:
            if self.schema != "hubbardflow.response_run_identity.v1":
                raise ResponseReuseError("unsupported run identity schema")
            for key, value in asdict(self).items():
                if key.endswith("sha256") or key == "reference_node_digest":
                    require_sha256(value, key)
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
        if set(raw) != set(cls.__dataclass_fields__):
            raise ResponseReuseError("run identity needs exactly the complete versioned fields")
        return cls(
            cast(str, raw["schema"]),
            cast(str, raw["effective_fdf_sha256"]),
            cast(str, raw["parent_dm_sha256"]),
            cast(str, raw["reference_node_digest"]),
            cast(str, raw["target"]),
            cast(float, raw["alpha_ev"]),
            ResponseMode(cast(str, raw["mode"])),
            cast(str, raw["dftu_record_sha256"]),
            cast(str, raw["species_identity_sha256"]),
            cast(str, raw["backend_identity"]),
            cast(str, raw["backend_version"]),
            cast(str, raw["scf_profile_sha256"]),
            cast(str, raw["observable_id"]),
            cast(str, raw["parser_version"]),
            cast(str, raw["magnetic_state_sha256"]),
            cast(str, raw["scientific_profile_sha256"]),
            cast(str, raw["mpi_layout_sha256"]),
        )

    @property
    def digest(self) -> str:
        return sha256(
            json.dumps(self.to_mapping(), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        ).hexdigest()


class ReuseStatus(str, Enum):
    EXACT_MATCH = "EXACT_MATCH"
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"


@dataclass(frozen=True)
class ReuseQualification:
    status: ReuseStatus
    mismatched_fields: tuple[str, ...]

    def to_mapping(self) -> dict[str, object]:
        return {"status": self.status.value, "mismatched_fields": list(self.mismatched_fields)}

    @classmethod
    def from_mapping(cls, row: Mapping[str, object]) -> ReuseQualification:
        return cls(ReuseStatus(cast(str, row["status"])), tuple(cast(list[str], row["mismatched_fields"])))


def qualify_response_reuse(pilot: ResponseRunIdentity, production: ResponseRunIdentity) -> ReuseQualification:
    """Require equality of the full typed key, with exact representable α."""
    if not isinstance(pilot, ResponseRunIdentity) or not isinstance(production, ResponseRunIdentity):
        raise ResponseReuseError("reuse requires complete typed identities")
    mismatches = tuple(
        sorted(
            name for name in pilot.__dataclass_fields__ if getattr(pilot, name) != getattr(production, name)
        )
    )
    return ReuseQualification(
        ReuseStatus.IDENTITY_MISMATCH if mismatches else ReuseStatus.EXACT_MATCH, mismatches
    )
