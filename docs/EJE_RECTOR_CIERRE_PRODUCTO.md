# Product Charter for Completing the Standalone SIESTA U Utility

**Date:** 2026-09-28. **Status:** execution plan; this document authorizes no new campaign.

> **Status update (2026-09-29):** this charter retains the plan's scope and
> gates; its baseline table does not supersede the later work status. The v3
> analysis occupation source was fixed as `siesta_occupations_total` for the
> selected events; `matrix_trace` remains a check / historical v2 semantics.
> The current adaptive NiO campaign ends as `NUMERICAL_CANDIDATE_UNASSESSED`
> with `physical_acceptance=NOT_ESTABLISHED`; its sensitivity tolerance had not
> been configured. The reported cubic printing bound is 0.03436273105 eV, and
> 0.01353711826 eV is a diagnostic linear fit, not the primary bound. The later
> ±0.02 eV target is operational, not a universal physical tolerance. For the
> current record and investigation paths, see
> [`INFORME_CONTEXTO_CUELLO_BOTELLA_U_20260929.md`](INFORME_CONTEXTO_CUELLO_BOTELLA_U_20260929.md).
> The [final P0–P6 log](P0_EXECUTION_20260928.md) declares
> `PRODUCT_BLOCKED`: the operational workflow and P5 campaign finished, but
> the user's required scientific U objective remains unestablished.

This document governs the **outstanding** work to deliver `siestaflow_hubbard`
as a standalone utility with its own CLI. The [earlier integration plan](PLAN_INTEGRACION_GLOBAL_DAG_U_POLINOMICO.md)
records what has already been implemented; completed phases are not repeated.
`AGENTS.md` retains priority for launching SIESTA nodes once a campaign is
authorized.

## 1. Verifiable goal and scientific limit

A person must be able to install the package, declare an FDF, pseudopotentials,
correlated sites, and an execution profile, then run
`init → run/status/resume → report` from PowerShell→WSL or directly on Linux,
including in a Slurm environment with an allocation already granted, without
an agent editing the live campaign. The Slurm path needs neither a second
scheduler nor an `sbatch` submission from every node; it uses the existing
allocation executor. The documented automatic policy must complete the
workflow or return a terminal state within its budget; an expert policy may
set different tolerances and limits before starting. The DAG must produce
versioned JSON and a regenerable Markdown report with the complete response
and a result **for each site**:

\[
\chi^0_{IJ}=\left.\partial n_I^{\mathrm{BARE}}/\partial\alpha_J\right|_0,
\quad \chi_{IJ}=\left.\partial n_I^{\mathrm{SCREENED}}/\partial\alpha_J\right|_0,
\quad U_I=[(\chi^0)^{-1}-\chi^{-1}]_{II}.
\]

The quantity in this version is `U_scalar_charge`, with its occupation
definition and projector declared. The report does **not** automatically
convert it to `Ueff_Dudarev`: SIESTA uses `U-J` in its collinear Dudarev
implementation, and that equivalence requires another physical contract. Nor
is an off-diagonal element automatically labeled the `V` of another
functional. The utility is considered complete even if a particular material
ends as a sensitive candidate, has no calculable U, or lacks physical
acceptance, provided the conclusion and its cause are correct and
reproducible. Agreement with a gap, lattice parameter, or literature may be
used as an independent comparison, never as a selector for alpha, estimator,
or U value.

**Certified v1 scope:** SIESTA 5.4.2 and spin modes for which the parser and
BARE/SCREENED protocol have real tests. Site count and MPI profile are campaign
parameters. There is no promised coverage for non-collinear spin, spin–orbit,
a calculated `J`, or a universal physical U. Expanding those capabilities
would be a separate version and will not block completion of this utility.

## 2. Baseline that will not be rebuilt

