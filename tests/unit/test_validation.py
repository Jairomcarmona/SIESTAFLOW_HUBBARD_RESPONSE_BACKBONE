"""Tests for common fail-closed domain validation helpers."""

from __future__ import annotations

import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from hubbardflow.domain.validation import (
    ValidationError,
    require_fdf_representable_ev,
    require_finite,
    require_int,
    require_nonnegative_finite,
    require_positive_finite,
    require_sha256,
)


@given(st.sampled_from([math.nan, math.inf, -math.inf]))
def test_require_finite_rejects_non_finite(value: float) -> None:
    with pytest.raises(ValidationError, match="finite"):
        require_finite(value, "sample")


def test_require_finite_rejects_integer_overflow() -> None:
    with pytest.raises(ValidationError, match="finite number"):
        require_finite(10**1000, "sample")


@given(st.booleans())
def test_numeric_helpers_reject_booleans(value: bool) -> None:
    for validator in (require_finite, require_positive_finite, require_nonnegative_finite):
        with pytest.raises(ValidationError, match="finite number"):
            validator(value, "sample")
    with pytest.raises(ValidationError, match="integer"):
        require_int(value, "sample", minimum=0)


@given(st.floats(allow_nan=False, allow_infinity=False))
def test_finite_values_round_trip(value: float) -> None:
    assert require_finite(value, "sample") == value


def test_positive_and_nonnegative_requirements() -> None:
    assert require_positive_finite(0.25, "alpha") == 0.25
    assert require_nonnegative_finite(0, "width") == 0.0
    with pytest.raises(ValidationError, match="positive"):
        require_positive_finite(0, "alpha")
    with pytest.raises(ValidationError, match="nonnegative"):
        require_nonnegative_finite(-0.1, "width")


def test_require_int_and_sha256() -> None:
    assert require_int(3, "degree", minimum=1) == 3
    assert require_sha256("a" * 64, "digest") == "a" * 64
    with pytest.raises(ValidationError, match="at least"):
        require_int(0, "degree", minimum=1)
    with pytest.raises(ValidationError, match="lowercase"):
        require_sha256("A" * 64, "digest")


def test_fdf_representability_is_exact_at_requested_precision() -> None:
    assert require_fdf_representable_ev(0.02, "alpha") == 0.02
    assert require_fdf_representable_ev(0.025, "alpha", decimals=3) == 0.025
    with pytest.raises(ValidationError, match="representable"):
        require_fdf_representable_ev(0.02001, "alpha")
