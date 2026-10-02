"""Resolved, per-column response plans and their estimator functionals.

The protocol records the amplitudes and estimator that analysis must use for
each perturbed site and response mode. Keeping these details together prevents
downstream analysis from silently re-selecting an estimator or grid.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from numbers import Real

import numpy as np

from hubbardflow.domain.symmetry_reduction import ResponseMode
from hubbardflow.domain.validation import (
    ValidationError,
    require_fdf_representable_ev,
    require_finite,
    require_int,
)


class ResponseProtocolError(ValueError):
    """Raised when a resolved response protocol is malformed or unusable."""


class PerturbationStrategy(str, Enum):
    """Source of a response grid; CALIBRATED is descriptive in phase 1 only."""

    FIXED_PROTOCOL_GRID = "FIXED_PROTOCOL_GRID"
    USER_EXPLICIT_GRID = "USER_EXPLICIT_GRID"
    CALIBRATED = "CALIBRATED"


class EstimatorKind(str, Enum):
    """Closed set of derivative functionals supported by the protocol model."""

    CENTRAL = "CENTRAL"
    RICHARDSON_2 = "RICHARDSON_2"
    POLYNOMIAL_LSQ = "POLYNOMIAL_LSQ"
    LINEAR_LSQ = "LINEAR_LSQ"


_SCHEMA = "hubbardflow.resolved_response_protocol.v1"


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ResponseProtocolError(f"{label} must be a nonempty string without surrounding whitespace")
    return value


def _amplitudes(values: object, label: str) -> tuple[float, ...]:
    if not isinstance(values, tuple):
        raise ResponseProtocolError(f"{label} must be a tuple of positive amplitudes")
    try:
        normalized = tuple(sorted(require_fdf_representable_ev(value, label) for value in values))
    except ValidationError as exc:
        raise ResponseProtocolError(str(exc)) from exc
    if not normalized:
        raise ResponseProtocolError(f"{label} must contain at least one amplitude")
    if any(value <= 0.0 for value in normalized):
        raise ResponseProtocolError(f"{label} must contain positive magnitudes")
    if len(set(normalized)) != len(normalized):
        raise ResponseProtocolError(f"{label} amplitudes must be distinct")
    return normalized


def _estimator_weights(
    kind: EstimatorKind, degree: int | None, amplitudes: tuple[float, ...]
) -> tuple[tuple[float, float], ...]:
    """Build the linear functional in occupation space for a declared estimator."""
    signed_alpha = tuple(sorted(alpha for amplitude in amplitudes for alpha in (-amplitude, amplitude)))
    if kind is EstimatorKind.CENTRAL:
        amplitude = amplitudes[0]
        return ((-amplitude, -0.5 / amplitude), (amplitude, 0.5 / amplitude))

    if kind is EstimatorKind.RICHARDSON_2:
        inner, outer = amplitudes
        denominator = outer**2 - inner**2
        inner_factor = outer**2 / denominator
        outer_factor = -(inner**2) / denominator
        weight_by_alpha = {
            -inner: -inner_factor / (2.0 * inner),
            inner: inner_factor / (2.0 * inner),
            -outer: -outer_factor / (2.0 * outer),
            outer: outer_factor / (2.0 * outer),
        }
        return tuple((alpha, weight_by_alpha[alpha]) for alpha in signed_alpha)

    fit_degree = 1 if kind is EstimatorKind.LINEAR_LSQ else degree
    if fit_degree is None:
        raise ResponseProtocolError("POLYNOMIAL_LSQ requires polynomial_degree")
    alpha_array = np.asarray(signed_alpha, dtype=float)
    alpha_scale = float(np.max(np.abs(alpha_array)))
    scaled_alpha = alpha_array / alpha_scale
    design = np.column_stack(tuple(scaled_alpha**power for power in range(fit_degree + 1)))
    # Solving against the identity gives the same least-squares coefficient
    # operator as fit_polynomial_response, including its scaled design matrix.
    coefficient_operator, _, rank, _ = np.linalg.lstsq(
        design,
        np.eye(len(signed_alpha)),
        rcond=None,
    )
    if int(rank) != fit_degree + 1:
        raise ResponseProtocolError(f"degree-{fit_degree} estimator design is rank deficient")
    weights = coefficient_operator[1] / alpha_scale
    return tuple((alpha, float(weight)) for alpha, weight in zip(signed_alpha, weights, strict=True))


@dataclass(frozen=True)
class EstimatorSpec:
    """Estimator kind, degree when applicable, and exact used amplitudes."""

    kind: EstimatorKind
    polynomial_degree: int | None
    amplitudes_ev: tuple[float, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.kind, EstimatorKind):
            raise ResponseProtocolError("kind must be an EstimatorKind")
        amplitudes = _amplitudes(self.amplitudes_ev, "amplitudes_ev")
        object.__setattr__(self, "amplitudes_ev", amplitudes)
        if self.kind is EstimatorKind.POLYNOMIAL_LSQ:
            try:
                degree = require_int(self.polynomial_degree, "polynomial_degree", minimum=1)
            except ValidationError as exc:
                raise ResponseProtocolError(str(exc)) from exc
            if degree > 3:
                raise ResponseProtocolError("polynomial_degree must be between 1 and 3")
            object.__setattr__(self, "polynomial_degree", degree)
            required_points = degree + 2  # fit_polynomial_response requires one residual degree of freedom
            if 2 * len(amplitudes) < required_points:
                raise ResponseProtocolError(
                    f"degree-{degree} polynomial estimator requires at least {required_points} alpha points"
                )
        else:
            if self.polynomial_degree is not None:
                raise ResponseProtocolError("polynomial_degree is only valid for POLYNOMIAL_LSQ")
            if self.kind is EstimatorKind.CENTRAL and len(amplitudes) != 1:
                raise ResponseProtocolError("CENTRAL requires exactly one amplitude")
            if self.kind is EstimatorKind.RICHARDSON_2 and len(amplitudes) != 2:
                raise ResponseProtocolError("RICHARDSON_2 requires exactly two amplitudes")
            if self.kind is EstimatorKind.LINEAR_LSQ and 2 * len(amplitudes) < 3:
                raise ResponseProtocolError("LINEAR_LSQ requires at least three alpha points")

    def weights(self) -> tuple[tuple[float, float], ...]:
        """Return ``(alpha_ev, weight)`` pairs for ``chi_hat = sum w*n(alpha)``."""
        return _estimator_weights(self.kind, self.polynomial_degree, self.amplitudes_ev)


@dataclass(frozen=True)
class ColumnPlan:
    """Perturbation plan for one site and response mode."""

    site_id: str
    mode: ResponseMode
    amplitudes_ev: tuple[float, ...]
    estimator: EstimatorSpec
    scf_level_id: str

    def __post_init__(self) -> None:
        _identifier(self.site_id, "site_id")
        if not isinstance(self.mode, ResponseMode):
            raise ResponseProtocolError("mode must be a ResponseMode")
        amplitudes = _amplitudes(self.amplitudes_ev, "amplitudes_ev")
        object.__setattr__(self, "amplitudes_ev", amplitudes)
        if not isinstance(self.estimator, EstimatorSpec):
            raise ResponseProtocolError("estimator must be an EstimatorSpec")
        if amplitudes != self.estimator.amplitudes_ev:
            raise ResponseProtocolError("column amplitudes must match estimator amplitudes")
        _identifier(self.scf_level_id, "scf_level_id")


@dataclass(frozen=True)
class ResolvedResponseProtocol:
    """Serializable response plan with a canonical identity digest."""

    schema: str
    strategy: PerturbationStrategy
    protocol_version: str
    reference_node_id: str
    observable_id: str
    columns: tuple[ColumnPlan, ...]

    def __post_init__(self) -> None:
        if self.schema != _SCHEMA:
            raise ResponseProtocolError(f"schema must be {_SCHEMA!r}")
        if not isinstance(self.strategy, PerturbationStrategy):
            raise ResponseProtocolError("strategy must be a PerturbationStrategy")
        _identifier(self.protocol_version, "protocol_version")
        _identifier(self.reference_node_id, "reference_node_id")
        _identifier(self.observable_id, "observable_id")
        if not isinstance(self.columns, tuple) or not self.columns:
            raise ResponseProtocolError("columns must be a nonempty tuple")
        if any(not isinstance(column, ColumnPlan) for column in self.columns):
            raise ResponseProtocolError("columns must contain ColumnPlan values")
        ordered = tuple(sorted(self.columns, key=lambda column: (column.site_id, column.mode.value)))
        object.__setattr__(self, "columns", ordered)
        keys = tuple((column.site_id, column.mode) for column in ordered)
        if len(keys) != len(set(keys)):
            raise ResponseProtocolError("each site must have exactly one BARE and one SCREENED column")
        sites = {column.site_id for column in ordered}
        for site_id in sorted(sites):
            modes = {column.mode for column in ordered if column.site_id == site_id}
            if modes != {ResponseMode.BARE, ResponseMode.SCREENED}:
                raise ResponseProtocolError(f"site {site_id!r} must declare one BARE and one SCREENED column")

    def is_common_grid(self) -> bool:
        """Return whether every site/mode column uses the same amplitudes."""
        grids = {column.amplitudes_ev for column in self.columns}
        return len(grids) == 1

    def to_mapping(self) -> dict[str, object]:
        """Serialize every protocol field using stable, JSON-compatible values."""
        return {
            "schema": self.schema,
            "strategy": self.strategy.value,
            "protocol_version": self.protocol_version,
            "reference_node_id": self.reference_node_id,
            "observable_id": self.observable_id,
            "columns": [
                {
                    "site_id": column.site_id,
                    "mode": column.mode.value,
                    "amplitudes_ev": list(column.amplitudes_ev),
                    "estimator": {
                        "kind": column.estimator.kind.value,
                        "polynomial_degree": column.estimator.polynomial_degree,
                        "amplitudes_ev": list(column.estimator.amplitudes_ev),
                    },
                    "scf_level_id": column.scf_level_id,
                }
                for column in self.columns
            ],
        }

    def digest(self) -> str:
        """Hash canonical JSON so mapping order and column input order cannot alter identity."""
        encoded = json.dumps(
            self.to_mapping(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> ResolvedResponseProtocol:
        """Parse the explicit versioned mapping and reject unknown or malformed fields."""
        required = {
            "schema",
            "strategy",
            "protocol_version",
            "reference_node_id",
            "observable_id",
            "columns",
        }
        if not isinstance(payload, Mapping) or set(payload) != required:
            raise ResponseProtocolError(f"protocol mapping must contain exactly {sorted(required)}")
        raw_columns = payload["columns"]
        if not isinstance(raw_columns, Sequence) or isinstance(raw_columns, (str, bytes)):
            raise ResponseProtocolError("columns must be a sequence of mappings")
        columns: list[ColumnPlan] = []
        for index, raw_column in enumerate(raw_columns):
            column_label = f"columns[{index}]"
            column = _mapping_with_keys(
                raw_column,
                {"site_id", "mode", "amplitudes_ev", "estimator", "scf_level_id"},
                column_label,
            )
            estimator_map = _mapping_with_keys(
                column["estimator"],
                {"kind", "polynomial_degree", "amplitudes_ev"},
                f"{column_label}.estimator",
            )
            estimator_amplitudes = _float_tuple(
                estimator_map["amplitudes_ev"], f"{column_label}.estimator.amplitudes_ev"
            )
            column_amplitudes = _float_tuple(column["amplitudes_ev"], f"{column_label}.amplitudes_ev")
            try:
                mode = ResponseMode(_identifier(column["mode"], f"{column_label}.mode"))
                kind = EstimatorKind(_identifier(estimator_map["kind"], f"{column_label}.estimator.kind"))
                raw_degree = estimator_map["polynomial_degree"]
                degree = (
                    None
                    if raw_degree is None
                    else require_int(raw_degree, f"{column_label}.estimator.polynomial_degree", minimum=1)
                )
                columns.append(
                    ColumnPlan(
                        site_id=_identifier(column["site_id"], f"{column_label}.site_id"),
                        mode=mode,
                        amplitudes_ev=column_amplitudes,
                        estimator=EstimatorSpec(
                            kind=kind,
                            polynomial_degree=degree,
                            amplitudes_ev=estimator_amplitudes,
                        ),
                        scf_level_id=_identifier(column["scf_level_id"], f"{column_label}.scf_level_id"),
                    )
                )
            except (TypeError, ValueError) as exc:
                if isinstance(exc, ResponseProtocolError):
                    raise
                raise ResponseProtocolError(f"{column_label} contains an invalid enum value") from exc
        try:
            return cls(
                schema=_identifier(payload["schema"], "schema"),
                strategy=PerturbationStrategy(_identifier(payload["strategy"], "strategy")),
                protocol_version=_identifier(payload["protocol_version"], "protocol_version"),
                reference_node_id=_identifier(payload["reference_node_id"], "reference_node_id"),
                observable_id=_identifier(payload["observable_id"], "observable_id"),
                columns=tuple(columns),
            )
        except (TypeError, ValueError) as exc:
            if isinstance(exc, ResponseProtocolError):
                raise
            raise ResponseProtocolError("protocol mapping contains an invalid strategy") from exc


def _mapping_with_keys(value: object, keys: set[str], label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or set(value) != keys:
        raise ResponseProtocolError(f"{label} must contain exactly {sorted(keys)}")
    return value


def _float_tuple(value: object, label: str) -> tuple[float, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ResponseProtocolError(f"{label} must be a sequence of numbers")
    result: list[float] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, Real):
            raise ResponseProtocolError(f"{label} must contain only numbers")
        try:
            result.append(require_finite(item, label))
        except ValidationError as exc:
            raise ResponseProtocolError(str(exc)) from exc
    return tuple(result)


def protocol_from_fixed_grid(
    site_ids: Sequence[str],
    alpha_grid_ev: Sequence[float],
    *,
    estimator: EstimatorKind,
    polynomial_degree: int | None,
    scf_level_id: str,
    reference_node_id: str,
    observable_id: str,
    strategy: PerturbationStrategy = PerturbationStrategy.FIXED_PROTOCOL_GRID,
    protocol_version: str,
) -> ResolvedResponseProtocol:
    """Expand one symmetric global grid into paired site/mode column plans."""
    if not isinstance(estimator, EstimatorKind):
        raise ResponseProtocolError("estimator must be an EstimatorKind")
    if not isinstance(strategy, PerturbationStrategy):
        raise ResponseProtocolError("strategy must be a PerturbationStrategy")
    try:
        signed = tuple(require_fdf_representable_ev(alpha, "alpha_grid_ev") for alpha in alpha_grid_ev)
    except (ValidationError, TypeError) as exc:
        raise ResponseProtocolError(str(exc)) from exc
    if not signed:
        raise ResponseProtocolError("alpha_grid_ev must not be empty")
    if any(alpha == 0.0 for alpha in signed):
        raise ResponseProtocolError(
            "alpha_grid_ev must contain perturbation amplitudes, not the reference zero"
        )
    if len(set(signed)) != len(signed):
        raise ResponseProtocolError("alpha_grid_ev values must be distinct")
    signed_set = set(signed)
    if any(-alpha not in signed_set for alpha in signed):
        raise ResponseProtocolError("alpha_grid_ev must contain symmetric positive and negative amplitudes")
    magnitudes = tuple(sorted(abs(alpha) for alpha in signed))
    amplitudes = tuple(sorted(set(magnitudes)))
    if not isinstance(site_ids, Sequence) or isinstance(site_ids, (str, bytes)) or not site_ids:
        raise ResponseProtocolError("site_ids must be a nonempty sequence")
    normalized_sites = tuple(_identifier(site_id, "site_id") for site_id in site_ids)
    if len(set(normalized_sites)) != len(normalized_sites):
        raise ResponseProtocolError("site_ids must be distinct")
    columns = tuple(
        ColumnPlan(
            site_id=site_id,
            mode=mode,
            amplitudes_ev=amplitudes,
            estimator=EstimatorSpec(estimator, polynomial_degree, amplitudes),
            scf_level_id=scf_level_id,
        )
        for site_id in normalized_sites
        for mode in (ResponseMode.BARE, ResponseMode.SCREENED)
    )
    return ResolvedResponseProtocol(
        schema=_SCHEMA,
        strategy=strategy,
        protocol_version=protocol_version,
        reference_node_id=reference_node_id,
        observable_id=observable_id,
        columns=columns,
    )
