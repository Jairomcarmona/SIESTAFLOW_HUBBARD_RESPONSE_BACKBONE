#!/usr/bin/env python3
"""Independent, streaming audit of final LR-U SIESTA outputs in an evidence tar."""
from __future__ import annotations

import argparse
import io
import json
import re
import tarfile
from pathlib import Path

import numpy as np

RUNS = (
    "00_REFERENCE", "10_A_BARE_MINUS", "11_A_BARE_PLUS",
    "12_A_SCREENED_MINUS", "13_A_SCREENED_PLUS", "20_B_BARE_MINUS",
    "21_B_BARE_PLUS", "22_B_SCREENED_MINUS", "23_B_SCREENED_PLUS",
)


def events(text: str) -> list[list[float]]:
    """Extract complete sixteen-site Hubbard occupation events from SIESTA text."""
    output: list[list[float]] = []
    current: list[float] | None = None
    for line in text.splitlines():
        if "hubbard_term: recalculating local occupations" in line:
            if current is not None:
                output.append(current)
            current = []
        elif current is not None and "Occupations:" in line:
            values = re.findall(r"[-+]?(?:\d*\.\d+|\d+)(?:[Ee][-+]?\d+)?", line.split("Occupations:", 1)[1])
            if len(values) >= 3:
                current.append(float(values[-1]))
    if current is not None:
        output.append(current)
    return [event for event in output if len(event) == 16]


def selected(events_for_run: list[list[float]], mode: str) -> np.ndarray:
    if mode == "BARE":
        if len(events_for_run) < 2:
            raise ValueError("BARE output has no second complete occupation event")
        return np.asarray(events_for_run[1], dtype=float)
    if not events_for_run:
        raise ValueError("output has no complete occupation event")
    return np.asarray(events_for_run[-1], dtype=float)


def translated(vector: np.ndarray, translation: int) -> np.ndarray:
    result = np.empty(16, dtype=float)
    for observed in range(16):
        source_t, sublattice = divmod(observed, 2)
        i, j, k = source_t // 4, (source_t // 2) % 2, source_t % 2
        ti, tj, tk = translation // 4, (translation // 2) % 2, translation % 2
        destination_t = ((i + ti) % 2) * 4 + ((j + tj) % 2) * 2 + ((k + tk) % 2)
        result[2 * destination_t + sublattice] = vector[observed]
    return result


