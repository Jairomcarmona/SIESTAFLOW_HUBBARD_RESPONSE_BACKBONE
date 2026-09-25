import json
from pathlib import Path

import pytest

from siestaflow_hubbard.domain.backend_compatibility import ScientificProfile
from siestaflow_hubbard.domain.lr_campaign_contract import LinearResponseBareCampaignContract
from siestaflow_hubbard.execution.execution_profile import ExecutionProfile
from siestaflow_hubbard.execution.lr_dag import LRDagNode, LRNodeKind
from siestaflow_hubbard.execution.runtime_adapters import NodeCommand
from siestaflow_hubbard.domain.symmetry_reduction import PerturbationSpec, ResponseMode
from siestaflow_hubbard.siesta_backend.backend_identity import sha256_file
from siestaflow_hubbard.siesta_backend.command_factory import SiestaCampaignLayout
from siestaflow_hubbard.siesta_backend.production_runtime import (
    AdmittedSiestaRuntime,
    SiestaProductionRuntimeError,
    build_admitted_siesta542_runtime,
)
from siestaflow_hubbard.siesta_backend.output_validator import SiestaOutputValidator, SiestaValidationPolicy
from siestaflow_hubbard.siesta_backend.siesta542_bare_profile import (
    Siesta542PotentialShiftHamiltonianProfile,
)


def _profile(executable: Path, launcher_command: list[str] | None = None) -> ExecutionProfile:
    launcher = executable.parent / "mpiexec.hydra"
    if not launcher.exists():
        launcher.write_bytes(b"hydra launcher")
    return ExecutionProfile.from_mapping({
        "target": "slurm", "evidence": "VALIDATED_RUNTIME",
        "slurm": {"partition": "private", "account": None, "qos": None},
        "allocation": {"nodes": 1, "total_cpus": 2, "memory": "private", "walltime": "private",
                       "max_parallel_steps": 1, "shutdown_margin_seconds": 60, "termination_grace_seconds": 30},
        "runtime": {"module_commands": ["private wrapper supplies modules"], "siesta_executable": str(executable),
                    "exclusive": True, "environment": {},
                    "launcher": {"kind": "hydra", "command": launcher_command or [str(launcher)], "bootstrap": "ssh", "processes_per_node": 2}},
        "task_policy": {"max_attempts": 1, "require_scf_converged": True},
    })


def _openmpi_profile(executable: Path, launcher: Path) -> ExecutionProfile:
    return ExecutionProfile.from_mapping({
        "target": "slurm", "evidence": "VALIDATED_RUNTIME",
        "slurm": {"partition": "local", "account": None, "qos": None},
        "allocation": {"nodes": 1, "total_cpus": 4, "memory": "1G", "walltime": "00:05:00",
                       "max_parallel_steps": 1, "shutdown_margin_seconds": 60, "termination_grace_seconds": 30},
        "runtime": {"module_commands": [], "siesta_executable": str(executable),
                    "exclusive": True, "environment": {},
                    "launcher": {"kind": "openmpi", "command": [str(launcher)],
                    "bootstrap": "ssh", "processes_per_node": 4}},
        "task_policy": {"max_attempts": 1, "require_scf_converged": True},
    })


def _fdf(path: Path) -> None:
    path.write_text(
        "SystemLabel reference\nNumberOfAtoms 1\nDFTU.ProjectorGenerationMethod 2\n"
        "DFTU.PotentialShift true\n%block DFTU.Proj\nM0 1\n3 2\n  0.0000 0.0000\n"
        " 3.0 0.05\n%endblock DFTU.Proj\n",
        encoding="utf-8",
    )


def _contract_files(root: Path, executable: Path, *, registered: Path | None = None) -> LinearResponseBareCampaignContract:
    profile = Siesta542PotentialShiftHamiltonianProfile()
    private = root / "private"; private.mkdir()
    digest = sha256_file(registered or executable)
    (private / "backend.json").write_text(json.dumps({
        "schema": "backend_compatibility_v1", "records": [{
            "backend": {"backend_id": "siesta", "version": "5.4.2", "executable_sha256": digest},
            "profile": {"profile_id": profile.profile_id, "version": profile.profile_version,
                        "metadata": {"source_revision": profile.source_revision}},
            "state": "compatible", "reason": "test fixture",
        }],
    }), encoding="utf-8")
    (private / "version.txt").write_text("SIESTA Version : 5.4.2\n", encoding="utf-8")
    return LinearResponseBareCampaignContract(
        campaign_id="fixture", scientific_profile=ScientificProfile(profile.profile_id, profile.profile_version),
        compatibility_registry="private/backend.json", declared_executable=executable.name,
        version_text_source="private/version.txt",
    )


