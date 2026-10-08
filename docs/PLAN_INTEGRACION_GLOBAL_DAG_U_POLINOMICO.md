# Independent workflow closeout plan: DAG and response U

**Plan review:** 2026-09-28 · **Status:** Phases A–C executed; integration and operational testing completed.
**Authorized scope:** Phases A–C of §5, including the adaptive controller, Slurm/historical-path integration, synthetic tests, and a small operational SIESTA check in WSL at closeout. Limited to one concurrent SIESTA process and up to four MPI ranks on the laptop. Excludes exploratory scans and integration with the general orchestrator.

**Outcome of this run:** the adaptive controller and Slurm/historical paths are connected to the common analyzer; focused synthetic tests and a targeted audit are complete; an operational NiO PBE campaign ran in WSL with one active SIESTA process and 4 ranks. The DAG completed with 11 validated nodes and produced JSON v2 and a Markdown report. Expansion of α depends on a valid SCF noise measurement and explicit per-campaign thresholds; it is not enabled automatically by default, and tolerances are not inferred from NiO.

**Current architecture decision:** `siestaflow_hubbard` remains an independent scientific package with its own CLI. This task does not integrate it into the general `siestaflow` repository or another orchestrator. Modularity is preserved through stable internal contracts among the CLI, execution, analysis, and reporting, leaving future integration possible without coupling it now.

## 1. User-facing outcome

For a campaign configured for a material and an explicit set of correlated subspaces, the independent CLI currently supports:

```text
siestaflow init material.fdf --name MATERIAL --lr-config lr-config.json --profile local-wsl.json
siestaflow run campaign.siestaflow.json
siestaflow status campaign.siestaflow.json
siestaflow resume campaign.siestaflow.json
siestaflow report campaign.siestaflow.json
siestaflow stop campaign.siestaflow.json
```

This is the public interface already registered in `pyproject.toml`; `init` creates v2 campaigns with a fixed grid or adaptive policy, `run` and `resume` control the persistent WSL worker, `status` queries its state, `stop` requests a safe stop, and `report` regenerates/prints the report from saved analysis. The v2 report shows the numerical candidate or the precise reason it could not be calculated.

**Expected end-user workflow:** the user operates the package from PowerShell without opening Codex or editing FDF during the campaign. The local profile invokes SIESTA in WSL through a persistent launcher; the 2026-09-28 operational test confirmed that work continued after control returned to PowerShell and that `status` queried durable state. The CLI returns a campaign/job identifier, concrete failures, and results.

The scope covers **any material and any number of correlated sites** that satisfy the input contract. NiO and MnO are regression cases, not sources of constants, thresholds, or U values for the algorithm. MPI ranks are configured in the profile and validated against resources exposed by the runtime; for this laptop the profile may be set to at most four ranks. Only one SIESTA run is allowed concurrently per workspace. Slurm must use resources declared by its profile, with no laptop limits hard-coded into the mathematics.

The local profile declares the WSL distribution, Linux executable/version, Windows↔WSL path map, working directory, and MPI/concurrency limits. Slurm and historical paths, as well as Windows→WSL operation, were connected and verified in this run.

### 1.1 Operational priority: run simulations

For an authorized campaign, **priority 1 is to start and complete pending SIESTA calculations**. Traceability is recorded automatically and in proportion to risk; it does not become a sequence of manual reviews before each job. The pre-launch critical path contains only: compatible FDF/functional/pseudopotentials, present inputs, valid α policy and resources, and an immutable input-configuration identifier calculated **once per campaign version**. Once these checks pass, dispatch the first calculation without waiting for the report, literature comparisons, an audit of all historical files, or human review of hashes.

When each job finishes, the DAG automatically records the state and provenance of its outputs; analysis, reporting, and their hashes are produced after the calculation that feeds them. During `resume`, evidence is checked only for nodes intended for reuse, once per resume; a digest is recalculated only if missing, if the file changed, or if that node's validation requires it. Do not rescan or recompute hashes for the whole tree for every α, transition, or attempt. An integrity failure in a required artifact does prevent reuse of **that node** and requires rerunning it and its descendants, without stopping independent jobs that are ready to run.

## 2. Package status at closeout

The fixed-grid v2 path already exists. The implementation plan starts from that code and does not propose rebuilding the CLI or report from scratch.

