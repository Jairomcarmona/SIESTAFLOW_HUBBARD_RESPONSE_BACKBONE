"""Pure deterministic assembly of injected inventory, reference and coverage.

Only declared fixed or explicit grids execute here. Candidate coverage requires
its mandatory shadow before READY; calibrated amplitudes require later tasks.
"""

from __future__ import annotations

from dataclasses import replace

from .coverage_models import (
    CoverageClass,
    CoverageQualification,
    CoverageReason,
    CoverageStatus,
    CoverageStrategy,
)
from .fdebq_models import CalibrationProtocol, RoundStatus
from .fdebq_models import CalibrationQualification as RoundQualification
from .fdebq_rounds import production_column_plan
from .perturbation_plan import (
    SCHEMA,
    AlphaStrategy,
    CalibrationQualification,
    CalibrationStatus,
    ColumnCalibration,
    PlanReason,
    PlanStatus,
    ReconstructionMap,
    ResolvedPerturbationPlan,
    RunSpec,
)
from .perturbation_plan_evidence import PerturbationPlanError, freeze_inventory
from .response_protocol import PerturbationStrategy, ResolvedResponseProtocol
from .state_evidence import EvidenceStatus
from .subspace_inventory import CorrelatedSubspaceInventory, InventoryStatus
from .symmetry_operation_models import IDENTITY


def resolve_perturbation_plan(
    inventory: CorrelatedSubspaceInventory,
    coverage: CoverageQualification,
    response_protocol: ResolvedResponseProtocol,
    *,
    source_fdf_sha256: str,
    alpha_strategy: AlphaStrategy,
    planner_version: str,
    backend_identity: str,
    tau_u_ev: float | None,
    explicit_sites: tuple[str, ...] | None = None,
    calibration_protocol: CalibrationProtocol | None = None,
    calibration_qualification: RoundQualification | None = None,
) -> ResolvedPerturbationPlan:
    """Freeze evidence; explicit targets bypass reduction, never reference admission.

    Explicit sites enumerate the whole inventory. A partial user declaration cannot
    silently discard scientific columns. Fixed targets preserve the supplied grid
    and estimator even when missing archived evidence lowers the plan's state.
    """
    try:
        return _resolve(
            inventory,
            coverage,
            response_protocol,
            source_fdf_sha256=source_fdf_sha256,
            alpha_strategy=alpha_strategy,
            planner_version=planner_version,
            backend_identity=backend_identity,
            tau_u_ev=tau_u_ev,
            explicit_sites=explicit_sites,
            calibration_protocol=calibration_protocol,
            calibration_qualification=calibration_qualification,
        )
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        raise PerturbationPlanError(f"cannot resolve perturbation plan: {exc}") from exc