def _layout(root: Path) -> SiestaCampaignLayout:
    fdf = root / "reference.fdf"; _fdf(fdf)
    dm = root / "reference.DM"; dm.write_bytes(b"dm")
    return SiestaCampaignLayout(fdf, root / "runs", dm, "reference.DM")


def test_admitted_runtime_allows_factory_only_after_exact_admission(tmp_path: Path):
    executable = tmp_path / "siesta"; executable.write_bytes(b"known backend")
    runtime = build_admitted_siesta542_runtime(
        campaign_root=tmp_path, contract=_contract_files(tmp_path, executable), executable_path=executable,
        profile=_profile(executable), hosts=["host-a"], layout=_layout(tmp_path),
    )
    command = runtime.factory.command_for(LRDagNode("reference", LRNodeKind.REFERENCE, ()))
    assert command.cwd.is_dir()
    assert runtime.admission.observed.version == "5.4.2"
    assert command.argv[-1] == str(executable.resolve())


def test_admitted_runtime_accepts_an_explicit_direct_openmpi_launcher(tmp_path: Path):
    executable = tmp_path / "siesta"; executable.write_bytes(b"known backend")
    launcher = tmp_path / "orterun"; launcher.write_bytes(b"openmpi launcher")
    runtime = build_admitted_siesta542_runtime(
        campaign_root=tmp_path, contract=_contract_files(tmp_path, executable), executable_path=executable,
        profile=_openmpi_profile(executable, launcher), hosts=["host-a"], layout=_layout(tmp_path),
    )
    command = runtime.factory.command_for(LRDagNode("reference", LRNodeKind.REFERENCE, ()))
    assert command.argv[:7] == (
        str(launcher.resolve()), "--host", "host-a:4", "--map-by", "ppr:4:node", "-np", "4",
    )


def test_relative_launcher_is_rejected_before_admission(tmp_path: Path):
    executable = tmp_path / "siesta"; executable.write_bytes(b"known backend")
    profile = ExecutionProfile.from_mapping({
        "target": "slurm", "evidence": "VALIDATED_RUNTIME",
        "slurm": {"partition": "private", "account": None, "qos": None},
        "allocation": {"nodes": 1, "total_cpus": 2, "memory": "private", "walltime": "private",
                       "max_parallel_steps": 1, "shutdown_margin_seconds": 60, "termination_grace_seconds": 30},
        "runtime": {"module_commands": [], "siesta_executable": str(executable), "exclusive": True,
                    "environment": {}, "launcher": {"kind": "hydra", "command": ["mpiexec.hydra"],
                    "bootstrap": "ssh", "processes_per_node": 2}},
        "task_policy": {"max_attempts": 1, "require_scf_converged": True},
    })
    with pytest.raises(SiestaProductionRuntimeError, match="Hydra launcher"):
        build_admitted_siesta542_runtime(
            campaign_root=tmp_path, contract=_contract_files(tmp_path, executable), executable_path=executable,
            profile=profile, hosts=["host-a"], layout=_layout(tmp_path),
        )


def test_changed_executable_is_rejected_before_each_node_materialization(tmp_path: Path):
    executable = tmp_path / "siesta"; executable.write_bytes(b"known backend")
    layout = _layout(tmp_path)
    runtime = build_admitted_siesta542_runtime(
        campaign_root=tmp_path, contract=_contract_files(tmp_path, executable), executable_path=executable,
        profile=_profile(executable), hosts=["host-a"], layout=layout,
    )
    executable.write_bytes(b"replaced backend")
    with pytest.raises(Exception, match="changed after admission"):
        runtime.factory.command_for(LRDagNode("reference", LRNodeKind.REFERENCE, ()))
    assert not layout.run_root.exists()