| Component | Current evidence | Actual outstanding work |
|---|---|---|
| CLI and DAG | The P3/P6 closeout exercised `init/run/status/resume/report/stop` from PowerShell→WSL and the public direct-manifest path for Linux/Slurm within an existing allocation. The adaptive DAG, budget, and selective resumption are implemented; P5 completed 25 serial nodes, and `resume` did not relaunch SIESTA. | Preserve evidence for the supported path and distinguish operational completion from the scientific U block. |
| Adaptive PBE NiO | The campaign contains 41 nodes: 1 reference, 20 BARE, and 20 SCREENED. The v3 analysis reports `NUMERICAL_CANDIDATE_UNASSESSED` and `physical_acceptance=NOT_ESTABLISHED` because no sensitivity tolerance was configured. The historical v2 analysis and the v3 reconstruction of the same OUT files are distinct versioned results; neither is overwritten. | Use the v3 reanalysis for current status and preserve historical artifacts and conclusions intact. Do not treat `STOP_STABLE` as passing a physical tolerance. |
| Occupation and precision | The v3 analysis fits `siesta_occupations_total`, the selected total from `Occupations:`; `matrix_trace` remains a check and historical v2 semantics. Precision is propagated from the actually selected tokens. | Keep one source per analysis/version and document the printing interval, fit sensitivity, and any repeatability term separately. Do not require a modified SIESTA executable for the portable path. |
| Report | The v3 schema and Markdown publish occupation source, per-site response, printing bound, fit diagnostics, SCF, and acceptance state. Historical v2 reports retain their original meaning. | Foreground the `PRODUCT_BLOCKED` status of the P0–P6 closeout and the limits of the numerical claim. |
| Policies | Operational gates, budget, symmetric refinement, and states completed P0–P6; the original NiO analysis lacked a preregistered sensitivity tolerance. | Prospectively determine what numerical guarantee and evidence allow a useful U to be declared under the user's goal, without changing the contract retroactively. |

The working tree already contains unconsolidated changes under
`src/siestaflow_hubbard`. Before editing, the executor will inspect affected
files and preserve `.out` files, manifests, and historical reports as
immutable evidence. It will not create a repository-wide hash inventory.

## 3. Investigation paths, in order, with required outputs

### R1. Define the fitted observable: one primary path

1. Read the local **SIESTA 5.4.2** source that accumulates and writes the
   matrix and `Occupations:`. Compare the actual print order with selected
   BARE and SCREENED events in the 41 NiO `.out` files; include at least one
   unpolarized case from the regression file. Documentation for another
   version does not determine this contract.
2. **If** the third `Occupations:` number represents the same internal sum of
   diagonals and each print interval agrees with the matrix trace from the
   same event, use that total as the primary reference, BARE, and SCREENED
   datum. Read its half-width directly from the token; retain `trace_total`
   only as an independent check. Recompute slopes, matrices, U, and the
   rounding bound from scratch. Never apply the six-decimal half-width to U
   computed from five-decimal diagonals.
3. **If** that equivalence fails, retain `trace_total` as primary with the
   half-widths of its diagonals; publish the specific discrepancy. If neither
   representation can be unambiguously tied to the physical event, end this
   path as `OBSERVABLE_UNRESOLVED`, with any prior value marked historical.
   Do not test additional observables until a new, verifiable hypothesis is
   available.
4. Changing the meaning of the fitted datum requires a mandatory
   `occupation_source` field and a new schema version if the interpretation of
   v2 changes. An old reader must continue to understand a v2 result as
   historical; `report` must never relabel its numbers.

**R1 output:** a documented decision, event-by-event comparison tables,
recalculated U for each site, and the printing bound for the variable actually
used, or a block with the code line / `.out` that demonstrates it. At most one
primary path and one alternative; do not choose the one that moves U closer to
the literature.

### R2. Distinguish sensitivity sources without inventing a total uncertainty

- **Printing:** propagate decimal intervals of the fitted datum through the
  fit and inversion. If the intervals allow a singular matrix or the bound
  cannot be certified, publish `bound_unavailable` and its cause; keep the
  point candidate separate.
