"""D16 reference reproduction at the precision of the printed state.

Parallel DM reductions need not be byte reproducible. Occupation matrix entries
and Fermi energy are compared using the sum of their two print half widths.
Decimal arithmetic keeps an exact one-quantum boundary free of binary noise.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import cast

from hubbardflow.domain.state_gate_types import PointState
from hubbardflow.domain.validation import require_nonnegative_finite, require_sha256


class ReferenceReproductionError(ValueError):
    """A reproduction record contains invalid numerical or provenance data."""


class ParentReproduction(str, Enum):
    PRINT_EQUIVALENT = "PRINT_EQUIVALENT"
    BITWISE = "BITWISE"


class ReproductionReason(str, Enum):
    EQUIVALENT = "EQUIVALENT"
    PARENT_STATE_NOT_EQUIVALENT = "PARENT_STATE_NOT_EQUIVALENT"
    PARENT_DM_NOT_REPRODUCED = "PARENT_DM_NOT_REPRODUCED"


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
    planning_parent_dm_sha256: str
    campaign_parent_dm_sha256: str
    detail: str
    max_occupation_difference_e: float | None = None
    max_fermi_difference_ev: float | None = None
    occupation_comparison_quanta_e: tuple[float, ...] = ()
    fermi_comparison_quantum_ev: float | None = None

    def __post_init__(self) -> None:
        try:
            require_sha256(self.planning_parent_dm_sha256, "planning_parent_dm_sha256")
            require_sha256(self.campaign_parent_dm_sha256, "campaign_parent_dm_sha256")
            for name in (
                "max_occupation_difference_e",
                "max_fermi_difference_ev",
                "fermi_comparison_quantum_ev",
            ):
                value = getattr(self, name)
                if value is not None:
                    require_nonnegative_finite(value, name)
            for value in self.occupation_comparison_quanta_e:
                if require_nonnegative_finite(value, "occupation quantum") == 0:
                    raise ReferenceReproductionError("occupation quantum must be positive")
            if self.fermi_comparison_quantum_ev == 0:
                raise ReferenceReproductionError("Fermi quantum must be positive")
            if not isinstance(self.criterion, ParentReproduction) or not isinstance(
                self.reason, ReproductionReason
            ):
                raise ReferenceReproductionError("criterion and reason must be typed enums")
            if not isinstance(self.detail, str) or not self.detail:
                raise ReferenceReproductionError("detail must be a non-empty string")
        except ValueError as exc:
            raise ReferenceReproductionError(str(exc)) from exc

    @property
    def equivalent(self) -> bool:
        return self.reason is ReproductionReason.EQUIVALENT

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
            )
            if type(value.get("equivalent")) is not bool or value["equivalent"] != result.equivalent:
                raise ReferenceReproductionError("equivalent flag disagrees with reason")
            return result
        except (ValueError, KeyError, TypeError) as exc:
            raise ReferenceReproductionError(f"invalid reference reproduction: {exc}") from exc


def compare_reference_states(
    planning: PointState,
    campaign: PointState,
    planning_dm_sha256: str,
    campaign_dm_sha256: str,
) -> ReferenceReproduction:
    """Compare every printed spin matrix entry and stdout Fermi energy under D16.

    Matching event atom/projector identities and SCF termination are prerequisites
    checked by the backend. No moment, eigenvalue, U or condition-number rule is
    introduced here. With equal precision the comparison radius is one quantum.
    """
    detail = "all occupation elements and Fermi energy agree within print bounds"
    failure = False
    max_occ = Decimal(0)
    quanta: set[float] = set()
    if tuple(a.atom_index for a in planning.atoms) != tuple(a.atom_index for a in campaign.atoms):
        failure = True
        detail = "atom indices differ between reference states"
    else:
        for first, second in zip(planning.atoms, campaign.atoms, strict=True):
            quantum = (
                Decimal(str(first.matrix_print_quantum_e)) + Decimal(str(second.matrix_print_quantum_e))
            ) / 2
            quanta.add(float(quantum))
            for spin, left, right in (
                ("up", first.matrix_up, second.matrix_up),
                ("down", first.matrix_down, second.matrix_down),
            ):
                if len(left) != len(right):
                    failure = True
                    detail = f"atom {first.atom_index} {spin} projector matrix dimensions differ"
                    continue
                for row, (left_row, right_row) in enumerate(zip(left, right, strict=True), 1):
                    for col, (left_token, right_token) in enumerate(zip(left_row, right_row, strict=True), 1):
                        difference = abs(_printed_decimal(left_token) - _printed_decimal(right_token))
                        max_occ = max(max_occ, difference)
                        if difference > quantum and not failure:
                            failure = True
                            detail = f"atom {first.atom_index} spin {spin} element ({row},{col}): difference {difference} e > quantum {quantum} e"
    fermi_quantum = Decimal(str(planning.fermi_stdout_half_width_ev)) + Decimal(
        str(campaign.fermi_stdout_half_width_ev)
    )
    fermi_diff = abs(
        _printed_decimal(planning.fermi_stdout_token) - _printed_decimal(campaign.fermi_stdout_token)
    )
    if fermi_diff > fermi_quantum and not failure:
        failure = True
        detail = f"Fermi: difference {fermi_diff} eV > quantum {fermi_quantum} eV"
    return ReferenceReproduction(
        ParentReproduction.PRINT_EQUIVALENT,
        ReproductionReason.PARENT_STATE_NOT_EQUIVALENT if failure else ReproductionReason.EQUIVALENT,
        planning_dm_sha256,
        campaign_dm_sha256,
        detail,
        float(max_occ),
        float(fermi_diff),
        tuple(sorted(quanta)),
        float(fermi_quantum),
    )
