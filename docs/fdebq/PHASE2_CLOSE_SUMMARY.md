# Phase 2 close summary

Branch: `fdebq/r3-task20-fixes`, based on `origin/fdebq/r2-task15-species-split` at `84b8eb6`.
The copied task specification is 716 lines and contains `PLANNER_VERSION_CHANGED`, `D12`, and
`test_every_manifest_path_is_rejected_read_only`.

## Item results

| Item | Commit | Premises | Auditor verdict | Tests added / existing-test edits | Conservative decisions |
|---|---|---|---|---|---|
| 20.1 | `6163c4e` | P1–P4 TRUE | Not [science] | Added legacy-resume regression; 30 focused tests and 70 scientific regressions passed. No existing test edits. | Resume without frozen inventory uses legacy base validation; planned manifests stay strict. |
| 20.6 | `b9388f6` | P1–P5 TRUE | Not [science] | Added portable destination-path coverage; Windows focused 74 passed and POSIX-focused 13 passed. Edited only explicitly named `test_every_manifest_path_is_rejected_read_only`. | Protect V6 roots portably and fail closed when the baseline manifest cannot be verified. |
| 20.7 | `c4b0cb6` | P1 TRUE | Not [science] | Added parameterized coverage for ten product-only options on legacy run targets; 10 passed. No existing test edits. | Reject supplied product options before legacy dispatch. |
| 20.2 | `af08f4c` (blocker record) | P1–P5 TRUE | `RISK_UNCOVERED` | No implementation or test. | Stop because the managed-label rejection rule conflicts with acceptance for punctuation variants. |
| 20.3 | No implementation commit; prerequisite recorded with 20.2 | Not evaluated; 20.2 is blocked | Not reached | No implementation or test. | Do not define SCF ladder labels or reuse behavior before canonical-label semantics are resolved. |
| 20.4 | `1cdef7f` (blocker record) | P1–P4 TRUE | `RISK_UNCOVERED` | No implementation or test; existing `test_real_archive_label_only_difference_is_never_a_positive` was not changed. | Stop because acceptance requires the opposite verdict from the protected existing test. |
| 20.5 | `59318c6` (blocker record) | P1–P8 TRUE | `RISK_UNCOVERED` | No implementation or test; existing F8 test was not changed. | Stop because discrete exactness acceptance conflicts with an existing test, and symmetry search paths are not shown equivalent. |
| 20.8 | No implementation commit; prerequisite recorded with 20.5 | Not evaluated; prerequisites 20.2/20.3 are blocked | Not reached | No implementation or test. | Do not implement calibrated rounds before the ladder and translation semantics are resolved. |
| 20.9 | `665d6e1` (blocker record) | P1 TRUE | `RISK_UNCOVERED` | Prototype/test was removed; no tests or fixtures committed. | Do not mix archived FDFs with incompatible cells, sites, alpha grids, or projector methods. |
| 20.11 | `e1dcb21` (blocker record) | Not evaluated; prerequisite 20.5 blocked | Not reached | No implementation or test. | Do not introduce planner-v2 or a frozen digest without the required shadowed golden. |
| 20.10 | `656a1ba` (blocker record) | Not evaluated; prerequisite 20.5 blocked | Not reached | No implementation or test. | Do not move the optional `spglib` resolver or establish its architecture allowlist ahead of 20.5. |
| TASK 21 | `8e287bb` | P1–P8 TRUE | Not tagged [science]; no scientific method changed | Added admission truth-table tests and product execution identity/TOCTOU tests (11 admission cases, 3 execution cases). No existing test edits. | D12 admits only explicit fixed-grid direct plans. SIESTA numerical equivalence remains the user's CoO check; no SIESTA was run. |

No evaluated premise was false. The blocked items and their supporting evidence are detailed in
`PHASE2_CLOSE_LOG.md` and `BLOCKERS.md`. Pre-existing Ruff/mypy debt for `campaign_runner.py` and
`cli.py` is recorded for Phase 3; counts did not increase and no diagnostic lands on changed lines.

## Final complete-suite comparison

