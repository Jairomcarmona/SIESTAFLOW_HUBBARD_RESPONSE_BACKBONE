# CODEX TASK 22: State-consistency evidence (FDRC I.5) as a diagnostic, plus two runner fixes

**Base:** `codex/hubbardflow-rename` at merge `299b8f0`.
**Branch:** `fdebq/r6-task22-i5`. Push it; do not open a PR.

## Goal and limits

For every fixed-grid campaign, produce and check the I.5 state evidence of
`HUBBARDFLOW_FDRC_INDEPENDENT_REVIEW.md` §I.5, and report it as a **diagnostic only**.

Nothing else changes:
- no U value, analysis-JSON field, run spec or admission decision;
- `CampaignShadow._complete_state_gate()` keeps returning `False`;
- reductions and calibrated grids stay disabled (that is TASK 23).

An independent audit of this file against the code and the real NiO data was done before
delivery, and its corrections are included.

### Author decisions (record them as D13 in `docs/fdebq/AMENDMENTS_2.md`)

**D13a. G3 smoothness (§I.5.5) is deferred.** Its rigorous form needs the SCF ladder error ("print +
ladder"), which has no production evidence yet (T0–T4). With only print bounds and three amplitudes:
- `verify_order` cannot see jumps at the largest amplitude or symmetric jumps;
- it false-alarms on Sz under realistic SCF noise.

The audit verified both by probe. G3 is reported as
`NOT_ESTABLISHED: SMOOTHNESS_REQUIRES_SCF_LADDER`. What replaces it are threshold-free per-point
checks that detect discrete branch changes: G2 subspace, G2b occupation count, G3a moment sign,
G4 band count.

**D13b. G2 also applies to fully occupied channels**, such as the NiO majority-spin t2g/eg split.
A reordering there is a real change of orbital polarization. As a diagnostic it is reported, not
hidden.

**D13c. Deviations recorded, not implemented now:**
- §I.5.1 dDmax/dHmax and iteration outliers (G1 uses node validation only);
- §I.5.3 total-moment quantization;
- §I.5.6 hysteresis;
- §I.5.7 Hellmann–Feynman.

## 0. Rules

1. **Premises.** Re-check each premise with one command and log it in `docs/fdebq/TASK22_LOG.md`.
   A false premise blocks only what depends on it; record it in BLOCKERS.md.
2. **Gates after every commit.**
   - the replay test against its own golden;
   - the 20.9 golden;
   - the product tests;
   - the 70 scientific regressions;
   - the architecture test (the allowlist may only shrink, and no item may add an entry);
   - ruff, format, mypy (`MYPYPATH=src`);
   - the V6 gate;
   - the full suite with no new failures.

   CI must be green twice in a row on the final tip.
3. **Test edits** only under R5, plus the ones named below. Log each one.
4. **Golden updates** only where an item authorizes them. Log the old and new hashes.
5. **Conservative-and-continue** for ambiguities that cannot change results. Stop only on an
   unauthorized golden mismatch or a false premise.
6. **Commits and reviews.** One item = one commit. Use `verificador_luna` on each diff. Use
   `auditor_cientifico` before 22.4.
7. **Never collect pytest from the repository root;** always run `pytest tests`.

---

## 22.1 Record why an execution failed

**Premises**
- `execution/runtime_adapters.py` `_failed_receipt` (~L61) stores only a digest. Stdout is `None`
  when it is redirected to a file.
- The runner merges an `extra` mapping into node records (`record_receipt`).
- `hubbardflow status` (`cli.py` ~L179) dumps `worker-state.json` through
  `campaign_runner.campaign_status`. A failed run ends with `heartbeat.finish("FAILED", ...)`
  (~L1790).

**Change**

1. On `FAILED_EXECUTION`, `LocalSubprocessExecutor.execute` writes `failure.json` atomically in
   `command.cwd`, with these fields:
   - `returncode`;
   - `returncode_meaning`, one of:
     - `"SIGNAL:<NAME>"` if `returncode < 0`;
     - `"PROBABLE_SIGNAL:<NAME> (128+N via launcher)"` if `returncode > 128` and `returncode − 128`
       is a valid signal number;
     - `"SYNTHETIC_OSERROR"` for the 127 produced by the `OSError` branch;
     - `"EXIT"` otherwise;
   - the last 20 lines of the stdout and stderr files, or of the captured strings;
   - `argv`.
2. The runner adds `returncode` and `returncode_meaning` to that node's record `extra` and to the
   `heartbeat.finish("FAILED", ...)` details. `status` therefore shows them through the existing
   path, and through `read_worker_status` for WSL pointers.
3. The receipt digest and every success path stay unchanged.

**Tests**
- A fake executable exiting 3 → `EXIT`.
- One that kills itself with SIGTERM directly → `SIGNAL:SIGTERM`.
- A launcher script returning 143 → `PROBABLE_SIGNAL:SIGTERM`.
- Success writes no `failure.json`.

## 22.2 Explicit planner-version error

**Premises**
- `verify_frozen_campaign_plan` (`execution/campaign_plan.py` ~L252–269) recomputes the plan inside
  a `try`, and re-wraps errors as "cannot resume …".
- The current version is the literal `campaign-planner-v3` (~L193).

**Change**
- Read the raw `planner_version` from the stored JSON before `from_mapping`, **outside** that `try`.
- If it differs from the current version, raise `PLANNER_VERSION_CHANGED`, naming both versions and
  saying "re-initialize the campaign; frozen plans are not migrated".
- No new golden digest test is needed: the replay manifest already pins the plan via
  `campaign.lock`.

**Test**
- A frozen plan edited to `campaign-planner-v2` → `PLANNER_VERSION_CHANGED`, not the generic
  message.

## 22.3 Per-run state evidence (siesta_backend)

**Premises** (author- and audit-verified on the real fixtures; re-check)
- **Occupation blocks.** Each per-atom block starts with
  `hubbard_term: atom, species: <atom> <species>`, followed by 25 rows `i j up down` with **5
  decimals**. The matrices are symmetric.
- **Same events as U.** The existing `event_parser` exposes the full matrices
  (`HubbardPopulationEvent.raw_matrix_up`/`raw_matrix_down`). The selectors
  `bare_profile.select_response` and `select_converged_screened_event` choose the events that the U
  analysis uses. The gate must use **the same selected events**, not "the last block". The two
  coincide on all 12 real BARE runs.
- **Mulliken.** The final `Mulliken Atomic Populations:` table gives `Sz [e]` per atom with 6
  decimals.
- **Fermi line.** The format is `siesta:   Fermi = <eV>` with variable spaces; use a
  whitespace-tolerant regex.
- **`.EIG` files.** `<SystemLabel>.EIG` exists in real run directories but not in the replay
  fixtures. Read its format and print precision from a real file of the WSL campaign
  `nio_p5_product_2`, and log three example lines.

**Change**
1. **Input types live in the domain.** Define them in `domain/state_gate.py` (22.4):
   `PointState`, with per atom and spin the printed matrix entries as decimal strings, and Sz, E_F,
   and per-k, per-spin band counts with their distances to E_F. This avoids a domain → siesta_backend
   import.
2. **Parser.** `siesta_backend/point_state_evidence.py` builds `PointState` from the selected event,
   the final Mulliken table, the Fermi line and an optional `.EIG` text.
   - Missing or malformed data raises a typed error.
   - A missing `.EIG` gives a band-count field of `NOT_AVAILABLE`.
   - Do not import private names from other modules; make needed helpers public in their home module
     (AGENTS rule 11).
3. **Fixtures.** Add a small, separate `tests/fixtures/i5_eig/` with the real `.EIG` of the reference
   and of two runs (xz), copied from `nio_p5_product_2`. **Do not** add `.EIG` to the replay
   fixtures.

**Print-quantum definitions** (use these exact names everywhere):
- `q`: one unit in the last printed decimal, 1e-5 for the matrices.
- Entry half-width: `q/2`.
- `W = m·q/2`, with m = 5, so W = 2.5e-5. This is a valid bound on the spectral norm of the print
  error, since ‖E‖₂ ≤ ‖E‖_F ≤ m·max|E_ij|.

**Tests**
- On the real reference and two runs: 2 atoms × 2 spins, q = 1e-5, W = 2.5e-5, and each trace
  within 2.55e-5 of the printed `Occupations:` line.
- A truncated block → typed error.

## 22.4 The I.5 gate (domain, pure) **[science]**

Create `domain/state_gate.py` with policy `i5-state-policy-v1`. All margins come from W. The only
constant is the majority criterion 1/2.

Inputs: the reference `PointState`, and the points of one (perturbed column, mode).

Checks per observed correlated atom and spin, at each point ±a:

- **G1. Node validated** under its mode's contract. BARE is single-step by design; `SCF_NOT_CONV`
  is expected there and is not a failure.

- **G2. Occupied subspace (principal angles).**
  - **Defining k.** In the reference spectrum (descending order), let Δ₁ be the largest gap
    between consecutive eigenvalues and Δ₂ the second largest. k is defined only if all of these
    hold:
    - Δ₁ − Δ₂ > 4W, so the split is unique;
    - Δ₁ > 4W;
    - the margin ε below is < 1/2.

    Otherwise the result is `NOT_DEFINED` for that atom and spin. It is recorded and does not fail.
  - **Point requirements.** The point spectrum's largest resolved gap must sit at the same index k.
    Otherwise → `OCCUPATION_COUNT_CHANGED` (fail).
    - If the point's own Δ₁ − Δ₂ ≤ 4W, its split is not unique, so the result is
      `SUBSPACE_AMBIGUOUS` (fail closed), not `OCCUPATION_COUNT_CHANGED`.
  - **Principal angle.** Let V_ref and V_pt be the top-k eigenvectors, and
    c = σ_min(V_refᵀ V_pt)², the squared cosine of the largest principal angle. This is basis
    independent inside degenerate clusters.
  - **Margin.**
    ε = 2·[W/(Δ_ref − 2W) + W/(Δ_pt − 2W)], where Δ_pt is the point's gap at index k
    (Davis–Kahan for each printed matrix; the factor 2 converts sin θ to cos²).
  - **Verdict.**
    - Pass iff c − ε > 1/2.
    - c + ε < 1/2 → `ORBITAL_ORDER_CHANGED` (fail).
    - Otherwise → `SUBSPACE_AMBIGUOUS` (fail closed).

- **G3a. Moment sign.** Whenever |Sz_ref| exceeds its half-width (5e-7), every point must keep the
  same sign of Sz, also resolved. Otherwise → `MOMENT_SIGN_CHANGED` (fail).

- **G4. Band count at E_F (only if `.EIG` is available).** Applicable only if, in the reference,
  every eigenvalue at every k and spin is farther from E_F than the `.EIG` print quantum (a
  resolved insulator).
  - If applicable, every point must have, at every k and spin, the same number of eigenvalues
    below its own E_F as the reference. Otherwise → `BAND_COUNT_CHANGED` (fail).
    - If a point has an eigenvalue within one `.EIG` print quantum of its own E_F, the count is
      ambiguous → `BAND_COUNT_AMBIGUOUS` (fail closed).
  - If not applicable, the result is `NOT_APPLICABLE`; if `.EIG` is missing, `NOT_AVAILABLE`.
    Neither fails.

- **G3.** Report `NOT_ESTABLISHED: SMOOTHNESS_REQUIRES_SCF_LADDER` (D13a).

**Monotone rule.** If a check fails at amplitude a (either sign), then a and every larger
amplitude are excluded for that column and mode.

**Verdict per (column, mode).**
- `PASS`: no failures.
- `FAIL`: admissible amplitudes and reasons.
- `NOT_ESTABLISHED`: missing required evidence, other than the documented
  `NOT_DEFINED` / `NOT_APPLICABLE` / `NOT_AVAILABLE` / G3 outcomes.

**Tests**
- **(a)** On the real NiO P5 outputs (24 runs plus the reference), all four (column, mode) pairs
  give `PASS`. The audit's extended prototype found the worst margin 0.49 above the threshold.
- **(b)** Rotating one occupied and one unoccupied reference eigenvector fully at a = 0.06 gives
  `ORBITAL_ORDER_CHANGED` and excludes only 0.06. A partial leak with cos² = 0.4 is detected
  regardless of the basis chosen inside degenerate clusters (test with two different bases).
- **(c)** A degenerate reference with no unique split gives `NOT_DEFINED`.
- **(d)** Making the point spectrum's largest gap move to another index gives
  `OCCUPATION_COUNT_CHANGED`.
- **(e)** An Sz sign flip at a = 0.04 excludes 0.04 and 0.06.
- **(f)** A band crossing E_F at one k in a synthetic `.EIG` gives `BAND_COUNT_CHANGED`.

## 22.5 Wire I.5 as a diagnostic output

**Change**

1. **Where it runs.** In `_execute_analysis` (fixed-grid path), **between**
   `write_lr_analysis_v2` and `write_lr_u_report`, the runner builds the gate for every
   (column, mode) from the validated nodes. It uses the selected events
   and reads `.EIG` from each node directory (`command.cwd` in the node record) when present.
   - It writes `results/i5_state_gate.json`.
   - It never touches the analysis object, the node records or `node-evidence.json`.
   - Adaptive and shadow analysis paths write the same file with `NOT_ESTABLISHED: PATH_NOT_COVERED`.
   - Any gate exception becomes `NOT_ESTABLISHED` with its reason. The analysis never fails
     because of I.5.
2. **Report.** In `reporting/lr_u_report.py`, add an optional "I.5 state consistency (diagnostic)"
   section, rendered from a mapping argument.
   - Reporting stays render-only: the execution callers read `results/i5_state_gate.json` and pass
     the parsed mapping.
   - Both the runner's report writer and `render_campaign_report` (`hubbardflow report`) must pass
     it, so re-rendering keeps the section.
3. **Replay test** (authorized R5 edit of `_campaign_file_manifest` and `_campaign_json_snapshot`).
   - Exclude `results/i5_state_gate.json` from byte hashing, like the analysis JSON.
   - Compare it with the existing comparator against a new golden `replay_i5_state_gate.json`.
   - The replay emits no `.EIG`, so its expected G4 is `NOT_AVAILABLE`, which is not a failure.
   - Its verdicts must be `PASS` for all four pairs.
   - Do not regenerate the manifest: if the hashes still change, stop and report why.

**Files:** `campaign_runner.py` (call site only), a new `execution/state_gate_step.py` if needed
to keep the runner thin, `reporting/lr_u_report.py`, the replay test and fixtures.

## 22.6 Real run and launch documentation

1. **Real run.** In WSL, from a frozen copy of the branch tip, rerun NiO P5 through the product:
   - a new product directory and campaign name;
   - the verified inputs from `nio_p5_20261003/inputs`;
   - launched with `setsid nohup … < /dev/null > log 2>&1 &`, then a check from a new shell that
     the worker is alive.

   Requirements:
   - U identical to Part A;
   - `i5_state_gate.json` `PASS` for all four pairs, with G4 `APPLICABLE` and passing (NiO is an
     insulator);
   - no `failure.json`.

   If any I.5 check fails on this real run, stop and report the full I.5 JSON. That would mean
   the gate is wrong, not the state.
2. Record the results in `docs/fdebq/TASK22_REAL_RUN.md`.
3. Add a "Long campaigns from WSL" section to `docs/fdebq/USER_GUIDE.md`, covering the `setsid`
   launch, the liveness check, and `failure.json`.

---

## Closing

Write `docs/fdebq/TASK22_SUMMARY.md` with:
- the items and their commits;
- the R5 and authorized test edits;
- the golden updates;
- the conservative decisions;
- the two green CI runs.

Push the branch; do not open a PR.

**Out of scope (TASK 23):**
- I.5 enabling `TRANSLATION_SHADOWED` reductions, with a real NiO P5 reduced-versus-direct
  comparison;
- G3 with the SCF ladder;
- near-symmetry detection without spglib;
- rotation enumeration;
- 20.8 calibrated rounds.
