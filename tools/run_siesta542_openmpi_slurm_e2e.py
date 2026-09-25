#!/usr/bin/env python3
"""Run a small canonical SIESTA 5.4.2 BARE integration inside Slurm."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import traceback

from siestaflow_hubbard.domain.backend_compatibility import ScientificProfile
from siestaflow_hubbard.domain.lr_campaign_contract import LinearResponseBareCampaignContract
from siestaflow_hubbard.domain.symmetry_reduction import PerturbationSpec, ResponseMode
from siestaflow_hubbard.execution.execution_profile import ExecutionProfile
from siestaflow_hubbard.execution.generic_executor import GenericDagExecutor
from siestaflow_hubbard.execution.lr_dag import LRDag, LRDagNode, LRNodeKind
from siestaflow_hubbard.execution.runtime_adapters import SlurmAllocationExecutor
from siestaflow_hubbard.siesta_backend.backend_identity import sha256_file
from siestaflow_hubbard.siesta_backend.command_factory import SiestaCampaignLayout
from siestaflow_hubbard.siesta_backend.production_runtime import build_admitted_siesta542_runtime
from siestaflow_hubbard.siesta_backend.siesta542_bare_profile import (
    Siesta542PotentialShiftHamiltonianProfile,
)


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs" / "evidence" / "siesta542_openmpi_slurm_e2e_20260920_run3_wheel"
SIESTA = Path("/home/jmc/.local/siesta-5.4.2-openmpi/bin/siesta")
MPI = Path("/usr/bin/orterun")
TEMPLATE = ROOT / "examples" / "tmo_campaigns" / "test_rc.fdf"
PSEUDO = ROOT / "examples" / "tmo_campaigns" / "Cu1.psml"


def _json_default(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    return str(value)


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=_json_default) + "\n",
        encoding="utf-8",
    )


def checked(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, check=True, text=True, capture_output=True)


class RecordingFactory:
    def __init__(self, delegate: object, records: list[dict[str, object]]):
        self.delegate = delegate
        self.records = records

    def command_for(self, node: LRDagNode):
        command = self.delegate.command_for(node)
        self.records.append({
            "node_id": node.node_id,
            "argv": list(command.argv),
            "cwd": str(command.cwd),
            "stdin_path": str(command.stdin_path) if command.stdin_path else None,
            "stdout_path": str(command.stdout_path) if command.stdout_path else None,
            "stderr_path": str(command.stderr_path) if command.stderr_path else None,
            "stdin_sha256_before_execution": (
                sha256_file(command.stdin_path) if command.stdin_path else None
            ),
        })
        return command


def reference_fdf() -> str:
    """Adapt the repository's smallest real Cu load to the admitted method-2 profile."""
    original = TEMPLATE.read_text(encoding="utf-8")
    header = original.split("%block DFTU.proj", 1)[0]
    header = header.replace("SystemLabel         cu_test", "SystemLabel         E2E_REFERENCE")
    header = header.replace("PAO.BasisSize       DZP", "PAO.BasisSize       SZ")
    header = header.replace("MeshCutoff          300.0 Ry", "MeshCutoff          100.0 Ry")
    header = header.replace("MaxSCFIterations    1", "MaxSCFIterations    100")
    return header.rstrip() + """

Spin non-polarized
OccupationFunction FD
ElectronicTemperature 300 K
SCF.Mix Hamiltonian
SCF.MustConverge true
DM.MixingWeight 0.10
DM.NumberPulay 4
WriteDM true
WriteMullikenPop 1
DFTU.ProjectorGenerationMethod 2
DFTU.PotentialShift true
%block DFTU.Proj
  Cu1 1
  3 2
  +0.0000 0.0000
  3.0000 0.0500
%endblock DFTU.Proj
"""


def profile(host: str) -> ExecutionProfile:
    del host
    return ExecutionProfile.from_mapping({
        "target": "slurm",
        "evidence": "VALIDATED_RUNTIME",
        "slurm": {"partition": "local", "account": None, "qos": None},
        "allocation": {
            "nodes": 1,
            "total_cpus": 4,
            "memory": "1G",
            "walltime": "00:10:00",
            "max_parallel_steps": 1,
            "shutdown_margin_seconds": 60,
            "termination_grace_seconds": 30,
        },
        "runtime": {
            "module_commands": [],
            "siesta_executable": str(SIESTA),
            "exclusive": True,
            "environment": {"OMP_NUM_THREADS": "1"},
            "launcher": {
                "kind": "openmpi",
                "command": [str(MPI)],
                "bootstrap": "ssh",
                "processes_per_node": 4,
            },
        },
        "task_policy": {"max_attempts": 1, "require_scf_converged": True},
    })