def reconstruct(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    matrix = np.empty((16, 16), dtype=float)
    for column in range(16):
        translation, sublattice = divmod(column, 2)
        matrix[:, column] = translated(a if sublattice == 0 else b, translation)
    return matrix


def text_member(archive: tarfile.TarFile, name: str) -> str:
    member = archive.getmember(name)
    extracted = archive.extractfile(member)
    if extracted is None:
        raise ValueError(f"cannot read {name}")
    return extracted.read().decode("utf-8", errors="ignore")


def audit(path: Path) -> dict:
    with tarfile.open(path, "r:gz") as archive:
        output: dict[str, np.ndarray] = {}
        audit_runs: dict[str, dict] = {}
        for run in RUNS:
            out = text_member(archive, f"runs/{run}/siesta.out")
            err = text_member(archive, f"runs/{run}/siesta.err")
            marker = text_member(archive, f"runs/{run}/0_NORMAL_EXIT")
            mode = "BARE" if "BARE" in run else "SCREENED"
            occupation_events = events(out)
            status = out + "\n" + err
            normal = "siesta completed, mpi exit: 0" in marker.lower() or "siesta: normal completion" in status.lower()
            unconverged = bool(re.search(r"SCF_NOT_CONV|SCF: not converged|ABNORMAL_TERMINATION", status, re.I))
            require_convergence = run == "00_REFERENCE" or mode == "SCREENED"
            if not normal:
                raise ValueError(f"{run}: normal completion missing")
            if require_convergence and unconverged:
                raise ValueError(f"{run}: required SCF convergence missing")
            output[run] = selected(occupation_events, mode)
            audit_runs[run] = {
                "mode": "REFERENCE" if run == "00_REFERENCE" else mode,
                "source": {
                    "stdout": f"runs/{run}/siesta.out",
                    "stderr": f"runs/{run}/siesta.err",
                    "normal_exit_marker": f"runs/{run}/0_NORMAL_EXIT",
                },
                "complete_events": len(occupation_events),
                "selected_event": "second" if mode == "BARE" else "last",
                "normal_completion": normal,
                "unconverged_marker": unconverged,
                "selected_occupations_electrons": output[run].tolist(),
            }

    d = lambda plus, minus: (output[plus] - output[minus]) / 0.10
    chi0_raw = reconstruct(d("11_A_BARE_PLUS", "10_A_BARE_MINUS"), d("21_B_BARE_PLUS", "20_B_BARE_MINUS"))
    chi_raw = reconstruct(d("13_A_SCREENED_PLUS", "12_A_SCREENED_MINUS"), d("23_B_SCREENED_PLUS", "22_B_SCREENED_MINUS"))
    chi0, chi = (chi0_raw + chi0_raw.T) / 2, (chi_raw + chi_raw.T) / 2
    inv0, inv = np.linalg.inv(chi0), np.linalg.inv(chi)
    kernel = inv0 - inv
    diagonal = np.diag(kernel)
    return {
        "archive": path.name,
        "audit": "independent_streaming_parser",
        "analysis_protocol": {
            "n_hubbard_sites": 16,
            "alpha_plus_minus_eV": 0.05,
            "finite_difference_denominator_eV": 0.10,
            "bare_event_selector": "second complete Hubbard occupation event",
            "reference_and_screened_event_selector": "last complete Hubbard occupation event",
            "matrix_reconstruction": "A/B response vectors translated across eight supercell translations",
            "symmetrization": "(A + A.T) / 2",
            "inverse": "numpy.linalg.inv (direct inverse; no pseudoinverse)",
            "kernel_eV": "inv(chi0) - inv(chi)",
            "reported_site_value_eV": "diagonal(kernel)",
        },
        "runs": audit_runs,
        "response_columns_electrons_per_eV": {
            "chi0_A": d("11_A_BARE_PLUS", "10_A_BARE_MINUS").tolist(),
            "chi0_B": d("21_B_BARE_PLUS", "20_B_BARE_MINUS").tolist(),
            "chi_A": d("13_A_SCREENED_PLUS", "12_A_SCREENED_MINUS").tolist(),
            "chi_B": d("23_B_SCREENED_PLUS", "22_B_SCREENED_MINUS").tolist(),
        },
        "matrices": {
            "chi0_raw_electrons_per_eV": chi0_raw.tolist(),
            "chi_raw_electrons_per_eV": chi_raw.tolist(),
            "chi0_electrons_per_eV": chi0.tolist(),
            "chi_electrons_per_eV": chi.tolist(),
            "inv_chi0_eV": inv0.tolist(),
            "inv_chi_eV": inv.tolist(),
            "K_hubbard_eV": kernel.tolist(),
            "U_by_site_eV": diagonal.tolist(),
        },
        "rank_chi0": int(np.linalg.matrix_rank(chi0)),
        "rank_chi": int(np.linalg.matrix_rank(chi)),
        "condition_chi0": float(np.linalg.cond(chi0)),
        "condition_chi": float(np.linalg.cond(chi)),
        "inversion_residual_chi0": float(np.linalg.norm(inv0 @ chi0 - np.eye(16))),
        "inversion_residual_chi": float(np.linalg.norm(inv @ chi - np.eye(16))),
        "U_mean_eV": float(diagonal.mean()),
        "U_A_mean_eV": float(diagonal[::2].mean()),
        "U_B_mean_eV": float(diagonal[1::2].mean()),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(args.archive)
    text = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    print(text)
