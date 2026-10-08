# P0 Execution Log — 2026-09-28

> **Final P0–P6 closeout — 2026-09-28.** This addendum supersedes the
> historical blocked status recorded below, which preceded locating the NiO
> data. The operational gates were completed, but the scientific objective
> the user requires for declaring the product ready was not achieved. Current
> terminal state: **PRODUCT_BLOCKED**. The P5 result remains
> `NUMERICAL_CANDIDATE_UNASSESSED` / `NOT_ESTABLISHED` and does not establish a
> useful/accepted U.

| Gate | Status | Verifiable evidence |
|---|---|---|
| P0 — freeze contract | `PASS` | Historical NiO campaign `99d5ee67-d9cf-41f1-9f8f-39315c6e81fd`: 41 `.out`/DM pairs verified; 948 matrix→`Occupations:` comparisons with no anomalies. R1 contract and two-site PBE NiO P5 path, 25 nodes, fixed before calculation. P5 FDF matches SHA-256 `b4fb34e642d862be6949a5b2033a60c5b9fcae56119879583bb3eaf237620ee7`; PSML NiLR0/NiLR1 `192eb05ffb64671715e570e2ca9a99a551cf15544984592082d43004f8554e06`; O `224ded5c59176d9bcb76d19b7a4a68a48d5dffabf8b262f64d5760250e87c35e`. |
| P1 — occupation source | `PASS` | Schema `siestaflow.lr_u_analysis.v3`; total from the `Occupations:` token is the primary observable for reference/BARE/SCREENED, using its precision from the same event. `trace_total` is only a cross-check. Historical v2 artifacts and reports remain intact. |
| P2 — mathematical decisions | `PASS` | v3 replay saved by round: `REFINE`, `REFINE`, `STOP_STABLE`; final `NUMERICAL_CANDIDATE_UNASSESSED`, acceptance `NOT_ESTABLISHED`, because no sensitivity tolerance was declared. Adaptive thresholds persisted unchanged; adaptive-control tests passed. |
| P3 — DAG, CLI, and report | `PASS` | Public `init/run/status/resume/report` path for PowerShell→WSL and Linux/Slurm manifest; report does not start a worker. Focused tests and independent P3 audit passed. |
| P4 — regression without SIESTA | `PASS` | Final public suite: `677 passed, 29 skipped, 20 subtests passed` (14.43 s). Skips have recorded reasons: retired legacy BARE APIs, legacy NiO generator incompatible with frozen historical FDF fixtures, POSIX helpers run on Windows, and calibration tied to a historical release whose hash differs from the current workspace. Archived Cu1 v3 regression validates outputs/DM and retains `FAIL_CLOSED_NO_AUTHORIZED_U`. |
| Sol audit — before P5 | `READY` | Independent scientific auditor, GPT-6 Sol / medium / read-only; one-time review of source, OLS fit via QR, bounds, matrices, inversion, and report. Reproduced χ⁰, χ, and U. Primary cubic rounding bound: `0.034362731047454464 eV`; the diagnostic linear bound is `0.013537118260117095 eV`. |
| P5 — final real campaign | `PASS` | One new campaign UUID `73a0a508-93df-41e2-b1bd-993c3dc7d94a`, `/home/jmc/.local/state/siestaflow/campaigns/nio-pbe-p5-20260928`. Ran `25/25` SIESTA nodes, 4 MPI ranks, serially; no duplicate nodes. DAG total `27/27` including analysis. No changes to the base FDF/PSML and no additional concurrent execution. |
| P6 — delivery | `PASS` | Wheel `dist/siestaflow_hubbard-0.1.2-py3-none-any.whl`, SHA-256 `e66ad3621e9f4c3f2ba42d2eb632878fc014bde9e38980f98eaf7c9ea30a610e`. Clean installation and `pip check` passed on Windows and WSL; `--help`, `audit-fdf`, `status`, `resume`, and `report` exercised. `resume` retained 27 nodes and did not relaunch SIESTA. README, manual, quickstart, and changelog aligned; reports regenerated identically. |

