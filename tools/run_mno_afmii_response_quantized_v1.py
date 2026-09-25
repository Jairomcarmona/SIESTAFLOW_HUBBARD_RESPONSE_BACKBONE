#!/usr/bin/env python3
"""Execute or reanalyse MnO response data with printed-total precision bounds.

This version preserves historical response receipts, reads each selected
SIESTA ``Occupations:`` total with its printed decimal precision, and propagates
that interval through the linear fit and direct response-matrix inversion.
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
    "SIESTAFLOW_MNO_RESPONSE_RESULTS", "response-matrix-precision-v1"
)
SOFTWARE_LOCK_PATH = CAMPAIGN / "locks/software-lock-precision-v2.json"
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
    software_lock = _verify_precision_software_lock()
    _require(not RESULTS.exists(), f"refusing to reuse response evidence directory {RESULTS}")
    return {"status": "VERIFIED", "response_nodes": 29, "calibration_noise_e": calibration["occupation_noise_e"],
            "precision_software_wheel_sha256": software_lock["wheel"]["sha256"]}


def _verify_precision_software_lock() -> dict[str, Any]:
    lock = json.loads(SOFTWARE_LOCK_PATH.read_text(encoding="utf-8"))
    wheel_path = CAMPAIGN / lock["wheel"]["path"]
    _require(wheel_path.is_file() and _sha(wheel_path) == lock["wheel"]["sha256"],
             "precision-analysis wheel hash mismatch")
    for relative, expected in lock["files"].items():
        path = ROOT / relative
        _require(path.is_file() and _sha(path) == expected, f"precision software lock mismatch: {relative}")
    return lock


def _frozen_wheel_wrapper(runtime: Path) -> str:
    software_lock = _verify_precision_software_lock()
    wheel = CAMPAIGN / software_lock["wheel"]["path"]
    python = Path(sys.executable)
    worker = Path(__file__).resolve()
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


def _occupations(output: Path, mode: str, correlated_atom_indices: list[int]) -> dict[str, list[float]]:
    from siestaflow_hubbard.siesta_backend.event_parser import parse_hubbard_population_events
    from siestaflow_hubbard.siesta_backend.occupation_precision import read_printed_occupation_precision
    from siestaflow_hubbard.siesta_backend.siesta542_bare_profile import Siesta542PotentialShiftHamiltonianProfile
    text = output.read_text(encoding="utf-8", errors="replace")
    events = parse_hubbard_population_events(text)
    _require(bool(events), f"no Hubbard projected populations: {output}")
    event = Siesta542PotentialShiftHamiltonianProfile().select_response(text).response_event if mode == "BARE" else events[-1]
    by_index = {atom.atom_index: atom for atom in event.atoms}
    _require(set(correlated_atom_indices) <= set(by_index), f"incomplete correlated-site occupations: {output}")
    selected = [by_index[index] for index in correlated_atom_indices]
    precision = read_printed_occupation_precision(text, event)
    half_steps = [precision[atom.atom_index].half_width for atom in selected]
    totals = [precision[atom.atom_index].total for atom in selected]
    return {
        "printed_totals_e": [float(value) for value in totals],
        "matrix_traces_e": [float(atom.trace_total) for atom in selected],
        "half_widths_e": [float(value) for value in half_steps],
    }


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
                measured = _occupations(output, mode, correlated_atom_indices)
                records[token] = {"role": role, "target": target, "mode": mode, "alpha_ev": alpha,
                                  "output": str(output.relative_to(RESULTS)), "sha256": _sha(output),
                                  "occupations_e": measured["printed_totals_e"],
                                  "occupation_source": "SIESTA Occupations total field",
                                  "occupation_half_widths_e": measured["half_widths_e"],
                                  "occupation_matrix_trace_e": measured["matrix_traces_e"],
                                  "moment_signature": _moment_signature(output, site_map),
                                  "parent_dm_sha256": _sha(dm)}
    software_lock = _verify_precision_software_lock()
    receipt = {"schema": "siestaflow-mno-response-receipt-v2", "slurm_job_id": os.environ["SLURM_JOB_ID"],
               "records": records, "runtime": {"siesta_sha256": _sha(SIESTA), "mpi_sha256": _sha(MPI),
                           "precision_software_wheel_sha256": software_lock["wheel"]["sha256"],
                           "response_runner_sha256": _sha(Path(__file__))}}
    _write(RESULTS / "response-receipt.json", receipt)
    return receipt


def _measurement_arrays(receipt: dict, roles: list[tuple[str, str]], atom_indices: list[int]) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[dict]]:
    """Re-read receipt-bound outputs, retaining the printed total and its precision."""
    records = receipt["records"]
    root = RESULTS.resolve()
    values_by_alpha, widths_by_alpha, moments_by_alpha, provenance = [], [], [], []
    for alpha in ALPHAS:
        value_row, width_row, moment_row = [], [], []
        for role, mode in roles:
            matches = [record for record in records.values()
                       if record.get("role") == role and record.get("mode") == mode
                       and abs(float(record["alpha_ev"]) - alpha) < 1e-12]
            _require(len(matches) == 1, f"expected exactly one receipt row for {role}/{mode}/alpha={alpha}")
            record = matches[0]
            output = (RESULTS / record["output"]).resolve()
            _require(output == root or root in output.parents, f"receipt output escapes results root: {output}")
            _require(output.is_file() and _sha(output) == record["sha256"], f"response output hash mismatch: {output}")
            measured = _occupations(output, mode, atom_indices)
            old_values = np.asarray(record.get("occupations_e", []), dtype=float)
            if record.get("occupation_source") == "SIESTA Occupations total field":
                _require(np.allclose(old_values, measured["printed_totals_e"], rtol=0.0, atol=1e-12),
                         f"receipt printed totals differ from output: {output}")
                _require(np.allclose(record.get("occupation_half_widths_e", []), measured["half_widths_e"],
                                     rtol=0.0, atol=1e-15), f"receipt precision differs from output: {output}")
            else:
                # Legacy receipts stored the rounded projector-matrix diagonal sum.
                _require(np.allclose(old_values, measured["matrix_traces_e"], rtol=0.0, atol=1e-12),
                         f"legacy receipt matrix traces differ from output: {output}")
            value_row.extend(measured["printed_totals_e"])
            width_row.extend(measured["half_widths_e"])
            moment_row.append(record["moment_signature"])
            provenance.append({"output": str(output.relative_to(root)).replace("\\", "/"),
                               "sha256": record["sha256"], "role": role, "mode": mode,
                               "alpha_ev": float(alpha), "occupation_source": "printed_total_trace",
                               "selected_sites": len(atom_indices),
                               "occupation_half_width_e": [min(measured["half_widths_e"]), max(measured["half_widths_e"])],
                               "max_matrix_vs_printed_total_delta_e": max(
                                   abs(a - b) for a, b in zip(measured["matrix_traces_e"], measured["printed_totals_e"]))})
        values_by_alpha.append(value_row)
        widths_by_alpha.append(width_row)
        moments_by_alpha.append(moment_row)
    expected_outputs = len(ALPHAS) * len(roles)
    _require(len(provenance) == expected_outputs, "incomplete selected output provenance")
    return (np.asarray(values_by_alpha, dtype=float), np.asarray(widths_by_alpha, dtype=float),
            np.asarray(moments_by_alpha, dtype=float), provenance)


def _fit_alpha_windows(values: np.ndarray, half_widths: np.ndarray, moments: np.ndarray,
                       alpha_policy: dict) -> list[dict[str, object]]:
    from siestaflow_hubbard.domain.quantized_response import fit_centered_linear_response
    order = np.argsort(ALPHAS)
    xall, y, h, m = np.asarray(ALPHAS, dtype=float)[order], values[order], half_widths[order], moments[order]
    magnetic_deviation = float(np.max(np.linalg.norm(m - m[3], axis=2)))
    magnetic_changed = magnetic_deviation > float(alpha_policy["magnetic_tolerance"])
    central = []
    amplitudes = 0.05 * np.array([0.5, 1.0, 2.0])
    for amplitude in amplitudes:
        im = int(np.argmin(np.abs(xall + amplitude)))
        ip = int(np.argmin(np.abs(xall - amplitude)))
        central.append((y[ip] - y[im]) / (2.0 * amplitude))
    central = np.asarray(central)
    fits = []
    for index, amplitude in enumerate(amplitudes):
        mask = np.abs(xall) <= amplitude * (1.0 + 1e-12)
        x, subset, precision = xall[mask], y[mask], h[mask]
        fit = fit_centered_linear_response(x, subset, precision)
        noise = np.max(precision, axis=0)
        centered_x = x - float(np.mean(x))
        denominator = float(centered_x @ centered_x)
        variance = np.maximum(np.sum(fit.residuals**2, axis=0) / (len(x) - 2), noise**2)
        stderr = np.sqrt(variance / denominator)
        drift = np.max(np.abs(central[:max(2, index + 1)] - fit.slope), axis=0)
        signal = np.abs(fit.slope) * amplitude
        residual_ok = bool(np.all(np.max(np.abs(fit.residuals), axis=0)
                                  <= 3.0 * noise + float(alpha_policy["residual_relative"]) * signal))
        slope_ok = bool(np.all(drift <= float(alpha_policy["slope_relative"]) * np.abs(fit.slope) + 3.0 * stderr))
        channel_signal_ok = (not alpha_policy.get("require_channel_signal", False)
                              or bool(np.all(signal >= float(alpha_policy.get("min_signal_to_noise", 10.0)) * noise)))
        fits.append({"alpha_ev": float(amplitude), "slope": fit.slope,
                     "rounding_half_width": fit.slope_half_width,
                     "stderr_diagnostic": stderr, "drift_diagnostic": drift,
                     "magnetic_deviation": magnetic_deviation,
                     "eligible": bool(not magnetic_changed and residual_ok and slope_ok and channel_signal_ok),
                     "residual_ok": residual_ok, "slope_ok": slope_ok,
                     "channel_signal_ok": channel_signal_ok})
    return fits


def _relative_antisymmetry(matrix: np.ndarray) -> float:
    return float(np.linalg.norm(matrix - matrix.T, ord=2) / max(np.linalg.norm(matrix, ord=2), 1e-300))


def analyze(output_path: Path | None = None) -> dict[str, object]:
    from siestaflow_hubbard.domain.quantized_response import hubbard_u_interval
    core = _load_core()
    receipt_path = RESULTS / "response-receipt.json"
    _require(receipt_path.is_file(), "response receipt missing")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    records = receipt["records"]
    expected = 1 + len(REPS) * len(MODES) * len(ALPHAS)
    _require(len(records) == expected, "incomplete response node set")
    ordered: list[tuple[str, str]] = [(role, mode) for role, _, _ in REPS for mode in MODES]
    atoms, site_map = core.build_atoms(_load("source-material.json"))
    atom_indices = _correlated_atom_indices(atoms, site_map)
    values, half_widths, moments, output_provenance = _measurement_arrays(receipt, ordered, atom_indices)
    policy_payload = _load("locks/matrix-response-acceptance-policy-v1.json")
    fits = _fit_alpha_windows(values, half_widths, moments, policy_payload["alpha_selection"])
    matrix_policy = policy_payload["matrix_acceptance"]
    windows = []
    for fit in fits:
        slopes = fit["slope"]
        rounding = fit["rounding_half_width"]
        blocks = {key: slopes[index * 16:(index + 1) * 16] for index, key in enumerate(ordered)}
        bound_blocks = {key: rounding[index * 16:(index + 1) * 16] for index, key in enumerate(ordered)}
        chi0_raw = core.reconstruct(blocks[("A", "BARE")], blocks[("B", "BARE")], site_map)
        chi_raw = core.reconstruct(blocks[("A", "SCREENED")], blocks[("B", "SCREENED")], site_map)
        chi0_width = core.reconstruct(bound_blocks[("A", "BARE")], bound_blocks[("B", "BARE")], site_map)
        chi_width = core.reconstruct(bound_blocks[("A", "SCREENED")], bound_blocks[("B", "SCREENED")], site_map)
        u_report = hubbard_u_interval(chi0_raw, chi_raw, chi0_width, chi_width)
        chi0_anti, chi_anti = _relative_antisymmetry(chi0_raw), _relative_antisymmetry(chi_raw)
        matrix_ok = bool(
            chi0_anti <= matrix_policy["max_antisymmetry_relative"]
            and chi_anti <= matrix_policy["max_antisymmetry_relative"]
            and u_report["chi0"]["condition_number"] <= matrix_policy["max_condition_number"]
            and u_report["chi"]["condition_number"] <= matrix_policy["max_condition_number"]
        )
        interval_ok = bool(u_report["robustly_invertible"] and matrix_ok)
        windows.append({
            "alpha_ev": fit["alpha_ev"], "eligible": fit["eligible"],
            "residual_ok": fit["residual_ok"], "slope_ok": fit["slope_ok"],
            "channel_signal_ok": fit["channel_signal_ok"],
            "magnetic_deviation": fit["magnetic_deviation"],
            "max_slope_rounding_half_width_e_per_ev": float(np.max(rounding)),
            "max_alpha_drift_e_per_ev": float(np.max(fit["drift_diagnostic"])),
            "chi0_antisymmetry_relative": chi0_anti, "chi_antisymmetry_relative": chi_anti,
            "chi0_condition_number": u_report["chi0"]["condition_number"],
            "chi_condition_number": u_report["chi"]["condition_number"],
            "chi0_beta": u_report["chi0"]["beta"], "chi_beta": u_report["chi"]["beta"],
            "matrix_checks_pass": matrix_ok, "robustly_invertible": u_report["robustly_invertible"],
            "u_mn_eV_point": u_report["u_eV_point"] if interval_ok else None,
            "u_mn_eV_interval": u_report["u_eV_interval"] if interval_ok else None,
            "u_by_site_eV": (u_report["u_by_site_eV"].tolist() if interval_ok else None),
            "chi0_inverse_error_bound": u_report["chi0"]["inverse_error_bound"],
            "chi_inverse_error_bound": u_report["chi"]["inverse_error_bound"],
        })

    eligible_all = all(bool(row["eligible"]) for row in windows)
    matrix_all = all(bool(row["matrix_checks_pass"]) and bool(row["robustly_invertible"]) for row in windows)
    intervals = [row["u_mn_eV_interval"] for row in windows if row["u_mn_eV_interval"] is not None]
    intersection = None
    if eligible_all and matrix_all and len(intervals) == len(windows):
        candidate = [max(interval[0] for interval in intervals), min(interval[1] for interval in intervals)]
        if candidate[0] <= candidate[1]:
            intersection = candidate
    accepted = intersection is not None
    outer = next((row for row in windows if row["alpha_ev"] == 0.1), None)
    reasons = []
    if not eligible_all:
        reasons.append("ALPHA_WINDOW_CHECK_FAILED")
    if not matrix_all:
        reasons.append("MATRIX_ROUNDING_INTERVAL_NOT_ACCEPTED")
    if eligible_all and matrix_all and intersection is None:
        reasons.append("ALPHA_WINDOW_U_INTERVALS_DO_NOT_INTERSECT")
    result: dict[str, object] = {
        "schema": "siestaflow-mno-response-analysis-quantized-v1",
        "status": "PRINT_ROUNDING_INTERVAL_ACCEPTED" if accepted else "UNRESOLVED_NO_PRINT_ROUNDING_INTERVAL",
        "U_Mn_eV": float(outer["u_mn_eV_point"]) if accepted and outer else None,
        "U_Mn_eV_interval": intersection,
        "point_estimates_and_bounds_by_alpha": windows,
        "response_receipt_sha256": _sha(receipt_path),
        "analysis_code_sha256": _sha(Path(__file__)),
        "occupation_observable": "SIESTA Occupations total field",
        "occupation_uncertainty": "per-record decimal half-step propagated through OLS and matrix inversion",
        "interval_scope": "printed-occupation rounding only; excludes SCF, discretization, basis, cell, projector, and model uncertainty",
        "accepted_alpha_windows_eV": [row["alpha_ev"] for row in windows if row["eligible"]],
        "matrix_error_acceptance": "invertible throughout print-rounding intervals (beta < 1); no percentage-error cutoff",
        "outputs_verified": len(output_provenance),
        "selected_site_observations": len(output_provenance) * len(atom_indices),
        "max_matrix_vs_printed_total_delta_e": max(row["max_matrix_vs_printed_total_delta_e"] for row in output_provenance),
        "output_provenance": output_provenance,
        "reason": None if accepted else reasons,
    }
    result_path = output_path or (RESULTS / "analysis-result-corrected-v1.json")
    _require(not result_path.exists(), f"refusing to overwrite corrected analysis: {result_path}")
    _write(result_path, result)
    return result

def main() -> int:
    parser = argparse.ArgumentParser(); sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("verify"); sub.add_parser("worker")
    analyze_command = sub.add_parser("analyze"); analyze_command.add_argument("--output", type=Path)
    launch = sub.add_parser("launch"); launch.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "verify": output = verify()
        elif args.command == "worker": output = worker()
        elif args.command == "analyze": output = analyze(args.output)
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
