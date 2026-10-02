# HubbardFlow — Codex task list, phase 2 (automatic perturbation planning, end to end)

Scientific specification (authoritative, read it first):
`docs/fdebq/HUBBARDFLOW_PERTURBATION_PLANNING_REVIEW.md` (sections cited as §A…§Y).
Earlier specification: `docs/fdebq/HUBBARDFLOW_FDRC_INDEPENDENT_REVIEW.md`, `docs/fdebq/ERRATA_I3.md`.
Repository rules: `AGENTS.md` (rule 5 is amended by TASK 6 below).
Phase 1 (TASK 0–5, FD-EBQ diagnostics) is already merged in `codex/hubbardflow-rename`.

## Goal of the whole phase

Given an authoritative SIESTA FDF, HubbardFlow decides **by itself, deterministically and with evidence**:

1. which atoms carry correlated (DFTU) subspaces and how they map to species/projectors (§C);
2. how many and which sites must be perturbed, using response symmetry only when F1–F8 prove it, with perturb-all as the safe fallback (§D–§H);
3. which finite-difference amplitudes each (column, mode) uses (§J–§N);
4. the frozen `ResolvedPerturbationPlan` that feeds the existing campaign DAG, execution, matrix analysis, U computation and certification (§O–§Q, §Y.12).

The human only supplies the FDF, resolves `AMBIGUOUS` / `NOT_ESTABLISHED` / `REVIEW`, and chooses the machine.
Scientific logic that is **not yet validated** (spin-flip ε=−1, rotations, automatic species splitting, calibrated α,
optional shadow) ships **implemented but disabled by flag**, never absent from the contract (§X).

## Working rules for every task

- One task = one branch = one commit (or a few), stacked on the previous task's branch, named
  `fdebq/taskNN-<slug>`. Push every branch. **Do not try to create PRs** (the user opens one PR at the end).
- Layering from `AGENTS.md` is strict: `domain/` pure (no I/O, clock, randomness), `siesta_backend/` interprets
  SIESTA files, `execution/` calls domain and never re-decides science.
- New code is covered by the ruff/mypy-strict scope in `pyproject.toml`: **extend the `include`/`files` lists in the
  same task** for every new module and test.
- Every tolerance, band, threshold or multiplier lives in a versioned policy/protocol object that enters its digest.
  No literal numerical thresholds in logic. Values for the first policy profile are given in TASK 9 and must be
  copied exactly.
- Every ambiguity resolves to the conservative outcome: `AMBIGUOUS` / `NOT_ESTABLISHED` → perturb more, never less.
- A decision may never read U, its stability, or the condition number (§P "no circularity").
- Frozen V6 baseline: read only. `bash tools/check_v6_integrity.sh` must print `V6 GATE OK` before each commit.
- Existing production behaviour must not change unless a task says so and a golden test proves equivalence.
- If a task cannot be completed as written (missing fixture, spec contradiction, a test that cannot pass without
  weakening it), **stop that task, write `docs/fdebq/BLOCKERS.md` with the exact reason, and continue with the next
  independent task**. Never weaken a test to pass it and never invent a threshold.
- After each task write the PR note to `C:\Users\Jairo\work\fdebq_pr_notes\TASKNN-<slug>.md` (what, why, tests, what is
  deliberately not done).

Each block below can be pasted into Codex as the prompt for that task.

---

## TASK 6 — Governance and documentation (docs only)

