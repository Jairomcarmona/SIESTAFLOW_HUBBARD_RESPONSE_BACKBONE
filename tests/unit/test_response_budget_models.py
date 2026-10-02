"""Fail-closed immutable mappings for diagnostic evidence."""

import json
import math
from dataclasses import FrozenInstanceError

import pytest
from hypothesis import given
from hypothesis import strategies as st

from hubbardflow.domain.response_budget_models import NoiseModel, PointObservation, ResponseBudgetError


@given(st.floats(allow_nan=True, allow_infinity=True))
def test_point_mapping_rejects_nonfinite_and_roundtrips_finite(value: float) -> None:
    if not math.isfinite(value):
        with pytest.raises(ResponseBudgetError):
            PointObservation(0.02, value, 0.0)
    else:
        point = PointObservation(0.02, value, 0.0)
        assert PointObservation.from_mapping(json.loads(json.dumps(point.to_mapping()))) == point


def test_record_immutable_and_exact_fields() -> None:
    point = PointObservation(0.02, 7.0, 0.0)
    with pytest.raises(FrozenInstanceError):
        point.occupation_e = 1.0  # type: ignore[misc]
    for payload in ({}, {"alpha_ev": 0.02, "occupation_e": 7.0, "half_width_e": 0.0, "unknown": 1}):
        with pytest.raises(ResponseBudgetError):
            PointObservation.from_mapping(payload)
    assert NoiseModel.from_mapping(NoiseModel().to_mapping()) == NoiseModel()
