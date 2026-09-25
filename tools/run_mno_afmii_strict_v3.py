#!/usr/bin/env python3
"""Operate the preregistered AFM-II MnO strict v3 zero-shift preflight.

The command intentionally stops after binding calibration evidence.  Response
submission belongs to a separate, matrix-aware executor and is impossible
until this preflight is admitted.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN = ROOT / "campaigns" / "mno_afmii_strict_lr_v3"
SIESTA = Path("/home/jmc/.local/siesta-5.4.2-openmpi/bin/siesta")
MPI = Path("/usr/bin/orterun")
# Only this directory participates in admission.  Earlier interrupted or
# malformed attempts stay next to it as forensic evidence, never as receipts.
ADMISSIBLE_REPLICA_ROOT = CAMPAIGN / "results" / "calibration-replicas-admissible"


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _load(relative: str) -> dict[str, Any]:
    return json.loads((CAMPAIGN / relative).read_text(encoding="utf-8"))


def _require(ok: bool, message: str) -> None:
    if not ok:
        raise RuntimeError(message)


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def verify() -> dict[str, object]:
    lock = _load("locks/calibration-methodology-lock.json")
    response = _load("locks/response-methodology-lock.json")
    manifest = _load("campaign-manifest.json")
    required = {
        CAMPAIGN / "runs/00_REFERENCE/siesta.fdf": lock["inputs"]["reference_fdf_sha256"],
        CAMPAIGN / "pseudopotentials/Mn.psml": lock["inputs"]["mn_psml_sha256"],
        CAMPAIGN / "pseudopotentials/O.psml": lock["inputs"]["o_psml_sha256"],
    }
    for path, expected in required.items():
        _require(path.is_file() and _sha(path) == expected, f"frozen input hash mismatch: {path.name}")
    fdf = (CAMPAIGN / "runs/00_REFERENCE/siesta.fdf").read_text(encoding="utf-8")
    for token in ("NumberOfAtoms 32", "Spin polarized", "PAO.BasisSize DZP", "MeshCutoff 200 Ry",
                  "DFTU.ProjectorGenerationMethod 2", "DFTU.CutoffNorm 0.90", "DFTU.PotentialShift true"):
        _require(token in fdf, f"reference lacks required MnO setting: {token}")
    _require(response["analysis"]["matrix_dimension"] == 16 and manifest["status"] == "PRE_EXECUTION",
             "invalid MnO strict response contract")
    return {"status": "VERIFIED", "campaign": manifest["campaign_id"], "response_nodes": 29,
            "preflight_replicas": 5, "runtime_locked": lock["runtime"]}


def _plan() -> list[dict[str, object]]:
    return [{"replica_id": f"replica-{index:02d}", "slurm": {"nodes": 1, "tasks": 4,
             "cpus_per_task": 1, "exclusive": True, "retry": "forbidden"},
             "controls": ["REFERENCE", "A_BARE_ZERO", "A_SCREENED_ZERO", "B_BARE_ZERO", "B_SCREENED_ZERO"]}
            for index in range(1, 6)]


def _check_runtime() -> None:
    lock = _load("locks/calibration-methodology-lock.json")["runtime"]
    _require(SIESTA.is_file() and _sha(SIESTA) == lock["siesta_sha256"], "SIESTA binary hash mismatch")
    _require(MPI.is_file() and _sha(MPI) == lock["mpi_sha256"], "MPI launcher hash mismatch")


def _fdf(run_id: str, mode: str, target: str | None, alpha: float) -> str:
    sys.path.insert(0, str(CAMPAIGN / "scripts"))
    from lru_core import build_atoms, render_fdf  # type: ignore
    config = _load("source-material.json")
    atoms, _ = build_atoms(config)
    return render_fdf(config, run_id, mode, target, alpha, atoms)


def _stage_pseudos(directory: Path) -> None:
    for index in range(16):
        shutil.copy2(CAMPAIGN / "pseudopotentials/Mn.psml", directory / f"MnLR{index:02d}.psml")
    shutil.copy2(CAMPAIGN / "pseudopotentials/O.psml", directory / "O.psml")


def _run(directory: Path, name: str, mode: str, target: str | None, alpha: float, parent_dm: Path | None) -> Path:
    directory.mkdir(parents=True, exist_ok=False)
    fdf = directory / "siesta.fdf"
    fdf.write_text(_fdf(name, mode, target, alpha), encoding="utf-8", newline="\n")
    _stage_pseudos(directory)
    if parent_dm is not None:
        shutil.copy2(parent_dm, directory / f"{name}.DM")
    host = socket.gethostname()
    command = [str(MPI), "--host", f"{host}:4", "--map-by", "ppr:4:node", "-np", "4", str(SIESTA)]
    completed = subprocess.run(command, cwd=directory, input=fdf.read_text(encoding="utf-8"), text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    (directory / "siesta.out").write_text(completed.stdout, encoding="utf-8")
    (directory / "siesta.err").write_text(completed.stderr, encoding="utf-8")
    _require(completed.returncode == 0, f"{name}: SIESTA returned {completed.returncode}")
    _require("Job completed" in completed.stdout, f"{name}: SIESTA did not report normal completion")
    if mode != "BARE":
        _require("SCF_NOT_CONV" not in completed.stdout, f"{name}: converged control did not converge")
    return directory / "siesta.out"


def _occupation(output: Path, target_index: int, bare: bool) -> float:
    from siestaflow_hubbard.siesta_backend.event_parser import parse_hubbard_population_events
    from siestaflow_hubbard.siesta_backend.siesta542_bare_profile import Siesta542PotentialShiftHamiltonianProfile
    events = parse_hubbard_population_events(output.read_text(encoding="utf-8", errors="replace"))
    _require(bool(events), f"no Hubbard projected population in {output}")
    event = Siesta542PotentialShiftHamiltonianProfile().select_response(output.read_text(encoding="utf-8", errors="replace")).response_event if bare else events[-1]
    matches = [atom.trace_total for atom in event.atoms if atom.atom_index == target_index]
    _require(len(matches) == 1, f"ambiguous projected occupation for atom {target_index}")
    return float(matches[0])


def worker(replica_id: str) -> dict[str, object]:
    _check_runtime()
    for key, expected in (("SLURM_JOB_ID", None), ("SLURM_JOB_NUM_NODES", "1"), ("SLURM_NTASKS", "4"), ("SLURM_CPUS_PER_TASK", "1")):
        _require(os.environ.get(key) if expected is None else os.environ.get(key) == expected, f"requires Slurm {key}={expected or 'set'}")
    _require(os.environ.get("SLURM_RESTART_COUNT") in (None, "", "0"), "Slurm restart/retry is forbidden")
    root = ADMISSIBLE_REPLICA_ROOT / replica_id
    _require(not root.exists(), f"refusing to reuse evidence directory {root}")
    reference_out = _run(root / "reference", f"{replica_id}_REFERENCE", "REFERENCE", None, 0.0, None)
    reference_dm = reference_out.parent / f"{replica_id}_REFERENCE.DM"
    _require(reference_dm.is_file() and reference_dm.stat().st_size > 0, "reference DM missing")
    values: dict[str, dict[str, object]] = {"REFERENCE": {"occupation_e": _occupation(reference_out, 1, False),
        "output": str(reference_out.relative_to(root)), "sha256": _sha(reference_out)}}
    for role, target, index, mode in (("A_BARE_ZERO", "MnLR00", 1, "BARE"), ("A_SCREENED_ZERO", "MnLR00", 1, "SCREENED"),
                                      ("B_BARE_ZERO", "MnLR01", 2, "BARE"), ("B_SCREENED_ZERO", "MnLR01", 2, "SCREENED")):
        output = _run(root / role.lower(), f"{replica_id}_{role}", mode, target, 0.0, reference_dm)
        values[role] = {"occupation_e": _occupation(output, index, mode == "BARE"), "output": str(output.relative_to(root)), "sha256": _sha(output),
                        "parent_dm_sha256": _sha(reference_dm), "mode": mode, "target": target}
    receipt = {"schema": "siestaflow-mno-preflight-receipt-v1", "replica_id": replica_id,
               "slurm_job_id": os.environ["SLURM_JOB_ID"], "values": values,
               "reference_dm": {"path": str(reference_dm.relative_to(root)), "sha256": _sha(reference_dm)},
               "runtime": {"siesta_sha256": _sha(SIESTA), "mpi_sha256": _sha(MPI)}}
    _write(root / "replica-result.json", receipt)
    return receipt


def bind() -> dict[str, object]:
    receipt_root = ADMISSIBLE_REPLICA_ROOT
    receipts = [receipt_root / f"replica-{index:02d}" / "replica-result.json" for index in range(1, 6)]
    _require(all(path.is_file() for path in receipts), "exactly five preregistered calibration receipts are required")
    records = [json.loads(path.read_text(encoding="utf-8")) for path in receipts]
    _require(len({r["replica_id"] for r in records}) == 5 and len({r["slurm_job_id"] for r in records}) == 5,
             "replica ids and Slurm job ids must be unique")
    roles = ("REFERENCE", "A_BARE_ZERO", "A_SCREENED_ZERO", "B_BARE_ZERO", "B_SCREENED_ZERO")
    for record in records:
        _require(tuple(record["values"].keys()) == roles, "calibration receipt controls do not match lock")
    spreads = {role: max(item["values"][role]["occupation_e"] for item in records) - min(item["values"][role]["occupation_e"] for item in records) for role in roles}
    noise = max(5e-5, 2.0 * max(spreads.values()))
    result = {"schema": "siestaflow-mno-calibration-result-v1", "status": "ADMITTED", "occupation_noise_e": noise,
              "within_mode_spread_e": spreads, "interrole_offsets_diagnostic_only": {
                  "A_bare_minus_reference": [r["values"]["A_BARE_ZERO"]["occupation_e"] - r["values"]["REFERENCE"]["occupation_e"] for r in records],
                  "B_bare_minus_reference": [r["values"]["B_BARE_ZERO"]["occupation_e"] - r["values"]["REFERENCE"]["occupation_e"] for r in records]},
              "receipt_sha256": {r["replica_id"]: _sha(path) for r, path in zip(records, receipts)},
              "calibration_lock_sha256": _sha(CAMPAIGN / "locks/calibration-methodology-lock.json")}
    output = CAMPAIGN / "results" / "calibration-result.json"
    _require(not output.exists(), "refusing to overwrite bound calibration result")
    _write(output, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    command = parser.add_subparsers(dest="command", required=True)
    command.add_parser("verify")
    preflight = command.add_parser("preflight")
    preflight.add_argument("--dry-run", action="store_true")
    worker_parser = command.add_parser("preflight-worker")
    worker_parser.add_argument("replica_id")
    command.add_parser("bind-calibration")
    args = parser.parse_args()
    try:
        if args.command == "verify": result = verify()
        elif args.command == "preflight":
            verify(); plan = _plan()
            if not args.dry_run:
                raise RuntimeError("physical submission is intentionally delegated one replica at a time; run preflight-worker only inside an independently submitted Slurm allocation")
            result = {"status": "DRY_RUN", "jobs": plan}
        elif args.command == "preflight-worker": result = worker(args.replica_id)
        else: result = bind()
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