def main() -> int:
    if EVIDENCE.exists():
        raise SystemExit(f"refusing to reuse existing evidence directory: {EVIDENCE}")
    EVIDENCE.mkdir(parents=True)
    commands: list[dict[str, object]] = []
    result: dict[str, object] = {
        "schema": "siestaflow-canonical-e2e-v1",
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "status": "RUNNING",
        "route": [
            "LinearResponseBareCampaignContract",
            "admit_siesta542_from_campaign_contract",
            "build_admitted_siesta542_runtime",
            "SiestaCommandFactory",
            "SiestaOutputValidator",
            "GenericDagExecutor",
            "SlurmAllocationExecutor",
        ],
    }
    write_json(EVIDENCE / "result.json", result)
    try:
        required = (SIESTA, MPI, TEMPLATE, PSEUDO)
        missing = [str(path) for path in required if not path.is_file()]
        if missing:
            raise RuntimeError("missing required files: " + ", ".join(missing))
        required_slurm = (
            "SLURM_JOB_ID", "SLURM_JOB_NUM_NODES", "SLURM_NTASKS",
            "SLURM_CPUS_PER_TASK", "SLURM_JOB_NODELIST",
        )
        missing_slurm = [name for name in required_slurm if not os.environ.get(name)]
        if missing_slurm:
            raise RuntimeError("must run inside a Slurm allocation: " + ", ".join(missing_slurm))

        host = socket.gethostname()
        version = checked([str(SIESTA), "--version"])
        version_text = version.stdout + version.stderr
        mpi_version = checked([str(MPI), "--version"])
        mpi_smoke = checked([
            str(MPI), "--host", f"{host}:4", "--map-by", "ppr:4:node",
            "-np", "4", "/bin/hostname",
        ])
        smoke_hosts = [line.strip() for line in mpi_smoke.stdout.splitlines() if line.strip()]
        if smoke_hosts != [host] * 4:
            raise RuntimeError(f"unexpected MPI placement: {smoke_hosts!r}")

        identity = {
            "executable": str(SIESTA.resolve()),
            "sha256": sha256_file(SIESTA),
            "size": SIESTA.stat().st_size,
            "version_output": version_text,
            "mpi_launcher": str(MPI.resolve()),
            "mpi_version_output": mpi_version.stdout + mpi_version.stderr,
            "mpi_smoke_hosts": smoke_hosts,
            "hydra_available": False,
        }
        write_json(EVIDENCE / "environment" / "identity.json", identity)
        write_json(EVIDENCE / "environment" / "slurm.json", {
            key: value for key, value in sorted(os.environ.items()) if key.startswith("SLURM_")
        })

        inputs = EVIDENCE / "inputs"
        inputs.mkdir()
        staged_fdf = inputs / "reference.fdf"
        staged_fdf.write_text(reference_fdf(), encoding="utf-8", newline="\n")
        write_json(inputs / "source_manifest.json", {
            "selection": "smallest repository load with one atom and an existing real Cu PSML",
            "template": str(TEMPLATE),
            "template_sha256": sha256_file(TEMPLATE),
            "pseudopotential": str(PSEUDO),
            "pseudopotential_sha256": sha256_file(PSEUDO),
            "staged_reference_fdf_sha256": sha256_file(staged_fdf),
        })

        bare_profile = Siesta542PotentialShiftHamiltonianProfile()
        contracts = EVIDENCE / "contracts"
        contracts.mkdir()
        version_path = contracts / "siesta-version.txt"
        version_path.write_text(version_text, encoding="utf-8")
        registry_path = contracts / "backend-compatibility.json"
        write_json(registry_path, {
            "schema": "backend_compatibility_v1",
            "records": [{
                "backend": {
                    "backend_id": "siesta",
                    "version": "5.4.2",
                    "executable_sha256": identity["sha256"],
                },
                "profile": {
                    "profile_id": bare_profile.profile_id,
                    "version": bare_profile.profile_version,
                    "metadata": {"source_revision": bare_profile.source_revision},
                },
                "state": "compatible",
                "reason": "exact local WSL executable registered for controlled canonical E2E",
            }],
        })
        contract = LinearResponseBareCampaignContract(
            campaign_id="siesta542-openmpi-slurm-e2e-20260920",
            scientific_profile=ScientificProfile(
                bare_profile.profile_id, bare_profile.profile_version,
            ),
            compatibility_registry="contracts/backend-compatibility.json",
            declared_executable="siesta",
            version_text_source="contracts/siesta-version.txt",
        )
        write_json(contracts / "campaign-contract.json", contract.to_dict())
        execution_profile = profile(host)
        write_json(contracts / "execution-profile.json", asdict(execution_profile))

        reference = LRDagNode("reference", LRNodeKind.REFERENCE, ())
        perturbation = PerturbationSpec(
            "E2E_BARE_P0p05", "orbit_000", 0, "Cu1",
            ResponseMode.BARE, 0.05, "representative_e2e",
        )
        bare = LRDagNode(
            "response:E2E_BARE_P0p05", LRNodeKind.PERTURBATION,
            (reference.node_id,), perturbation,
        )
        screened_spec = PerturbationSpec(
            "E2E_SCREENED_P0p05", "orbit_000", 0, "Cu1",
            ResponseMode.SCREENED, 0.05, "representative_e2e",
        )
        screened = LRDagNode(
            "response:E2E_SCREENED_P0p05", LRNodeKind.PERTURBATION,
            (reference.node_id,), screened_spec,
        )
        dag = LRDag((reference, bare, screened), analysis_requires_authorization=False)
        dag_executor = GenericDagExecutor(dag, EVIDENCE / "receipts" / "checkpoint.json")

        reference_layout = SiestaCampaignLayout(
            reference_fdf=staged_fdf,
            run_root=EVIDENCE / "runs" / "reference",
            reference_dm=None,
            reference_dm_name="E2E_REFERENCE.DM",
            static_artifacts={"Cu1.psml": PSEUDO},
        )
        reference_runtime = build_admitted_siesta542_runtime(
            campaign_root=EVIDENCE,
            contract=contract,
            executable_path=SIESTA,
            profile=execution_profile,
            hosts=[host],
            layout=reference_layout,
            bare_profile=bare_profile,
        )
        reference_adapter = SlurmAllocationExecutor(
            execution_profile, [host], RecordingFactory(reference_runtime.factory, commands),
            reference_runtime.validator, environment=os.environ,
        )
        reference_receipts = dag_executor.advance(reference_adapter, max_nodes=1)
        if len(reference_receipts) != 1 or reference_receipts[0].state.value != "VALIDATED":
            raise RuntimeError(f"reference was not validated: {reference_receipts!r}")
        write_json(
            EVIDENCE / "receipts" / "reference-provenance.json",
            reference_runtime.validator.last_provenance,
        )

        reference_run_dirs = list(reference_layout.run_root.iterdir())
        if len(reference_run_dirs) != 1:
            raise RuntimeError("reference materialization did not create exactly one node directory")
        reference_dm = reference_run_dirs[0] / "E2E_REFERENCE.DM"
        if not reference_dm.is_file() or reference_dm.stat().st_size == 0:
            raise RuntimeError("validated reference did not produce a non-empty DM")

        response_layout = SiestaCampaignLayout(
            reference_fdf=staged_fdf,
            run_root=EVIDENCE / "runs" / "responses",
            reference_dm=reference_dm,
            reference_dm_name="E2E_REFERENCE.DM",
            static_artifacts={"Cu1.psml": PSEUDO},
        )
        response_runtime = build_admitted_siesta542_runtime(
            campaign_root=EVIDENCE,
            contract=contract,
            executable_path=SIESTA,
            profile=execution_profile,
            hosts=[host],
            layout=response_layout,
            bare_profile=bare_profile,
        )
        response_adapter = SlurmAllocationExecutor(
            execution_profile, [host], RecordingFactory(response_runtime.factory, commands),
            response_runtime.validator, environment=os.environ,
        )
        bare_receipts = dag_executor.advance(response_adapter, max_nodes=1)
        if len(bare_receipts) != 1 or bare_receipts[0].state.value != "VALIDATED":
            raise RuntimeError(f"BARE node was not validated: {bare_receipts!r}")
        write_json(
            EVIDENCE / "receipts" / "bare-provenance.json",
            response_runtime.validator.last_provenance,
        )

        screened_receipts = dag_executor.advance(response_adapter, max_nodes=1)
        if len(screened_receipts) != 1 or screened_receipts[0].state.value != "VALIDATED":
            raise RuntimeError(f"SCREENED node was not validated: {screened_receipts!r}")
        write_json(
            EVIDENCE / "receipts" / "screened-provenance.json",
            response_runtime.validator.last_provenance,
        )

        receipts = [*reference_receipts, *bare_receipts, *screened_receipts]
        result.update({
            "status": "PASS",
            "finished_utc": datetime.now(timezone.utc).isoformat(),
            "slurm_job_id": os.environ["SLURM_JOB_ID"],
            "host": host,
            "mpi_ranks": 4,
            "receipts": [
                {
                    "node_id": receipt.node_id,
                    "state": receipt.state.value,
                    "evidence_digest": receipt.evidence_digest,
                }
                for receipt in receipts
            ],
            "reference_dm": {
                "path": str(reference_dm),
                "sha256": sha256_file(reference_dm),
                "size": reference_dm.stat().st_size,
            },
        })
        write_json(EVIDENCE / "commands.json", commands)
        write_json(EVIDENCE / "result.json", result)
        print(EVIDENCE)
        return 0
    except Exception as exc:
        result.update({
            "status": "FAIL",
            "finished_utc": datetime.now(timezone.utc).isoformat(),
            "error_type": type(exc).__name__,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        })
        write_json(EVIDENCE / "commands.json", commands)
        write_json(EVIDENCE / "result.json", result)
        print(traceback.format_exc(), file=sys.stderr)
        print(EVIDENCE, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
