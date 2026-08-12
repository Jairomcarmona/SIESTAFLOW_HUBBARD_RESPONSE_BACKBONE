#!/usr/bin/env python3
"""Extract compact, independently reconstructed Cu3N LR-U evidence from a TAR.

The archive is read member-by-member.  Native SIESTA output is the primary
source for occupations and convergence gates; packaged JSON files are used
only for an explicit comparison report.  No pseudoinverse is used.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import tarfile
from pathlib import Path
from typing import Any

import numpy as np


NUMBER = r"[-+]?(?:\d*\.\d+|\d+)(?:[Ee][-+]?\d+)?"
OCCUPATION_RE = re.compile(NUMBER)
UNCONVERGED_RE = re.compile(
    r"SCF_NOT_CONV|SCF:\s*not\s+converged|ABNORMAL_TERMINATION|MPI_Abort",
    re.IGNORECASE,
)


def read_member(store: dict[str, bytes], name: str, required: bool = True) -> bytes:
    if name not in store:
        if required:
            raise ValueError(f"missing archive member: {name}") from None
        return b""
    return store[name]


def occupation_events(text: str) -> list[list[float]]:
    """Parse complete semantic Hubbard occupation events from SIESTA output.

    Cu3N is non-spin-polarized, so SIESTA prints two spin-channel values and
    their sum is the scalar occupation.  For a three-value line (spin-
    polarized output), the final value is the total, matching the production
    campaign parser.
    """
    events: list[list[float]] = []
    current: list[float] | None = None
    for line in text.splitlines():
        if "hubbard_term: recalculating local occupations" in line:
            if current is not None:
                events.append(current)
            current = []
            continue
        if current is None or "Occupations:" not in line:
            continue
        values = OCCUPATION_RE.findall(line.split("Occupations:", 1)[1])
        if len(values) == 2:
            current.append(float(values[0]) + float(values[1]))
        elif len(values) >= 3:
            current.append(float(values[-1]))
        else:
            raise ValueError(f"unrecognized Occupations line: {line!r}")
    if current is not None:
        events.append(current)
    return events


def selected_event(text: str, mode: str, n_sites: int) -> tuple[list[float], int, list[int]]:
    all_events = occupation_events(text)
    complete = [event for event in all_events if len(event) == n_sites]
    if not complete:
        raise ValueError(f"no complete {n_sites}-site Hubbard occupation event")
    if mode == "BARE":
        if len(complete) < 2:
            raise ValueError("BARE second complete occupation event missing")
        index = 1
    else:
        index = len(complete) - 1
    return complete[index], index + 1, [len(event) for event in all_events]


def translate(vector: np.ndarray, shift: tuple[int, int, int], side: int) -> np.ndarray:
    n = 3 * side**3
    output = np.empty(n, dtype=float)
    for source_t in range(side**3):
        i, j, k = source_t // (side * side), (source_t // side) % side, source_t % side
        destination_t = (
            ((i + shift[0]) % side) * side * side
            + ((j + shift[1]) % side) * side
            + (k + shift[2]) % side
        )
        for parent in range(3):
            output[3 * destination_t + parent] = vector[3 * source_t + parent]
    return output


def reconstruct(columns: list[np.ndarray], side: int) -> np.ndarray:
    n = 3 * side**3
    shifts = [(i, j, k) for i in range(side) for j in range(side) for k in range(side)]
    matrix = np.empty((n, n), dtype=float)
    for translation_index, shift in enumerate(shifts):
        for parent in range(3):
            matrix[:, 3 * translation_index + parent] = translate(columns[parent], shift, side)
    return matrix


def array_json(value: np.ndarray) -> list[Any]:
    return np.asarray(value, dtype=float).tolist()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def finite_difference(raw: dict[str, np.ndarray], prefix: str, mode: str, alpha: float) -> np.ndarray:
    return (raw[f"{prefix}_{mode}_PLUS"] - raw[f"{prefix}_{mode}_MINUS"]) / (2.0 * alpha)


def reference_fdf_parameters(text: str) -> dict[str, Any]:
    """Recover compact numerical settings from the materialized reference FDF."""
    def scalar(pattern: str) -> str | None:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        return match.group(1) if match else None

    kgrid: list[int] = []
    in_kgrid = False
    for line in text.splitlines():
        if line.strip().lower() == "%block kgrid_monkhorst_pack":
            in_kgrid = True
            continue
        if in_kgrid and line.strip().lower() == "%endblock kgrid_monkhorst_pack":
            break
        if in_kgrid:
            values = OCCUPATION_RE.findall(line)
            if len(values) >= 2:
                row = len(kgrid)
                diagonal = values[row] if row < len(values) else values[0]
                kgrid.append(int(float(diagonal)))
    return {
        "number_of_atoms": int(scalar(r"^NumberOfAtoms\s+(\d+)") or 0),
        "basis": scalar(r"^PAO\.BasisSize\s+([^\s]+)"),
        "energy_shift": scalar(r"^PAO\.EnergyShift\s+(.+)$"),
        "mesh_cutoff": scalar(r"^MeshCutoff\s+(.+)$"),
        "kgrid": kgrid[:3],
        "projector_method": scalar(r"^DFTU\.ProjectorGenerationMethod\s+(.+)$"),
        "potential_shift": scalar(r"^DFTU\.PotentialShift\s+(.+)$"),
        "max_scf_iterations": scalar(r"^MaxSCFIterations\s+(.+)$"),
        "scf_must_converge": scalar(r"^SCF\.MustConverge\s+(.+)$"),
    }


def compare_numbers(actual: Any, packaged: Any, tolerance: float = 1e-9) -> dict[str, Any]:
    if actual is None or packaged is None:
        return {"available": False}
    difference = abs(float(actual) - float(packaged))
    return {"available": True, "max_abs_difference": difference, "within_tolerance": difference <= tolerance}


def audit_campaign(store: dict[str, bytes], root: str) -> dict[str, Any]:
    config = json.loads(read_member(store, f"{root}/campaign.json"))
    manifest = json.loads(read_member(store, f"{root}/runs/manifest.json"))
    n_sites = int(config["n_hubbard_sites"])
    side = int(config["supercell"][0])
    alpha = float(config["alpha_ev"])
    raw: dict[str, np.ndarray] = {}
    run_audit: dict[str, Any] = {}
    reference_fdf_name = f"{root}/runs/00_REFERENCE/siesta.fdf"
    fdf_params = reference_fdf_parameters(read_member(store, reference_fdf_name).decode("utf-8", errors="ignore"))
    site_map_name = f"{root}/geometry/site_map.json"
    site_map = json.loads(read_member(store, site_map_name, required=False) or b"[]")

    for record in manifest:
        run_id = record["id"]
        mode = record["mode"]
        run_root = f"{root}/runs/{run_id}"
        out_name = f"{run_root}/siesta.out"
        err_name = f"{run_root}/siesta.err"
        out = read_member(store, out_name).decode("utf-8", errors="ignore")
        err = read_member(store, err_name, required=False).decode("utf-8", errors="ignore")
        marker_name = f"{run_root}/0_NORMAL_EXIT"
        marker = read_member(store, marker_name, required=False).decode("utf-8", errors="ignore")
        status_text = out + "\n" + err
        event, selected_index, event_lengths = selected_event(out, mode, n_sites)
        normal = bool(marker.strip()) or bool(re.search(r"job completed|normal completion", status_text, re.I))
        unconverged = bool(UNCONVERGED_RE.search(status_text))
        if not normal:
            raise ValueError(f"{root}/{run_id}: normal completion missing")
        if mode in {"REFERENCE", "SCREENED"} and unconverged:
            raise ValueError(f"{root}/{run_id}: required SCF convergence missing")
        raw[run_id] = np.asarray(event, dtype=float)
        run_audit[run_id] = {
            "mode": mode,
            "source": {"stdout": out_name, "stderr": err_name, "normal_exit": marker_name},
            "normal_completion": normal,
            "unconverged_marker": unconverged,
            "complete_event_count": sum(length == n_sites for length in event_lengths),
            "all_event_lengths": event_lengths,
            "selected_event": "second_complete" if mode == "BARE" else "last_complete",
            "selected_event_index_one_based": selected_index,
            "selected_occupations_electrons": event,
        }

    bare_columns = [finite_difference(raw, label, "BARE", alpha) for label in ("10_X", "20_Y", "30_Z")]
    screened_columns = [finite_difference(raw, label, "SCREENED", alpha) for label in ("10_X", "20_Y", "30_Z")]
    chi0_raw = reconstruct(bare_columns, side)
    chi_raw = reconstruct(screened_columns, side)
    chi0 = (chi0_raw + chi0_raw.T) / 2.0
    chi = (chi_raw + chi_raw.T) / 2.0
    rank0 = int(np.linalg.matrix_rank(chi0))
    rank = int(np.linalg.matrix_rank(chi))
    package_result_name = f"{root}/results/final/campaign_result.json"
    packaged = json.loads(read_member(store, package_result_name, required=False) or b"null")

    evidence: dict[str, Any] = {
        "campaign_id": config["campaign_id"],
        "configuration": {
            "material": config.get("material"),
            "functional": config.get("functional"),
            "basis": config.get("basis") or fdf_params.get("basis"),
            "kgrid": config.get("kgrid") or fdf_params.get("kgrid"),
            "supercell": config.get("supercell"),
            "n_hubbard_sites": n_sites,
            "alpha_ev": alpha,
            "projector": config.get("projector"),
        },
        "source": {
            "campaign_json": f"{root}/campaign.json",
            "manifest": f"{root}/runs/manifest.json",
            "reference_fdf": reference_fdf_name,
            "site_map": site_map_name,
        },
        "site_map": site_map,
        "reference_fdf_parameters": fdf_params,
        "protocol": {
            "occupation_source": "native SIESTA siesta.out",
            "non_spin_polarized_occupation": "sum of the two values after Occupations:",
            "spin_polarized_occupation": "third value after Occupations:",
            "bare_selector": "second complete Hubbard occupation event",
            "reference_screened_selector": "last complete Hubbard occupation event",
            "finite_difference": "(n(+alpha)-n(-alpha))/(2*alpha)",
            "matrix_reconstruction": "three representative X/Y/Z response columns translated over the supercell",
            "symmetrization": "(A + A.T)/2",
            "inverse": "numpy.linalg.inv; direct inverse only; no pseudoinverse",
            "kernel": "inv(chi0) - inv(chi)",
            "reported_U": "mean of diagonal(kernel), in eV",
        },
        "runs": run_audit,
        "response_columns_electrons_per_eV": {
            "chi0_X": array_json(bare_columns[0]),
            "chi0_Y": array_json(bare_columns[1]),
            "chi0_Z": array_json(bare_columns[2]),
            "chi_X": array_json(screened_columns[0]),
            "chi_Y": array_json(screened_columns[1]),
            "chi_Z": array_json(screened_columns[2]),
        },
        "matrices": {
            "chi0_raw_electrons_per_eV": array_json(chi0_raw),
            "chi_raw_electrons_per_eV": array_json(chi_raw),
            "chi0_electrons_per_eV": array_json(chi0),
            "chi_electrons_per_eV": array_json(chi),
        },
        "rank_chi0": rank0,
        "rank_chi": rank,
        "condition_chi0": float(np.linalg.cond(chi0)),
        "condition_chi": float(np.linalg.cond(chi)),
        "singular_values_chi0": array_json(np.linalg.svd(chi0, compute_uv=False)),
        "singular_values_chi": array_json(np.linalg.svd(chi, compute_uv=False)),
        "relative_antisymmetry_chi0_raw": float(np.linalg.norm(chi0_raw - chi0_raw.T) / np.linalg.norm(chi0_raw)),
        "relative_antisymmetry_chi_raw": float(np.linalg.norm(chi_raw - chi_raw.T) / np.linalg.norm(chi_raw)),
        "packaged_result_comparison": {},
    }
    if rank0 == n_sites and rank == n_sites:
        inv0 = np.linalg.inv(chi0)
        inv = np.linalg.inv(chi)
        kernel = inv0 - inv
        diagonal = np.diag(kernel)
        evidence["matrices"].update(
            {
                "chi0_inverse_eV": array_json(inv0),
                "chi_inverse_eV": array_json(inv),
                "K_hubbard_kernel_eV": array_json(kernel),
                "U_by_site_eV": array_json(diagonal),
            }
        )
        evidence.update(
            {
                "status": "PASS",
                "U_Cu_eV": float(diagonal.mean()),
                "rank_full": True,
                "inversion_residual_chi0": float(np.linalg.norm(inv0 @ chi0 - np.eye(n_sites))),
                "inversion_residual_chi": float(np.linalg.norm(inv @ chi - np.eye(n_sites))),
                "max_site_deviation_from_mean_eV": float(np.max(np.abs(diagonal - diagonal.mean()))),
            }
        )
    else:
        evidence.update({"status": "FAIL", "rank_full": False, "notes": ["singular response matrix; direct U not computed"]})
    if packaged:
        for key in ("U_Cu_eV", "rank_chi0", "rank_chi", "condition_chi0", "condition_chi"):
            if key in packaged and key in evidence:
                value = evidence[key]
                evidence["packaged_result_comparison"][key] = (
                    {"actual": value, "packaged": packaged[key]}
                    if key.startswith("rank")
                    else {"actual": value, "packaged": packaged[key], **compare_numbers(value, packaged[key])}
                )
    return evidence


def markdown_summary(summary: dict[str, Any]) -> str:
    lines = [
        "# Cu3N LR-U mathematical evidence extracted from native SIESTA output",
        "",
        f"Archive: `{summary['archive']}`",
        "",
        "This report was generated by the independent streaming parser. Occupations were parsed from native `siesta.out`; the packaged result JSON was used only for comparison. Direct matrix inversion was used; no pseudoinverse was used.",
        "",
        "| Campaign | SC | basis | k-grid | U (eV) | rank chi0 | rank chi | cond chi0 | cond chi | status |",
        "|---|---:|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for item in summary["campaigns"]:
        c = item["configuration"]
        supercell = "".join(map(str, c["supercell"])) if c.get("supercell") else "?"
        kgrid = "x".join(map(str, c["kgrid"])) if c.get("kgrid") else "?"
        lines.append(
            f"| `{item['campaign_id']}` | `{supercell}` | {c.get('basis') or '?'} | `{kgrid}` | {item.get('U_Cu_eV', float('nan')):.10f} | {item['rank_chi0']} | {item['rank_chi']} | {item['condition_chi0']:.6g} | {item['condition_chi']:.6g} | {item['status']} |"
        )
    lines += [
        "",
        "## Reconstruction",
        "",
        "For each campaign, the parser selects the second complete Hubbard event for BARE and the last complete event for REFERENCE/SCREENED. Response columns are finite differences with denominator `2 alpha`; the X/Y/Z columns are translated over the supercell. It forms `chi0=(chi0_raw+chi0_raw.T)/2` and `chi=(chi_raw+chi_raw.T)/2`, then computes `K = inv(chi0) - inv(chi)` and reports the mean diagonal as U.",
        "",
        "Per-campaign JSON files contain the selected occupation vectors, response columns, raw/symmetrized matrices, direct inverses, kernel, site-resolved U, ranks, condition numbers, inversion residuals, convergence gates, and source member paths.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    # Read only the compact audit members in one sequential pass.  This is
    # important for gzip TARs: repeated random extraction would restart the
    # decompressor for every SIESTA output.
    store: dict[str, bytes] = {}
    with tarfile.open(args.archive, "r:gz") as archive:
        for member in archive:
            name = member.name
            if not (
                name.endswith("/campaign.json")
                or name.endswith("/runs/manifest.json")
                or name.endswith("/results/final/campaign_result.json")
                or name.endswith("/runs/00_REFERENCE/siesta.fdf")
                or name.endswith("/geometry/site_map.json")
                or name.endswith("/siesta.out")
                or name.endswith("/siesta.err")
                or name.endswith("/0_NORMAL_EXIT")
            ):
                continue
            handle = archive.extractfile(member)
            if handle is not None:
                store[name] = handle.read()
    roots = sorted({name.split("/", 1)[0] for name in store if name.endswith("/campaign.json")})
    campaigns = [audit_campaign(store, root) for root in roots]
    summary = {
        "audit": "cu3n_native_siesta_streaming_parser",
        "parser": Path(__file__).name,
        "archive": args.archive.name,
        "archive_sha256": sha256_file(args.archive),
        "campaign_count": len(campaigns),
        "campaigns": campaigns,
    }
    (args.output_dir / "cu3n_mathematical_evidence.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    for campaign in campaigns:
        safe = campaign["campaign_id"] + ".json"
        (args.output_dir / safe).write_text(json.dumps(campaign, indent=2) + "\n", encoding="utf-8")
    (args.output_dir / "README.md").write_text(markdown_summary(summary), encoding="utf-8")
    print(args.output_dir / "README.md")
    print(args.output_dir / "cu3n_mathematical_evidence.json")


if __name__ == "__main__":
    main()
