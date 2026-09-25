"""Keep a charge-response U distinct from a Dudarev FDF parameter."""

from __future__ import annotations

from math import isfinite
from typing import Any, Mapping


SCALAR_CHARGE = "U_scalar_charge"
DUDAREV_UEFF = "Ueff_Dudarev"


class HubbardParameterSemanticsError(ValueError):
    """A response result cannot be used as the requested DFT+U parameter."""


def require_dudarev_evidence(evidence: Mapping[str, Any]) -> tuple[float, tuple[float, float] | None]:
    """Admit an explicitly sourced Ueff; never infer it from a scalar U."""
    if evidence.get("parameter_kind") != DUDAREV_UEFF:
        raise HubbardParameterSemanticsError("physical DFT+U requires parameter_kind=Ueff_Dudarev")
    if evidence.get("source_parameter_kind") == SCALAR_CHARGE:
        raise HubbardParameterSemanticsError(
            "U_scalar_charge cannot be promoted automatically to Ueff_Dudarev"
        )
    if not isinstance(evidence.get("source_parameter_kind"), str) or not evidence["source_parameter_kind"].strip():
        raise HubbardParameterSemanticsError("Ueff_Dudarev requires an explicit source_parameter_kind")
    if not isinstance(evidence.get("derivation"), str) or not evidence["derivation"].strip():
        raise HubbardParameterSemanticsError("Ueff_Dudarev requires a documented derivation")
    if not isinstance(evidence.get("source_reference"), str) or not evidence["source_reference"].strip():
        raise HubbardParameterSemanticsError("Ueff_Dudarev requires a source reference")
    if isinstance(evidence.get("value_eV"), bool):
        raise HubbardParameterSemanticsError("Ueff_Dudarev value_eV must be numeric")
    try:
        value = float(evidence["value_eV"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HubbardParameterSemanticsError("Ueff_Dudarev value_eV must be numeric") from exc
    if not isfinite(value) or value < 0:
        raise HubbardParameterSemanticsError("Ueff_Dudarev value_eV must be finite and nonnegative")
    raw_interval = evidence.get("interval_eV")
    if raw_interval is None:
        return value, None
    if not isinstance(raw_interval, (list, tuple)) or len(raw_interval) != 2 or any(
        isinstance(item, bool) for item in raw_interval
    ):
        raise HubbardParameterSemanticsError("Ueff_Dudarev interval_eV must have two numeric endpoints")
    try:
        low, high = (float(item) for item in raw_interval)
    except (TypeError, ValueError) as exc:
        raise HubbardParameterSemanticsError("Ueff_Dudarev interval_eV must have two numeric endpoints") from exc
    if not all(isfinite(item) for item in (low, high)) or not 0 <= low <= value <= high:
        raise HubbardParameterSemanticsError("Ueff_Dudarev interval_eV must contain value_eV")
    return value, (low, high)
