# CODEX TASKS — Phase 3, part B: safety net + first behavior-preserving extractions

Base: `fdebq/r4-real-validation`, the result of Part A, which is not merged yet. Create
`fdebq/r5-phase3-runner` from its tip. Push it; no PR (the user merges).

**Goal.** Give `execution/campaign_runner.py` (2,261 lines; `CampaignRunner` is 1,790 lines with 45
methods) a real end-to-end safety net, make CI run everything, and extract the two lowest-risk
collaborators. Nothing may change any result, file or CLI behavior.

**Out of scope here** (record in BLOCKERS.md as deferred):
- the analysis step (`_execute_analysis` interleaves adaptive and shadow code);
- adaptive-α code;
- runner `__init__` and admission;
- atomic two-file receipts;
- the remaining allowlist entries;
- the typed `LRAnalysisResult`.

This file was audited against `041adf8` before delivery. The audit's corrections are already
included.

---

## 0. Working rules

1. **Premises.** Re-check each listed premise with one command and log it in
   `docs/fdebq/PHASE3_LOG.md`. If one is FALSE, record it in BLOCKERS.md and skip only what depends
   on it.
2. **Gates after every commit.**
   - (a) the Part A golden recompute test (`tests/fixtures/real_nio_p5_rerun`), byte-identical;
   - (b) the 3.1 replay test against its own frozen manifest, byte-identical;
   - (c) the 20.9 NiO P5 golden;
   - (d) the product and TASK 21 tests;
   - (e) the 70 scientific regressions;
   - (f) the architecture test, whose allowlist may only shrink. **No item may add an entry.**
   - (g) ruff, `ruff format --check` and mypy (`MYPYPATH=src`) on configured and new files;
   - (h) the V6 gate;
   - (i) the full suite with `--continue-on-collection-errors`, failing set ⊆ baseline.

   **Where they run.** Gate (b) needs POSIX: `fcntl` and an executable script. Run it in WSL (ext4
   copy or `/mnt/c`) or CI and record the output. On Windows it must be skipped
   (`sys.platform == "win32"`), never failed and never silently passed.

   **On a golden mismatch,** stop the item, `git restore` it and record it. Never adjust a golden.
3. **Test edits (R5).** You may rewrite a test only to adapt how it reaches code an item moved:
   `object.__new__(CampaignRunner)` sites, instance monkeypatches of moved methods, and imports of
   moved functions. Prefer leaving delegators and re-export aliases in `campaign_runner.py` so that
   most tests need no edit. Assertions and expected values never change. Log every edit (old →
   new).
4. **Moving code.**
   - Move code with only the edits needed for strict mypy, ruff format and explicit typed
     signatures on the new modules.
   - No logic, ordering, file names, JSON keys, exception types or messages may change.
   - New modules stay ≤ 400 lines (split if needed) and get a small unit test of their public
     surface.
5. **Private helpers of `campaign_runner.py` itself.** These are needed by moved code, for example
   `_atomic_json` (store) and `_campaign_relative_path` (assembler).
   - Move each one into the new module, or into a small `execution/campaign_files.py`, as a public
     name.
   - `campaign_runner.py` imports it from there, keeping a private alias.
   - New modules never import `campaign_runner`, which would be a cycle and fail the architecture
     test.
6. **Live state.** `CampaignShadow.install` (`campaign_shadow.py` ~L82-86) and adaptive
   `_rebuild_adaptive_graph` (~L611) **replace** `runner.dag`, `runner.specs`, `runner.executor`
   and `runner.checkpoint_identity` at runtime. Collaborators must never capture these at
   construction. They receive them per call as arguments, or through a zero-argument accessor that
   reads the runner's current attribute.
7. **Reviews.** Use `verificador_luna` on each diff. `auditor_cientifico` is not required, because
   the goldens are the check. Ambiguity that cannot change results: choose the conservative option,
   log it as **conservative implementer decision**, and continue.
8. **Static debt.** For pre-existing files outside the lint list, counts must not increase and
   touched lines must be clean.
9. Always run `pytest tests`, never the repository root.

---

## 1. Items (one commit each, in order)

### 3.0 Preconditions and baseline (no code)

- `docs/fdebq/REAL_VALIDATION_NIO_P5.md` must exist with verdict `IDENTICAL` or
  `WITHIN_REPORTED_BOUNDS`. Otherwise stop the whole part.
- The Part A recompute test must pass. If Part A recorded that recomputing from the stored dataset
  alone is not possible, gate (a) is dropped and the 3.1 replay test becomes the only end-to-end
  golden. Record this in the log.
- Record `BASELINE_FAILURES` (full suite) on the tip, both in your environment and in WSL.

### 3.1 End-to-end replay test (tests and fixtures only)