| Area | Current status | Remaining work |
|---|---|---|
| v2 fitting and analysis | Common linear/polynomial analyzer with matrices, diagnostics, and per-site candidates in JSON. | Calibrate default tolerances against diverse cases; do not infer them from NiO. |
| Campaign DAG | Persistent WSL worker, serial execution, round-based refinement, budget, receipts, and selective resume. | No blocking structural functionality; complete scientific calibration of campaign policies before recommending presets. |
| Independent CLI | `init`, `run`, `status`, `resume`, `report`, `stop`, and `audit-fdf` available; tested from PowerShell→WSL. | Keep it as the package's own interface; no integration with the general orchestrator in this scope. |
| Persistence and resources | Configurable profile, validation against WSL CPUs, and one concurrent SIESTA run; campaign returned to `status=COMPLETED`. | Nothing pending for the verified local case; WSL shutdown/restart requires `resume`, as documented in the quickstart. |
| JSON and human-readable report | JSON v2 and `LR_U_REPORT.md` generated; public `report` command verified and its files retained in the campaign directory. | The `linear` policy in the two-amplitude smoke test is sensitive; it does not validate a cubic fit. |
| Adaptive α refinement | Versioned policy, decisions, rounds, probes, budget, and dynamic DAG integrated; synthetic tests complete. | Outer expansion only when the SCF probe quantifies noise comparably and the campaign declares thresholds; those thresholds are not supplied as universal constants. |
| Slurm and historical paths | Adapted to the common analyzer and report, with receipts and observation validation. | No integration remains within the authorized phases. |
| External integration | Not part of this delivery. | No connection to the general `siestaflow` repository; retain a modular interface for future integration. |

The package's canonical source is `src/siestaflow_hubbard`. Before editing, the implementer reviews only the files and changes they intend to touch, preserves existing modifications, and avoids copying code from historical campaigns as a parallel implementation. A general inventory or recomputation of hashes is not required to start this software task.

### 2.1 Status of the two previously recorded tasks

| Prior document | Status | Application to this plan |
|---|---|---|
| `ADAPTIVE_ALPHA_GRID_IMPLEMENTATION_TASK.md` | Integrated into the DAG and verified with synthetic tests. | Keep noise/tolerance calibration as explicit configuration before enabling expansion in real campaigns. |
| `PENDING_HUMAN_READABLE_RESULTS_EXPORT.md` | JSON v2 and canonical Markdown generated and verified by the public CLI in an operational campaign. | Keep Markdown as the canonical format; `.txt`/`.out` remains optional. |

The original documents are retained as a requirements record. If any criterion there mentions the former “acceptance gates,” apply the distinction in §3.2: data, electronic-branch, and algebra checks remain in force; intersection of three linear windows becomes a diagnostic, not a veto on showing a numerical candidate.

## 3. Scientific contract and reporting rule

For each perturbed site (J), observed site (I), and BARE/SCREENED mode, fit over amplitudes declared before seeing the result:

\[
n_I(\alpha_J)=c_0+c_1\alpha_J+c_2\alpha_J^2+c_3\alpha_J^3,
\qquad
\chi^0_{IJ}=c_{1,\mathrm{BARE}},\quad
\chi_{IJ}=c_{1,\mathrm{SCREENED}}.
\]

With rows = observed sites and columns = perturbed sites, invert the full matrices under the declared representation:

\[
K=(\chi^0)^{-1}-\chi^{-1},\qquad U_I=K_{II}.
\]

Keep off-diagonal terms in JSON as elements of the response kernel; **do not automatically label them as (V)** from another functional. The quantity obtained from spin-summed charge occupations is identified as `U_scalar_charge`. Its transfer to `Ueff_Dudarev` requires a separate physical contract; a numerical U report alone does not authorize writing `DFTU.proj` for production.

### 3.1 Estimator selection, applicable to any material

1. Declare `auto`, `polynomial`, or `linear` in a versioned policy. `auto` is the default **for new campaigns**, without silently changing the interpretation of frozen campaigns.
2. For a centered grid with at least five distinct amplitudes, positive and negative signs, a full-rank design, and at least one residual degree of freedom, `auto` uses the already implemented **degree-3 cubic**. With seven points it retains three residual degrees of freedom. Fit BARE and SCREENED using the same policy and all required channels.
3. When those requirements are not met, `auto` declares `linear_fallback` and explains why; it never pretends to have performed a cubic fit or lowers the degree without recording it. An explicitly requested `polynomial` mode fails clearly if the grid cannot support it.
4. Calculate the linear comparison estimator on **the same points**. If the grid supports narrower symmetric windows with enough residual degrees of freedom, also calculate their derivatives at zero. Record degree, coefficients, residuals, DoF, design condition, and amplitudes used per channel.
5. Select the model and grid using rules declared before the campaign; proximity to literature, gap, lattice, or magnetic moment is not part of selection. Do not average U values across models, windows, or sites.

