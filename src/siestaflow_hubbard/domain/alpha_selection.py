"""Conservative selection of a common finite-difference alpha window.

This module analyses measurements already obtained by a campaign.  It does not
create FDF files, submit work, or choose an electronic state.  The caller must
provide occupations and magnetic moments selected by a versioned backend
policy.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

import numpy as np


@dataclass(frozen=True)
class AlphaSelectionPolicy:
    """Acceptance thresholds in occupation and eV units.

    ``occupation_noise`` is an externally justified bound; it is not inferred
    from a single SCF trace.  A result is only a recommended analysis window,
    never a universal material parameter.
    """

    occupation_noise: float
    residual_relative: float = 0.02
    slope_relative: float = 0.05
    min_signal_to_noise: float = 10.0
    magnetic_tolerance: float = 0.05
    require_channel_signal: bool = True

    def validate(self) -> None:
        values = np.asarray([self.occupation_noise, self.residual_relative, self.slope_relative,
                             self.min_signal_to_noise, self.magnetic_tolerance], dtype=float)
        if not np.all(np.isfinite(values)) or np.any(values <= 0.0):
            raise ValueError("alpha selection policy requires positive finite thresholds")
        if not isinstance(self.require_channel_signal, bool):
            raise ValueError("require_channel_signal must be boolean")


def _require_centered_grid(alphas_ev: Sequence[float], initial_alpha_ev: float) -> np.ndarray:
    if not np.isfinite(initial_alpha_ev) or initial_alpha_ev <= 0.0:
        raise ValueError("initial_alpha_ev must be positive and finite")
    axis = np.asarray(alphas_ev, dtype=float)
    expected = initial_alpha_ev * np.array([-2.0, -1.0, -0.5, 0.0, 0.5, 1.0, 2.0])
    if axis.shape != (7,) or not np.all(np.isfinite(axis)):
        raise ValueError("exactly seven finite alpha values are required")
    if not np.allclose(np.sort(axis), expected, rtol=1e-12, atol=0.0):
        raise ValueError("alpha grid must be centered and contain +/-h/2, +/-h, +/-2h")
    return axis


def select_common_alpha_window(
    alphas_ev: Sequence[float],
    occupations: Any,
    magnetic_moments: Any,
    initial_alpha_ev: float,
    policy: AlphaSelectionPolicy,
    *,
    magnetic_states: Sequence[str] | None = None,
    override: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Evaluate three nested OLS windows and return the widest admissible one.

    ``occupations`` has shape ``(7, channels)`` (or ``(7,)``).  All relevant
    BARE and SCREENED channels must be supplied together so a window cannot be
    silently selected for only a favourable subset.  The routine rejects,
    rather than regularises, non-linear or magnetically discontinuous data.
    """

    policy.validate()
    axis = _require_centered_grid(alphas_ev, initial_alpha_ev)
    values = np.asarray(occupations, dtype=float)
    moments = np.asarray(magnetic_moments, dtype=float)
    if values.ndim == 1:
        values = values[:, None]
    if (
        values.ndim != 2
        or values.shape[0] != 7
        or values.shape[1] == 0
        or moments.ndim != 3
        or moments.shape[0] != 7
        or moments.shape[1] == 0
        or moments.shape[2] != 3
        or not np.all(np.isfinite(values))
        or not np.all(np.isfinite(moments))
    ):
        raise ValueError("occupations and magnetic moments have invalid shape or values")

    order = np.argsort(axis)
    axis, values, moments = axis[order], values[order], moments[order]
    state_changed = False
    if magnetic_states is not None:
        if len(magnetic_states) != 7 or any(not isinstance(state, str) or not state for state in magnetic_states):
            raise ValueError("magnetic state labels must be seven non-empty strings")
        state_changed = len(set(magnetic_states)) != 1
    magnetic_deviation = float(np.max(np.linalg.norm(moments - moments[3], axis=2)))
    magnetic_changed = state_changed or magnetic_deviation > policy.magnetic_tolerance

    amplitudes = initial_alpha_ev * np.array([0.5, 1.0, 2.0])
    central_slopes = []
    for amplitude in amplitudes:
        minus = int(np.argmin(np.abs(axis + amplitude)))
        plus = int(np.argmin(np.abs(axis - amplitude)))
        central_slopes.append((values[plus] - values[minus]) / (2.0 * amplitude))
    central_slopes = np.asarray(central_slopes)

    windows: list[dict[str, object]] = []
    for index, amplitude in enumerate(amplitudes):
        mask = np.abs(axis) <= amplitude * (1.0 + 1e-12)
        x, y = axis[mask], values[mask]
        denominator = float(x @ x)
        if denominator <= 0.0 or not np.isfinite(denominator):
            raise ValueError("alpha scale is numerically invalid")
        intercept = y.mean(axis=0)
        slope = x @ y / denominator
        residuals = y - intercept - x[:, None] * slope
        variance = np.maximum(
            np.sum(residuals**2, axis=0) / (len(x) - 2), policy.occupation_noise**2
        )
        stderr = np.sqrt(variance / denominator)
        comparison = central_slopes[: max(2, index + 1)]
        drift = np.max(np.abs(comparison - slope), axis=0)
        signal = np.abs(slope) * amplitude
        diagnostics = (intercept, slope, residuals, stderr, drift, signal)
        if not all(np.all(np.isfinite(item)) for item in diagnostics):
            raise ValueError("non-finite alpha diagnostics")

        reasons: list[str] = []
        if magnetic_changed:
            reasons.append("magnetic_state_changed")
        if policy.require_channel_signal and np.any(signal < policy.min_signal_to_noise * policy.occupation_noise):
            reasons.append("signal_unresolved")
        if np.any(np.max(np.abs(residuals), axis=0) > 3.0 * policy.occupation_noise + policy.residual_relative * signal):
            reasons.append("nonlinear_residual")
        if np.any(drift > policy.slope_relative * np.abs(slope) + 3.0 * stderr):
            reasons.append("slope_unstable")
        windows.append(
            {
                "alpha_ev": float(amplitude),
                "interval_ev": [-float(amplitude), float(amplitude)],
                "slope": slope.tolist(),
                "slope_standard_error": stderr.tolist(),
                "slope_uncertainty": (stderr + drift).tolist(),
                "residual_max": np.max(np.abs(residuals), axis=0).tolist(),
                "eligible": not reasons,
                "reasons": reasons,
            }
        )

    eligible = [window for window in windows if window["eligible"]]
    chosen: dict[str, object] | None = eligible[-1] if eligible else None
    applied_override: dict[str, object] | None = None
    if override is not None:
        if set(override) != {"alpha_ev", "actor", "reason"}:
            raise ValueError("override must contain alpha_ev, actor, and reason")
        alpha = override["alpha_ev"]
        if (
            not isinstance(alpha, (int, float))
            or isinstance(alpha, bool)
            or not np.isfinite(alpha)
            or not isinstance(override["actor"], str)
            or not override["actor"].strip()
            or not isinstance(override["reason"], str)
            or not override["reason"].strip()
        ):
            raise ValueError("invalid alpha override")
        chosen = next(
            (window for window in eligible if np.isclose(window["alpha_ev"], alpha, rtol=1e-12, atol=0.0)),
            None,
        )
        applied_override = dict(override, applied=chosen is not None)

    return {
        "status": "proposed" if chosen is not None else "rejected",
        "recommended_alpha_ev": chosen["alpha_ev"] if chosen is not None else None,
        "selected_interval_ev": chosen["interval_ev"] if chosen is not None else None,
        "slope_uncertainty": chosen["slope_uncertainty"] if chosen is not None else None,
        "magnetic_deviation": magnetic_deviation,
        "windows": windows,
        "policy": asdict(policy),
        "override": applied_override,
    }
