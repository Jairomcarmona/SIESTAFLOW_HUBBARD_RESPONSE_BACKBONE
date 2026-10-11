"""Typed helpers for installed-controller synthetic campaign tests."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import sysconfig
import time
from pathlib import Path

import hubbardflow.siesta_backend.siesta542_bare_profile as bare_profile
from hubbardflow.execution.campaign_v2 import CONFIG_SCHEMA
from hubbardflow.execution.wsl_campaign_init import initialize_campaign
from hubbardflow.siesta_backend.backend_identity import sha256_file


def _fdf() -> str:
    return """NumberOfAtoms 1
NumberOfSpecies 1
%block ChemicalSpeciesLabel
1 27 Co
%endblock ChemicalSpeciesLabel
LatticeConstant 2 Ang
%block LatticeVectors
1 0 0
0 1 0
0 0 1
%endblock LatticeVectors
AtomicCoordinatesFormat Fractional
%block AtomicCoordinatesAndAtomicSpecies
0 0 0 1 # Co label
%endblock AtomicCoordinatesAndAtomicSpecies
%block DFTU.Proj
Co 1
3 2
0 0
3.0 0.05 9.0
%endblock DFTU.Proj
DFTU.ProjectorGenerationMethod 2
Spin non-polarized
DFTU.PotentialShift true
XC.functional GGA
XC.authors PBE
%block PAO.Basis
Co
n=3 0 2 E 40 5
%endblock PAO.Basis
"""


def _write_executable(path: Path, content: str) -> Path:
    path.write_text(f"#!{sys.executable}\n{content}", encoding="utf-8")
    path.chmod(0o755)
    return path


def initialize_synthetic_campaign(root: Path) -> tuple[Path, Path, Path]:
    root.mkdir(parents=True, exist_ok=True)
    input_root = root / "source"
    input_root.mkdir()
    fdf_path = input_root / "reference.fdf"
    fdf_path.write_text(_fdf(), encoding="utf-8")
    pseudo = input_root / "Co.psml"
    pseudo.write_text(
        "<psml><functional>PBE GGA</functional><input-file>Co 27</input-file></psml>\n",
        encoding="utf-8",
    )
    parent_dm = input_root / "parent.DM"
    parent_dm.write_bytes(b"synthetic parent density matrix input\n")

    siesta = _write_executable(
        input_root / "siesta",
        """import os, pathlib, signal, sys, time
counter = pathlib.Path(os.environ['HF_TEST_COUNTER'])
number = int(counter.read_text() if counter.exists() else '0') + 1
counter.write_text(str(number))
if number > 1 and os.environ.get('HF_TEST_BLOCK_AFTER_REFERENCE') == '1':
    def stop(*_args):
        pathlib.Path(os.environ['HF_TEST_CHILD_TERM']).write_text('term')
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, stop)
    pathlib.Path(os.environ['HF_TEST_CHILD_STARTED']).write_text('ready')
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        time.sleep(0.05)
    raise SystemExit('synthetic child maximum lifetime elapsed')
pathlib.Path('reference.DM').write_bytes(b'synthetic nonempty density matrix output\\n')
print('redata: Spin configuration = none')
print('redata: Number of spin components = 1')
print('redata: Time-Reversal Symmetry = T')
print('siesta: normal completion')
stop_path = os.environ.get('HF_TEST_STOP_AFTER_REFERENCE')
if number == 1 and stop_path:
    pathlib.Path(stop_path).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(stop_path).write_text('stop between native nodes')
""",
    )
    mpi = _write_executable(
        input_root / "mpiexec.openmpi",
        """import os, sys