The cubic estimator gives a derivative at α = 0; it does not automatically prove that all points belong to the same electronic branch. Validation of SCF convergence, magnetic continuity, and response provenance is independent of the fit.

### 3.2 Replace the intersection veto with a transparent diagnostic

Intersection of intervals from three linear windows is no longer a necessary condition to **show** a candidate. Retain the three values as `window_sensitivity_eV` and the cubic/linear contrast as `model_sensitivity_eV`. Bounds from rounding printed occupations are recorded as `printing_rounding_bound_eV`; they are not called confidence intervals or added to an unjustified total uncertainty.

Proposed states for the common result:

| State | Condition | Output |
|---|---|---|
| `NUMERICAL_CANDIDATE` | Validated data, same electronic branch, valid design and inverses; diagnostics within policy. | (U_I), matrices, sensitivity, and limitations. |
| `NUMERICAL_CANDIDATE_SENSITIVE` | (U_I) can be calculated by inversion, but window/model/noise exceeds a declared threshold or there is no admitted linear window. | Show (U_I), differences, and reasons; no automatic physical acceptance. |
| `NO_SINGLE_STATE_U` | Magnetic/electronic state changes among the perturbations used. | Curves and diagnostics; no single U obtained by mixing states. |
| `NO_NUMERICAL_U` | Incomplete or invalid observations, insufficient-rank matrices, or failed inversion. | Exact reason and available evidence; U field is null. |

Sensitivity thresholds belong to a versioned policy, with units and justification; they are not tuned using the NiO result. If no quantified SCF noise limit exists, report `noise_not_quantified` and avoid fictitious physical precision. Compatibility among sites is reported separately. Emit `U_common_scalar` only when a physical site-equivalence policy and an explicit aggregation rule support it; always preserve the (U_I).

Amplitude-node evaluation may complete successfully even when its conclusion is `no_linear_window`. The DAG must advance to `MATRIX_ANALYSIS` to produce the sensitive candidate or final diagnostic. Execution failures, incomplete outputs, invalid provenance, and branch changes retain their own states and do not become a scientific `PASS`.

### 3.3 Adaptive α refinement as part of the DAG

**Recommended choice for v1:** retain an initial symmetric grid of seven amplitudes `{-3h, -2h, -h, 0, h, 2h, 3h}` and use the cubic fit as the primary estimator when the design is valid. For each round and possible direction (`shrink`/`expand`), the policy must define its own active window, degree, and minimum degrees of freedom; points outside the window are retained as diagnostics and do not silently enter the active estimator. For this default grid, the `shrink` path adds `±h/2` and uses `|α|≤2h` in the first round; it then adds `±h/4` and uses `|α|≤h`. Thus each active estimate retains seven points, while outer points remain available to measure sensitivity. For a different grid, the policy must explicitly declare the sequence of new points and active windows for each branch.

The `expand` path adds predeclared outer pairs and includes them only in the active window of the round that calculates them. **Do not expand α based on a weak signal, a low residual, or an isolated SCF probe.** Require an empirical measurement of numerical SCF sensitivity, comparison of equivalent channels/vectors, a prediction of signal versus occupation/SCF noise within policy limits, and evidence of branch continuity. If the required versioned predicates and thresholds are unavailable, close with a sensitive candidate; do not expand or declare stability. Apply each accepted pair to all sites/modes. Two rounds add at most four α values: 11 total starting from an initial grid of seven, plus any targeted SCF-check jobs. This round limit is a **v1 cost cap**, not a physical constant; it may be explicitly increased in the campaign profile.

The `h` scale must be declared or selected through a visible preset. As a trial seed, `alpha_seed_span_eV = 3h = 0.1 eV` is reasonable: ABINIT uses 0.1 eV by default and reports a broad linear range in its tests. That result depends on ABINIT/PAW and does not prove that 0.1 eV is optimal for SIESTA; therefore it is recorded as a configurable seed, symmetry and nonlinearity are examined, and it is not hard-coded as universal truth. If an explicit validated grid exists in the manifest, retain it. `alpha_ceiling_eV` is a **separate bound** that must exceed the seed when expansion is enabled; otherwise, the controller proposes no outer pairs.