- **Model/window:** compare cubic and linear fits on the same mesh and
  predeclared windows only when they have sufficient rank and degrees of
  freedom. Report each difference and why a window was excluded. Do not average
  estimators or increase the degree to improve R².
- **SCF:** retain the state of each reference and SCREENED calculation, number
  of iterations, final `dDmax`/`dHmax`, and tolerances. Report one-step BARE as
  `BARE_SINGLE_STEP`, even when SIESTA prints `SCF_NOT_CONV`. An SCF residual is
  not an error bar on U. The current NiO campaign does not justify a stricter
  default SCF rerun.
- **Electronic branch, projector, and algebra:** validate state continuity,
  projector identity across reference/perturbations, completeness of χ rows
  and columns, rank, and inversion. If any check fails, the DAG emits a
  terminal cause, not an apparent number.
- **Automation without a fictitious physical threshold:** a default policy
  may choose estimator, initial mesh, and operational budget; it is labeled
  `WITHIN_TOLERANCE` only when the scientific U tolerance is declared and its
  scope explained. Without it, the CLI ends normally with `UNASSESSED`, shows
  U and sensitivities, and does not require agent supervision.

**R2 output:** independent states and causes for `printing_rounding`,
`fit_window`, `scf`, `magnetic_branch`, `projector`, and `inversion`; no sum of
uncertainties from uncalibrated sources.

### R3. Decide whether a new calculation could change a conclusion

Add nodes only if there is a predeclared quantitative question whose answer
could change the state and whose cost fits the budget. For `shrink`, the policy
fixes the symmetric pair, window, and limit before dispatch. For `expand`, the
controller's already defined noise probe and signal/continuity predicates are
required; a partial probe neither certifies U nor authorizes expansion of other
columns. Changing the SCF level of the **final U** requires rerunning every
point used by its matrices at that same level; values must not be mixed. If a
threshold or budget is missing, the result ends as `UNASSESSED` or `SENSITIVE`
with a reason. A “promising” U or one close to literature never triggers a
round.

## 4. Decision contract that prevents cyclic iterations

| Gate | To continue or declare a candidate within policy | If it fails |
|---|---|---|
| Input | Compatible FDF/functional/pseudopotentials/projector/reference state; alpha, estimator, resources, and budget frozen. | `INPUT_INVALID`; fix before the first SIESTA run. |
| Data | One unambiguous event for each site, alpha, and mode, tied to normal output and parent DM; reference/SCREENED converged; BARE validated as one step. | `DATA_INVALID` or `NO_NUMERICAL_U`; do not fit incomplete data. |
| Calculation | Fit design with declared rank and DoF; usable χ⁰ and χ; reproducible inversion; occupations from a single branch. | `NO_NUMERICAL_U` or `NO_SINGLE_STATE_U`; retain diagnostics. |
| Evaluation | **Predeclared** sensitivity threshold, required metrics present and within it; two comparisons between comparable rounds for `STOP_STABLE` when using adaptation. | Candidate `UNASSESSED` or `SENSITIVE`; `STOP_LIMIT_SENSITIVE` when rounds/budget are exhausted. |
| Printing | Bound tied to the fitted observable and invertible matrices for all values admitted by that bound. | Candidate remains visible with `bound_unavailable`; do not certify decimals using another metric. |
| Result publication | JSON and report agree on datum, equation, per-site U, units, state, cost, and reasons. | A reporting failure blocks delivery; it does not rerun SIESTA. |

The implemented limits remain: at most `max_refinement_rounds`,
`max_alpha_points`, `total_siesta_node_budget`, and the number of profile
attempts. Configuration does not change mid-campaign. A terminal node is
reopened only when a reproducible error is identified in its input, output, or
code; the new campaign/analysis is versioned. **No agent may adjust
thresholds, alpha, or projector to force `STOP_STABLE` or a desired U.**

By software gate, two localized corrections are allowed with a rerun of the
failed test, and at most twelve localized corrections across the entire P1–P6
execution; counters do not reset when the agent or phase changes. If the same
failure appears a third time, or the global limit is exhausted, the one-shot
execution ends `BLOCKED` with file, command, output, and likely cause; it does
not begin another open-ended investigation. A critical block prevents product
completion. A `SENSITIVE` material with a valid method does **not** block the
product.

