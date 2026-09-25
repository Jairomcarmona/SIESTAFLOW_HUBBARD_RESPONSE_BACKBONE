import pytest

from siestaflow_hubbard.execution import (
    EvidenceLevel, ExecutionProfile, NodeState, ProfileValidationError,
    SlurmEnvironment, build_hydra_launch, build_mpi_launch, may_analyze, may_start,
)


def profile_payload(evidence="VALIDATED_RUNTIME"):
    return {
        "target": "slurm", "evidence": evidence,
        "slurm": {"partition": "private-profile-value", "account": None, "qos": None},
        "allocation": {"nodes": 2, "total_cpus": 8, "memory": "site-defined", "walltime": "site-defined", "max_parallel_steps": 2, "shutdown_margin_seconds": 60, "termination_grace_seconds": 30},
        "runtime": {"module_commands": ["site-defined"], "siesta_executable": "site-defined", "exclusive": True, "environment": {"OMP_NUM_THREADS": "1"}, "launcher": {"kind": "hydra", "command": ["mpiexec.hydra"], "bootstrap": "ssh", "processes_per_node": 2}},
        "task_policy": {"max_attempts": 1, "require_scf_converged": True},
    }


def test_profile_requires_complete_runtime_and_validated_evidence():
    profile = ExecutionProfile.from_mapping(profile_payload())
    profile.require_submission_evidence()
    with pytest.raises(ProfileValidationError):
        ExecutionProfile.from_mapping(profile_payload("OBSERVED")).require_submission_evidence()
    bad = profile_payload(); bad["runtime"]["launcher"].pop("processes_per_node")
    with pytest.raises(ProfileValidationError): ExecutionProfile.from_mapping(bad)


def test_granted_slurm_environment_must_match_profile_and_hosts():
    profile = ExecutionProfile.from_mapping(profile_payload())
    env = SlurmEnvironment.from_environ({"SLURM_JOB_ID":"opaque", "SLURM_SUBMIT_DIR":"relative-root", "SLURM_JOB_END_TIME":"opaque", "SLURM_NNODES":"2", "SLURM_NTASKS":"8", "SLURM_CPUS_PER_TASK":"1", "SLURM_JOB_NODELIST":"opaque"})
    env.validate_profile(profile, ["host-a", "host-b"])
    with pytest.raises(ProfileValidationError): env.validate_profile(profile, ["host-a"])


def test_hydra_placement_is_exact_and_gets_fresh_uuid():
    launcher = ExecutionProfile.from_mapping(profile_payload()).runtime.launcher
    first = build_hydra_launch(launcher, ["host-a", "host-b"], 4, "siesta")
    second = build_hydra_launch(launcher, ["host-a", "host-b"], 4, "siesta")
    assert first.uuid != second.uuid and "-bootstrap" in first.argv and "-ppn" in first.argv
    with pytest.raises(ProfileValidationError): build_hydra_launch(launcher, ["host-a", "host-b"], 2, "siesta")


def test_openmpi_placement_uses_provider_specific_arguments():
    payload = profile_payload()
    payload["runtime"]["launcher"].update({
        "kind": "openmpi", "command": ["/usr/bin/orterun"],
    })
    launcher = ExecutionProfile.from_mapping(payload).runtime.launcher
    launch = build_mpi_launch(launcher, ["host-a", "host-b"], 4, "/opt/siesta")
    assert launch.argv == (
        "/usr/bin/orterun", "--host", "host-a:2,host-b:2", "--map-by", "ppr:2:node",
        "-np", "4", "/opt/siesta",
    )


def test_dag_refuses_partial_or_failed_scientific_descendants():
    assert may_start([NodeState.VALIDATED])
    assert not may_start([NodeState.FAILED_SCIENCE])
    assert may_analyze([NodeState.VALIDATED, NodeState.VALIDATED])
    assert not may_analyze([NodeState.VALIDATED, NodeState.FAILED_OUTPUT_VALIDATION])