LR-U literature recommends several small perturbations of both signs and warns that large amplitudes can introduce nonlinearity/asymmetry. It does not prescribe seven points, two rounds, or a universal stability percentage. These are transparent engineering choices for an initial bounded policy; adaptive finite-difference work contributes the principle of balancing truncation and noise, not a U-specific recipe.

In each round, compare estimates obtained using the **same fit family and window-selection rule** fixed in the policy. The comparable signature includes method/degree, minimum DoF, selection rule, matrix policy, and SCF level; the specific active window may change according to the predeclared branch/round and is reported as a refinement variable, not as a method change. If the rule or SCF level of the observations used changes, reset the stable-comparison counter; do not count a method change as evidence of convergence. Retain central/full-window fits, the linear fit on the same data, and their residuals as diagnostics. The decision is not based on the lowest RMS of a single fit. A truncation predicate compares `U_I` from the active and interior windows under the same policy; its absolute/relative tolerances belong to the campaign and their units are reported. Without a configured threshold, evidence is reported as sensitivity and does not authorize automatic `shrink`. For each site, calculate the largest absolute change in `U_I` between comparable rounds and compare it against a mixed tolerance:

```text
delta_U(r) = max_I |U_I(r) - U_I(r-1)|
tol_U(r)   = max(tol_abs_eV, tol_rel * max_I |U_I(r)|)
```

`STOP_STABLE` requires `delta_U <= tol_U` for **two consecutive inter-round comparisons**, a consistent electronic/magnetic branch, usable matrices, and window/model sensitivity that does not worsen beyond its configured tolerance. Therefore, the initial grid and two comparable refinements are required; a policy with fewer than two possible rounds cannot emit `STOP_STABLE`. The absolute-relative form follows the pattern used by numerical software to control errors at different scales; the literature provides no universal percentage that certifies physical U. Thus `tol_abs_eV`, `tol_rel`, and window tolerances belong to a versioned policy: the default preset must be calibrated using a set of systems and convergence studies independent of NiO, and the report must print their exact values. If a required tolerance or predicate is not configured, stability is not claimed and a refinement depending on that criterion is not activated; the candidate remains marked sensitive.

The controller does not interpret fit RMS as physical uncertainty. It presents model/window sensitivity, the occupation-rounding bound, and SCF-convergence sensitivity separately. If the latter has not been measured, it is marked `noise_not_quantified`; convergence with respect to the α grid may be reported, but not a total numerical uncertainty.

**Targeted check within the same campaign:** after the initial grid, if SCF jobs converged but the norm of the occupation change for a column between `+h` and `-h` is near printed resolution according to the policy's `probe_trigger_ratio`, rerun only the reference point and that symmetric pair using the next stricter SCF level predeclared in the policy. Compare response vectors separately for BARE and SCREENED, using the same site ordering and amplitude; record the norm, vector print resolution, and difference between levels. The difference is an **empirical measure of sensitivity to the SCF criterion**, not a rigorous bound on U error. Do not compare incompatible scalar changes or interpret the maximum occupation change as U error. Limit the check to once per affected column and count all its nodes in the budget; do not mix results from the stricter level with earlier results when fitting a single matrix. If the stricter level is adopted for final U, consistently rerun the points used by the response matrices while retaining previous receipts as evidence. An unconverged SCF output follows the normal failure/retry path and is not used as a noise probe.

To define the probe comparison, for column J and mode m ∈ {BARE, SCREENED}, define `v_m^L(J,h)=n_m^L(J,+h)-n_m^L(J,-h)` and `eta_m(J)=||v_m^strict-v_m^base||₂`. `eta_m` is empirical response sensitivity to SCF level. The resolution of the difference vector is derived from the validated rounding intervals of both vectors; if these are unavailable, the probe is `noise_not_quantified`. Probe activation/materiality is evaluated separately by mode using configured ratios, never using the maximum of an isolated component. To propose expansion up to `a`, estimate `rho_m(J,a)=(a/h)||v_m^strict||₂/(eta_m(J)+q_m(J))`, where `q_m` is the deterministic rounding bound for the difference vector. `REFINE(expand)` requires an explicit `rho_min` and that required modes/columns satisfy it, in addition to the α bound and branch continuity. Because the grid and response matrices share α across all sites, global expansion requires complete metrics for all columns and both modes; a partial probe may trigger SCF improvement for affected columns but does not authorize expansion of the others. This linear projection only decides whether it is worthwhile to measure the new pair; it does not prove that the response remains linear outside the existing grid, which must be checked using the next round's data.


