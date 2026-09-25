"""Compose an admitted SIESTA LR runtime without teaching the DAG about a site.

The generic DAG and Slurm allocation adapters intentionally know nothing about
SIESTA binaries or scientific profiles.  This module is the narrow production
composition seam: an exact backend admission happens *before* a command
factory exists, so a rejected backend cannot materialize an FDF, create a run
directory, or reach a subprocess.
"""
from __future__ import annotations

from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import Mapping, Sequence

from siestaflow_hubbard.domain.lr_campaign_contract import LinearResponseBareCampaignContract
from siestaflow_hubbard.execution.execution_profile import ExecutionProfile
from siestaflow_hubbard.execution.runtime_adapters import LocalSubprocessExecutor, SlurmAllocationExecutor

from .backend_admission import BackendAdmission, BackendAdmissionError
from .backend_admission_plugin import (
    _is_campaign_contract_admission,
    admit_siesta542_from_campaign_contract,
)
from .command_factory import SiestaCampaignLayout, SiestaCommandFactory
from .output_validator import SiestaArtifactSpec, SiestaOutputValidator, SiestaValidationPolicy
from .siesta542_bare_profile import Siesta542PotentialShiftHamiltonianProfile


class SiestaProductionRuntimeError(ValueError):
    """The private runtime facts cannot be composed into an admitted backend."""


@dataclass(frozen=True)
class AdmittedSiestaRuntime:
    """Backend-specific execution pieces created only after exact admission."""

    admission: BackendAdmission
    factory: SiestaCommandFactory
    validator: SiestaOutputValidator

    def __post_init__(self) -> None:
        """Reject hand-assembled production pieces that do not share admission."""
        if not isinstance(self.admission, BackendAdmission):
            raise SiestaProductionRuntimeError("an admitted SIESTA backend is required")
        if not _is_campaign_contract_admission(self.admission):
            raise SiestaProductionRuntimeError("production runtime requires campaign-contract admission")
        if self.factory.admission != self.admission:
            raise SiestaProductionRuntimeError("factory is not bound to this backend admission")
        if self.factory.artifacts is not self.validator.artifacts:
            raise SiestaProductionRuntimeError("factory and validator must share one artifact registry")
        policy = self.validator.policy
        if (
            policy.bare_profile != self.factory.bare_profile
            or policy.bare_backend_admission != self.admission
            or policy.siesta_version != self.admission.observed.version
        ):
            raise SiestaProductionRuntimeError("validator lacks the admitted current BARE profile")
        if not (
            policy.require_reference_magnetic_evidence
            and policy.require_dm
            and policy.require_scf_convergence_for_screened
        ):
            raise SiestaProductionRuntimeError("production validator policy cannot weaken scientific acceptance")

    def local_executor(self) -> LocalSubprocessExecutor:
        return LocalSubprocessExecutor(self.factory, self.validator)

    def slurm_executor(
        self,
        profile: ExecutionProfile,
        hosts: Sequence[str],
        *,
        environment: Mapping[str, str] | None = None,
    ) -> SlurmAllocationExecutor:
        """Use an already granted allocation; this method never calls ``sbatch``."""
        return SlurmAllocationExecutor(
            profile, hosts, self.factory, self.validator, environment=environment,
        )


def build_admitted_siesta542_runtime(
    *,
    campaign_root: str | PathLike[str],
    contract: LinearResponseBareCampaignContract,
    executable_path: str | PathLike[str],
    profile: ExecutionProfile,
    hosts: Sequence[str],
    layout: SiestaCampaignLayout,
    artifacts: dict[str, SiestaArtifactSpec] | None = None,
    bare_profile: Siesta542PotentialShiftHamiltonianProfile | None = None,
) -> AdmittedSiestaRuntime:
    """Build the production SIESTA route only after exact backend admission.

    ``executable_path`` is private deployment data.  The portable contract
    names it logically, and admission binds its observed hash and version to
    the versioned scientific profile.  The execution profile must launch that
    exact same file; accepting two paths would leave a bypass between
    admission and MPI.
    """
    bare_profile = bare_profile or Siesta542PotentialShiftHamiltonianProfile()
    executable = Path(executable_path)
    if not executable.is_absolute():
        raise SiestaProductionRuntimeError("private SIESTA executable must be an explicit absolute path")
    try:
        resolved = executable.resolve(strict=True)
    except OSError as exc:
        raise SiestaProductionRuntimeError("private SIESTA executable cannot be resolved") from exc
    profile_executable_input = Path(profile.runtime.siesta_executable)
    if not profile_executable_input.is_absolute():
        raise SiestaProductionRuntimeError("execution profile SIESTA executable must be an explicit absolute path")
    if not profile.runtime.launcher.command or not Path(profile.runtime.launcher.command[0]).is_absolute():
        launcher_label = "Hydra" if profile.runtime.launcher.kind == "hydra" else "Open MPI"
        raise SiestaProductionRuntimeError(
            f"execution profile {launcher_label} launcher must be an explicit absolute path"
        )
    try:
        profile_executable = profile_executable_input.resolve(strict=True)
    except OSError as exc:
        raise SiestaProductionRuntimeError("execution profile SIESTA executable cannot be resolved") from exc
    if profile_executable != resolved:
        raise SiestaProductionRuntimeError(
            "execution profile executable differs from the backend submitted for admission"
        )
    try:
        admission = admit_siesta542_from_campaign_contract(
            campaign_root=campaign_root,
            contract=contract,
            executable_path=resolved,
            profile=bare_profile,
        )
    except BackendAdmissionError as exc:
        raise SiestaProductionRuntimeError("SIESTA backend admission rejected") from exc

    registry = {} if artifacts is None else artifacts
    factory = SiestaCommandFactory(
        profile, hosts, layout, registry, admission=admission, bare_profile=bare_profile,
    )
    validator = SiestaOutputValidator(
        registry,
        policy=SiestaValidationPolicy(
            siesta_version=admission.observed.version,
            bare_profile=bare_profile,
            bare_backend_admission=admission,
        ),
    )
    return AdmittedSiestaRuntime(admission, factory, validator)


__all__ = [
    "AdmittedSiestaRuntime",
    "SiestaProductionRuntimeError",
    "build_admitted_siesta542_runtime",
]
