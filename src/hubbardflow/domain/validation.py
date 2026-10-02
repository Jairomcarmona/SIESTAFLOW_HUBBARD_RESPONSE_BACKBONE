"""Shared input validators for FD-EBQ domain models.

These helpers keep invalid numerical data out of diagnostic calculations. In
particular, FDF amplitudes must survive the backend's fixed decimal formatting
without changing the requested perturbation.
"""

from __future__ import annotations

import math
import re
from decimal import Decimal, InvalidOperation
from numbers import Real


class ValidationError(ValueError):
    """Raised when a value cannot safely enter a domain model."""


_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")


def require_finite(value: object, label: str) -> float:
    """Return a finite real as ``float``, rejecting booleans and non-numbers."""
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValidationError(f"{label} must be a finite number")
    try:
        result = float(value)
    except (OverflowError, TypeError, ValueError) as exc:
        raise ValidationError(f"{label} must be a finite number") from exc
    if not math.isfinite(result):
        raise ValidationError(f"{label} must be finite")
    return result


def require_positive_finite(value: object, label: str) -> float:
    """Return a finite real greater than zero."""
    result = require_finite(value, label)
    if result <= 0.0:
        raise ValidationError(f"{label} must be positive")
    return result


def require_nonnegative_finite(value: object, label: str) -> float:
    """Return a finite real greater than or equal to zero."""
    result = require_finite(value, label)
    if result < 0.0:
        raise ValidationError(f"{label} must be nonnegative")
    return result


def require_int(value: object, label: str, *, minimum: int) -> int:
    """Return an integer at least ``minimum``; booleans are not integers here."""
    if isinstance(minimum, bool) or not isinstance(minimum, int):
        raise ValidationError("minimum must be an integer")
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(f"{label} must be an integer")
    if value < minimum:
        raise ValidationError(f"{label} must be at least {minimum}")
    return value


def require_sha256(value: object, label: str) -> str:
    """Return a lowercase, 64-character SHA-256 hexadecimal digest."""
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise ValidationError(f"{label} must be a lowercase 64-character SHA-256 hex digest")
    return value


def require_fdf_representable_ev(value: float, label: str, *, decimals: int = 4) -> float:
    """Require an energy amplitude exactly representable at the FDF precision.

    The FDF materializer emits fixed decimal places. Comparing decimal strings
    avoids accepting binary floating-point noise by an invented tolerance.
    """
    require_finite(value, label)
    places = require_int(decimals, "decimals", minimum=0)
    try:
        decimal_value = Decimal(str(value))
        quantum = Decimal(1).scaleb(-places)
        represented = decimal_value.quantize(quantum)
    except (InvalidOperation, ValueError) as exc:
        raise ValidationError(f"{label} cannot be represented with {places} decimal places") from exc
    if decimal_value != represented:
        raise ValidationError(f"{label} must be representable to {places} decimal places")
    return float(represented)
