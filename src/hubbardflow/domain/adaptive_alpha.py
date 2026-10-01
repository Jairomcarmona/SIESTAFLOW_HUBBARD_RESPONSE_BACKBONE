"""Campaign planning and fail-closed authorization for finite-difference alpha.

This module deliberately separates *planning seven points* from deciding which
window may be used in the final response matrix.  It never changes an FDF,
submits a task, or widens a rejected window.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Sequence

from .alpha_selection import AlphaSelectionPolicy, select_common_alpha_window


class AlphaPlanError(ValueError):
    """An adaptive-alpha plan is incomplete or not scientifically usable."""


@dataclass(frozen=True)
class AdaptiveAlphaPolicy:
    initial_alpha_ev: float
    selection: AlphaSelectionPolicy
    require_seven_points: bool = True

    def validate(self) -> None:
        if not isfinite(self.initial_alpha_ev) or self.initial_alpha_ev <= 0.0:
            raise AlphaPlanError("initial_alpha_ev must be positive and finite")
        self.selection.validate()
        if not self.require_seven_points:
            raise AlphaPlanError("adaptive alpha requires a seven-point symmetric evidence grid")

    @property
    def levels_ev(self) -> tuple[float, ...]:
        self.validate()
        h = self.initial_alpha_ev
        return (-2.0 * h, -h, -0.5 * h, 0.0, 0.5 * h, h, 2.0 * h)


def authorize_alpha_window(
    policy: AdaptiveAlphaPolicy,
    alphas_ev: Sequence[float],
    occupations: Any,
    magnetic_moments: Any,
    *,
    magnetic_states: Sequence[str] | None = None,
) -> dict[str, object]:
    """Return an auditable decision or raise before matrix reconstruction.

    The report records the rejected diagnostics.  The exception prevents an
    executor from continuing to invert a response calculated at an arbitrary
    amplitude after the common linear regime was rejected.
    """
    policy.validate()
    report = select_common_alpha_window(
        alphas_ev, occupations, magnetic_moments, policy.initial_alpha_ev,
        policy.selection, magnetic_states=magnetic_states,
    )
    if report["status"] != "proposed":
        raise AlphaPlanError("no common, linear, magnetically stable alpha window was authorized")
    return {
        "kind": "adaptive_alpha_authorization_v1",
        "initial_alpha_ev": policy.initial_alpha_ev,
        "levels_ev": list(policy.levels_ev),
        "decision": report,
    }
