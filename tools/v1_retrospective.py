"""Read-only V1 checks; archived reconstruction is development evidence.

No U, condition number, experiment or response-dependent tolerance enters any
comparison. The report retains all raw scalar data and labels missing shadows.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from fractions import Fraction
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

import numpy as np

from hubbardflow.domain.response_error_budget import (
    BoundKind,
    ElementSeries,
    NoiseModel,
    PointObservation,
    decompose,
)
from hubbardflow.domain.response_reconstruction import (
    ObservableKind,
    ReconstructionClass,
    ScalarPermutation,
    reciprocity_residuals,
    reconstruct_matrix,
    symmetrization_report,
)
from hubbardflow.domain.symmetry_reduction import ResponseMode
from hubbardflow.siesta_backend.occupation_precision import read_printed_matrix_trace_precision
from hubbardflow.siesta_backend.siesta542_bare_profile import Siesta542PotentialShiftHamiltonianProfile
from hubbardflow.siesta_backend.siesta542_screened_selection import select_converged_screened_event


class V1Status(str, Enum):
    DEVELOPMENT_ONLY = "DEVELOPMENT_ONLY"
    INDEPENDENT_SHADOW_NOT_AVAILABLE = "INDEPENDENT_SHADOW_NOT_AVAILABLE"


@dataclass(frozen=True)
class V1Report:
    campaigns: tuple[Mapping[str, object], ...]
    sources: tuple[tuple[str, str], ...]

    def to_mapping(self) -> dict[str, object]:
        return {
            "schema": "hubbardflow.v1_retrospective.v1",
            "status": V1Status.DEVELOPMENT_ONLY.value,
            "qualification": "No production qualification; SCF ESTIMATE and V2–V4 unavailable",
            "campaigns": list(self.campaigns),
            "sources_sha256": dict(self.sources),
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> V1Report:
        if value["schema"] != "hubbardflow.v1_retrospective.v1":
            raise ValueError("unsupported V1 schema")
        json.dumps(value, allow_nan=False)
        return cls(tuple(value["campaigns"]), tuple(sorted(value["sources_sha256"].items())))


def _load(root: Path, name: str, sources: dict[str, str]) -> dict[str, Any]:
    data = (root / name).read_bytes()
    sources[name] = sha256(data).hexdigest()
    value: dict[str, Any] = json.loads(data, parse_constant=lambda token: _bad_constant(token))
    return value


def _bad_constant(token: str) -> None:
    raise ValueError(f"nonfinite JSON token: {token}")


def _operations(permutations: Sequence[tuple[int, ...]]) -> tuple[ScalarPermutation, ...]:
    return tuple(ScalarPermutation(p) for p in permutations)


def _slopes(
    values: Sequence[Sequence[float]], widths: Sequence[Sequence[float]], alpha_ev: float, mode: str
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    slopes, radii = [], []
    for i, (minus, plus) in enumerate(zip(values[0], values[1], strict=True)):
        series = ElementSeries(
            "representative",
            ResponseMode(mode),
            str(i),
            0.0,
            0.0,
            (
                PointObservation(-alpha_ev, minus, widths[0][i]),
                PointObservation(alpha_ev, plus, widths[1][i]),
            ),
        )
        dec = decompose(series, NoiseModel(0.0, 0.0, BoundKind.BOUND))
        # Preserve the historical NumPy arithmetic for exact script comparison;
        # TASK2 decimal-rational arithmetic supplies the bound independently.
        slopes.append((plus - minus) / (2 * alpha_ev))
        radii.append(dec.slope_noise_e_per_ev[0])
    return tuple(slopes), tuple(radii)


def _compare(
    direct: Sequence[float],
    representative: Sequence[float],
    direct_bound: Sequence[float],
    representative_bound: Sequence[float],
    permutation: tuple[int, ...],
    alpha_ev: float,
    mode: str,
) -> dict[str, object]:
    predicted, bound = np.empty(len(direct)), np.empty(len(direct))
    for i, j in enumerate(permutation):
        predicted[j] = representative[i]
        bound[j] = direct_bound[j] + representative_bound[i]
    residual = np.asarray(direct) - predicted
    difference = float(np.max(np.abs(residual)))
    return {
        "mode": mode,
        "alpha_ev": alpha_ev,
        "direct_column_e_per_ev": list(direct),
        "reconstructed_column_e_per_ev": predicted.tolist(),
        "signed_difference_e_per_ev": residual.tolist(),
        "max_abs_difference_e_per_ev": difference,
        "alpha_scaled_difference_e": difference * alpha_ev,
        "print_bound_kind": BoundKind.BOUND.value,
        "print_bounds_e_per_ev": bound.tolist(),
        "within_print_bounds": bool(np.all(np.abs(residual) <= bound)),
        "scf_estimate": "NOT_AVAILABLE",
        "total_fd_ebq_qualification": "NOT_ESTABLISHED",
    }


def _oxide(root: Path, material: str, name: str, sources: dict[str, str]) -> dict[str, object]:
    rows = _load(root, name, sources)["response_observation_dataset"]["rows"]
    data, widths = {}, {}
    for row in rows:
        for observed in row["observed_sites"]:
            for mode in ("BARE", "SCREENED"):
                key = (mode, row["perturbed_site_index"], observed["observed_site_index"], row["alpha_eV"])
                if key in data:
                    raise ValueError("duplicate archived observation")
                data[key] = observed["occupations_electron"][mode.lower()]
                widths[key] = observed["occupation_half_widths_electron"][mode.lower()]
    comparisons, matrices = [], []
    for mode in ("BARE", "SCREENED"):
        for a in sorted({key[3] for key in data if key[3] > 0}):
            columns, budgets = [], []
            for j in (0, 1):
                values = [[data[(mode, j, i, sign * a)] for i in (0, 1)] for sign in (-1, 1)]
                bounds = [[widths[(mode, j, i, sign * a)] for i in (0, 1)] for sign in (-1, 1)]
                column, budget = _slopes(values, bounds, a, mode)
                columns.append(column)
                budgets.append(budget)
            comparison = _compare(columns[1], columns[0], budgets[1], budgets[0], (1, 0), a, mode)
            comparison.update(
                chi00_minus_chi11=columns[0][0] - columns[1][1],
                chi01_minus_chi10=columns[1][0] - columns[0][1],
                abs_chi00=abs(columns[0][0]),
            )
            comparisons.append(comparison)
            ops = _operations(((0, 1), (1, 0)))
            reconstructed = reconstruct_matrix(
                {0: columns[0]},
                (ReconstructionClass((0, 1), 0, ((0, 0), (1, 1))),),
                ops,
                observable=ObservableKind.SPIN_SUMMED_TRACE,
            )
            matrices.append(
                {
                    "mode": mode,
                    "alpha_ev": a,
                    "direct_raw": [list(pair) for pair in zip(*columns, strict=True)],
                    "direct_reciprocity": reciprocity_residuals(
                        tuple(zip(*columns, strict=True))
                    ).to_mapping(),
                    "direct_symmetrization": symmetrization_report(
                        tuple(zip(*columns, strict=True))
                    ).to_mapping(),
                    "reconstructed": reconstructed.to_mapping(),
                    "symmetrization": symmetrization_report(reconstructed.raw_matrix).to_mapping(),
                }
            )
    return {
        "material": material,
        "eps": -1,
        "raw_observations": rows,
        "comparisons": comparisons,
        "matrices": matrices,
        "status": V1Status.DEVELOPMENT_ONLY.value,
    }


def _mno(root: Path, sources: dict[str, str]) -> dict[str, object]:
    base = "campaigns/mno_afmii_strict_lr_v3r2"
    name = base + "/results/response-matrix-foreground-recovery-v4/response-receipt.json"
    records = _load(root, name, sources)["records"]
    site_name = base + "/geometry/site_map.json"
    sources[site_name] = sha256((root / site_name).read_bytes()).hexdigest()
    sites = json.loads((root / site_name).read_text())
    indices = [site["index"] for site in sites]
    if any(type(index) is not int for index in indices) or sorted(indices) != list(range(len(sites))):
        raise ValueError("MnO site_map requires unique contiguous integer indices")
    sites = sorted(sites, key=lambda site: site["index"])
    positions = [tuple(Fraction(str(x)) for x in site["fractional_supercell"]) for site in sites]
    if len(set(positions)) != len(positions):
        raise ValueError("MnO site_map contains duplicate correlated positions")
    translation = tuple(b - a for a, b in zip(positions[0], positions[1], strict=True))
    shifted = [
        tuple((p + t) % 1 for p, t in zip(position, translation, strict=True)) for position in positions
    ]
    permutation = tuple(positions.index(position) for position in shifted)
    comparisons, matrices = [], []
    for mode in ("BARE", "SCREENED"):
        for a in sorted({r["alpha_ev"] for r in records.values() if r.get("alpha_ev", 0) > 0}):
            columns, budgets = [], []
            for role in ("A", "B"):
                selected = []
                for sign in (-1, 1):
                    matches = [
                        r
                        for r in records.values()
                        if r.get("role") == role and r["mode"] == mode and r["alpha_ev"] == sign * a
                    ]
                    if len(matches) != 1:
                        raise ValueError(f"MnO requires exactly one {role}/{mode}/{sign * a} record")
                    selected.append(matches[0])
                values, widths = [], []
                for record in selected:
                    output_name = str(Path(name).parent / record["output"]).replace("\\", "/")
                    content = (root / output_name).read_bytes()
                    sources[output_name] = sha256(content).hexdigest()
                    if sources[output_name] != record["sha256"]:
                        raise ValueError(f"MnO receipt output digest mismatch: {output_name}")
                    text = content.decode()
                    event = (
                        Siesta542PotentialShiftHamiltonianProfile().select_response(text).response_event
                        if mode == "BARE"
                        else select_converged_screened_event(text)
                    )
                    measured = read_printed_matrix_trace_precision(text, event)
                    ordered = [measured[i] for i in sorted(measured)]
                    archived = tuple(record["occupations_e"])
                    if (
                        tuple(
                            atom.trace_total for atom in sorted(event.atoms, key=lambda atom: atom.atom_index)
                        )
                        != archived
                    ):
                        raise ValueError(f"MnO archived matrix trace mismatch: {output_name}")
                    values.append(archived)
                    widths.append(tuple(v.half_width for v in ordered))
                column, budget = _slopes(values, widths, a, mode)
                columns.append(column)
                budgets.append(budget)
            comparison = _compare(columns[1], columns[0], budgets[1], budgets[0], permutation, a, mode)
            comparison["legacy_script_comparison_bound_e_per_ev"] = 1e-5 / a
            comparison["legacy_bound_note"] = (
                "Reference-script diagnostic only; not an audited bound (10 diagonal tokens)"
            )
            comparisons.append(comparison)
            maps: list[ReconstructionClass] = []
            permutations: list[tuple[int, ...]] = []
            for representative in (0, 1):
                members = tuple(
                    i
                    for i, site in enumerate(sites)
                    if site["parent_sublattice"] == sites[representative]["parent_sublattice"]
                )
                pairs = []
                for member in members:
                    shift = tuple(
                        b - a for a, b in zip(positions[representative], positions[member], strict=True)
                    )
                    pi = tuple(
                        positions.index(tuple((p + t) % 1 for p, t in zip(position, shift, strict=True)))
                        for position in positions
                    )
                    pairs.append((member, len(permutations)))
                    permutations.append(pi)
                maps.append(ReconstructionClass(members, representative, tuple(pairs)))
            raw = reconstruct_matrix(
                {0: columns[0], 1: columns[1]},
                maps,
                _operations(permutations),
                observable=ObservableKind.SPIN_SUMMED_TRACE,
            )
            matrices.append(
                {
                    "mode": mode,
                    "alpha_ev": a,
                    "reconstructed": raw.to_mapping(),
                    "symmetrization": symmetrization_report(raw.raw_matrix).to_mapping(),
                }
            )
    return {
        "material": "MnO",
        "eps": -1,
        "correlated_permutation": list(permutation),
        "geometry_limitation": "Historical map uses Mn only; oxygen mapping is assumed, not qualified",
        "raw_observations": records,
        "comparisons": comparisons,
        "matrices": matrices,
        "status": V1Status.DEVELOPMENT_ONLY.value,
    }


def _cu3n(root: Path, sources: dict[str, str]) -> dict[str, object]:
    name = "docs/evidence/cu3n_mathematical_20260812/cu3n_mathematical_evidence.json"
    evidence = _load(root, name, sources)
    retained = []
    for campaign in evidence["campaigns"]:
        raw = campaign["matrices"]
        retained.append(
            {
                "campaign_id": campaign["campaign_id"],
                "raw_runs": campaign["runs"],
                "representative_columns": campaign["response_columns_electrons_per_eV"],
                "archived_matrices": raw,
                "protocol": campaign["protocol"],
                "computed_columns": ["X", "Y", "Z"],
                "missing_independent_shadow_columns": campaign["configuration"]["n_hubbard_sites"] - 3,
                "print_budget": "NOT_AVAILABLE: compact archive omits decimal tokens",
                "bare_semantics": "Historical second-complete event; not source-audited frozen-Hamiltonian BARE",
            }
        )
    return {
        "material": "Cu3N",
        "status": V1Status.INDEPENDENT_SHADOW_NOT_AVAILABLE.value,
        "campaigns": retained,
        "comparisons": [],
        "limitation": "Reconstructed CSV equality is not independent shadow evidence",
    }


def build_report(root: Path) -> V1Report:
    """Reproduce the reference arithmetic without modifying archived campaigns."""
    sources: dict[str, str] = {}
    campaigns = (
        _oxide(
            root,
            "CoO",
            "results/stage-ub-v6-observables/coo-u-b-campaigns/stageubv6-coo-a0/lr_u_analysis.v3.json",
            sources,
        ),
        _oxide(root, "NiO", "campaigns/nio_pbe_p5_20260928/results/lr_u_analysis.v3.json", sources),
        _mno(root, sources),
        _cu3n(root, sources),
    )
    return V1Report(campaigns, tuple(sorted(sources.items())))


def markdown(report: V1Report) -> str:
    lines = [
        "# V1 retrospective reconstruction",
        "",
        "Development evidence only. No production qualification.",
        "",
        "Print BOUNDs are added componentwise using TASK2; SCF ESTIMATE is NOT_AVAILABLE.",
        "",
        "| System | Mode | α (eV) | max shadow difference (e/eV) | α × difference (e) | print BOUND | Pass |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for campaign in report.campaigns:
        for comparison in cast(Sequence[Mapping[str, Any]], campaign["comparisons"]):
            row = comparison
            lines.append(
                f"| {campaign['material']} | {row['mode']} | {row['alpha_ev']:.3f} | "
                f"{row['max_abs_difference_e_per_ev']:.6e} | {row['alpha_scaled_difference_e']:.6e} | "
                f"{max(row['print_bounds_e_per_ev']):.6e} | {row['within_print_bounds']} |"
            )
    lines += [
        "",
        "MnO receipt occupations are sums of ten printed matrix diagonal entries (5 decimals).",
        "Each occupation has BOUND 5e-5 e, giving 1e-4/α for direct plus reconstructed central slopes.",
        "The reference script's 1e-5/α comparison is retained in JSON as a legacy diagnostic; it is smaller by ×10.",
        "MnO α × discrepancy is around 1.5e-5 e: an absolute occupation-scale discrepancy, consistent with 1/α slope scaling.",
        "This scaling does not identify an SCF cause or establish an SCF ESTIMATE.",
        "",
        "Cu3N has X/Y/Z representative columns and reconstructed matrices; independent translated shadows are absent (21 in SC222, 78 in SC333).",
        "Compact Cu3N evidence omits printed tokens; no rounding budget is guessed. Historical BARE selection is reported.",
        "MnO historical permutation uses only Mn positions and assumes oxygen mapping; no F1–F8 qualification is implied.",
        "CoO/NiO exchange and spin-flip comparisons are candidates; flags remain disabled.",
        "",
        "Raw observations, reconstructed and symmetrized data, correction norms and source digests are retained in JSON.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--markdown", type=Path, required=True)
    args = parser.parse_args()
    report = build_report(args.root)
    args.json.write_text(
        json.dumps(report.to_mapping(), sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    args.markdown.write_text(markdown(report), encoding="utf-8")


if __name__ == "__main__":
    main()
