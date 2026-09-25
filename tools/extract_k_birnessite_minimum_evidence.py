#!/usr/bin/env python3
"""Independently reconstruct the K-birnessite validation matrices from a TAR.

The archive is read member-by-member.  Native ``siesta.out`` files supply all
occupations; package JSON/CSV artefacts are comparison targets only.  The
calculation deliberately uses direct ``numpy.linalg.inv`` and never a
pseudoinverse.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import tarfile
from collections import defaultdict
from pathlib import Path

import numpy as np


NUMBER = re.compile(r"[-+]?(?:\d*\.\d+|\d+)(?:[Ee][-+]?\d+)?")
FAIL = re.compile(r"SCF_NOT_CONV|SCF:\s*not\s+converged|ABNORMAL_TERMINATION|MPI_Abort|pseudo_read:\s*ERROR", re.I)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_archive(path: Path) -> dict[str, bytes]:
    with tarfile.open(path, "r:gz") as archive:
        return {member.name: archive.extractfile(member).read() for member in archive.getmembers() if member.isfile()}


def text(files: dict[str, bytes], name: str, required: bool = True) -> str:
    if name not in files:
        if required:
            raise ValueError(f"Missing archive member: {name}")
        return ""
    return files[name].decode("utf-8", errors="ignore")


def events(output: str, n_sites: int) -> list[list[float]]:
    result: list[list[float]] = []
    current: list[float] | None = None
    for line in output.splitlines():
        if "hubbard_term: recalculating local occupations" in line:
            if current is not None:
                result.append(current)
            current = []
        elif current is not None and "Occupations:" in line:
            values = NUMBER.findall(line.split("Occupations:", 1)[1])
            if len(values) == 2:
                current.append(float(values[0]) + float(values[1]))
            elif len(values) >= 3:
                current.append(float(values[-1]))
    if current is not None:
        result.append(current)
    return [event for event in result if len(event) == n_sites]


def selected(output: str, mode: str, n_sites: int) -> tuple[np.ndarray, int, int]:
    complete = events(output, n_sites)
    if not complete:
        raise ValueError(f"No complete {n_sites}-site occupation event")
    index = 1 if mode == "BARE" else len(complete) - 1
    if index >= len(complete):
        raise ValueError("BARE second complete occupation event missing")
    return np.asarray(complete[index], dtype=float), index + 1, len(complete)


def matrix_text(values: np.ndarray) -> list[list[float]]:
    return np.asarray(values, dtype=float).tolist()


def direct_solution(raw: dict[str, np.ndarray], records: list[dict], labels: list[str], alpha: float) -> dict:
    n = len(labels)
    chi0_raw, chi_raw = np.empty((n, n)), np.empty((n, n))
    for column, label in enumerate(labels):
        def vector(mode: str, sign: float) -> np.ndarray:
            matches = [r for r in records if r.get("target") == label and r["mode"] == mode and abs(float(r["alpha_ev"]) - sign * alpha) < 1e-12]
            if len(matches) != 1:
                raise ValueError(f"Expected one {label}/{mode}/{sign * alpha:+.3f}; got {len(matches)}")
            return raw[matches[0]["id"]]
        chi0_raw[:, column] = (vector("BARE", 1.0) - vector("BARE", -1.0)) / (2 * alpha)
        chi_raw[:, column] = (vector("SCREENED", 1.0) - vector("SCREENED", -1.0)) / (2 * alpha)
    chi0, chi = (chi0_raw + chi0_raw.T) / 2, (chi_raw + chi_raw.T) / 2
    rank0, rank = int(np.linalg.matrix_rank(chi0)), int(np.linalg.matrix_rank(chi))
    if rank0 != n or rank != n:
        raise ValueError(f"Rank deficient response: rank(chi0)={rank0}, rank(chi)={rank}, n={n}")
    inv0, inv = np.linalg.inv(chi0), np.linalg.inv(chi)
    kernel = inv0 - inv
    identity = np.eye(n)
    return {
        "chi0_raw_electrons_per_eV": matrix_text(chi0_raw), "chi_raw_electrons_per_eV": matrix_text(chi_raw),
        "chi0_electrons_per_eV": matrix_text(chi0), "chi_electrons_per_eV": matrix_text(chi),
        "inv_chi0_eV": matrix_text(inv0), "inv_chi_eV": matrix_text(inv), "K_hubbard_eV": matrix_text(kernel),
        "U_by_site_eV": matrix_text(np.diag(kernel)), "U_Mn_mean_eV": float(np.diag(kernel).mean()),
        "rank_chi0": rank0, "rank_chi": rank,
        "condition_chi0": float(np.linalg.cond(chi0)), "condition_chi": float(np.linalg.cond(chi)),
        "antisymmetry_chi0": float(np.linalg.norm(chi0_raw - chi0_raw.T) / max(np.linalg.norm(chi0_raw), 1e-30)),
        "antisymmetry_chi": float(np.linalg.norm(chi_raw - chi_raw.T) / max(np.linalg.norm(chi_raw), 1e-30)),
        "inversion_residuals": {"chi0": float(np.linalg.norm(inv0 @ chi0 - identity)), "chi": float(np.linalg.norm(inv @ chi - identity))},
    }


def comparison(files: dict[str, bytes], root: str, level: str, solution: dict) -> dict:
    final = "alpha_linearity_result.json" if root.endswith("01_ALPHA_LINEARITY") else "campaign_result.json"
    packaged = json.loads(text(files, f"{root}/results/final/{final}"))
    package_level = packaged["by_alpha"][level]
    result: dict[str, object] = {"result_json": f"{root}/results/final/{final}", "tolerance": 1e-9}
    for field in ("U_Mn_mean_eV", "condition_chi0", "condition_chi"):
        delta = abs(float(solution[field]) - float(package_level[field]))
        result[field] = {"difference": delta, "within_tolerance": delta <= 1e-9}
    packaged_u = np.asarray([package_level["U_by_site_eV"][f"MnLR{i:02d}"] for i in range(6)], dtype=float)
    result["U_by_site_eV"] = {
        "max_abs_difference": float(np.max(np.abs(np.asarray(solution["U_by_site_eV"]) - packaged_u))),
        "within_tolerance": bool(np.allclose(solution["U_by_site_eV"], packaged_u, atol=1e-9, rtol=0)),
    }
    for name, ours in (("chi0", solution["chi0_electrons_per_eV"]), ("chi", solution["chi_electrons_per_eV"]), ("K_hubbard", solution["K_hubbard_eV"])):
        member = f"{root}/results/by_alpha/{level}/{name}.csv"
        packaged_matrix = np.loadtxt(io.StringIO(text(files, member)), delimiter=",")
        result[name] = {"source": member, "max_abs_difference": float(np.max(np.abs(np.asarray(ours) - packaged_matrix))), "within_tolerance": bool(np.allclose(ours, packaged_matrix, atol=1e-9, rtol=0))}
    return result


def audit_campaign(files: dict[str, bytes], root: str) -> dict:
    config, records = json.loads(text(files, f"{root}/campaign.json")), json.loads(text(files, f"{root}/runs/manifest.json"))
    labels = [f"MnLR{index:02d}" for index in range(6)]
    raw: dict[str, np.ndarray] = {}
    runs: dict[str, dict] = {}
    for record in records:
        run_id, mode = record["id"], record["mode"]
        base = f"{root}/runs/{run_id}"
        out, err = text(files, f"{base}/siesta.out"), text(files, f"{base}/siesta.err", False)
        occupations, chosen, complete = selected(out, mode, len(labels))
        marker_exists = f"{base}/0_NORMAL_EXIT" in files
        normal = marker_exists or bool(re.search(r"normal completion|job completed", out + err, re.I))
        failed = bool(FAIL.search(out + err))
        if not normal:
            raise ValueError(f"{root}/{run_id}: normal completion marker absent")
        if mode in {"REFERENCE", "SCREENED"} and failed:
            raise ValueError(f"{root}/{run_id}: failed required converged calculation")
        raw[run_id] = occupations
        runs[run_id] = {"mode": mode, "target": record.get("target"), "alpha_ev": record.get("alpha_ev"), "normal_completion": normal,
                        "unconverged_marker": failed, "complete_event_count": complete,
                        "selected_event": "second_complete" if mode == "BARE" else "last_complete", "selected_event_index_one_based": chosen,
                        "selected_occupations_electrons": occupations.tolist()}
    levels = sorted({abs(float(record["alpha_ev"])) for record in records if record["mode"] != "REFERENCE"})
    by_alpha = {}
    for alpha in levels:
        level = f"{alpha:.3f}"
        solution = direct_solution(raw, records, labels, alpha)
        solution["package_comparison"] = comparison(files, root, level, solution)
        by_alpha[level] = solution
    return {"campaign_id": config["campaign_id"], "purpose": config.get("purpose"), "configuration": {key: config.get(key) for key in ("material", "formula", "atom_count", "basis", "kgrid", "correlated_subspace", "site_classes", "magnetic_initialization_muB", "run_count", "execution", "no_symmetry_reduction")},
            "labels": labels, "protocol": {"occupation_source": "native SIESTA siesta.out", "occupation_selector": "BARE=second complete semantic event; REFERENCE/SCREENED=last complete semantic event", "finite_difference": "[n_I(+alpha_J)-n_I(-alpha_J)]/(2 alpha_J)", "symmetrization": "(A+A^T)/2", "kernel": "inv(chi0)-inv(chi)", "inverse": "numpy.linalg.inv direct inverse; pseudoinverse prohibited"},
            "runs": runs, "by_alpha": by_alpha}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("--sha256-file", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    actual = sha256(args.archive)
    expected = None
    if args.sha256_file:
        expected = args.sha256_file.read_text(encoding="utf-8").split()[0].lower()
        if actual != expected:
            raise SystemExit(f"SHA256 mismatch: expected {expected}, got {actual}")
    files = load_archive(args.archive)
    roots = sorted({name.split("/", 1)[0] for name in files if name.endswith("/campaign.json")})
    if len(roots) != 5:
        raise SystemExit(f"Expected five campaigns; found {roots}")
    audit = {"evidence_type": "K-birnessite minimum targeted-validation independent mathematical audit", "archive": {"filename": args.archive.name, "sha256": actual, "sha256_verified": expected is not None, "members": len(files), "native_siesta_outputs": sum(name.endswith("/siesta.out") for name in files), "normal_exit_markers": sum(name.endswith("/0_NORMAL_EXIT") for name in files)},
             "campaigns": {root: audit_campaign(files, root) for root in roots}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