## 5. Implementation and test sequence for the one-shot execution

| Phase | Concrete work | Output evidence and advancement condition |
|---|---|---|
| P0. Freeze contract | Review only affected files; fix SIESTA 5.4.2 source, schema versions, two archived real datasets (multisite NiO and the Cu1 campaign in `docs/evidence/siesta542_openmpi_slurm_full_campaign_20260920_run2_wheel`, if its outputs pass integrity checks; if not, document another dataset selection before P1), test policy, and resource limit. | Short list of files/decisions and costs. Do not recompute historical hashes in bulk. |
| P1. Occupation source | Run R1 on existing `.out` files; implement one occupation adapter with explicit source and cross-check; migrate analysis without mutating v2. | Every fitted vector maps to its token and event; independently recompute χ, inverses, U, and bound. |
| P2. Mathematical decisions | Review states, window, printing, branch, SCF, and matrix; adapt only predicates that do not represent the §4 contract. | Tests with synthetic known U and adverse cases; every case ends in one state within budget. |
| P3. DAG, CLI, and report | Connect P1–P2 to the shared `run/resume/report` closeout for fixed and adaptive paths; add SCF summary and per-node table in JSON/Markdown; retain bounded automatic provenance. Route the public CLI by profile: pointer and supervisor for PowerShell→WSL; direct manifest for Linux and a Slurm allocation, without duplicating the parser or adding a new `sbatch` submission. Remove the `local_wsl` restriction only where the existing adapter and a test support it. | The same analysis yields the same JSON/report on resume; `report` does not invoke SIESTA; the user sees a cause and value when available; Linux/Slurm CLI controls the DAG through the documented public path. |
| P4. Regression without SIESTA compute | Reprocess the 41 NiO `.out` files and another archived real dataset; cover supported spin mode, multiple sites, BARE/SCREENED, singular matrices, limited resolution, branch change, budget, `resume`, and the **public** Linux/Slurm path with fixtures and archived real Slurm evidence. Run the public suite once and classify current/obsolete failures. | Product-relevant tests pass; every suite failure is fixed or explicitly retired with a reason. Old evidence retains its semantics and the new result has its own version. |
| P5. Final real test | One **new, small** campaign, with FDF and PSML audited beforehand and controlled entirely through the CLI from PowerShell→WSL. Primary path: one correlated site and six symmetric nonzero alpha values, `1 + 2×1×6 = 13` nodes. If no one-site FDF passes P0, choose the already known two-site PBE NiO with the same six alpha values **before calculating**: `1 + 2×2×6 = 25` nodes. Select exactly one campaign at P0, never two attempts based on U preference. Up to four laptop MPI ranks and one concurrent SIESTA run. Exercise `status/resume/report` without manually editing the FDF. Archived NiO covers the multisite adaptive regression. | Ends with a numerical result or honest scientific diagnosis; count ≤13 on the primary path or ≤25 on the alternative, without duplicate nodes or agent intervention during normal transitions. A post-launch failure is fixed/resumed in the same campaign without changing the material. |
| P6. Delivery | Install the built package in a clean environment; run the real quickstart for PowerShell and the public command on Linux within WSL; align README/manual/policies with the CLI and certified limits; set delivery version and change notes. | Installable artifact, reproducible commands on both surfaces, professional JSON and report, and a matrix of supported and pending capabilities without promising Ueff. |

P4 tests may be numerous because they are local and repeatable; P5 is bounded
and is a product test, not a search campaign for U. The new Slurm CLI is tested
against the existing executor and archived real outputs. A **new** Slurm test
with SIESTA is included only if P4 finds a defect that archived evidence
cannot resolve; its own budget is declared beforehand and is not charged to
P5. No phase uses lattice parameters, gaps, or literature U as an algorithm's
expected value.

