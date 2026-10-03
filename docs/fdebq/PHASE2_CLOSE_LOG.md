# Phase 2 close execution log

Base: `84b8eb6` (`origin/fdebq/r2-task15-species-split`). Branch: `fdebq/r3-task20-fixes`.

## §0.2 Baseline — BASELINE_FAILURES (corrected run)

- Revision: clean detached worktree at `84b8eb6741442dbbcd2f860d89212cefc2e07f3b`.
- Import check: `hubbardflow.__file__` resolved to `C:\Users\Jairo\AppData\Local\Temp\hubbardflow-baseline-84b8eb6\src\hubbardflow\__init__.py`.
- Command: `PYTHONPATH=C:\Users\Jairo\AppData\Local\Temp\hubbardflow-baseline-84b8eb6\src pytest tests -q -rfE --continue-on-collection-errors` using `C:\Users\Jairo\work\fdebq_venv\Scripts\pytest.exe`.
- Result: `20 failed, 1234 passed, 24 skipped, 2 warnings, 5 errors, 4 subtests passed in 295.59s`.
- Exact collection errors:
  - `tests/adversarial/test_method2_reference.py` — `ModuleNotFoundError: siestaflow_hubbard`.
  - `tests/adversarial/test_phase4_alpha0_control.py` — `ModuleNotFoundError: siestaflow_hubbard`.
  - `tests/test_nio_polynomial_analysis.py` — missing `campaigns/nio_afmii_four_atom_lru_v2_20260926/scripts/analyze_nio_lru_v3.py`.
  - `tests/test_nio_shared_lru_regression.py` — `ModuleNotFoundError: lru_core`.
  - `tests/unit/test_stage_ub_baseline_summary.py` — `ModuleNotFoundError: siestaflow_hubbard`.
- Exact failing test IDs:
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
- The first worktree attempt imported the active checkout because the installed editable path preceded the worktree source. It is discarded; only the corrected run above defines `BASELINE_FAILURES`.

§0.2.5 campaign-marker check:

- Command: Python `Path.rglob('*')` over `C:\Users\Jairo\work\hubbardflow` and `C:\Users\Jairo\work`, excluding `.git`, `tests`, `tmp`, `temp`, `__pycache__`, `.venv`, and `venv`, checking exact basenames `campaign.lock` and `resolved_perturbation_plan.json`.
- Output: `NO_PHASE2_CAMPAIGN_MARKERS_FOUND`.
- D11's no-campaign assumption is verified in this search scope.

## Item premise checks

| Item / premise | Result | Command and evidence |
|---|---|---|
| 20.1/P1 | TRUE | `rg -n "campaign_inventory|validate_lr_config" src/hubbardflow/execution/campaign_runner.py`; lines 385–386 call both, passing `inventory=`. |
| 20.1/P2 | TRUE | `git grep -n "parse_effective_fdf" b2b65ca -- src/hubbardflow/execution/campaign_runner.py`; no matches. `git show b2b65ca:src/hubbardflow/execution/campaign_runner.py` shows resume calling `validate_lr_config` without an inventory, and no strict parser call. |
| 20.1/P3 | TRUE | Venv Python probe passed an FDF containing `%block LatticeParameters` to both APIs: `validate_reference_fdf` returned `PBE`; `parse_effective_fdf` raised `FdfModelError: LatticeParameters is unsupported; use LatticeConstant and LatticeVectors`. |
| 20.1/P4 | TRUE | `rg -n "resolved_plan|freeze_campaign_plan" src/hubbardflow/execution/wsl_campaign_init.py`; current `initialize_campaign` assigns `planning.plan`, calls `freeze_campaign_plan`, and writes `resolved_perturbation_plan.json` into the manifest. |
| 20.6/P1 | TRUE | `Get-Content src/hubbardflow/execution/product_paths.py`; line 15 hardcodes `Path(__file__).resolve().parents[3]` as `WORKSPACE`. |
| 20.6/P2 | TRUE | WSL Linux probe with `PYTHONPATH=src` imported `protect_product_destination`; `Validation_Observables_V6/x`, `benchmarks/LR_U`, `results/Stage-UB-V6-Observables`, and `FINAL_SIESTA_VALIDATION_REPORT_v6.md` all printed `ALLOWED`. The existing `is_relative_to` comparisons are component/case-sensitive on POSIX. |
| 20.6/P3 | TRUE | `Get-Content tools/hubbardflow_plan_diagnose.py` lines 223–224 shows direct `args.json.write_text(...)` and `args.markdown.write_text(...)` without destination protection. |
| 20.6/P4 | TRUE | `Get-Content src/hubbardflow/execution/product_paths.py` lines 45–49 checks `Path(relative).drive`; the WSL Linux probe printed an empty `Path("C:/outside").drive`. |
| 20.6/P5 | TRUE | `rg -n 'setattr\(product_paths, "WORKSPACE"' tests/unit/test_product_paths.py` found four callers at lines 64, 78, 90, 99; the `test_missing_manifest_fails_closed` test is among them. |
| 20.7/P1 | TRUE | `rg`/`Get-Content` showed `cli.py` attaches `add_product_options` to every `run`. Venv Python probe made a schema-valid v2 manifest, mocked `run_campaign_worker`, ran `cli.main(["run", manifest, "--output-dir", ignored])`; output was `exit: 17` and one worker call with mode `run`. |

