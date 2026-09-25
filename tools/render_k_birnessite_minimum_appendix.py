#!/usr/bin/env python3
"""Render a readable, complete numerical appendix from the birnessite audit."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def vector(values: list[float]) -> str:
    return "[" + ", ".join(f"{value:.8f}" for value in values) + "]"


def matrix(title: str, values: list[list[float]], unit: str, labels: list[str]) -> str:
    data = np.asarray(values, dtype=float)
    header = " " * 10 + " ".join(f"{label:>10}" for label in labels)
    lines = [header]
    for label, row in zip(labels, data, strict=True):
        lines.append(f"{label:>9} " + " ".join(f"{value:>10.6f}" for value in row))
    return f"### {title}\n\nUnits: {unit}.\n\n```text\n" + "\n".join(lines) + "\n```\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    audit = json.loads(args.source.read_text(encoding="utf-8"))
    lines = [
        "# K-birnessite LR-U minimum-validation: complete numerical appendix",
        "",
        "This appendix is rendered from the independently reconstructed native-output audit "
        f"[`{args.source.name}`](../../{args.source.name}). It contains all response matrices used in the "
        "direct-inversion calculation. The raw audit JSON also preserves the selected occupation vector and "
        "semantic-event selection for every one of the 173 native SIESTA outputs.",
        "",
        "## Numerical convention",
        "",
        "For Hubbard sites $I,J$, the displayed matrices use the central differences ",
        "$\\chi^0_{IJ}=[n_I^{bare}(+\\alpha_J)-n_I^{bare}(-\\alpha_J)]/(2\\alpha_J)$ and "
        "$\\chi_{IJ}=[n_I^{screened}(+\\alpha_J)-n_I^{screened}(-\\alpha_J)]/(2\\alpha_J)$. "
        "The raw response is symmetrized as $A=(A_{raw}+A_{raw}^T)/2$. "
        "The Hubbard kernel is $K=(\\chi^0)^{-1}-\\chi^{-1}$ and $U_I=K_{II}$. "
        "All inversions are direct; no pseudoinverse is used.",
        "",
        "`BARE` selects the second complete semantic Hubbard-occupation event. REFERENCE and SCREENED "
        "select the last complete event. For this spin-polarized material, the final number after "
        "`Occupations:` is the total Mn-3d occupation.",
        "",
    ]
    for campaign, data in audit["campaigns"].items():
        labels = data["labels"]
        lines += [f"## {campaign}", "", f"Purpose: {data.get('purpose') or 'not declared'}", ""]
        for level, solution in data["by_alpha"].items():
            matrices = solution
            lines += [f"### $|\\alpha|={level}$ eV", ""]
            lines += [
                f"- $\\overline U_{{Mn}}$: **{matrices['U_Mn_mean_eV']:.12f} eV**",
                f"- rank($\\chi^0$), rank($\\chi$): {matrices['rank_chi0']}, {matrices['rank_chi']}",
                f"- condition numbers: {matrices['condition_chi0']:.10g}, {matrices['condition_chi']:.10g}",
                f"- direct inverse residuals: {matrices['inversion_residuals']['chi0']:.3e}, {matrices['inversion_residuals']['chi']:.3e}",
                "",
            ]
            lines.append(matrix("Bare response $\\chi^0$", matrices["chi0_electrons_per_eV"], "e/eV", labels))
            lines.append(matrix("Screened response $\\chi$", matrices["chi_electrons_per_eV"], "e/eV", labels))
            lines.append(matrix("Direct inverse $(\\chi^0)^{-1}$", matrices["inv_chi0_eV"], "eV", labels))
            lines.append(matrix("Direct inverse $\\chi^{-1}$", matrices["inv_chi_eV"], "eV", labels))
            lines.append(matrix("Hubbard kernel $K$", matrices["K_hubbard_eV"], "eV", labels))
            lines += [f"$U_I=diag(K)$ (eV): `{vector(matrices['U_by_site_eV'])}`", ""]
        lines += ["### Selected native occupations", ""]
        for run, item in data["runs"].items():
            lines += [f"- `{run}` — `{item['mode']}`, event `{item['selected_event']}` "
                      f"(#{item['selected_event_index_one_based']} of {item['complete_event_count']} complete): "
                      f"`{vector(item['selected_occupations_electrons'])}`"]
        lines.append("")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
