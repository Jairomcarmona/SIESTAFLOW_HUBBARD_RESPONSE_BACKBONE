"""Physical reference-state comparison with retained DM traceability.

Parallel DM reductions need not be byte reproducible. Occupation matrix entries
use a declared SCF-derived tolerance bounded below by summed print half-widths.
Fermi energy uses only a separately declared energy tolerance, bounded below by
summed print half-widths; it never inherits the density-matrix tolerance.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import cast

from hubbardflow.domain.state_gate_types import PointState
from hubbardflow.domain.validation import require_nonnegative_finite


class ReferenceReproductionError(ValueError):
    """A reproduction record contains invalid numerical or provenance data."""


class ParentReproduction(str, Enum):
    PRINT_EQUIVALENT = "PRINT_EQUIVALENT"
    RECORD_ONLY = "RECORD_ONLY"


class ReproductionReason(str, Enum):
    EQUIVALENT = "EQUIVALENT"
    PARENT_STATE_NOT_EQUIVALENT = "PARENT_STATE_NOT_EQUIVALENT"
    PARENT_FERMI_NOT_EQUIVALENT = "PARENT_FERMI_NOT_EQUIVALENT"
    PARENT_IDENTITY_NOT_ESTABLISHED = "PARENT_IDENTITY_NOT_ESTABLISHED"
    EQUIVALENCE_NOT_ASSESSED = "EQUIVALENCE_NOT_ASSESSED"


class OccupationEquivalence(str, Enum):
    EQUIVALENT = "EQUIVALENT"
    NOT_EQUIVALENT = "NOT_EQUIVALENT"
    NOT_ASSESSED = "NOT_ASSESSED"


class FermiEquivalence(str, Enum):
    EQUIVALENT = "EQUIVALENT"
    NOT_EQUIVALENT = "NOT_EQUIVALENT"
    RECORDED_NOT_ASSESSED = "RECORDED_NOT_ASSESSED"


class ReproductionWarning(str, Enum):
    FERMI_TOLERANCE_BELOW_PRINT_HALF_WIDTH = "FERMI_TOLERANCE_BELOW_PRINT_HALF_WIDTH"


class ToleranceSource(str, Enum):
    CONFIG = "config"
    CLI = "cli"


def _printed_decimal(token: str) -> Decimal:
    try:
        value = Decimal(token.replace("D", "E").replace("d", "e"))
    except InvalidOperation as exc:
        raise ReferenceReproductionError(f"invalid printed token {token!r}") from exc
    if not value.is_finite():
        raise ReferenceReproductionError(f"non-finite printed token {token!r}")
    return value


@dataclass(frozen=True)
class ReferenceReproduction:
    """Measured reproduction evidence retaining both DM file identities."""

    criterion: ParentReproduction
    reason: ReproductionReason
    planning_parent_dm_sha256: str | None
    campaign_parent_dm_sha256: str | None
    detail: str
    max_occupation_difference_e: float | None = None
    max_fermi_difference_ev: float | None = None
    occupation_comparison_quanta_e: tuple[float, ...] = ()
    fermi_comparison_quantum_ev: float | None = None
    occupation_tolerance_e: float | None = None
    fermi_tolerance_ev: float | None = None
    scf_dm_tolerance: float | None = None
    tolerance_factor: float | None = None
    affected_atom_indices: tuple[int, ...] = ()
    all_reduced_classes_affected: bool = False
    occupation_tolerances_e: tuple[float, ...] = ()
    occupation_equivalence: OccupationEquivalence = OccupationEquivalence.NOT_ASSESSED
    fermi_equivalence: FermiEquivalence = FermiEquivalence.RECORDED_NOT_ASSESSED
    declared_fermi_tolerance_ev: float | None = None
    fermi_tolerance_source: ToleranceSource | None = None
    fermi_print_half_widths_ev: tuple[float, ...] = ()
    warnings: tuple[ReproductionWarning, ...] = ()

    def __post_init__(self) -> None:
        try:
            for name in (
                "max_occupation_difference_e",
                "max_fermi_difference_ev",
                "fermi_comparison_quantum_ev",
                "occupation_tolerance_e",
                "fermi_tolerance_ev",
                "scf_dm_tolerance",
                "tolerance_factor",
                "declared_fermi_tolerance_ev",
            ):
                value = getattr(self, name)
                if value is not None:
                    require_nonnegative_finite(value, name)
            for value in self.occupation_comparison_quanta_e:
                if require_nonnegative_finite(value, "occupation quantum") == 0:
                    raise ReferenceReproductionError("occupation quantum must be positive")
            if self.affected_atom_indices != tuple(sorted(set(self.affected_atom_indices))) or any(
                type(index) is not int or index < 1 for index in self.affected_atom_indices
            ):
                raise ReferenceReproductionError(
                    "affected atom indices must be unique sorted positive integers"
                )
            if type(self.all_reduced_classes_affected) is not bool:
                raise ReferenceReproductionError("all_reduced_classes_affected must be boolean")
            for value in self.occupation_tolerances_e:
                require_nonnegative_finite(value, "occupation tolerance")
            if self.fermi_comparison_quantum_ev == 0:
                raise ReferenceReproductionError("Fermi quantum must be positive")
            if not isinstance(self.criterion, ParentReproduction) or not isinstance(
                self.reason, ReproductionReason
            ):
                raise ReferenceReproductionError("criterion and reason must be typed enums")
            if not isinstance(self.detail, str) or not self.detail:
                raise ReferenceReproductionError("detail must be a non-empty string")
            if not isinstance(self.occupation_equivalence, OccupationEquivalence) or not isinstance(
                self.fermi_equivalence, FermiEquivalence
            ):
                raise ReferenceReproductionError("comparison states must be typed enums")
            if self.fermi_tolerance_source is not None and not isinstance(
                self.fermi_tolerance_source, ToleranceSource
            ):
                raise ReferenceReproductionError("Fermi tolerance source must be a typed enum")
            for width in self.fermi_print_half_widths_ev:
                require_nonnegative_finite(width, "Fermi print half-width")
            if any(not isinstance(warning, ReproductionWarning) for warning in self.warnings):
                raise ReferenceReproductionError("warnings must be typed enums")
        except ValueError as exc:
            raise ReferenceReproductionError(str(exc)) from exc

    @property
    def equivalent(self) -> bool:
        return self.reason is ReproductionReason.EQUIVALENT

    @property
    def rejects_reduction(self) -> bool:
        """Only assessed physical differences reject a reduction."""
        return self.reason in {
            ReproductionReason.PARENT_STATE_NOT_EQUIVALENT,
            ReproductionReason.PARENT_IDENTITY_NOT_ESTABLISHED,
            ReproductionReason.PARENT_FERMI_NOT_EQUIVALENT,
        }

    def to_mapping(self) -> dict[str, object]:
        return {
            "schema": "hubbardflow.reference_reproduction.v1",
            "criterion": self.criterion.value,
            "equivalent": self.equivalent,
            "reason": self.reason.value,
            "planning_parent_dm_sha256": self.planning_parent_dm_sha256,
            "campaign_parent_dm_sha256": self.campaign_parent_dm_sha256,
            "detail": self.detail,
            "max_occupation_difference_e": self.max_occupation_difference_e,
            "max_fermi_difference_ev": self.max_fermi_difference_ev,
            "occupation_comparison_quanta_e": list(self.occupation_comparison_quanta_e),
            "fermi_comparison_quantum_ev": self.fermi_comparison_quantum_ev,
            "occupation_tolerance_e": self.occupation_tolerance_e,
            "fermi_tolerance_ev": self.fermi_tolerance_ev,
            "scf_dm_tolerance": self.scf_dm_tolerance,
            "tolerance_factor": self.tolerance_factor,
            "affected_atom_indices": list(self.affected_atom_indices),
            "all_reduced_classes_affected": self.all_reduced_classes_affected,
            "occupation_tolerances_e": list(self.occupation_tolerances_e),
            "occupation_equivalence": self.occupation_equivalence.value,
            "fermi_equivalence": self.fermi_equivalence.value,
            "declared_fermi_tolerance_ev": self.declared_fermi_tolerance_ev,
            "fermi_tolerance_source": None
            if self.fermi_tolerance_source is None
            else self.fermi_tolerance_source.value,
            "fermi_print_half_widths_ev": list(self.fermi_print_half_widths_ev),
            "warnings": [warning.value for warning in self.warnings],
        }

    @classmethod
    def from_mapping(cls, value: object) -> ReferenceReproduction:
        if not isinstance(value, dict) or value.get("schema") != "hubbardflow.reference_reproduction.v1":
            raise ReferenceReproductionError("invalid reference reproduction schema")
        try:
            result = cls(
                ParentReproduction(value["criterion"]),
                ReproductionReason(value["reason"]),
                value["planning_parent_dm_sha256"],
                value["campaign_parent_dm_sha256"],
                value["detail"],
                cast(float | None, value["max_occupation_difference_e"]),
                cast(float | None, value["max_fermi_difference_ev"]),
                tuple(value["occupation_comparison_quanta_e"]),
                cast(float | None, value["fermi_comparison_quantum_ev"]),
                cast(float | None, value.get("occupation_tolerance_e")),
                cast(float | None, value.get("fermi_tolerance_ev")),
                cast(float | None, value.get("scf_dm_tolerance")),
                cast(float | None, value.get("tolerance_factor")),
                tuple(value.get("affected_atom_indices", ())),
                value.get("all_reduced_classes_affected", False),
                tuple(value.get("occupation_tolerances_e", ())),
                OccupationEquivalence(value.get("occupation_equivalence", "NOT_ASSESSED")),
                FermiEquivalence(value.get("fermi_equivalence", "RECORDED_NOT_ASSESSED")),
                cast(float | None, value.get("declared_fermi_tolerance_ev")),
                None
                if value.get("fermi_tolerance_source") is None
                else ToleranceSource(value["fermi_tolerance_source"]),
                tuple(value.get("fermi_print_half_widths_ev", ())),
                tuple(ReproductionWarning(warning) for warning in value.get("warnings", ())),
            )
            if type(value.get("equivalent")) is not bool or value["equivalent"] != result.equivalent:
                raise ReferenceReproductionError("equivalent flag disagrees with reason")
            return result
        except (ValueError, KeyError, TypeError) as exc:
            raise ReferenceReproductionError(f"invalid reference reproduction: {exc}") from exc


def compare_reference_states(
    planning: PointState,
    campaign: PointState,
    planning_dm_sha256: str | None,
    campaign_dm_sha256: str | None,
    scf_dm_tolerance: float | None = None,
    tolerance_factor: float | None = None,
    criterion: ParentReproduction = ParentReproduction.PRINT_EQUIVALENT,
    tol_fermi_ev: float | None = None,
    fermi_tolerance_source: ToleranceSource | None = None,
) -> ReferenceReproduction:
    """Compare state values using the declared physical tolerance and print widths.

    The user-declared factor is required to make a decision. Missing tolerance
    provenance leaves the comparison unassessed. RECORD_ONLY cannot grant
    equivalence, but preserves rejection of measured physical/identity failures.
    """
    for name, value in (
        ("scf_dm_tolerance", scf_dm_tolerance),
        ("tolerance_factor", tolerance_factor),
        ("tol_fermi_ev", tol_fermi_ev),
    ):
        if value is not None:
            require_nonnegative_finite(value, name)
    detail = "all occupation elements and Fermi energy agree within declared physical tolerances"
    identity_failure = False
    max_occ = Decimal(0)
    quanta: set[float] = set()
    tolerances: set[float] = set()
    affected_atoms: set[int] = set()
    differences: list[str] = []
    scf_radius = (
        None
        if scf_dm_tolerance is None or tolerance_factor is None
        else Decimal(str(scf_dm_tolerance)) * Decimal(str(tolerance_factor))
    )
    if tuple(a.atom_index for a in planning.atoms) != tuple(a.atom_index for a in campaign.atoms):
        identity_failure = True
        differences.append("atom indices differ between reference states")
    else:
        for first, second in zip(planning.atoms, campaign.atoms, strict=True):
            for spin, left, right in (
                ("up", first.matrix_up, second.matrix_up),
                ("down", first.matrix_down, second.matrix_down),
            ):
                if len(left) != len(right):
                    identity_failure = True
                    differences.append(f"atom {first.atom_index} {spin} projector matrix dimensions differ")
                    continue
                for row, (left_row, right_row) in enumerate(zip(left, right, strict=True), 1):
                    for col, (left_token, right_token) in enumerate(zip(left_row, right_row, strict=True), 1):
                        left_value, right_value = _printed_decimal(left_token), _printed_decimal(right_token)
                        # Each lexical token retains its own precision. A coarse
                        # token elsewhere cannot widen this element's comparison.
                        print_radius = (
                            Decimal(1).scaleb(int(left_value.as_tuple().exponent))
                            + Decimal(1).scaleb(int(right_value.as_tuple().exponent))
                        ) / 2
                        quanta.add(float(print_radius))
                        difference = abs(left_value - right_value)
                        max_occ = max(max_occ, difference)
                        if scf_radius is None:
                            continue
                        tolerance = max(print_radius, scf_radius)
                        tolerances.add(float(tolerance))
                        if difference > tolerance:
                            affected_atoms.add(first.atom_index)
                            differences.append(
                                f"atom {first.atom_index} spin {spin} element ({row},{col}): "
                                f"difference {difference} e > tolerance {float(tolerance)} e"
                            )
    fermi_quantum = Decimal(str(planning.fermi_stdout_half_width_ev)) + Decimal(
        str(campaign.fermi_stdout_half_width_ev)
    )
    fermi_diff = abs(
        _printed_decimal(planning.fermi_stdout_token) - _printed_decimal(campaign.fermi_stdout_token)
    )
    # This compatibility scalar is the maximum effective element tolerance;
    # it is recorded only, never used to decide other elements.
    occ_tolerance = max(tolerances) if tolerances else None
    # Independent rounded measurements contribute additive half-widths. The
    # combined radius prevents rejecting a difference explained by printing.
    warnings: tuple[ReproductionWarning, ...] = ()
    fermi_tolerance = None if tol_fermi_ev is None else max(Decimal(str(tol_fermi_ev)), fermi_quantum)
    if tol_fermi_ev is not None and Decimal(str(tol_fermi_ev)) < fermi_quantum:
        warnings = (ReproductionWarning.FERMI_TOLERANCE_BELOW_PRINT_HALF_WIDTH,)
    fermi_failure = fermi_tolerance is not None and fermi_diff > fermi_tolerance
    fermi_equivalence = FermiEquivalence.RECORDED_NOT_ASSESSED
    if fermi_failure:
        fermi_equivalence = FermiEquivalence.NOT_EQUIVALENT
    elif fermi_tolerance is not None and criterion is ParentReproduction.PRINT_EQUIVALENT:
        fermi_equivalence = FermiEquivalence.EQUIVALENT
    physical_difference = "; ".join(differences) if differences else None
    missing = []
    if scf_dm_tolerance is None:
        missing.append("SCF.DM.Tolerance")
    if tolerance_factor is None:
        missing.append("explicit tolerance_factor")
    occupation_equivalence = OccupationEquivalence.NOT_ASSESSED
    if identity_failure or physical_difference is not None:
        occupation_equivalence = OccupationEquivalence.NOT_EQUIVALENT
    elif not missing and criterion is ParentReproduction.PRINT_EQUIVALENT:
        occupation_equivalence = OccupationEquivalence.EQUIVALENT
    reason = ReproductionReason.EQUIVALENCE_NOT_ASSESSED
    if identity_failure:
        reason = ReproductionReason.PARENT_IDENTITY_NOT_ESTABLISHED
    elif physical_difference is not None:
        reason = ReproductionReason.PARENT_STATE_NOT_EQUIVALENT
    elif fermi_failure:
        reason = ReproductionReason.PARENT_FERMI_NOT_EQUIVALENT
    elif criterion is ParentReproduction.PRINT_EQUIVALENT and not missing:
        reason = ReproductionReason.EQUIVALENT
    if reason in {
        ReproductionReason.PARENT_STATE_NOT_EQUIVALENT,
        ReproductionReason.PARENT_IDENTITY_NOT_ESTABLISHED,
    }:
        assert physical_difference is not None
        detail = physical_difference
        if missing:
            detail += "; other comparisons unassessed: missing " + ", ".join(missing)
    elif reason is ReproductionReason.PARENT_FERMI_NOT_EQUIVALENT:
        detail = f"Fermi difference {fermi_diff} eV > tolerance {fermi_tolerance} eV"
    elif criterion is ParentReproduction.RECORD_ONLY:
        detail = "record-only policy: no equivalence granted; no assessed physical difference"
        if missing:
            detail += "; missing " + ", ".join(missing)
    elif missing:
        detail = "physical equivalence not assessed; missing " + ", ".join(missing)
        if physical_difference is not None:
            detail += "; observed occupation difference: " + physical_difference
    elif physical_difference is not None:
        detail = physical_difference
    else:
        detail = "occupation elements agree within declared physical tolerances"
    if tol_fermi_ev is None:
        detail += "; Fermi difference recorded without declared energy tolerance"
    return ReferenceReproduction(
        criterion,
        reason,
        planning_dm_sha256,
        campaign_dm_sha256,
        detail,
        float(max_occ),
        float(fermi_diff),
        tuple(sorted(quanta)),
        float(fermi_quantum),
        occ_tolerance,
        None if fermi_tolerance is None else float(fermi_tolerance),
        scf_dm_tolerance,
        tolerance_factor,
        tuple(sorted(affected_atoms)),
        identity_failure or fermi_failure,
        tuple(sorted(tolerances)),
        occupation_equivalence,
        fermi_equivalence,
        tol_fermi_ev,
        fermi_tolerance_source,
        (planning.fermi_stdout_half_width_ev, campaign.fermi_stdout_half_width_ev),
        warnings,
    )