**Do.**
1. Copy into `docs/fdebq/`: `HUBBARDFLOW_PERTURBATION_PLANNING_REVIEW.md`, `CODEX_TASKS_PHASE2.md`
   (both provided by the user in `C:\Users\Jairo\work\fdebq_phase2\`).
   Also copy `coverage_review_checks.py` and `toy_symmetry_ring.py` to `docs/fdebq/reference/`.
2. In `AGENTS.md` replace rule 5 with exactly:
   > 5. Never infer site equivalences from element, label, coordination or chemical similarity, nor from the
   > similarity of U values. Equivalences may be used to reduce perturbations only through a
   > `CoverageQualification` produced by `domain/coverage.py`: operations satisfying F1–F8
   > (`docs/fdebq/HUBBARDFLOW_PERTURBATION_PLANNING_REVIEW.md` §F) with declared tolerance bands, a mandatory shadow
   > column per reduced class, and fallback to explicit perturbation of the whole class on any failure.
   > User-declared equivalences may only restrict a reduction, never add one.
   Add rule 5b: "Features listed as 'disabled by flag' in `docs/fdebq/CODEX_TASKS_PHASE2.md` (spin-flip ε=−1, rotations,
   automatic species splitting, calibrated α grid, optional shadow) must stay disabled by default and may be enabled
   only by an explicit policy value that is recorded in the plan digest."
3. Add a short `docs/fdebq/README.md` indexing the documents.

**Do not.** Touch code. **Done when.** V6 gate OK; `git diff` shows only docs and `AGENTS.md`.

---

## TASK 7 — Single FDF model and canonical subspace inventory (read-only) (§C, §T row 1–2)

**Goal.** One audited parser for the supported FDF subset and a pure canonical inventory; fail closed outside the subset.

**Create** `src/hubbardflow/siesta_backend/fdf_model.py` (reuse `campaign_v2.resolve_fdf_includes`; do not duplicate it):
- `parse_effective_fdf(path) -> FdfModel` (frozen dataclasses): lattice (`LatticeConstant`, `LatticeVectors`/`LatticeParameters`),
  `NumberOfAtoms`, `NumberOfSpecies`, `ChemicalSpeciesLabel` (index, Z, label), `AtomicCoordinatesFormat` (Fractional, Ang,
  Bohr, ScaledCartesian — each converted to fractional exactly, with the conversion recorded),
  `AtomicCoordinatesAndAtomicSpecies` (atom_index 0-based, species index, coordinates, optional trailing label),
  `DFTU.Proj` records `(label, n, l, U_ref, J_ref, rc, omega, lambda…)` exactly as the existing adapter reads them,
  `DFTU.Method`, `DFTU.PotentialShift`, `Spin`/`SpinPolarized`, `SpinOrbit`, `DM.InitSpin` block (kept only as *declared input*, never as evidence),
  `MeshCutoff`, `kgrid` block / `kgrid_cutoff`, `PAO.Basis` blocks by label, `PAO.BasisSize`, `PAO.BasisType`.
- Digest of the effective FDF (after includes) and of each relevant block.
- `species_identity(model, search_dirs) -> dict[label, SpeciesIdentity]`: sha256 of the pseudopotential file
  (`<label>.psml`/`.psf`/`.vps`), of the label's `PAO.Basis` block (label-stripped canonical text), of the `.ion` file when present, plus Z.
  Missing pseudopotential file → `SPECIES_IDENTITY_NOT_ESTABLISHED`.
- Closed, stable error/status codes, at least: `UNSUPPORTED_SYNTAX`, `AMBIGUOUS_DFTU_LABEL`, `DFTU_LABEL_MULTIPLE_ATOMS`,
  `DFTU_LABEL_NO_ATOM`, `SPECIES_IDENTITY_NOT_ESTABLISHED`, `NONCOLLINEAR_OR_SOC_NOT_SUPPORTED`.

**Create** `src/hubbardflow/domain/subspace_inventory.py` (pure):
`CorrelatedSubspace(site_id, atom_index, species_label, Z, dftu_record, identity_digest)`,
`CorrelatedSubspaceInventory(subspaces, effective_fdf_sha256, status, reason_codes, digest)`,
`build_inventory(model, identities) -> CorrelatedSubspaceInventory` with deterministic order by `atom_index` and
the status machine `OK | SHARED_LABEL_NEEDS_SPLIT | NOT_SUPPORTED | SUBSPACE_MAPPING_NOT_ESTABLISHED`.
A DFTU label used by several atoms is `SHARED_LABEL_NEEDS_SPLIT` (the split is TASK 15), not an error to hide.

**Tests.** Cases from the repo fixtures (CoO, NiO, MnO, Cu3N FDFs found under `campaigns/`, `benchmarks/`, `tests/fixtures`; read
only), plus synthetic FDFs for: reordered atoms, `%include`, each coordinate format, unsupported syntax, two atoms sharing a
DFTU label, DFTU label with no atom, missing PSML, noncollinear/SOC. Cross-check test: for every existing campaign FDF
the inventory agrees with what `campaign_v2.validate_reference_fdf` accepts (same sites, same atom indices).

**Do not.** Change `campaign_v2.py` or `fdf_symmetry_adapter.py` yet. **Done when.** gates pass; fail-closed tests cover every code.

---

## TASK 8 — Reference state evidence (read-only) (§Q `state_evidence`, §F5, §F7, §F8)

**Create** `src/hubbardflow/siesta_backend/reference_state_evidence.py` extending `reference_magnetic_evidence.py` (keep its
API untouched) with `ReferenceStateEvidence` (frozen) built from the FDF text and the **reference SCF output**:
final collinear moments per atom with their printed half-width; normal completion and SCF convergence flag;
effective real-space `InitMesh` divisions; effective k-mesh; **local occupation matrices per correlated subspace and spin**
(read them with the existing parsers/`occupation_precision.py`; print half-width per entry) and their eigenvalue spectra;
digests binding it to the FDF and the output file. Missing/partial data → `REFERENCE_NOT_ADMISSIBLE` with reason codes.
`DM.InitSpin` is never evidence.

**Create** `domain/state_evidence.py` (pure dataclasses mirroring the above, plus `spectrum_difference(a, b, flip: bool)`).

**Tests.** Real archived SIESTA outputs from the repository (CoO V6, NiO V6, MnO v3r2, Cu3N, FeO diagnostic; read only) and
corrupted/truncated variants → `REFERENCE_NOT_ADMISSIBLE`. A test must show that FeO-type orbital differences between
nominally equivalent sites are visible in the spectra, if the archived FeO export contains the needed data; otherwise
record that as a documented limitation in the PR note.

**Done when.** gates pass.

---

## TASK 9 — Operations, bands and the F1–F8 classifier (§D, §E.4, §F, §G)

**Create** `domain/symmetry_operations.py` (pure; move the geometric core of `src/symmetry_reduction_proposal.py::detect_symmetry`
without changing that file's behaviour — leave it in place and add a test showing both agree on translations):
- `Operation(rotation_int, translation_frac, eps: Literal[1, -1], atom_permutation, correlated_permutation)`;
  `eps = -1` is the **global spin flip** of collinear spin without SOC, *not* a vector-axial transformation of the moment (§E.4, §A of the
  `detect_symmetry` audit).
- `candidate_operations(model, geometry_band)`: all lattice-compatible rotations that are signed permutations of the lattice
  axes **plus** (if `spglib` is importable) its operations; spglib missing → only the signed-permutation set and a recorded
  reason; never a silent guess. Deterministic order. Exactness class per operation:
  `EXACT_TRANSLATION` (rotation = identity), `EXACT_IN_CONTINUUM_ONLY` (rotation ≠ identity).
- `EquivalenceBands(tau_eq, tau_neq)` per quantity and `CoveragePolicy` (frozen, versioned, digested, **no defaults in code
  except the named profile below**).
- `classify(op, inventory, state, policy) -> OperationClassification` with one result per condition F1…F8, each
  `EQUAL | DIFFERENT | AMBIGUOUS | NOT_APPLICABLE` plus the measured value. Any `AMBIGUOUS` or `DIFFERENT` excludes the operation.
  F6: `eps = -1` additionally requires collinear spin, no SOC, spin-independent perturbation/observable (read from the FDF model).
  F4: rotations need a complete l shell (`DFTU.Method 2`) and invariant k-mesh, else `DIFFERENT`.
  F8: classify the commensurability of the translation with the real-space mesh from `ReferenceStateEvidence`
  (`COMMENSURATE | INCOMMENSURATE`), recorded, not used to exclude translations.
- `close_under_composition(ops)` verifying group closure over the correlated permutations; non-closure → the whole set is dropped and a reason recorded.
- `orbits(group, inventory)`: orbit of each correlated subspace; representative = minimum `atom_index`; shadow = next reachable minimum
  index (deterministic).

**Named profile `coverage-policy-v1`** (copy exactly; these are *declared protocol values*, not results-driven; every ambiguity
only costs compute because AMBIGUOUS expands, and every reduction carries a mandatory shadow):
- geometry: `tau_eq = 1e-5`, `tau_neq = 1e-3` (fractional coordinates, max over atoms after periodic wrapping);
- magnetic moment difference `| m_g(s) − eps·m_s |`: `tau_eq = 10 × print_half_width`, `tau_neq = 1000 × print_half_width`
  where `print_half_width` is the larger of the two atoms' printed half-widths from `ReferenceStateEvidence`; floor the half-width at `5e-7`;
- spectral difference (max over sorted eigenvalue pairs of the local occupation matrix, in e): `tau_eq = 10 × print_half_width_entry`,
  `tau_neq = 1000 × print_half_width_entry`;
- strategy flags: `allow_spin_flip = False`, `allow_rotations = False`, `shadow = MANDATORY`.

**Tests.** Mean-field ring and structure toys reproducing every positive and negative case of `docs/fdebq/reference/toy_symmetry_ring.py`
and §D.5 counterexamples (equal |m| but different environment; symmetric structure with spontaneous symmetry breaking; ferrimagnet; near-symmetric
structure inside the band → AMBIGUOUS; same label different `PAO.Basis`). Property tests (hypothesis): group closure; orbit partition; determinism under atom reordering.
**Zero false acceptances** on the negative set is a hard test.

**Do not.** Wire into production. **Done when.** gates pass.

---

## TASK 10 — `CoverageQualification`, diagnostic mode (§Q, §H, §U.3)

**Create** `domain/coverage.py`: `CoverageClass(members, representative, shadow, ops_rep_to_member, status)`,
status machine `PROVEN | CANDIDATE_PENDING_SHADOW | REJECTED_EXPANDED | NOT_ESTABLISHED | DISABLED`,
global strategy `ALL_SUBSPACES | SYMMETRY_REDUCED | PARTIALLY_REDUCED | USER_RESTRICTED`, `reasons`, digest, and
`qualify_coverage(inventory, state, model, policy, user_policy) -> CoverageQualification` implementing §P exactly:
coverage disabled / missing evidence / any AMBIGUOUS leaving an orbit uncovered / identity not established / unsupported syntax /
small system with `|orbit| = |S|` → `ALL_SUBSPACES` with the reason code. User-declared classes may only restrict (§F).

**Create** `tools/hubbardflow_plan_diagnose.py` (read-only): inputs FDF + reference output → JSON + human Markdown report with the
inventory, operation classification table (F1–F8 values), orbits, `would_reduce_to N representatives`, and every reason code.
In this task the tool **never reduces anything**; it reports.

**Tests.** Golden reports for CoO, NiO, MnO (expected diagnostic: CoO 2→1 and MnO 16→1 only for `eps=-1` flag on; with flags off MnO 16→2),
Cu3N, and the negative controls of TASK 9; `ALL_SUBSPACES` fallback tests for each trigger in §H.

**Done when.** gates pass; reports are deterministic (byte-identical on re-run).

---

## TASK 11 — Reconstruction, free checks, retrospective V1 (§E, §R V1, §U.4–U.5)

**Create** `domain/response_reconstruction.py` (generalises `campaigns/mno_afmii_strict_lr_v3r2/scripts/lru_core.py::reconstruct`, which stays untouched):
`reconstruct_matrix(columns_by_representative, classes, ops) -> raw matrix` permuting rows **and** columns with the same Π_g (§E.1);
`reciprocity_residuals`, `stabilizer_residuals` (free checks when a representative has a nontrivial stabilizer);
report of the norm of any symmetrization (raw is always retained). Matrices of occupations (not traces) are *not* supported:
reject explicitly (§E.2).

**Create** `tools/v1_retrospective.py`: reproduces on archived campaigns (read only) CoO V6, NiO V6, MnO v3r2 A/B, Cu3N (X/Y/Z) the
shadow–reconstruction consistency within FD-EBQ budgets (TASK 2) and records the α-independent discrepancy; output JSON + Markdown.
It must reproduce the numbers of `docs/fdebq/reference/coverage_review_checks.py` for CoO and MnO.

**Tests.** Synthetic permutation tests (machine precision); the retrospective tool on bundled archived data; a negative test where a deliberately
wrong permutation is detected.

**Done when.** gates pass; `docs/fdebq/V1_RETROSPECTIVE_REPORT.md` generated and committed.

---

## TASK 12 — `ResolvedPerturbationPlan` and the planner (pure) (§O, §P, §Y.12)

**Create** `domain/perturbation_plan.py` with exactly the schema of §Y.12 (frozen dataclasses, `schema = "hubbardflow.resolved_perturbation_plan.v1"`,
canonical JSON, `digest`, `to_mapping/from_mapping`, `status ∈ {READY, REVIEW, NOT_ESTABLISHED, FAIL}` + reason codes), embedding
`CorrelatedSubspaceInventory`, `ReferenceEvidence`, `CoverageQualification`, per-(column, mode) `ColumnPlan` from TASK 1
with `alpha_strategy ∈ {FIXED_PROTOCOL_GRID, USER_EXPLICIT_GRID, CALIBRATED_GRID}`, `computed_columns`, deterministic `run_specs [(J, mode, ±a_k)]`,
`reconstruction_maps`, bands, versions.

**Create** `domain/perturbation_planner.py`: `resolve_perturbation_plan(...)` implementing §P with injected evidence (pure). In this
task only `FIXED_PROTOCOL_GRID` and `USER_EXPLICIT_GRID` execute; `CALIBRATED_GRID` raises `NOT_ESTABLISHED` with the reason `CALIBRATION_NOT_ENABLED`.
Coverage strategies available: `ALL_SUBSPACES` (default) and `SYMMETRY_REDUCED` for translations with `eps=+1`.

**Golden test (critical).** For CoO V6, NiO V6, MnO v3r2 and Cu3N the planner with explicit sites + the V6 grid and `coverage = DISABLED`
produces run specs identical (site, mode, alpha, directory-independent identity) to those the current `campaign_v2` produces. Digest invariant to input order.

**Do not.** Modify `campaign_v2.py`. **Done when.** gates pass.

---

## TASK 13 — Integration in `campaign_v2` (sites optional) (§T)

**Modify** `execution/campaign_v2.py`:
- `lr-config.sites` becomes optional. When absent, the inventory (TASK 7) fills it; when present, it is **validated against the inventory**
  (this closes the gap that today nothing checks `AtomicCoordinatesAndAtomicSpecies`: atom_index/species mismatch → `CampaignV2Error`).
- `lr-config.coverage` ∈ {`DISABLED`, `DIAGNOSTIC` (default), `TRANSLATION_SHADOWED`}: `DIAGNOSTIC` records `CoverageQualification` in the campaign lock and
  perturbs everything; `TRANSLATION_SHADOWED` activates the reduction of TASK 14.
- `alpha_grid_ev` keeps working as `USER_EXPLICIT_GRID`/`FIXED_PROTOCOL_GRID`.
- The frozen `ResolvedPerturbationPlan` (digest) is written next to `campaign.lock` and checked on resume; any change of FDF, reference DM, bands or policy invalidates it.
- Pilot-to-production reuse (§Q): reuse only when FDF, parent DM, target, exact α, mode, DFTU record, backend identity/version, SCF profile, parser version,
  magnetic state and scientific profile all match — never by file name.

**Tests.** Existing campaign tests keep passing unchanged; new tests for sites auto-fill, mismatch rejection, resume invalidation, reuse rules.
**Done when.** gates pass; V6 golden equivalence from TASK 12 still holds through the real `campaign_v2` path.

---

## TASK 14 — Translation reduction with ε=+1 and mandatory shadow (§U.7, §P shadow loop)

**Modify** `domain/symmetry_reduction.py` (keep existing public API working; deprecate the fixed literals):
- remove the literals `occupation_max_abs_e`, `response_max_abs_e_per_ev`, `response_max_relative_l2`; the shadow comparison is, per (I, mode),
  `|direct − reconstructed| ≤ B_dir + B_rep` with budgets from `response_error_budget` (print bounds now; the SCF ESTIMATE component joins in TASK 17);
- shadow runs use the **representative's `ColumnPlan`** (same amplitudes/estimator);
- per-class outcome `PROVEN | REJECTED_EXPANDED`; a rejected class is expanded to explicit perturbation of its members **reusing** valid completed runs;
- reconstruction into the full raw χ0 and χ via TASK 11; raw matrices retained; rank/condition/direct-inversion gates untouched.

**Modify** `execution/campaign_runner.py` / DAG builder so that with `coverage = TRANSLATION_SHADOWED` the run specs come from the plan
(representatives + shadows) and downstream nodes consume the reconstructed matrices. `DISABLED`/`DIAGNOSTIC` paths are byte-identical to before.

**Tests.** Synthetic campaigns through the runner with fake SIESTA (existing synthetic runner tests as pattern): all-pass reduction;
a shadow that fails → class expanded and final matrix equals the explicit one; MnO-like 16→1 toy under the translation group; resume after interruption;
byte-identical behaviour for `DISABLED`.

**Done when.** gates pass; existing runner tests unchanged.

---

## TASK 15 — Automatic species splitting with semantic identity (flag, default off) (§C.3, §S, §T)

**Modify** `siesta_backend/fdf_builder.py::materialize_split_species_fdf` (keep current behaviour reachable): when a DFTU label covers several atoms and
`lr-config.auto_split_species = true`, produce `X0…XN-1` while **duplicating**: the `PAO.Basis` block, the `DFTU.Proj` record, the pseudopotential file
(copy under the new label, same sha256), and verifying the generated `.ion`/basis equality against the original label in the reference
(species identity digests must be identical across the split labels; otherwise `SPECIES_IDENTITY_NOT_ESTABLISHED` and stop).
Orphan DFTU entry of the original label must not remain. `DM.InitSpin` preserved per atom.

**Tests.** Split of CoO/NiO/MnO FDFs reproduces the physics inputs (diff of the effective FDFs only in labels); missing PSML or basis → hard failure;
orphan-entry regression; flag off → `SHARED_LABEL_NEEDS_SPLIT` is reported and the campaign refuses (never silently splits).

**Done when.** gates pass.

---

## TASK 16 — FD-EBQ phase 2: calibrated amplitudes, deterministic rounds (flag, default off) (§J, §L, §M, §N)

**Create** `domain/fdebq_rounds.py` (pure): common candidate lattice (declared in the protocol, representable in FDF); per-(column, mode) round machine using
TASK 2 budgets: round barriers with all results of the round, deterministic tie-breaks, ≥ 4 amplitudes in the calibrated protocol (spec: 3 amplitudes cannot cover a
cancelling k·a|a| plus opposite-sign analytic term), states per element and column, acceptance in **U-space** by `u_influence` propagation of element budgets
against a **user-supplied** `tau_U` (never a code default), no read of U, its stability or the condition number for any decision (§P).
Output: `CalibrationQualification` and `ColumnPlan` per (column, mode); symmetry classes share their representative's plan.

**Wire** `alpha_strategy = CALIBRATED_GRID` into the planner/campaign behind `lr-config.alpha_strategy = "CALIBRATED"`; default stays fixed grid.
Replace `adaptive_alpha_control.decide_round` **only** when that flag is set; legacy path untouched otherwise (it is already deprecated).

**Tests.** Synthetic responses with known truncation/noise: coverage of the true value by the reported total budget on ≥ 400 random cases per regime
(analytic; k·a|a|; mixed); determinism under shuffled arrival; no-circularity test (changing U-dependent inputs does not alter decisions); `tau_U` required.

**Done when.** gates pass; calibrated mode cannot produce `READY` unless the SCF ESTIMATE component exists (TASK 17), otherwise at most `REVIEW`.

---

## TASK 17 — SCF tolerance ladder for the α-independent error component (flag, default off) (§K, §Y.9)

**Create** `domain/scf_ladder.py` (pure): given the same (J, mode, ±a) computed at a declared ladder of SCF tolerances θ_1 > θ_2 > …, estimate the
α-independent SCF error of the response `ESTIMATE` (kind `BoundKind.ESTIMATE`), with ρ_max (contraction) and θ as **protocol parameters**
supplied by the user/protocol object (no defaults). No replicas at α=0 as a noise floor (§W).
**Create** `tools/fdebq_scf_ladder_campaign.py` that builds the extra SIESTA runs (DM.Tolerance ladder, same inputs) and a validation script
`tools/fdebq_validate_t0_t4.py` documenting the T0–T4 program and its pass criteria (§R, earlier review). **Codex cannot run SIESTA here: implement,
test on synthetic data, and document exactly what the user must run.** `docs/fdebq/T0_T4_RUNBOOK.md`.

**Done when.** gates pass; the budget of TASK 14 can add the ESTIMATE component through a documented parameter; `READY` is still impossible for CALIBRATED
without a recorded T0–T4 result file whose digest is referenced by the protocol.

---

## TASK 18 — ε=−1 (spin flip) and rotations behind flags + negative controls (V3) (§G, §R)

Implement the already-specified logic end to end behind `CoveragePolicy.allow_spin_flip` and `allow_rotations` (default `False`):
F5/F6/F7 with spin swap, `EXACT_IN_CONTINUUM_ONLY` with explicit egg-box quantification in the plan, reconstruction with the right permutation, shadow mandatory.
**Create** `tests/science/test_coverage_negative_controls.py` implementing V3 synthetic controls: ferrimagnet, orbital-order state (FeO-like), slab/defect supercell,
near-symmetric structure inside the band, same label with different basis, SOC/noncollinear, equal |m| but different environment. Requirement:
**zero false acceptances with the flags on and off**, and `ε=−1` must reproduce the CoO (2→1) and MnO (16→1) retrospective results of TASK 11 as *candidates*, not accepted automatically unless the flag is on.
Document in `docs/fdebq/VALIDATION_GATES.md` the exact conditions (V1–V4 results with digests) under which the user may flip each flag.

**Done when.** gates pass; flags default off in all example configs.

---

## TASK 19 — Product layer: `hubbardflow plan`, `run`, `submit` and the final report (§O end, user document §27–§28)

**Add CLI commands** (extend the existing `hubbardflow` CLI; do not break current commands):
- `hubbardflow plan system.fdf [--reference-output …] [--coverage …] [--alpha-strategy …]` → runs TASK 7→12, writes the frozen `ResolvedPerturbationPlan`,
  a human report with every decision, evidence, reason code and what the human must resolve (`AMBIGUOUS`, `NOT_ESTABLISHED`, `REVIEW`).
- `hubbardflow run system.fdf` → plan (if not frozen) → materialization → campaign lock → DAG → local/MPI execution → parsing → χ0/χ → matrix analysis → U → existing
  downstream certification → final report. It must stop and ask (non-zero exit with a clear state) when the plan status is not `READY` unless the user passes the explicit
  override that is recorded in the provenance.
- `hubbardflow submit system.fdf --partition <user-choice>` → same, using the existing SLURM supervisor/launcher; partition/account are user choices, never defaulted.
Reuse the existing orchestrator, DAG, runner, receipts, resume and portable bundle code; this task wires, it does not re-implement.
Final report includes: inventory, coverage decisions and shadows, α protocol per (column, mode), matrix gates, U with budgets and qualification, full provenance digests.

**Tests.** End-to-end with fake SIESTA on a synthetic 2-site system and a 4-site translationally-reduced system; resume after kill; `NOT_ESTABLISHED` stops the run;
override recorded; V6 campaign reproduced through `plan`+`run` with `coverage DISABLED` and explicit grid (golden digest equality with the existing path).

**Done when.** gates pass; `docs/fdebq/USER_GUIDE.md` shows the two commands above with every state the user can meet.

---

## Final checklist for the whole phase (write it to `C:\Users\Jairo\work\fdebq_pr_notes\PHASE2_SUMMARY.md`)

1. Table: task, branch, commit, gates, tests added, what is deliberately disabled.
2. List of every flag with default value and the exact condition to enable it (`VALIDATION_GATES.md`).
3. Open blockers (`docs/fdebq/BLOCKERS.md`), if any.
4. What the user must run on SIESTA to unlock: V2 prospective shadows (MnO, Cu3N), V3 negatives with real data, V4 holdout, T0–T4.
5. Confirmation that `bash tools/check_v6_integrity.sh` prints `V6 GATE OK` on the tip of the stack and that no frozen path changed.
