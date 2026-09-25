"""Materialize auditable SIESTA LR nodes inside an existing allocation.

This factory is intentionally site-neutral: it knows no module name, cluster,
partition, account or absolute institutional path.  A validated execution
profile supplies the executable and Hydra launcher; the surrounding private
job wrapper is responsible for making its declared modules available.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from hashlib import sha256
from pathlib import Path
from shutil import copy2
import re
from typing import Mapping, Sequence

from siestaflow_hubbard.execution.execution_profile import ExecutionProfile, ProfileValidationError
from siestaflow_hubbard.execution.hydra_launcher import build_mpi_launch
from siestaflow_hubbard.execution.lr_dag import LRDagNode, LRNodeKind
from siestaflow_hubbard.execution.runtime_adapters import NodeCommand

from .output_validator import SiestaArtifactSpec
from .backend_admission import BackendAdmission, BackendAdmissionError
from .backend_admission_plugin import _is_campaign_contract_admission
from .siesta542_bare_profile import Siesta542PotentialShiftHamiltonianProfile
from .symmetry_materializer import write_materialized_response


class SiestaCommandFactoryError(ValueError):
    """A node cannot be safely materialized from its declared inputs."""


def _verified_absolute_file(value: str, label: str) -> Path:
    """Resolve one deployment-supplied program without consulting PATH."""
    candidate = Path(value)
    if not value or not candidate.is_absolute():
        raise SiestaCommandFactoryError(f"{label} must be an explicit absolute path")
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise SiestaCommandFactoryError(f"{label} cannot be resolved") from exc
    if not resolved.is_file():
        raise SiestaCommandFactoryError(f"{label} must be a regular file")
    return resolved


def _verified_mpi_launcher(command: Sequence[str], kind: str) -> Path:
    """Accept only a direct, provider-specific MPI executable."""
    label = "Hydra" if kind == "hydra" else "Open MPI" if kind == "openmpi" else "MPI"
    if len(command) != 1:
        raise SiestaCommandFactoryError(
            f"{label} launcher must be exactly one direct executable path; launcher arguments are forbidden"
        )
    launcher = _verified_absolute_file(command[0], f"{label} launcher")
    if kind == "hydra" and launcher.name.casefold() not in {"mpiexec.hydra", "mpiexec.hydra.exe"}:
        raise SiestaCommandFactoryError("SIESTA launcher must be the direct mpiexec.hydra executable")
    if kind == "openmpi" and launcher.name.casefold() not in {
        "orterun", "orterun.exe", "mpiexec.openmpi", "mpiexec.openmpi.exe",
        "mpirun.openmpi", "mpirun.openmpi.exe",
    }:
        raise SiestaCommandFactoryError("SIESTA launcher must be a direct Open MPI executable")
    if kind not in {"hydra", "openmpi"}:
        raise SiestaCommandFactoryError("unsupported MPI launcher kind")
    return launcher


def _relative_name(value: str, label: str) -> Path:
    candidate = Path(value)
    if not value or candidate.is_absolute() or any(part in {"", ".", ".."} for part in candidate.parts):
        raise SiestaCommandFactoryError(f"{label} must be a non-empty relative path")
    return candidate


def _digest_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_node_name(node: LRDagNode) -> str:
    readable = re.sub(r"[^A-Za-z0-9_.-]+", "_", node.node_id).strip("_.") or "node"
    return f"{readable[:72]}_{sha256(node.node_id.encode()).hexdigest()[:12]}"


@dataclass(frozen=True)
class SiestaCampaignLayout:
    """Immutable input layout for one campaign; all artifact names are relative."""

    reference_fdf: Path
    run_root: Path
    reference_dm: Path | None
    reference_dm_name: str
    static_artifacts: Mapping[str, Path] = field(default_factory=dict)
    fdf_name: str = "siesta.fdf"
    output_name: str = "siesta.out"
    error_name: str = "siesta.err"

    def validate(self) -> None:
        if not self.reference_fdf.is_file():
            raise SiestaCommandFactoryError("reference FDF is missing")
        if self.reference_dm is not None and not self.reference_dm.is_file():
            raise SiestaCommandFactoryError("reference DM is missing")
        for label, value in (("reference DM name", self.reference_dm_name), ("FDF name", self.fdf_name),
                             ("output name", self.output_name), ("error name", self.error_name)):
            _relative_name(value, label)
        for destination, source in self.static_artifacts.items():
            _relative_name(destination, "static artifact destination")
            if not isinstance(source, Path) or not source.is_file():
                raise SiestaCommandFactoryError("static artifact source is missing")


class SiestaCommandFactory:
    """A command factory that materializes one node without running it.

    ``artifacts`` is a shared registry passed to ``SiestaOutputValidator``.
    It is filled only after the corresponding node directory and files have
    been materialized successfully.
    """

    def __init__(
        self,
        profile: ExecutionProfile,
        hosts: Sequence[str],
        layout: SiestaCampaignLayout,
        artifacts: dict[str, SiestaArtifactSpec],
        *,
        admission: BackendAdmission,
        bare_profile: Siesta542PotentialShiftHamiltonianProfile,
    ):
        profile.require_submission_evidence()
        layout.validate()
        if not isinstance(admission, BackendAdmission):
            raise SiestaCommandFactoryError("an admitted SIESTA backend is required")
        if not _is_campaign_contract_admission(admission):
            raise SiestaCommandFactoryError(
                "production SIESTA factory requires admission from a campaign contract"
            )
        if not isinstance(bare_profile, Siesta542PotentialShiftHamiltonianProfile):
            raise SiestaCommandFactoryError("the current SIESTA 5.4.2 BARE profile is required")
        if not hosts or len(set(hosts)) != len(hosts):
            raise SiestaCommandFactoryError("hosts must be a non-empty unique sequence")
        if len(hosts) * profile.runtime.launcher.processes_per_node != profile.allocation.total_cpus:
            raise SiestaCommandFactoryError("profile CPU allocation does not match Hydra host placement")
        executable = _verified_absolute_file(profile.runtime.siesta_executable, "SIESTA executable")
        launcher_program = _verified_mpi_launcher(
            profile.runtime.launcher.command, profile.runtime.launcher.kind,
        )
        try:
            admission.require_declared_executable(executable)
        except BackendAdmissionError as exc:
            raise SiestaCommandFactoryError("SIESTA executable differs from backend admission") from exc
        self.profile, self.hosts, self.layout, self.artifacts = profile, tuple(hosts), layout, artifacts
        self.admission = admission
        self.executable = executable
        self.launcher = replace(
            profile.runtime.launcher,
            command=(str(launcher_program),),
        )
        self.bare_profile = bare_profile

    @property
    def required_module_commands(self) -> tuple[str, ...]:
        """For the private allocation wrapper; never executed by this factory."""
        return self.profile.runtime.module_commands

    def command_for(self, node: LRDagNode) -> NodeCommand:
        if node.kind not in {LRNodeKind.REFERENCE, LRNodeKind.PERTURBATION}:
            raise SiestaCommandFactoryError(f"{node.kind.value} is not a materializable SIESTA node")
        try:
            # Re-hash immediately before creating the launch command.  This
            # covers REFERENCE and SCREENED nodes as well as BARE nodes.
            self.admission.require_declared_executable(self.executable)
        except BackendAdmissionError as exc:
            raise SiestaCommandFactoryError("SIESTA executable changed after admission") from exc
        run_dir = (self.layout.run_root / _safe_node_name(node)).resolve()
        if run_dir.exists():
            raise SiestaCommandFactoryError("refusing to overwrite an existing node directory")
        run_dir.mkdir(parents=True, exist_ok=False)
        try:
            self._stage_static_artifacts(run_dir)
            fdf_path = run_dir / self.layout.fdf_name
            if node.kind is LRNodeKind.REFERENCE:
                copy2(self.layout.reference_fdf, fdf_path)
                dm_name = self.layout.reference_dm_name
            else:
                if node.perturbation is None:
                    raise SiestaCommandFactoryError("perturbation node lacks a perturbation specification")
                if self.layout.reference_dm is None:
                    raise SiestaCommandFactoryError("perturbation requires a declared reference DM")
                write_materialized_response(
                    self.layout.reference_fdf, node.perturbation, fdf_path,
                    bare_profile=self.bare_profile, admission=self.admission,
                )
                dm_name = f"{node.perturbation.run_id}.DM"
                copy2(self.layout.reference_dm, run_dir / dm_name)
                # The sidecar contract binds the parent DM explicitly.  Keep a
                # second immutable copy under its declared parent name; the
                # active ``SystemLabel.DM`` copy remains the file SIESTA reads.
                copy2(self.layout.reference_dm, run_dir / self.layout.reference_dm_name)
            self.artifacts[node.node_id] = SiestaArtifactSpec(
                fdf=self.layout.fdf_name,
                output=self.layout.output_name,
                dm=dm_name,
                executable=str(self.executable),
                reference_dm=self.layout.reference_dm_name if node.kind is LRNodeKind.PERTURBATION else None,
            )
            launch = build_mpi_launch(
                self.launcher, list(self.hosts),
                self.profile.allocation.total_cpus, str(self.executable),
            )
            return NodeCommand(
                argv=launch.argv, cwd=run_dir, stdin_path=fdf_path,
                stdout_path=run_dir / self.layout.output_name,
                stderr_path=run_dir / self.layout.error_name,
            )
        except Exception:
            # Preserve forensic material but never leave it eligible for reuse.
            self.artifacts.pop(node.node_id, None)
            raise

    def _stage_static_artifacts(self, run_dir: Path) -> None:
        for destination, source in self.layout.static_artifacts.items():
            target = (run_dir / _relative_name(destination, "static artifact destination")).resolve()
            try:
                target.relative_to(run_dir)
            except ValueError as exc:
                raise SiestaCommandFactoryError("static artifact escapes node directory") from exc
            target.parent.mkdir(parents=True, exist_ok=True)
            copy2(source, target)
