"""Scalar trace reconstruction and free consistency diagnostics (§E).

These functions apply supplied maps, never establish a symmetry. The caller
must qualify the operations and shadows. Raw data survive every diagnostic.
Spin flips do not multiply the spin-summed trace by a sign.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Protocol, cast

import numpy as np

from .validation import ValidationError, require_finite, require_int

Matrix = tuple[tuple[float, ...], ...]


class ResponseReconstructionError(ValueError):
    """A missing or invalid scalar map cannot reconstruct a response."""


class ObservableKind(str, Enum):
    SPIN_SUMMED_TRACE = "SPIN_SUMMED_TRACE"
    OCCUPATION_MATRIX = "OCCUPATION_MATRIX"


class PermutationLike(Protocol):
    @property
    def correlated_permutation(self) -> tuple[int, ...]: ...


@dataclass(frozen=True)
class ScalarPermutation:
    """An algebraic index map carrying no geometric or magnetic evidence."""

    correlated_permutation: tuple[int, ...]

    def __post_init__(self) -> None:
        try:
            for index in self.correlated_permutation:
                require_int(index, "permutation index", minimum=0)
        except ValidationError as exc:
            raise ResponseReconstructionError(str(exc)) from exc
        if sorted(self.correlated_permutation) != list(range(len(self.correlated_permutation))):
            raise ResponseReconstructionError("scalar permutation must be a bijection")
        object.__setattr__(self, "correlated_permutation", tuple(self.correlated_permutation))

    def to_mapping(self) -> dict[str, object]:
        return {"correlated_permutation": list(self.correlated_permutation)}

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> ScalarPermutation:
        return cls(tuple(cast(Sequence[int], value["correlated_permutation"])))


def _rectangular(value: Sequence[Sequence[float]]) -> Matrix:
    try:
        rows = tuple(tuple(require_finite(x, "matrix entry") for x in row) for row in value)
    except (TypeError, ValidationError) as exc:
        raise ResponseReconstructionError(str(exc)) from exc
    if not rows or not rows[0] or any(len(row) != len(rows[0]) for row in rows):
        raise ResponseReconstructionError("residuals must be a nonempty rectangular array")
    return rows


def _matrix(value: Sequence[Sequence[float]]) -> Matrix:
    rows = _rectangular(value)
    if any(len(row) != len(rows) for row in rows):
        raise ResponseReconstructionError("matrix must be nonempty and square")
    return rows


@dataclass(frozen=True)
class ReconstructionClass:
    """Explicit column mapping; operation indices reference the supplied ops."""

    members: tuple[int, ...]
    representative: int
    ops_rep_to_member: tuple[tuple[int, int], ...]

    def __post_init__(self) -> None:
        try:
            require_int(self.representative, "representative", minimum=0)
            for member in self.members:
                require_int(member, "member", minimum=0)
            for member, index in self.ops_rep_to_member:
                require_int(member, "mapped member", minimum=0)
                require_int(index, "operation index", minimum=0)
        except (TypeError, ValueError) as exc:
            raise ResponseReconstructionError(str(exc)) from exc
        if not self.members or len(set(self.members)) != len(self.members):
            raise ResponseReconstructionError("class members must be nonempty and unique")
        if self.representative not in self.members:
            raise ResponseReconstructionError("representative must belong to its class")
        targets = [member for member, _ in self.ops_rep_to_member]
        if len(set(targets)) != len(targets) or set(targets) != set(self.members):
            raise ResponseReconstructionError(
                "one operation is required for every member, including representative"
            )
        object.__setattr__(self, "members", tuple(sorted(self.members)))
        object.__setattr__(self, "ops_rep_to_member", tuple(sorted(self.ops_rep_to_member)))

    def to_mapping(self) -> dict[str, object]:
        return {
            "members": list(self.members),
            "representative": self.representative,
            "ops_rep_to_member": [list(pair) for pair in self.ops_rep_to_member],
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> ReconstructionClass:
        try:
            return cls(
                tuple(cast(Sequence[int], value["members"])),
                cast(int, value["representative"]),
                tuple(
                    cast(tuple[int, int], tuple(pair))
                    for pair in cast(Sequence[Sequence[int]], value["ops_rep_to_member"])
                ),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ResponseReconstructionError(f"invalid reconstruction class: {exc}") from exc


@dataclass(frozen=True)
class ReconstructionResult:
    raw_matrix: Matrix

    def __post_init__(self) -> None:
        object.__setattr__(self, "raw_matrix", _matrix(self.raw_matrix))

    def to_mapping(self) -> dict[str, object]:
        return {"raw_matrix": [list(row) for row in self.raw_matrix]}

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> ReconstructionResult:
        return cls(_matrix(cast(Sequence[Sequence[float]], value["raw_matrix"])))


def reconstruct_matrix(
    columns_by_representative: Mapping[int, Sequence[float]],
    classes: Sequence[ReconstructionClass],
    ops: Sequence[PermutationLike],
    *,
    observable: ObservableKind,
) -> ReconstructionResult:
    """Apply χ[g(I),g(J)] = χ[I,J] to traces or scalar slopes.

    The same permutation selects the destination column and destination rows.
    There is no averaging over maps or stabilizers, and no symmetrization.
    Full orbital matrices require D^l transformations and are rejected.
    """
    if observable is not ObservableKind.SPIN_SUMMED_TRACE:
        raise ResponseReconstructionError(
            "occupation matrices are unsupported; supply spin-summed scalar traces"
        )
    members = [member for cls in classes for member in cls.members]
    n = len(members)
    if n == 0 or sorted(members) != list(range(n)):
        raise ResponseReconstructionError("classes must partition all matrix indices exactly once")
    if set(columns_by_representative) != {cls.representative for cls in classes}:
        raise ResponseReconstructionError("computed columns must match class representatives exactly")
    if any(type(index) is not int for index in columns_by_representative):
        raise ResponseReconstructionError("computed column indices must be integers, never booleans")
    out = np.empty((n, n))
    for cls in sorted(classes, key=lambda item: item.representative):
        try:
            column = tuple(
                require_finite(x, "scalar column entry")
                for x in columns_by_representative[cls.representative]
            )
        except ValidationError as exc:
            raise ResponseReconstructionError(str(exc)) from exc
        if len(column) != n:
            raise ResponseReconstructionError("each scalar column must cover all observed sites")
        for member, index in cls.ops_rep_to_member:
            if index >= len(ops):
                raise ResponseReconstructionError("operation index is absent from ops")
            permutation = ops[index].correlated_permutation
            ScalarPermutation(permutation)
            if len(permutation) != n or permutation[cls.representative] != member:
                raise ResponseReconstructionError("operation must map representative to destination column")
            for source_row, destination_row in enumerate(permutation):
                out[destination_row, permutation[cls.representative]] = column[source_row]
    return ReconstructionResult(_matrix(out.tolist()))


@dataclass(frozen=True)
class ResidualReport:
    """Diagnostic differences, with no tolerance or acceptance decision."""

    residuals: Matrix
    max_abs: float
    frobenius_norm: float

    def __post_init__(self) -> None:
        rows = _rectangular(self.residuals)
        object.__setattr__(self, "residuals", rows)
        try:
            require_finite(self.max_abs, "max_abs")
            require_finite(self.frobenius_norm, "frobenius_norm")
        except ValidationError as exc:
            raise ResponseReconstructionError(str(exc)) from exc
        array = np.asarray(rows)
        if self.max_abs != float(np.max(np.abs(array))) or self.frobenius_norm != float(
            np.linalg.norm(array)
        ):
            raise ResponseReconstructionError("residual summaries disagree with raw residuals")

    def to_mapping(self) -> dict[str, object]:
        return {
            "residuals": [list(row) for row in self.residuals],
            "max_abs": self.max_abs,
            "frobenius_norm": self.frobenius_norm,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> ResidualReport:
        return cls(
            _rectangular(cast(Sequence[Sequence[float]], value["residuals"])),
            cast(float, value["max_abs"]),
            cast(float, value["frobenius_norm"]),
        )


def _residual_report(residual: Sequence[Sequence[float]]) -> ResidualReport:
    rows = _rectangular(residual)
    array = np.asarray(rows)
    try:
        return ResidualReport(
            rows,
            require_finite(float(np.max(np.abs(array))), "max residual"),
            require_finite(float(np.linalg.norm(array)), "residual norm"),
        )
    except ValidationError as exc:
        raise ResponseReconstructionError(str(exc)) from exc


def reciprocity_residuals(raw_matrix: Sequence[Sequence[float]]) -> ResidualReport:
    """χ-χᵀ checks derivative reciprocity; it cannot replace a column."""
    array = np.asarray(_matrix(raw_matrix))
    return _residual_report((array - array.T).tolist())


def stabilizer_residuals(
    column: Sequence[float], representative: int, ops: Sequence[PermutationLike]
) -> ResidualReport:
    """Check all supplied maps fixing r: Π_g χ[:,r] - χ[:,r]."""
    try:
        values = tuple(require_finite(x, "scalar column entry") for x in column)
        require_int(representative, "representative", minimum=0)
    except ValidationError as exc:
        raise ResponseReconstructionError(str(exc)) from exc
    if not values or representative >= len(values):
        raise ResponseReconstructionError("representative must index a nonempty column")
    residuals = []
    for op in sorted(ops, key=lambda item: item.correlated_permutation):
        permutation = op.correlated_permutation
        ScalarPermutation(permutation)
        if len(permutation) != len(values):
            raise ResponseReconstructionError("stabilizer permutation dimension disagrees with column")
        if permutation[representative] == representative:
            predicted = [0.0] * len(values)
            for source, target in enumerate(permutation):
                predicted[target] = values[source]
            residuals.append([predicted[i] - values[i] for i in range(len(values))])
    # No nontrivial stabilizer yields a zero diagnostic, never missing evidence.
    return _residual_report(residuals or [[0.0] * len(values)])


@dataclass(frozen=True)
class SymmetrizationReport:
    raw_matrix: Matrix
    symmetrized_matrix: Matrix
    correction_frobenius_norm: float

    def __post_init__(self) -> None:
        raw, symmetric = _matrix(self.raw_matrix), _matrix(self.symmetrized_matrix)
        object.__setattr__(self, "raw_matrix", raw)
        object.__setattr__(self, "symmetrized_matrix", symmetric)
        array = np.asarray(raw)
        expected = array / 2 + array.T / 2
        try:
            require_finite(self.correction_frobenius_norm, "correction_frobenius_norm")
        except ValidationError as exc:
            raise ResponseReconstructionError(str(exc)) from exc
        if symmetric != _matrix(expected.tolist()) or self.correction_frobenius_norm != float(
            np.linalg.norm(expected - array)
        ):
            raise ResponseReconstructionError("symmetrization summaries disagree with raw matrix")

    def to_mapping(self) -> dict[str, object]:
        return {
            "raw_matrix": [list(row) for row in self.raw_matrix],
            "symmetrized_matrix": [list(row) for row in self.symmetrized_matrix],
            "correction_frobenius_norm": self.correction_frobenius_norm,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> SymmetrizationReport:
        return cls(
            _matrix(cast(Sequence[Sequence[float]], value["raw_matrix"])),
            _matrix(cast(Sequence[Sequence[float]], value["symmetrized_matrix"])),
            cast(float, value["correction_frobenius_norm"]),
        )


def symmetrization_report(raw_matrix: Sequence[Sequence[float]]) -> SymmetrizationReport:
    """Retain raw χ and expose exactly how much (χ+χᵀ)/2 changes it."""
    raw = _matrix(raw_matrix)
    array = np.asarray(raw)
    symmetric = array / 2 + array.T / 2
    norm = _residual_report((symmetric - array).tolist()).frobenius_norm
    return SymmetrizationReport(raw, _matrix(symmetric.tolist()), norm)
