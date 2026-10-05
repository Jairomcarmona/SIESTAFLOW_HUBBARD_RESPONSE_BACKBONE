# CODEX TASK 23: Translation-shadowed reductions in production, validated on real MnO, plus a Cu3N diagnostic

**Base:** `codex/hubbardflow-rename` after the TASK 22 merge (branch `fdebq/r6-task22-i5`, tip `a1b3c31`).
**Branch:** `fdebq/r7-task23-ts`. Push it; do not open a PR.

## Goal and limits

Make `--coverage TRANSLATION_SHADOWED` (TS) usable end to end:

```
hubbardflow reference system.fdf --lr-config C --profile P --name N_ref --output-dir D_ref
hubbardflow run       system.fdf --lr-config C --profile P --name N --output-dir D \
    --coverage TRANSLATION_SHADOWED \
    --reference-output D_ref/planning_reference/reference.out \
    --reference-dm     D_ref/planning_reference/<SystemLabel>.DM
```

Then validate it on real MnO (16 Mn sites → 2 translation classes, 49 SIESTA runs instead of 193),
and run a diagnostic on Cu3N.

What does **not** change:
- the fixed-grid direct path (`DISABLED`/`DIAGNOSTIC`), its U values and its admission;
- the U analysis code (`lr_analysis_v2`, `u_certification`);
- spin flip, rotations, calibrated grids and the SCF ladder stay disabled;
- I.5 stays diagnostic-only for direct campaigns.

Everything in this file was checked by the author against the code at `a1b3c31` and against the
archived MnO data, including a prototype of 23.1 run against the full suite. An independent audit
was done before delivery; its corrections are included. The audit also ran the whole TS path end to
end on MnO with a fake SIESTA serving the archived outputs: 51 nodes, both shadows `PROVEN`, U spread
inside a class 7e-15 eV. That run had the state gate forced to True, because 23.2 does not exist
yet.

### Author decisions (record them as D14 in `docs/fdebq/AMENDMENTS_2.md`)

**D14a. Species identity without an explicit `PAO.Basis`.** In one FDF, every species without a
`PAO.Basis` record gets its basis from the global `PAO.*` directives, which are shared by
construction. Such a species is `ESTABLISHED` when its pseudopotential bytes are known and the FDF
has no block outside an audited species-neutral list and no user-supplied basis (`User.Basis`).
Any other block makes every species `NOT_ESTABLISHED` (fail closed): HubbardFlow cannot tell
whether an unknown block is species-scoped. The explicit lr-config pseudopotential map is the
identity source when present; directory search by `<label>.psml` remains the fallback.

**D14b. The shadow state gate is I.5.** `CampaignShadow._complete_state_gate` is True iff, for every
computed column (representatives, shadows, expanded columns) and both modes, the I.5 verdict is
`PASS` and no check in any point has outcome `FAIL`, `NOT_AVAILABLE` or `NOT_ESTABLISHED`.
`NOT_DEFINED` and `NOT_APPLICABLE` are allowed. G3 smoothness stays `NOT_ESTABLISHED` (D13a) and
does not block: smoothness concerns the estimator, which is the same for direct and reduced
campaigns. The shadow comparison is the direct empirical test of translation equivalence.
Note: unlike the diagnostic verdict, G4 `NOT_AVAILABLE` (missing `.EIG`) blocks here.

**D14c. Superseded by D16 and the current D16.1 instruction.** Parent-state
comparison is physical; DM and file digests are recorded as traceability only.
Occupation elements use their individual summed print half-widths and the
explicit SCF-derived tolerance described in 23.3 below. A measured physical
state difference invalidates the affected parent's reduction and schedules
only its affected classes directly. Incomplete global atom/projector identity
requires direct calculation of all reduced classes using that parent. Shadow
rejection still follows the declared STOP/EXPAND policy; reference digest
changes never reject or expand a reduction.

**D14d. The planning reference comes from `hubbardflow reference`.** It runs only the reference
node of an ordinary direct campaign. There is no pilot reuse and no adoption of foreign outputs.
The reference campaign can later be resumed as a full direct campaign.

**D14e. Deferred.** The following wait for TASK 24:
- near-symmetry refinement for relaxed or non-rational coordinates (they stay `ALL_SUBSPACES`,
  which is safe);
- I.5 for non-polarized outputs (the parser fails on them today; see 23.7);
- rotations and spin flip;
- an automatic one-command `run` that chains `reference`.

## 0. Rules

1. **Premises.** Re-check each premise with one real command and log it in `docs/fdebq/TASK23_LOG.md`.
   A false premise blocks only what depends on it; record it in `BLOCKERS.md`.
2. **Gates after every commit:**
   - replay test;
   - 20.9 golden;
   - product tests;
   - the 70 scientific regressions;
   - architecture test (the allowlist may only shrink; no item adds an entry);
   - ruff, format, mypy (`MYPYPATH=src`);
   - V6 gate;
   - full suite with no new failures (`pytest tests --continue-on-collection-errors`).

   CI must be green twice in a row on the final tip.
3. **Test edits.** Allowed only under R5 (adapt access to moved or renamed code, never an
   assertion), plus the edits each item names. Log each one.
4. **Golden updates.** Allowed only where an item authorizes them. Log the old and new hashes and a
   summary of the JSON differences.
5. **Conservative-and-continue** for ambiguities that cannot change results. Stop only on an
   unauthorized golden mismatch, a false premise, or a stop rule in 23.6 or 23.7.
6. **Commits and reviews.** One item = one commit. Use `verificador_luna` on each diff. Use
   `auditor_cientifico` before 23.1 and 23.2.