@pytest.mark.parametrize("launcher_name, launcher_args", [("sh", ["-c", "echo unsafe"]), ("cmd.exe", ["/c", "echo unsafe"]), ("powershell.exe", ["-Command", "echo unsafe"])])
def test_interpreter_launcher_is_rejected_before_node_materialization(
    tmp_path: Path, launcher_name: str, launcher_args: list[str],
):
    executable = tmp_path / "siesta"; executable.write_bytes(b"known backend")
    interpreter = tmp_path / launcher_name; interpreter.write_bytes(b"interpreter")
    layout = _layout(tmp_path)
    with pytest.raises(Exception, match="Hydra launcher|mpiexec.hydra"):
        build_admitted_siesta542_runtime(
            campaign_root=tmp_path, contract=_contract_files(tmp_path, executable), executable_path=executable,
            profile=_profile(executable, [str(interpreter), *launcher_args]), hosts=["host-a"], layout=layout,
        )
    assert not layout.run_root.exists()


def test_admitted_runtime_materializes_bare_only_with_its_current_profile(tmp_path: Path):
    executable = tmp_path / "siesta"; executable.write_bytes(b"known backend")
    runtime = build_admitted_siesta542_runtime(
        campaign_root=tmp_path, contract=_contract_files(tmp_path, executable), executable_path=executable,
        profile=_profile(executable), hosts=["host-a"], layout=_layout(tmp_path),
    )
    node = LRDagNode(
        "response:bare", LRNodeKind.PERTURBATION, ("reference",),
        PerturbationSpec("bare", "orbit", 0, "M0", ResponseMode.BARE, 0.05, "representative"),
    )
    command = runtime.factory.command_for(node)
    fdf = command.stdin_path.read_text(encoding="utf-8")
    assert "MaxSCFIterations 1" in fdf
    assert "SCF.Mix hamiltonian" in fdf
    assert runtime.validator.policy.bare_backend_admission == runtime.admission


def test_runtime_rejects_a_weakened_validator_policy(tmp_path: Path):
    executable = tmp_path / "siesta"; executable.write_bytes(b"known backend")
    runtime = build_admitted_siesta542_runtime(
        campaign_root=tmp_path, contract=_contract_files(tmp_path, executable), executable_path=executable,
        profile=_profile(executable), hosts=["host-a"], layout=_layout(tmp_path),
    )
    weak = SiestaOutputValidator(runtime.factory.artifacts, policy=SiestaValidationPolicy(
        siesta_version=runtime.admission.observed.version,
        require_reference_magnetic_evidence=False,
        bare_profile=runtime.factory.bare_profile,
        bare_backend_admission=runtime.admission,
    ))
    with pytest.raises(SiestaProductionRuntimeError, match="cannot weaken"):
        AdmittedSiestaRuntime(runtime.admission, runtime.factory, weak)


def test_runtime_rejects_factory_and_validator_with_different_artifact_registries(tmp_path: Path):
    executable = tmp_path / "siesta"; executable.write_bytes(b"known backend")
    runtime = build_admitted_siesta542_runtime(
        campaign_root=tmp_path, contract=_contract_files(tmp_path, executable), executable_path=executable,
        profile=_profile(executable), hosts=["host-a"], layout=_layout(tmp_path),
    )
    other_registry = {}
    validator = SiestaOutputValidator(other_registry, policy=runtime.validator.policy)
    with pytest.raises(SiestaProductionRuntimeError, match="artifact registry"):
        AdmittedSiestaRuntime(runtime.admission, runtime.factory, validator)


def test_production_validator_rejects_artifact_paths_not_bound_to_the_command(tmp_path: Path):
    executable = tmp_path / "siesta"; executable.write_bytes(b"known backend")
    runtime = build_admitted_siesta542_runtime(
        campaign_root=tmp_path, contract=_contract_files(tmp_path, executable), executable_path=executable,
        profile=_profile(executable), hosts=["host-a"], layout=_layout(tmp_path),
    )
    node = LRDagNode("reference", LRNodeKind.REFERENCE, ())
    command = runtime.factory.command_for(node)
    mismatched = NodeCommand(
        command.argv, command.cwd, stdin_path=command.stdin_path,
        stdout_path=command.cwd / "alternate.out", stderr_path=command.stderr_path,
    )
    with pytest.raises(Exception, match="does not match the command artifact path"):
        runtime.validator.validate(node, mismatched, type("Done", (), {"returncode": 0})())


