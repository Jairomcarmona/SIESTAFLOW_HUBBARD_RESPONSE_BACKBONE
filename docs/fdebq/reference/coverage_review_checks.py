"""Reproducible checks supporting the perturbation-coverage review.

Part 1 (retrospective, read-only): tests the response reconstruction law on
archived campaigns in which BOTH symmetry-related columns were computed
directly (CoO V6: two AFM sites; MnO v3r2: representatives A and B).
Part 2 (synthetic): mean-field Hubbard rings with known symmetry and
counterexamples (hidden inequivalence with equal |m|; spontaneous breaking).

Usage, from a checkout of codex/hubbardflow-rename:
    python coverage_review_checks.py .
Nothing is written. Development data only; not validation.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np


def coo(root: Path) -> None:
    path = root / "results/stage-ub-v6-observables/coo-u-b-campaigns/stageubv6-coo-a0/lr_u_analysis.v3.json"
    rows = json.loads(path.read_text())["response_observation_dataset"]["rows"]
    data = {}
    for r in rows:
        for o in r["observed_sites"]:
            for m in ("bare", "screened"):
                data[(m, r["perturbed_site_index"], o["observed_site_index"], r["alpha_eV"])] = o["occupations_electron"][m]
    print("CoO V6 (2 Co, opposite spins; g = sublattice exchange with spin flip, eps=-1)")
    for m in ("bare", "screened"):
        for a in (0.02, 0.04, 0.06):
            S = np.array([[(data[(m, J, I, a)] - data[(m, J, I, -a)]) / (2 * a) for J in (0, 1)] for I in (0, 1)])
            print(f"  {m:8s} a={a:.2f}  chi00-chi11={S[0,0]-S[1,1]:+.2e}  chi01-chi10={S[0,1]-S[1,0]:+.2e}"
                  f"  (|chi00|={abs(S[0,0]):.4f})")


def mno(root: Path) -> None:
    base = root / "campaigns/mno_afmii_strict_lr_v3r2"
    rec = json.loads((base / "results/response-matrix-foreground-recovery-v4/response-receipt.json").read_text())["records"]
    sm = json.loads((base / "geometry/site_map.json").read_text())
    pos = np.array([s["fractional_supercell"] for s in sm])
    n = len(sm)

    def find(p):
        hits = [j for j in range(n) if np.allclose((pos[j] - p + 0.5) % 1 - 0.5, 0, atol=1e-9)]
        return hits[0] if len(hits) == 1 else None

    t = pos[1] - pos[0]
    pi = [find((pos[i] + t) % 1) for i in range(n)]
    print("MnO v3r2 (16 Mn; g = translation A->B with spin flip, eps=-1); printed totals have 5 decimals")
    for mode in ("BARE", "SCREENED"):
        for a, tag in ((0.025, "0d025"), (0.05, "0d050"), (0.1, "0d100")):
            col = {}
            for role in "AB":
                p = np.array(rec[f"{role}_{mode}_p{tag}"]["occupations_e"])
                m = np.array(rec[f"{role}_{mode}_m{tag}"]["occupations_e"])
                col[role] = (p - m) / (2 * a)
            pred = np.empty(n)
            for i in range(n):
                pred[pi[i]] = col["A"][i]
            d = np.abs(col["B"] - pred).max()
            print(f"  {mode:8s} a={a:.3f}  max|chi_B - P chi_A|={d:.1e} e/eV   x a = {d*a:.1e} e"
                  f"   print-only bound 2*5e-6/a={1e-5/a:.1e}")


if __name__ == "__main__":
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    coo(root)
    mno(root)
