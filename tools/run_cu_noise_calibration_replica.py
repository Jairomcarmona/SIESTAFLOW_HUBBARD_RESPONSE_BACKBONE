#!/usr/bin/env python3
"""Run one independently allocated preregistered Cu zero-shift calibration replica."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from hashlib import sha256
import json
import os
from pathlib import Path
import socket

from siestaflow_hubbard.domain.backend_compatibility import ScientificProfile
from siestaflow_hubbard.domain.lr_campaign_contract import LinearResponseBareCampaignContract
from siestaflow_hubbard.domain.symmetry_reduction import PerturbationSpec, ResponseMode
from siestaflow_hubbard.execution.execution_profile import ExecutionProfile
from siestaflow_hubbard.execution.campaign_software_lock import verify_locked_software
from siestaflow_hubbard.execution.generic_executor import GenericDagExecutor
from siestaflow_hubbard.execution.lr_dag import LRDag, LRDagNode, LRNodeKind
from siestaflow_hubbard.execution.runtime_adapters import SlurmAllocationExecutor
from siestaflow_hubbard.siesta_backend.backend_identity import sha256_file
from siestaflow_hubbard.siesta_backend.command_factory import SiestaCampaignLayout
from siestaflow_hubbard.siesta_backend.event_parser import parse_hubbard_population_events
from siestaflow_hubbard.siesta_backend.production_runtime import build_admitted_siesta542_runtime
from siestaflow_hubbard.siesta_backend.siesta542_bare_profile import Siesta542PotentialShiftHamiltonianProfile

ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN = ROOT / "campaigns" / "cu_one_atom_noise_calibrated_lr_v1"
SIESTA = Path("/home/jmc/.local/siesta-5.4.2-openmpi/bin/siesta")
MPI = Path("/usr/bin/orterun")


def _json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def _profile() -> ExecutionProfile:
    return ExecutionProfile.from_mapping({"target": "slurm", "evidence": "VALIDATED_RUNTIME",
        "slurm": {"partition": "local", "account": None, "qos": None},
        "allocation": {"nodes": 1, "total_cpus": 4, "memory": "1G", "walltime": "00:15:00",
                       "max_parallel_steps": 1, "shutdown_margin_seconds": 60, "termination_grace_seconds": 30},
        "runtime": {"module_commands": [], "siesta_executable": str(SIESTA), "exclusive": True,
                    "environment": {"OMP_NUM_THREADS": "1"},
                    "launcher": {"kind": "openmpi", "command": [str(MPI)], "bootstrap": "ssh", "processes_per_node": 4}},
        "task_policy": {"max_attempts": 1, "require_scf_converged": True}})


class _RecordingFactory:
    def __init__(self, delegate, records): self.delegate, self.records = delegate, records
    def command_for(self, node):
        command = self.delegate.command_for(node)
        parent = self.delegate.layout.reference_dm
        artifact = self.delegate.artifacts[node.node_id]
        self.records.append({"node_id": node.node_id, "argv": list(command.argv),
                             "stdin_path": str(command.stdin_path),
                             "stdout_path": str(command.stdout_path),
                             "dm_path": str(command.cwd / artifact.dm),
                             "stdin_sha256_before_execution": sha256_file(command.stdin_path),
                             "parent_reference_dm_sha256_before_execution": sha256_file(parent) if parent is not None else None})
        return command


def _occupation(path: Path, mode: ResponseMode, profile: Siesta542PotentialShiftHamiltonianProfile) -> float:
    text = path.read_text(encoding="utf-8", errors="replace")
    event = profile.select_response(text).response_event if mode is ResponseMode.BARE else parse_hubbard_population_events(text)[-1]
    if len(event.atoms) != 1 or event.atoms[0].atom_index != 1:
        raise RuntimeError("ambiguous Cu projected occupation")
    return event.atoms[0].trace_total


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("replica_id")
    parser.add_argument("--output-root", type=Path, default=CAMPAIGN / "results" / "calibration-replicas")
    parser.add_argument("--software-lock", type=Path, default=CAMPAIGN / "locks" / "software-lock.json")
    parser.add_argument("--expected-software-lock-sha256", required=True)
    args = parser.parse_args()
    required = ("SLURM_JOB_ID", "SLURM_JOB_NUM_NODES", "SLURM_NTASKS", "SLURM_CPUS_PER_TASK")
    if any(not os.environ.get(key) for key in required): raise SystemExit("must execute inside Slurm allocation")
    if os.environ["SLURM_JOB_NUM_NODES"] != "1" or os.environ["SLURM_NTASKS"] != "4" or os.environ["SLURM_CPUS_PER_TASK"] != "1": raise SystemExit("requires exactly one node, four MPI ranks and one thread")
    if os.environ.get("SLURM_RESTART_COUNT") not in (None, "", "0"): raise SystemExit("Slurm restart/retry is forbidden")
    plan = json.loads((CAMPAIGN / "plans/calibration-plan.json").read_text(encoding="utf-8"))
    if args.replica_id not in {item["replica_id"] for item in plan["replicas"]}: raise SystemExit("unknown preregistered replica id")
    verify_locked_software(CAMPAIGN, args.software_lock, expected_lock_sha256=args.expected_software_lock_sha256,
                           require_installed_wheel=True)
    root = args.output_root / args.replica_id
    if root.exists(): raise SystemExit("refusing to reuse replica evidence directory")
    lock = json.loads((CAMPAIGN / "locks/calibration-methodology-lock.json").read_text())
    if sha256_file(SIESTA) != lock["runtime"]["siesta_sha256"]: raise SystemExit("SIESTA binary hash mismatch")
    if sha256_file(MPI) != lock["runtime"]["mpi_launcher_sha256"]: raise SystemExit("MPI launcher hash mismatch")
    if sha256_file(CAMPAIGN / "inputs/reference.fdf") != lock["input_provenance"]["reference_fdf_sha256"]: raise SystemExit("reference FDF hash mismatch")
    if sha256_file(ROOT / "examples/tmo_campaigns/Cu1.psml") != lock["input_provenance"]["pseudo_sha256"]: raise SystemExit("pseudopotential hash mismatch")
    profile, bare = _profile(), Siesta542PotentialShiftHamiltonianProfile()
    contract = LinearResponseBareCampaignContract(args.replica_id, ScientificProfile(bare.profile_id, bare.profile_version),
        "backend-compatibility.json", "siesta", "siesta-version.txt")
    _json(root / "backend-compatibility.json", {"schema": "backend_compatibility_v1", "records": [{"backend": {"backend_id": "siesta", "version": "5.4.2", "executable_sha256": sha256_file(SIESTA)}, "profile": {"profile_id": bare.profile_id, "version": bare.profile_version, "metadata": {"source_revision": bare.source_revision}}, "state": "compatible", "reason": "exact preregistered calibration runtime"}]})
    (root / "siesta-version.txt").write_text("SIESTA 5.4.2\n", encoding="utf-8")
    reference = LRDagNode("reference", LRNodeKind.REFERENCE, ())
    nodes = [reference] + [LRDagNode(f"response:{mode.value}_zero", LRNodeKind.PERTURBATION, ("reference",),
        PerturbationSpec(f"{mode.value}_zero", "orbit_001", 0, "Cu1", mode, 0.0, "independent_zero_shift_control")) for mode in ResponseMode]
    executor = GenericDagExecutor(LRDag(tuple(nodes), True, True), root / "checkpoint.json")
    commands, host = [], socket.gethostname()
    staged = root / "inputs/reference.fdf"; staged.parent.mkdir(parents=True); staged.write_bytes((CAMPAIGN / "inputs/reference.fdf").read_bytes())
    staged_pseudo = root / "inputs/Cu1.psml"; staged_pseudo.write_bytes((ROOT / "examples/tmo_campaigns/Cu1.psml").read_bytes())
    layout = SiestaCampaignLayout(staged, root / "runs/reference", None, "CU_NOISE_LR_REFERENCE.DM", {"Cu1.psml": staged_pseudo})
    runtime = build_admitted_siesta542_runtime(campaign_root=root, contract=contract, executable_path=SIESTA, profile=profile, hosts=[host], layout=layout, bare_profile=bare)
    adapter = SlurmAllocationExecutor(profile, [host], _RecordingFactory(runtime.factory, commands), runtime.validator, environment=os.environ)
    receipts = list(executor.advance(adapter, max_nodes=1))
    if len(receipts) != 1 or receipts[0].state.value != "VALIDATED": raise RuntimeError("reference receipt not VALIDATED")
    _json(root / "provenance/reference.json", runtime.validator.last_provenance)
    refdir = next((root / "runs/reference").iterdir()); dm = refdir / "CU_NOISE_LR_REFERENCE.DM"
    if not dm.is_file() or not dm.stat().st_size: raise RuntimeError("reference DM unavailable")
    layout = SiestaCampaignLayout(staged, root / "runs/controls", dm, "CU_NOISE_LR_REFERENCE.DM", {"Cu1.psml": staged_pseudo})
    runtime = build_admitted_siesta542_runtime(campaign_root=root, contract=contract, executable_path=SIESTA, profile=profile, hosts=[host], layout=layout, bare_profile=bare)
    adapter = SlurmAllocationExecutor(profile, [host], _RecordingFactory(runtime.factory, commands), runtime.validator, environment=os.environ)
    while len(receipts) < 3:
        progress = list(executor.advance(adapter, max_nodes=1))
        if len(progress) != 1 or progress[0].state.value != "VALIDATED": raise RuntimeError("control receipt not VALIDATED")
        receipts.extend(progress)
        _json(root / "provenance" / f"{progress[0].node_id.replace(':', '_')}.json", runtime.validator.last_provenance)
    outputs = {item["node_id"]: Path(item["stdout_path"]) for item in commands}
    receipt_payload = [{"node_id": receipt.node_id, "state": receipt.state.value, "evidence_digest": receipt.evidence_digest} for receipt in receipts]
    _json(root / "receipts.json", receipt_payload)
    receipt_hash = sha256_file(root / "receipts.json")
    payload = {"schema": "siestaflow-calibration-replica-v2", "replica_id": args.replica_id, "slurm_job_id": os.environ["SLURM_JOB_ID"], "slurm_restart_count": os.environ.get("SLURM_RESTART_COUNT"), "alpha_ev": 0.0, "validated": all(r.state.value == "VALIDATED" for r in receipts),
      "occupations": {"REFERENCE": _occupation(outputs["reference"], ResponseMode.SCREENED, bare), **{mode.value: _occupation(outputs[f"response:{mode.value}_zero"], mode, bare) for mode in ResponseMode}},
      "receipts_path": "receipts.json", "receipts_sha256": receipt_hash,
      "reference_dm_path": str(dm), "reference_dm_sha256": sha256_file(dm),
      "pseudo_path": str(staged_pseudo), "parent_dm_sha256": {"BARE": sha256_file(dm), "SCREENED": sha256_file(dm)}, "commands": commands, "execution_profile": asdict(profile),
      "reference_fdf_sha256": sha256_file(staged), "pseudo_sha256": sha256_file(staged_pseudo), "siesta_sha256": sha256_file(SIESTA), "mpi_launcher": str(MPI), "mpi_launcher_sha256": sha256_file(MPI)}
    _json(root / "replica-result.json", payload); print(root / "replica-result.json")
    return 0

if __name__ == "__main__": raise SystemExit(main())
