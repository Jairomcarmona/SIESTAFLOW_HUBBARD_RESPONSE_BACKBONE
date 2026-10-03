"""Closure of response permutation images and deterministic coverage orbits."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .subspace_inventory import CorrelatedSubspaceInventory
from .symmetry_operation_models import Operation, SymmetryOperationsError, SymmetryReason


@dataclass(frozen=True)
class OperationGroup:
    operations: tuple[Operation, ...]
    reasons: tuple[SymmetryReason, ...]


def close_under_composition(ops: Sequence[Operation]) -> OperationGroup:
    """Verify closure of the response permutation image; drop all on failure."""
    keys = {(op.correlated_permutation, op.eps) for op in ops}
    sizes = {len(op.correlated_permutation) for op in ops}
    closed = len(sizes) <= 1 and all(
        (
            tuple(
                right.correlated_permutation[left.correlated_permutation[i]]
                for i in range(len(left.correlated_permutation))
            ),
            left.eps * right.eps,
        )
        in keys
        for left in ops
        for right in ops
    )
    if not closed:
        return OperationGroup((), (SymmetryReason.GROUP_NOT_CLOSED,))
    return OperationGroup(
        tuple(
            sorted(ops, key=lambda op: (op.rotation_int, op.translation_frac, op.eps, op.atom_permutation))
        ),
        (),
    )


@dataclass(frozen=True)
class SymmetryOrbit:
    members: tuple[str, ...]
    representative: str
    shadow: str | None


@dataclass(frozen=True)
class OrbitPartition:
    orbits: tuple[SymmetryOrbit, ...]


def orbits(group: OperationGroup, inventory: CorrelatedSubspaceInventory) -> OrbitPartition:
    """Partition by response permutations; minimum atom index defines rep/shadow."""
    subspaces = sorted(inventory.subspaces, key=lambda item: item.atom_index)
    remaining = set(range(len(subspaces)))
    result = []
    if any(len(op.correlated_permutation) != len(subspaces) for op in group.operations):
        raise SymmetryOperationsError("group permutations disagree with inventory size")
    while remaining:
        orbit = {min(remaining)}
        while True:
            expanded = orbit | {op.correlated_permutation[i] for op in group.operations for i in orbit}
            if expanded == orbit:
                break
            orbit = expanded
        members = tuple(subspaces[i].site_id for i in sorted(orbit))
        result.append(SymmetryOrbit(members, members[0], members[1] if len(members) > 1 else None))
        remaining -= orbit
    return OrbitPartition(tuple(result))
