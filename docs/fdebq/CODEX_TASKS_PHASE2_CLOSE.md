# CODEX TASKS — Phase 2 close (TASK 20 corrections, TASK 21 product execution)

Base: `origin/fdebq/r2-task15-species-split` (tip `84b8eb6`). This file amends
`CODEX_TASKS_PHASE2.md` and `AMENDMENTS_2.md` only where an item says so explicitly. §4 lists the
new author decisions (D9–D12).

Branches (stacked; push each; the orchestrator opens no PRs, the user merges):

- `fdebq/r3-task20-fixes`: one commit per item, in the order of §3.
- `fdebq/r3-task21-product-run`: on top of the previous branch.

---

## 0. Verification locks

### 0.0 Why this file has locks

This file was written after an external review of the Phase 2 stack. Before delivery, an
independent audit of this file found six blocking errors in its first draft, and they were
corrected. Several defects fixed here (20.3, 20.4, 20.5) come from errors in the same author's
earlier specification.

**Treat every factual statement below as a claim to verify, not an instruction to trust.** Line
numbers are approximate (±15) and refer to `84b8eb6`.

### 0.1 Mandatory protocol for every item

1. **Premise check, before any code.**
   - Verify every premise `P#` with a command you actually run: `git grep`, `sed -n`,
     `python -c`, an AST script, or reading a file.
   - Record one row per premise in `docs/fdebq/PHASE2_CLOSE_LOG.md`: item, premise, TRUE/FALSE,
     the exact command, and a short excerpt of its output.
2. **False premise → stop the item.**
   - Do not implement it.
   - Add `PREMISE_FALSE: <item>/<premise>: <evidence>` to `docs/fdebq/BLOCKERS.md`.
   - Continue with the next item that does not depend on it.
   - Never adapt the instruction to fit a false premise.
3. **Pre-implementation review.**
   - Items marked **[science]** go to `auditor_cientifico` before implementation. The auditor
     reads the item, its premises and the touched code.
   - An uncovered risk to scientific results, frozen artifacts or resume of existing campaigns
     stops the item (`RISK_UNCOVERED` in BLOCKERS.md).
4. **Closed scope.**
   - Each item lists the files it may touch. A diff outside that list invalidates the item.
   - New tests may always be added.
5. **Never edit an existing test to make it pass.** The only exception is a test that an item names
   explicitly, with the reason. AGENTS.md rule 8 still applies.
6. **One item = one commit.** Each commit must be revertible on its own. Behavior changes and
   refactors never share a commit.
7. **Gates for every commit.** Run all of these:
   - the item's tests and the focused tests of the touched modules;
   - the 70 scientific regressions;
   - `ruff check`, `ruff format --check` and strict `mypy`;
   - `bash tools/check_v6_integrity.sh`;
   - from 20.10 on, `tests/unit/test_import_architecture.py`.
8. **Fail closed.** Where this file is silent, choose the conservative option and record it as
   **conservative implementer decision**.

### 0.2 Baseline (first, before any item)

1. On `84b8eb6`, run `pytest tests -q -rfE`. Record the exact failing ids and collection errors in
   the log as `BASELINE_FAILURES`.
2. An external Linux run found three groups:
   - 20 pre-existing failures, also present on `codex/hubbardflow-rename`;
   - 5 collection errors (`siestaflow_hubbard` / `lru_core` imports, untracked campaign files);
   - 2 Linux-only failures in `test_product_paths.py::test_manifest_traversal_fails_closed[C:/outside]`
     and `[C:outside]`.

   Your set may differ on Windows; record yours.
3. At the end, the failing set must be ⊆ `BASELINE_FAILURES` minus the failures that items fix.
4. Never collect the repository root. `examples/tmo_campaigns/test_order.py` launches SIESTA and
   truncates `test_ua.out` when imported. Always pass `tests`.
5. Check that no Phase-2 campaign exists in the repository or in `C:\Users\Jairo\work`:
   - Search for `campaign.lock` and `resolved_perturbation_plan.json` outside `tests/` and
     temporary directories.
   - Record the result. D11 (§4) assumes none exists.
   - If one exists, stop before 20.5 and report it.

### 0.3 Explicit exception to AGENTS.md rule 9

Items 20.2 and 20.5 change what the FIXED_PROTOCOL_GRID **init** accepts and the bytes of the
frozen plan, and the author authorizes both changes:
- 20.2 makes init reject some inputs (fail closed);
- 20.5 makes the coverage qualification embedded in the plan record different exactness classes.

What may not change, for any accepted input: run specs, materialized FDF bytes, analysis or results.
Item 20.9 and the V6 gate prove this.

---

## 1. TASK 20 — Corrections before merging Phase 2

### 20.1 Legacy resume must not go through the strict FDF parser

**Premises**

- **P1.** `execution/campaign_runner.py` (~L385-386) calls `campaign_inventory(...)` and
  `validate_lr_config(..., inventory=...)` for every manifest.