def _resolve(
    inventory: CorrelatedSubspaceInventory,
    coverage: CoverageQualification,
    response_protocol: ResolvedResponseProtocol,
    *,
    source_fdf_sha256: str,
    alpha_strategy: AlphaStrategy,
    planner_version: str,
    backend_identity: str,
    tau_u_ev: float | None,
    explicit_sites: tuple[str, ...] | None,
    calibration_protocol: CalibrationProtocol | None,
    calibration_qualification: RoundQualification | None,
) -> ResolvedPerturbationPlan:
    inventory = freeze_inventory(inventory)
    if not isinstance(alpha_strategy, AlphaStrategy):
        raise PerturbationPlanError("alpha_strategy must be an AlphaStrategy")
    strategy = {
        AlphaStrategy.FIXED_PROTOCOL_GRID: PerturbationStrategy.FIXED_PROTOCOL_GRID,
        AlphaStrategy.USER_EXPLICIT_GRID: PerturbationStrategy.USER_EXPLICIT_GRID,
        AlphaStrategy.CALIBRATED_GRID: PerturbationStrategy.CALIBRATED,
    }[alpha_strategy]
    if response_protocol.strategy is not strategy:
        raise PerturbationPlanError("alpha strategy disagrees with response protocol")
    sites = tuple(s.site_id for s in inventory.subspaces)
    if {c.site_id for c in response_protocol.columns} != set(sites):
        raise PerturbationPlanError("injected response protocol must cover the entire inventory")
    if explicit_sites is not None and (
        len(set(explicit_sites)) != len(explicit_sites) or set(explicit_sites) != set(sites)
    ):
        raise PerturbationPlanError("explicit sites must enumerate the whole inventory without duplicates")
    reasons: set[PlanReason] = set()
    status = PlanStatus.READY
    if inventory.status is not InventoryStatus.OK or not sites:
        reasons.add(PlanReason.INVENTORY_NOT_ESTABLISHED)
        status = PlanStatus.NOT_ESTABLISHED
    reference = coverage.reference
    if (
        reference.status is not EvidenceStatus.ADMISSIBLE
        or not reference.input_output_consistent
        or reference.perturbation_detected
        or not reference.state.normal_completion_verified
        or not reference.state.scf_converged
    ):
        reasons.add(PlanReason.REFERENCE_NOT_ADMISSIBLE)
        status = PlanStatus.NOT_ESTABLISHED
    bypass = explicit_sites is not None or not coverage.user_policy.enabled

    def feature_class(c: CoverageClass) -> bool:
        return c.reduced and any(
            coverage.operations[i].operation.eps != 1
            or coverage.operations[i].operation.rotation_int != IDENTITY
            for _, i in c.ops_rep_to_member
        )

    if coverage.user_policy.enabled and (coverage.policy.allow_spin_flip or coverage.policy.allow_rotations):
        # No recorded prospective V2/V3 contract or runtime I.5 producer exists.
        # An opt-in records candidates but cannot grant production readiness.
        reasons.add(PlanReason.FEATURES_NOT_ENABLED)
        if status is PlanStatus.READY:
            status = PlanStatus.REVIEW
    if bypass:
        reason = CoverageReason.DISABLED_OR_FIXED
        coverage = replace(
            coverage,
            classes=tuple(
                CoverageClass((s,), s, None, (), CoverageStatus.DISABLED, (reason,)) for s in sites
            ),
            strategy=CoverageStrategy.ALL_SUBSPACES,
            reasons=tuple(sorted(set(coverage.reasons) | {reason}, key=lambda r: r.value)),
        )
        reasons.add(PlanReason.DISABLED_OR_FIXED)
    else:
        rejected = CoverageReason.FEATURE_VALIDATION_NOT_ESTABLISHED
        features = any(feature_class(c) for c in coverage.classes)
        coverage = replace(
            coverage,
            classes=tuple(
                replace(c, status=CoverageStatus.REJECTED_EXPANDED, reasons=(rejected,))
                if feature_class(c)
                else c
                for c in sorted(coverage.classes, key=lambda c: sites.index(c.representative))
            ),
            reasons=tuple(
                sorted(set(coverage.reasons) | ({rejected} if features else set()), key=lambda r: r.value)
            ),
        )
        reduced = [c for c in coverage.classes if c.reduced]
        if not reduced:
            coverage = replace(coverage, strategy=CoverageStrategy.ALL_SUBSPACES)
        if reduced and len(reduced) == len(coverage.classes) and not coverage.user_policy.declared_classes:
            coverage = replace(coverage, strategy=CoverageStrategy.SYMMETRY_REDUCED)
        if any(c.status is CoverageStatus.CANDIDATE_PENDING_SHADOW for c in reduced):
            reasons.add(PlanReason.SHADOW_PENDING)
            if status is PlanStatus.READY:
                status = PlanStatus.REVIEW
    computed = coverage.computed_columns
    calibration = []
    runs: list[RunSpec] = []
    maps = []
    calibrated = alpha_strategy is AlphaStrategy.CALIBRATED_GRID
    established_calibration = False
    if calibrated and calibration_protocol is not None and calibration_qualification is not None:
        if calibration_qualification.protocol_sha256 != calibration_protocol.digest:
            pass  # Digest is recorded; semantic calibration/protocol constraints follow.
        if tau_u_ev != calibration_protocol.tau_u_ev:
            raise PerturbationPlanError("tau_u_ev must equal the explicit calibration protocol requirement")
        if calibration_qualification.status in (RoundStatus.QUALIFIED, RoundStatus.REVIEW):
            selected = tuple(
                production_column_plan(c, calibration_protocol) for c in calibration_qualification.columns
            )
            if all(c is not None for c in selected) and {
                (c.site_id, c.mode) for c in selected if c is not None
            } == {(s, mode) for s in sites for mode in (c.mode for c in response_protocol.columns)}:
                response_protocol = replace(
                    response_protocol,
                    columns=tuple(c for c in selected if c is not None),
                    protocol_version=calibration_protocol.version,
                )
                established_calibration = True
                reasons.add(PlanReason.CALIBRATION_REVIEW)
                # TASK17's recorded T0–T4 qualification is not yet available.
                if status is PlanStatus.READY:
                    status = PlanStatus.REVIEW
    elif calibration_protocol is not None or calibration_qualification is not None:
        raise PerturbationPlanError("calibration protocol and qualification require CALIBRATED_GRID together")
    if calibrated and not established_calibration:
        reasons.add(
            PlanReason.CALIBRATION_NOT_ENABLED
            if calibration_protocol is None
            else PlanReason.CALIBRATION_NOT_ESTABLISHED
        )
        status = PlanStatus.NOT_ESTABLISHED
        computed = ()
        # The seed remains provenance only; no calibrated run is executable.
        coverage = replace(
            coverage,
            classes=tuple(
                CoverageClass(
                    (s,), s, None, (), CoverageStatus.NOT_ESTABLISHED, (CoverageReason.DISABLED_OR_FIXED,)
                )
                for s in sites
            ),
            strategy=CoverageStrategy.ALL_SUBSPACES,
        )
    else:
        columns = {(c.site_id, c.mode): c for c in response_protocol.columns}
        for group in coverage.classes:
            for site in (group.representative, group.shadow) if group.reduced else group.members:
                assert site is not None
                for mode in sorted({c.mode for c in response_protocol.columns}, key=lambda m: m.value):
                    original = columns[(group.representative if group.reduced else site, mode)]
                    column = replace(original, site_id=site)
                    # Shadows inherit the representative's complete ColumnPlan.
                    columns[(site, mode)] = column
                    evidence_sha256 = (
                        calibration_qualification.evidence_sha256
                        if calibrated and calibration_qualification is not None
                        else None
                    )
                    calibration.append(
                        ColumnCalibration(
                            alpha_strategy,
                            column,
                            CalibrationQualification(
                                CalibrationStatus.REVIEW if calibrated else CalibrationStatus.NOT_ASSESSED,
                                (evidence_sha256,) if evidence_sha256 is not None else (),
                                calibration_qualification if calibrated else None,
                                calibration_protocol if calibrated else None,
                            ),
                        )
                    )
                    runs.extend(RunSpec(site, mode, a) for v in column.amplitudes_ev for a in (-v, v))
            if group.reduced:
                for site, operation_id in group.ops_rep_to_member:
                    if site not in computed:
                        maps.append(ReconstructionMap(site, group.representative, operation_id))
        response_protocol = replace(response_protocol, columns=tuple(columns.values()))
    return ResolvedPerturbationPlan(
        SCHEMA,
        source_fdf_sha256,
        inventory.effective_fdf_sha256,
        inventory,
        reference,
        coverage,
        response_protocol,
        tuple(calibration),
        computed,
        tuple(runs),
        tuple(maps),
        response_protocol.protocol_version,
        planner_version,
        backend_identity,
        tau_u_ev,
        status,
        tuple(sorted(reasons, key=lambda r: r.value)),
    )