The versioned policy fixes the tolerance, permitted initial scale, maximum rounds/points, budget, and noise handling before execution. Points are not selected based on proximity to literature. The budget is counted as **additional actual SIESTA nodes** after expanding amplitudes across sites and modes; the DAG does not start an incomplete round if its cost exceeds the remaining budget. U values are not averaged across sites.

In each round, the controller also checks residuals, DoF, design condition, SCF convergence, magnetic state, and rank/condition of χ₀ and χ. It must record one of these decisions, with its reason, inputs, and consumed budget:

| Controller decision | DAG action |
|---|---|
| Controller decision | DAG action |
|---|---|
| `PROBE_SCF` | Reserve and run only the probe nodes authorized by policy; persist the probe's idempotent receipt/ID and cost first. Reevaluate the policy after validating the results. |
| `STOP_STABLE` | Conclude only after passing two consecutive inter-round comparisons under explicit tolerances, with branch, matrix, and sensitivity checks satisfied; two possible refinements are required. |
| `REFINE` | Record `shrink` or `expand` direction, active window/degree/DoF, predicates, and supporting values; `expand` requires measured empirical SCF sensitivity and a predeclared signal/noise criterion. Add a symmetric pair within the limits, materialize only its FDF files, and run only missing responses. |
| `IMPROVE_SCF_FIRST` | If the check reveals material SCF sensitivity, adopt only a preconfigured stricter level and rerun the points needed to analyze a matrix under consistent conditions; if the budget cannot cover it, stop and report the limitation. |
| `STOP_LIMIT_SENSITIVE` | Exhaust the budget or rounds without stability: close as **stability unresolved**, retaining and showing any numerical candidate with its sensitivity. |
| `STOP_INVALID` | Stop for invalid data, branch change, or unusable matrix; state the exact cause and do not mix states. |

A good residual is not equivalent to stability or physical acceptance. `STOP_LIMIT_SENSITIVE` and `NUMERICAL_CANDIDATE_SENSITIVE` may coexist: the first state expresses the campaign decision; the second indicates that a U estimate could be calculated. The policy, active windows, SCF level, budget, and decisions are frozen/versioned. Each round transition is persisted atomically before dispatching nodes; each durable node identity includes campaign/policy, α, site, BARE/SCREENED mode, SCF level, and relevant parent DM. Shared references are deduplicated and counted once. `resume` must reconstruct the same decision without repeating points, probes, or already committed cost. Convergence in α does not certify convergence with respect to supercell size, functional, pseudopotential, or projector definition; these are independent physical checks.

## 4. DAG input/output contract

### New campaign input

The existing v2 manifest declares the effective FDF and resolved `include` files, structure, correlated sites/subspaces and their projectors, pseudopotentials, functional, reference magnetic state, fixed α grid, estimator policy, validation, SIESTA identity, and execution profile. For the adaptive extension, add a schema version that also declares the **refinement and budget policy**; the adaptive result must be versioned compatibly with JSON v2. Do not silently change the meaning of fixed campaigns. Do not infer the subspace from the material name. If the FDF and pseudopotential provenance declare incompatible functionals, block before launching SIESTA; this prevents repeating the LDA/PBE mix-up.

The SIESTA adapter must provide normalized `ResponseObservation` objects with stable site labels, BARE/SCREENED mode, amplitude, occupations, parent DM, output, and validation receipt. Analysis consumes **only** verified observations; verification occurs when the output is consumed, not as a repeated audit before launching other independent simulations. The local profile declares `mpi_ranks` based on resources exposed by the runtime and `max_concurrent_siesta = 1`; Slurm uses the installation profile, without hard-coding laptop values into the mathematics.

The supervisor has a durable campaign record, a lock preventing two controllers from operating on the same DAG, a process/job identifier, and a heartbeat. If the process ends during a node, `status` reports it as interrupted; `resume` archives the partial attempt and retries only that node from validated inputs. Do not assume an old PID is still alive merely because it is saved on disk. Deterministic DAG gates require their own local handlers; they are not sent as if they were SIESTA commands.