**P5 artifacts:** JSON `/home/jmc/.local/state/siestaflow/campaigns/nio-pbe-p5-20260928/results/lr_u_analysis.v3.json`; Markdown `/home/jmc/.local/state/siestaflow/campaigns/nio-pbe-p5-20260928/results/LR_U_REPORT.v3.md`. JSON SHA-256 `d9b76e3841c1da43e70a82a56fad9f69fb68ddd9726779a5643f0cf39b1860ba`; Markdown `f52f370f1ee6b7198ac27e9c7dc5748261ae5df33c80bc943c975c7e34138f1d`. `U_scalar_charge`: NiLR0 `6.864267700049239 eV`, NiLR1 `6.864387475210124 eV`; occupation rounding bound `±0.01183306193 eV` per site. Interpretation remains `NUMERICAL_CANDIDATE_UNASSESSED` and `NOT_ESTABLISHED`.

**Current terminal state: `PRODUCT_BLOCKED`.** Package execution and delivery work, but the primary scientific output did not reach an established U: P5 has no predeclared and justified stability/noise criterion by which to interpret the value as useful. This block cannot be resolved by labeling U accepted or retrospectively changing alpha, tolerances, projectors, windows, or criteria. Minimum work to reopen: establish an independent acceptance/noise protocol and budget before any additional calculation; then reevaluate the contract from P0. This execution does not authorize another campaign. Agreement with literature was not used as a criterion.

> **Resumption addendum — 2026-09-28.** Local review of the 41 NiO results
> cleared the earlier block. The remaining sections below retain the initial
> record as background; their campaign states and decisions are superseded by
> this final closeout.

## Decisions and evidence added during P0–P2 execution

**Single P5 path fixed at P0 before any new campaign:** there is no one-site
NiO input with a public `lr-config.json` in the inspected local datasets; the
two PBE NiO candidates have sites `NiLR0` and `NiLR1`. The two-site PBE NiO
alternative was selected with six symmetric nonzero amplitudes
`[-0.06,-0.04,-0.02,0.02,0.04,0.06] eV`, at most `1+2×2×6=25` SIESTA nodes.
Reference FDF: `campaigns/nio_pbe_adaptive_20260928/reference_pbe.fdf`; Ni/O
PSML and PBE functional: the inputs already used by that campaign, with
provenance hashes in the v3 result. The new campaign will use a fixed mesh and
the public CLI; FDF and PSML will not be edited. Profile: up to 4 MPI ranks,
one concurrent SIESTA run. The historical 41-node adaptive campaign will not
be the P5 test.

**P2 reproduced with the v3 observable and without SIESTA:** the replay
reverified the same selected receipts/output/DM and recomputed each round with
`occupation_source=siesta_occupations_total`. Rounds 0 and 1 return
`REFINE/shrink`, adding `[-0.01,+0.01]` and `[-0.005,+0.005] eV`, respectively;
their meshes match the persisted rounds. In round 2, two comparisons give
`ΔU=0.00375228894 eV`, below the applied tolerance `0.06867064122 eV`
(`tol_abs=0.05 eV`, `tol_rel=0.01`), and `STOP_STABLE` takes precedence over
the truncation metric. Closeout: candidate `NUMERICAL_CANDIDATE_UNASSESSED`;
physical acceptance `NOT_ESTABLISHED`; budget `41/41`. This supersedes only the
historical decision for v3 analysis; historical v2 results and WSL adaptive
state remain intact.

Reproducible v3 artifacts: `campaigns/nio_pbe_adaptive_20260928/results/lr_u_analysis.v3.json`,
`LR_U_REPORT.v3.md`, and `alpha_rounds_v3/round-00..02/analysis.v3.json`.
Policy tests run by `implementador_luna`:
`.venv\Scripts\python.exe -m pytest tests/unit/test_adaptive_alpha_control.py -q`
→ 11 passed. SIESTA was not run.

## P0 reopened and contract frozen

