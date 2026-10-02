"""Reproducible numerics supporting the independent FDRC-v1 review.

Part 1 re-analyses the frozen V6 CoO response observations (read-only) to show
the error regimes of BARE and SCREENED and the behaviour of several estimators.
Part 2 runs a synthetic coverage check of the proposed error-budget qualifier.

Usage (from a checkout of codex/hubbardflow-rename):
    python fdrc_review_numerics.py \
        results/stage-ub-v6-observables/coo-u-b-campaigns/stageubv6-coo-a0/lr_u_analysis.v3.json

Nothing here is production code and nothing writes into the repository.
All numbers are illustrations on a development system, not validation.
"""
from __future__ import annotations

import json
import sys

import numpy as np

Q_PRINT = 5e-7  # half-step of SIESTA f12.6 occupation output (e)


# ----------------------------------------------------------------------------
# Part 1: CoO V6 data (development system; post-hoc illustration only)
# ----------------------------------------------------------------------------
def coo_reanalysis(path: str) -> None:
    d = json.load(open(path))
    rows = d["response_observation_dataset"]["rows"]
    data, refs = {}, {}
    for r in rows:
        J, a = r["perturbed_site_index"], r["alpha_eV"]
        for o in r["observed_sites"]:
            I = o["observed_site_index"]
            for m in ("bare", "screened"):
                data[(m, J, I, a)] = o["occupations_electron"][m]
            refs[I] = o["occupations_electron"]["reference"]
    A = np.array([0.02, 0.04, 0.06])
    x = np.array([-0.06, -0.04, -0.02, 0.02, 0.04, 0.06])

    def S(m, a):
        return np.array([[(data[(m, J, I, a)] - data[(m, J, I, -a)]) / (2 * a) for J in (0, 1)] for I in (0, 1)])

    def fit(m, deg):
        M = np.zeros((2, 2))
        for I in (0, 1):
            for J in (0, 1):
                M[I, J] = np.polyfit(x, [data[(m, J, I, a)] for a in x], deg)[-2]
        return M

    def rich(m, a1, a2):
        return (a2**2 * S(m, a1) - a1**2 * S(m, a2)) / (a2**2 - a1**2)

    def U(c0, c):
        return np.diag(np.linalg.inv(c0) - np.linalg.inv(c))

    print("== Part 1: CoO V6 central-difference drift (theory for pure c3*a^2: ratio 20/12 = 1.667)")
    for m in ("bare", "screened"):
        for J in (0, 1):
            for I in (0, 1):
                s = [S(m, a)[I, J] for a in A]
                d1, d2 = s[1] - s[0], s[2] - s[1]
                ratio = d2 / d1 if d1 != 0 else float("nan")
                print(f"  {m:8s} chi[{I},{J}] s(a)={['%.6f' % v for v in s]} drift={d1:+.2e},{d2:+.2e} ratio={ratio:+.3f}")

    print("\n== BARE even part e(a)=[n(+a)+n(-a)]/2 - n_ref fitted as delta0 + c2 a^2 + c4 a^4")
    V = np.vstack([np.ones(3), A**2, A**4]).T
    for J, I in ((0, 0), (0, 1)):
        e = np.array([(data[("bare", J, I, a)] + data[("bare", J, I, -a)]) / 2 - refs[I] for a in A])
        print(f"  J={J} I={I} e={e} -> delta0, c2, c4 = {np.linalg.solve(V, e)}")

    print("\n== Estimators (U per site, eV). Sites are symmetry-equivalent AFM sublattices.")
    ests = {f"central a={a}": (S("bare", a), S("screened", a)) for a in A}
    ests["richardson(0.02,0.04)"] = (rich("bare", 0.02, 0.04), rich("screened", 0.02, 0.04))
    ests["linear OLS 6pt"] = (fit("bare", 1), fit("screened", 1))
    ests["cubic 6pt (V6 production)"] = (fit("bare", 3), fit("screened", 3))
    ests["BARE richardson / SCREENED central 0.02"] = (rich("bare", 0.02, 0.04), S("screened", 0.02))
    ests["BARE cubic / SCREENED central 0.02"] = (fit("bare", 3), S("screened", 0.02))
    for k, (c0, c) in ests.items():
        u = U(c0, c)
        print(f"  {k:42s} U={u[0]:.5f},{u[1]:.5f}  |U0-U1|={abs(u[0]-u[1]):.1e}")

    c0, c = ests["cubic 6pt (V6 production)"]
    i0, i1 = np.linalg.inv(c0), np.linalg.inv(c)
    print("\n  chi0 eigenvalues", np.linalg.eigvalsh((c0 + c0.T) / 2), " chi eigenvalues", np.linalg.eigvalsh((c + c.T) / 2))
    print("  dU_0/dchi0_IJ =\n", np.round(-np.outer(i0[0], i0[:, 0]), 2))
    print("  dU_0/dchi_IJ  =\n", np.round(np.outer(i1[0], i1[:, 0]), 2))

    print("\n== Noise gain sum|w| (e -> e/eV) and leading truncation moment on the V6 grid")
    for deg in (1, 3):
        W = np.linalg.pinv(np.vander(x, deg + 1, increasing=True))[1]
        print(f"  degree {deg}: sum|w|={np.abs(W).sum():.2f}/eV  sum w a^3={(W * x**3).sum():.2e}  sum w a^5={(W * x**5).sum():.2e}")
    print("  central a=0.02: sum|w|=50.00/eV ; richardson(0.02,0.04): sum|w|=75.00/eV")