def test_rejected_hash_creates_no_run_directory_and_exposes_no_executor(tmp_path: Path):
    executable = tmp_path / "siesta"; executable.write_bytes(b"unknown backend")
    registered = tmp_path / "registered-siesta"; registered.write_bytes(b"known backend")
    layout = _layout(tmp_path)
    with pytest.raises(SiestaProductionRuntimeError, match="admission rejected"):
        build_admitted_siesta542_runtime(
            campaign_root=tmp_path, contract=_contract_files(tmp_path, executable, registered=registered),
            executable_path=executable, profile=_profile(executable), hosts=["host-a"], layout=layout,
        )
    assert not layout.run_root.exists()


def test_profile_launch_target_mismatch_blocks_before_backend_admission(tmp_path: Path):
    executable = tmp_path / "siesta"; executable.write_bytes(b"known backend")
    other = tmp_path / "other-siesta"; other.write_bytes(b"other backend")
    layout = _layout(tmp_path)
    with pytest.raises(SiestaProductionRuntimeError, match="execution profile executable differs"):
        build_admitted_siesta542_runtime(
            campaign_root=tmp_path, contract=_contract_files(tmp_path, executable), executable_path=executable,
            profile=_profile(other), hosts=["host-a"], layout=layout,
        )
    assert not layout.run_root.exists()


def test_version_mismatch_blocks_before_run_materialization(tmp_path: Path):
    executable = tmp_path / "siesta"; executable.write_bytes(b"known backend")
    layout = _layout(tmp_path)
    contract = _contract_files(tmp_path, executable)
    (tmp_path / "private" / "version.txt").write_text(
        "SIESTA Version : 5.4.1\n", encoding="utf-8"
    )
    with pytest.raises(SiestaProductionRuntimeError, match="admission rejected"):
        build_admitted_siesta542_runtime(
            campaign_root=tmp_path, contract=contract, executable_path=executable,
            profile=_profile(executable), hosts=["host-a"], layout=layout,
        )
    assert not layout.run_root.exists()


def test_missing_registry_blocks_before_run_materialization(tmp_path: Path):
    executable = tmp_path / "siesta"; executable.write_bytes(b"known backend")
    layout = _layout(tmp_path)
    contract = _contract_files(tmp_path, executable)
    (tmp_path / "private" / "backend.json").unlink()
    with pytest.raises(SiestaProductionRuntimeError, match="admission rejected"):
        build_admitted_siesta542_runtime(
            campaign_root=tmp_path, contract=contract, executable_path=executable,
            profile=_profile(executable), hosts=["host-a"], layout=layout,
        )
    assert not layout.run_root.exists()


def test_malformed_registry_blocks_before_run_materialization(tmp_path: Path):
    executable = tmp_path / "siesta"; executable.write_bytes(b"known backend")
    layout = _layout(tmp_path)
    contract = _contract_files(tmp_path, executable)
    (tmp_path / "private" / "backend.json").write_text("{not-json", encoding="utf-8")
    with pytest.raises(SiestaProductionRuntimeError, match="admission rejected"):
        build_admitted_siesta542_runtime(
            campaign_root=tmp_path, contract=contract, executable_path=executable,
            profile=_profile(executable), hosts=["host-a"], layout=layout,
        )
    assert not layout.run_root.exists()


def test_logical_executable_mismatch_blocks_before_run_materialization(tmp_path: Path):
    executable = tmp_path / "siesta"; executable.write_bytes(b"known backend")
    layout = _layout(tmp_path)
    contract = _contract_files(tmp_path, executable)
    contract = LinearResponseBareCampaignContract(
        campaign_id=contract.campaign_id,
        scientific_profile=contract.scientific_profile,
        compatibility_registry=contract.compatibility_registry,
        declared_executable="different-siesta",
        version_text_source=contract.version_text_source,
    )
    with pytest.raises(SiestaProductionRuntimeError, match="admission rejected"):
        build_admitted_siesta542_runtime(
            campaign_root=tmp_path, contract=contract, executable_path=executable,
            profile=_profile(executable), hosts=["host-a"], layout=layout,
        )
    assert not layout.run_root.exists()