**Premise.** No test constructs `CampaignRunner(manifest)` end-to-end (TASK 21 P8: "none").

**Recipe.** It is feasible without production changes; follow it and adapt only where a premise
proves different. Build `tests/integration/test_runner_replay_nio_p5.py`:

1. **Campaign.** Initialize it with `initialize_campaign` from the NiO P5 inputs, using a
   **test-written** profile and a test-written lr-config. Rewrite the lr-config's absolute paths to
   fixture paths. The profile is:
   - `local_wsl`, with `workspace_root` = `tmp_path`;
   - 1 rank, `environment: {}`;
   - launcher = a script named `mpirun.openmpi` (required by `command_factory.py` ~L58-63) that
     execs its executable argument;
   - SIESTA = a replay script named `siesta`.
2. **Executable registry.** Write the registry/backend contract with the replay script's sha256,
   following `tests/unit/test_siesta_production_runtime.py` ~L70-79. Never weaken or bypass
   production admission. If that is impossible, stop the item and report why.
3. **Replay.** For each run, the script copies the Part A output files of the run whose input FDF
   has the same sha256.
   - Store under `tests/fixtures/replay_nio_p5/` only what the validator and parsers read, plus each
     run's DM. Find out which files those are by reading the code, and log the list.
   - Compress with xz. If the total exceeds 50 MB, stop the item and report the size per file type.
     The author expects about 30–45 MB because of the DMs.
4. **Assertions.**
   - (a) The worker completes.
   - (b) **Against Part A**, the analysis JSON is equal after removing only fields from these
     categories:
     - campaign identity: `campaign_id`, `campaign.name`, `input_identity`, and contract/backend
       hashes that embed the campaign id;
     - timestamps;
     - attempt paths (`attempt-<time_ns>-<uuid>` inside `fdf_path` / `out_path` / `dm_path`);
     - hashes of inputs that embed the campaign root's absolute path (for example
       `declared_inputs.lr_config.sha256`);
     - runtime binding: `evidence_digest`, `runtime_executable`, the execution-profile sha256,
       `package_version`;
     - DM-derived hashes, if the DMs differ from Part A's.

     Every numerical field, every occupation and every U value must be equal. Log the exact key
     paths removed and the category of each.
   - (c) **Against its own frozen golden,** stored in the test as a manifest of every file written
     in the campaign directory with sha256 (attempt directory names normalized), the run is
     byte-identical. This is gate (b).
   - (d) **Resume.** The replay script writes `stop-request.json` after about half the runs. The
     worker stops, the test resumes it, and the final manifest equals (c).
5. Mark the test POSIX-only (rule 2).

### 3.2 CI runs the full suite (CI and test configuration only)

**Premises**

- `.github/workflows/backend-contracts.yml` is path-filtered.
- `pyproject.toml` has no `testpaths`.
- `examples/tmo_campaigns/test_order.py` launches SIESTA when imported.
- With `fetch-depth: 1`, `tools/check_v6_integrity.sh` cannot see tag `scientific-v6-final` and
  passes silently.

**Change**

1. **`pyproject.toml`.** Add `[tool.pytest.ini_options] testpaths = ["tests"]`.
2. **New `.github/workflows/ci.yml`.** On every push and PR, with no path filter:
   - checkout with `fetch-depth: 0` and tags;
   - Python 3.12;
   - `pip install -e ".[test]"` with the **exact** ruff and mypy versions you use locally, pinned in
     the workflow;
   - then `pytest tests`, ruff, `ruff format --check`, `MYPYPATH=src mypy`, the architecture test
     and `bash tools/check_v6_integrity.sh`.
   - Make the V6 script fail loudly if the tag is missing. That is a behavior change to the script
     only for the missing-tag case; log it.

   Keep `backend-contracts.yml` unchanged.
3. **Known failures.**
   - List them in `tests/known_failures.txt`: the baseline failing ids and the collection-error
     files, each with a reason.
   - `tests/conftest.py` adds the collection-error files to `collect_ignore`.
   - It marks a listed failure `xfail(strict=True)` **only when its reason is not a missing file, or
     when the missing file is absent.** Detect this with the path named in the reason. A test whose
     untracked data exists on the user's machine therefore runs normally there.
4. If the Hypothesis deadline flake recorded in the Phase 2 close log reappears, set
   `deadline=None` only for that test, and log it.
5. Add to AGENTS.md §2: "12. `tests/known_failures.txt` may only shrink."

**Acceptance**

- `pytest tests` with no flags is green in your environment and in WSL.
- The new workflow passes on the pushed branch (`gh run view` if available; otherwise ask the user
  to check).

### 3.3 Pass the profile environment explicitly instead of mutating `os.environ` **[execution]**

**Premises**