# ----------------------------------------------------------------------------
# Part 2: synthetic coverage check of the error-budget qualifier
# ----------------------------------------------------------------------------
rng = np.random.default_rng(7)
LATTICE = np.array([0.005, 0.01, 0.02, 0.04, 0.08])  # illustrative only
R = 2.0


def observe(a, p, eps_abs, eps_rel, bias_rel=0.0):
    y = sum(p.get(f"c{k}", 0.0) * a**k for k in range(2, 6)) + p["chi"] * a + p.get("k", 0.0) * a * abs(a)
    y *= 1.0 + bias_rel
    noise = rng.uniform(-1, 1) * (eps_abs + eps_rel * abs(y))
    return np.round(7.0 + y + noise, 6)  # f12.6 print quantization


def qualify(p, eps_abs, eps_rel, bias_rel=0.0, assumed=None):
    ea, er = assumed if assumed is not None else (eps_abs, eps_rel)
    s, nu = [], []
    for a in LATTICE:
        o = (observe(a, p, eps_abs, eps_rel, bias_rel) - observe(-a, p, eps_abs, eps_rel, bias_rel)) / 2
        s.append(o / a)
        nu.append(Q_PRINT / a + ea / a + er * abs(o / a))
    s, nu, t = np.array(s), np.array(nu), LATTICE**2
    d, dn = np.diff(s), np.array(nu[:-1]) + np.array(nu[1:])
    resolved = np.abs(d) > dn
    order = [None] * len(d)
    for k in range(len(d) - 1):
        if resolved[k] and resolved[k + 1] and np.sign(d[k]) == np.sign(d[k + 1]):
            lo = (abs(d[k + 1]) - dn[k + 1]) / (abs(d[k]) + dn[k])
            hi = (abs(d[k + 1]) + dn[k + 1]) / max(abs(d[k]) - dn[k], 1e-300)
            c2, c1 = lo <= R**2 <= hi, lo <= R <= hi
            order[k] = 2 if (c2 and not c1) else (1 if c1 else -1)
    cands = []
    for k in range(len(d)):
        ok = order[k] if k < len(order) and order[k] is not None else (order[k - 1] if k > 0 else None)
        if ok == -1:
            continue
        p_used = 2 if ok == 2 else 1  # conservative unless order 2 is verified
        cands.append(("central", k, s[k], nu[k] + (abs(d[k]) + dn[k]) / (R**p_used - 1)))
        if ok == 2 and k + 1 < len(d) and order[k + 1] in (2, None):
            w1, w2 = t[k + 1] / (t[k + 1] - t[k]), -t[k] / (t[k + 1] - t[k])
            est = w1 * s[k] + w2 * s[k + 1]
            est2 = (t[k + 2] * s[k + 1] - t[k + 1] * s[k + 2]) / (t[k + 2] - t[k + 1])
            n1 = abs(w1) * nu[k] + abs(w2) * nu[k + 1]
            n2 = (t[k + 2] * nu[k + 1] + t[k + 1] * nu[k + 2]) / (t[k + 2] - t[k + 1])
            cands.append(("richardson", k, est, n1 + (abs(est2 - est) + n1 + n2) / (R**4 - 1)))
    adm = [c for c in cands if all(abs(c[2] - o[2]) <= c[3] + o[3]
                                   for o in cands if o[0] == c[0] and abs(o[1] - c[1]) == 1)]
    return min(adm, key=lambda c: (c[3], c[1])) if adm else None


def synthetic() -> None:
    print("\n== Part 2: synthetic coverage (true chi inside reported bound?)")
    bare = dict(chi=-1.355, c2=0.35, c3=9.4, c4=-7.8, c5=-60.0)
    scr = dict(chi=-0.117, c3=0.03)
    cases = [
        ("BARE-like, print noise only", bare, 0, 0, 0.0, None),
        ("SCREENED-like, SCF abs 2e-6 (known)", scr, 2e-6, 0, 0.0, None),
        ("SCREENED-like, SCF rel 1e-3 (known)", scr, 0, 1e-3, 0.0, None),
        ("SCREENED-like, SCF abs 2e-6 assumed 0", scr, 2e-6, 0, 0.0, (0, 0)),
        ("systematic relative SCF bias 1e-3", scr, 0, 0, 1e-3, None),
        ("odd non-analytic k*a|a| (metal-like)", dict(chi=-0.5, k=0.8), 0, 0, 0.0, None),
    ]
    for name, p, ea, er, bias, assumed in cases:
        cover = n = 0
        widths, chosen = [], {}
        for _ in range(400):
            b = qualify(p, ea, er, bias, assumed)
            if b is None:
                continue
            n += 1
            widths.append(b[3] / abs(p["chi"]))
            cover += abs(b[2] - p["chi"]) <= b[3]
            chosen[b[0]] = chosen.get(b[0], 0) + 1
        print(f"  {name:42s} accepted {n:3d}/400 coverage {cover/max(n,1):.3f} "
              f"median rel. bound {np.median(widths):.1e} chosen {chosen}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        coo_reanalysis(sys.argv[1])
    synthetic()
