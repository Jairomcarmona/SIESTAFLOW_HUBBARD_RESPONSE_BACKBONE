"""Pure canonical map from correlated projector labels to individual atoms.

The inventory records a shared DFTU label explicitly. It never pretends that
one label assigned to multiple atoms already represents independent columns.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class InventoryStatus(str, Enum):
    OK = "OK"
    SHARED_LABEL_NEEDS_SPLIT = "SHARED_LABEL_NEEDS_SPLIT"
    NOT_SUPPORTED = "NOT_SUPPORTED"
    SUBSPACE_MAPPING_NOT_ESTABLISHED = "SUBSPACE_MAPPING_NOT_ESTABLISHED"


class InventoryReason(str, Enum):
    DFTU_LABEL_MULTIPLE_ATOMS = "DFTU_LABEL_MULTIPLE_ATOMS"
    DFTU_LABEL_NO_ATOM = "DFTU_LABEL_NO_ATOM"
    SPECIES_IDENTITY_NOT_ESTABLISHED = "SPECIES_IDENTITY_NOT_ESTABLISHED"
    NONCOLLINEAR_OR_SOC_NOT_SUPPORTED = "NONCOLLINEAR_OR_SOC_NOT_SUPPORTED"


class _SpeciesLabel(Protocol):
    @property
    def label(self) -> str: ...

    @property
    def atomic_number(self) -> int: ...


class _Atom(Protocol):
    @property
    def atom_index(self) -> int: ...

    @property
    def species_label(self) -> str: ...


class _DftuRecord(Protocol):
    @property
    def label(self) -> str: ...

    @property
    def n(self) -> int: ...

    @property
    def l(self) -> int: ...


class _Identity(Protocol):
    @property
    def atomic_number(self) -> int: ...

    @property
    def digest(self) -> str: ...

    @property
    def status(self) -> object: ...


class _FdfModel(Protocol):
    @property
    def effective_fdf_sha256(self) -> str: ...

    @property
    def chemical_species_labels(self) -> tuple[_SpeciesLabel, ...]: ...

    @property
    def atoms(self) -> tuple[_Atom, ...]: ...

    @property
    def dftu_records(self) -> tuple[_DftuRecord, ...]: ...

    @property
    def noncollinear(self) -> bool: ...

    @property
    def spin_orbit(self) -> bool: ...


@dataclass(frozen=True)
class CorrelatedSubspace:
    site_id: str
    atom_index: int
    species_label: str
    atomic_number: int
    dftu_record: _DftuRecord
    identity_digest: str


@dataclass(frozen=True)
class CorrelatedSubspaceInventory:
    subspaces: tuple[CorrelatedSubspace, ...]
    effective_fdf_sha256: str
    status: InventoryStatus
    reason_codes: tuple[InventoryReason, ...]
    digest: str


class SubspaceInventoryError(ValueError):
    """Raised when an inventory input violates its typed FDF contract."""


def build_inventory(
    model: _FdfModel,
    identities: Mapping[str, _Identity],
) -> CorrelatedSubspaceInventory:
    """Build a deterministic one-row-per-atom inventory without file access."""
    species_by_label = {item.label: item for item in model.chemical_species_labels}
    atoms_by_label: dict[str, list[_Atom]] = {}
    for atom in model.atoms:
        atoms_by_label.setdefault(atom.species_label, []).append(atom)
    for values in atoms_by_label.values():
        values.sort(key=lambda atom: atom.atom_index)

    reasons: set[InventoryReason] = set()
    subspaces: list[CorrelatedSubspace] = []
    if model.noncollinear or model.spin_orbit:
        reasons.add(InventoryReason.NONCOLLINEAR_OR_SOC_NOT_SUPPORTED)
    for record in sorted(model.dftu_records, key=lambda value: (value.label, value.n, value.l)):
        matches = atoms_by_label.get(record.label, [])
        if not matches:
            reasons.add(InventoryReason.DFTU_LABEL_NO_ATOM)
            continue
        if len(matches) > 1:
            reasons.add(InventoryReason.DFTU_LABEL_MULTIPLE_ATOMS)
        species = species_by_label.get(record.label)
        identity = identities.get(record.label)
        if (
            species is None
            or identity is None
            or getattr(identity.status, "value", identity.status) != "ESTABLISHED"
        ):
            reasons.add(InventoryReason.SPECIES_IDENTITY_NOT_ESTABLISHED)
            identity_digest = identity.digest if identity is not None else ""
        else:
            if identity.atomic_number != species.atomic_number:
                reasons.add(InventoryReason.SPECIES_IDENTITY_NOT_ESTABLISHED)
            identity_digest = identity.digest
        if species is None:
            continue
        for atom in matches:
            # Atom index is part of the identifier because shared labels await
            # explicit splitting in the later materialization task.
            site_id = f"{record.label}@{atom.atom_index}:{record.n}:{record.l}"
            subspaces.append(
                CorrelatedSubspace(
                    site_id, atom.atom_index, record.label, species.atomic_number, record, identity_digest
                )
            )
    ordered = tuple(
        sorted(
            subspaces,
            key=lambda item: (item.atom_index, item.dftu_record.n, item.dftu_record.l, item.species_label),
        )
    )
    if InventoryReason.NONCOLLINEAR_OR_SOC_NOT_SUPPORTED in reasons:
        status = InventoryStatus.NOT_SUPPORTED
    elif InventoryReason.DFTU_LABEL_MULTIPLE_ATOMS in reasons:
        status = InventoryStatus.SHARED_LABEL_NEEDS_SPLIT
    elif reasons:
        status = InventoryStatus.SUBSPACE_MAPPING_NOT_ESTABLISHED
    else:
        status = InventoryStatus.OK
    reason_codes = tuple(sorted(reasons, key=lambda item: item.value))
    payload = "\n".join(
        (
            model.effective_fdf_sha256,
            status.value,
            *(reason.value for reason in reason_codes),
            *(
                f"{item.atom_index}|{item.species_label}|{item.atomic_number}|"
                f"{item.dftu_record.n}|{item.dftu_record.l}|{item.identity_digest}"
                for item in ordered
            ),
        )
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return CorrelatedSubspaceInventory(ordered, model.effective_fdf_sha256, status, reason_codes, digest)
