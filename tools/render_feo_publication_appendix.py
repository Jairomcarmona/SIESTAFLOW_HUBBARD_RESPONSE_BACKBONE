#!/usr/bin/env python3
"""Render the complete FeO LR-U audit arrays as a readable Markdown appendix."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "evidence_audit_feo_20260812.json"
TARGET = ROOT / "docs" / "evidence" / "feo_mathematical_20260812" / "FEO_COMPLETE_NUMERICAL_APPENDIX.md"


def vector(values: list[float]) -> str:
    return "[" + ", ".join(f"{value:.8f}" for value in values) + "]"


def matrix(name: str, values: list[list[float]], unit: str) -> str:
    array = np.asarray(values, dtype=float)
    labels = " ".join(f"{index:>11}" for index in range(array.shape[1]))
    rows = [f"columns:{labels}"]
    for index, row in enumerate(array):
        rows.append(f"{index:>7}:" + "".join(f" {value:>10.6f}" for value in row))
    return f"### {name}\n\nUnits: {unit}. Rows and columns follow FeLR00, FeLR01, ..., FeLR15.\n\n```text\n" + "\n".join(rows) + "\n```\n"


def main() -> None:
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    lines = [
        "# FeO LR-U complete numerical appendix",
        "",
        "This is the human-readable numerical supplement to "
        "[`FEO_LR_U_MATHEMATICAL_EVIDENCE.md`](FEO_LR_U_MATHEMATICAL_EVIDENCE.md). "
        "It is rendered directly from "
        "[`../../evidence_audit_feo_20260812.json`](../../evidence_audit_feo_20260812.json), "
        "whose values were independently parsed from the native SIESTA archive.",
        "",
        "## Conventions",
        "",
        "Site index 0--15 means FeLR00--FeLR15.  `BARE` uses the second "
        "complete semantic occupation event; REFERENCE and SCREENED use the last. "
        "The finite-difference denominator is 0.10 eV.  The displayed response "
        "matrices are symmetrized as `(M_raw + M_raw.T)/2`; the raw arrays are in "
        "the JSON supplement.",
        "",
        "## Selected native occupations",
        "",
    ]
    for run, record in data["runs"].items():
        lines += [
            f"### {run}",
            "",
            f"- mode: `{record['mode']}`; complete events: {record['complete_events']}; "
            f"selected: `{record['selected_event']}`",
            f"- normal completion: `{record['normal_completion']}`; "
            f"SCF non-convergence marker: `{record['unconverged_marker']}`",
            f"- occupations (electrons): `{vector(record['selected_occupations_electrons'])}`",
            "",
        ]
    lines += ["## Explicit finite-difference response columns", ""]
    for name, values in data["response_columns_electrons_per_eV"].items():
        lines += [f"- `{name}` (e/eV): `{vector(values)}`", ""]
    matrices = data["matrices"]
    lines += ["## Complete reconstructed matrices", ""]
    lines.append(matrix("Bare response $\\chi^0$", matrices["chi0_electrons_per_eV"], "e/eV"))
    lines.append(matrix("Screened response $\\chi$", matrices["chi_electrons_per_eV"], "e/eV"))
    lines.append(matrix("Direct inverse $(\\chi^0)^{-1}$", matrices["inv_chi0_eV"], "eV"))
    lines.append(matrix("Direct inverse $\\chi^{-1}$", matrices["inv_chi_eV"], "eV"))
    lines.append(matrix("Hubbard kernel $K=(\\chi^0)^{-1}-\\chi^{-1}$", matrices["K_hubbard_eV"], "eV"))
    lines += [
        "## Diagonal Hubbard values",
        "",
        "`U_I = diag(K)` (eV): `" + vector(matrices["U_by_site_eV"]) + "`",
        "",
        "## Direct-inversion diagnostics",
        "",
        f"- rank(chi0): {data['rank_chi0']}; cond(chi0): {data['condition_chi0']:.14g}; "
        f"residual: {data['inversion_residual_chi0']:.14g}",
        f"- rank(chi): {data['rank_chi']}; cond(chi): {data['condition_chi']:.14g}; "
        f"residual: {data['inversion_residual_chi']:.14g}",
        f"- mean $U_\\mathrm{{Fe}}$: **{data['U_mean_eV']:.13f} eV**",
        "",
    ]
    TARGET.write_text("\n".join(lines), encoding="utf-8")
    print(TARGET)


if __name__ == "__main__":
    main()