- **P2.** At `b2b65ca`, resume did not call `parse_effective_fdf`.
- **P3.** There is an FDF that the base `validate_reference_fdf` accepts and `parse_effective_fdf`
  rejects (for example `%block LatticeParameters`).
- **P4.** Every manifest created by the current `initialize_campaign` carries a frozen plan
  (`wsl_campaign_init.py` ~L272-304). So "no frozen plan" ⇔ "pre-Phase-2 manifest".

**Change**

- Pre-Phase-2 manifests (no frozen plan) resume through exactly the base validation path.
- Plan-bearing manifests keep the strict path.
- New `init` keeps strict parsing.

**Files:** `execution/campaign_runner.py`; new tests.

**Acceptance**

- A pre-Phase-2 manifest whose FDF `fdf_model` rejects resumes, with run specs equal to base. Build
  the fixture with base code or copy an archived manifest; never edit a frozen file.
- The same FDF under a plan-bearing manifest fails closed.

### 20.2 FDF labels follow SIESTA's label rules **[science]**

**Premises**

- **P1.** The SIESTA 5.4.2 manual (FDF syntax section) says: "fdf labels are case insensitive, and
  characters - _ . in a data label are ignored." Cite the page if the PDF is on your machine;
  otherwise write "verified by the spec author: manual p.19".
- **P2.** `fdf_model._directives` (~L147) matches `re.escape(key)` with `IGNORECASE`, which is
  punctuation-sensitive.
- **P3.** Block names are only casefolded (~L172).
- **P4.** `coverage_reference.py` (~L35-46) matches `DFTU.PotentialShift` and `%block DFTU.proj`
  literally.
- **P5.** `Spin_Orbit T`, `spin.orbit true` and `Non-Collinear-Spin T` currently give
  `spin_orbit=False, noncollinear=False`. Show this with a probe.

**Change**

1. **`canonical_fdf_label`.**
   - Create `siesta_backend/fdf_labels.py` with a public `canonical_fdf_label(text) -> str`. It
     casefolds and removes `-`, `_` and `.`.
   - Use it for every directive and block-name lookup in `fdf_model.py`, `coverage_reference.py`
     and `scf_ladder_inputs.py`.
2. **Canonical duplicates.**
   - Two directives with the same canonical label → `UNSUPPORTED_SYNTAX` (duplicate). Do not guess
     which one SIESTA takes. The same applies to blocks.
   - This error wins over item 3.
3. **Managed labels.**
   - The managed set is the canonical labels HubbardFlow writes, removes or reads. List them in the
     log from `fdf_builder.py`, the profiles, `scf_ladder_inputs.py`, the ladder tool and the
     spin/DFTU readers.
   - Every spelling is recognised.
   - **Non-canonical spelling, defined exactly:** the input's label, after `casefold()`, differs
     from HubbardFlow's own spelling after `casefold()`. Only punctuation differences count;
     `DFTU.proj` and `DFTU.Proj` are the same spelling.
   - A non-canonical spelling is rejected with the new code `NONCANONICAL_MANAGED_LABEL`. The
     message gives the expected spelling.
4. Do not change the legacy validators. In the log, list which of them are punctuation-sensitive,
   as input for Phase 3.

**Files:** `siesta_backend/fdf_labels.py` (new), `fdf_model.py`, `coverage_reference.py`,
`scf_ladder_inputs.py`; new tests.

**Acceptance**

- The P5 spellings are detected and rejected as SOC/noncollinear.
- `Chemical_Species_Label` is read.
- `DM.Tolerance` plus `dm_tolerance` → duplicate.
- `DFTU_PotentialShift T` → `NONCANONICAL_MANAGED_LABEL`.
- `DFTU.Proj` is accepted.
- All 197 repo FDFs: record how many parse before and after. All 40 that the base validator accepts
  still parse. Any newly rejected FDF → stop (`RISK_UNCOVERED`).

### 20.3 SCF ladder: right labels, H tolerance, one parent DM per level **[science]** (author error in TASK 17; see D9)

**Premises**

- **P1.** TASK 17 says "DM.Tolerance ladder, same inputs". Review §E.2 says two things: levels
  harden DM.Tolerance and the H tolerance by a declared factor, and each level has its own parent
  reference of the same level.
- **P2.** `tools/fdebq_scf_ladder_campaign.py` (~L110) removes only lines starting with
  `DM.Tolerance` and appends `DM.Tolerance <v>`.