### Integration and test map

| Contract | Modules reviewed and modified only if needed | Decisive check |
|---|---|---|
| Occupation source and precision | `siesta_backend/occupation_precision.py`, occupation parser, and `domain/quantized_response.py` | Fitted observation, source token, and interval map to the same event; unit test and NiO/Cu1 reprocessing. |
| Fit and decisions | `domain/matrix_response_acceptance.py`, `domain/adaptive_alpha.py`, `domain/adaptive_alpha_control.py` | Known synthetic data and singular/sensitive cases end with one cause; no loop exceeds its limits. |
| DAG and profiles | `execution/campaign_runner.py`, `execution/campaign_v2.py`, `execution/slurm_foreground.py`, `cli.py` | `run/resume` reuse valid nodes and exercise the same closeout in WSL, Linux, and Slurm; only one active SIESTA run on the laptop. |
| Scientific delivery | `reporting/lr_u_report.py`, JSON exporter, and versioned schema | `report` regenerates tables and diagnostics without running SIESTA; JSON and Markdown agree, and historical v2 remains interpretable. |

These names are inspection points, not an instruction to rewrite every file.
Existing tests `tests/unit/test_occupation_precision.py`,
`tests/unit/test_quantized_response.py`,
`tests/unit/test_matrix_response_acceptance.py`,
`tests/unit/test_adaptive_alpha_dag_resume.py`,
`tests/unit/test_campaign_runner_synthetic.py`,
`tests/unit/test_slurm_foreground.py`, and `tests/test_cli_and_manifest.py` are
the starting point; add only cases covering new contracts. The default
automatic policy, its units and limits, and the meaning of `UNASSESSED` must
be tested as part of P2 and documented in P6.

## 6. Final product criterion and closeout report

Declare `PRODUCT_READY` only when P1–P6 pass their gates, the CLI completes the
real test within budget, the versioned result regenerates from saved data, and
no critical defect remains in the supported path. The closeout will deliver:

1. Tested installation command and minimal `init/run/status/resume/report` example.
2. JSON + Markdown from a real campaign with the exact occupation definition,
   χ⁰, χ, per-site U, diagnostics, state, and cost.
3. Regression table: archived NiO, archived independent material, new campaign,
   Slurm fixture, and adverse cases.
4. Brief list of v1 capabilities out of scope (`Ueff_Dudarev` automatic, J,
   functional V, spin–orbit/non-collinear, universal presets), without
   disguising them as charge-calculation defects.

If a mandatory gate still fails after bounded corrections, the final state is
`PRODUCT_BLOCKED`, with one reproducible blocker and the minimum work needed
to reopen it. Never announce `PRODUCT_READY` because time ran out or because a
U matched the literature.

### Single assignment to agents after execution is authorized

> Execute P0→P6 in this document. Luna controls the changes and the only SIESTA
> campaign; Sol performs a focused audit of the scientific contract and
> corresponding diff, with effort matching the user's current instruction.
> Each audit returns `READY`, `LOCAL_CORRECTION`, or `BLOCKED` with evidence and
> is not repeated if the contract has not changed. Respect the gates, two
> corrections per failure, the 13-node budget on the primary path or 25-node
> budget on the P5 alternative, and terminal states. Do not expand scope to
> pursue a particular U. Deliver `PRODUCT_READY` or `PRODUCT_BLOCKED` with
> verifiable evidence.

## Methodological sources for the contract

- [Cococcioni and de Gironcoli, linear-response method](https://arxiv.org/abs/cond-mat/0405160): requires consistency between response and the definition of localized occupation.
- [SIESTA 5.4 Reference Manual, DFT+U](https://docs.siesta-project.org/projects/siesta/en/5.4/reference/siesta.html): defines projectors and use of `Ueff=U-J` on the collinear path.
- [Official ABINIT LRUJ tutorial](https://docs.abinit.org/tutorial/lruj/): shows comparison of linear/polynomial fits and their residuals; it does not set universal thresholds for SIESTA.
