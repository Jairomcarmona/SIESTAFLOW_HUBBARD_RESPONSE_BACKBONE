#!/usr/bin/env python3
"""Execute and analyse the admitted AFM-II MnO v3r2 response matrix.

This executor owns one fresh reference and the preregistered 28 perturbations.
It deliberately fails closed: no partial matrix, pseudo-inverse, or adjusted
physical input can produce a Hubbard U result.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import shlex
import shutil
import sys
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN = ROOT / "campaigns" / "mno_afmii_strict_lr_v3r2"
# A recovery must never append to a partial response matrix.  The evidence
# root is supplied before the Slurm process starts, so every worker and the
# post-run analysis agree on one fresh, immutable directory.
RESULTS = CAMPAIGN / "results" / os.environ.get(
    "SIESTAFLOW_MNO_RESPONSE_RESULTS", "response-matrix-foreground-v1"
)
SIESTA = Path("/home/jmc/.local/siesta-5.4.2-openmpi/bin/siesta")
MPI = Path("/usr/bin/orterun")
ALPHAS = (-0.1, -0.05, -0.025, 0.0, 0.025, 0.05, 0.1)
MODES = ("BARE", "SCREENED")
REPS = (("A", "MnLR00", 1), ("B", "MnLR01", 2))


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _require(ok: bool, message: str) -> None:
    if not ok:
        raise RuntimeError(message)


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load(relative: str) -> dict[str, Any]:
    return json.loads((CAMPAIGN / relative).read_text(encoding="utf-8"))


def verify() -> dict[str, object]:
    calibration = json.loads((CAMPAIGN / "results/calibration-result.json").read_text())
    lock = _load("locks/response-methodology-lock.json")
    _require(calibration.get("status") == "ADMITTED", "response requires admitted calibration")
    _require(tuple(lock["alpha_ev"]) == ALPHAS and tuple(lock["modes"]) == MODES,
             "response grid/modes do not match frozen lock")
    _require(lock["analysis"] == {"common_alpha_window": True, "direct_inversion_only": True, "matrix_dimension": 16},
             "response analysis contract changed")
    _require(not RESULTS.exists(), f"refusing to reuse response evidence directory {RESULTS}")
    return {"status": "VERIFIED", "response_nodes": 29, "calibration_noise_e": calibration["occupation_noise_e"]}


def _frozen_wheel_wrapper(runtime: Path) -> str:
    wheel = CAMPAIGN / "software/siestaflow_hubbard-0.1.0-py3-none-any.whl"
    python = Path(sys.executable)
    worker = ROOT / "tools/run_mno_afmii_response_v3r2.py"
    return "; ".join((
        "set -eu", f"test ! -e {shlex.quote(str(runtime))}",
        f"{shlex.quote(str(python))} -m venv --system-site-packages {shlex.quote(str(runtime))}",
        f"{shlex.quote(str(runtime / 'bin' / 'python'))} -m pip install --no-index --no-deps --force-reinstall {shlex.quote(str(wheel))}",
        "env -u PYTHONPATH SIESTAFLOW_MNO_RESPONSE_RESULTS=" + shlex.quote(RESULTS.name) + " " + " ".join(
            shlex.quote(str(x)) for x in (runtime / "bin/python", worker, "worker")
        ),
    ))


def foreground_command() -> list[str]:
    from siestaflow_hubbard.execution.slurm_foreground import four_rank_foreground_command
    return four_rank_foreground_command(_frozen_wheel_wrapper(RESULTS.with_suffix(".runtime")))


def _check_runtime() -> None:
    lock = _load("locks/calibration-methodology-lock.json")["runtime"]
    _require(SIESTA.is_file() and _sha(SIESTA) == lock["siesta_sha256"], "SIESTA binary hash mismatch")
    _require(MPI.is_file() and _sha(MPI) == lock["mpi_sha256"], "MPI launcher hash mismatch")


def _load_core():
    sys.path.insert(0, str(CAMPAIGN / "scripts"))
    import lru_core  # type: ignore
    return lru_core


def _stage_pseudos(directory: Path) -> None:
    for index in range(16):
        shutil.copy2(CAMPAIGN / "pseudopotentials/Mn.psml", directory / f"MnLR{index:02d}.psml")
    shutil.copy2(CAMPAIGN / "pseudopotentials/O.psml", directory / "O.psml")


def _run(directory: Path, name: str, mode: str, target: str | None, alpha: float, parent_dm: Path | None) -> Path:
    from run_mno_afmii_strict_v3r2 import _run as execute  # same locked SIESTA/MPI invocation
    return execute(directory, name, mode, target, alpha, parent_dm)


def _correlated_atom_indices(atoms: list[dict], site_map: list[dict]) -> list[int]:
    """Return SIESTA atom indices in the canonical correlated-site order."""
    positions = {atom["label"]: index for index, atom in enumerate(atoms, start=1)}
    ordered_sites = sorted(site_map, key=lambda site: site["index"])
    labels = [site["label"] for site in ordered_sites]
    _require(len(labels) == len(set(labels)), "duplicate correlated-site labels")
    _require(set(labels) <= set(positions), "correlated site absent from atom order")
    return [positions[label] for label in labels]


def _ordered_occupations(values: dict[int, float], correlated_atom_indices: list[int], output: Path) -> list[float]:
    expected = set(correlated_atom_indices)
    _require(expected <= set(values), f"incomplete correlated-site occupations: {output}")
    return [values[index] for index in correlated_atom_indices]


def _occupations(output: Path, mode: str, correlated_atom_indices: list[int]) -> list[float]:
    from siestaflow_hubbard.siesta_backend.event_parser import parse_hubbard_population_events
    from siestaflow_hubbard.siesta_backend.siesta542_bare_profile import Siesta542PotentialShiftHamiltonianProfile
    text = output.read_text(encoding="utf-8", errors="replace")
    events = parse_hubbard_population_events(text)
    _require(bool(events), f"no Hubbard projected populations: {output}")
    event = Siesta542PotentialShiftHamiltonianProfile().select_response(text).response_event if mode == "BARE" else events[-1]
    values = {atom.atom_index: float(atom.trace_total) for atom in event.atoms}
    return _ordered_occupations(values, correlated_atom_indices, output)


def _moment_signature(output: Path, site_map: list[dict]) -> list[float]:
    core = _load_core()
    state = core.magnetic_state(output, site_map)
    return [float(np.mean(state["A_moments"])), float(np.mean(state["B_moments"])), float(state["Mn_total_moment"])]


def worker() -> dict[str, object]:
    _check_runtime()
    for key, expected in (("SLURM_JOB_ID", None), ("SLURM_JOB_NUM_NODES", "1"), ("SLURM_NTASKS", "4"), ("SLURM_CPUS_PER_TASK", "1")):
        _require(os.environ.get(key) if expected is None else os.environ.get(key) == expected, f"requires Slurm {key}={expected or 'set'}")
    _require(os.environ.get("SLURM_RESTART_COUNT") in (None, "", "0"), "Slurm restart/retry is forbidden")
    _require(not RESULTS.exists(), f"refusing to reuse evidence directory {RESULTS}")
    core, config = _load_core(), _load("source-material.json")
    atoms, site_map = core.build_atoms(config)
    correlated_atom_indices = _correlated_atom_indices(atoms, site_map)
    reference = _run(RESULTS / "00_REFERENCE", "00_REFERENCE", "REFERENCE", None, 0.0, None)
    dm = reference.parent / "00_REFERENCE.DM"
    _require(dm.is_file() and dm.stat().st_size > 0, "reference DM missing")
    _moment_signature(reference, site_map)
    records: dict[str, object] = {"reference": {"output": str(reference.relative_to(RESULTS)), "sha256": _sha(reference), "dm_sha256": _sha(dm)}}
    for role, target, _target_index in REPS:
        for mode in MODES:
            for alpha in ALPHAS:
                token = f"{role}_{mode}_{alpha:+.3f}".replace("+", "p").replace("-", "m").replace(".", "d")
                output = _run(RESULTS / token, token, mode, target, alpha, dm)
                records[token] = {"role": role, "target": target, "mode": mode, "alpha_ev": alpha,
                                  "output": str(output.relative_to(RESULTS)), "sha256": _sha(output),
                                  "occupations_e": _occupations(output, mode, correlated_atom_indices), "moment_signature": _moment_signature(output, site_map),
                                  "parent_dm_sha256": _sha(dm)}
    receipt = {"schema": "siestaflow-mno-response-receipt-v1", "slurm_job_id": os.environ["SLURM_JOB_ID"],
               "records": records, "runtime": {"siesta_sha256": _sha(SIESTA), "mpi_sha256": _sha(MPI)}}
    _write(RESULTS / "response-receipt.json", receipt)
    return receipt


def analyze() -> dict[str, object]:
    from siestaflow_hubbard.domain.alpha_selection import AlphaSelectionPolicy, select_common_alpha_window
    from siestaflow_hubbard.domain.matrix_response_acceptance import MatrixResponseAcceptancePolicy, accept_response_matrices
    core, config = _load_core(), _load("source-material.json")
    _require((RESULTS / "response-receipt.json").is_file(), "response receipt missing")
    receipt = json.loads((RESULTS / "response-receipt.json").read_text())
    records = receipt["records"]
    expected = 1 + len(REPS) * len(MODES) * len(ALPHAS)
    _require(len(records) == expected, "incomplete response node set")
    ordered: list[tuple[str, str]] = [(role, mode) for role, _, _ in REPS for mode in MODES]
    occupations, moments = [], []
    for alpha in ALPHAS:
        row, moment_row = [], []
        for role, mode in ordered:
            token = f"{role}_{mode}_{alpha:+.3f}".replace("+", "p").replace("-", "m").replace(".", "d")
            record = records.get(token)
            _require(record is not None and record["alpha_ev"] == alpha and record["mode"] == mode and record["role"] == role,
                     f"invalid/missing response record {token}")
            row.extend(record["occupations_e"]); moment_row.append(record["moment_signature"])
        occupations.append(row); moments.append(moment_row)
    noise = float(json.loads((CAMPAIGN / "results/calibration-result.json").read_text())["occupation_noise_e"])
    policy_payload = _load("locks/matrix-response-acceptance-policy-v1.json")
    alpha_policy = policy_payload["alpha_selection"]
    report = select_common_alpha_window(ALPHAS, occupations, moments, 0.05, AlphaSelectionPolicy(
        occupation_noise=noise, require_channel_signal=alpha_policy["require_channel_signal"],
        residual_relative=alpha_policy["residual_relative"], slope_relative=alpha_policy["slope_relative"],
        magnetic_tolerance=alpha_policy["magnetic_tolerance"],
    ))
    result: dict[str, object] = {"schema": "siestaflow-mno-response-analysis-v1", "status": "FAIL", "common_alpha_window": report,
                                  "response_receipt_sha256": _sha(RESULTS / "response-receipt.json"), "U_Mn_eV": None}
    if report["status"] != "proposed":
        result["reason"] = "SCIENTIFIC_ANALYSIS_FAILED: NO_COMMON_LINEAR_ALPHA_WINDOW"; _write(RESULTS / "analysis-result.json", result); return result
    window = report["windows"][[w["alpha_ev"] for w in report["windows"]].index(report["recommended_alpha_ev"])]
    slopes = np.asarray(window["slope"], dtype=float)
    slope_uncertainty = np.asarray(window["slope_uncertainty"], dtype=float)
    columns = {key: slopes[index * 16:(index + 1) * 16] for index, key in enumerate(ordered)}
    uncertainty_columns = {key: slope_uncertainty[index * 16:(index + 1) * 16] for index, key in enumerate(ordered)}
    site_map = core.build_atoms(config)[1]
    chi0_raw = core.reconstruct(columns[("A", "BARE")], columns[("B", "BARE")], site_map)
    chi_raw = core.reconstruct(columns[("A", "SCREENED")], columns[("B", "SCREENED")], site_map)
    chi0_uncertainty = core.reconstruct(uncertainty_columns[("A", "BARE")], uncertainty_columns[("B", "BARE")], site_map)
    chi_uncertainty = core.reconstruct(uncertainty_columns[("A", "SCREENED")], uncertainty_columns[("B", "SCREENED")], site_map)
    matrix_policy = MatrixResponseAcceptancePolicy(**policy_payload["matrix_acceptance"])
    matrix_report = accept_response_matrices(chi0_raw, chi_raw, chi0_uncertainty, chi_uncertainty, matrix_policy)
    result["matrix_acceptance"] = {key: value for key, value in matrix_report.items() if key not in {"chi0_matrix", "chi_matrix"}}
    if not matrix_report["accepted"]:
        result["reason"] = "SCIENTIFIC_ANALYSIS_FAILED: MATRIX_STABILITY"; _write(RESULTS / "analysis-result.json", result); return result
    chi0, chi = matrix_report["chi0_matrix"], matrix_report["chi_matrix"]
    kernel = core.direct_kernel(chi0, chi); site_u = np.diag(kernel)
    np.savetxt(RESULTS / "chi0.csv", chi0, delimiter=","); np.savetxt(RESULTS / "chi.csv", chi, delimiter=",")
    np.savetxt(RESULTS / "K_hubbard.csv", kernel, delimiter=",")
    result.update(status="PASS", U_Mn_eV=float(site_u.mean()), U_by_site_eV={site["label"]: float(site_u[site["index"]]) for site in site_map},
                  inversion_residuals={"chi0": float(np.linalg.norm(np.linalg.inv(chi0) @ chi0 - np.eye(16))), "chi": float(np.linalg.norm(np.linalg.inv(chi) @ chi - np.eye(16)) )})
    _write(RESULTS / "analysis-result.json", result); return result


def main() -> int:
    parser = argparse.ArgumentParser(); sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("verify"); sub.add_parser("worker"); sub.add_parser("analyze"); launch = sub.add_parser("launch"); launch.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "verify": output = verify()
        elif args.command == "worker": output = worker()
        elif args.command == "analyze": output = analyze()
        else:
            verify(); command = foreground_command()
            if args.dry_run: output = {"status": "DRY_RUN", "command": command}
            else:
                from siestaflow_hubbard.execution.slurm_foreground import submit_four_rank_foreground
                completed = submit_four_rank_foreground(command[-1], cwd=ROOT)
                output = {"status": "COMPLETED", "slurm_job_id": completed.stdout.strip().split(";", 1)[0], "analysis": analyze()}
        print(json.dumps(output, indent=2, sort_keys=True)); return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr); return 1


if __name__ == "__main__":
    raise SystemExit(main())