7. **pytest.** Never collect from the repository root. Always run `pytest tests`.
8. **SIESTA.** Only in 23.6 and 23.7, only from the main session, only in WSL, and always with
   `setsid nohup … < /dev/null > log 2>&1 &` plus a liveness check from a new shell.
   - **Workspace.** Campaigns go under `~/hubbardflow_validation/`. In the working copy of the
     execution profile, the only authorized edit is `wsl.workspace_root`, as in TASK 22. Log the new
     sha256.
   - **Frozen code.** Run the CLI with the frozen worktree's code
     (`PYTHONPATH=<worktree>/src <python> -m hubbardflow.cli`) and log `hubbardflow.__file__`.
   - **Inside WSL**, use the `campaign.v2.json` path for `status`, `stop` and `resume`, not the
     Windows pointer.
   - **Code defects found after SIESTA ran in 23.6** (our code, not SIESTA):
     1. fix them in a new commit with a test;
     2. re-freeze the worktree at that commit;
     3. continue with `resume`. Receipts survive as long as the planner version does not change.
        Do not rerun finished SIESTA nodes.

     Log every such fix in the item's document.

---

## 23.1 Species identity from the global basis **[science]**

**Premises**
- `siesta_backend/fdf_model.py` `species_identity` (~L725) returns `ESTABLISHED` only if the
  pseudopotential is found **and** the species has a `PAO.Basis` record. No archived FDF in the
  repository has `PAO.Basis`. The only blocks found in repository FDFs are: `LatticeVectors`,
  `ChemicalSpeciesLabel`, `AtomicCoordinatesAndAtomicSpecies`, `DFTU.Proj`,
  `kgrid_Monkhorst_Pack`, `DM.InitSpin`, `BandPoints`, `BandLines`, and once each `DFTU.Projector`
  and `DFTU.Hubbard` in `examples/MnO_smoke_-0.10.fdf`.
- **Consequence for MnO.** The MnO v3r2 reference
  (`campaigns/mno_afmii_strict_lr_v3r2/results/response-matrix-foreground-recovery-v4/00_REFERENCE/siesta.fdf`,
  sha256 `3c86abab…`) gets inventory `SUBSPACE_MAPPING_NOT_ESTABLISHED`. Coverage F2 is then
  `AMBIGUOUS` and every operation carries `EVIDENCE_BINDING_MISMATCH`: the inventory digest is set,
  but `bind_symmetry_model` sets `identity_digest=None` for non-established species.
- **Author prototype.** With identity established, `hubbardflow plan … --coverage
  TRANSLATION_SHADOWED` on that FDF gives the following, with no other change:
  - `SYMMETRY_REDUCED`;
  - 2 classes of 8: {MnLR00, 02, 04, 06, 08, 10, 12, 14} and {MnLR01, 03, …, 15};
  - shadows MnLR02 and MnLR03;
  - 4 computed columns, 48 run specs;
  - plan status `REVIEW` with reasons `[SHADOW_PENDING]`.

  This used the archived `siesta.out` as reference output and any DM file.
- **PAO.Basis header.** Its first row (`<label> <nshells> [ionic charge]`) is dropped from
  `pao_basis_blocks` (~L685: `current_label, current_basis = first, []`). Two labels that differ
  only in ionic charge therefore get the same digest. This is a fail-open defect.
- **Identity lookup ignores the lr-config map.** `species_identity` looks for `<label>.psml`
  in the search directories. Callers pass the **parents** of the lr-config pseudopotential paths. The plan-time callers are
  `product_plan.resolve_product_snapshot` (~L157) and `campaign_plan._resolve_campaign_planning`
  (~L118–123), which calls `species_identity` directly. A config that maps 16 labels to a single
  `Mn.psml` therefore gets no identity at plan time. The author's prototype used label-named copies,
  which hides this. Campaign init then stages
  `pseudopotentials/<label>.psml` copies (`wsl_campaign_init.py` ~L179), so the same input is
  established at run time.

**Change** (`fdf_model.py`, plus the two callers)
1. **Species-neutral blocks**, compared with `canonical_fdf_label`: `ChemicalSpeciesLabel`,
   `AtomicCoordinatesAndAtomicSpecies`, `LatticeVectors`, `LatticeParameters`,
   `kgrid_Monkhorst_Pack`, `DM.InitSpin`, `DFTU.Proj`, `PAO.Basis`, `BandLines`, `BandPoints`.
   Take the block set from `_blocks(model.effective_text)`. Do not add a field to `FdfModel`.
2. **Global-basis condition.** Let `global_basis` be true iff no other block exists and
   `User.Basis` / `User.Basis.NetCDF` is not true. Then `ESTABLISHED` iff all of these hold:
   - the pseudopotential is known;
   - `global_basis` is true;
   - either the species has a `PAO.Basis` record, or the FDF has no `PAO.Basis` records at all.
3. **Fail-closed coverage.** The same unknown-block / User.Basis rule now also applies to species
   with a `PAO.Basis` record. The author's suite run shows this adds no failures.
4. **Digest payload.** Keep it unchanged, except that the `PAO.Basis` record now includes the
   header fields after the label (fixes the ionic-charge defect).
   - Existing digests for FDFs without `PAO.Basis` stay byte-identical. The author verified this on
     MnO, where all 16 Mn labels share `c6392b95…`.
   - Keep the raw `.ion` digest as is. Labels inside `.ion` files keep such species distinct,
     which is fail closed.
5. **Explicit pseudopotential map.** Add an optional `pseudopotentials: Mapping[str, Path]`
   argument to `species_identity`. When a label is mapped, hash that file and do not search for it.
   - Pass the lr-config map (`config["pseudopotentials"]`) **only** from
     `product_plan.resolve_product_snapshot` (~L157) and `campaign_plan._resolve_campaign_planning`
     (~L123).
   - Leave the `campaign_inventory` callers unchanged: run-time inventories hash the staged
     `pseudopotentials/<label>.psml`, which are the same bytes.
   - Passing the map there breaks the fake in
     `test_campaign_runner_legacy_resume.py`, which is not authorized.
   - Keep the directory search for unmapped labels and for `--identity-dir`.
   - Add a test for a single-file map. After `initialize_campaign`, the product plan's
     `inventory.digest` must equal both
     `campaign_inventory(root/'reference.fdf', (root/'pseudopotentials',)).digest` and the frozen
     `resolved_perturbation_plan.json` `inventory.digest`.
6. **Planner version.** Bump `CAMPAIGN_PLANNER_VERSION` to `campaign-planner-v4`: plans for the
   same inputs change. 22.2 already makes old frozen plans fail with `PLANNER_VERSION_CHANGED`.

