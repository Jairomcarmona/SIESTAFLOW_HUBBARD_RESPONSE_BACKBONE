"""Scheduler-neutral admission adapter for an explicit backend matrix.

The adapter is intentionally small: callers provide the registry JSON, the
selected executable, and version text captured by their environment.  It
never searches ``PATH``, loads modules, invokes a backend, or knows about a
cluster scheduler.  Malformed or missing registry data fails closed.
"""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Union

from siestaflow_hubbard.domain.backend_compatibility import (
    BackendCompatibilityError,
    BackendCompatibilityRegistry,
)
from siestaflow_hubbard.domain.lr_campaign_contract import (
    LinearResponseBareCampaignContract,
    LinearResponseContractError,
)

from .backend_admission import (
    BackendAdmission,
    BackendAdmissionError,
    admit_siesta542_potential_shift_hamiltonian,
)
from .siesta542_bare_profile import Siesta542PotentialShiftHamiltonianProfile


PathLike = Union[str, bytes, Path]
_CAMPAIGN_ADMISSION_TOKEN = object()


def _is_campaign_contract_admission(admission: BackendAdmission) -> bool:
    """Internal provenance guard for production runtime composition."""
    return admission._campaign_contract_token is _CAMPAIGN_ADMISSION_TOKEN


def load_backend_compatibility_registry(path: PathLike) -> BackendCompatibilityRegistry:
    """Load one explicit JSON matrix without accepting implicit defaults."""
    candidate = Path(path)
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise BackendAdmissionError("compatibility registry path does not exist") from exc
    if not resolved.is_file():
        raise BackendAdmissionError("compatibility registry path is not a regular file")
    try:
        text = resolved.read_text(encoding="utf-8")
        payload = json.loads(text)
        return BackendCompatibilityRegistry.from_dict(payload)
    except (OSError, UnicodeError, json.JSONDecodeError, BackendCompatibilityError) as exc:
        raise BackendAdmissionError("compatibility registry cannot be loaded") from exc


def admit_siesta542_from_registry_file(
    *,
    executable_path: PathLike,
    version_text: str,
    registry_path: PathLike,
    profile: Siesta542PotentialShiftHamiltonianProfile | None = None,
) -> BackendAdmission:
    """Return an admission from an explicit matrix and explicit observations.

    The registry is loaded on every call so a caller cannot accidentally use
    a stale in-memory allowlist.  Identity and profile resolution remain the
    responsibility of the existing domain admission gate.
    """
    registry = load_backend_compatibility_registry(registry_path)
    try:
        return admit_siesta542_potential_shift_hamiltonian(
            executable_path, version_text, registry, profile,
        )
    except BackendAdmissionError:
        raise


def admit_siesta542_from_campaign_contract(
    *,
    campaign_root: PathLike,
    contract: LinearResponseBareCampaignContract,
    executable_path: PathLike,
    profile: Siesta542PotentialShiftHamiltonianProfile | None = None,
) -> BackendAdmission:
    """Compose the portable campaign declaration with a private executable.

    The declaration contains only a logical executable name.  A private
    runtime plugin supplies the actual path; its basename must match the
    declaration, so a registry-approved binary cannot be substituted for a
    different declared backend.
    """
    profile = profile or Siesta542PotentialShiftHamiltonianProfile()
    if contract.backend_id != "siesta" or contract.scientific_profile.key != (
        profile.profile_id, profile.profile_version
    ):
        raise BackendAdmissionError("campaign contract does not select this SIESTA scientific profile")
    try:
        root = Path(campaign_root).resolve(strict=True)
        executable = Path(executable_path).resolve(strict=True)
        if executable.name != Path(contract.declared_executable).name:
            raise BackendAdmissionError("declared executable name differs from private executable")
        version_text = contract.version_text_path(root).read_text(encoding="utf-8")
        registry_path = contract.registry_path(root)
    except (OSError, LinearResponseContractError) as exc:
        raise BackendAdmissionError("campaign contract artifacts cannot be resolved") from exc
    admission = admit_siesta542_from_registry_file(
        executable_path=executable,
        version_text=version_text,
        registry_path=registry_path,
        profile=profile,
    )
    return replace(admission, _campaign_contract_token=_CAMPAIGN_ADMISSION_TOKEN)


__all__ = [
    "admit_siesta542_from_registry_file",
    "admit_siesta542_from_campaign_contract",
    "load_backend_compatibility_registry",
]
