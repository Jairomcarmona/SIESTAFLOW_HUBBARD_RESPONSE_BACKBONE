#!/usr/bin/env python3
"""Execute one fail-closed seven-point SIESTA 5.4.2 LR campaign for one Cu site.

This is an operational composition of the installed canonical package.  It
accepts only the preregistered, hash-bound occupation-noise calibration after
reopening its physical evidence.  That admission occurs before any response
node runs.  Matrix reconstruction and U remain fail-closed behind the common
alpha-window and direct-inversion gates.
"""

from __future__ import annotations

import argparse
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

import numpy as np

from siestaflow_hubbard.domain.backend_compatibility import ScientificProfile
from siestaflow_hubbard.domain.alpha_selection import AlphaSelectionPolicy, select_common_alpha_window
from siestaflow_hubbard.domain.occupation_noise_calibration import validate_calibration_result
from siestaflow_hubbard.domain.matrix_pipeline import compute_diagnostics, invert_matrix, select_matrix
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
from siestaflow_hubbard.siesta_backend.siesta542_bare_profile import (
    Siesta542PotentialShiftHamiltonianProfile,
)


ROOT = Path(__file__).resolve().parents[1]
PREREGISTERED_CAMPAIGN = ROOT / "campaigns" / "cu_one_atom_mode_centered_lr_v2"
EVIDENCE = ROOT / "docs" / "evidence" / "siesta542_openmpi_slurm_full_campaign_20260920_run2_wheel"
SIESTA = Path("/home/jmc/.local/siesta-5.4.2-openmpi/bin/siesta")
MPI = Path("/usr/bin/orterun")
TEMPLATE = ROOT / "examples" / "tmo_campaigns" / "test_rc.fdf"
PSEUDO = ROOT / "examples" / "tmo_campaigns" / "Cu1.psml"
ALPHA_H_EV = 0.05
ALPHAS = (-0.10, -0.05, -0.025, 0.025, 0.05, 0.10)
REFERENCE_FDF: Path | None = None
REFERENCE_LABEL = "CU_FULL_REFERENCE"
REFERENCE_DM_NAME = "CU_FULL_REFERENCE.DM"
CALIBRATION_RESULT: Path | None = None
CALIBRATION_LOCK: Path | None = None
EXPECTED_CALIBRATION_RESULT_SHA256: str | None = None
EXPECTED_CALIBRATION_LOCK_SHA256: str | None = None
SOFTWARE_LOCK: Path | None = None
EXPECTED_SOFTWARE_LOCK_SHA256: str | None = None


def _default(value: object) -> object:
    if isinstance(value, (Enum, Path)):
        return value.value if isinstance(value, Enum) else str(value)
    return str(value)


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=_default) + "\n", encoding="utf-8")


def checked(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, check=True, text=True, capture_output=True)


def _tag(alpha: float) -> str:
    return ("p" if alpha > 0 else "m") + f"{abs(alpha):.3f}".replace(".", "p")


def reference_fdf() -> str:
    if REFERENCE_FDF is not None:
        return REFERENCE_FDF.read_text(encoding="utf-8")
    original = TEMPLATE.read_text(encoding="utf-8")
    header = original.split("%block DFTU.proj", 1)[0]
    header = header.replace("SystemLabel         cu_test", f"SystemLabel         {REFERENCE_LABEL}")
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


def profile() -> ExecutionProfile:
    return ExecutionProfile.from_mapping({
        "target": "slurm",
        "evidence": "VALIDATED_RUNTIME",
        "slurm": {"partition": "local", "account": None, "qos": None},
        "allocation": {
            "nodes": 1, "total_cpus": 4, "memory": "1G", "walltime": "00:15:00",
            "max_parallel_steps": 1, "shutdown_margin_seconds": 60,
            "termination_grace_seconds": 30,
        },
        "runtime": {
            "module_commands": [], "siesta_executable": str(SIESTA), "exclusive": True,
            "environment": {"OMP_NUM_THREADS": "1"},
            "launcher": {"kind": "openmpi", "command": [str(MPI)], "bootstrap": "ssh",
                         "processes_per_node": 4},
        },
        "task_policy": {"max_attempts": 1, "require_scf_converged": True},
    })