- `campaign_runner.py` ~L401: `os.environ.update(self.profile.runtime.environment)`.
- `LocalSubprocessExecutor.run()` (`runtime_adapters.py` ~L80) passes no `env=`, so SIESTA and
  mpirun get the profile variables only by inheriting the mutated environment.
- `scontrol` in `_slurm_hosts` (~L536) also inherits.
- `SlurmAllocationExecutor` uses `environment` only for validation (~L121-122).
- Every tracked profile has `runtime.environment == {}`. Check every tracked `*profile*.json`.
- Find every other reader of `os.environ` that could rely on the mutation after construction (grep
  `os.environ` / `getenv` across `src/`), and log them.

**Change**

1. Compute `self.environment = {**os.environ, **profile.runtime.environment}` at the same point.
2. Add an optional `env` parameter to `LocalSubprocessExecutor`, defaulting to the current
   behavior, and pass `self.environment` to it.
3. Pass `env=self.environment` to the `scontrol` call, and use it in
   `SlurmEnvironment.from_environ` and the Slurm executor validation.
4. Remove the `os.environ.update`.
5. If the grep finds another reader that depends on the mutation, stop the item and report it.

**Acceptance**

- A new test with a profile that sets one variable: the environment given to the subprocess (and to
  `scontrol`, mocked) contains it, and the process `os.environ` is unchanged afterwards.
- 3.1 is identical.

### 3.4 Extract the persistence store

**Scope** (verified): `_load_records`, `_save_records`, `_checkpoint`, `_record_receipt`,
`_archive_unvalidated_attempts`, `_archive_orphaned_attempts`.

Not in scope, and they stay in the runner:
- `_command_record`, which is execution: it needs the factory artifacts, validator provenance and
  adaptive digest;
- `_identity`, which depends on shadow, adaptive and dag. The store receives the identity mapping as
  an argument when saving.
- `_verify_record_artifacts`, which moves in 3.5.

**Change**

1. Create `execution/campaign_store.py` with a `CampaignStore` that holds the records path and the
   records.
2. The checkpoint manager is read through an accessor on every call, never stored (rule 6). The
   store is created after `shadow.install`, at ~L466 of `__init__`.
3. The runner keeps delegators with the old names.
4. `campaign_shadow.py` uses public runner methods `runner.checkpoint()` and `runner.save_records()`
   instead of `runner._checkpoint` / `runner._save_records`. The runner's `save_records()` computes
   `self._identity()` and calls the store. The shadow must not call `runner._identity()`.
5. `_record_receipt` keeps its exact two-step order: records, then checkpoint.

**Acceptance**

- All gates pass.
- A new test runs a real shadow expansion (`install` after construction) and then a store
  save/load. The checkpoint used is the post-install one.

### 3.5 Extract observation assembly (non-adaptive part only)

**Scope** (verified):
- runner methods: `_event_occupations`, `_event_trace_half_widths`, `_projector_fingerprint`,
  `_reference_node`, `_verified_observations`, `_response_observation_dataset`,
  `_verify_record_artifacts` (static);
- module functions: `_build_verified_dataset`, `_dataset_half_widths`, `_dataset_half_width`,
  `_source_record`.

Not in scope (adaptive-only): `_read_response_vector`, `_matching_response_node`, `_signal_vectors`.

**Change**

1. Create `execution/observation_assembly.py` with an `ObservationAssembler` and the module
   functions as public names.
2. `campaign_runner.py` keeps re-export aliases under the old private names and delegating methods.
   Existing tests that import `_build_verified_dataset` or monkeypatch instance methods then keep
   working; edit them under R5 only if they still break.
3. The assembler receives `dag`, `specs`, records and the checkpoint per call (rule 6).
4. `campaign_shadow.py` calls `runner.observations.verified_observations(...)` and
   `.response_observation_dataset(...)`.
5. **Architecture test.** If a moved function imports a private name from another module, do not
   add an allowlist entry. Either keep that function in the runner, or make the imported name
   public in its home module, keeping the old alias. Removing the now-stale entry is required.

**Acceptance**

- All gates pass.
- `grep "runner\._" src/hubbardflow/execution/campaign_shadow.py` returns nothing.
- A new test runs the **real** assembler (no stubs) after a runtime shadow expansion and checks
  that observations include the expanded nodes. The existing shadow tests stub these methods, so
  this gap is real.

---

## 2. Closing

Write `docs/fdebq/PHASE3_SUMMARY.md` with:
- one row per item: commit, premises, R5 edits, and conservative decisions;
- `campaign_runner.py` lines and method count before and after;
- the final failing set compared with the baseline, in your environment and in WSL;
- CI status.

Push the branch. No PR, no SIESTA (the replay uses recorded outputs).
