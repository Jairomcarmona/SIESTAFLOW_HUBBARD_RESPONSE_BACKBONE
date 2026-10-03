# Phase 3 implementation log

## 3.0 Preconditions and baseline

- Part A report exists and records `IDENTICAL`: `docs/fdebq/REAL_VALIDATION_NIO_P5.md`.
- Part A complete-analysis recomputation from its observation dataset alone was
  not possible with the current boundary; see the fixture README and Part A
  report. Gate 2(a) is dropped as expressly allowed. The POSIX 3.1 replay is the
  end-to-end golden.
- Premise check: `rg -n 'CampaignRunner\\(' tests` returned no matches; tests do
  not construct `CampaignRunner(manifest)` end to end.
- Both full-suite baselines used
  `python -m pytest tests --continue-on-collection-errors -q` at the Part A tip
  plus the 3.0 task-document commit. No production code changed after the Part
  A commit.

| Environment | Result |
|---|---|
| Windows Python 3.12 | 1350 passed, 24 skipped, 20 failed, 5 collection errors, 4 subtests passed (suite elapsed 287.99 s) |
| WSL Python 3.12 | 1354 passed, 20 skipped, 20 failed, 5 collection errors, 4 subtests passed (suite elapsed 592.35 s) |

Both environments reported the same 20 failing test IDs:

```text
tests/test_cli_and_manifest.py::test_cli_audit_fdf_reports_repository_nio_pbe_spin_and_dftu
tests/unit/test_cu1_archived_occupation_v3.py::test_archived_cu1_occupations_v3_builds_verified_dataset_without_authorizing_u
tests/unit/test_cu3n_symmetry_shadow_package.py::test_fdf_mutation_changes_only_the_declared_target_shift
tests/unit/test_cu_one_atom_noise_calibrated_campaign.py::test_static_campaign_is_admitted_without_a_calibration_result
tests/unit/test_cu_one_atom_noise_calibrated_campaign.py::test_lock_and_plan_strictly_separate_calibration_from_response_mesh
tests/unit/test_cu_one_atom_noise_calibrated_campaign.py::test_fdf_hash_and_recorded_native_six_decimal_format_evidence_are_locked
tests/unit/test_fdf_symmetry_adapter.py::test_real_campaign_fdf_parses_but_never_uses_initial_spin_as_evidence[NiO]
tests/unit/test_fdf_symmetry_adapter.py::test_real_campaign_fdf_parses_but_never_uses_initial_spin_as_evidence[MnO]
tests/unit/test_fdf_symmetry_adapter.py::test_real_campaign_fdf_parses_but_never_uses_initial_spin_as_evidence[FeO]
tests/unit/test_fdf_symmetry_adapter.py::test_real_campaign_fdf_parses_but_never_uses_initial_spin_as_evidence[Cu3N]
tests/unit/test_fdf_symmetry_adapter.py::test_evidence_must_bind_hash_and_cover_every_atom
tests/unit/test_fdf_symmetry_adapter.py::test_missing_magnetic_evidence_materializes_explicit_site_neutral_plan
tests/unit/test_hubbard_parameter_semantics.py::test_scalar_charge_result_cannot_feed_dudarev_input
tests/unit/test_hubbard_parameter_semantics.py::test_physical_fdf_replaces_the_saved_u_entry_with_explicit_ueff
tests/unit/test_mno_foreground_preflight.py::test_mno_preflight_reuses_canonical_foreground_slurm_contract
tests/unit/test_mno_independent_audit_regressions.py::test_screened_reanalysis_rejects_an_unconverged_trace
tests/unit/test_mno_independent_audit_regressions.py::test_screened_reanalysis_rejects_an_explicit_nonconvergence
tests/unit/test_mno_independent_audit_regressions.py::test_screened_reanalysis_rejects_a_population_block_after_completion
tests/unit/test_mno_independent_audit_regressions.py::test_screened_reanalysis_keeps_archived_converged_values
tests/unit/test_mno_independent_audit_regressions.py::test_quantized_analysis_declares_scalar_charge_and_keeps_estimate
```

Both environments reported these five collection-error files:

```text
tests/adversarial/test_method2_reference.py
tests/adversarial/test_phase4_alpha0_control.py
tests/test_nio_polynomial_analysis.py
tests/test_nio_shared_lru_regression.py
tests/unit/test_stage_ub_baseline_summary.py
```

The collection failures are historical namespace or fixture issues: missing
`siestaflow_hubbard` / `lru_core`, or absent NiO campaign script data. The
remaining failure causes include absent archived campaign files, missing
`LOCKS.sha256`, and tests importing the retired `siestaflow_hubbard` namespace.
These are the baseline only; R5 may document/skip them as allowed by task 3.2,
but will not change their assertions or product behavior.

The Part A fixture files and detached campaign remain unmodified during Phase
3. SIESTA will not be invoked in Part B; the replay uses recorded outputs.

## 3.1 End-to-end replay test

- The premise held: no `CampaignRunner(manifest)` construction existed in
  tests. The test initializes with `initialize_campaign`, Part A verified
  NiO inputs, a test-written local WSL profile and a route-rewritten test
  configuration. Its compatibility registry admits the replay executable by
  its SHA256 and the SIESTA 5.4.2 scientific profile. It does not bypass
  admission.
