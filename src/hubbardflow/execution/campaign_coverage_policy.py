"""Bind explicit campaign flags to the versioned coverage policy.

An opt-in only permits diagnostic candidates. Prospective validation and the
complete I.5 state gate remain independent requirements for production.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

from hubbardflow.domain.symmetry_operation_models import CoveragePolicy, coverage_policy_v1


class CampaignCoveragePolicyError(ValueError):
    """Conflicting flag declarations cannot establish a reproducible policy."""


def campaign_coverage_policy(config: Mapping[str, object]) -> CoveragePolicy:
    """Accept top-level opt-ins or a full policy, rejecting conflicting values."""
    raw = config.get("coverage_policy")
    if raw is not None and not isinstance(raw, Mapping):
        raise CampaignCoveragePolicyError("coverage_policy must be a mapping")
    try:
        policy = coverage_policy_v1() if raw is None else CoveragePolicy.from_mapping(raw)
    except (ValueError, KeyError, TypeError) as exc:
        raise CampaignCoveragePolicyError(f"invalid coverage_policy: {exc}") from exc
    flags: dict[str, bool] = {}
    for name in ("allow_spin_flip", "allow_rotations"):
        value = config.get(name, getattr(policy, name))
        if type(value) is not bool:
            raise CampaignCoveragePolicyError(f"{name} must be a boolean")
        if raw is not None and name in config and value != getattr(policy, name):
            raise CampaignCoveragePolicyError(f"{name} conflicts with coverage_policy")
        flags[name] = value
    return replace(policy, allow_spin_flip=flags["allow_spin_flip"], allow_rotations=flags["allow_rotations"])
