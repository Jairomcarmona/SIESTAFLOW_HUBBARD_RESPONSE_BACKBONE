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