### Canonical output per campaign

`results/lr_u_analysis.v2.json` is already the source for the fixed DAG and reports. For adaptive campaigns, retain the v2 contract when the extension is compatible; if incompatible fields or semantics are required, publish a new version rather than changing the meaning of v2. Minimum fields for a complete result:

```text
schema_version, campaign_id, material, functional, quantity,
site_labels, alpha_grid_eV, estimator_policy, selected_estimator,
chi0_raw, chi_raw, matrix_for_inversion, U_matrix_eV,
U_by_site_eV, U_common_scalar_eV_or_null,
fit_diagnostics_by_channel, window_sensitivity_eV,
model_sensitivity_eV, printing_rounding_bound_eV,
scf_and_magnetic_diagnostics, matrix_diagnostics,
alpha_rounds, refinement_policy, refinement_decision,
scf_probe_trigger_and_pairs, scf_levels_and_occupation_deltas,
cost_budget_and_consumption,
numerical_status, physical_acceptance, reasons, provenance
```

All unavailable numeric fields are `null` with an explicit reason; do not use `NaN` in JSON. `results/LR_U_REPORT.md` is the **canonical human-readable v2 format**, generated from that JSON. Its table identifies the material, campaign, functional, observable, value and unit, method/estimator, comparison reference when available, sensitivity by source, reportability status, and action permitted by the DAG. A section per site shows U, amplitudes, fits, and status; other observables appear only if present in the JSON, without invented references. The header records pseudopotentials, source files, hashes, analyzer version, and whether each datum is canonical or a candidate. A `.txt`/`.out` view may be added later as a derived view without creating another source of truth. JSON retains curves, matrices, and sources. Export is idempotent, records input/output hashes, and does not invoke SIESTA or submit Slurm jobs.

The `tools/scientific_dag_analysis.py` contract records the numerical result as `RECORDED_ONLY` and `physical_acceptance=NOT_ESTABLISHED`, unless a separate physical policy explicitly establishes more. `tools/scientific_dag_gate.py` retains the hash link among the JSON, verdict, and Markdown. Old campaigns keep their original schemas and verdicts; the new version does not rewrite NiO v1/v2, MnO, or their receipts.

## 5. Remaining work sequence

Refinement is applied as a versioned extension to the existing workflow; it preserves compatibility with fixed campaigns and earlier manifests.

### Phase A — Adaptive α controller and round-based DAG (complete)

- Add a versioned schema for the adaptive policy. Implement the seven-point symmetric grid and at most two rounds adding an inner or outer pair (up to eleven amplitudes) as proposed defaults; `h`, active windows per round/direction, degree/DoF, `alpha_seed_span_eV`, `alpha_ceiling_eV`, `probe_trigger_ratio`, signal/noise predicates/thresholds and tolerances, SCF ladder, and total budget must remain configurable and visible. The 0.1 eV seed requires validation for SIESTA before being announced as a product default.
- Calibrate the `tol_abs_eV`/`tol_rel` preset and window tolerances across diverse cases with known response data and numerical convergence; do not infer them only from NiO or copy another library's default tolerance. Until that calibration exists, require an explicit policy to enable `STOP_STABLE`/tolerance-based refinements and allow budget-based closeout as a sensitive candidate.
- Implement the §3.3 decisions `STOP_STABLE`, `REFINE`, `IMPROVE_SCF_FIRST`, `STOP_LIMIT_SENSITIVE`, and `STOP_INVALID`. Each decision saves its supporting diagnostics and remaining cost.
- For `REFINE(shrink)`, require that the U difference between inner/active windows exceed the versioned truncation threshold; select the degree and points according to the frozen active window. For `REFINE(expand)`, require a validated SCF probe, a signal/noise metric for equivalent channels, configured tolerances, and branch continuity. If a predicate is missing, close as sensitive. Add the corresponding symmetric pair within declared limits, materialize only missing FDFs, expand the pair across all sites/modes first, and check the full round cost. The new round retains still-valid nodes and receipts; `resume` reruns only incomplete or invalidated work and its descendants.
- Implement §3.3 `PROBE_SCF` as diagnostic nodes activated once per affected column, without rerunning the full campaign to measure sensitivity. Its receipt identifies the reference, ±α pair, comparable BARE/SCREENED vectors, SCF level, print resolution, empirical difference, and decision. If global α expansion is considered, complete probes for all required columns/modes or close without expansion. Count cost before dispatch, deduplicate shared references, and do not reuse a response from another SCF level in the final fit.
- If an SCF ladder is supported, version it and apply the same level to the entire set used to compare derivatives; never mix responses converged under different SCF criteria without recording it and rerunning the relevant set.
- Keep calculation status, the numerical U candidate, and physical acceptance independent. Lack of stability neither removes a calculable candidate nor presents it as converged.
- Preserve reading of fixed-grid v2 manifests/analysis. Adaptive integration must use a new version or validated additive schema extension; do not silently reinterpret earlier campaigns. Persist each policy/decision atomically before dispatching work; node identity includes policy, round, α, site, mode, SCF level, and relevant parent DM.