The required campaign is at
`/home/jmc/.local/state/siestaflow/campaigns/nio-pbe-adaptive-20260928-v2`.
The
ode-evidence.json` manifest selects all 41 SIESTA outputs (1 reference,
20 BARE, and 20 SCREENED); read-only review verified hashes for all 41 outputs
and their parent DMs. This resolves the data absence that caused the earlier
block. Historical campaign reports remain unchanged.

The local SIESTA 5.4.2 source,
[`dftu.F`](../third_party/siesta-5.4.2-source-audit/Src/dftu.F), prints the
matrix using `f12.5`, accumulates its diagonals, and then prints
`Occupations:` and `sum(oc)` using `f12.6`. Across the 41 outputs, 948 complete
matrix→`Occupations:` population blocks were compared: maximum error per
channel `2.2e-5`, below the rounding limit `2.55e-5`; maximum total error
`3.1e-5`, below `5.05e-5`; zero anomalies. Reproducible example: reference
output, atom 1, lines 1010–1038: printed traces sum to `5.01139`, `3.01979`,
and `8.03118`; the summary reports `5.011377`, `3.019776`, and `8.031153`
(differences `1.3e-5`, `1.4e-5`, and `2.7e-5`).

**R1 decision frozen:** the `Occupations:` total from the selected event is the
primary observable for reference, BARE, and SCREENED. Its half-width is read
from its tokens (`f12.6`; for the two-channel format without an explicit
total, the half-widths of the two tokens are added). `trace_total` and the
matrix trace remain independent cross-checks only: they do not feed fits,
`χ0`, `χ`, `U`, or the bound. The semantic change is published as schema
`siestaflow.lr_u_analysis.v3` with
`occupation_source=siesta_occupations_total`; historical v2 results are not
relabeled.

P0 is complete. P1/R1 reprocessed the same 41 outputs without rerunning SIESTA
and created v3 artifacts with `occupation_source=siesta_occupations_total`; P2
reanalyzed the three rounds separately and froze `STOP_STABLE` within the
declared policy. Historical v2 artifacts and WSL state remain unchanged. P3
was in progress; P4–P6 had not yet run. Alpha, tolerances, projectors, windows,
and criteria were not changed; literature does not contribute to acceptance;
P5 was selected but not dispatched.

| Gate | Current status | Evidence/reason |
|---|---|---|
| P0 — freeze contract | `PASS` | WSL location recovered; 41 output/DM pairs verified; 948/948 comparisons and R1 primary source fixed above. |
| P1 — occupation source | `PASS` | Reprocessing of 41 outputs published in v3 JSON/Markdown with `occupation_source=siesta_occupations_total`; historical v2 intact. |
| P2 — mathematical decisions | `PASS` | Three decisions reproduced with original policy; `STOP_STABLE` from two within-tolerance comparisons and rounds 0/1 reduced by declared truncation. |
| P3 — DAG, CLI, and report | `PASS` | Public Linux/Slurm CLI accepts a direct manifest within an allocation; WSL retains pointer/supervisor; `report` does not start a worker. Focused tests 7 passed and independent verification 4 passed. |
| P4 — regression without SIESTA | `IN_PROGRESS` | v3 NiO reprocessing complete; closing second real Cu1 dataset and public suite without SIESTA compute. |
| P5 — final real test | `SELECTED / NOT DISPATCHED` | Two-site PBE NiO alternative; 25-node maximum. |
| P6 — delivery | `NOT STARTED` | Project was still in P1. |

---

**Governing plan:** [`EJE_RECTOR_CIERRE_PRODUCTO.md`](EJE_RECTOR_CIERRE_PRODUCTO.md), §§ 2–6.
**Result:** `PRODUCT_BLOCKED` at P0.
**Executed scope:** P0 inspection only. No code, configuration, campaign input, or historical data was edited; no tests or SIESTA were run.

## P0 decision

P0 cannot freeze the occupation contract or authorize P1: the required
41-output adaptive PBE NiO dataset is missing, so print order and BARE/SCREENED
events cannot be cross-checked. The alternative Cu1 dataset is evidence of
real execution and its nodes are intact, but its own verdict closes the
analysis without authorizing χ, inversions, or U because there is no applicable
external occupation-noise bound. It does not replace the NiO scientific
evidence required by P0 for the primary path.

Because this gate failed, **P1–P6 are not run**. In particular, no campaign is
started and Sol is not asked to audit: the audit planned before P5 depends on
completing P0–P4, and that point is not reached.

## Reproducible evidence

1. **SIESTA 5.4.2 source.** In
   [`third_party/siesta-5.4.2-source-audit/Src/dftu.F`](../third_party/siesta-5.4.2-source-audit/Src/dftu.F),
   lines 525–526 print the matrix with `(2i4,2f12.5)`; lines 534–538 accumulate
   the diagonals; lines 541–544 write `Occupations:` and `sum(oc)` with
   `(a,/,a,3f12.6)`. This establishes which local source code must be checked,
   but does not show that the tokens correspond to the same physical event in
   the missing NiO files.
2. **Required NiO data missing.** Directory
   [`campaigns/nio_pbe_adaptive_20260928`](../campaigns/nio_pbe_adaptive_20260928)
   contains **0** `*.out` and `*.DM` files (recursive count limited to those
   extensions). The same 41-output series is not present in `docs/evidence`.
   Other NiO campaign folders exist, but they are different campaigns and were
   not used as substitute data.
3. **Archived Cu1, scope, and status.**
   [`final-verdict.json`](../docs/evidence/siesta542_openmpi_slurm_full_campaign_20260920_run2_wheel/final-verdict.json)
   records `13_VALIDATED_NODES`, `FAIL_CLOSED_NO_AUTHORIZED_U`, and
   `U_ev: null`; its reasons say `occupation_noise` was not declared with
   external justification and must not be derived from the observed mesh,
   synthetic tests, or historical MnO repeatability.
   [`result.json`](../docs/evidence/siesta542_openmpi_slurm_full_campaign_20260920_run2_wheel/result.json)
   confirms `METHODOLOGY_LOCK_MISSING_EXTERNAL_OCCUPATION_NOISE_BOUND`,
   inversion `NOT_AUTHORIZED`, and matrix reconstruction `NOT_AUTHORIZED`.
   Inspecting `artifact-manifest.json` found 450 entries: 449 artifacts match
   in size and SHA256; the only size discrepancy is for
   `FULL_CAMPAIGN_REPORT.md`. All 13 nodes and their execution outputs are
   validated in the archived verdict and result. This discrepancy does not
   make the Cu1 result an authorized U.
4. **Resources recorded, not dispatched.** The archived Slurm profile declares
   4 CPUs/ranks and SIESTA 5.4.2. The laptop exposes a WSL command, not a native
   SIESTA command; reading `Win32_Processor` was denied, so no unverified local
   CPU count is asserted. No work was launched.

## Retained contract and limits

- Preserve historical v2 schema semantics as a reference. If later analysis
  changes the fitted representation, the plan requires explicit
  `occupation_source` and a new schema version; `report` must not relabel v2
  numbers.
- The decision to use `Occupations:` as the primary variable remains
  **pending** a cross-check against the same events in the 41 NiO `.out` files;
  equivalence is not inferred merely because the source accumulates diagonals
  and then prints `sum(oc)`.
- No material or P5 path was selected. The plan limits P5 to one campaign of
  up to 13 nodes for one site, or up to 25 for the two-site NiO alternative
  chosen before calculation; it allows up to four MPI ranks and one concurrent
  SIESTA run. These limits are recorded without dispatch authorization.
- Alpha, tolerances, projectors, windows, limits, and criteria are not changed
  to obtain a U. Literature is not an acceptance criterion. Historical
  artifacts and reports remain immutable.

## Minimum required to reopen

Recover the **41 `.out` files**, their parent `.DM` files, and provenance/
integrity manifest in the declared NiO location so each output can be tied to
its input and event. P0 can then resume and verify the scientific selection
fixed by the plan. If Cu1 is to support a decision depending on occupation
noise, it also needs a predeclared Cu-applicable repeatability/calibration
protocol and its immutable methodology-block receipt, as specified by
`final-verdict.json`.

| Gate | Status | Evidence/reason |
|---|---|---|
| P0 — freeze contract | `BLOCKED` | Source inspected; 41 NiO `.out` files, parent `.DM` files, and manifest are missing. Cu1 is closed without an authorized U. |
| P1 — occupation source | `NOT RUN` | P0 not passed; required NiO data for comparison are unavailable. |
| P2 — mathematical decisions | `NOT RUN` | P0 not passed. |
| P3 — DAG, CLI, and report | `NOT RUN` | P0 not passed. |
| P4 — regression without SIESTA | `NOT RUN` | P0 not passed. |
| P5 — final real test | `NOT RUN / NOT AUTHORIZED` | No campaign selected; SIESTA was not run. |
| P6 — delivery | `NOT RUN` | The product does not meet the preceding gates. |

**Terminal state of this execution:** `PRODUCT_BLOCKED`, due to the
reproducible absence of the NiO data and provenance required at P0. Scope is
not expanded to fabricate a substitute, and work does not proceed to P1–P6.
