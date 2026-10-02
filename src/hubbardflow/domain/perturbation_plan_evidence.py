"""Frozen scientific provenance for the plan, without backend imports or I/O.

The complete projector record is preserved rather than reducing its identity
to an element or angular momentum. Missing semantic fields fail closed.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import cast

from .subspace_inventory import (
    CorrelatedSubspace,
    CorrelatedSubspaceInventory,
    InventoryReason,
    InventoryStatus,
)
from .validation import require_finite, require_int, require_sha256


class PerturbationPlanError(ValueError):
    """Injected evidence or a serialized plan violates the frozen contract."""


def identifier(value: object, name: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise PerturbationPlanError(f"{name} must be an explicit nonempty identifier")
    return value


@dataclass(frozen=True)
class ProjectorEvidence:
    label: str
    projector_header_value: str
    n: int
    l: int
    u_ref_ev: float
    j_ref_ev: float
    rc_bohr: float
    omega: float
    lambda_values: tuple[float, ...]
    canonical_text: str

    def __post_init__(self) -> None:
        identifier(self.label, "projector label")
        identifier(self.projector_header_value, "projector header")
        require_int(self.n, "n", minimum=1)
        require_int(self.l, "l", minimum=0)
        for name in ("u_ref_ev", "j_ref_ev", "rc_bohr", "omega"):
            require_finite(getattr(self, name), name)
        for value in self.lambda_values:
            require_finite(value, "lambda")
        identifier(self.canonical_text, "canonical projector text")

    @classmethod
    def from_mapping(cls, row: Mapping[str, object]) -> ProjectorEvidence:
        return cls(
            cast(str, row["label"]),
            cast(str, row["projector_header_value"]),
            cast(int, row["n"]),
            cast(int, row["l"]),
            cast(float, row["u_ref_ev"]),
            cast(float, row["j_ref_ev"]),
            cast(float, row["rc_bohr"]),
            cast(float, row["omega"]),
            tuple(cast(Sequence[float], row["lambda_values"])),
            cast(str, row["canonical_text"]),
        )

    def to_mapping(self) -> dict[str, object]:
        return asdict(self)


def freeze_inventory(inventory: CorrelatedSubspaceInventory) -> CorrelatedSubspaceInventory:
    """Copy protocol-shaped input records into deeply immutable domain records."""
    try:
        return _freeze_inventory(inventory)
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        raise PerturbationPlanError(f"invalid frozen inventory: {exc}") from exc


def _freeze_inventory(inventory: CorrelatedSubspaceInventory) -> CorrelatedSubspaceInventory:
    rows = []
    for site in sorted(inventory.subspaces, key=lambda s: (s.atom_index, s.site_id)):
        record = ProjectorEvidence.from_mapping(
            {name: getattr(site.dftu_record, name) for name in ProjectorEvidence.__dataclass_fields__}
        )
        identifier(site.site_id, "site_id")
        require_int(site.atom_index, "atom_index", minimum=0)
        require_int(site.atomic_number, "atomic_number", minimum=1)
        if site.identity_digest:
            require_sha256(site.identity_digest, "species identity")
        rows.append(
            CorrelatedSubspace(
                site.site_id,
                site.atom_index,
                site.species_label,
                site.atomic_number,
                record,
                site.identity_digest,
            )
        )
    require_sha256(inventory.effective_fdf_sha256, "effective FDF")
    require_sha256(inventory.digest, "inventory digest")
    if len({s.site_id for s in rows}) != len(rows) or len({s.atom_index for s in rows}) != len(rows):
        raise PerturbationPlanError("inventory must have unique sites and one correlated subspace per atom")
    if not isinstance(inventory.status, InventoryStatus):
        raise PerturbationPlanError("inventory status must be an InventoryStatus")
    return CorrelatedSubspaceInventory(
        tuple(rows),
        inventory.effective_fdf_sha256,
        inventory.status,
        tuple(sorted(inventory.reason_codes, key=lambda r: r.value)),
        inventory.digest,
    )


def inventory_mapping(inventory: CorrelatedSubspaceInventory) -> dict[str, object]:
    return {
        "subspaces": [asdict(s) for s in inventory.subspaces],
        "effective_fdf_sha256": inventory.effective_fdf_sha256,
        "status": inventory.status.value,
        "reason_codes": [r.value for r in inventory.reason_codes],
        "digest": inventory.digest,
    }


def inventory_from_mapping(row: Mapping[str, object]) -> CorrelatedSubspaceInventory:
    return freeze_inventory(
        CorrelatedSubspaceInventory(
            tuple(
                CorrelatedSubspace(
                    cast(str, s["site_id"]),
                    cast(int, s["atom_index"]),
                    cast(str, s["species_label"]),
                    cast(int, s["atomic_number"]),
                    ProjectorEvidence.from_mapping(cast(Mapping[str, object], s["dftu_record"])),
                    cast(str, s["identity_digest"]),
                )
                for s in cast(Sequence[Mapping[str, object]], row["subspaces"])
            ),
            cast(str, row["effective_fdf_sha256"]),
            InventoryStatus(cast(str, row["status"])),
            tuple(InventoryReason(r) for r in cast(Sequence[str], row["reason_codes"])),
            cast(str, row["digest"]),
        )
    )