**Delivery:** an adaptive campaign that decides whether to continue or stop within budget, records why, and reuses valid amplitudes without repeating their SIESTA runs.

### Phase B — Slurm and historical adapters (complete)

- Connect the Slurm template to the common observation, analysis, and reporting contract; the adapter submits scientific nodes according to the cluster profile and preserves the same JSON/Markdown as the local path.
- Adapt `production_benchmarks/lr_arithmetic.py` and `campaign_controller.py` to the common analyzer. Historical paths may convert their observations to the common contract, but must not maintain a parallel U formula or policy.
- Keep this phase decoupled from the PowerShell/WSL CLI: Slurm is another backend for the standalone package, not an integration with the general SIESTAFLOW orchestrator.

**Delivery:** the same reproducible analysis in local and Slurm profiles from equivalent observations.

### Phase C — Synthetic verification and operational closeout (complete)

- Cover linear/cubic fitting, N=1/2/3, five-/seven-point grids, insufficient DoF, branch changes, singular/ill-conditioned matrices, per-site differences, rounding versus sensitivity, output failures, refinement, and cost limits.
- Verify `REFINE` using only new FDFs, stability over consecutive rounds, conditional activation of the SCF check, expansion only after a confirmed weak signal, consistent SCF level across matrices, budget including diagnostic nodes, `STOP`/`UNRESOLVED` with no extra jobs, interruption/resume without duplicate nodes, idempotent reporting, and that report-only changes do not rerun SIESTA.
- Reproduce, without new SIESTA runs and using already validated existing PBE data, approximately 6.8684 eV (NiLR0) and 6.8638 eV (NiLR1) for `U_scalar_charge`. Investigate any difference as a change in data, contract, or algebra; do not tune thresholds to force agreement.
- Complete an operational Windows→WSL check from ordinary PowerShell using a small PBE case based on existing audited inputs: launch, close the terminal, query `status`, recover with `resume` if applicable, and generate JSON/report. On the laptop use at most four MPI ranks and one concurrent SIESTA process. This test establishes persistence; synthetic tests alone do not.
- Audit the contract and final diff once. Under the user's current instruction for this integration, Luna GPT-6 max executes and Sol GPT-6 high performs targeted review of contracts or concrete findings; do not repeat audits for every amplitude or conduct general repository reviews.

**Delivery:** scientific, resume, and operational criteria verified; no new campaign is launched merely to run software tests.

## 6. Acceptance criteria and limits

### Already implemented in the fixed v2 path

- Independent CLI with `init`, `run`, `status`, `resume`, `report`, `stop`, and `audit-fdf`, registered as an installable command.
- Fixed-grid campaign with configurable MPI profile, persistent WSL worker, serial execution, JSON v2 analysis, and Markdown report generated from saved data.
- The report shows the occupation dataset, fits, matrices, diagnostics, sensitivity, and provenance; it requires no PDF or heavyweight dependencies.
- Focused verification: synthetic controller/DAG/common-analysis tests passed; targeted tests confirmed `audit-fdf`, UTF-8 bridge output, and safe output on a cp1252 console. The operational PBE campaign ran with SIESTA/MPI and generated JSON/Markdown reports.

### Criteria covered at integration closeout