class RecordingFactory:
    def __init__(self, delegate: object, records: list[dict[str, object]]):
        self.delegate, self.records = delegate, records

    def command_for(self, node: LRDagNode):
        command = self.delegate.command_for(node)
        parent = self.delegate.layout.reference_dm
        artifact = self.delegate.artifacts[node.node_id]
        self.records.append({
            "node_id": node.node_id, "argv": list(command.argv), "cwd": str(command.cwd),
            "stdin_path": str(command.stdin_path), "stdout_path": str(command.stdout_path),
            "dm_path": str(command.cwd / artifact.dm),
            "stderr_path": str(command.stderr_path),
            "stdin_sha256_before_execution": sha256_file(command.stdin_path),
            "parent_reference_dm_sha256_before_execution": sha256_file(parent) if parent is not None else None,
        })
        return command


def _response_nodes() -> tuple[LRDagNode, ...]:
    nodes: list[LRDagNode] = []
    for mode in (ResponseMode.BARE, ResponseMode.SCREENED):
        for alpha in (*ALPHAS, 0.0):
            run_id = f"CU1_{mode.value}_{_tag(alpha)}"
            spec = PerturbationSpec(run_id, "orbit_001", 0, "Cu1", mode, alpha,
                                    "explicit_one_site_adaptive_alpha")
            nodes.append(LRDagNode(f"response:{run_id}", LRNodeKind.PERTURBATION,
                                   ("reference",), spec))
    return tuple(nodes)


def _reference_observation(output: Path) -> dict[str, object]:
    events = parse_hubbard_population_events(output.read_text(encoding="utf-8", errors="replace"))
    if not events or len(events[-1].atoms) != 1 or events[-1].atoms[0].atom_index != 1:
        raise RuntimeError("reference projected occupation is absent or ambiguous")
    return {"event_occurrence": events[-1].occurrence_index, "scf_iteration": events[-1].scf_iteration,
            "source_lines_zero_based": [events[-1].source_start_line, events[-1].source_end_line],
            "occupation_trace": events[-1].atoms[0].trace_total}


def _response_observation(node: LRDagNode, output: Path, bare_profile: Siesta542PotentialShiftHamiltonianProfile) -> dict[str, object]:
    text = output.read_text(encoding="utf-8", errors="replace")
    if node.perturbation.mode is ResponseMode.BARE:
        selected = bare_profile.select_response(text).response_event
        role = "source_audited_first_hamiltonian_response"
    else:
        events = parse_hubbard_population_events(text)
        if not events:
            raise RuntimeError(f"{node.node_id}: no Hubbard population events")
        selected, role = events[-1], "final_converged_population"
    if len(selected.atoms) != 1 or selected.atoms[0].atom_index != 1:
        raise RuntimeError(f"{node.node_id}: projected occupation is absent or ambiguous")
    return {
        "node_id": node.node_id, "mode": node.perturbation.mode.value,
        "alpha_ev": node.perturbation.alpha_ev, "role": role,
        "event_occurrence": selected.occurrence_index, "scf_iteration": selected.scf_iteration,
        "source_lines_zero_based": [selected.source_start_line, selected.source_end_line],
        "occupation_trace": selected.atoms[0].trace_total,
        "output_sha256": sha256_file(output),
    }


def _artifact_manifest(root: Path) -> list[dict[str, object]]:
    return [{"path": str(path.relative_to(root)).replace("\\", "/"), "sha256": sha256_file(path),
             "size_bytes": path.stat().st_size}
            for path in sorted(root.rglob("*")) if path.is_file() and path.name != "artifact-manifest.json"]