- **P3.** The manual says `SCF.DM.Tolerance` takes precedence ("DM.Tolerance is the actual default
  for this flag").
- **P4.** Repo FDFs mostly use `SCF.DM.Tolerance` and `SCF.H.Tolerance`. Count both spellings.
- **P5.** The tool requires one shared parent DM (~L101).
- **P6.** `siesta542_bare_profile.py` sets `MaxSCFIterations 1`.
- **P7.** Outputs echo `redata: DM tolerance for SCF = <v>`,
  `redata: Hamiltonian tolerance for SCF = <v> eV` and the `redata: Require ... convergence` lines,
  printed with 6 decimals.
- **P8.** `bind_ladder_input` rejects α=0, so it cannot materialize the level references.
- **P9.** SIESTA overwrites the DM file in its run directory, so a parent DM hash computed after
  the run is not the parent's.

**Change**

1. **ScfLadderProtocol v2.**
   - Each level declares `dm_tolerance` and `h_tolerance_ev` explicitly, with no defaults.
   - Both must be ≥ 1e-6 and exact multiples of 1e-6. Otherwise the protocol is rejected, because
     the 6-decimal echo could not prove them.
   - v1 records load as `NOT_ESTABLISHED` (`SCF_LADDER_PROTOCOL_V1`).
2. **Materialization of ±a runs.**
   - The input goes through `parse_effective_fdf`, so 20.2 applies: a non-canonical spelling such as
     `scf_dm_tolerance` is rejected, and the message says how to rewrite it.
   - Remove every directive with canonical label `dmtolerance`, `scfdmtolerance` or
     `scfhtolerance`. Write `SCF.DM.Tolerance <v>` and `SCF.H.Tolerance <v> eV`.
   - Record the effective values of `SCF.DM.Converge`, `SCF.H.Converge`, `SCF.EDM.*`,
     `SCF.FreeE.*`, Harris and `MaxSCFIterations` in the receipt.
3. **Level references.**
   - Add a separate public function `materialize_ladder_reference(reference_fdf, level) -> ...` for
     the α=0 reference of each level. It is not `bind_ladder_input`.
   - It writes the same tolerance directives and no DFTU shift.
   - The user runs these references.
4. **One parent DM per level, for both modes.**
   - Every ±a run of level l declares the DM produced by the level-l reference.
   - The parent DM sha256 is computed **from the reference's output DM, at materialization time**,
     and stored in the receipt. It is never recomputed from the run directory afterwards.
   - Two levels with identical parent bytes → `NOT_ESTABLISHED` (`PARENT_LEVEL_NOT_DISTINCT`).
   - BARE keeps `MaxSCFIterations 1`; its level difference comes from the parent DM only (D9).
5. **Validator for user-produced outputs.** Each check below failing gives `NOT_ESTABLISHED` with
   the reason in parentheses.
   - For every reference and ±a output, the `redata:` DM and H tolerances must equal the level's
     values at 6 decimals (`SCF_LEVEL_NOT_APPLIED`).
   - `Require DM convergence` and `Require H convergence` must both be `T` (`SCF_CRITERIA_NOT_ACTIVE`).
   - Each level reference must have converged, using the existing SCF convergence detection
     (`LEVEL_REFERENCE_NOT_CONVERGED`).
6. Update `docs/fdebq/T0_T4_RUNBOOK.md`: exact commands, references per level, the BARE note, and
   the 1e-6 representability rule.

**Files:** `domain/scf_ladder_models.py`, `domain/scf_ladder.py` (only if models require it),
`siesta_backend/scf_ladder_inputs.py`, `tools/fdebq_scf_ladder_campaign.py`,
`tools/fdebq_validate_t0_t4.py`, `docs/fdebq/T0_T4_RUNBOOK.md`; new tests.

**Acceptance**

- `SCF.DM.Tolerance 1.0e-5` in the input → exactly one DM directive and one H directive, at the
  level's values.
- The `scf_dm_tolerance` spelling → `NONCANONICAL_MANAGED_LABEL`.
- A tolerance of 5e-7 → protocol rejected.
- A mismatched echo → `SCF_LEVEL_NOT_APPLIED`.
- `SCF.H.Converge F` in the echo → `SCF_CRITERIA_NOT_ACTIVE`.
- BARE: three distinct parents are accepted; a shared parent → `PARENT_LEVEL_NOT_DISTINCT`.
- The D5 formulas are unchanged and the existing ladder math tests pass unchanged.

### 20.4 Species-split identity: width-preserving label normalization (author error in D6; see D10)

**Premises**

- **P1.** `siesta_backend/semantic_ion_identity.py` already provides `relabel_ion_bytes` /
  `canonical_ion_bytes`. They replace only the `<basis_specs>` header label and the value before
  `# Label`, preserve fixed field widths, and fail closed on unknown layouts.
- **P2.** In the repository there is a real SIESTA-generated alias pair:
  `FEO_SCF_DIAGNOSTIC_EXPORT_20261001/feo_lru_fullU_PopTol1e-5_MixerWeight0.05/FeLR0.ion` and
  `FeLR1.ion`. Their raw diff is exactly lines 5 and 79, the two label fields. This directory is a
  frozen V6 root, so read it and never write to it.
- **P3.** The current verdict (`split_generated_identity.py`,
  `tools/hubbardflow_verify_split_identity.py`) requires raw sha256 equality. That can never hold
  for different labels.
- **P4.** The chemical symbol also appears on the `# Symbol` line and in the
  `<pseudopotential_header>`. Neither is a label field, and neither is changed by the relabel.

**Change**

- The verdict is `MATCH` iff both hold:
  - `canonical_ion_bytes(original, label_o) == canonical_ion_bytes(alias, label_a)`;
  - the raw line diff is confined to the lines that the relabel touches.
- Otherwise `MISMATCH`, listing the differing lines.
- Raw sha256 values stay in the receipt as diagnostics. Bump the receipt version.
- TASK 15 remains `STAGED_PENDING_GENERATED_IDENTITY` until a user receipt exists.

**Files:** `siesta_backend/split_generated_identity.py`, `tools/hubbardflow_verify_split_identity.py`,
`docs/fdebq/SPECIES_SPLIT_RUNBOOK.md`; new tests.

**Acceptance**

- The real pair FeLR0/FeLR1 → `MATCH`. Read only; copy into `tmp_path` if the tool needs a
  directory.
- The pair with one numeric line edited (in the copy) → `MISMATCH` at that line.
- Editing the `# Symbol` line → `MISMATCH`.

### 20.5 Translation exactness, operation preference, non-polarized flip, planner determinism **[science]** (author error in TASK 9; see D11)

**Premises**

- **P1.** `exactness_class` (`domain/symmetry_operation_models.py`) returns `EXACT_TRANSLATION` for
  any identity rotation.
- **P2.** F8 is excluded for translations (`symmetry_operations.py` ~L140, ~L391-394; `coverage.py`
  ~L156).
- **P3.** Review §D.3 treats non-commensurate translations as `EXACT_IN_CONTINUUM_ONLY`.
- **P4.** Translations come from float `positions % 1` (`symmetry_operations.py` ~L53-66).
  Commensurability uses `Fraction(str(float))` (~L386), and atoms are matched within the `tau_neq`
  band.
- **P5.** `coverage.py` (~L192-199) takes `matching[0]` as the member operation.
- **P6.** With `allow_spin_flip=True`, a verified non-polarized reference has its only channel
  relabelled, and F7 becomes AMBIGUOUS. Probe with a Cu3N-like toy.
- **P7.** `domain/symmetry_operations.py` (~L47-75) imports `spglib` dynamically when it is
  installed. spglib is not declared in `pyproject.toml`, so candidate operations and reasons, and
  therefore the plan digest, depend on the environment.
- **P8.** Even DISABLED plans embed the coverage qualification, operations with `exactness_class`
  included. On NiO that is 16 operations. So 20.5 changes the plan digest of every Phase-2 campaign
  (D11).

**Change**

1. **Exact translation.** An operation is `EXACT_TRANSLATION` iff all three hold:
   - (a) the rotation is the identity and ε=+1;
   - (b) the atom mapping is exact in rationals: every translated atom coincides exactly, modulo 1,
     with its image, using `Fraction` built from the FDF decimal text;
   - (c) for each lattice vector i, the reduced fractional translation times the InitMesh size N_i
     is an integer.

   Exact rationals are available only when coordinates are fractional/scaled-by-lattice, or when
   Cartesian coordinates and the lattice share one unit after `LatticeConstant` scaling. With mixed
   units, or without InitMesh evidence, the operation is `EXACT_IN_CONTINUUM_ONLY`.
   - Carry the decimal text from the parser to the symmetry code.
   - Continuum-only operations follow the feature-validation path that rotations use. Production
     class: `REJECTED_EXPANDED`.
2. **Preference order for each member's operation**, highest priority first:
   1. exact translation;
   2. other ε=+1 identity-rotation translation;
   3. ε=+1 rotation;
   4. ε=−1.

   Ties keep the existing canonical order.
3. **Non-polarized reference.** If the reference is verified non-polarized, ε=−1 operations are not
   generated (`NOT_APPLICABLE`).
4. **Planner determinism.**
   - Remove the spglib path from planning. Candidate operations come only from the internal
     enumeration.
   - If the log shows that spglib finds operations the internal enumeration cannot, record them and
     stop the item (`RISK_UNCOVERED`). Do not add spglib as a dependency.
5. Bump `planner_version` to `campaign-planner-v2` (D11).

**Files:** `domain/symmetry_operation_models.py`, `domain/symmetry_operations.py`,
`domain/coverage.py`, the planner version constant, and the parser modules needed to carry decimal
text (list them); new tests.

**Acceptance**

- ½ translation with even N → exact.
- ½ translation with odd N → continuum-only.
- 0.3333 → continuum-only.
- Missing InitMesh → continuum-only.
- Mixed units → continuum-only.
- An 8-site translation orbit with `allow_rotations=True` uses translations for every member.
- The Cu3N-like toy gives the same coverage with the spin flip on and off.
- Plan digest is identical with and without spglib importable (simulate both).
- For the archived examples, each change in the coverage golden reports is listed in the log with
  its cause.
- 20.9 run specs are unchanged.

### 20.6 Frozen V6 path protection

**Premises**

- **P1.** `execution/product_paths.py` sets `WORKSPACE = Path(__file__).resolve().parents[3]`
  (~L15). In a non-editable install it does not point at the repository.
- **P2.** Protection uses `is_relative_to`, which is case-sensitive on POSIX. `Validation_Observables_V6`
  and `benchmarks/LR_U` pass.
- **P3.** `tools/hubbardflow_plan_diagnose.py` (~L209-224) writes its outputs without protection.
- **P4.** The drive check uses `Path(relative).drive`, which is platform-dependent and causes the 2
  Linux failures.
- **P5.** Four existing tests monkeypatch `product_paths.WORKSPACE`. One of them,
  `test_missing_manifest_fails_closed`, expects failure when the manifest is absent.

**Change**

1. **Workspace.**
   - Keep the module attribute, now typed `WORKSPACE: Path | None = None`. When set (tests only),
     it is the workspace.
   - When it is `None`, walk up the resolved destination's ancestors. The first one containing
     `src/hubbardflow/__init__.py` **or** `docs/history/SCIENTIFIC_BASELINE_V6.sha256` is the
     workspace.
   - Workspace found but manifest missing → fail closed, which preserves the existing test.
   - No workspace on the path → allowed. Record `v6_protection: NO_WORKSPACE_ON_PATH` in the
     receipt.
   - Do not use `__file__`.
2. **Comparison.**
   - Compare component-wise with `casefold()` on all platforms.
   - Also compare `(st_dev, st_ino)` of every existing ancestor of the destination with the frozen
     roots.
3. **Drive letters.** Reject manifest rows where `PureWindowsPath(row).anchor or ":" in row`, on
   all platforms.
4. **Diagnose tool.** `hubbardflow_plan_diagnose.py` protects each output **file**: its parent
   directory and the path itself. It opens the outputs with `"x"`.
5. **Product report.** Write the report atomically (temp file, then replace) after the protection
   check.

**Files:** `execution/product_paths.py`, `execution/product_plan.py` (wrapper only),
`execution/product_models.py` (receipt field only), `product_cli.py` (report write only),
`tools/hubbardflow_plan_diagnose.py`; new tests.

**Acceptance**

- The 4 existing WORKSPACE tests pass unchanged, including both drive-letter parametrizations, now
  on Linux too.
- Allowed test edit: `test_every_manifest_path_is_rejected_read_only` (test_product_paths.py ~L37-46).
  - It calls `_frozen_files()` with no workspace and monkeypatches it with a zero-argument lambda.
  - Make `_frozen_files(workspace)` take the workspace explicitly, and update only this test to pass
    the workspace (`tmp_path` or the repo root).
  - Record the edit in the log.
- These case variants are rejected:
  - `VALIDATION_OBSERVABLES_V6/x`
  - `Validation_Observables_V6`
  - `benchmarks/LR_U`
  - `results/Stage-UB-V6-Observables`
  - `FINAL_SIESTA_VALIDATION_REPORT_v6.md`
- With the package imported from outside the repository: a destination outside any checkout works,
  and one inside is protected.
- The diagnose tool refuses a V6 file.

### 20.7 Legacy `run` rejects product-only options

**Premise**

- **P1.** In `cli.py` (~L251), the product options are attached to every `run` target. A legacy
  target ignores them silently. Show this with a probe that mocks the worker.

**Change.** A non-`.fdf` target given any product option → exit 2, naming the options.

**Files:** `cli.py`; new test.

### 20.8 Calibrated rounds hardening **[science]**

**Premises**

- **P1.** `select_column` (~L82-91) → `scf_element_report` (`scf_budget_adapter.py` ~L103-106)
  requires every L0 ladder point. A failure below the large ladder endpoint, with ≥4 usable
  amplitudes, raises `FdebqRoundsError`. Reproduce it.
- **P2.** `_next` (~L161-169) can request amplitudes outside the envelope coverage.
- **P3.** θ and ρ_max are not bound into `CalibrationProtocol.digest`. Nothing requires one ladder
  protocol, or L0 == `scf_level_id`.
- **P4.** `t0_t4_result_sha256` is checked only for `None` (~L271).
- **P5.** `ScfCandidateEstimate(qualified=True)` can enter `ColumnEvidence` (~L152-200) without a
  validated envelope.
- **P6.** A single-site campaign raises in `fdebq_matrix.full_budget_box` (~L34) instead of
  returning a status.

**Change**

1. **Evidence-shaped conditions never raise.**
   - A candidate that uses an amplitude the remaining ladder points cannot cover is inadmissible.
   - If no candidate remains, the column is UNRESOLVED under the existing rules.
2. **Envelope-bounded requests.**
   - `_next` requests only amplitudes inside the envelope coverage of that column and mode.
   - If there are none, it requests nothing for that column and records `SCF_ENVELOPE_NOT_COVERED`.
3. **Ladder protocol binding.**
   - Bind the ladder protocol digest (v2, from 20.3) into `CalibrationProtocol.digest`.
   - Require one ladder protocol for all envelopes, and L0 == `scf_level_id`.
   - Otherwise `NOT_ESTABLISHED` (`SCF_PROTOCOL_MISMATCH`).
4. **T0–T4 result.**
   - The decision receives the `ValidationResult` object itself.
   - It requires: digest equality, status `PASSED`, and θ/ρ_max equal to the ladder's.
   - Otherwise `VALIDATION_NOT_ESTABLISHED`.
5. **Qualified estimates.**
   - `qualified=True` is accepted only if it was recomputed from a validated envelope in the same
     evidence.
   - Enforce this in `ColumnEvidence.__post_init__`.
   - Allowed test edit: the fixture in `tests/unit/test_fdebq_rounds.py` (~L87) that builds such an
     estimate directly. Rebuild it from an envelope and record it in the log.
6. **Single site.** One site → `NOT_ESTABLISHED` (`SINGLE_SUBSPACE_NOT_SUPPORTED`).
   `u_certification.py` is untouched.

**Files:** `domain/fdebq_rounds.py`, `domain/fdebq_models.py`, `domain/scf_budget_adapter.py`,
`domain/fdebq_matrix.py`, `domain/scf_validation.py` (exposure only); new tests. Allowed test edits:
the one named in item 5, and tests that build `t0_t4_result_sha256` without a result (list each in
the log).

### 20.9 Golden test against the real archived grids

**Premise**

- **P1.** `test_real_init_fixed_disabled_golden_and_resume` (~L300) uses a synthetic grid,
  auto-filled sites and a self-comparison.

**Change**

1. For CoO, NiO, MnO v3r2 and Cu3N, find the archived campaign that defines the reference grid and
   sites, and list the paths in the log.
2. Write `tools/dev/generate_phase2_golden.py`. Run it in a `git worktree` of `b2b65ca` to produce
   `tests/fixtures/phase2_golden/<system>.json`, containing:
   - `(site label, atom index, mode, alpha)`;
   - sha256 of each materialized run FDF.
3. Commit the fixture and the script.
4. Add a new test that initializes the same inputs with the current code (`coverage=DISABLED`,
   explicit grid and sites) and compares against the fixture.
5. A missing archived input → record it and test what exists. Never fabricate.

**Files:** new script, new fixtures, new test file.

### 20.10 Import structure: break the cycle, add the architecture test

**Premises**

- **P1.** `fdf_model.py` (~L17) and `scf_ladder_inputs.py` (~L20) import
  `execution.campaign_v2.resolve_fdf_includes` / `CampaignV2Error`.
- **P2.** There is a cycle: `fdf_model` → `campaign_v2` → (function-level) `campaign_plan` →
  `fdf_model`.
- **P3.** `reporting/product_report.py` (~L7) imports `execution.product_models`.
- **P4.** There are cross-module private imports. Produce the full list with an AST script.
- **P5.** List every caller that catches `CampaignV2Error` around `resolve_fdf_includes`.

**Change**

1. **Move the include resolver.**
   - Move `resolve_fdf_includes` into `siesta_backend/fdf_includes.py`. It raises a new
     `FdfIncludeError(ValueError)`.
   - `campaign_v2.resolve_fdf_includes` remains a thin wrapper that converts `FdfIncludeError` to
     `CampaignV2Error`, so existing callers see the same exception type (P5).
   - `fdf_model` and `scf_ladder_inputs` call the siesta_backend version and convert to their own
     errors.
2. **`tests/unit/test_import_architecture.py`.**
   - Use an `ast` graph that includes function-level imports and excludes `TYPE_CHECKING`.
   - Rules:
     - `domain` imports only `domain`, the stdlib and numpy. The dynamic `importlib` import of
       spglib is gone after 20.5.
     - `siesta_backend` never imports `execution`, `reporting` or `cli`.
     - `reporting` never imports `execution`.
     - No cycles.
     - No cross-module private names.
   - Existing violations go in an explicit allowlist, one line each, marked `# phase 3`.
   - The test fails on a new violation and on a stale allowlist entry.
3. **AGENTS.md §2.** Add:
   - "10. `tests/unit/test_import_architecture.py` must pass; its allowlists may only shrink."
   - "11. Never import a private name (leading underscore) from another module, never call a
     private method of another class; existing cases are allowlisted for Phase 3."

**Files:** `siesta_backend/fdf_includes.py` (new), `siesta_backend/fdf_model.py`,
`siesta_backend/scf_ladder_inputs.py`, `execution/campaign_v2.py` (wrapper only), `AGENTS.md`; new
test.

### 20.11 Planner version handling for frozen campaigns (see D11)

**Premises**

- **P1.** `verify_frozen_campaign_plan` (`campaign_plan.py` ~L251-280) recomputes the plan with
  current code and compares digests, so any planner change invalidates frozen campaigns.
- **P2.** `planner_version` is part of the digest.

**Change**

1. **Version check first.** On load, read the raw `planner_version` field from the stored JSON
   **before** calling `ResolvedPerturbationPlan.from_mapping`. A v1 mapping may no longer
   deserialize after 20.5. If the version differs from the current one, fail with the dedicated
   reason `PLANNER_VERSION_CHANGED`. The message names both
   versions and says: "re-initialize the campaign; frozen plans are not migrated".
   - This replaces the generic "campaign plan invalidated" for that case only.
2. **Golden digests.**
   - Add a golden test that pins the plan digests of the four DISABLED plans of 20.9 and one
     synthetic `TRANSLATION_SHADOWED` plan, under `campaign-planner-v2`.
   - Docstring: "changing planner output requires bumping `planner_version` and updating this
     golden in the same commit".
3. Leave the existing `except` clauses unchanged: malformed evidence can raise `KeyError` or
   `TypeError`.

**Files:** `execution/campaign_plan.py`; new test.

---

## 2. TASK 21 — `hubbardflow run system.fdf` executes legacy-equivalent plans (see D12)

### Problem

The product boundary always blocks. That includes a fixed explicit grid with every subspace
perturbed directly, which is what the legacy flow already runs and V6 validates. The I.5 state gate
is needed only for reductions and calibrated grids; pilot reuse is only a saving.

### Premises

- **P1.** `product_execution_boundary` (~L372) adds `SCIENTIFIC_STATE_NOT_ESTABLISHED` and
  `PILOT_REUSE_NOT_ESTABLISHED` unconditionally.
- **P2.** The planner (~L110-126) sets `NOT_ESTABLISHED` when the reference output or parent DM is
  missing, even for bypass plans. Plan status therefore cannot be the execution admission.
- **P3.** Legacy campaigns run their own reference node and parent DM. Verify this in the DAG.
- **P4.** `execution.campaign_runner.run_campaign_worker(manifest, "run")` is the public function
  that legacy `run campaign.v2.json` calls on Linux (`cli.py` ~L171-175).
  `execution.wsl_campaign_init.initialize_campaign` is public.
- **P5.** `validate_lr_config` accepts `adaptive_alpha_policy` together with `FIXED_PROTOCOL_GRID`.
  The runner would then add adaptive runs that are not in the plan.
- **P6.** The product directory today freezes only the plan, lock and resolved plan, not the
  lr-config bytes. `--reference-output` / `--reference-dm` are merged in memory.
- **P7.** The legacy runner never calls `sbatch`; it runs inside an allocation.
- **P8.** Whether an existing test harness runs the legacy runner end-to-end with a fake SIESTA.
  Record the test names, or "none".

### Design

1. **Admission.** Add `execution/product_admission.py` with a pure function
   `execution_admission(snapshot, frozen_lr_config) -> ExecutionAdmission`.
   - Statuses: `ADMISSIBLE_LEGACY_EQUIVALENT` or `BLOCKED` with reasons.
   - Admissible iff all hold:
     1. inventory OK with ≥1 site;
     2. `alpha_strategy` is `FIXED_PROTOCOL_GRID` or `USER_EXPLICIT_GRID`, with the grid explicit
        in the frozen lr-config;
     3. `adaptive_alpha_policy` is absent or null (P5);
     4. every (site, mode) column is computed directly: no reconstruction map and no reduced class;
     5. spin flip, rotations and `auto_split_species` are all off;
     6. coverage is `DISABLED` or `DIAGNOSTIC`;
     7. the frozen snapshot verifies (existing checks).
   - For admissible plans, I.5 and pilot reuse appear as `NOT_REQUIRED`, and reference/parent-DM
     reasons as "coverage diagnostic only".
   - Every other plan keeps today's behavior.
   - `--override-plan-state` never makes `BLOCKED` admissible.
2. **Freeze the lr-config.**
   - `plan` and `run` write the **merged, path-resolved** lr-config to the product directory: the
     output of `product_plan._config()`, with CLI reference options merged and relative paths made
     absolute. Do not write the user's raw bytes, because `initialize_campaign` resolves relative
     paths against the config's own directory.
   - Record the sha256 in the snapshot (P6). `initialize_campaign` receives this frozen copy.
   - Also record in the snapshot the sha256 of every input file the plan hashed: pseudopotentials,
     static artifacts, version/registry files and `%include` files.
3. **CLI.** `run system.fdf --lr-config C --profile P --name N [--campaign-root R]`.
   - Without `--profile`, the behavior is exactly today's: receipt only, exit 3.
   - With `--profile`, an admissible plan executes **only from a Linux shell**: WSL shell, cluster
     login, or inside an allocation for Slurm profiles, as legacy does.
   - On a Windows host Python → error pointing to the WSL shell. The PowerShell pointer route is
     out of scope.
   - `submit` is unchanged (receipt only, P7).
4. **Execution order.**
   - (a) Protect the campaign root as in 20.6.
   - (b) Call `initialize_campaign` with the frozen lr-config copy and the FDF.
   - (c) Verify, before running anything (TOCTOU), every manifest `input_files` sha256 against the
     bytes the snapshot hashed.
     - Use the byte-preserving provenance copies `provenance/source_reference.fdf` and
       `provenance/source_lr_config.json`. Do not use the include-resolved `reference.fdf` or the
       rewritten `lr_config.json`; verify these names with a premise check.
     - Compare every pseudopotential, static artifact, version/registry and include file the same
       way.
   - (d) Verify that the run-spec set in the campaign's frozen plan equals the product plan's
     executable run-spec set. Compare plan JSON data only; never `_build_dag`.
   - (e) Write `execution_link.json` with the campaign path, manifest sha256 and product plan
     digest.
   - (f) Call `run_campaign_worker(manifest, "run")`.
   - Any mismatch → stop before (f), leaving the campaign un-run and recorded.
   - An existing link → refuse, and point the user to `hubbardflow resume <campaign.v2.json>`.
5. **Docs.** Add the admission table to `docs/fdebq/USER_GUIDE.md`, plus the user's real check: run
   CoO via `run system.fdf` and via legacy `init`+`run`, then compare the final analysis JSON.

**Files:** `execution/product_admission.py` (new), `execution/product_plan.py`,
`execution/product_models.py`, `product_cli.py`, `cli.py` (option wiring only),
`reporting/product_report.py`, `docs/fdebq/USER_GUIDE.md`; new tests.

Do not change `campaign_runner.py`, `campaign_v2.py`, `wsl_campaign_init.py`, `lr_dag.py` or any
`domain/` module. No new private cross-module call (AGENTS rule 11).

### Acceptance

- **A.** A truth-table test: each condition failing alone → `BLOCKED` with its reason; all
  conditions passing → admissible.
- **B.** Equivalence with legacy:
  - If P8 found a fake-SIESTA harness: the product route and legacy `init`+`run` give an analysis
    JSON that is byte-identical after removing only the fields that differ between two legacy runs
    of the same inputs (list them).
  - Otherwise: compare the run-spec sets, the materialized FDF bytes per run and the captured
    `run_campaign_worker` call. Record that numerical equivalence is the user's CoO check.
- **C.** TOCTOU tests: modifying the FDF, or one pseudopotential, between admission and (c) → stops
  before running.
- **D.** Legacy commands, `submit`, the V6 gate and every Phase-2 blocking behavior are unchanged.

---

## 3. Order, closing, out of scope

**Order**

1. 0.2 baseline.
2. 20.1, 20.6, 20.7.
3. 20.2.
4. 20.3, 20.4, 20.5, 20.8.
5. 20.9, 20.11.
6. 20.10.
7. TASK 21.

**Closing**

- Write `docs/fdebq/PHASE2_CLOSE_SUMMARY.md` with one row per item:
  - commit;
  - TRUE/FALSE premises;
  - auditor verdict;
  - tests added;
  - test edits made under an explicit exception;
  - decisions taken as **conservative implementer decision**.
- Include the final failing set compared with `BASELINE_FAILURES`.
- No PRs, no SIESTA runs.

**Out of scope (Phase 3; do not start)**

- `CampaignRunner` decomposition, and `CampaignShadow`'s private access.
- Removing allowlisted private imports.
- Dead or test-only code.
- Pre-existing failing tests and the `siestaflow_hubbard` imports.
- `examples/` collection safety.
- Punctuation-insensitive legacy validators.
- Pilot reuse.
- The I.5 runtime state producer (TASK 22, specified separately).

---

## 4. New author decisions (copy into `docs/fdebq/AMENDMENTS_2.md` under "Phase 2 close")

- **D9 (SCF ladder).** Review §E.2 is authoritative over TASK 17.
  - Levels harden both the DM and the H tolerance, and each level has its own α=0 reference and
    parent DM.
  - For BARE, the level difference comes only from the parent DM (`MaxSCFIterations 1`). The D5
    formulas apply with three parent levels.
  - This extends §E.2, which describes BARE with two levels as an indicator. The third level gives
    the contraction check at the cost of two cheap BARE runs per amplitude.
- **D10 (species identity).** The verdict is width-preserving label normalization plus a diff
  confined to the label lines, not raw sha256 equality. The real pair FeLR0/FeLR1 is the positive
  control.
- **D11 (frozen Phase-2 plans).**
  - No Phase-2 campaign has run with SIESTA (checked in 0.2.5).
  - Plans frozen under `campaign-planner-v1` are not migrated: resume fails with
    `PLANNER_VERSION_CHANGED`, and the user re-initializes.
  - Plan content must not depend on optional packages.
- **D12 (product execution).**
  - A plan with no reduction, a fixed explicit grid and no adaptive policy is executable through
    the legacy runner. Its scientific content is the legacy V6-validated path.
  - I.5 and pilot reuse are requirements only for reduced or calibrated plans.