**Tests**
- Use the MnO reference FDF, with a lr-config map of the 16 MnLR labels to the single repository
  `Mn.psml` (`campaigns/mno_afmii_strict_lr_v3r2/pseudopotentials/Mn.psml`). Expect 17
  `ESTABLISHED` identities, one shared digest for the 16 Mn labels, and a different one for O.
- Adding `%block PS.lmax` (any contents), or adding `User.Basis T`, gives `NOT_ESTABLISHED` for
  every species.
- `PAO.Basis` headers `MnLR00 2 0.0` and `MnLR01 2 0.5` with identical shells give different
  digests.
- `PAO.Basis` present for some labels only gives `NOT_ESTABLISHED` for the others.
- An unmapped label with no `<label>.psml` gives `NOT_ESTABLISHED` (existing behavior).
- **Product plan on MnO.** Use TS, `--reference-output` set to the archived `00_REFERENCE/siesta.out`,
  and `--reference-dm` set to any small file written by the test. Expect the prototype result
  above: 2 classes with those exact members, shadows MnLR02/MnLR03, 4 computed columns, 48 run
  specs, `REVIEW`/`[SHADOW_PENDING]`.

**Authorized test and golden edits.** These are the failures that the author's and the auditor's
prototypes produced: 6 identity-related failures plus 3 planner-version tests. Anything else failing
is a stop.
- `docs/fdebq/task10_reports/{CoO,NiO,FeO,Cu3N}.json`: regenerate.
  - The diff may only touch identity-derived fields: `SPECIES_IDENTITY_NOT_ESTABLISHED` and
    `EVIDENCE_BINDING_MISMATCH` reasons, `identity_digest` values, F2 status/value, the inventory
    digest/status, and the digests that hash them.
  - If `strategy` or `would_reduce_to` changes, stop. The auditor's run changed only `$.reasons[]`.
- `tests/fixtures/replay_nio_p5/campaign_manifest.sha256.json`: only the entries `campaign.lock`,
  `campaign.v2.json` and `resolved_perturbation_plan.json`. Regenerate
  `campaign_json_snapshot.json` as well: it is diagnostic and not asserted.
  - Every other replay assertion must still pass unchanged: analysis equivalence, Part A U and I.5.
- `tests/unit/test_symmetry_operations.py::test_archived_fdf_geometry_binding_includes_ligands_and_missing_identity_stays_explicit`:
  - replace the single assertion `any(atom.identity_digest is None …)` with "all identities set"
    (CoO has `Co.psml` and `O.psml`);
  - add a case with a search directory lacking `O.psml`, where O atoms have `None`;
  - you may rename the test.
- `tests/unit/test_campaign_plan.py`: the `campaign-planner-v3` literals become `v4` (3 tests),
  including renaming `test_new_planner_version_is_v3…`.

## 23.2 I.5 as the shadow state gate **[science]**

**Premises**
- `CampaignShadow._complete_state_gate()` (`execution/campaign_shadow.py` ~L212) returns False and
  takes no arguments. `_outcomes` uses it in `state_valid`. The synthetic runner tests monkeypatch
  it with `lambda: True` (`tests/unit/test_campaign_shadow.py` ~L222).
- In `_execute_analysis` (~L1740), `state_gate_mapping(…, covered=not adaptive and self.shadow is None)`
  marks every pair `PATH_NOT_COVERED` in TS campaigns.
- In TS campaigns, `runner.sites[i]` corresponds to `plan.inventory.subspaces[i]`. The runner's
  `site_id` is the lr-config label (`MnLR00`); the plan's `site_id` is `MnLR00@0:3:2`. **Match
  columns by inventory index, never by id string.**
- `qualify_state_gate` gives verdict `PASS` even when G4 is `NOT_AVAILABLE`. The replay golden
  shows G4 `NOT_AVAILABLE` (no `.EIG` in the replay fixtures). The real TASK 22 run shows G4
  `PASS`.
- **Author check on archived MnO.** Columns MnLR00 and MnLR01, both modes, all six α, G4 without
  `.EIG`: every check passes (G1 24, G2 768, G3a 768).
- **Auditor check.** With `covered=True` and no index filter on a TS replay, the 12 reconstructed
  (never-run) columns come out `FAIL` with G1 `NODE_NOT_VALIDATED`. The index filter below is
  therefore required.

**Change**
1. `state_gate_mapping` gains `site_indices: Collection[int] | None = None`.
   - When given, columns outside it get verdict `NOT_ESTABLISHED` with a new reason
     `RECONSTRUCTED_FROM_REPRESENTATIVE`. They are not evaluated.
   - `None` keeps today's behavior exactly.
2. A pure function `shadow_state_gate_passed(mapping, site_ids) -> bool` in
   `execution/state_gate_step.py`, implementing D14b. `site_ids` are the mapping's `column_id`
   values: the runner labels. It is false if any computed column/mode pair is missing.
3. `CampaignShadow._complete_state_gate(self, runner)`:
   - takes `computed_indices` = the inventory indices of `plan.computed_columns` ∪ `self.expanded`;
   - builds the mapping with `site_indices=computed_indices`;
   - returns `shadow_state_gate_passed(mapping, [runner.sites[i]["site_id"] for i in computed_indices])`.

   Any exception → False. `_outcomes` and `analysis_data` pass the runner.
4. In `_execute_analysis`, shadow campaigns call `state_gate_mapping` with `covered=not adaptive`
   and `site_indices` = computed ∪ expanded. Direct campaigns are unchanged. The replay golden
   must not change.
5. Dataset field `translation_shadow.complete_state_gate` reflects the new gate.

**Tests**
- `shadow_state_gate_passed` on crafted mappings:
  - all `PASS` with G4 `PASS` → True;
  - one G4 `NOT_AVAILABLE` → False;
  - one pair `FAIL` → False;
  - a missing computed pair → False;
  - G2 `NOT_DEFINED` with everything else `PASS` → True.
- A mapping built with the existing helpers from `tests/fixtures/i5_real_nio` (NiO, with `.EIG`)
  satisfies the rule: the rule is satisfiable on real data.
