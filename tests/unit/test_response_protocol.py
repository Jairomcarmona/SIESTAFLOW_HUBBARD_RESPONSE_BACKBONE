"""Tests for the serialized, per-site response protocol model."""

from __future__ import annotations

import numpy as np
import pytest

from hubbardflow.domain.matrix_lr import fit_polynomial_response
from hubbardflow.domain.response_protocol import (
    EstimatorKind,
    EstimatorSpec,
    PerturbationStrategy,
    ResolvedResponseProtocol,
    ResponseProtocolError,
    protocol_from_fixed_grid,
)
from hubbardflow.domain.symmetry_reduction import ResponseMode

V6_GRID = (-0.06, -0.04, -0.02, 0.02, 0.04, 0.06)


def _protocol(grid: tuple[float, ...] = V6_GRID) -> ResolvedResponseProtocol:
    return protocol_from_fixed_grid(
        ("site-b", "site-a"),
        grid,
        estimator=EstimatorKind.POLYNOMIAL_LSQ,
        polynomial_degree=3,
        scf_level_id="scf-tight-v1",
        reference_node_id="reference-0",
        observable_id="siesta_occupations_total",
        protocol_version="test-v1",
    )


def test_mapping_round_trip_and_sorted_columns() -> None:
    protocol = _protocol()
    restored = ResolvedResponseProtocol.from_mapping(protocol.to_mapping())
    assert restored == protocol
    assert [column.site_id for column in protocol.columns] == [
        "site-a",
        "site-a",
        "site-b",
        "site-b",
    ]
    assert protocol.is_common_grid()


def test_digest_is_invariant_to_column_input_order() -> None:
    protocol = _protocol()
    reordered = ResolvedResponseProtocol(
        schema=protocol.schema,
        strategy=protocol.strategy,
        protocol_version=protocol.protocol_version,
        reference_node_id=protocol.reference_node_id,
        observable_id=protocol.observable_id,
        columns=tuple(reversed(protocol.columns)),
    )
    assert reordered.digest() == protocol.digest()


@pytest.mark.parametrize(
    ("grid", "message"),
    [
        ((-0.02, -0.04, 0.02), "symmetric"),
        ((-0.02001, 0.02001), "representable"),
        ((-0.02, 0.02, 0.02), "distinct"),
        ((-0.02, 0.02, 0.0), "reference zero"),
    ],
)
def test_rejects_invalid_alpha_grids(grid: tuple[float, ...], message: str) -> None:
    with pytest.raises(ResponseProtocolError, match=message):
        _protocol(grid)


@pytest.mark.parametrize(
    ("kind", "degree", "expected"),
    [
        (EstimatorKind.LINEAR_LSQ, None, 21.428571428571427),
        (EstimatorKind.POLYNOMIAL_LSQ, 3, 58.33333333333333),
    ],
)
def test_v6_grid_noise_gain(kind: EstimatorKind, degree: int | None, expected: float) -> None:
    estimator = EstimatorSpec(kind, degree, (0.02, 0.04, 0.06))
    assert sum(abs(weight) for _, weight in estimator.weights()) == pytest.approx(expected, abs=1e-12)


def test_polynomial_weights_match_existing_fit() -> None:
    amplitudes = (0.02, 0.04, 0.06)
    estimator = EstimatorSpec(EstimatorKind.POLYNOMIAL_LSQ, 3, amplitudes)
    weights = estimator.weights()
    alpha = np.asarray([point for point, _ in weights], dtype=float)
    weight = np.asarray([factor for _, factor in weights], dtype=float)
    rng = np.random.default_rng(8721)
    for occupations in rng.normal(size=(25, len(alpha))):
        weighted_slope = float(weight @ occupations)
        fitted_slope = fit_polynomial_response(alpha.tolist(), occupations.tolist(), degree=3).slope
        assert weighted_slope == pytest.approx(fitted_slope, abs=1e-12)


def test_requires_both_modes_and_estimator_sufficient_grid() -> None:
    protocol = _protocol()
    with pytest.raises(ResponseProtocolError, match="one BARE and one SCREENED"):
        ResolvedResponseProtocol(
            protocol.schema,
            protocol.strategy,
            protocol.protocol_version,
            protocol.reference_node_id,
            protocol.observable_id,
            tuple(column for column in protocol.columns if column.mode is ResponseMode.BARE),
        )
    with pytest.raises(ResponseProtocolError, match="requires at least"):
        EstimatorSpec(EstimatorKind.POLYNOMIAL_LSQ, 3, (0.02, 0.04))


def test_protocol_strategy_and_per_column_estimators_are_preserved() -> None:
    protocol = protocol_from_fixed_grid(
        ("site-0",),
        V6_GRID,
        estimator=EstimatorKind.LINEAR_LSQ,
        polynomial_degree=None,
        scf_level_id="scf-default",
        reference_node_id="ref-0",
        observable_id="occ",
        strategy=PerturbationStrategy.USER_EXPLICIT_GRID,
        protocol_version="user-v2",
    )
    assert protocol.strategy is PerturbationStrategy.USER_EXPLICIT_GRID
    assert all(column.estimator.kind is EstimatorKind.LINEAR_LSQ for column in protocol.columns)
    assert all(column.estimator.polynomial_degree is None for column in protocol.columns)
    assert all(column.mode in (ResponseMode.BARE, ResponseMode.SCREENED) for column in protocol.columns)
