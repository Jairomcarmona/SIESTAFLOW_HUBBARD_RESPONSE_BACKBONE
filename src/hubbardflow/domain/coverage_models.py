"""Coverage records: candidates never prove a response reconstruction.

The D1 admission wrapper preserves one output's partial observations while
recording its input binding and perturbation check independently of TASK 8.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from enum import Enum
from hashlib import sha256
from typing import cast

from .state_evidence import (
    EvidenceStatus,
    MomentEvidence,
    OccupationSpectraStatus,
    OccupationSpectrum,
    ReferenceStateEvidence,
    StateEvidenceReason,
    SubspaceOccupationEvidence,
)
from .symmetry_operation_models import (
    Commensurability,
    ConditionStatus,
    CoveragePolicy,
    Operation,
    SymmetryReason,
)
from .symmetry_operations import ConditionResult, OperationClassification
from .validation import ValidationError, require_int, require_sha256


class CoverageError(ValueError):
    """Coverage input or serialized evidence cannot support a safe plan."""


class CoverageStatus(str, Enum):
    PROVEN = "PROVEN"
    CANDIDATE_PENDING_SHADOW = "CANDIDATE_PENDING_SHADOW"
    REJECTED_EXPANDED = "REJECTED_EXPANDED"
    NOT_ESTABLISHED = "NOT_ESTABLISHED"
    DISABLED = "DISABLED"


class CoverageStrategy(str, Enum):
    ALL_SUBSPACES = "ALL_SUBSPACES"
    SYMMETRY_REDUCED = "SYMMETRY_REDUCED"
    PARTIALLY_REDUCED = "PARTIALLY_REDUCED"
    USER_RESTRICTED = "USER_RESTRICTED"


class CoverageReason(str, Enum):
    EVIDENCE_INCOMPLETE = "EVIDENCE_INCOMPLETE"
    REFERENCE_NOT_ADMISSIBLE = "REFERENCE_NOT_ADMISSIBLE"
    EVIDENCE_BINDING_MISMATCH = "EVIDENCE_BINDING_MISMATCH"
    SPECIES_IDENTITY_NOT_ESTABLISHED = "SPECIES_IDENTITY_NOT_ESTABLISHED"
    UNSUPPORTED_SYNTAX = "UNSUPPORTED_SYNTAX"
    INVENTORY_NOT_ESTABLISHED = "INVENTORY_NOT_ESTABLISHED"
    DISABLED_OR_FIXED = "DISABLED_OR_FIXED"
    AMBIGUOUS_OPERATION = "AMBIGUOUS_OPERATION"
    GROUP_NOT_CLOSED = "GROUP_NOT_CLOSED"
    IDENTITY_OPERATION_NOT_ESTABLISHED = "IDENTITY_OPERATION_NOT_ESTABLISHED"
    NO_SAVING = "NO_SAVING"
    USER_RESTRICTION = "USER_RESTRICTION"
    SHADOW_PENDING = "SHADOW_PENDING"


@dataclass(frozen=True)
class UserCoveragePolicy:
    version: str
    enabled: bool
    declared_classes: tuple[tuple[str, ...], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.version, str) or not self.version or type(self.enabled) is not bool:
            raise CoverageError("explicit user policy version and boolean enabled are required")
        flat = [site for group in self.declared_classes for site in group]
        if any(not group for group in self.declared_classes) or len(set(flat)) != len(flat):
            raise CoverageError("declared classes must be nonempty and disjoint")
        object.__setattr__(
            self, "declared_classes", tuple(sorted(tuple(sorted(g)) for g in self.declared_classes))
        )

    def to_mapping(self) -> dict[str, object]:
        return {"version": self.version, "enabled": self.enabled, "declared_classes": self.declared_classes}

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> UserCoveragePolicy:
        return cls(
            cast(str, value["version"]),
            cast(bool, value["enabled"]),
            tuple(tuple(g) for g in cast(Sequence[Sequence[str]], value["declared_classes"])),
        )


@dataclass(frozen=True)
class CoverageReferenceEvidence:
    state: ReferenceStateEvidence
    input_file_sha256: str
    echoed_input_sha256: str | None
    input_output_consistent: bool
    nonpolarized_verified: bool
    perturbation_detected: bool
    status: EvidenceStatus
    # No archived DM identity is inferred from a filename or from a save-DM flag.
    parent_dm_sha256: str | None

    def __post_init__(self) -> None:
        try:
            for name, digest in (
                ("input_file_sha256", self.input_file_sha256),
                ("input_fdf_sha256", self.state.input_fdf_sha256),
                ("siesta_output_sha256", self.state.siesta_output_sha256),
            ):
                require_sha256(digest, name)
            for optional_digest in (self.echoed_input_sha256, self.parent_dm_sha256):
                if optional_digest is not None:
                    require_sha256(optional_digest, "reference identity")
        except ValidationError as exc:
            raise CoverageError(str(exc)) from exc
        if any(
            type(flag) is not bool
            for flag in (self.input_output_consistent, self.nonpolarized_verified, self.perturbation_detected)
        ):
            raise CoverageError("reference admission flags must be explicit booleans")
        if not isinstance(self.status, EvidenceStatus):
            raise CoverageError("reference status must be an EvidenceStatus")

    def to_mapping(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> CoverageReferenceEvidence:
        raw = cast(Mapping[str, object], value["state"])
        spectra = tuple(
            SubspaceOccupationEvidence(
                cast(str, row["site_id"]),
                cast(int, row["atom_index"]),
                tuple(
                    OccupationSpectrum(
                        cast(str, spec["spin"]),
                        tuple(cast(Sequence[float], spec["eigenvalues_e"])),
                        tuple(
                            tuple(r) for r in cast(Sequence[Sequence[float]], spec["matrix_half_widths_e"])
                        ),
                    )
                    for spec in cast(Sequence[Mapping[str, object]], row["spectra"])
                ),
            )
            for row in cast(Sequence[Mapping[str, object]], raw["occupation_spectra_by_subspace"])
        )
        mesh = raw["mesh_divisions"]
        kmesh = raw["k_mesh"]
        state = ReferenceStateEvidence(
            cast(str, raw["input_fdf_sha256"]),
            cast(str, raw["siesta_output_sha256"]),
            cast(bool, raw["normal_completion_verified"]),
            cast(bool, raw["scf_converged"]),
            tuple(
                MomentEvidence(
                    cast(int, row["atom_index"]),
                    cast(float, row["moment_e"]),
                    cast(float, row["half_width_e"]),
                )
                for row in cast(Sequence[Mapping[str, object]], raw["moments_by_atom"])
            ),
            None if mesh is None else cast(tuple[int, int, int], tuple(cast(Sequence[int], mesh))),
            None
            if kmesh is None
            else tuple(
                cast(tuple[int, int, int, float], tuple(row))
                for row in cast(Sequence[Sequence[float]], kmesh)
            ),
            OccupationSpectraStatus(cast(str, raw["occupation_spectra_status"])),
            spectra,
            EvidenceStatus(cast(str, raw["status"])),
            tuple(StateEvidenceReason(r) for r in cast(Sequence[str], raw["reason_codes"])),
        )
        return cls(
            state,
            cast(str, value["input_file_sha256"]),
            cast(str | None, value["echoed_input_sha256"]),
            cast(bool, value["input_output_consistent"]),
            cast(bool, value["nonpolarized_verified"]),
            cast(bool, value["perturbation_detected"]),
            EvidenceStatus(cast(str, value["status"])),
            cast(str | None, value["parent_dm_sha256"]),
        )


@dataclass(frozen=True)
class CoverageClass:
    members: tuple[str, ...]
    representative: str
    shadow: str | None
    ops_rep_to_member: tuple[tuple[str, int], ...]
    status: CoverageStatus
    reasons: tuple[CoverageReason, ...]

    def __post_init__(self) -> None:
        if (
            not self.members
            or len(set(self.members)) != len(self.members)
            or self.representative != self.members[0]
        ):
            raise CoverageError("coverage members must be unique with the representative first")
        if self.shadow is not None and (
            self.shadow not in self.members or self.shadow == self.representative
        ):
            raise CoverageError("shadow must be a distinct member of its class")
        if not isinstance(self.status, CoverageStatus) or any(
            not isinstance(r, CoverageReason) for r in self.reasons
        ):
            raise CoverageError("coverage status and reasons must be enums")
        if self.reduced and (self.shadow is None or len(self.members) <= 2):
            raise CoverageError("reduced class requires a mandatory shadow and strictly positive run saving")
        try:
            for site, index in self.ops_rep_to_member:
                if site not in self.members:
                    raise CoverageError("reconstruction map names a nonmember")
                require_int(index, "operation index", minimum=0)
        except ValidationError as exc:
            raise CoverageError(str(exc)) from exc

    @property
    def reduced(self) -> bool:
        return self.status in (CoverageStatus.CANDIDATE_PENDING_SHADOW, CoverageStatus.PROVEN)

    def to_mapping(self) -> dict[str, object]:
        return {**asdict(self), "status": self.status.value, "reasons": [r.value for r in self.reasons]}

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> CoverageClass:
        return cls(
            tuple(cast(Sequence[str], value["members"])),
            cast(str, value["representative"]),
            cast(str | None, value["shadow"]),
            tuple(
                (cast(str, row[0]), cast(int, row[1]))
                for row in cast(Sequence[Sequence[object]], value["ops_rep_to_member"])
            ),
            CoverageStatus(cast(str, value["status"])),
            tuple(CoverageReason(r) for r in cast(Sequence[str], value["reasons"])),
        )


def _classification(value: Mapping[str, object]) -> OperationClassification:
    return OperationClassification(
        Operation.from_mapping(cast(Mapping[str, object], value["operation"])),
        tuple(
            ConditionResult(
                cast(str, row["condition"]),
                ConditionStatus(cast(str, row["status"])),
                cast(float | None, row["measured_value"]),
                cast(float | None, row["tau_eq"]),
                cast(float | None, row["tau_neq"]),
                tuple(
                    cast(tuple[int, int, float, float, float], tuple(pair))
                    for pair in cast(Sequence[Sequence[float]], row["pair_measurements"])
                ),
                tuple(
                    cast(tuple[int, int], tuple(pair))
                    for pair in cast(Sequence[Sequence[int]], row["ambiguous_pairs"])
                ),
            )
            for row in cast(Sequence[Mapping[str, object]], value["conditions"])
        ),
        Commensurability(cast(str, value["commensurability"])),
        tuple(SymmetryReason(r) for r in cast(Sequence[str], value["reasons"])),
    )


@dataclass(frozen=True)
class CoverageQualification:
    inventory_digest: str
    effective_fdf_sha256: str
    reference: CoverageReferenceEvidence
    policy: CoveragePolicy
    user_policy: UserCoveragePolicy
    operations: tuple[OperationClassification, ...]
    classes: tuple[CoverageClass, ...]
    strategy: CoverageStrategy
    reasons: tuple[CoverageReason, ...]
    search_reasons: tuple[SymmetryReason, ...]
    would_reduce_to: int
    species_identity_digests: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        try:
            require_sha256(self.inventory_digest, "inventory_digest")
            require_sha256(self.effective_fdf_sha256, "effective_fdf_sha256")
            require_int(self.would_reduce_to, "would_reduce_to", minimum=0)
        except ValidationError as exc:
            raise CoverageError(str(exc)) from exc
        members = [s for c in self.classes for s in c.members]
        if len(set(members)) != len(members) or self.would_reduce_to > len(members):
            raise CoverageError(
                "coverage classes must partition the inventory and candidate count cannot exceed its size"
            )
        if not isinstance(self.strategy, CoverageStrategy):
            raise CoverageError("strategy must be a CoverageStrategy")
        for group in self.classes:
            for site, index in group.ops_rep_to_member:
                if index >= len(self.operations) or not self.operations[index].accepted:
                    raise CoverageError(f"reconstruction for {site} must name an accepted operation")

    @property
    def computed_columns(self) -> tuple[str, ...]:
        return tuple(
            site
            for group in self.classes
            for site in ((group.representative, cast(str, group.shadow)) if group.reduced else group.members)
        )

    def to_mapping(self) -> dict[str, object]:
        return {
            "schema": "hubbardflow.coverage_qualification.v1",
            "inventory_digest": self.inventory_digest,
            "effective_fdf_sha256": self.effective_fdf_sha256,
            "reference": self.reference.to_mapping(),
            "policy": self.policy.to_mapping(),
            "user_policy": self.user_policy.to_mapping(),
            "operations": [op.to_mapping() for op in self.operations],
            "classes": [c.to_mapping() for c in self.classes],
            "strategy": self.strategy.value,
            "reasons": [r.value for r in self.reasons],
            "search_reasons": [r.value for r in self.search_reasons],
            "would_reduce_to": self.would_reduce_to,
            "species_identity_digests": self.species_identity_digests,
        }

    @property
    def digest(self) -> str:
        try:
            return sha256(
                json.dumps(self.to_mapping(), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
            ).hexdigest()
        except (ValueError, TypeError) as exc:
            raise CoverageError("coverage evidence contains nonfinite or nonserializable data") from exc

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> CoverageQualification:
        if value.get("schema") != "hubbardflow.coverage_qualification.v1":
            raise CoverageError("unsupported coverage schema")
        try:
            json.dumps(value, allow_nan=False)
            require_sha256(value["inventory_digest"], "inventory_digest")
            require_sha256(value["effective_fdf_sha256"], "effective_fdf_sha256")
            return cls(
                cast(str, value["inventory_digest"]),
                cast(str, value["effective_fdf_sha256"]),
                CoverageReferenceEvidence.from_mapping(cast(Mapping[str, object], value["reference"])),
                CoveragePolicy.from_mapping(cast(Mapping[str, object], value["policy"])),
                UserCoveragePolicy.from_mapping(cast(Mapping[str, object], value["user_policy"])),
                tuple(
                    _classification(op) for op in cast(Sequence[Mapping[str, object]], value["operations"])
                ),
                tuple(
                    CoverageClass.from_mapping(c)
                    for c in cast(Sequence[Mapping[str, object]], value["classes"])
                ),
                CoverageStrategy(cast(str, value["strategy"])),
                tuple(CoverageReason(r) for r in cast(Sequence[str], value["reasons"])),
                tuple(SymmetryReason(r) for r in cast(Sequence[str], value["search_reasons"])),
                cast(int, value["would_reduce_to"]),
                tuple(
                    (cast(str, row[0]), cast(str, row[1]))
                    for row in cast(Sequence[Sequence[object]], value["species_identity_digests"])
                ),
            )
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            raise CoverageError(f"invalid coverage mapping: {exc}") from exc