- The DAG decides `REFINE`/`STOP` using an explicit policy and budget, adds only new FDFs, and retains valid receipts between rounds.
- If an initial response is near resolution, a targeted, budgeted SCF check allows a choice between improving SCF, expanding α within its bound, or closing with a diagnostic. Expansion requires a noise measurement and configured predicates for all involved sites/modes; the report does not present occupation differences as a rigorous error bound.
- Invertible per-site candidates are shown even if stability is unproven; branch changes, invalid data, or impossible inversion produce their own state and reason. The report separates numerical candidacy from physical acceptance.
- The same policy and observations produce the same result in continuous execution and after `resume`. Editing only the report does not rerun SIESTA.
- The adaptive controller and results are versioned without altering manifests, data, or receipts from earlier fixed campaigns.
- The general contract works for different materials and site counts; NiO/MnO serve as regressions and do not determine constants or thresholds.
- Slurm integration and historical paths use the common analyzer and report; the package remains independent and does not depend on the general SIESTAFLOW orchestrator.
- The Windows→WSL path was operationally verified using an authorized SIESTA campaign on 2026-09-28; work persisted after control returned to PowerShell.
- The critical path of an authorized campaign launches the first SIESTA after the minimum physical checks in §1.1. Hashes are automatically recorded once per relevant input/output; the entire tree is not inspected or rehashed for each node.

A real simulation is not required to check the mathematics using saved inputs or synthetic adapters, but it is required to claim that persistent Windows→WSL operation has been demonstrated. Implementation must not start new campaigns during software phases without express authorization.

## 7. Execution and closeout evidence

Execution followed `AGENTS.md`: Luna GPT-6 max implemented and ran the work; Sol GPT-6 high performed a targeted audit of the adaptive contract and pre-campaign scientific check. No exploratory scans were launched and manual hash reviews were not repeated.

- Phases A–C were implemented and verified; the local PBE smoke test used SIESTA 5.4.2, 4 MPI ranks, and maximum concurrency 1.
- The PowerShell process ended after dispatching the worker; subsequent checks confirmed persistence and `status=COMPLETED` with 11 validated nodes.
- The smoke-test report gives `U_scalar_charge = 6.86087028 eV` per site and status `NUMERICAL_CANDIDATE_SENSITIVE`. Because it used only α = ±0.025 eV and a linear estimator, this verifies operational/analytical DAG closeout, not cubic stability or physical acceptance.
- The smoke test exposed cp1252 decoding of the report on Windows; the bridge was corrected to read UTF-8 and emit safe text to legacy consoles.
- Accessible evidence: `campaigns/nio_pbe_cli_smoke_20260928/results/LR_U_REPORT.md` and `campaigns/nio_pbe_cli_smoke_20260928/results/lr_u_analysis.v2.json`.

No user decision remains pending to close the authorized scope. α expansion for future materials should be activated only if a comparable SCF noise measurement and explicit campaign thresholds allow signal to be distinguished from noise; otherwise, the DAG reports a sensitive candidate and stops within budget.

## Internal and methodological references

- [Polynomial response fitting](RESPONSE_POLYNOMIAL_FIT.md): current implementation and fit limitations.
- [Adaptive α refinement](ADAPTIVE_ALPHA_GRID_IMPLEMENTATION_TASK.md): requirements incorporated into the DAG controller; its implementation and synthetic tests do not by themselves authorize a new SIESTA campaign.
- [Human-readable results report](PENDING_HUMAN_READABLE_RESULTS_EXPORT.md): requirements incorporated into the canonical v2 Markdown report.
- [Cococcioni and de Gironcoli, linear response](https://arxiv.org/abs/cond-mat/0405160).
- [Official ABINIT LR-U(J) tutorial](https://docs.abinit.org/tutorial/lruj/): precedent for polynomial regression over multiple perturbations.
- [MacEnulty et al., LR-U/J practices](https://doi.org/10.1088/2516-1075/ad610f): amplitude, noise, nonlinearity, and response sensitivity.
- [Shi et al., adaptive interval for noisy finite differences](https://arxiv.org/abs/2110.06380): numerical basis for balancing truncation error and noise; not a physical rule specific to calculating U.
- [Official SciPy `quad` documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.quad.html): example of a stopping criterion with absolute/relative tolerances and an evaluation limit; its numerical default is not transferred to the U estimator.

## Implementation history — updated 2026-09-28

Phases A–C are closed. In addition to focused synthetic tests, targeted tests of PBE `audit-fdf` and CLI UTF-8 handling passed; the smoke test generated a Markdown/JSON report and verified persistent Windows→WSL operation with a low-cost real SIESTA campaign. The scope remains independent of the general SIESTAFLOW repository. Calibrating policy tolerances across material families and selecting recommended presets remain future scientific work, not integration blockers.