- Captured files are only materialized input FDFs (used as SHA keys), the
  corresponding SIESTA stdout, and each run's DM. The reference and 24
  response run files are xz-compressed in
  `tests/fixtures/replay_nio_p5/`; compressed stdout+DM payloads total 30.3 MB.
- The replay script requests stop on its 13th call. The first worker returns
  `STOPPED` with at least 13 validated nodes; `resume` then validates all 27
  DAG nodes (reference, 24 responses, alpha diagnostic, matrix analysis).
- Against Part A, all numerical fields, occupations and U values compare
  equal after these exact fields/categories are removed:

  | Exact JSON path | Category |
  |---|---|
  | `$.campaign.campaign_id` | campaign identity |
  | `$.campaign.name` | campaign identity |
  | `$.provenance.campaign_inputs.input_identity` | campaign identity |
  | `$.provenance.campaign_inputs.declared_inputs.campaign_contract.sha256` | campaign-bound input hash |
  | `$.provenance.campaign_inputs.declared_inputs.execution_profile.sha256` | profile/path-bound input hash |
  | `$.provenance.campaign_inputs.declared_inputs.lr_config.sha256` | route/path-bound input hash |
  | `$.provenance.campaign_inputs.analysis_implementation.package_version` | runtime binding |
  | `$.provenance.campaign_inputs.siesta_runtime.runtime_executable` | runtime binding |
  | `$.response_observation_dataset.reference_source.evidence_digest` | runtime evidence digest |
  | `$.response_observation_dataset.rows[i].sources.{bare,screened}.evidence_digest`, `i = 0…11` | runtime evidence digests, 24 entries |

  Attempt-directory identifiers inside source paths are normalized to
  `ATTEMPT-GROUP`, `attempt-NORMALIZED`, and `ATTEMPT-SUFFIX`. No DM-derived
  hashes were removed: Part A and replay DMs match exactly. The standalone
  comparator also asserts exact equality of every `primary.U_by_site_eV`.
- The final campaign's persisted files match the frozen 3.1 manifest in
  `tests/fixtures/replay_nio_p5/campaign_manifest.sha256.json`; 220 files are
  covered. The manifest canonicalizes attempt IDs, fixed test timestamps,
  temporary campaign-root strings and runtime/receipt identity metadata so
  the filesystem-rooted fixture remains reproducible.
- The campaign-file manifest normalizes only attempt IDs, the temp-root
  binding, and the runtime-dependent input/evidence hashes embedded in the
  generated Markdown report. The report's scientific values and source hashes
  remain covered. The golden was frozen after this normalization; two
  independent POSIX replay runs matched it, then a third verification run also
  passed (`1 passed`, 11.32–12.00 seconds). Windows uses the declared skip
  because `fcntl` and executable scripts require POSIX.
- The fixture tree is 30,311,362 bytes including scripts and manifests; the
  compressed stdout and DM payloads are 30.3 MB.

## 3.2 CI and baseline known failures

- Rechecked premises before editing: `backend-contracts.yml` has path filters
  on both push and pull requests; `pyproject.toml` had no pytest settings;
  importing `examples/tmo_campaigns/test_order.py` writes an FDF and invokes
  SIESTA at module scope; and `check_v6_integrity.sh` had no required-tag
  check. Added a full `ci.yml` workflow with checkout depth 0, Python 3.12,
  Ruff 0.16.10, mypy 2.4.0, the full test suite, lint/format/type/architecture
  checks and the V6 gate. `backend-contracts.yml` is unchanged. The V6 script
  now fails explicitly if `scientific-v6-final` is absent.
- The required-profile scan (`rg --files -g '*profile*.json'` plus JSON
  inspection) found empty runtime environments in every tracked execution
  profile; the production example contains only `<site-defined>` placeholders.
  The source scan for `os.environ`/`getenv` found the runner mutation and Slurm
  reads listed in item 3.3, plus `campaign_software_lock.py`'s PYTHONPATH
  prohibition. `verify_locked_software` has no call sites under `src/` or
  `tests/`, so that independent validator does not read the runner-mutated
  environment.
- The post-3.1 WSL full-suite run (`pytest tests --continue-on-collection-errors
  -q`) yielded 1,355 passed, 20 skipped, 20 failed, five collection errors and
  four subtests passed in 594.75 seconds. The 20 failure IDs match the recorded
  baseline exactly; only the pass count changed by one due to the new replay.
  The five collection errors were also the same baseline files. Their causes
  and the individual failed-test causes are captured in
  `tests/known_failures.txt`: absent archived files, missing `LOCKS.sha256`, or
  the retired `siestaflow_hubbard` / `lru_core` source trees.
- Added pytest test discovery rooted at `tests`, dynamic strict xfails only
  while each named missing path is absent, and `collect_ignore` entries for the
  five baseline collection errors. If a missing fixture returns, its test runs
  normally. Added AGENTS.md rule 12 requiring the known-failure list to shrink.
- The first post-commit acceptance attempt exposed that pytest resolves
  `collect_ignore` relative to `tests/`; after correcting those five paths,
  `pytest --collect-only -q tests` completed in Windows and WSL with 1,395
  collected and no collection errors. The baseline-failure subset then reported
  18 xfails, 11 passes and 13 skips; extant-fixture tests ran normally.
- Conservative decision: each xfail is tied to a concrete absent path found in
  the baseline traceback; collection errors are ignored by exact test-file
  path because their imports fail before pytest can collect individual tests.