- `state_gate_mapping` with `site_indices`: reconstructed columns get
  `RECONSTRUCTED_FROM_REPRESENTATIVE`; computed ones are evaluated as before.
- R5 adaptation: `lambda: True` becomes `lambda *_: True` in `test_campaign_shadow.py`. No
  assertion changes. All synthetic shadow tests pass.

## 23.3 Product admission for TS, and the parent-DM check

**Premises**
- `execution/product_admission.py` `execution_admission` has only
  `ADMISSIBLE_LEGACY_EQUIVALENT`/`BLOCKED`. It blocks coverage outside `{DISABLED, DIAGNOSTIC}`
  and any reduced class.
- `product_plan.product_execution_boundary` (~L395) adds `SCIENTIFIC_STATE_NOT_ESTABLISHED`,
  `PILOT_REUSE_NOT_ESTABLISHED` and `PLAN_NOT_READY` unless the admission is legacy.
- `product_cli.product_command` (~L350) executes only on `ADMISSIBLE_LEGACY_EQUIVALENT`.
- `wsl_campaign_init` copies `planning_reference_output`/`planning_reference_dm` into the campaign
  (~L168, ~L265), and `product_cli._verify_campaign_inputs` verifies the copies (~L163).
- The runner records the reference DM after validation (`_execute_siesta` ~L819).

**Change**
1. **New status `ADMISSIBLE_TRANSLATION_SHADOWED`.** Admit iff all of these hold:
   - frozen plan and config;
   - coverage `TRANSLATION_SHADOWED`;
   - inventory `OK` (no identity-only exemption on this route);
   - no split staging, no adaptive policy, strategy fixed or user-explicit grid;
   - spin flip, rotations and auto-split all false;
   - plan reference `ADMISSIBLE`; the parent DM digest is traceability metadata;
   - `plan.reason_codes ⊆ {SHADOW_PENDING}`;
   - at least one reduced class, every reduced class with a shadow;
   - run specs = computed columns × {BARE, SCREENED} × grid;
   - the declared lr-config sites equal the inventory sites.

   - `reference_dm_name` equals `<SystemLabel>.DM` of the reference FDF, or `siesta.DM` when the
     FDF has no `SystemLabel`.

   New reasons:
   - `PARENT_DM_REQUIRED`;
   - `REFERENCE_NOT_ADMISSIBLE`;
   - `PLAN_REASONS_PRESENT`;
   - `NO_TRANSLATION_REDUCTION` (TS requested but nothing reduces: use `DISABLED`);
   - `REFERENCE_DM_NAME_MISMATCH`.

   The legacy route does **not** get the DM-name check: its fixtures have no `SystemLabel`.
2. **Boundary.** `product_execution_boundary` treats this admission like the legacy one: no
   `SCIENTIFIC_STATE_NOT_ESTABLISHED`, `PILOT_REUSE_NOT_ESTABLISHED` or `PLAN_NOT_READY`.
   `product_command` executes on either admissible status.
3. **Runner (D16.1).** Before `reference_completed`, compare the final converged
   planning and campaign reference state. Both outputs must converge and terminate
   normally to establish equivalence, and complete atom/projector identities must
   agree. Every corresponding occupation element uses
   `tol_e = max(print_half_width_planning_e + print_half_width_campaign_e,
   parent_reproduction_factor * SCF.DM.Tolerance)`.
   The printing radius is calculated separately from the two lexical tokens of
   that element, never from a global maximum. `parent_reproduction_factor` must
   be explicitly declared, recorded in the frozen policy and has no implicit
   numerical value. `SCF.DM.Tolerance` is read from the reference FDF.
   - `parent_reproduction` accepts `PRINT_EQUIVALENT` (default) or `RECORD_ONLY`.
     No bitwise reproduction mode or DM-hash rejection exists. The default
     cannot establish physical equivalence when the factor/tolerance is missing;
     it records `EQUIVALENCE_NOT_ASSESSED` without blocking response execution.
   - `RECORD_ONLY` never grants equivalence. It still records and rejects a real
     assessed occupation difference outside the effective tolerance, or incomplete
     atom/projector identity. It cannot suppress a physical failure.
   - A measured occupation difference records `PARENT_STATE_NOT_EQUIVALENT` with
     atom, spin, element, difference and effective tolerance. All affected atom
     indices are persisted; every affected class of this parent runs directly.
     Incomplete identity records `PARENT_IDENTITY_NOT_ESTABLISHED` and schedules
     all reduced classes using that parent directly. Unparseable output records
     `EQUIVALENCE_NOT_ASSESSED`; digest agreement never replaces missing evidence.
   - The node evidence and report retain both planning/campaign DM digests,
     criterion, reason, maximum differences, per-element effective tolerances,
     SCF.DM.Tolerance and factor. Campaign response nodes use that campaign's own
     reference DM. Parent DM digest consistency is recorded as a warning only.
   - **Separate dimensional policy for Fermi (D16.1).** `tol_Fermi_eV` is an
     optional nonnegative finite energy tolerance declared in lr-config, with no
     default. Product CLI `--tol-fermi-ev` overrides config and freezes source
     `cli`; config declarations freeze source `config`. SCF.DM.Tolerance never
     applies to Fermi. With a declaration compare the absolute energy difference
     against `max(tol_Fermi_eV, half_width_planning_eV + half_width_campaign_eV)`.
     Independent print half-widths add conservatively; a declaration below this
     combined radius emits `FERMI_TOLERANCE_BELOW_PRINT_HALF_WIDTH` and uses the
     combined radius. Both the declared and effective values remain recorded.
     Without a declaration Fermi is `RECORDED_NOT_ASSESSED` and cannot alter the
     parent verdict. `occupation_equivalence` is `EQUIVALENT`, `NOT_EQUIVALENT`
     or `NOT_ASSESSED`; `fermi_equivalence` is `EQUIVALENT`, `NOT_EQUIVALENT` or
     `RECORDED_NOT_ASSESSED`. Occupations decide the global verdict except that
     a declared Fermi tolerance exceeded produces `PARENT_FERMI_NOT_EQUIVALENT`
     and direct computation of the classes using that parent. `RECORD_ONLY`
     never grants equivalence, retaining rejection of assessed physical failures.
