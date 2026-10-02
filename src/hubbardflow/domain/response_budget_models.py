"""Immutable, explicitly serialized evidence records for response diagnostics."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from fractions import Fraction
from types import UnionType
from typing import Self, cast, get_args, get_origin, get_type_hints

from hubbardflow.domain.response_protocol import EstimatorKind, EstimatorSpec
from hubbardflow.domain.symmetry_reduction import ResponseMode
from hubbardflow.domain.validation import (
    ValidationError,
    require_fdf_representable_ev,
    require_finite,
    require_nonnegative_finite,
)


class ResponseBudgetError(ValueError):
    """Evidence cannot safely enter the phase-one response diagnostic."""


def _derived_finite(value: Fraction | float, label: str) -> float:
    """Convert derived evidence through the shared finite-number validator."""
    try:
        return require_finite(value, label)
    except ValidationError as exc:
        raise ResponseBudgetError(
            f"derived {label} is not representable as a finite float; check occupation magnitudes and amplitudes"
        ) from exc


class BoundKind(str, Enum):
    BOUND = "BOUND"
    ESTIMATE = "ESTIMATE"
    DIAGNOSTIC = "DIAGNOSTIC"


class OrderStatus(str, Enum):
    VERIFIED_2 = "VERIFIED_2"
    VERIFIED_1 = "VERIFIED_1"
    UNRESOLVED = "UNRESOLVED"
    INCONSISTENT = "INCONSISTENT"


class BudgetReason(str, Enum):
    ORDER_INCONSISTENT = "ORDER_INCONSISTENT"
    ORDER_NOT_VERIFIED_FOR_ESTIMATOR = "ORDER_NOT_VERIFIED_FOR_ESTIMATOR"
    ORDER_1_VERIFIED = "ORDER_1_VERIFIED"
    ORDER_UNRESOLVED_CONSERVATIVE_P1 = "ORDER_UNRESOLVED_CONSERVATIVE_P1"
    MOMENT_RATIO_NOT_INCREASING = "MOMENT_RATIO_NOT_INCREASING"
    TAIL_UNRESOLVED = "TAIL_UNRESOLVED"
    NEIGHBOUR_INCONSISTENT = "NEIGHBOUR_INCONSISTENT"


class QualificationCap(str, Enum):
    """Upper limit on later qualification; phase one does not qualify campaigns."""

    REVIEW = "REVIEW"


class _Record:
    """Exact field mappings; tuples and rationals have explicit JSON encodings."""

    def __post_init__(self) -> None:
        hints = _hints(type(self))
        for name, annotation in hints.items():
            normalized = _decode(getattr(self, name), annotation)
            object.__setattr__(self, name, normalized)

    def to_mapping(self) -> dict[str, object]:
        return {name: _encode(getattr(self, name)) for name in _hints(type(self))}

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> Self:
        hints = _hints(cls)
        names = set(hints)
        if not isinstance(payload, Mapping) or set(payload) != names:
            raise ResponseBudgetError(f"{cls.__name__} mapping must contain exactly {sorted(names)}")
        values = {name: _decode(payload[name], hints[name]) for name in sorted(names)}
        return cast(Self, cast(Callable[..., object], cls)(**values))


_TYPE_HINTS: dict[type[object], dict[str, object]] = {}


def _hints(cls: type[object]) -> dict[str, object]:
    if cls not in _TYPE_HINTS:
        _TYPE_HINTS[cls] = dict(get_type_hints(cls))
    return _TYPE_HINTS[cls]


def _encode(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Fraction):
        return {"numerator": value.numerator, "denominator": value.denominator}
    if isinstance(value, EstimatorSpec):
        return {
            "kind": value.kind.value,
            "polynomial_degree": value.polynomial_degree,
            "amplitudes_ev": list(value.amplitudes_ev),
        }
    if isinstance(value, _Record):
        return value.to_mapping()
    if isinstance(value, tuple):
        return [_encode(item) for item in value]
    return value


def _decode(value: object, annotation: object) -> object:
    """Reject unknown fields, booleans as numbers, and nonfinite JSON numbers."""
    origin, args = get_origin(annotation), get_args(annotation)
    try:
        if origin is UnionType:
            for option in args:
                try:
                    return _decode(value, option)
                except ResponseBudgetError:
                    continue
            raise ResponseBudgetError("value does not match the declared optional field")
        if annotation is type(None) and value is None:
            return None
        if annotation is float:
            return require_finite(value, "number")
        if annotation is int and isinstance(value, int) and not isinstance(value, bool):
            return value
        if annotation is bool and isinstance(value, bool):
            return value
        if annotation is str and isinstance(value, str) and value.strip() and value == value.strip():
            return value
        if origin is tuple and isinstance(value, (tuple, list)):
            annotations = (args[0],) * len(value) if args[-1] is Ellipsis else args
            if len(value) != len(annotations):
                raise ResponseBudgetError("tuple has the wrong length")
            return tuple(_decode(item, hint) for item, hint in zip(value, annotations, strict=True))
        if annotation is Fraction and isinstance(value, Fraction):
            return value
        if (
            annotation is Fraction
            and isinstance(value, Mapping)
            and set(value) == {"numerator", "denominator"}
        ):
            numerator = cast(int, _decode(value["numerator"], int))
            denominator = cast(int, _decode(value["denominator"], int))
            if denominator <= 0:
                raise ResponseBudgetError("fraction denominator must be positive")
            return Fraction(numerator, denominator)
        if annotation is EstimatorSpec and isinstance(value, EstimatorSpec):
            return value
        if annotation is EstimatorSpec and isinstance(value, Mapping):
            if set(value) != {"kind", "polynomial_degree", "amplitudes_ev"}:
                raise ResponseBudgetError("estimator mapping has unexpected fields")
            return EstimatorSpec(
                cast(EstimatorKind, _decode(value["kind"], EstimatorKind)),
                cast(int | None, _decode(value["polynomial_degree"], int | None)),
                cast(tuple[float, ...], _decode(value["amplitudes_ev"], tuple[float, ...])),
            )
        if isinstance(annotation, type) and issubclass(annotation, Enum):
            if not isinstance(value, str):
                raise ResponseBudgetError("enum value must be a string")
            return annotation(value)
        if isinstance(annotation, type) and issubclass(annotation, _Record):
            if isinstance(value, annotation):
                return value
            if isinstance(value, Mapping):
                return annotation.from_mapping(value)
    except (ValidationError, ValueError, TypeError) as exc:
        raise ResponseBudgetError(str(exc)) from exc
    raise ResponseBudgetError(f"invalid field value for {annotation}")


@dataclass(frozen=True)
class PointObservation(_Record):
    """Printed occupation and its exact print-quantization radius."""

    alpha_ev: float
    occupation_e: float
    half_width_e: float

    def __post_init__(self) -> None:
        super().__post_init__()
        try:
            require_fdf_representable_ev(self.alpha_ev, "alpha_ev")
            require_nonnegative_finite(self.half_width_e, "half_width_e")
        except ValidationError as exc:
            raise ResponseBudgetError(str(exc)) from exc
        if self.alpha_ev == 0:
            raise ResponseBudgetError(
                "points must be nonzero perturbations; use the reference fields for zero"
            )


@dataclass(frozen=True)
class ElementSeries(_Record):
    site_perturbed: str
    mode: ResponseMode
    site_observed: str
    reference_occupation_e: float
    reference_half_width_e: float
    points: tuple[PointObservation, ...]

    def __post_init__(self) -> None:
        super().__post_init__()
        try:
            require_nonnegative_finite(self.reference_half_width_e, "reference_half_width_e")
        except ValidationError as exc:
            raise ResponseBudgetError(str(exc)) from exc
        ordered = tuple(sorted(self.points, key=lambda point: point.alpha_ev))
        object.__setattr__(self, "points", ordered)
        alphas = {point.alpha_ev for point in ordered}
        if not ordered or len(alphas) != len(ordered) or any(-alpha not in alphas for alpha in alphas):
            raise ResponseBudgetError("points require distinct symmetric ±a partners")


@dataclass(frozen=True)
class NoiseModel(_Record):
    """Phase one supplies print bounds only; SCF estimation requires phase two."""

    eps_abs_e: float = 0.0
    eps_rel: float = 0.0
    kind: BoundKind = BoundKind.BOUND

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.eps_abs_e != 0 or self.eps_rel != 0 or self.kind is not BoundKind.BOUND:
            raise ResponseBudgetError("phase one accepts zero SCF noise and BOUND print quantization only")


@dataclass(frozen=True)
class OddEvenDecomposition(_Record):
    amplitudes_ev: tuple[float, ...]
    odd_e: tuple[float, ...]
    slopes_e_per_ev: tuple[float, ...]
    slope_noise_e_per_ev: tuple[float, ...]
    even_e: tuple[float, ...]
    even_fit: tuple[float, float, float] | None
    # Exact decimal-token arithmetic prevents a zero-width ratio test from
    # acquiring a floating-point tolerance absent from the scientific protocol.
    slope_fractions: tuple[Fraction, ...]
    noise_fractions: tuple[Fraction, ...]

    def __post_init__(self) -> None:
        super().__post_init__()
        lengths = {
            len(self.amplitudes_ev),
            len(self.odd_e),
            len(self.slopes_e_per_ev),
            len(self.slope_noise_e_per_ev),
            len(self.even_e),
            len(self.slope_fractions),
            len(self.noise_fractions),
        }
        if len(lengths) != 1 or not self.amplitudes_ev:
            raise ResponseBudgetError("decomposition arrays must have the same nonzero length")
        if tuple(sorted(set(self.amplitudes_ev))) != self.amplitudes_ev or self.amplitudes_ev[0] <= 0:
            raise ResponseBudgetError("decomposition amplitudes must be distinct, positive and sorted")
        if any(value < 0 for value in self.noise_fractions):
            raise ResponseBudgetError("decomposition noise radii must be nonnegative")
        if (
            tuple(_derived_finite(value, "decomposition.slope_fractions") for value in self.slope_fractions)
            != self.slopes_e_per_ev
        ):
            raise ResponseBudgetError("exact and displayed slopes disagree")
        if (
            tuple(_derived_finite(value, "decomposition.noise_fractions") for value in self.noise_fractions)
            != self.slope_noise_e_per_ev
        ):
            raise ResponseBudgetError("exact and displayed noise radii disagree")


@dataclass(frozen=True)
class PrintedResponseBudget(_Record):
    """Resolved estimator value and additive print BOUND, with no SCF claim."""

    estimate_e_per_ev: float
    print_bound_e_per_ev: float
    kind: BoundKind

    def __post_init__(self) -> None:
        super().__post_init__()
        require_nonnegative_finite(self.print_bound_e_per_ev, "print_bound_e_per_ev")
        if self.kind is not BoundKind.BOUND:
            raise ResponseBudgetError("printed response uncertainty must be a BOUND")


@dataclass(frozen=True)
class CandidateBudget(_Record):
    """Print BOUND plus conditional truncation ESTIMATE; never a certification."""

    estimator: EstimatorSpec
    estimate_e_per_ev: float
    noise_e_per_ev: float
    truncation_e_per_ev: float
    order_status: OrderStatus
    admissible: bool
    reasons: tuple[BudgetReason, ...]
    p_used: int
    j0: int
    moments: tuple[Fraction, ...]
    moment_ratio: Fraction | None
    noise_kind: BoundKind = BoundKind.BOUND
    truncation_kind: BoundKind = BoundKind.ESTIMATE

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.noise_e_per_ev < 0 or self.truncation_e_per_ev < 0:
            raise ResponseBudgetError("candidate noise and truncation radii must be nonnegative")
        if self.p_used not in (1, 2) or self.j0 < 1 or self.j0 > len(self.moments):
            raise ResponseBudgetError("candidate order and first surviving moment are invalid")
        if any(self.moments[: self.j0 - 1]) or not self.moments[self.j0 - 1]:
            raise ResponseBudgetError("candidate j0 must be the exact first nonzero moment")
        if self.noise_kind is not BoundKind.BOUND or self.truncation_kind is not BoundKind.ESTIMATE:
            raise ResponseBudgetError("phase-one candidates require print BOUND and truncation ESTIMATE")
        disqualifying = {
            BudgetReason.ORDER_INCONSISTENT,
            BudgetReason.ORDER_NOT_VERIFIED_FOR_ESTIMATOR,
            BudgetReason.TAIL_UNRESOLVED,
            BudgetReason.MOMENT_RATIO_NOT_INCREASING,
            BudgetReason.NEIGHBOUR_INCONSISTENT,
        }
        if self.admissible and any(reason in disqualifying for reason in self.reasons):
            raise ResponseBudgetError("a disqualified candidate cannot be marked admissible")

    @property
    def total_e_per_ev(self) -> float:
        return self.noise_e_per_ev + self.truncation_e_per_ev


@dataclass(frozen=True)
class ElementBudgetReport(_Record):
    series_key: tuple[str, ResponseMode, str]
    decomposition: OddEvenDecomposition
    drift_ratios: tuple[float | None, ...]
    candidates: tuple[CandidateBudget, ...]
    best: CandidateBudget | None
    qualification_cap: QualificationCap | None = None
    reasons: tuple[BudgetReason, ...] = ()


@dataclass(frozen=True)
class ReciprocityResidual(_Record):
    """Cross-element residual relative to conditional budgets, diagnostic only."""

    pair: tuple[str, str]
    mode: ResponseMode
    residual_e_per_ev: float
    allowed_e_per_ev: float
    consistent: bool