def _external_occupation_noise() -> tuple[float, dict[str, object]] | None:
    """Load only a calibration result that is bound to its immutable lock."""
    if CALIBRATION_RESULT is None:
        return None
    assert CALIBRATION_LOCK is not None
    if not CALIBRATION_RESULT.is_file() or not CALIBRATION_LOCK.is_file():
        raise RuntimeError("external occupation-noise result or lock is missing")
    if EXPECTED_CALIBRATION_RESULT_SHA256 is None or EXPECTED_CALIBRATION_LOCK_SHA256 is None:
        raise RuntimeError("frozen calibration result and lock hashes are required")
    expected_result_path = (PREREGISTERED_CAMPAIGN / "results-v2/calibration-result.json").resolve()
    expected_lock_path = (PREREGISTERED_CAMPAIGN / "locks/calibration-methodology-lock.json").resolve()
    if CALIBRATION_RESULT.resolve() != expected_result_path or CALIBRATION_LOCK.resolve() != expected_lock_path:
        raise RuntimeError("response execution accepts only the preregistered campaign calibration paths")
    admission = subprocess.run(
        [sys.executable, str(ROOT / "tools/run_preregistered_cu_one_atom_mode_centered_v2.py"), "response-admission"],
        cwd=ROOT, text=True, capture_output=True, check=False,
    )
    if admission.returncode != 0:
        raise RuntimeError("physical calibration evidence admission failed: " + admission.stderr.strip())
    try:
        admission_payload = json.loads(admission.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("calibration evidence admission returned invalid JSON") from exc
    if admission_payload.get("status") != "ADMITTED" or admission_payload.get("calibration_result") != "bound":
        raise RuntimeError("calibration evidence was not admitted")
    validated = validate_calibration_result(
        CALIBRATION_RESULT, CALIBRATION_LOCK,
        expected_result_sha256=EXPECTED_CALIBRATION_RESULT_SHA256,
        expected_lock_sha256=EXPECTED_CALIBRATION_LOCK_SHA256,
    )
    payload = json.loads(CALIBRATION_RESULT.read_text(encoding="utf-8"))
    expected = sha256_file(CALIBRATION_LOCK)
    if payload.get("calibration_lock_sha256") != expected:
        raise RuntimeError("external occupation-noise calibration lock hash mismatch")
    value = payload.get("occupation_noise_e")
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not np.isfinite(value) or value <= 0.0:
        raise RuntimeError("external occupation-noise bound is invalid")
    return float(value), {"result": str(CALIBRATION_RESULT), "result_sha256": validated["result_sha256"],
                          "lock": str(CALIBRATION_LOCK), "lock_sha256": expected}


def main() -> int:
    global EVIDENCE, REFERENCE_FDF, REFERENCE_LABEL, REFERENCE_DM_NAME, CALIBRATION_RESULT, CALIBRATION_LOCK
    global EXPECTED_CALIBRATION_RESULT_SHA256, EXPECTED_CALIBRATION_LOCK_SHA256, SOFTWARE_LOCK, EXPECTED_SOFTWARE_LOCK_SHA256
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", type=Path)
    parser.add_argument("--reference-fdf", type=Path)
    parser.add_argument("--reference-label")
    parser.add_argument("--reference-dm-name")
    parser.add_argument("--calibration-result", type=Path)
    parser.add_argument("--calibration-lock", type=Path)
    parser.add_argument("--expected-calibration-result-sha256")
    parser.add_argument("--expected-calibration-lock-sha256")
    parser.add_argument("--software-lock", type=Path)
    parser.add_argument("--expected-software-lock-sha256")
    args = parser.parse_args()
    if args.evidence_dir is not None:
        EVIDENCE = args.evidence_dir.resolve()
    REFERENCE_FDF = args.reference_fdf.resolve() if args.reference_fdf is not None else None
    if REFERENCE_FDF is not None and not REFERENCE_FDF.is_file():
        raise SystemExit("--reference-fdf is missing")
    if args.reference_label is not None:
        REFERENCE_LABEL = args.reference_label
    if args.reference_dm_name is not None:
        REFERENCE_DM_NAME = args.reference_dm_name
    CALIBRATION_RESULT, CALIBRATION_LOCK = args.calibration_result, args.calibration_lock
    EXPECTED_CALIBRATION_RESULT_SHA256 = args.expected_calibration_result_sha256
    EXPECTED_CALIBRATION_LOCK_SHA256 = args.expected_calibration_lock_sha256
    SOFTWARE_LOCK, EXPECTED_SOFTWARE_LOCK_SHA256 = args.software_lock, args.expected_software_lock_sha256
    if any(value is None for value in (CALIBRATION_RESULT, CALIBRATION_LOCK, EXPECTED_CALIBRATION_RESULT_SHA256,
                                       EXPECTED_CALIBRATION_LOCK_SHA256, SOFTWARE_LOCK, EXPECTED_SOFTWARE_LOCK_SHA256)):
        raise SystemExit("response execution requires frozen calibration result, calibration lock, and software lock hashes")
    calibrated = _external_occupation_noise()
    if calibrated is None:
        raise SystemExit("response execution requires an admitted external occupation-noise calibration")
    if EVIDENCE.exists():
        raise SystemExit(f"refusing to reuse existing evidence directory: {EVIDENCE}")
    EVIDENCE.mkdir(parents=True)
    commands: list[dict[str, object]] = []
    result: dict[str, object] = {
        "schema": "siestaflow-canonical-full-lr-v1", "status": "RUNNING",
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "scientific_result": None,
        "route": ["LinearResponseBareCampaignContract", "build_admitted_siesta542_runtime",
                  "SiestaCommandFactory", "SiestaOutputValidator", "GenericDagExecutor",
                  "SlurmAllocationExecutor", "HubbardPopulationEventParser", "alpha-linearity-gate"],
    }
    write_json(EVIDENCE / "result.json", result)
    try:
        if os.environ.get("SLURM_RESTART_COUNT") not in (None, "", "0"):
            raise RuntimeError("Slurm restart/retry is forbidden")
        assert SOFTWARE_LOCK is not None and EXPECTED_SOFTWARE_LOCK_SHA256 is not None
        software_provenance = verify_locked_software(
            PREREGISTERED_CAMPAIGN, SOFTWARE_LOCK,
            expected_lock_sha256=EXPECTED_SOFTWARE_LOCK_SHA256, require_installed_wheel=True,
        )
        missing = [str(p) for p in (SIESTA, MPI, TEMPLATE, PSEUDO) if not p.is_file()]
        if missing:
            raise RuntimeError("missing required files: " + ", ".join(missing))
        response_lock_path = ROOT / "campaigns" / "cu_one_atom_mode_centered_lr_v2" / "locks" / "response-methodology-lock.json"
        response_lock = json.loads(response_lock_path.read_text(encoding="utf-8"))
        calibration_lock = json.loads(CALIBRATION_LOCK.read_text(encoding="utf-8"))
        assert REFERENCE_FDF is not None
        expected_fdf = response_lock["input_provenance"]["reference_fdf_sha256"]
        expected_pseudo = response_lock["input_provenance"]["pseudo_sha256"]
        expected_binary = response_lock["runtime"]["siesta_sha256"]
        if (sha256_file(REFERENCE_FDF) != expected_fdf or sha256_file(REFERENCE_FDF) != calibration_lock["input_provenance"]["reference_fdf_sha256"]):
            raise RuntimeError("reference FDF differs from preregistered locks")
        if (sha256_file(PSEUDO) != expected_pseudo or sha256_file(PSEUDO) != calibration_lock["input_provenance"]["pseudo_sha256"]):
            raise RuntimeError("pseudopotential differs from preregistered locks")
        if (sha256_file(SIESTA) != expected_binary or sha256_file(SIESTA) != calibration_lock["runtime"]["siesta_sha256"]):
            raise RuntimeError("SIESTA binary differs from preregistered locks")
        if (sha256_file(MPI) != response_lock["runtime"]["mpi_launcher_sha256"] or
                sha256_file(MPI) != calibration_lock["runtime"]["mpi_launcher_sha256"]):
            raise RuntimeError("MPI launcher differs from preregistered locks")
        required_slurm = ("SLURM_JOB_ID", "SLURM_JOB_NUM_NODES", "SLURM_NTASKS",
                          "SLURM_CPUS_PER_TASK", "SLURM_JOB_NODELIST", "SLURM_JOB_END_TIME")
        absent = [name for name in required_slurm if not os.environ.get(name)]
        if absent:
            raise RuntimeError("must run inside complete Slurm allocation: " + ", ".join(absent))
        host = socket.gethostname()
        version = checked([str(SIESTA), "--version"])
        mpi_version = checked([str(MPI), "--version"])
        smoke = checked([str(MPI), "--host", f"{host}:4", "--map-by", "ppr:4:node", "-np", "4", "/bin/hostname"])
        smoke_hosts = [line.strip() for line in smoke.stdout.splitlines() if line.strip()]
        if smoke_hosts != [host] * 4:
            raise RuntimeError(f"unexpected MPI placement: {smoke_hosts!r}")
        identity = {"executable": str(SIESTA.resolve()), "sha256": sha256_file(SIESTA),
                    "version_output": version.stdout + version.stderr, "mpi_launcher": str(MPI.resolve()),
                    "mpi_version_output": mpi_version.stdout + mpi_version.stderr, "mpi_smoke_hosts": smoke_hosts,
                    "software_provenance": software_provenance}
        write_json(EVIDENCE / "environment" / "identity.json", identity)
        write_json(EVIDENCE / "environment" / "slurm.json", {k: v for k, v in sorted(os.environ.items()) if k.startswith("SLURM_")})
        inputs = EVIDENCE / "inputs"; inputs.mkdir()
        staged_fdf = inputs / "reference.fdf"; staged_fdf.write_text(reference_fdf(), encoding="utf-8", newline="\n")
        write_json(inputs / "source_manifest.json", {"template": str(TEMPLATE), "template_sha256": sha256_file(TEMPLATE),
                   "pseudopotential": str(PSEUDO), "pseudopotential_sha256": sha256_file(PSEUDO),
                   "reference_fdf_sha256": sha256_file(staged_fdf), "alpha_grid_ev": [-0.10, -0.05, -0.025, 0.0, 0.025, 0.05, 0.10],
                   "alpha_zero_representation": "validated_reference_only"})
        bare_profile = Siesta542PotentialShiftHamiltonianProfile()
        contracts = EVIDENCE / "contracts"; contracts.mkdir()
        (contracts / "siesta-version.txt").write_text(identity["version_output"], encoding="utf-8")
        write_json(contracts / "backend-compatibility.json", {"schema": "backend_compatibility_v1", "records": [{
            "backend": {"backend_id": "siesta", "version": "5.4.2", "executable_sha256": identity["sha256"]},
            "profile": {"profile_id": bare_profile.profile_id, "version": bare_profile.profile_version,
                        "metadata": {"source_revision": bare_profile.source_revision}},
            "state": "compatible", "reason": "exact local WSL executable registered for controlled full campaign"}]})
        contract = LinearResponseBareCampaignContract("siesta542-openmpi-slurm-full-campaign-20260920",
            ScientificProfile(bare_profile.profile_id, bare_profile.profile_version), "contracts/backend-compatibility.json",
            "siesta", "contracts/siesta-version.txt")
        write_json(contracts / "campaign-contract.json", contract.to_dict())
        execution_profile = profile(); write_json(contracts / "execution-profile.json", asdict(execution_profile))
        reference = LRDagNode("reference", LRNodeKind.REFERENCE, ())
        responses = _response_nodes()
        dag = LRDag((reference, *responses), analysis_requires_authorization=True, alpha_requires_authorization=True)
        write_json(contracts / "dag.json", {"analysis_requires_authorization": True, "alpha_requires_authorization": True,
                   "nodes": [{"node_id": n.node_id, "kind": n.kind.value, "dependencies": list(n.dependencies),
                              "perturbation": asdict(n.perturbation) if n.perturbation else None} for n in dag.nodes]})
        executor = GenericDagExecutor(dag, EVIDENCE / "receipts" / "checkpoint.json")
        reference_layout = SiestaCampaignLayout(staged_fdf, EVIDENCE / "runs" / "reference", None,
                                                REFERENCE_DM_NAME, {"Cu1.psml": PSEUDO})
        runtime = build_admitted_siesta542_runtime(campaign_root=EVIDENCE, contract=contract, executable_path=SIESTA,
                    profile=execution_profile, hosts=[host], layout=reference_layout, bare_profile=bare_profile)
        adapter = SlurmAllocationExecutor(execution_profile, [host], RecordingFactory(runtime.factory, commands), runtime.validator, environment=os.environ)
        receipts = list(executor.advance(adapter, max_nodes=1))
        if len(receipts) != 1 or receipts[0].state.value != "VALIDATED":
            raise RuntimeError(f"reference not validated: {receipts!r}")
        write_json(EVIDENCE / "receipts" / "reference-provenance.json", runtime.validator.last_provenance)
        ref_dirs = list(reference_layout.run_root.iterdir())
        if len(ref_dirs) != 1:
            raise RuntimeError("reference materialization is ambiguous")
        reference_dm = ref_dirs[0] / REFERENCE_DM_NAME
        if not reference_dm.is_file() or reference_dm.stat().st_size == 0:
            raise RuntimeError("reference DM is missing or empty")
        response_layout = SiestaCampaignLayout(staged_fdf, EVIDENCE / "runs" / "responses", reference_dm,
                                               REFERENCE_DM_NAME, {"Cu1.psml": PSEUDO})
        runtime = build_admitted_siesta542_runtime(campaign_root=EVIDENCE, contract=contract, executable_path=SIESTA,
                    profile=execution_profile, hosts=[host], layout=response_layout, bare_profile=bare_profile)
        adapter = SlurmAllocationExecutor(execution_profile, [host], RecordingFactory(runtime.factory, commands), runtime.validator, environment=os.environ)
        for _ in responses:
            node_receipts = executor.advance(adapter, max_nodes=1)
            if len(node_receipts) != 1 or node_receipts[0].state.value != "VALIDATED":
                raise RuntimeError(f"response not validated: {node_receipts!r}")
            receipts.extend(node_receipts)
            safe = node_receipts[0].node_id.replace(":", "_")
            write_json(EVIDENCE / "receipts" / f"{safe}-provenance.json", runtime.validator.last_provenance)
        write_json(EVIDENCE / "commands.json", commands)
        by_node = {record["node_id"]: Path(str(record["stdout_path"])) for record in commands}
        observations = [_response_observation(node, by_node[node.node_id], bare_profile) for node in responses]
        observations.sort(key=lambda x: (str(x["mode"]), float(x["alpha_ev"])))
        write_json(EVIDENCE / "analysis" / "projected-occupation-observations.json", observations)
        noise, calibration_provenance = calibrated
        axis = np.asarray([-0.10, -0.05, -0.025, 0.0, 0.025, 0.05, 0.10])
        table = {(str(item["mode"]), float(item["alpha_ev"])): float(item["occupation_trace"])
                 for item in observations}
        values = np.asarray([[table[(mode, float(alpha))] for mode in ("BARE", "SCREENED")] for alpha in axis])
        selection = select_common_alpha_window(axis, values, np.zeros((7, 1, 3)), ALPHA_H_EV,
                                               AlphaSelectionPolicy(occupation_noise=noise))
        gate = {"schema": "siestaflow-alpha-linearity-gate-v1", "alpha_grid_ev": axis.tolist(),
                "occupation_noise_e": noise, "calibration_provenance": calibration_provenance,
                "selection": selection}
        if selection["status"] != "proposed":
            gate.update({"status": "REJECTED", "gate": "ALPHA_LINEARTY_GATE_REJECTED",
                         "matrix_reconstruction": {"status": "NOT_AUTHORIZED", "chi0": None, "chi": None},
                         "inversion": {"status": "NOT_AUTHORIZED", "method": None}, "U_ev": None})
        else:
            slopes = next(item["slope"] for item in selection["windows"]
                          if item["alpha_ev"] == selection["recommended_alpha_ev"])
            chi0_raw, chi_raw = np.asarray([[slopes[0]]]), np.asarray([[slopes[1]]])
            lock_ref = calibration_provenance["lock_sha256"]
            chi0, chi = (select_matrix(chi0_raw, chi0_raw, "raw", lock_ref),
                         select_matrix(chi_raw, chi_raw, "raw", lock_ref))
            try:
                diag0, diag = compute_diagnostics(chi0), compute_diagnostics(chi)
                inv0, inv = invert_matrix(chi0, diag0), invert_matrix(chi, diag)
                u = inv0 - inv
                diagnostic_payload = lambda value: {"condition_number": value.condition_number,
                    "singular_values": value.singular_values.tolist(), "numerical_rank": value.numerical_rank,
                    "tolerance": value.tolerance, "is_full_rank": value.is_full_rank}
                gate.update({"status": "ACCEPTED", "gate": "ALPHA_AND_DIRECT_INVERSION_ACCEPTED",
                             "matrix_reconstruction": {"status": "AUTHORIZED", "chi0": chi0.tolist(), "chi": chi.tolist()},
                             "conditioning": {"chi0": diagnostic_payload(diag0), "chi": diagnostic_payload(diag)},
                             "inversion": {"status": "DIRECT", "chi0_inverse": inv0.tolist(), "chi_inverse": inv.tolist()},
                             "U_ev": u.tolist()})
            except Exception as exc:
                gate.update({"status": "REJECTED", "gate": "DIRECT_INVERSION_REJECTED", "reason": str(exc),
                             "matrix_reconstruction": {"status": "NOT_AUTHORIZED", "chi0": None, "chi": None},
                             "inversion": {"status": "NOT_AUTHORIZED", "method": None}, "U_ev": None})
        write_json(EVIDENCE / "analysis" / "alpha-gate.json", gate)
        report = "# SIESTA 5.4.2 mode-centred Cu LR campaign\n\nEach response mode has its own alpha=0 control from the same parent reference DM; the reference is lineage evidence only. The alpha gate is fail-closed.\n"
        (EVIDENCE / "FULL_CAMPAIGN_REPORT.md").write_text(report, encoding="utf-8")
        result.update({"status": "SUCCESS_ANALYSIS_AUTHORIZED" if gate["status"] == "ACCEPTED" else "FAIL_CLOSED_ANALYSIS_NOT_AUTHORIZED", "finished_utc": datetime.now(timezone.utc).isoformat(),
            "slurm_job_id": os.environ["SLURM_JOB_ID"], "host": host, "mpi_ranks": 4,
            "reference_dm": {"path": str(reference_dm), "sha256": sha256_file(reference_dm), "size": reference_dm.stat().st_size},
            "execution_receipts": [{"node_id": r.node_id, "state": r.state.value, "evidence_digest": r.evidence_digest} for r in receipts],
            "analysis_gate": gate})
        write_json(EVIDENCE / "result.json", result)
        write_json(EVIDENCE / "artifact-manifest.json", _artifact_manifest(EVIDENCE))
        print(EVIDENCE)
        return 0
    except Exception as exc:
        result.update({"status": "FAIL_EXECUTION", "finished_utc": datetime.now(timezone.utc).isoformat(),
                       "error_type": type(exc).__name__, "error": str(exc), "traceback": traceback.format_exc()})
        write_json(EVIDENCE / "commands.json", commands)
        write_json(EVIDENCE / "result.json", result)
        write_json(EVIDENCE / "artifact-manifest.json", _artifact_manifest(EVIDENCE))
        print(traceback.format_exc(), file=sys.stderr)
        print(EVIDENCE, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
