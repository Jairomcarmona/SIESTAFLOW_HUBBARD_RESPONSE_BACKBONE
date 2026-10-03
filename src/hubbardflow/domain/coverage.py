"""Pure diagnostic coverage qualification with compulsory response shadows.

F1–F8 eligibility creates candidates only. D2 counts both representative and
shadow before allowing a proposed omission; a diagnostic never proves it.
"""

from __future__ import annotations

from dataclasses import replace

from .coverage_models import (
    CoverageClass,
    CoverageError,
    CoverageQualification,
    CoverageReason,
    CoverageReferenceEvidence,
    CoverageStatus,
    CoverageStrategy,
    UserCoveragePolicy,
)
from .state_evidence import EvidenceStatus, OccupationSpectraStatus
from .subspace_inventory import CorrelatedSubspaceInventory, InventoryReason, InventoryStatus
from .symmetry_operation_models import (
    IDENTITY,
    ConditionStatus,
    CoveragePolicy,
    ExactnessClass,
    SymmetryModel,
    SymmetryOperationsError,
    SymmetryReason,
)
from .symmetry_operations import (
    ConditionResult,
    OperationClassification,
    candidate_operations,
    classify,
    close_under_composition,
    orbits,
)
from .validation import ValidationError, require_sha256

__all__ = [
    "CoverageClass",
    "CoverageError",
    "CoverageQualification",
    "CoverageReason",
    "CoverageReferenceEvidence",
    "CoverageStatus",
    "CoverageStrategy",
    "UserCoveragePolicy",
    "qualify_coverage",
]


