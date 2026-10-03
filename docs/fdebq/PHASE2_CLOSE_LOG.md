# Phase 2 close execution log

Base: `84b8eb6` (`origin/fdebq/r2-task15-species-split`). Branch: `fdebq/r3-task20-fixes`.

## §0.2 Baseline — BASELINE_FAILURES

The literal shell command `pytest tests -q -rfE` was attempted first but PowerShell reported that `pytest` is not recognized. Retried the same requested test invocation using the project venv executable:

- Command: `& 'C:\Users\Jairo\work\fdebq_venv\Scripts\pytest.exe' tests -q -rfE`
- Result: exit 1; collection interrupted before test execution; 5 collection errors, 2 warnings, 4.86s.
- Exact failing collection IDs:
  - `tests/adversarial/test_method2_reference.py` — `ModuleNotFoundError: No module named 'siestaflow_hubbard'` via `scratch/phase4_method2_revalidation.py`.
  - `tests/adversarial/test_phase4_alpha0_control.py` — same legacy namespace import.
  - `tests/test_nio_polynomial_analysis.py` — `FileNotFoundError` for `campaigns/nio_afmii_four_atom_lru_v2_20260926/scripts/analyze_nio_lru_v3.py`.
  - `tests/test_nio_shared_lru_regression.py` — `ModuleNotFoundError: No module named 'lru_core'`.
  - `tests/unit/test_stage_ub_baseline_summary.py` — `ModuleNotFoundError: No module named 'siestaflow_hubbard'`.
- No test failure IDs were produced because collection stopped.

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

## 20.1 checks and pre-existing-file static comparison

- Focused tests: venv `pytest.exe tests/unit/test_campaign_runner_legacy_resume.py tests/unit/test_campaign_runner_synthetic.py tests/unit/test_campaign_runner_execution_identity.py tests/unit/test_campaign_plan.py -q` → `30 passed`.
- Scientific regression gate: venv `pytest.exe tests/unit/test_lr_analysis_v2.py tests/unit/test_matrix_lr.py tests/unit/test_quantized_response.py tests/unit/test_u_certification.py -q` → `70 passed`.
- Configured static files plus the new test: `ruff check . tests/unit/test_campaign_runner_legacy_resume.py` → `All checks passed!`; `ruff format --check . tests/unit/test_campaign_runner_legacy_resume.py` → `86 files already formatted`; `MYPYPATH=src mypy --strict` → `Success: no issues found in 85 source files`; additionally `MYPYPATH=src mypy --strict tests/unit/test_campaign_runner_legacy_resume.py` → `Success: no issues found in 1 source file`.
- V6: `bash tools/check_v6_integrity.sh` → `V6 GATE OK`.
- `campaign_runner.py` is outside pyproject's configured file lists. Per the user's static-check rule, comparison at `84b8eb6` vs working tree: Ruff violations `23 → 23`; Ruff format would-reformat file count `1 → 1`; strict mypy errors `24 → 24`. The current Ruff JSON has no diagnostics on the changed helper lines. No pre-existing violation count increased, and none is on a changed line.
