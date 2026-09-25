"""Admission gate binding a source-audited BARE profile to an executable.

The gate is local and scheduler-neutral.  It never loads a module or starts a
process: callers supply an executable path and captured version text.  The
observed identity must match an explicit compatibility-registry record before
the 5.4.2 BARE profile can be used.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from siestaflow_hubbard.domain.backend_compatibility import (
    BackendCompatibilityError,
    BackendCompatibilityRegistry,
    BackendIdentity as RegisteredBackendIdentity,
    CompatibilityRecord,
    ScientificProfile,
)

from .backend_identity import BackendIdentity as ObservedBackendIdentity
from .backend_identity import BackendIdentityError, identify_backend, sha256_file
from .siesta542_bare_profile import Siesta542PotentialShiftHamiltonianProfile


class BackendAdmissionError(ValueError):
    """A backend is not admitted for an audited scientific profile."""


@dataclass(frozen=True)
class BackendAdmission:
    observed: ObservedBackendIdentity
    scientific_profile: ScientificProfile
    registry_record: CompatibilityRecord
    # Set only by the campaign-contract plugin.  Low-level registry admission
    # remains useful for inspection, but cannot construct a production runtime.
    _campaign_contract_token: object | None = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.registry_record.identity.executable_sha256 != self.observed.executable_sha256:
            raise BackendAdmissionError("registry record does not bind the observed executable")

    def require_declared_executable(self, executable_path: str | Path) -> None:
        """Re-hash the declared launch target; path equality is never trusted."""
        try:
            digest = sha256_file(executable_path)
        except BackendIdentityError as exc:
            raise BackendAdmissionError("declared executable cannot be identified") from exc
        if digest != self.observed.executable_sha256:
            raise BackendAdmissionError("declared executable hash differs from admitted backend")


def admit_siesta542_potential_shift_hamiltonian(
    executable_path: str | Path,
    version_text: str,
    registry: BackendCompatibilityRegistry,
    profile: Siesta542PotentialShiftHamiltonianProfile | None = None,
) -> BackendAdmission:
    """Authorize only an exact registered executable for the audited profile."""
    profile = profile or Siesta542PotentialShiftHamiltonianProfile()
    try:
        observed = identify_backend(executable_path, version_text, backend="siesta")
        scientific_profile = ScientificProfile(
            profile.profile_id,
            profile.profile_version,
            {"source_revision": profile.source_revision},
        )
        record = registry.require_compatible(
            RegisteredBackendIdentity("siesta", observed.version, observed.executable_sha256),
            scientific_profile,
        )
    except (BackendIdentityError, BackendCompatibilityError) as exc:
        raise BackendAdmissionError("backend/profile admission rejected: {0}".format(exc)) from exc
    return BackendAdmission(observed, scientific_profile, record)


__all__ = [
    "BackendAdmission",
    "BackendAdmissionError",
    "admit_siesta542_potential_shift_hamiltonian",
]
