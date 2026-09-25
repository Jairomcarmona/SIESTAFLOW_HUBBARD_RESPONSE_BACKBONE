"""Material-neutral planning and authorization of LR-U symmetry reduction.

The module contains no FDF mutation, SIESTA parser, scheduler command, site
path, chemical symbol, or cluster setting.  It converts a *verified* symmetry
certificate into a finite-difference run plan and keeps reduction provisional
until direct shadow responses pass declared tolerances.

This is deliberately stricter than merely grouping atoms by geometry: a
certificate must already bind geometry, magnetic evidence and local Hubbard
definitions.  By default only identity-rotation operations (translations in
the supplied fractional basis) may reduce a correlated subspace.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from math import isfinite
from typing import Iterable, Sequence
import re

from symmetry_reduction_proposal import Operation, SymmetryCertificate


class SymmetryPlanError(ValueError):
    """The supplied scientific evidence cannot produce a safe run plan."""


@dataclass(frozen=True)
class SymmetryEvidenceBundle:
    """Explicit provenance required by the strict symmetry planning route.

    The legacy planner accepts a verified ``SymmetryCertificate`` for backward
    compatibility.  The strict route additionally binds that certificate to
    the exact reference FDF, output, magnetic moments and local Hubbard
    definitions.  This prevents a geometrically valid certificate from being
    reused with a different magnetic state or projector definition.
    """

    certificate_input_hash: str
    reference_fdf_sha256: str
    reference_output_sha256: str
    magnetic_evidence_sha256: str
    subspace_fingerprints: tuple[str, ...]
    magnetic_evidence_complete: bool = True
    reference_output_normal: bool = True
    source_format: str = "versioned_reference_evidence_v1"

    def validate(self, *, certificate: SymmetryCertificate, site_count: int) -> None:
        hashes = (
            self.certificate_input_hash,
            self.reference_fdf_sha256,
            self.reference_output_sha256,
            self.magnetic_evidence_sha256,
        )
        if any(not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value)
               for value in hashes):
            raise SymmetryPlanError("symmetry evidence hashes must be lowercase SHA-256")
        if self.certificate_input_hash != certificate.input_hash:
            raise SymmetryPlanError("symmetry evidence is bound to a different certificate input")
        if not self.magnetic_evidence_complete or not self.reference_output_normal:
            raise SymmetryPlanError("reference magnetic evidence is incomplete or not normal")
        if self.source_format != "versioned_reference_evidence_v1":
            raise SymmetryPlanError("unknown symmetry evidence format")
        if (len(self.subspace_fingerprints) != site_count
                or any(not isinstance(value, str) or not value
                       for value in self.subspace_fingerprints)):
            raise SymmetryPlanError("subspace evidence must cover every atom")


def filter_evidence_compatible_operations(
    certificate: SymmetryCertificate,
    evidence: SymmetryEvidenceBundle,
    atom_ids: Sequence[str],
) -> tuple[Operation, ...]:
    """Return only magnetic operations preserving declared local subspaces.

    Magnetic compatibility is already certified by ``detect_symmetry``;
    this second, explicit filter prevents reduction when two mapped atoms have
    different local Hubbard definitions.  Non-trivial orbital rotations are
    still rejected by the planner's ``translation_only`` policy.
    """
    evidence.validate(certificate=certificate, site_count=len(atom_ids))
    if len(set(atom_ids)) != len(atom_ids):
        raise SymmetryPlanError("atom identifiers must be unique for evidence filtering")
    allowed: list[Operation] = []
    for operation in certificate.magnetic_operations:
        if any(evidence.subspace_fingerprints[source]
               != evidence.subspace_fingerprints[destination]
               for source, destination in enumerate(operation.permutation)):
            continue
        allowed.append(operation)
    return tuple(allowed)


class ReductionState(str, Enum):
    EXPLICIT_REQUIRED = "EXPLICIT_REQUIRED"
    SHADOW_VALIDATION_REQUIRED = "SHADOW_VALIDATION_REQUIRED"
    REDUCTION_AUTHORIZED = "REDUCTION_AUTHORIZED"
    EXPLICIT_FALLBACK_REQUIRED = "EXPLICIT_FALLBACK_REQUIRED"


class ResponseMode(str, Enum):
    BARE = "BARE"
    SCREENED = "SCREENED"


@dataclass(frozen=True)
class SymmetryReductionPolicy:
    """Predeclared policy; no post-hoc tolerance selection is allowed."""

    alpha_ev: float
    occupation_max_abs_e: float = 2.0e-5
    response_max_abs_e_per_ev: float = 5.0e-5
    response_max_relative_l2: float = 1.0e-3
    translation_only: bool = True
    require_shadow_validation: bool = True

    def validate(self) -> None:
        numeric = (self.alpha_ev, self.occupation_max_abs_e,
                   self.response_max_abs_e_per_ev,
                   self.response_max_relative_l2)
        if not all(isfinite(value) and value > 0.0 for value in numeric):
            raise SymmetryPlanError("symmetry policy tolerances must be positive and finite")


@dataclass(frozen=True)
class PerturbationSpec:
    """One ±alpha BARE or SCREENED input to be materialized by a backend."""

    run_id: str
    orbit_id: str
    site_index: int
    site_id: str
    mode: ResponseMode
    alpha_ev: float
    purpose: str  # representative, shadow, or explicit_fallback


@dataclass(frozen=True)
class SymmetryOrbitPlan:
    orbit_id: str
    member_indices: tuple[int, ...]
    member_site_ids: tuple[str, ...]
    representative_index: int
    representative_site_id: str
    shadow_index: int | None
    shadow_site_id: str | None
    operation: Operation | None


@dataclass(frozen=True)
class SymmetryReductionPlan:
    """A pure scientific plan that a backend/DAG may later materialize."""

    state: ReductionState
    certificate_digest: str | None
    policy: SymmetryReductionPolicy
    correlated_site_ids: tuple[str, ...]
    orbit_plans: tuple[SymmetryOrbitPlan, ...]
    perturbations: tuple[PerturbationSpec, ...]
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "state": self.state.value,
            "certificate_digest": self.certificate_digest,
            "policy": asdict(self.policy),
            "correlated_site_ids": list(self.correlated_site_ids),
            "orbit_plans": [
                {
                    **{key: value for key, value in asdict(orbit).items() if key != "operation"},
                    "operation": asdict(orbit.operation) if orbit.operation else None,
                }
                for orbit in self.orbit_plans
            ],
            "perturbations": [
                {**asdict(spec), "mode": spec.mode.value}
                for spec in self.perturbations
            ],
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class ShadowObservation:
    """Comparison of one directly calculated shadow against its prediction."""

    orbit_id: str
    scientific_output_valid: bool
    occupation_max_abs_e: float
    chi0_max_abs_e_per_ev: float
    chi0_relative_l2: float
    chi_max_abs_e_per_ev: float
    chi_relative_l2: float

    def validate(self) -> None:
        metrics = (self.occupation_max_abs_e, self.chi0_max_abs_e_per_ev,
                   self.chi0_relative_l2, self.chi_max_abs_e_per_ev,
                   self.chi_relative_l2)
        if not all(isfinite(value) and value >= 0.0 for value in metrics):
            raise SymmetryPlanError("shadow metrics must be finite and non-negative")


@dataclass(frozen=True)
class ReductionAuthorization:
    state: ReductionState
    accepted_orbits: tuple[str, ...]
    rejected_orbits: tuple[str, ...]
    explicit_expansion_site_ids: tuple[str, ...]
    reasons: tuple[str, ...]


def _identity_rotation(operation: Operation) -> bool:
    return operation.rotation == ((1, 0, 0), (0, 1, 0), (0, 0, 1))


def _run_specs(orbit: SymmetryOrbitPlan, policy: SymmetryReductionPolicy, *, purpose: str,
               site_index: int, site_id: str) -> tuple[PerturbationSpec, ...]:
    prefix = f"{orbit.orbit_id}_{purpose}_{site_id}"
    return tuple(
        PerturbationSpec(
            run_id=f"{prefix}_{mode.value.lower()}_{sign}", orbit_id=orbit.orbit_id,
            site_index=site_index, site_id=site_id, mode=mode,
            alpha_ev=sign_value * policy.alpha_ev, purpose=purpose,
        )
        for mode in ResponseMode
        for sign, sign_value in (("minus", -1.0), ("plus", 1.0))
    )


def _validate_site_ids(atom_ids: Sequence[str], correlated_site_ids: Sequence[str]) -> dict[str, int]:
    if not atom_ids or len(set(atom_ids)) != len(atom_ids):
        raise SymmetryPlanError("atom identifiers must be non-empty and unique")
    if not correlated_site_ids or len(set(correlated_site_ids)) != len(correlated_site_ids):
        raise SymmetryPlanError("correlated site identifiers must be non-empty and unique")
    positions = {site_id: index for index, site_id in enumerate(atom_ids)}
    unknown = set(correlated_site_ids) - set(positions)
    if unknown:
        raise SymmetryPlanError(f"correlated site identifiers absent from atom IDs: {sorted(unknown)}")
    return positions


def _operation_for_pair(operations: Iterable[Operation], source: int, destination: int) -> Operation | None:
    return next((operation for operation in operations if operation.permutation[source] == destination), None)


def build_symmetry_reduction_plan(
    atom_ids: Sequence[str],
    correlated_site_ids: Sequence[str],
    certificate: SymmetryCertificate | None,
    policy: SymmetryReductionPolicy,
    evidence: SymmetryEvidenceBundle | None = None,
) -> SymmetryReductionPlan:
    """Create representative/shadow perturbations from verified evidence.

    If the certificate is absent, rejected, ambiguous, or has no permitted
    operation for a correlated orbit, the returned plan explicitly perturbs
    every correlated site.  It never silently picks a geometric nearest site.
    """
    policy.validate()
    positions = _validate_site_ids(atom_ids, correlated_site_ids)
    correlated_indices = tuple(sorted(positions[site_id] for site_id in correlated_site_ids))
    correlated_set = set(correlated_indices)

    if certificate is None:
        return _explicit_plan(tuple(atom_ids), correlated_indices, policy,
                              reasons=("symmetry_certificate_missing", "reduction_fail_closed"))
    certificate.verify()
    if certificate.site_count != len(atom_ids) or not certificate.reduction_enabled:
        return _explicit_plan(tuple(atom_ids), correlated_indices, policy,
                              certificate_digest=certificate.digest,
                              reasons=("symmetry_certificate_not_reduction_enabled", "reduction_fail_closed"))

    if evidence is None:
        operations_source = certificate.magnetic_operations
    else:
        operations_source = filter_evidence_compatible_operations(certificate, evidence, atom_ids)
    operations = tuple(operation for operation in operations_source
                       if not policy.translation_only or _identity_rotation(operation))
    if not operations:
        return _explicit_plan(tuple(atom_ids), correlated_indices, policy,
                              certificate_digest=certificate.digest,
                              reasons=("no_permitted_symmetry_operation", "reduction_fail_closed"))

    orbit_indices: list[tuple[int, ...]] = []
    assigned: set[int] = set()
    for raw_orbit in certificate.orbits:
        selected = tuple(sorted(set(raw_orbit) & correlated_set))
        if selected:
            orbit_indices.append(selected)
            assigned.update(selected)
    if assigned != correlated_set or len({index for orbit in orbit_indices for index in orbit}) != len(correlated_set):
        raise SymmetryPlanError("certificate correlated orbits do not partition the correlated subspace")

    orbits: list[SymmetryOrbitPlan] = []
    perturbations: list[PerturbationSpec] = []
    incomplete = False
    for number, members in enumerate(sorted(orbit_indices), 1):
        representative = min(members)
        shadow: int | None = None
        operation: Operation | None = None
        for candidate in members:
            if candidate != representative and (found := _operation_for_pair(operations, representative, candidate)):
                shadow, operation = candidate, found
                break
        if len(members) > 1 and shadow is None:
            incomplete = True
        orbit = SymmetryOrbitPlan(
            orbit_id=f"orbit_{number:03d}", member_indices=members,
            member_site_ids=tuple(atom_ids[index] for index in members),
            representative_index=representative, representative_site_id=atom_ids[representative],
            shadow_index=shadow, shadow_site_id=atom_ids[shadow] if shadow is not None else None,
            operation=operation,
        )
        orbits.append(orbit)
        perturbations.extend(_run_specs(orbit, policy, purpose="representative",
                                        site_index=representative, site_id=atom_ids[representative]))
        if shadow is not None and policy.require_shadow_validation:
            perturbations.extend(_run_specs(orbit, policy, purpose="shadow",
                                            site_index=shadow, site_id=atom_ids[shadow]))

    if incomplete:
        return _explicit_plan(tuple(atom_ids), correlated_indices, policy,
                              certificate_digest=certificate.digest,
                              reasons=("correlated_orbit_missing_direct_shadow_operation", "reduction_fail_closed"))
    state = ReductionState.SHADOW_VALIDATION_REQUIRED if policy.require_shadow_validation else ReductionState.REDUCTION_AUTHORIZED
    return SymmetryReductionPlan(
        state=state, certificate_digest=certificate.digest, policy=policy,
        correlated_site_ids=tuple(correlated_site_ids), orbit_plans=tuple(orbits),
        perturbations=tuple(perturbations),
        reasons=("direct_shadow_validation_required",) if policy.require_shadow_validation else ("policy_allows_unvalidated_reduction",),
    )


def _explicit_plan(atom_ids: tuple[str, ...], correlated_indices: tuple[int, ...],
                   policy: SymmetryReductionPolicy, *, certificate_digest: str | None = None,
                   reasons: tuple[str, ...]) -> SymmetryReductionPlan:
    orbits = []
    perturbations = []
    for number, index in enumerate(correlated_indices, 1):
        orbit = SymmetryOrbitPlan(
            orbit_id=f"orbit_{number:03d}", member_indices=(index,), member_site_ids=(atom_ids[index],),
            representative_index=index, representative_site_id=atom_ids[index],
            shadow_index=None, shadow_site_id=None, operation=None,
        )
        orbits.append(orbit)
        perturbations.extend(_run_specs(orbit, policy, purpose="explicit_fallback",
                                        site_index=index, site_id=atom_ids[index]))
    return SymmetryReductionPlan(
        state=ReductionState.EXPLICIT_REQUIRED, certificate_digest=certificate_digest,
        policy=policy, correlated_site_ids=tuple(atom_ids[index] for index in correlated_indices),
        orbit_plans=tuple(orbits), perturbations=tuple(perturbations), reasons=reasons,
    )


def authorize_symmetry_reduction(plan: SymmetryReductionPlan,
                                 observations: Sequence[ShadowObservation]) -> ReductionAuthorization:
    """Authorize only classes whose exact direct shadows pass all gates."""
    if plan.state is ReductionState.EXPLICIT_REQUIRED:
        return ReductionAuthorization(ReductionState.EXPLICIT_REQUIRED, (), (), plan.correlated_site_ids, plan.reasons)
    expected = {orbit.orbit_id for orbit in plan.orbit_plans if orbit.shadow_index is not None}
    received = {observation.orbit_id for observation in observations}
    if received != expected:
        raise SymmetryPlanError("shadow observations must cover exactly the planned shadow orbits")
    by_orbit = {observation.orbit_id: observation for observation in observations}
    accepted, rejected = [], []
    for orbit_id in sorted(expected):
        observation = by_orbit[orbit_id]
        observation.validate()
        passed = (
            observation.scientific_output_valid
            and observation.occupation_max_abs_e <= plan.policy.occupation_max_abs_e
            and observation.chi0_max_abs_e_per_ev <= plan.policy.response_max_abs_e_per_ev
            and observation.chi0_relative_l2 <= plan.policy.response_max_relative_l2
            and observation.chi_max_abs_e_per_ev <= plan.policy.response_max_abs_e_per_ev
            and observation.chi_relative_l2 <= plan.policy.response_max_relative_l2
        )
        (accepted if passed else rejected).append(orbit_id)
    rejected_sites = tuple(
        site_id for orbit in plan.orbit_plans if orbit.orbit_id in rejected for site_id in orbit.member_site_ids
    )
    if rejected:
        return ReductionAuthorization(
            ReductionState.EXPLICIT_FALLBACK_REQUIRED, tuple(accepted), tuple(rejected), rejected_sites,
            ("one_or_more_direct_shadows_failed", "expand_rejected_orbits_to_explicit_perturbations"),
        )
    return ReductionAuthorization(
        ReductionState.REDUCTION_AUTHORIZED, tuple(accepted), (), (),
        ("all_direct_shadows_passed", "translation_subgroup_authorized"),
    )


def explicit_expansion_specs(plan: SymmetryReductionPlan,
                             authorization: ReductionAuthorization) -> tuple[PerturbationSpec, ...]:
    """Return the direct responses required after a rejected shadow gate.

    Existing validated results are not represented here as reusable scheduler
    state; an execution adapter must checkpoint and skip them by provenance.
    Returning the full rejected orbit makes the scientific fallback explicit
    and prevents an implementation from retaining an unvalidated reconstructed
    column.
    """
    if authorization.state is not ReductionState.EXPLICIT_FALLBACK_REQUIRED:
        return ()
    # ``correlated_site_ids`` retains input order, while orbit indices refer to
    # the full atom list.  Use plan orbit membership to preserve exact IDs.
    specs: list[PerturbationSpec] = []
    for orbit in plan.orbit_plans:
        if orbit.orbit_id not in authorization.rejected_orbits:
            continue
        for site_id, site_index in zip(orbit.member_site_ids, orbit.member_indices):
            specs.extend(_run_specs(orbit, plan.policy, purpose="explicit_fallback",
                                    site_index=site_index, site_id=site_id))
    return tuple(specs)