4. **Stop instead of expanding on shadow rejection (D14 policy).**
   - **The key.** Add an optional lr-config key `shadow_rejection_policy` ∈ {`EXPAND`, `STOP`}.
     `validate_lr_config` validates it and copies it into its output **only when the input sets
     it**. An absent key means `EXPAND`. Configs without the key keep byte-identical planning
     digests, so the replay golden must not change in 23.3.
   - **Injection.** The product injects `STOP` when coverage is TS and the lr-config does not set
     the key. Do it in `product_plan._config()`, after the CLI `--coverage` merge, so that it is
     part of `frozen_lr_config_json` and its sha. Never inject after freezing: that would break
     `_verify_campaign_inputs` and the snapshot re-resolution in `product_command`.
   - **Behavior under `STOP`.** Where `CampaignShadow` would expand (a `REJECTED_EXPANDED` outcome
     in `prepare`, or `failed_shadow`), it raises a typed `ShadowRejected` carrying the outcomes and
     installs no new DAG. `advance` catches it and returns 1 after it:
     - persists the outcomes in `translation-shadow-state.json`;
     - persists the state-gate mapping used by `_complete_state_gate` to
       `results/i5_state_gate.json`;
     - finishes the heartbeat `FAILED` with `reason: "SHADOW_REJECTED"` and the rejecting class;
       `status` shows them.

     Do not return False from `prepare`: `advance` would call it again forever on the same gate
     node.
   - **Afterwards.** The user reruns with `DISABLED`. No SIESTA run starts after the rejection.
5. **`run --dry-run`.** It plans, freezes, computes admission and boundary, prints them, and never
   initializes or executes a campaign. 23.6 and 23.7 use it.
   - It needs `--profile` but not `--name`: skip the `--name` check under `--dry-run`.
   - Add `--dry-run` to the FDF-only product options that are rejected for manifest targets
     (`cli.py` ~L279–290).
6. The legacy route and its results are unchanged.

**Tests**
- The 23.1 MnO TS plan → `ADMISSIBLE_TRANSLATION_SHADOWED`. Each of these → `BLOCKED` with the
  right reason:
  - no reference DM;
  - spin flip on;
  - adaptive policy;
  - an extra plan reason;
  - a TS plan with no reduction (NiO P5 inputs with a reference: its sites are AFM-inequivalent).
- NiO P5 `DISABLED` → still `ADMISSIBLE_LEGACY_EQUIVALENT`.
- The boundary for TS has none of the three blocking reasons.
- `product_command` launches the worker for TS (monkeypatched worker, as existing product tests do).
- A synthetic TS runner whose reference writes different DM bytes and has no assessed physical
  difference completes; both digests are recorded and never decide. Noise below the effective
  occupation tolerance does not reject. A real occupation difference outside tolerance records
  `PARENT_STATE_NOT_EQUIVALENT` and schedules all affected classes directly, in both reproduction
  modes. Incomplete identity uses `PARENT_IDENTITY_NOT_ESTABLISHED`; unparseable or missing
  occupation tolerance evidence is explicitly `EQUIVALENCE_NOT_ASSESSED`. Fermi without an
  energy declaration records `RECORDED_NOT_ASSESSED` and does not change the occupation verdict.
  Declared Fermi tolerances exercise inclusive pass, own reason code on failure, and the
  warning plus effective summed print radius when the declaration is too small.
- Under `STOP`, a rejected shadow finishes `FAILED`/`SHADOW_REJECTED` with no further node
  executed. `prepare` is called exactly once, and `results/i5_state_gate.json` exists. Under
  `EXPAND`, the existing expansion tests pass unchanged.
- A product TS snapshot's `frozen_lr_config_json` contains `shadow_rejection_policy: STOP`; a
  DISABLED one does not.