def qualify_coverage(
    inventory: CorrelatedSubspaceInventory,
    state: CoverageReferenceEvidence,
    model: SymmetryModel,
    policy: CoveragePolicy,
    user_policy: UserCoveragePolicy,
) -> CoverageQualification:
    """Propose only evidence-bound, closed candidate classes, never PROVEN.

    User classes intersect the inferred orbits; unspecified sites become explicit.
    An ambiguous allowed operation conservatively expands the entire inventory.
    Unavailable evidence cannot provide a hypothetical reduction count: its count
    is the number of explicit sites. No response, U, or condition number is read.
    """
    sites = tuple(sorted(inventory.subspaces, key=lambda s: s.atom_index))
    identifiers = tuple(s.site_id for s in sites)
    if len(set(identifiers)) != len(sites) or len({s.atom_index for s in sites}) != len(sites):
        raise CoverageError("coverage needs unique site identifiers and one subspace per atom")
    try:
        for name, digest in (
            ("inventory_digest", inventory.digest),
            ("input_file_sha256", state.input_file_sha256),
            ("siesta_output_sha256", state.state.siesta_output_sha256),
        ):
            require_sha256(digest, name)
    except ValidationError as exc:
        raise CoverageError(str(exc)) from exc
    declared = {s for group in user_policy.declared_classes for s in group}
    if not declared <= set(identifiers):
        raise CoverageError("declared classes contain sites absent from the inventory")
    base_reasons: set[CoverageReason] = set()
    if not user_policy.enabled:
        base_reasons.add(CoverageReason.DISABLED_OR_FIXED)
    if (
        state.status is not EvidenceStatus.ADMISSIBLE
        or not state.input_output_consistent
        or state.perturbation_detected
        or not state.state.normal_completion_verified
        or not state.state.scf_converged
        or state.state.occupation_spectra_status is not OccupationSpectraStatus.AVAILABLE
        or not state.state.occupation_spectra_by_subspace
        or {s.atom_index for s in state.state.occupation_spectra_by_subspace} != {s.atom_index for s in sites}
        or (not state.nonpolarized_verified and len(state.state.moments_by_atom) != len(model.atoms))
    ):
        base_reasons.update((CoverageReason.REFERENCE_NOT_ADMISSIBLE, CoverageReason.EVIDENCE_INCOMPLETE))
    if not (inventory.effective_fdf_sha256 == model.effective_fdf_sha256 == state.state.input_fdf_sha256):
        base_reasons.add(CoverageReason.EVIDENCE_BINDING_MISMATCH)
    if (
        any(a.identity_digest is None for a in model.atoms)
        or InventoryReason.SPECIES_IDENTITY_NOT_ESTABLISHED in inventory.reason_codes
    ):
        base_reasons.add(CoverageReason.SPECIES_IDENTITY_NOT_ESTABLISHED)
    if inventory.status is InventoryStatus.NOT_SUPPORTED or not model.collinear or model.spin_orbit:
        base_reasons.add(CoverageReason.UNSUPPORTED_SYNTAX)
    if inventory.status is not InventoryStatus.OK or not sites:
        base_reasons.add(CoverageReason.INVENTORY_NOT_ESTABLISHED)
    classifications: tuple[OperationClassification, ...] = ()
    search_reasons: tuple[SymmetryReason, ...] = ()
    candidate_orbits: tuple[tuple[str, ...], ...] = tuple((s,) for s in identifiers)
    if inventory.status is not InventoryStatus.NOT_SUPPORTED:
        search = candidate_operations(model, policy.geometry)
        search_reasons = search.reasons
        results = []
        for operation in search.operations:
            if state.nonpolarized_verified and operation.eps == -1:
                continue
            try:
                result = classify(operation, inventory, state.state, policy)
            except SymmetryOperationsError as exc:
                raise CoverageError(str(exc)) from exc
            if state.nonpolarized_verified:
                result = replace(
                    result,
                    conditions=tuple(
                        ConditionResult("F5", ConditionStatus.NOT_APPLICABLE, None, None, None)
                        if c.condition == "F5"
                        else c
                        for c in result.conditions
                    ),
                )
            if CoverageReason.REFERENCE_NOT_ADMISSIBLE in base_reasons:
                result = replace(
                    result,
                    reasons=tuple(
                        sorted(
                            set(result.reasons) | {SymmetryReason.REFERENCE_NOT_ADMISSIBLE},
                            key=lambda r: r.value,
                        )
                    ),
                )
            results.append(result)
        classifications = tuple(results)
    if not base_reasons:
        group = close_under_composition(tuple(r.operation for r in classifications if r.accepted))
        if group.reasons:
            base_reasons.add(CoverageReason.GROUP_NOT_CLOSED)
        if not any(
            op.eps == 1 and op.correlated_permutation == tuple(range(len(sites))) for op in group.operations
        ):
            base_reasons.add(CoverageReason.IDENTITY_OPERATION_NOT_ESTABLISHED)
        candidate_orbits = tuple(o.members for o in orbits(group, inventory).orbits)
        if any(
            (r.operation.eps == 1 or policy.allow_spin_flip)
            and (r.operation.rotation_int == IDENTITY or policy.allow_rotations)
            and any(c.status is ConditionStatus.AMBIGUOUS and c.condition != "F8" for c in r.conditions)
            for r in classifications
        ):
            base_reasons.add(CoverageReason.AMBIGUOUS_OPERATION)
    if user_policy.declared_classes:
        restricted = []
        for orbit in candidate_orbits:
            remaining = set(orbit)
            for declared_group in user_policy.declared_classes:
                intersection = tuple(s for s in orbit if s in declared_group)
                if intersection:
                    restricted.append(intersection)
                    remaining -= set(intersection)
            restricted.extend((s,) for s in orbit if s in remaining)
        candidate_orbits = tuple(sorted(restricted, key=lambda g: identifiers.index(g[0])))
    would_reduce_to = len(candidate_orbits)
    reasons = set(base_reasons)
    classes = []
    if base_reasons:
        status = (
            CoverageStatus.DISABLED
            if CoverageReason.DISABLED_OR_FIXED in base_reasons
            else CoverageStatus.NOT_ESTABLISHED
        )
        classes = [
            CoverageClass((s,), s, None, (), status, tuple(sorted(base_reasons, key=lambda r: r.value)))
            for s in identifiers
        ]
    else:
        for members in candidate_orbits:
            representative = members[0]
            shadow = members[1] if len(members) > 1 else None
            maps = []
            rep_index = identifiers.index(representative)
            for member in members:
                index = identifiers.index(member)
                matching = [
                    i
                    for i, r in enumerate(classifications)
                    if r.accepted and r.operation.correlated_permutation[rep_index] == index
                ]
                if not matching:
                    raise CoverageError("closed group did not provide a representative-to-member operation")
                matching.sort(
                    key=lambda operation_index: (
                        0
                        if classifications[operation_index].operation.exactness_class
                        is ExactnessClass.EXACT_TRANSLATION
                        else 1
                        if classifications[operation_index].operation.rotation_int == IDENTITY
                        and classifications[operation_index].operation.eps == 1
                        else 2
                        if classifications[operation_index].operation.eps == 1
                        else 3
                    )
                )
                maps.append((member, matching[0]))
            saving = 2 < len(members)
            continuum_translation = saving and any(
                classifications[operation_index].operation.rotation_int == IDENTITY
                and classifications[operation_index].operation.eps == 1
                and classifications[operation_index].operation.exactness_class
                is ExactnessClass.EXACT_IN_CONTINUUM_ONLY
                for _, operation_index in maps
            )
            class_reasons = (
                (CoverageReason.FEATURE_VALIDATION_NOT_ESTABLISHED,)
                if continuum_translation
                else (CoverageReason.SHADOW_PENDING,)
                if saving
                else (CoverageReason.NO_SAVING,)
            )
            reasons.update(class_reasons)
            classes.append(
                CoverageClass(
                    members,
                    representative,
                    shadow,
                    tuple(maps),
                    CoverageStatus.REJECTED_EXPANDED
                    if continuum_translation
                    else CoverageStatus.CANDIDATE_PENDING_SHADOW
                    if saving
                    else CoverageStatus.REJECTED_EXPANDED
                    if shadow
                    else CoverageStatus.NOT_ESTABLISHED,
                    class_reasons,
                )
            )
    reduced = any(c.reduced for c in classes)
    strategy = CoverageStrategy.PARTIALLY_REDUCED if reduced else CoverageStrategy.ALL_SUBSPACES
    if user_policy.declared_classes:
        reasons.add(CoverageReason.USER_RESTRICTION)
        if reduced:
            strategy = CoverageStrategy.USER_RESTRICTED
    qualification = CoverageQualification(
        inventory.digest,
        inventory.effective_fdf_sha256,
        state,
        policy,
        user_policy,
        classifications,
        tuple(classes),
        strategy,
        tuple(sorted(reasons, key=lambda r: r.value)),
        search_reasons,
        would_reduce_to,
        tuple(sorted({(s.species_label, s.identity_digest) for s in sites})),
    )
    # Validate even fallback evidence: NaN/inf must never enter canonical JSON.
    _ = qualification.digest
    return qualification
