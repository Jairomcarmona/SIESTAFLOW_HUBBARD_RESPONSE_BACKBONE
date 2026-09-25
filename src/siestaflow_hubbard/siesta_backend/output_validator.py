"""Fail-closed validation of one completed SIESTA LR node.

This module is deliberately an output validator, not a launcher.  It accepts
only artifacts declared by the caller and never infers scientific validity
from a process exit code or from a node name.  Site-specific command profiles
and scheduler logic remain outside the backend.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
from subprocess import CompletedProcess
from typing import Mapping

from siestaflow_hubbard.execution.dag_contract import NodeState
from siestaflow_hubbard.execution.generic_executor import NodeReceipt
from siestaflow_hubbard.execution.lr_dag import LRDagNode, LRNodeKind
from siestaflow_hubbard.execution.runtime_adapters import NodeCommand

from .reference_magnetic_evidence import ReferenceMagneticEvidenceError, reference_moments_from_fdf_and_output
from .backend_admission import BackendAdmission, BackendAdmissionError
from .backend_admission_plugin import _is_campaign_contract_admission
from .siesta542_bare_profile import Siesta542BareProfileError, Siesta542PotentialShiftHamiltonianProfile


class SiestaOutputValidationError(ValueError):
    """A completed process did not produce scientifically admissible evidence."""


@dataclass(frozen=True)
class SiestaArtifactSpec:
    """Relative artifacts belonging to one node.

    All paths are relative to ``NodeCommand.cwd``.  Explicit declarations make
    accidental reuse of a neighboring run impossible and keep private cluster
    paths out of the scientific contract.
    """

    fdf: str
    output: str
    dm: str
    executable: str | None = None
    reference_dm: str | None = None


@dataclass(frozen=True)
class SiestaValidationPolicy:
    """Scientific acceptance rules for the scalar collinear LR backend."""

    siesta_version: str = "5.4.2"
    require_reference_magnetic_evidence: bool = True
    require_dm: bool = True
    require_scf_convergence_for_screened: bool = True
    bare_profile: Siesta542PotentialShiftHamiltonianProfile | None = None
    bare_backend_admission: BackendAdmission | None = None


_FAILURE = re.compile(
    r"SCF_NOT_CONV|SCF\s*:\s*not\s+converged|ABNORMAL_TERMINATION|MPI_Abort|pseudo_read:\s*ERROR|FATAL",
    re.IGNORECASE,
)
_NORMAL = re.compile(r">>\s*End of run|siesta:\s*normal completion|^\s*Job completed\s*$", re.IGNORECASE | re.MULTILINE)


def _sha256_bytes(data: bytes) -> str:
    return sha256(data).hexdigest()


def _safe_artifact(cwd: Path, value: str | None, name: str, *, required: bool) -> Path | None:
    if value is None:
        if required:
            raise SiestaOutputValidationError(f"{name} path is required")
        return None
    candidate = Path(value)
    if candidate.is_absolute() or not value or any(part == ".." for part in candidate.parts):
        raise SiestaOutputValidationError(f"{name} must be a relative path inside the node directory")
    resolved = (cwd / candidate).resolve()
    try:
        resolved.relative_to(cwd.resolve())
    except ValueError as exc:
        raise SiestaOutputValidationError(f"{name} escapes the node directory") from exc
    if not resolved.is_file():
        raise SiestaOutputValidationError(f"required {name} artifact is missing")
    if resolved.stat().st_size == 0:
        raise SiestaOutputValidationError(f"required {name} artifact is empty")
    return resolved


def _declared_executable(command: NodeCommand, value: str | None) -> Path:
    """Accept an external executable only when it is the declared argv entry.

    Executables normally live in a module installation outside a run directory,
    unlike scientific artifacts.  The private profile must therefore supply a
    resolved file path, and it must be exactly the executable invoked by Hydra.
    """
    if not isinstance(value, str) or not value:
        raise SiestaOutputValidationError("BARE executable path is required")
    path = Path(value)
    if not path.is_absolute() or not path.is_file():
        raise SiestaOutputValidationError("BARE executable must be an existing absolute profile path")
    if value not in command.argv:
        raise SiestaOutputValidationError("BARE executable is not the executable declared in argv")
    return path.resolve()


def _normal_and_converged(output: str, *, require_convergence: bool, allow_bare_scf_marker: bool = False) -> None:
    failure_pattern = _FAILURE
    if allow_bare_scf_marker:
        # A certified BARE trace may intentionally end with SCF_NOT_CONV:
        # its fixed-Hxc population is not a converged SCREENED solution.  The
        # sidecar still has to prove ordering and normal non-aborted exit.
        failure_pattern = re.compile(
            r"SCF\s*:\s*not\s+converged|ABNORMAL_TERMINATION|MPI_Abort|pseudo_read:\s*ERROR|FATAL",
            re.IGNORECASE,
        )
    if failure_pattern.search(output):
        raise SiestaOutputValidationError("SIESTA output contains an explicit failure or non-converged SCF marker")
    if not _NORMAL.search(output):
        raise SiestaOutputValidationError("SIESTA output has no certified normal-termination marker")
    if require_convergence and re.search(r"SCF\s*:\s*not\s+converged|SCF_NOT_CONV", output, re.IGNORECASE):
        raise SiestaOutputValidationError("SCREENED node lacks converged SCF evidence")


class SiestaOutputValidator:
    """Validate one SIESTA node and return a provenance-bearing receipt.

    The validator supports the currently certified scalar/collinear route only.
    Unknown node kinds, modes, sidecar schemas, and artifact layouts are
    rejected rather than approximated.
    """

    def __init__(
        self,
        artifacts: Mapping[str, SiestaArtifactSpec],
        *,
        policy: SiestaValidationPolicy | None = None,
    ):
        # A command factory may populate a mutable registry immediately before
        # execution.  Retain a concrete dict by reference for that narrowly
        # defined hand-off; other Mapping implementations are copied.
        self.artifacts = artifacts if isinstance(artifacts, dict) else dict(artifacts)
        self.policy = policy or SiestaValidationPolicy()
        self.last_provenance: dict[str, object] | None = None

    def _require_campaign_admission(self, command: NodeCommand, spec: SiestaArtifactSpec) -> None:
        admission = self.policy.bare_backend_admission
        if admission is None or not _is_campaign_contract_admission(admission):
            raise SiestaOutputValidationError(
                "production SIESTA validation requires admission from a campaign contract"
            )
        profile = self.policy.bare_profile
        if (
            profile is None
            or admission.scientific_profile.key != (profile.profile_id, profile.profile_version)
            or admission.observed.version != self.policy.siesta_version
        ):
            raise SiestaOutputValidationError(
                "production SIESTA validation requires the admission-bound current scientific profile"
            )
        if not (
            self.policy.require_reference_magnetic_evidence
            and self.policy.require_dm
            and self.policy.require_scf_convergence_for_screened
        ):
            raise SiestaOutputValidationError(
                "production SIESTA validation policy cannot weaken scientific acceptance"
            )
        executable = _declared_executable(command, spec.executable)
        try:
            admission.require_declared_executable(executable)
        except BackendAdmissionError as exc:
            raise SiestaOutputValidationError(
                "declared executable differs from admitted backend"
            ) from exc

    def _require_command_artifact_binding(self, command: NodeCommand, spec: SiestaArtifactSpec) -> None:
        cwd = command.cwd.resolve()
        for label, declared, command_path in (
            ("FDF", spec.fdf, command.stdin_path),
            ("SIESTA output", spec.output, command.stdout_path),
        ):
            if command_path is None:
                raise SiestaOutputValidationError(f"production command lacks declared {label} path")
            candidate = Path(declared)
            if candidate.is_absolute() or not declared or any(part == ".." for part in candidate.parts):
                raise SiestaOutputValidationError(f"{label} must be a relative path inside the node directory")
            if command_path.resolve() != (cwd / candidate).resolve():
                raise SiestaOutputValidationError(
                    f"declared {label} does not match the command artifact path"
                )

    def validate(self, node: LRDagNode, command: NodeCommand, completed: CompletedProcess[str]) -> NodeReceipt:
        if node.node_id not in self.artifacts:
            raise SiestaOutputValidationError(f"no artifact contract declared for node {node.node_id}")
        if node.kind not in (LRNodeKind.REFERENCE, LRNodeKind.PERTURBATION):
            raise SiestaOutputValidationError(f"node kind {node.kind.value} is not a SIESTA execution node")

        spec = self.artifacts[node.node_id]
        # This applies before branch-specific semantics to REFERENCE,
        # SCREENED, and BARE alike.
        self._require_campaign_admission(command, spec)
        self._require_command_artifact_binding(command, spec)
        if completed.returncode != 0:
            return NodeReceipt(node.node_id, NodeState.FAILED_OUTPUT_VALIDATION, self._digest(node, command, {"returncode": completed.returncode}))
        cwd = command.cwd.resolve()
        fdf = _safe_artifact(cwd, spec.fdf, "FDF", required=True)
        output_path = _safe_artifact(cwd, spec.output, "SIESTA output", required=True)
        dm = _safe_artifact(cwd, spec.dm, "DM", required=self.policy.require_dm)
        assert fdf is not None and output_path is not None
        output = output_path.read_text(encoding="utf-8", errors="replace")
        if node.kind is LRNodeKind.PERTURBATION and node.perturbation is None:
            raise SiestaOutputValidationError("perturbation node has no perturbation specification")
        is_bare = (
            node.kind is LRNodeKind.PERTURBATION
            and getattr(node.perturbation.mode, "value", node.perturbation.mode) == "BARE"
        )
        _normal_and_converged(
            output,
            require_convergence=False,
            allow_bare_scf_marker=is_bare,
        )

        semantic: dict[str, object] = {"node_kind": node.kind.value}
        if node.kind is LRNodeKind.REFERENCE:
            if self.policy.require_reference_magnetic_evidence:
                try:
                    moments, parser = reference_moments_from_fdf_and_output(
                        fdf.read_text(encoding="utf-8", errors="replace"), output
                    )
                except (ReferenceMagneticEvidenceError, ValueError) as exc:
                    raise SiestaOutputValidationError(f"reference magnetic evidence rejected: {exc}") from exc
                semantic.update({"magnetic_parser": parser, "atom_count": int(len(moments))})
        else:
            mode_value = getattr(node.perturbation.mode, "value", node.perturbation.mode)
            mode = str(mode_value).upper()
            if mode not in {"BARE", "SCREENED"}:
                raise SiestaOutputValidationError(f"unsupported LR mode {mode}; only BARE and SCREENED are certified")
            semantic["response_mode"] = mode
            reference_dm = _safe_artifact(cwd, spec.reference_dm, "reference DM", required=True)
            assert reference_dm is not None
            semantic["reference_dm_sha256"] = _sha256_bytes(reference_dm.read_bytes())
            if mode == "SCREENED":
                _normal_and_converged(output, require_convergence=self.policy.require_scf_convergence_for_screened)
            elif mode == "BARE":
                if self.policy.bare_profile is None or self.policy.bare_backend_admission is None:
                    raise SiestaOutputValidationError(
                        "BARE profile evidence rejected: current profile and backend admission are required"
                    )
                if not _is_campaign_contract_admission(self.policy.bare_backend_admission):
                    raise SiestaOutputValidationError(
                        "BARE profile evidence rejected: admission must come from a campaign contract"
                    )
                executable = _declared_executable(command, spec.executable)
                try:
                    self.policy.bare_backend_admission.require_declared_executable(executable)
                    if self.policy.bare_backend_admission.observed.version != self.policy.siesta_version:
                        raise BackendAdmissionError("policy version differs from admitted backend")
                    self.policy.bare_profile.validate_fdf(fdf.read_text(encoding="utf-8", errors="replace"))
                    selection = self.policy.bare_profile.select_response(output)
                except (BackendAdmissionError, Siesta542BareProfileError) as exc:
                    raise SiestaOutputValidationError(
                        "BARE profile evidence rejected: {0}".format(exc)
                    ) from exc
                semantic.update({
                    "bare_profile": self.policy.bare_profile.profile_id,
                    "bare_response_occurrence": selection.response_event.occurrence_index,
                    "bare_parent_occurrence": selection.pre_perturbation_event.occurrence_index,
                })

        files: dict[str, str] = {}
        for label, path in (("fdf", fdf), ("output", output_path), ("dm", dm)):
            if path is not None:
                files[label] = _sha256_bytes(path.read_bytes())
        provenance = {
            "schema": "siestaflow-siesta-node-evidence-v1",
            "node_id": node.node_id,
            "node": asdict(node),
            "artifacts": files,
            "semantic": semantic,
        }
        digest = self._digest(node, command, provenance)
        self.last_provenance = {**provenance, "evidence_digest": digest}
        return NodeReceipt(node.node_id, NodeState.VALIDATED, digest)

    @staticmethod
    def _event_lines(output: str) -> tuple[int, int]:
        lines = output.splitlines()
        indices = [i + 1 for i, line in enumerate(lines) if "hubbard_term" in line.lower()]
        if not indices:
            raise SiestaOutputValidationError("BARE output contains no Hubbard population event")
        return min(indices), max(indices)

    @staticmethod
    def _digest(node: LRDagNode, command: NodeCommand, payload: object) -> str:
        encoded = json.dumps(
            {"node_id": node.node_id, "argv": list(command.argv), "payload": payload},
            sort_keys=True, separators=(",", ":"), default=str,
        ).encode()
        return _sha256_bytes(encoded)