- `run --dry-run` never calls `initialize_campaign` or the worker.
- **POSIX integration test: MnO TS replay on archived real outputs** (no new large fixtures).
  This is the first end-to-end run of the new code; it must pass before 23.6. Fake SIESTA:
  - keyed by `SystemLabel`;
  - `00_REFERENCE` serves the archived reference `siesta.out` and writes a fixed DM whose bytes
    are also the plan's planning DM;
  - `lr_s000_*` / `lr_s001_*` serve the archived `A_*` / `B_*` outputs from
    `campaigns/mno_afmii_strict_lr_v3r2/results/response-matrix-foreground-recovery-v4/`;
  - the shadow columns serve the same outputs with the 16 per-atom `hubbard_term` occupation
    blocks permuted by the translation that maps the representative to the shadow;
  - every run, including `00_REFERENCE`, also writes a synthetic insulating `<SystemLabel>.EIG`,
    so that G4 is `PASS`:
    - line 1 is the last `siesta: Fermi =` token of the output that this run serves, copied
      verbatim: G4 first checks it against stdout;
    - the k/spin/band layout and the band energies are identical for all runs;
    - every band is at least 0.5 eV from all the Fermi values served;
    - format sample: `tests/fixtures/i5_eig/`.
  - the harness lr-config sets `shadow_rejection_policy: STOP`, or the test drives the product
    `run` so that the injection is tested.

  The auditor's working prototype of this fake (scratch paths hard-coded; parametrize them) is in
  the delivery package at `C:\Users\Jairo\work\fdebq_task23\aux\mno_ts_replay_harness\`, not in
  the repository. Expect:
  - `COMPLETED` with 49 SIESTA executions;
  - both shadows `PROVEN`;
  - `complete_state_gate: PROVEN`;
  - the reconstructed matrices equal the analysis primary matrices within `atol=1e-12`;
  - the class-member U spread ≤ 1e-9 eV.

  Variants:
  - a fake whose reference DM bytes differ without an assessed physical difference still completes
    with distinct planning/campaign digests recorded;
  - a fake whose reference occupation state differs outside the effective tolerance gives
    `PARENT_STATE_NOT_EQUIVALENT` and directs every affected class to explicit computation;
  - both `PRINT_EQUIVALENT` and `RECORD_ONLY` retain rejection of physical differences and
    incomplete identities; missing SCF tolerance/factor or unparseable evidence is explicitly
    unassessed. Fermi uses only its own declared eV tolerance or remains record-only;
  - a fake that serves the shadow column unpermuted gives `SHADOW_REJECTED` with no execution after
    the barrier;
  - a fake without `.EIG` gives `SHADOW_REJECTED` through the D14b gate;
  - one variant keeps `EXPAND` with the unpermuted shadow and asserts that the expansion happens.

## 23.4 `hubbardflow reference`

**Premises**
- `run_campaign_worker(manifest, mode)` passes `mode` to `CampaignRunner.advance`, which
  special-cases `run` and `resume`.
- The reference node copies the source FDF bytes verbatim (`command_factory.py` ~L188). Its DM is
  `layout.reference_dm_name`, and the node record has `artifact_spec.dm` and
  `command.stdout_path`.
- A `reference_dm_name` different from `<SystemLabel>.DM` fails only after SIESTA, in the output
  validator ("required DM artifact is missing", `output_validator` ~L86/L211). `validate_lr_config`
  defaults it to `reference.DM` (`campaign_v2` ~L379). For MnO the right value is
  `00_REFERENCE.DM`.

**Change**
0. **DM-name check.** `reference` refuses to start when `reference_dm_name` differs from
   `<SystemLabel>.DM` (or `siesta.DM` without a `SystemLabel`), with a `ProductError` naming both.
   It shares the helper with the TS admission check of 23.3. `_execute_product_campaign` and the
   legacy route are untouched.
1. **`advance("reference")`.** Behaves like `run`, but returns 0 after the reference node
   validates, with heartbeat `STOPPED`, `stop_reason: "reference_only"`. A failed reference
   finishes `FAILED` as usual. `resume` later continues the campaign as a full direct run.
2. **Product subcommand `reference`.** It takes the same product options as `run`, and refuses
   `--coverage TRANSLATION_SHADOWED`, `--reference-output` and `--reference-dm`.
   - It plans, requires `ADMISSIBLE_LEGACY_EQUIVALENT`, initializes the campaign exactly like
     `run`, and runs the worker in mode `reference`.
   - Then it copies the reference stdout to `<output-dir>/planning_reference/reference.out` and the
     DM to `<output-dir>/planning_reference/<dm name>`, never overwriting.
   - It writes `<output-dir>/planning_reference/receipt.json` with:
     - both sha256s;
     - the campaign manifest path, node id and command argv;
     - the input FDF sha256.
   - It prints the follow-up `run` command.
   - Default output dir: `.hubbardflow/<FDF stem>-reference`.
3. **USER_GUIDE.** Add a section "Translation-shadowed runs" covering the two commands, what
   `PARENT_STATE_NOT_EQUIVALENT` means, the `parent_reproduction` modes, and when to use
   `DISABLED` instead.

**Tests**
- `advance("reference")` executes only the reference node (synthetic runner).
- CLI refusals, and the DM-name mismatch error raised before any execution.
- **POSIX integration test.** Reuse the replay harness's fake SIESTA and NiO P5 inputs; you may move
  shared harness helpers into a test helper module under R5. Expect:
  - `reference` executes exactly one SIESTA run;
  - `planning_reference/<dm>` has sha256 `f7fca191f941bbda5ee38eb361096aa8a802dfd410e12aaa680f39f3cf2193ef`;
  - `reference.out` equals the fixture's reference output bytes;
  - `plan --coverage TRANSLATION_SHADOWED` with those two files gives reference `ADMISSIBLE` and
    that parent DM.

## 23.5 Plan report: readable summary and real actions

**Premises**
- `reporting/product_report.py` embeds the full canonical planning JSON in "Decisions and
  evidence". For MnO this makes `plan_report.md` 2.6 MB (3.15 MB after 23.1): each of
  the 128 operations embeds the whole atom model.
- "Actions required" is static text that says production needs the I.5 producer, which is no
  longer true for TS.

**Change**
1. Replace the JSON dump with:
   - a classes table: representative, shadow, member count, status, reasons;
   - an operations summary: total; accepted; count by exactness class; count by first failing
     condition;
   - the admission status and reasons when present, read from `ProductBoundary.admission`. Do
     not add a `reporting → execution` import: the architecture test forbids it;
   - links to `resolved_perturbation_plan.json` and `product_plan.json`, which keep the full
     evidence unchanged.
2. Derive "Actions required" from the actual reasons. Examples:
   - `PARENT_DM_NOT_ESTABLISHED` → "run `hubbardflow reference` and pass `--reference-output/--reference-dm`";
   - `SPECIES_IDENTITY_NOT_ESTABLISHED` → name the cause (missing pseudopotential, unknown block,
     User.Basis);
   - TS admissible → "ready: run with `--profile`".

   Never claim a producer is missing when it exists.
3. No JSON artifact or digest changes.

**Tests**
- For the 23.1 MnO TS plan, `plan_report.md` is < 200 kB and contains both classes. No fenced block
  exceeds 10 kB.
- Existing report tests that assert the old static text: update only those strings (authorized,
  logged).

## 23.6 Real validation: MnO v3r2, translation-shadowed (SIESTA)

Start only after the 23.3 MnO TS replay test passes.

**Setup**
- **Frozen code.** `~/hubbardflow_validation/code_<short sha>`, a clean worktree of the 23.5 commit
  on ext4. Run with `PYTHONPATH=<worktree>/src` and the TASK 22 Python,
  `/home/jmc/.local/state/siestaflow/hubbard-response-env/bin/python`. Log `git rev-parse HEAD` and
  `hubbardflow.__file__`.
- **Work folder.** `~/hubbardflow_validation/mno_ts_<YYYYMMDD>/inputs/`. Copy these files, verifying
  each sha256:

  | file | source in the repo | sha256 |
  |---|---|---|
  | `reference.fdf` | `campaigns/mno_afmii_strict_lr_v3r2/results/response-matrix-foreground-recovery-v4/00_REFERENCE/siesta.fdf` | `3c86abab6daf4c0c00a10da6a7e060470e54bcc5364f70a0e2932285c24941e6` |
  | `Mn.psml` | `campaigns/mno_afmii_strict_lr_v3r2/pseudopotentials/Mn.psml` | `0b97ccd71456e4a7b28316f78ddb30bb1f6a82d9aba386c7fde78090d31c0dc6` |
  | `O.psml` | `campaigns/mno_afmii_strict_lr_v3r2/pseudopotentials/O.psml` | `5ca5d753a995bd054279007ba76be71d622b60460c6f9a0d9bb37d81bdf185fe` |
  | `backend_compatibility.json` | `tests/fixtures/real_nio_p5_rerun/inputs/software/` | `5189620dfa1e8b6090cbdbb9c36c412835d16feb5c50bbc82b16c139d3bcff2e` |
  | `siesta_version.txt` | same | `bb5a9b03dfaec9953401a7ef8db045149461047c44f15f9c5bf7758900b5f3ee` |
  | `execution_profile.json` | `tests/fixtures/real_nio_p5_rerun/inputs/` | `fbc9ff5ae47a6791d0e1ff962b6070f8690f1ffef475bafd8784a7388d755ae1` (then the `workspace_root` edit of rule 8) |

- **`lr_config.json`.** Schema `siestaflow.lr_config.v2`, functional `PBE`, and **absolute paths
  only**: relative paths resolve against the lr-config's own folder.
  - **Sites.** The 16 sites `{site_id: MnLRxx, atom_index, orbit_id: MnLRxx}`. Atom indices for
    MnLR00..15 are 1, 2, 5, 6, 9, 10, 13, 14, 17, 18, 21, 22, 25, 26, 29, 30; verify them against
    the FDF.
  - `alpha_grid_ev`: `[-0.1, -0.05, -0.025, 0.025, 0.05, 0.1]`.
  - **Pseudopotentials.** All 16 MnLR labels map to the one `Mn.psml`; O maps to `O.psml`.
  - `compatibility_registry` and `version_text_source` point to the two software files.
  - `declared_executable` is `siesta`; `reference_dm_name` is `00_REFERENCE.DM`.
  - `analysis_policy`, `magnetic_moment_tolerance_muB` (0.1) and `adaptive_alpha_policy` (null):
    copy them from the NiO P5 config.
- **Binary check.** Log the sha256 of the SIESTA binary. The registry pins `aaa9a2e4…`, which is
  also the archived receipt's `runtime.siesta_sha256`, so admission already guarantees the same
  binary.

**Steps**
1. **Direct plan.** `plan --coverage DISABLED` (no SIESTA). Expect:
   - inventory `OK` with no reasons;
   - 16 sites;
   - 192 run specs, which is 193 SIESTA runs including the reference.

   Check the 17 identities by calling `species_identity` with the lr-config map; a DISABLED plan
   without a reference does not list them.
2. **Reference.** `reference --name mno_ts_ref --output-dir <work>/ref`. Log:
   - the wall time;
   - the DM sha256;
   - whether that DM equals the archived parent DM
     `65d418d1a21b4b4052d41d68554639fc4bc4682566bb780c0d072fd4cfe5eb47`.
3. **TS dry run.** `run --dry-run --coverage TRANSLATION_SHADOWED` with the two files from step 2
   and `--profile`. Expect:
   - the 23.1 classes, 4 computed columns and 48 run specs;
   - admission `ADMISSIBLE_TRANSLATION_SHADOWED`.

   Anything else is a product defect: **stop and report**.
4. **Run.** `run --coverage TRANSLATION_SHADOWED … --name mno_ts --output-dir <work>/ts`, launched
   with `setsid nohup`, about 1.5 h. Monitor with `status <campaign>/campaign.v2.json`.
   - If the worker finishes `FAILED`, for example with `PARENT_STATE_NOT_EQUIVALENT` or
     `SHADOW_REJECTED`, nothing expands (23.3). Report:
     - the failure record;
     - `<campaign>/.siestaflow/translation-shadow-state.json` with every comparison;
     - `results/i5_state_gate.json` (absent when the reference is rejected before the state gate).
   - If the failure is a defect in our code, apply rule 8. Otherwise stop.
5. **Gates.** Write `docs/fdebq/TASK23_MNO_TS.md` with gates a–e, then the verdict.
   - **a)** Physical state equivalence between the planning and campaign reference: per-element
     occupation tolerance is the maximum of summed print half-widths and the explicitly declared
     factor times FDF SCF.DM.Tolerance. Both DM digests are informational. Missing tolerance/factor
     is `EQUIVALENCE_NOT_ASSESSED`. Fermi has its separate assessment: without `tol_Fermi_eV`
     it is recorded without deciding this gate; with a declaration it must agree within the
     maximum of that energy tolerance and the summed print half-widths. The report presents
     both occupation and Fermi states explicitly, both digests, differences and used tolerances.
   - **b)** Both shadow outcomes are `PROVEN`/`WITHIN_PRINT_BOUNDS`. Report, per class and mode:
     - max |direct − reconstructed| / (sum of print bounds);
     - the SCF iteration count of each representative run and each shadow run.
   - **c)** I.5 is `PASS` for the 4 computed columns × 2 modes, with G4 `PASS`, and
     `complete_state_gate` is `PROVEN`.
   - **d) Archive comparison.** It is a gate only if the step-2 DM equals `65d418d1…`; otherwise it
     is informational.
     - Parse the archived `A_*/siesta.out` (MnLR00) and `B_*/siesta.out` (MnLR01) with **the same
       HubbardFlow parser and event selection** used for the new runs: the 6-decimal `Occupations:`
       totals.
     - Compare them with the new representative runs, per mode and α. Report the max difference in
       units of the last printed decimal; it should be 0.
     - **Do not** use `occupations_e` in `response-receipt.json`. Those are traces of the 5-decimal
       matrix and differ from the totals by up to 2.6 quanta even for identical runs.
     - Expected FDF differences:
       - SCREENED FDFs are byte-identical to the archive apart from `SystemLabel`;
       - BARE FDFs differ only in SCF convergence and tolerance lines, the position of
         `MaxSCFIterations 1`, `false`/`F` and `hamiltonian`/`Hamiltonian`, all irrelevant for one
         iteration.

       Report any other difference.
   - **e) U.** Report:
     - the 16 reconstructed U values;
     - the max spread inside each class, which must be ≤ 1e-9 eV;
     - a comparison with the archived certificate
       (`validation_observables_v6/mno/authoritative_u_inputs.json`, `central_u_eV`) and with
       `analysis-result-corrected-v1.json` (`U_Mn_eV`), stating the estimator and window differences.

     The U comparison is not a gate.

   **Verdict:** `TS_VALIDATED` iff a, b and c pass, and d (when it is a gate) gives 0. Otherwise
   `TS_NOT_VALIDATED`, with reasons.
6. **Fixture.** Put in `tests/fixtures/real_mno_ts/`:
   - `resolved_perturbation_plan.json`, xz-compressed;
   - `results/i5_state_gate.json`;
   - the dataset's `translation_shadow` section;
   - from `lr_u_analysis.v3.json` (about 8 MB), only the primary matrices and the U values, xz-compressed.

   Add a README with origin, input hashes, SIESTA version, layout and commit. Add a test that
   re-reads the fixture and checks:
   - both outcomes are `PROVEN`;
   - the reconstructed matrices equal the primary matrices within `atol=1e-12`;
   - the class-member U spread is ≤ 1e-9 eV.

   No SIESTA in CI.

## 23.7 Cu3N diagnostic (SIESTA, no code changes)

Goal: find what in **our** code fails on Cu3N. Do not fix anything here, even if rule 8 would
allow it; the findings feed TASK 24.

1. **Locate the inputs.** The repository has `tests/fixtures/cu3n_reference_siesta.fdf` (sha256
   `cb83162115cd2e8b414c1ebd05acc276b7b9a5d75535e18196f91e5a33641eaa`). Commit `c822f8b` copied it
   from `CU3N_PBE_LRU_SC222_RC3p0_V1/runs/00_REFERENCE/siesta.fdf`, which lives at the user's
   repository root.
   - Look first for that directory in the user's Windows clone(s) of the repository, and in their
     WSL copies. Compare its FDF against `cb831621…`.
   - Then search, bounded with `-maxdepth 6` (a `/mnt/c` scan is slow), excluding `.git`, for the
     evidence archive `cu3n_mathematical_evidence_20260812T210120Z.tar.gz` (sha256
     `76f5effd3d124d1723725a9f30d4ac17056b4d892f73b4c14c6028f96a87f11f`). From it extract only
     `runs/00_REFERENCE/siesta.fdf`, `siesta.out` and the pseudopotentials.
   - You need the FDF (`cb831621…`) and its pseudopotentials. Log every candidate and its sha256.
   - If the pseudopotentials cannot be found, skip 23.7 and report. Never substitute files.
2. **Describe the input.** Record:
   - atoms, species, `Spin`, k-grid, `MeshCutoff`;
   - the number of `DFTU.Proj` records;
   - the PAO settings;
   - every block name;
   - the identity outcome under 23.1.
3. **Direct plan.** `plan --coverage DISABLED` (no SIESTA). Record inventory and identity. Expect 24
   sites and 288 run specs (289 runs).
4. **Reference.** Run `reference` on the full FDF, with `reference_dm_name: 00_REFERENCE.DM` in its
   lr-config. Record:
   - wall time, normal completion and SCF iterations;
   - whether the reference is `ADMISSIBLE` for coverage;
   - the result of the I.5 point parser on its output (expected today:
     `PointStateEvidenceError … malformed Occupations summary`).

   Then run `run --dry-run --coverage TRANSLATION_SHADOWED --profile …` with it, and record:
   - the classes (the audit `docs/audits/CU3N_SYMMETRY_REDUCTION_AUDIT_20260909.md` expects three
     orbits of 8);
   - the computed columns;
   - the admission.

   **Never run TS on Cu3N:** without non-polarized I.5 it can only stop with `SHADOW_REJECTED`.
5. **One-column probe.**
   - Make `probe.fdf` by deleting every `DFTU.Proj` record except the record of the first class's
     representative. `diff` must show only removed lines. With U = 0 and no shift, the other
     projectors do not change the physics.
   - Write an lr-config with that one site, absolute paths, the same grid as 23.6, and
     `reference_dm_name: 00_REFERENCE.DM` (the Cu3N `SystemLabel` is `00_REFERENCE`). The legacy
     route has no pre-launch DM-name check.
   - Estimate the run as 13 × the reference wall time. If the estimate is above 4 h, skip the probe
     and report the estimate.
   - Otherwise launch `run --coverage DISABLED` with `setsid nohup`.
   - Report:
     - per run: mode, α, SCF iterations, wall time, returncode, `failure.json`;
     - the diagonal Δocc(α) for BARE and SCREENED, in print quanta;
     - the analysis status and the 1×1 U, labelled "single-site diagnostic, not the supercell U";
     - `i5_state_gate.json`;
     - every exception or traceback from our code (`worker-error.json`), with the failing node.
6. **Write `docs/fdebq/TASK23_CU3N_DIAGNOSTIC.md`.** It ends with two lists:
   - "Failures in HubbardFlow code", each with evidence;
   - "SIESTA behavior": SCF convergence, timing, and response magnitude versus the print quantum.

---

## Closing

Write `docs/fdebq/TASK23_SUMMARY.md` with:
- the items and their commits;
- the R5 and authorized test edits;
- the golden updates, with JSON-diff summaries;
- the conservative decisions;
- the MnO verdict;
- the Cu3N findings;
- the two green CI runs.

Push the branch. Do not open a PR.

**Out of scope (TASK 24):**
- the fixes found by 23.7;
- I.5 for non-polarized outputs and the Cu3N TS run;
- near-symmetry refinement;
- rotations and spin flip;
- the SCF ladder (T0–T4) and G3;
- one-command `run` chaining `reference`;
- the remaining runner refactor.
