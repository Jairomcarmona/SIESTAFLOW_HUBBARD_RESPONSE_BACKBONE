"""Generic empirical repeatability summaries, independent of materials."""
from __future__ import annotations

from fractions import Fraction
from typing import Sequence

from .u_certification import CertificationError, rational


def repeatability_envelope(primary: str | int | Fraction,
                           replicas: Sequence[str | int | Fraction]) -> dict[str, Fraction]:
    """Return the max observed absolute replica delta and its primary-centered band.

    Values are exact decimal strings or integers. The returned band is an
    empirical envelope for the supplied replicas, not a confidence interval.
    """
    if not replicas:
        raise CertificationError("repeatability requires at least one replica")
    center = rational(primary)
    observed = [rational(value) for value in replicas]
    maximum_delta = max(abs(value - center) for value in observed)
    return {
        "max_abs_delta": maximum_delta,
        "lower": center - maximum_delta,
        "upper": center + maximum_delta,
    }