Baseline on `84b8eb6` with
`pytest tests -q -rfE --continue-on-collection-errors`:
`20 failed, 1234 passed, 24 skipped, 5 errors, 4 subtests passed`.

Final branch with the same command:
`20 failed, 1270 passed, 24 skipped, 5 errors, 4 subtests passed`.
The exact failing test IDs and collection-error IDs match the baseline; no new failures. The final
run has 36 additional passing tests.

The five collection errors in both runs are:

- `tests/adversarial/test_method2_reference.py` — `siestaflow_hubbard` is unavailable.
- `tests/adversarial/test_phase4_alpha0_control.py` — `siestaflow_hubbard` is unavailable.
- `tests/test_nio_polynomial_analysis.py` — historical `analyze_nio_lru_v3.py` is missing.
- `tests/test_nio_shared_lru_regression.py` — `lru_core` is unavailable.
- `tests/unit/test_stage_ub_baseline_summary.py` — `siestaflow_hubbard` is unavailable.

The 20 failing test IDs in both runs are:

- `tests/test_cli_and_manifest.py::test_cli_audit_fdf_reports_repository_nio_pbe_spin_and_dftu`
- `tests/unit/test_cu1_archived_occupation_v3.py::test_archived_cu1_occupations_v3_builds_verified_dataset_without_authorizing_u`
- `tests/unit/test_cu3n_symmetry_shadow_package.py::test_fdf_mutation_changes_only_the_declared_target_shift`
- `tests/unit/test_cu_one_atom_noise_calibrated_campaign.py::test_static_campaign_is_admitted_without_a_calibration_result`
- `tests/unit/test_cu_one_atom_noise_calibrated_campaign.py::test_lock_and_plan_strictly_separate_calibration_from_response_mesh`
- `tests/unit/test_cu_one_atom_noise_calibrated_campaign.py::test_fdf_hash_and_recorded_native_six_decimal_format_evidence_are_locked`
- `tests/unit/test_fdf_symmetry_adapter.py::test_real_campaign_fdf_parses_but_never_uses_initial_spin_as_evidence[NiO]`
- `tests/unit/test_fdf_symmetry_adapter.py::test_real_campaign_fdf_parses_but_never_uses_initial_spin_as_evidence[MnO]`
- `tests/unit/test_fdf_symmetry_adapter.py::test_real_campaign_fdf_parses_but_never_uses_initial_spin_as_evidence[FeO]`
- `tests/unit/test_fdf_symmetry_adapter.py::test_real_campaign_fdf_parses_but_never_uses_initial_spin_as_evidence[Cu3N]`
- `tests/unit/test_fdf_symmetry_adapter.py::test_evidence_must_bind_hash_and_cover_every_atom`
- `tests/unit/test_fdf_symmetry_adapter.py::test_missing_magnetic_evidence_materializes_explicit_site_neutral_plan`
- `tests/unit/test_hubbard_parameter_semantics.py::test_scalar_charge_result_cannot_feed_dudarev_input`
- `tests/unit/test_hubbard_parameter_semantics.py::test_physical_fdf_replaces_the_saved_u_entry_with_explicit_ueff`
- `tests/unit/test_mno_foreground_preflight.py::test_mno_preflight_reuses_canonical_foreground_slurm_contract`
- `tests/unit/test_mno_independent_audit_regressions.py::test_screened_reanalysis_rejects_an_unconverged_trace`
- `tests/unit/test_mno_independent_audit_regressions.py::test_screened_reanalysis_rejects_an_explicit_nonconvergence`
- `tests/unit/test_mno_independent_audit_regressions.py::test_screened_reanalysis_rejects_a_population_block_after_completion`
- `tests/unit/test_mno_independent_audit_regressions.py::test_screened_reanalysis_keeps_archived_converged_values`
- `tests/unit/test_mno_independent_audit_regressions.py::test_quantized_analysis_declares_scalar_charge_and_keeps_estimate`

Final TASK 21 gates: focused product suite `85 passed`; scientific regressions `70 passed`; configured
Ruff, format check, and strict mypy green; V6 integrity `V6 GATE OK`.