## 20.7 checks

- Implemented rejection before legacy dispatch: a non-`.fdf` `run` with any of the ten product options exits 2 and names every supplied option. The new parametrized test covers each option individually; focused result: `10 passed`.
- `cli.py` is outside `pyproject.toml`'s Ruff/mypy file lists. Before/after diagnostics: Ruff `2 → 2` (both pre-existing I001 import-order reports at lines 17 and 173); strict mypy `7 → 7` (pre-existing diagnostics at lines 157, 180, 183, 186, 204, 207, 208). No diagnostic is on the changed lines. No whole-file formatting or cleanup was done.
- Configured checks plus new test: Ruff passed; format check reported `88 files already formatted`; configured strict mypy reported `Success: no issues found in 87 source files`. The new test's strict mypy check requires `MYPYPATH=src` so it resolves the checkout rather than the installed package.

## 20.1 checks and pre-existing-file static comparison

- Focused tests: venv `pytest.exe tests/unit/test_campaign_runner_legacy_resume.py tests/unit/test_campaign_runner_synthetic.py tests/unit/test_campaign_runner_execution_identity.py tests/unit/test_campaign_plan.py -q` → `30 passed`.
- Scientific regression gate: venv `pytest.exe tests/unit/test_lr_analysis_v2.py tests/unit/test_matrix_lr.py tests/unit/test_quantized_response.py tests/unit/test_u_certification.py -q` → `70 passed`.
- Configured static files plus the new test: `ruff check . tests/unit/test_campaign_runner_legacy_resume.py` → `All checks passed!`; `ruff format --check . tests/unit/test_campaign_runner_legacy_resume.py` → `86 files already formatted`; `MYPYPATH=src mypy --strict` → `Success: no issues found in 85 source files`; additionally `MYPYPATH=src mypy --strict tests/unit/test_campaign_runner_legacy_resume.py` → `Success: no issues found in 1 source file`.
- V6: `bash tools/check_v6_integrity.sh` → `V6 GATE OK`.
- `campaign_runner.py` is outside pyproject's configured file lists. Per the user's static-check rule, comparison at `84b8eb6` vs working tree: Ruff violations `23 → 23`; Ruff format would-reformat file count `1 → 1`; strict mypy errors `24 → 24`. The current Ruff JSON has no diagnostics on the changed helper lines. No pre-existing violation count increased, and none is on a changed line.

## Current full-suite comparison after 20.1 and 20.6

- Command: `PYTHONPATH=C:\\Users\\Jairo\\work\\hubbardflow\\src pytest tests -q -rfE --continue-on-collection-errors` using the project venv `pytest.exe`; `hubbardflow.__file__` confirmed the current branch's `src/hubbardflow/__init__.py`.
- Result: `20 failed, 1246 passed, 24 skipped, 2 warnings, 5 errors, 4 subtests passed in 254.77s`.
- The 5 collection errors and all 20 failed IDs are exactly the same sets listed under `BASELINE_FAILURES`. No new failures. The current run includes 12 additional passing tests compared with baseline.
- 20.6 focused Windows suites: `74 passed`; POSIX-specific WSL command `pytest tests/unit/test_product_paths.py::test_manifest_traversal_fails_closed tests/unit/test_product_paths.py::test_missing_manifest_fails_closed tests/unit/test_product_paths_portable.py -q` → `13 passed`; a full WSL run on `/mnt/c` was interrupted after extended filesystem latency and is not counted.
- 70 scientific regressions: `70 passed`; configured Ruff + new files: `All checks passed`; configured format + new files: `90 files already formatted`; strict mypy on the three new test modules: `Success: no issues found in 3 source files`; V6: `V6 GATE OK`.
- Explicit test edit under the 20.6 exception: `tests/unit/test_product_paths.py::test_every_manifest_path_is_rejected_read_only` now passes `workspace` to `_frozen_files(workspace)` and its monkeypatch accepts the workspace argument.
