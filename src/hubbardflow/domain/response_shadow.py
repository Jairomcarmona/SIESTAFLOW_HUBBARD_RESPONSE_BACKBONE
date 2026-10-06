"""Mandatory scalar shadows falsify coverage using additive print bounds.

Only a supplied F1–F8 qualification can propose an orbit. A passed translation
shadow authorizes scalar reconstruction. Spin flips and rotations additionally
require prospective validation; the incomplete admission API fails closed.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum

from .coverage_models import CoverageStatus
from .perturbation_plan import ResolvedPerturbationPlan
from .response_budget_models import _Record
from .response_error_budget import ElementSeries, PrintedResponseBudget, printed_response_budget
from .response_reconstruction import (
    Matrix,
    ObservableKind,
    ReconstructionClass,
    ReconstructionResult,
    ScalarPermutation,
    reconstruct_matrix,
)
from .scf_ladder_models import ScfResponseEstimate, ScfStatus
from .symmetry_operation_models import IDENTITY
from .symmetry_reduction import ResponseMode
from .validation import ValidationError, require_finite, require_nonnegative_finite


class ResponseShadowError(ValueError):
    """Missing shadow evidence must expand coverage, never permit omission."""


class ShadowReason(str, Enum):
    WITHIN_PRINT_BOUNDS = "WITHIN_PRINT_BOUNDS"
    OUTSIDE_PRINT_BOUNDS = "OUTSIDE_PRINT_BOUNDS"
    SCIENTIFIC_STATE_NOT_ESTABLISHED = "SCIENTIFIC_STATE_NOT_ESTABLISHED"
    INCOMPLETE_RESPONSE_EVIDENCE = "INCOMPLETE_RESPONSE_EVIDENCE"
    PREVIOUSLY_REJECTED_CLASS = "PREVIOUSLY_REJECTED_CLASS"
    SCF_ESTIMATE_NOT_ESTABLISHED = "SCF_ESTIMATE_NOT_ESTABLISHED"
    FEATURE_VALIDATION_NOT_ESTABLISHED = "FEATURE_VALIDATION_NOT_ESTABLISHED"
    REFERENCE_STATE_NOT_EQUIVALENT = "REFERENCE_STATE_NOT_EQUIVALENT"
    REFERENCE_FERMI_NOT_EQUIVALENT = "REFERENCE_FERMI_NOT_EQUIVALENT"


@dataclass(frozen=True)
class ShadowComparison(_Record):
    site_observed: str
    mode: ResponseMode
    direct_e_per_ev: float
    reconstructed_e_per_ev: float
    direct_bound_e_per_ev: float
    representative_bound_e_per_ev: float
    direct_scf_estimate_e_per_ev: float | None = None
    representative_scf_estimate_e_per_ev: float | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        try:
            require_nonnegative_finite(self.direct_bound_e_per_ev, "direct_bound_e_per_ev")
            require_nonnegative_finite(self.representative_bound_e_per_ev, "representative_bound_e_per_ev")
            require_finite(self.direct_bound_e_per_ev + self.representative_bound_e_per_ev, "summed bounds")
            require_finite(self.direct_e_per_ev - self.reconstructed_e_per_ev, "shadow residual")
            for value in (self.direct_scf_estimate_e_per_ev, self.representative_scf_estimate_e_per_ev):
                if value is not None:
                    require_nonnegative_finite(value, "SCF estimate")
            require_finite(
                self.direct_bound_e_per_ev
                + self.representative_bound_e_per_ev
                + (self.direct_scf_estimate_e_per_ev or 0)
                + (self.representative_scf_estimate_e_per_ev or 0),
                "total shadow budget",
            )
        except ValidationError as exc:
            raise ResponseShadowError(str(exc)) from exc

    @property
    def passed(self) -> bool:
        return abs(self.direct_e_per_ev - self.reconstructed_e_per_ev) <= (
            self.direct_bound_e_per_ev
            + self.representative_bound_e_per_ev
            + (self.direct_scf_estimate_e_per_ev or 0)
            + (self.representative_scf_estimate_e_per_ev or 0)
        )


@dataclass(frozen=True)
class ShadowOutcome(_Record):
    representative: str
    shadow: str
    status: CoverageStatus
    comparisons: tuple[ShadowComparison, ...]
    reason: ShadowReason

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.status not in (CoverageStatus.PROVEN, CoverageStatus.REJECTED_EXPANDED):
            raise ResponseShadowError("shadow outcome must be PROVEN or REJECTED_EXPANDED")
        if self.status is CoverageStatus.PROVEN and (
            self.reason is not ShadowReason.WITHIN_PRINT_BOUNDS
            or not self.comparisons
            or not all(c.passed for c in self.comparisons)
        ):
            raise ResponseShadowError("PROVEN requires every direct comparison within print bounds")


@dataclass(frozen=True)
class ShadowMatrices:
    chi0_raw: Matrix
    chi_raw: Matrix

    def __post_init__(self) -> None:
        object.__setattr__(self, "chi0_raw", ReconstructionResult(self.chi0_raw).raw_matrix)
        object.__setattr__(self, "chi_raw", ReconstructionResult(self.chi_raw).raw_matrix)
        if len(self.chi0_raw) != len(self.chi_raw):
            raise ResponseShadowError("raw chi0 and chi must have identical dimensions")

    def to_mapping(self) -> dict[str, object]:
        return {"chi0_raw": self.chi0_raw, "chi_raw": self.chi_raw}

    @classmethod
    def from_mapping(cls, row: Mapping[str, object]) -> ShadowMatrices:
        from typing import cast

        if set(row) != {"chi0_raw", "chi_raw"}:
            raise ResponseShadowError("raw matrices mapping must contain exactly chi0_raw and chi_raw")
        return cls(
            tuple(tuple(r) for r in cast(Sequence[Sequence[float]], row["chi0_raw"])),
            tuple(tuple(r) for r in cast(Sequence[Sequence[float]], row["chi_raw"])),
        )


def response_budgets(
    plan: ResolvedPerturbationPlan, series: Sequence[ElementSeries]
) -> tuple[tuple[tuple[str, ResponseMode, str], PrintedResponseBudget], ...]:
    """Use ColumnPlan for every observed row, including the inherited shadow."""
    columns = {(c.site_id, c.mode): c for c in plan.response_protocol.columns}
    keys = [(s.site_perturbed, s.mode, s.site_observed) for s in series]
    if len(keys) != len(set(keys)):
        raise ResponseShadowError("duplicate response series")
    sites = {s.site_id for s in plan.inventory.subspaces}
    for s in series:
        column = columns.get((s.site_perturbed, s.mode))
        if column is None or s.site_observed not in sites:
            raise ResponseShadowError("response series must name inventory sites and resolved modes")
        if tuple(sorted({abs(p.alpha_ev) for p in s.points})) != column.amplitudes_ev:
            raise ResponseShadowError("response series amplitudes must match its ColumnPlan exactly")
    return tuple(
        (key, printed_response_budget(s, columns[(s.site_perturbed, s.mode)].estimator))
        for key, s in sorted(zip(keys, series, strict=True), key=lambda item: item[0])
    )


def qualify_shadows(
    plan: ResolvedPerturbationPlan,
    series: Sequence[ElementSeries],
    *,
    scientific_state_valid: bool,
    scf_estimates: Sequence[ScfResponseEstimate] = (),
) -> tuple[ShadowOutcome, ...]:
    """Check all (I, mode) with the same declared estimator and permuted radius.

    Missing state evidence or printed widths conservatively expands the entire
    class. No occupation, relative-norm or empirically chosen tolerance is used.
    """
    if type(scientific_state_valid) is not bool:
        raise ResponseShadowError("scientific_state_valid must be an explicit boolean")
    sites = tuple(s.site_id for s in plan.inventory.subspaces)
    columns = {(c.site_id, c.mode): c for c in plan.response_protocol.columns}
    budgets = dict(response_budgets(plan, series))
    scf = {(e.site_perturbed, e.mode, e.site_observed): e for e in scf_estimates}
    if len(scf) != len(scf_estimates) or not scf.keys() <= budgets.keys():
        raise ResponseShadowError("SCF estimates must identify distinct available response elements")
    if any(e.estimator != columns[(e.site_perturbed, e.mode)].estimator for e in scf_estimates):
        raise ResponseShadowError("SCF estimates must use the declared ColumnPlan estimator")
    outcomes = []
    for group in plan.coverage.classes:
        if not group.reduced:
            continue
        if group.shadow is None:
            raise ResponseShadowError("a reduced class must declare its shadow")
        features = False
        for _, op_id in group.ops_rep_to_member:
            classification = plan.coverage.operations[op_id]
            op = classification.operation
            if (
                not classification.accepted
                or (op.eps == -1 and not plan.coverage.policy.allow_spin_flip)
                or (op.rotation_int != IDENTITY and not plan.coverage.policy.allow_rotations)
            ):
                raise ResponseShadowError("shadow operation requires F1–F8 and its explicit policy flag")
            features |= op.eps == -1 or op.rotation_int != IDENTITY
        for mode in ResponseMode:
            rep = columns[(group.representative, mode)]
            shadow = columns[(group.shadow, mode)]
            if (rep.amplitudes_ev, rep.estimator, rep.scf_level_id) != (
                shadow.amplitudes_ev,
                shadow.estimator,
                shadow.scf_level_id,
            ):
                raise ResponseShadowError("shadow must inherit the representative ColumnPlan")
        op_id = dict(group.ops_rep_to_member)[group.shadow]
        permutation = plan.coverage.operations[op_id].operation.correlated_permutation
        comparisons = []
        scf_complete = True
        for source, target in enumerate(permutation):
            for mode in ResponseMode:
                direct = budgets.get((group.shadow, mode, sites[target]))
                rep_budget = budgets.get((group.representative, mode, sites[source]))
                if direct is not None and rep_budget is not None:
                    direct_scf = scf.get((group.shadow, mode, sites[target]))
                    rep_scf = scf.get((group.representative, mode, sites[source]))
                    if scf_estimates and any(
                        e is None or e.status is not ScfStatus.ESTABLISHED for e in (direct_scf, rep_scf)
                    ):
                        scf_complete = False
                    comparisons.append(
                        ShadowComparison(
                            sites[target],
                            mode,
                            direct.estimate_e_per_ev,
                            rep_budget.estimate_e_per_ev,
                            direct.print_bound_e_per_ev,
                            rep_budget.print_bound_e_per_ev,
                            None if direct_scf is None else direct_scf.radius_e_per_ev,
                            None if rep_scf is None else rep_scf.radius_e_per_ev,
                        )
                    )
        reason = (
            ShadowReason.INCOMPLETE_RESPONSE_EVIDENCE
            if len(comparisons) != len(sites) * len(ResponseMode)
            else ShadowReason.SCIENTIFIC_STATE_NOT_ESTABLISHED
            if not scientific_state_valid
            else ShadowReason.SCF_ESTIMATE_NOT_ESTABLISHED
            if not scf_complete
            else ShadowReason.OUTSIDE_PRINT_BOUNDS
            if not all(c.passed for c in comparisons)
            else ShadowReason.FEATURE_VALIDATION_NOT_ESTABLISHED
            if features
            else ShadowReason.WITHIN_PRINT_BOUNDS
        )
        outcomes.append(
            ShadowOutcome(
                group.representative,
                group.shadow,
                CoverageStatus.PROVEN
                if reason is ShadowReason.WITHIN_PRINT_BOUNDS
                else CoverageStatus.REJECTED_EXPANDED,
                tuple(sorted(comparisons, key=lambda c: (sites.index(c.site_observed), c.mode.value))),
                reason,
            )
        )
    return tuple(outcomes)


def reconstruction_classes(
    plan: ResolvedPerturbationPlan, outcomes: Sequence[ShadowOutcome]
) -> tuple[ReconstructionClass, ...]:
    """Rejected members become singleton direct columns in TASK 11's partition."""
    sites = tuple(s.site_id for s in plan.inventory.subspaces)
    index = {site: i for i, site in enumerate(sites)}
    by_rep = {o.representative: o for o in outcomes}
    if len(by_rep) != len(outcomes) or set(by_rep) != {
        c.representative for c in plan.coverage.classes if c.reduced
    }:
        raise ResponseShadowError("outcomes must cover exactly the reduced classes")
    classes = []
    identity_id = len(plan.coverage.operations)
    for group in plan.coverage.classes:
        if group.reduced and by_rep[group.representative].status is CoverageStatus.PROVEN:
            if any(
                plan.coverage.operations[i].operation.eps == -1
                or plan.coverage.operations[i].operation.rotation_int != IDENTITY
                for _, i in group.ops_rep_to_member
            ):
                raise ResponseShadowError("feature reconstruction requires recorded prospective validation")
            outcome = by_rep[group.representative]
            expected = {(s, m) for s in sites for m in ResponseMode}
            keys = [(c.site_observed, c.mode) for c in outcome.comparisons]
            if outcome.shadow != group.shadow or len(keys) != len(expected) or set(keys) != expected:
                raise ResponseShadowError(
                    "PROVEN requires complete unique comparisons for the planned shadow"
                )
            classes.append(
                ReconstructionClass(
                    tuple(index[s] for s in group.members),
                    index[group.representative],
                    tuple((index[s], op_id) for s, op_id in group.ops_rep_to_member),
                )
            )
        else:
            classes.extend(
                ReconstructionClass((index[s],), index[s], ((index[s], identity_id),)) for s in group.members
            )
    return tuple(classes)


def reconstruct_responses(
    plan: ResolvedPerturbationPlan,
    outcomes: Sequence[ShadowOutcome],
    columns: Mapping[tuple[int, ResponseMode], Sequence[float]],
) -> ShadowMatrices:
    """Retain raw unsymmetrized matrices; inversion and certification stay downstream."""
    classes = reconstruction_classes(plan, outcomes)
    ops = tuple(c.operation for c in plan.coverage.operations) + (
        ScalarPermutation(tuple(range(len(plan.inventory.subspaces)))),
    )
    matrices = []
    for mode in ResponseMode:
        matrices.append(
            reconstruct_matrix(
                {c.representative: columns[(c.representative, mode)] for c in classes},
                classes,
                ops,
                observable=ObservableKind.SPIN_SUMMED_TRACE,
            ).raw_matrix
        )
    return ShadowMatrices(*matrices)