executable = sys.argv[-1]
os.execv(sys.executable, [sys.executable, executable])
""",
    )

    profile = bare_profile.Siesta542PotentialShiftHamiltonianProfile()
    registry = input_root / "backend.json"
    registry.write_text(
        json.dumps(
            {
                "schema": "backend_compatibility_v1",
                "records": [
                    {
                        "backend": {
                            "backend_id": "siesta",
                            "version": "5.4.2",
                            "executable_sha256": sha256_file(siesta),
                        },
                        "profile": {
                            "profile_id": profile.profile_id,
                            "version": profile.profile_version,
                            "metadata": {"source_revision": profile.source_revision},
                        },
                        "state": "compatible",
                        "reason": "synthetic controller campaign fixture",
                    }
                ],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    version = input_root / "version.txt"
    version.write_text("SIESTA Version : 5.4.2\n", encoding="utf-8")
    config = input_root / "lr.json"
    config.write_text(
        json.dumps(
            {
                "schema": CONFIG_SCHEMA,
                "functional": "PBE",
                "pseudopotentials": {"Co": str(pseudo)},
                "static_artifacts": {"parent.DM": str(parent_dm)},
                "alpha_grid_ev": [-0.06, -0.04, -0.02, 0.02, 0.04, 0.06],
                "coverage": "DISABLED",
                "compatibility_registry": str(registry),
                "version_text_source": str(version),
                "declared_executable": "siesta",
                "analysis_policy": {"estimator": "polynomial", "polynomial_degree": 3},
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    execution_profile = input_root / "profile.json"
    execution_profile.write_text(
        json.dumps(
            {
                "target": "local_wsl",
                "evidence": "VALIDATED_RUNTIME",
                "wsl": {
                    "distribution": "Ubuntu",
                    "python_executable": sys.executable,
                    "workspace_root": str(root),
                },
                "allocation": {
                    "nodes": 1,
                    "total_cpus": 1,
                    "memory": "1G",
                    "walltime": "01:00:00",
                    "max_parallel_steps": 1,
                    "shutdown_margin_seconds": 60,
                    "termination_grace_seconds": 30,
                },
                "runtime": {
                    "module_commands": [],
                    "siesta_executable": str(siesta),
                    "exclusive": True,
                    "environment": {},
                    "launcher": {
                        "kind": "openmpi",
                        "command": [str(mpi)],
                        "bootstrap": "local",
                        "processes_per_node": 1,
                    },
                },
                "task_policy": {"max_attempts": 3, "require_scf_converged": True},
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    initialized = initialize_campaign(
        fdf_path=str(fdf_path),
        lr_config_path=str(config),
        profile_path=str(execution_profile),
        name="campaign",
        campaign_root=str(root),
        pointer_path=str(root / "campaign.pointer.json"),
    )
    return Path(initialized["manifest_path"]), siesta, mpi


def installed_controller_entrypoint() -> Path:
    script = Path(sysconfig.get_path("scripts")) / "hubbardflow-controller"
    assert script.is_file(), "installed hubbardflow-controller console entrypoint is required"
    assert script.resolve().is_relative_to(Path(sys.prefix).resolve())
    return script


def write_controller_reservation(
    run_root: Path,
    manifest: Path,
    mpi: Path,
    attempt: int,
    environment: dict[str, str] | None = None,
) -> tuple[Path, Path]:
    previous = None
    prior_path: Path | None = None
    if attempt > 1:
        prior_path = run_root / "tasks/hf1-lru/attempt-1.jsonl"
        previous = {
            "attempt_id": "attempt-1",
            "outcome": "INTERRUPTED",
            "closure": "CLOSED",
            "state_manifest_sha256": "c" * 64,
        }
    ledger = run_root / f"tasks/hf1-lru/attempt-{attempt}.jsonl"
    verdict = run_root / f"tasks/hf1-lru/resume-verdict-{attempt}.json"
    descriptor = {
        "contract": "qraft.controller-reservation@1.0",
        "run_fingerprint": "a" * 64,
        "task_id": "hf1-lru",
        "attempt_id": f"attempt-{attempt}",
        "attempt_number": attempt,
        "authority_generation": None,
        "capability": {"capability_id": "hubbardflow.hf1.lr-u", "version": "1", "plugin_version": "1"},
        "allocation": {"scheduler": "local", "allocation_id": "synthetic-local-1"},
        "reserved": {
            "hosts": ["node-a"],
            "nodes": 1,
            "runtime_cpus": 1,
            "min_cpus": 1,
            "scheduler_cpus_on_host": {"value": 1, "source": "LOCAL_PROFILE_DECLARATION"},
        },
        "containment": {
            "method": "SUBREAPER_PIDFD",
            "supervisor": {
                "pid": os.getpid(),
                "start_time_ticks": "1",
                "boot_id": "12345678-1234-1234-1234-123456789abc",
            },
        },
        "inner": {
            "launcher_kind": "openmpi",
            "launcher_command": [str(mpi)],
            "processes_per_node": 1,
            "cpus_per_process": 1,
            "max_concurrent": 1,
            "environment": {
                "HF_TEST_COUNTER": str(run_root / "fake-launch-count"),
                **(environment or {}),
            },
        },
        "deadline": {
            "stop_launching_at": "2099-10-11T19:00:00Z",
            "hard_stop_at": "2099-10-11T20:00:00Z",
        },
        "paths": {
            "state_dir": manifest.parent.relative_to(run_root).as_posix(),
            "stop_request": f"tasks/hf1-lru/attempt-{attempt}-stop.json",
            "inner_ledger": ledger.relative_to(run_root).as_posix(),
            "resume_verdict": verdict.relative_to(run_root).as_posix(),
        },
        "previous_attempt": previous,
    }
    descriptor_path = run_root / f"reservation-{attempt}.json"
    descriptor_path.write_text(json.dumps(descriptor), encoding="utf-8")
    return descriptor_path, prior_path if prior_path is not None else ledger


def run_installed_controller_attempt(
    run_root: Path,
    manifest: Path,
    mpi: Path,
    attempt: int,
    environment: dict[str, str] | None = None,
    *,
    prior_path: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    descriptor, default_prior = write_controller_reservation(run_root, manifest, mpi, attempt, environment)
    arguments = [
        str(installed_controller_entrypoint()),
        "--qraft-reservation",
        descriptor.relative_to(run_root).as_posix(),
        "--campaign",
        manifest.relative_to(run_root).as_posix(),
    ]
    if attempt > 1:
        arguments.extend(["--prior-ledger", (prior_path or default_prior).relative_to(run_root).as_posix()])
    child_env = {key: value for key, value in os.environ.items() if key not in {"PYTHONPATH", "PYTHONHOME"}}
    return subprocess.run(
        arguments, cwd=run_root, env=child_env, capture_output=True, text=True, timeout=60, check=False
    )


def read_controller_ledger(path: Path) -> list[dict[str, object]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def ledger_node_id(row: dict[str, object]) -> str:
    key = row["key"]
    assert isinstance(key, dict)
    return str(key["node_id"])


def terminate_installed_controller_after_child_ready(
    run_root: Path,
    manifest: Path,
    descriptor: Path,
    ready_path: Path,
    *,
    prior_ledger: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Wait on a synthetic child barrier, TERM its controller, and collect output."""
    arguments = [
        str(installed_controller_entrypoint()),
        "--qraft-reservation",
        descriptor.relative_to(run_root).as_posix(),
        "--campaign",
        manifest.relative_to(run_root).as_posix(),
    ]
    if prior_ledger is not None:
        arguments.extend(["--prior-ledger", prior_ledger.relative_to(run_root).as_posix()])
    child_env = {key: value for key, value in os.environ.items() if key not in {"PYTHONPATH", "PYTHONHOME"}}
    worker = subprocess.Popen(
        arguments, cwd=run_root, env=child_env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    try:
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline and not ready_path.exists() and worker.poll() is None:
            time.sleep(0.05)
        if not ready_path.exists():
            worker.terminate()
            stdout, stderr = worker.communicate(timeout=10)
            raise AssertionError(f"synthetic active node did not start; stdout={stdout!r}, stderr={stderr!r}")
        os.kill(worker.pid, signal.SIGTERM)
        stdout, stderr = worker.communicate(timeout=30)
        assert worker.returncode is not None
        return subprocess.CompletedProcess(arguments, worker.returncode, stdout, stderr)
    finally:
        if worker.poll() is None:
            worker.terminate()
            try:
                worker.communicate(timeout=3)
            except subprocess.TimeoutExpired:
                worker.kill()
                worker.communicate(timeout=3)
