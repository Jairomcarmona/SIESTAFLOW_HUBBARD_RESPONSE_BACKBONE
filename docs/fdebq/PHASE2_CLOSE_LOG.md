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
| 20.2/P1 | TRUE (author-specified source) | Recursive local search found no SIESTA 5.4.2 manual PDF. Per item instruction, recorded the spec author's verification: manual p.19 says FDF labels are case insensitive and `-`, `_`, `.` are ignored. |
| 20.2/P2 | TRUE | `Get-Content src/hubbardflow/siesta_backend/fdf_model.py` lines 147–149 shows `_directives` uses `re.escape(key)` with `re.IGNORECASE`, which does not normalize punctuation. |
| 20.2/P3 | TRUE | Same source lines 161–182 casefolds block names, but does not remove punctuation. |
| 20.2/P4 | TRUE | `Get-Content src/hubbardflow/siesta_backend/coverage_reference.py` lines 34–47 uses literal regex labels `DFTU.PotentialShift` and `%block DFTU.proj`, case-insensitive only. |
| 20.2/P5 | TRUE | Temporary-file Python probe built a minimal parseable FDF per spelling and called `parse_effective_fdf`: `Spin_Orbit T`, `spin.orbit true`, `Non-Collinear-Spin T` each returned `spin_orbit=False, noncollinear=False`. |
| 20.4/P1 | TRUE | `Get-Content src/hubbardflow/siesta_backend/semantic_ion_identity.py`: `relabel_ion_bytes` replaces exactly one `<basis_specs>` header label and one value before `# Label`, preserves the width by padding, and raises `IonIdentityError` unless both audited fields are unique. `canonical_ion_bytes` calls it with sentinel `X`. |
| 20.4/P2 | TRUE | Read-only Python diff of the two named V6 `.ion` files: both exist, each has 8119 lines; unified diff changes only FeLR0/FeLR1 at lines 5 and 79. No frozen file was written. |
| 20.4/P3 | TRUE | Same read-only probe: raw SHA256 FeLR0=`da4c483af1ab2525ffa3818f37dff77e64944a11a98223afb69276f23b46b066`; FeLR1=`fe1760376a91af5a7c2b8af38e86551cb7008eddfed11eb286beeded98d1a541`. `split_generated_identity.py` adds `ION_BYTES_DIFFER` on raw digest inequality. |
| 20.4/P4 | TRUE | Read-only Python inspection: both files have `Fe # Symbol`; `FeLR0`/`FeLR1` occur before `# Label`; each `<pseudopotential_header>` contains one `Fe`. The header content is unchanged between pair files. |

## 20.2 pre-change FDF census

- Command: Python `Path.rglob('*.fdf')` over the repository, excluding `.git` and virtual environments, then `parse_effective_fdf` on every path. Result: `197` repository FDFs; `130` parse before 20.2.
- In the same census, `validate_reference_fdf(text, 'PBE')` accepted `40`; all `40` also parsed with the strict model (`LEGACY_AND_STRICT 40`, `LEGACY_NOT_STRICT` empty).
- The item asks for an independent scientific audit before any implementation. No 20.2 code has been changed.
- Auditor verdict: `RISK_UNCOVERED`, stop 20.2 before implementation. Evidence: the managed-label rule at §20.2.3 covers `ChemicalSpeciesLabel` because `fdf_builder.py` writes it and `fdf_model.py` reads it, so the punctuation variant must be rejected; §20.2 Acceptance also requires `Chemical_Species_Label` to be read. The specification does not define whether “read” means recognized before rejection or accepted as a block. No exception or scientific choice was inferred.
- 20.3 explicitly depends on 20.2's canonical-label behavior, so it cannot proceed until the author resolves this risk. Continue with the next independent item in §3.

## 20.4 disposition

- Do not implement: the required acceptance (`canonical_ion_bytes` equal and raw diff limited to relabel fields ⇒ `MATCH`) necessarily changes the outcome of the existing `tests/unit/test_split_generated_identity.py::test_real_archive_label_only_difference_is_never_a_positive`, whose asserted behavior is the opposite for canonical-equal alias ions. §20.4 lists only new tests; §0.1.5 prohibits editing this existing test unless the item explicitly names it. No production-code workaround can satisfy both requirements and the exact verdict rule. This is recorded as `RISK_UNCOVERED`; ask for an explicit specification/test-scope correction before 20.4.

## 20.5 premise checks

| Item / premise | Result | Command and evidence |
|---|---|---|
| 20.5/P1 | TRUE | `Get-Content src/hubbardflow/domain/symmetry_operation_models.py` lines 349–354: `exactness_class` is `EXACT_TRANSLATION` whenever `rotation_int == IDENTITY`, without checking ε, mapping, or mesh. |
| 20.5/P2 | TRUE | `Get-Content src/hubbardflow/domain/symmetry_operations.py` lines 136–145: F8 is exempted from the ambiguous exclusion for identity-rotation operations; the F8 classifier only records commensurability. |
| 20.5/P3 | TRUE | `rg -n 'EXACT_IN_CONTINUUM_ONLY|no conmensurables' docs/fdebq/HUBBARDFLOW_PERTURBATION_PLANNING_REVIEW.md` and §D.3 lines 145–154: noncommensurate translations are classified `EXACT_IN_CONTINUUM_ONLY` and require shadows/validation. |
| 20.5/P4 | TRUE | `Get-Content src/hubbardflow/domain/symmetry_operations.py` lines 50–57 builds positions from float `coordinates_fractional` modulo 1; lines 383–394 use `Fraction(str(t))`, mesh, and the in-band atom matching. |
| 20.5/P5 | TRUE | `Get-Content src/hubbardflow/domain/coverage.py` lines 192–199: `matching` is filtered in operation order and `maps.append((member, matching[0]))` selects its first entry. |
| 20.5/P6 | TRUE | Venv Python toy probe imported `_toy(4, nonpolarized=True)` and ran `qualify_coverage` with `allow_spin_flip=True`: `NONPOLARIZED True SPIN_FLIP_OPERATIONS 32`; first ε=−1 operation F7 status `AMBIGUOUS`; coverage remains explicit in computed columns. |
| 20.5/P7 | TRUE (conditional path, not available locally) | `Get-Content src/hubbardflow/domain/symmetry_operations.py` lines 65–82 dynamically imports optional `spglib`; `rg -n spglib pyproject.toml` produced no matches; `importlib.util.find_spec('spglib')` returned `None` here. No extra operation was observed locally. |
| 20.5/P8 | TRUE | Pure Python probe parsed the actual four-atom `campaigns/nio_pbe_adaptive_20260928/reference_pbe.fdf`, built a `SymmetryModel` and called `candidate_operations`: `CAMPAIGN_NIO_ATOMS 4 CANDIDATES 16`. `Operation.to_mapping` serializes `exactness_class`; campaign planner source declares `campaign-planner-v1`. §0.2.5 scan found no current campaign markers. |

### 20.5 disposition

- Auditor verdict: `RISK_UNCOVERED`; no implementation. The exactness correction matches review §D.3/F8, but the acceptance conflicts with existing test `tests/unit/test_symmetry_operations.py::test_f8_records_incommensurate_translation_without_excluding_candidate`, which expects `EXACT_TRANSLATION` for t=1/4 and mesh 3³; §20.5 does not authorize editing this test, so the requested behavior would add a failure.
- Auditor's pure geometry probe also showed that a valid metric-preserving rotation for lattice `((1,0,0),(1,1,0),(0,0,1))` lies outside the internal signed-axis-permutation enumeration. A simulated `spglib.get_symmetry` that returned that operation changed the candidate count 8→10. The auditor did not run real spglib (not installed here) and did not claim that spglib found this operation. The production equivalence of both search paths remains unverified.
- 20.8 depends on 20.3's v2 ladder protocol, which is blocked on 20.2; 20.10 and 20.11 also refer to 20.5 changes. Do not implement dependent items until their prerequisite risks are resolved; continue with independent items only.

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

## 20.9 premise and archive census

| Item / premise | Result | Command and evidence |
|---|---|---|
| 20.9/P1 | TRUE | `Get-Content tests/unit/test_campaign_plan.py` lines 300–331: `test_real_init_fixed_disabled_golden_and_resume` creates inputs via `inputs(...)`, retains the helper's synthetic default alpha grid, auto-fills `raw["sites"]` through `normalized(...)`, and compares `old_specs` from `_build_dag` to `new_specs` from the same function; there is no independent fixture. |

Archived source census (read-only): `examples/tmo_campaigns/run_tmo_campaign.py` defines CoO/NiO target element, 1-based atom index 1, grid `[-0.02,-0.01,0.00,0.01,0.02]`, and the `*_BARE_*.fdf` / `*_SCR_*.fdf` materialized files exist. `examples/tmo_campaigns/run_cu3n_campaign.py` defines Cu1, atom index 2, same grid and modes; corresponding `Cu3N_BARE_*.fdf` / `Cu3N_SCR_*.fdf` files exist. MnO v3r2 source is `campaigns/mno_afmii_strict_lr_v3r2/campaign-manifest.json` (representatives MnLR00/MnLR01; grid `[-.1,-.05,-.025,0,.025,.05,.1]`, BARE/SCREENED); materialized FDFs exist under `campaigns/mno_afmii_strict_lr_v3r2/results/response-matrix-foreground-recovery-v4/{A,B}_{BARE,SCREENED}_*/siesta.fdf`.

20.9 audit command: `pytest tests/unit/test_phase2_golden.py -q` on the temporary prototype returned four failures because explicit site inputs must enumerate every DFTU.Proj label. The prototype was removed after the provenance audit showed the candidate archives do not match those complete current plans. The `b2b65ca` worktree resolves to `b2b65caebf60d525e183917eef5a89356edfe758`.

## 20.9 disposition — RISK_UNCOVERED

P1 is TRUE, as recorded above. The read-only scientific audit found that the available CoO/NiO materialized FDFs under `examples/tmo_campaigns` do not belong to the modern CoO/NiO campaign inputs/configurations: the legacy templates are two-atom, one-site inputs with ±0.01/±0.02 eV, while modern references/configurations are four-atom, two-site inputs with ±0.02/±0.04/±0.06 eV. The legacy materialized FDFs also use projector method 1; current campaign initialization requires method 2. Direct `validate_reference_fdf(..., "PBE")` rejects both old templates, while it accepts the modern references. Pairing these hashes to modern initialized plans would violate the FDF/projector identity provenance rule; modifying their XC or projector method would fabricate an input. The audit verdict is `RISK_UNCOVERED` for such a mixed golden.

No compatible complete archived run-FDF chain was established for Cu3N or MnO v3r2 either: the available Cu3N campaign FDFs derive from the old four-atom `Cu1` workflow while the candidate current fixture is a 32-atom, 24-site model; the MnO run archive materializes only representatives A/B while the valid reference FDF declares 16 projector sites. A direct inventory probe confirmed 16 Mn subspaces. Therefore the available files cannot supply the requested hashes for the current explicit all-site plans without inventing or mismatching runs. The generator/test prototype was removed; no implementation or fixture was committed. Need an author-designated compatible archived input/materialization set (or explicit permission to narrow the comparison contract) to resume 20.9.

## 20.11 disposition — prerequisite blocked

No premises were evaluated for implementation because its required golden includes the `TRANSLATION_SHADOWED` plan whose semantics/version bump belong to 20.5, stopped as `RISK_UNCOVERED`. D11's no-migration behavior remains recorded; no `campaign-planner-v2` digest or version-change code was introduced.

## 20.10 disposition — prerequisite blocked

No premises were evaluated for implementation because acceptance item 2 requires the optional `spglib` import to be removed by 20.5 and checks updated module layering after that change. The 20.5 audit stopped before implementation; no import resolver was moved and no architecture allowlist/test was authored ahead of that prerequisite.

## TASK 21 premise checks

| Premise | Result | Command and evidence |
|---|---|---|
| P1 | TRUE | `Get-Content src/hubbardflow/execution/product_plan.py` around `product_execution_boundary` (lines 358–374): its reasons begin unconditionally with `SCIENTIFIC_STATE_NOT_ESTABLISHED` and `PILOT_REUSE_NOT_ESTABLISHED`, regardless of coverage/reduction/grid. |
| P2 | TRUE | Python probe called `resolve_campaign_planning` on a valid synthetic fixed-grid input with no reference output or parent DM: status `NOT_ESTABLISHED`; reasons `DISABLED_OR_FIXED`, `PARENT_DM_NOT_ESTABLISHED`, `REFERENCE_NOT_ADMISSIBLE`. |
| P3 | TRUE | Python probe called legacy `_build_dag` with two explicit amplitudes and found the `('reference', 'REFERENCE')` node. |
| P4 | TRUE | Python `inspect.signature` showed public `run_campaign_worker(manifest_path, mode) -> int` and `initialize_campaign(*, fdf_path, lr_config_path, profile_path, name, pointer_path=None, campaign_root=None) -> dict[str, Any]`; CLI source calls the worker for the legacy run branch. |
| P5 | TRUE | Python validation probe loaded the versioned adaptive policy from `benchmarks/lr_u/CoO/lr-config.json`, applied it to a valid fixed-grid input and normalized successfully with `alpha_strategy=FIXED_PROTOCOL_GRID` and an adaptive policy present. |
| P6 | TRUE | `freeze_product_snapshot` in `product_plan.py` writes only `product_plan.json`, `product_campaign.lock`, and `resolved_perturbation_plan.json`; it does not freeze lr-config bytes. `product_cli.py` merges `--reference-output`/`--reference-dm` into the request before planning. |
| P7 | TRUE | `rg -n "sbatch" src/hubbardflow/execution/campaign_runner.py` returned no matches; the campaign runner launches tasks within its current execution environment. |
| P8 | TRUE (none) | `rg -n "FakeSiesta|fake_siesta|fake-SIESTA|fake.*SIESTA|run_campaign_worker|CampaignRunner\\(" tests/unit` found only two tests monkeypatching/forbidding `run_campaign_worker`; no end-to-end fake-SIESTA legacy-runner harness exists. |

Pre-change static baseline for pre-existing `src/hubbardflow/cli.py` (outside pyproject's configured file lists): `ruff check --output-format=json` → 2 diagnostics; `mypy --strict src/hubbardflow/cli.py` → 7 errors. No formatting pass was run on this file.

## TASK 21 implementation and gates

- Implemented a pure admission predicate for fixed, explicit, direct legacy-equivalent plans. Coverage remains recorded as `DISABLED` or `DIAGNOSTIC`; reduced, adaptive, split, and optional-symmetry plans remain blocked by their existing requirements.
- Product snapshots now freeze the merged path-resolved lr-config and SHA256 map of the FDF, recursive includes, referenced outputs/DM, pseudopotentials, static artifacts, registry/version, and planning references. The frozen config's grid is sorted to preserve the existing order-invariant plan identity.
- Linux `run system.fdf --profile P --name N [--campaign-root R]` initializes using the frozen config, checks copied source/profile hashes and campaign inventory, compares canonical run-spec sets in JSON, creates an exclusive `execution_link.json`, and invokes the legacy worker. Existing links direct users to resume. Windows returns a WSL requirement; no-profile run remains receipt-only; `submit` is unchanged.
- No SIESTA executable or SIESTA campaign was run. The new integration test replaces `run_campaign_worker` with a test double and checks initialization/materialized FDF identity only.
- Focused product suite: `python -m pytest tests/unit/test_product_cli.py tests/unit/test_product_paths.py tests/unit/test_product_paths_portable.py tests/unit/test_product_admission.py tests/unit/test_product_execution.py -q` → `85 passed, 2 warnings`; includes FDF and pseudopotential TOCTOU mutations that stop before the worker.
- Scientific regression suite: `python -m pytest tests/unit/test_lr_analysis_v2.py tests/unit/test_matrix_lr.py tests/unit/test_quantized_response.py tests/unit/test_u_certification.py -q` → `70 passed, 2 warnings`.
- Configured static gates: Ruff `All checks passed`; format `90 files already formatted`; `mypy --strict` `Success: no issues found in 90 source files`.
- Pre-existing `src/hubbardflow/cli.py` static comparison: Ruff `2 → 2` and strict mypy `7 → 7`; no diagnostics on the added argument lines. It was not reformatted; phase-3 debt is recorded in `BLOCKERS.md`.
- V6: `bash tools/check_v6_integrity.sh` → `V6 GATE OK`.

## Final complete-suite comparison

- Command: `.venv/Scripts/pytest.exe tests -q -rfE --continue-on-collection-errors`; import check resolved `hubbardflow.__file__` to this checkout's `src/hubbardflow/__init__.py`.
- Result: `20 failed, 1270 passed, 24 skipped, 2 warnings, 5 errors, 4 subtests passed in 355.78s`.
- The five collection errors are exactly the five IDs recorded in `BASELINE_FAILURES`. The 20 failing test IDs are also exactly the same 20 IDs recorded there. No new failing test or collection error; there are 36 more passing tests than the corrected baseline.
- The five collection errors: adversarial `test_method2_reference.py` and `test_phase4_alpha0_control.py` (`siestaflow_hubbard` absent); `test_nio_polynomial_analysis.py` (historical analyzer missing); `test_nio_shared_lru_regression.py` (`lru_core` absent); and `test_stage_ub_baseline_summary.py` (`siestaflow_hubbard` absent).
- All 20 failure IDs are enumerated in the corrected §0.2 `BASELINE_FAILURES` list above; the current pytest short summary reproduced that exact list.

## Reopened phase-close work — author resolutions R1–R4

The author resolutions were committed first as `e4d9029`. The existing `BASELINE_FAILURES` from
the corrected `84b8eb6` run remains the comparison set; every complete run below uses
`pytest tests -q -rfE --continue-on-collection-errors`.

### 20.2 premise checks after R1

| Premise | Result | Command and evidence |
|---|---|---|
| 20.2/P1 | TRUE | Official SIESTA 5.4 reference lookup (`web.search_query` for the FDF label rule, then `web.open` on `https://docs.siesta-project.org/projects/siesta/en/5.4/reference/siesta.html`): labels are case insensitive and `-`, `_`, `.` are ignored. This agrees with R1's recognized-then-reject meaning. |
| 20.2/P2 | TRUE | `rg -n -C 2 '_directives|re.escape\(key\)' src/hubbardflow/siesta_backend/fdf_model.py` → `_directives` builds `re.escape(key)` with `re.IGNORECASE`; punctuation remains literal. |
| 20.2/P3 | TRUE | `rg -n -C 2 'active_name|casefold\(\)|re.fullmatch' src/hubbardflow/siesta_backend/fdf_model.py` → block labels are indexed with `casefold()` and name-specific lookups use escaped literal names. |
| 20.2/P4 | TRUE | `Get-Content src/hubbardflow/siesta_backend/coverage_reference.py -TotalCount 65` → literal regexes for `DFTU.PotentialShift` and `%block DFTU.proj`, only `re.IGNORECASE`. |
| 20.2/P5 | TRUE | Temporary valid fixture from `tests/unit/test_fdf_model.py::_fdf()` plus each of `Spin_Orbit T`, `spin.orbit true`, `Non-Collinear-Spin T` printed `spin_orbit=False, noncollinear=False` with current `parse_effective_fdf`. |

20.2 FDF census before implementation: `Path.rglob('*.fdf')`, excluding `.git`, Python virtual environments, and `__pycache__`, found `197`; current `parse_effective_fdf` accepted `130`, rejected `67` (first failures were legacy `DFTU.Proj record shape is unsupported`). Directive census command counted `SCF.DM.Tolerance=66`, `DM.Tolerance=12`, `SCF.H.Tolerance=66` across the same FDF files.

Managed labels recorded from `fdf_builder.py`, `fdf_model.py`, `coverage_reference.py`,
`scf_ladder_inputs.py`, the SIESTA profile, `symmetry_materializer.py`, `fdf_validator.py`, and
spin/DFTU readers (comparison preserves each spelling, case insensitive):

- Directives: `AtomicCoordinatesFormat`, `DFTU.FirstIteration`, `DFTU.Method`,
  `DFTU.PotentialShift`, `DFTU.ProjectorGenerationMethod`, `DM.Tolerance`, `DM.UseSaveDM`,
  `File.DM.Init`, `LatticeConstant`, `LatticeParameters`, `MaxSCFIterations`, `MeshCutoff`,
  `MD.NumCGsteps`, `MD.TypeOfRun`, `NonCollinearSpin`, `NumberOfAtoms`, `NumberOfSpecies`,
  `PAO.BasisSize`, `PAO.BasisType`, `SCF.Mix`, `SCF.Mixer.Method`, `SCF.Mixer.Weight`,
  `SCF.Mixer.History`, `SCF.MustConverge`, `SCF.DM.Converge`, `SCF.H.Converge`,
  `SCF.DM.Tolerance`, `SCF.H.Tolerance`, `Spin`, `SpinOrbit`, `SpinPolarized`, `SystemLabel`,
  `kgrid_cutoff`.
- Blocks: `AtomicCoordinatesAndAtomicSpecies`, `ChemicalSpeciesLabel`, `DFTU.proj`, `LDAU.proj`,
  `DM.InitSpin`, `LatticeParameters`, `LatticeVectors`, `PAO.Basis`,
  `kgrid_Monkhorst_Pack`.
- `LongOutput` is not managed: `rg -n 'LongOutput|Long_Output|Long\\.Output|Long-Output' src/hubbardflow tools -g '*.py'` returned no matches. The pre-change generic `_one('Long_Output true', 'LongOutput')` probe returned `None`; the positive punctuation-recognition test uses this unmanaged label and asserts the value is read.

Independent `auditor_cientifico` pre-implementation verdict: `RISK_COVERED` under R1. The audit
requires duplicate canonical labels to fail before managed-spelling rejection, never normalize
inside block payloads as directives, preserve exact echo-FDF comparison in
`coverage_reference._canonical`, and stop if any of the 130 pre-accepted FDFs becomes rejected.

20.2 implementation and gates: `fdf_labels.py` supplies canonical FDF identity and the recorded
managed set; `fdf_model.py` canonicalizes directive/block lookup, reports managed spelling
violations as `NONCANONICAL_MANAGED_LABEL`, and rejects canonical duplicates before spelling
validation. `coverage_reference._canonical` remains unchanged. The positive read case is unmanaged
`Long_Output`/`LongOutput`. Read-only baseline/current comparison command loaded
`8e99fe6:src/hubbardflow/siesta_backend/fdf_model.py` via `git show` and parsed the same 197 FDFs:
`PRE_ACCEPTED=130 POST_ACCEPTED=130 NEWLY_REJECTED=[] NEWLY_ACCEPTED=[]`. All 40 FDFs accepted by
`validate_reference_fdf(..., "PBE")` still parse.

- Focused tests: `.venv/Scripts/python.exe -m pytest tests/unit/test_fdf_labels.py tests/unit/test_fdf_model.py tests/unit/test_scf_ladder_inputs.py tests/unit/test_coverage_features.py tests/unit/test_coverage.py -q` → `107 passed, 2 warnings`.
- 70 scientific regressions → `70 passed, 2 warnings`.
- Configured static gates → Ruff `All checks passed`; format `90 files already formatted`; mypy `Success: no issues found in 90 source files`. Explicit new-file/test static gates also passed (Ruff clean, 5 formatted, mypy 2 files clean).
- V6: `bash tools/check_v6_integrity.sh` → `V6 GATE OK`.

Additional 20.2 validation evidence: official 5.4 docs give the FDF equivalence example
`LatticeConstant` / `lattice_constant`; on the current strict parser,
`_one('Long_Output true', 'LongOutput')` returned `None`. Pre-change
`rg -n 'LongOutput|Long_Output|Long\.Output|Long-Output' src/hubbardflow tools -g '*.py'`
returned no matches. The `Long_Output`/`LongOutput` pair is therefore the positive unmanaged-label
read case; it does not add a HubbardFlow scientific field.

P3 nuance checked against the official SIESTA 5.4 convergence reference, lines 3286–3313: newer
`SCF.DM.Tolerance` has precedence over the older DM-prefixed option, while the legacy
`DM.Tolerance` supplies its actual default. This reading matches the premise quote.

Punctuation-sensitive legacy paths recorded for Phase 3: `fdf_builder.py` uses literal regexes for
`DFTU.proj`, `LDAU.proj`, `ChemicalSpeciesLabel`, `AtomicCoordinatesAndAtomicSpecies`, and
`DM.InitSpin`; `coverage_reference._perturbed` matches `DFTU.PotentialShift` and `DFTU.proj`
literally; `reference_magnetic_evidence._is_explicitly_nonpolarized` matches literal `Spin
non-polarized`; and `campaign_v2.validate_reference_fdf`/`fdf_validator.py` use their current
legacy regex spellings. These validators remain untouched by 20.2.

### 20.3 premise checks (before implementation)

| Premise | Result | Command and evidence |
|---|---|---|
| 20.3/P1 | TRUE | `rg -n -i -C 3 'DM\.Tolerance ladder|same inputs|E\.2|factor|parent.*reference|reference.*level' docs/fdebq/CODEX_TASKS_PHASE2.md docs/fdebq/HUBBARDFLOW_FDRC_INDEPENDENT_REVIEW.md` → TASK 17 calls for “DM.Tolerance ladder, same inputs”; review §E.2 calls for DM and H tolerances tightened together and a same-level parent reference. |
| 20.3/P2 | TRUE | `Get-Content tools/fdebq_scf_ladder_campaign.py | Select-Object -Skip 90 -First 60` → materializer removes only `DM.Tolerance` and appends that spelling. |
| 20.3/P3 | TRUE | Official SIESTA 5.4 manual, `https://docs.siesta-project.org/projects/siesta/en/5.4/reference/siesta.html`, §Convergence criteria lines 3288–3313: newer `SCF.DM.*` flags have precedence; `DM.Tolerance` is the default for `SCF.DM.Tolerance`. |
| 20.3/P4 | TRUE | `$files = rg --no-ignore --files -g '*.fdf' -g '!**/.git/**' -g '!**/.venv/**' -g '!**/venv/**' -g '!**/__pycache__/**'; ... [PowerShell regex count for each file]` → `FILES=197 SCF.DM.Tolerance=66 DM.Tolerance=12 SCF.H.Tolerance=66`. |
| 20.3/P5 | TRUE | `Get-Content tools/fdebq_scf_ladder_campaign.py | Select-Object -Skip 80 -First 48` → requires identical SHA256 across all parent DMs with error `all ladder runs must preserve the same parent DM identity`. |
| 20.3/P6 | TRUE | `rg -n -C 3 'MaxSCFIterations' src/hubbardflow/siesta_backend/siesta542_bare_profile.py` → profile declares `"MaxSCFIterations": "1"`. |
| 20.3/P7 | TRUE | `Select-String -Path campaigns/mno_afmii_strict_lr_v3r2/results/calibration-replicas-admissible-foreground-v3/recovery-01/reference/siesta.out -Pattern 'redata: Require DM convergence|redata: DM tolerance for SCF|redata: Require H convergence|redata: Hamiltonian tolerance for SCF' | Select-Object -First 4` → echoes both criteria as `T`, DM `0.000010`, H `0.000100 eV`, each to six decimal places. |
| 20.3/P8 | TRUE | `rg -n -C 4 'def bind_ladder_input|alpha.*zero|alpha_ev.*0|alpha_ev == 0' src/hubbardflow/siesta_backend/scf_ladder_inputs.py` → `bind_ladder_input` raises `zero perturbations are not SCF ladder inputs` for `alpha_ev == 0`. |
| 20.3/P9 | TRUE | Official SIESTA documentation lookup: `https://docs.siesta-project.org/projects/siesta/en/latest/tutorials/applications/optical-properties/` says the DM is copied, not linked, because the calculation overwrites the DM file; the 5.4 reference also states DM output is overwritten at every SCF step. |

The nine 20.3 premises are TRUE. Independent pre-implementation review completed with `RISK_COVERED`.
The draft was then stopped on the existing-test/specification conflict documented below.

### 20.3 draft stopped: conflict with existing tests

Pre-implementation auditor verdict: `RISK_COVERED`. Conditions: v2 requires explicit DM/H
values >=1e-6 and exact multiples of 1e-6; preserve D5 mathematics and the named
`synthetic-v1` algebraic tests without enabling v1 evidence/materialization; bind each level to
its distinct reference-output DM at preparation time; check exact six-decimal echoes;
require positive existing convergence evidence for references; do not require convergence
from perturbed BARE runs; preserve BARE `MaxSCFIterations 1`.

The draft changes only 20.3's permitted models/backend/two tools/runbook and a new test file.
It is **not committed or integrated**. No existing test was edited. The code draft is saved in
`git stash` as `draft blocked task 20.3`, outside the working tree. The stop is a test/specification conflict, not an uncovered scientific
risk; the auditor's verdict remains `RISK_COVERED`.

Command:
`.venv/Scripts/python.exe -m pytest tests/unit/test_scf_ladder_v2.py tests/unit/test_scf_ladder.py tests/unit/test_scf_ladder_inputs.py tests/unit/test_scf_validation.py -q`

Literal short summary:
```text
FAILED tests/unit/test_scf_validation.py::test_materialized_ladder_changes_only_tolerance_and_preserves_parent
FAILED tests/unit/test_scf_validation.py::test_materializer_rejects_missing_parent_assets_and_unsafe_restart
2 failed, 54 passed, 2 warnings in 7.90s
```

The first test calls `build_ladder_runs(..., policy(), ...)` where `policy()` is
`synthetic-v1`, has a tightest DM tolerance `1e-7`, lacks every H tolerance and supplies the
same parent for all levels. It expects materialization to succeed. The draft correctly rejects
it with `NOT_ESTABLISHED: SCF_LADDER_PROTOCOL_V1`, because 20.3 and the auditor explicitly
prohibit v1 production materialization and require distinct level parents and representable
DM/H tolerances. No scope authorization names this existing test for editing.

The second test uses the same v1 protocol and an incomplete FDF containing
`File.DM.Init parent.DM`. It expects the `File.DM.Init` error first. The new v1 rejection
occurs first: expected regex `File.DM.Init`; actual message
`NOT_ESTABLISHED: SCF_LADDER_PROTOCOL_V1`. This test also is not authorized for editing.
The orchestration must resolve both existing-test expectations before committing 20.3.

Other draft checks, recorded without treating the item as accepted:
- Earlier focused command excluding `test_scf_validation.py`: `52 passed, 2 warnings in 6.81s`.
- `.venv/Scripts/python.exe -m pytest tests/unit/test_lr_analysis_v2.py tests/unit/test_matrix_lr.py tests/unit/test_quantized_response.py tests/unit/test_u_certification.py -q`: `70 passed, 2 warnings in 1.19s`.
- Ruff on the six touched/new Python files: `All checks passed!`.
- Ruff format check on those six files: `6 files already formatted`.
- Strict mypy on those six files: `Success: no issues found in 6 source files`.
- `bash tools/check_v6_integrity.sh`: `V6 GATE OK`.

Decisiones del implementador (conservadoras) in the uncommitted draft: retain absent criterion
families as explicit null evidence instead of inferring SIESTA defaults; refuse v1 evidence or
materialization while preserving `synthetic-v1` algebraic calculations; capture parent bytes
once before copying; preserve the existing SCREENED output failure/convergence check and
require positive existing convergence evidence for each reference. D5 numerical formulas
are unchanged.

### 20.4 premise checks (after R2, before implementation)

| Premise | Result | Command and evidence |
|---|---|---|
| 20.4/P1 | TRUE | `rg -n -C 2 'def relabel_ion_bytes|def canonical_ion_bytes|<basis_specs>|# Label' src/hubbardflow/siesta_backend/semantic_ion_identity.py` → both helpers exist, normalize only the basis header label and scalar before `# Label`, preserve line structure, and reject unknown layouts. |
| 20.4/P2 | TRUE | `python probe using pathlib bytes/splitlines on FEO_SCF_DIAGNOSTIC_EXPORT_20261001/feo_lru_fullU_PopTol1e-5_MixerWeight0.05/FeLR0.ion and FeLR1.ion` → both files have 8119 lines; raw diff is exactly `[5, 79]`, showing only the basis-header label and `# Label` value. Frozen V6 files were read only. |
| 20.4/P3 | TRUE | `rg -n -C 2 'raw SHA256 equality|raw_sha256.*!=' src/hubbardflow/siesta_backend/split_generated_identity.py` → current code adds `ION_BYTES_DIFFER` when raw hashes differ and returns `SPECIES_IDENTITY_NOT_ESTABLISHED`; the real pair's raw bytes differ. |
| 20.4/P4 | TRUE | `rg -n -C 1 '# Symbol|pseudopotential_header|FeLR[01]' .../FeLR0.ion .../FeLR1.ion` and the P2 byte diff → `# Symbol` is `Fe` in both; pseudopotential header is `Fe pb nrl pcec` in both; neither line differs. |

R2 explicitly authorizes renaming/editing only `tests/unit/test_split_generated_identity.py::test_real_archive_label_only_difference_is_never_a_positive` to `test_real_archive_label_only_difference_matches`, expecting `MATCH` for the frozen real FeLR0/FeLR1 pair. A current read-only probe reports `canonical_ion_bytes(FeLR0, "FeLR0") == canonical_ion_bytes(FeLR1, "FeLR1")` as `True`. No implementation has started for 20.4.

### 20.4 stopped before implementation: existing fixture contradicts canonical identity

All 20.4 premises were verified TRUE by the orchestrator. R2 authorizes only editing/renaming
`tests/unit/test_split_generated_identity.py::test_real_archive_label_only_difference_is_never_a_positive`
to `test_real_archive_label_only_difference_matches`, expecting MATCH for the real FeLR0/FeLR1 pair.
It does not authorize changes to `_run()` or `test_exact_receipt_roundtrip_and_cli`.
No 20.4 source or test edits were made, and there is no 20.4 implementation commit.
The stop is an existing-test/specification conflict, not a scientific `RISK_UNCOVERED` verdict.

Evidence command: a temporary-directory Python probe imports
`tests.unit.test_split_generated_identity._run`, writes its existing synthetic fixture, calls
`verify_generated_split_identity(root, 'Mn', ['MnLR0', 'MnLR1'])`, and independently calls
`canonical_ion_bytes` with each requested label. Literal output:

```text
EXISTING_TEST_VERDICT=EXACT_ION_BYTES_MATCH
ORIGINAL_CANONICAL_LENGTH=163
MnLR0: canonical rejected: ion must have exactly one matching basis_specs species header
MnLR1: canonical rejected: ion must have exactly one matching basis_specs species header
```

`rg -n 'def test_|_run\(|raw_sha256|EXACT_ION' tests/unit/test_split_generated_identity.py`
shows `_run()` at line 23 writes the internal Mn bytes under each alias filename. The positive
`test_exact_receipt_roundtrip_and_cli` at line 31 requires MATCH and CLI exit 0 for that fixture,
whose alias content has the wrong label for `canonical_ion_bytes(alias, alias_label)`.

Current-gate command:
`.venv/Scripts/python.exe -m pytest tests/unit/test_split_generated_identity.py::test_exact_receipt_roundtrip_and_cli -q`
returned `1 passed, 2 warnings in 0.77s`. Implementing the stipulated MATCH iff canonical equality
rule would make this existing positive gate fail, since both alias canonicalizations reject.
Allowing raw equality as a shortcut would violate 20.4's stated necessary conditions.
The fixture cannot be changed under R2's narrow authorization. Implementation stops pending an
explicit resolution of this additional existing-test expectation; no shortcut was introduced.

### 20.5 premise checks (after R3, before implementation)

| Premise | Result | Command and evidence |
|---|---|---|
| 20.5/P1 | TRUE | `rg -n -C 3 'def exactness_class|EXACT_TRANSLATION' src/hubbardflow/domain/symmetry_operation_models.py` → current property returns `EXACT_TRANSLATION` whenever `rotation_int == IDENTITY`, without checking epsilon, atom mapping, or mesh. |
| 20.5/P2 | TRUE | `rg -n -C 3 'F8|exactness_class|EXACT_TRANSLATION|translations' src/hubbardflow/domain/symmetry_operations.py src/hubbardflow/domain/coverage.py` → F8 ambiguity is ignored for identity-rotation candidates and F8 does not gate translation candidacy. |
| 20.5/P3 | TRUE | `rg -n -C 2 'EXACT_IN_CONTINUUM_ONLY|commensurate|continuum' docs/fdebq/HUBBARDFLOW_PERTURBATION_PLANNING_REVIEW.md` → review D.3 marks noncommensurate translations `EXACT_IN_CONTINUUM_ONLY`, requiring a shadow and validation before enabling. |
| 20.5/P4 | TRUE | `rg -n -C 3 'positions|Fraction\(str|tau_neq|Fractional|LatticeConstant|AtomicCoordinatesFormat|InitMesh' src/hubbardflow/domain/symmetry_operations.py src/hubbardflow/siesta_backend/fdf_model.py` → candidates use floating `coordinates_fractional % 1`; F8 uses `Fraction(str(float))`; atom matching uses the declared geometry band; parser normalizes coordinates/lattice units but retains only numeric values in the current model. |
| 20.5/P5 | TRUE | `rg -n -C 3 'matching\[0\]' src/hubbardflow/domain/coverage.py` → member operation is selected as `matching[0]`. |
| 20.5/P6 | TRUE | `python probe using tests.unit.test_coverage._toy(4, nonpolarized=True), qualify_coverage, and spin-flip false/true policies` → both reports contain 32 epsilon=-1 rows and F7 `AMBIGUOUS`; current code creates the channel-relabel operation instead of marking epsilon=-1 `NOT_APPLICABLE`. |
| 20.5/P7 | TRUE | `rg -n -C 4 'spglib|importlib' src/hubbardflow/domain/symmetry_operations.py pyproject.toml` plus `python -c find_spec('spglib')` → candidate search dynamically imports optional spglib; pyproject has no declaration; this environment reports `spglib_importable=False`. |
| 20.5/P8 | TRUE | `rg -n -C 3 'coverage_qualification|"coverage": "DISABLED"|NiO' src/hubbardflow/execution/campaign_plan.py tests/unit/test_campaign_plan.py` and read-only in-memory `resolve_campaign_planning` on `benchmarks/lr_u/stage_u_b/materials/NiO/reference.fdf` with `coverage=DISABLED` → qualification is embedded; the current NiO result has 16 operations and a plan digest. |

R3(a) explicitly authorizes updating only `tests/unit/test_symmetry_operations.py::test_f8_records_incommensurate_translation_without_excluding_candidate`: t=1/4 with mesh (3,3,3) remains a candidate and becomes `EXACT_IN_CONTINUUM_ONLY`. R3(b) retires spglib from planning; rotation candidates missed on non-orthogonal cells are a known conservative Phase 3 savings limitation, not an uncovered risk. Translation candidates must be checked by a dedicated test; if one is lost, stop before implementation. Independent scientific audit is now required before code because 20.5 is `[science]`.

### 20.5 independent scientific audit and stop under R3(b)

Auditor verdict: `RISK_UNCOVERED`; no code or tests were changed for 20.5. The read-only counterexample uses `tests.unit.test_symmetry_operations._ring((0.8,)*4)`, moves alternating fractional x coordinates by `0.75*tau_neq`, constructs the valid candidate operation (IDENTITY, t=(0.25,0,0), eps=+1, permutation=(1,2,3,0)), and forces the internal path without spglib by patching `importlib.import_module` to raise ImportError.

Observed output:

```text
F1 AMBIGUOUS 0.0007500000000000284
internal identity translations: t=0 (identity permutation), t=0.5 (permutation 2,3,0,1)
missing candidate: t=0.25 (permutation 1,2,3,0)
```

The declared `tau_neq=0.001` admits this near-symmetry as an `AMBIGUOUS` candidate; the current anchor enumeration proposes t=0.25075, whose residual on other atoms reaches 0.0015, and discards the needed t=0.25 mapping. The audit also simulated a spglib result supplying t=0.25 and observed that it adds the missing candidate; this was a controlled simulation, not a claim that spglib was installed or run. R3 explicitly requires stopping if a translation candidate is lost, so no implementation/test attempt is authorized until translation search can retain it.

R3(b) resolves the separate rotation omission: omitted rotations on non-orthogonal lattices are a conservative lost-savings limitation because rotations are off by default and cannot reduce production without V2 validation. This is not `RISK_UNCOVERED`; record it as a known Phase 3 limitation. The translation counterexample is the active uncovered risk.

Exact audit probe and output are recorded in the auditor report for `/root/audit_20_5_r3`; the critical executed logic was the candidate_operations call with the optional import patched to ImportError, then an inventory check of its identity/epsilon operations. No baseline file or campaign was modified.

### Exact 20.5 read-only probe commands

P6 command:
`powershell
@'
from dataclasses import replace
from tests.unit.test_coverage import _toy, USER
from hubbardflow.domain.coverage import qualify_coverage
from hubbardflow.domain.symmetry_operation_models import coverage_policy_v1
for enabled in (False, True):
    inv, ref, model = _toy(4, nonpolarized=True)
    q = qualify_coverage(inv, ref, model, replace(coverage_policy_v1(), allow_spin_flip=enabled), USER)
    rows = [(r.operation.eps, [(c.condition,c.status.value) for c in r.conditions if c.condition=='F7']) for r in q.operations if r.operation.eps == -1]
    print('allow_spin_flip=',enabled,'eps_minus_rows=',len(rows),'F7=',rows[:2])
'@ | .venv/Scripts/python.exe -
`
Output: allow_spin_flip=False and True each produced 32 epsilon=-1 rows with F7 AMBIGUOUS.

P8 command:
`powershell
@'
import tempfile
from pathlib import Path
from tests.unit.test_campaign_plan import inputs, normalized
from hubbardflow.execution.campaign_plan import resolve_campaign_planning
source=Path.cwd()/'benchmarks/lr_u/stage_u_b/materials/NiO/reference.fdf'
with tempfile.TemporaryDirectory() as tmp:
    fdf, raw, _=inputs(Path(tmp), source.read_text(encoding='utf-8'))
    raw['coverage']='DISABLED'
    result=resolve_campaign_planning(fdf,normalized(fdf,raw))
    print(raw['coverage'],len(result.diagnostic_coverage.operations),result.plan.digest)
'@ | .venv/Scripts/python.exe -
`
Output: DISABLED 16 47f5bbb9dde9803fed4d1a5601d3cebd1926990f2ebf3ef3d851bcf7e1925136.

### 20.8 — dependency stop before premise checks or implementation

20.8 requires the SCF ladder v2 protocol from 20.3 and validates calibration against coverage/planner evidence from 20.5. 20.3 is blocked by two existing tests that demand v1 production materialization; 20.5 is stopped under R3 because a within-band translation candidate is lost. Therefore 20.8 is not independent and no 20.8 code, tests, or premise checks were started. Resume after the two upstream blockers are resolved.


### 20.9 — comprobación R4 sobre NiO P5 (detenida por diferencia)

La única cadena archivada compatible especificada por R4 existe en `/home/jmc/.local/state/siestaflow/campaigns/nio-pbe-p5-20260928/`. Los hashes del campaign.v2.json, reference.fdf, lr_config.json y node-evidence.json son, respectivamente, `0917d0ca393f167aaff02f5730d0a6a549ea35cbc17ddbe818cb662b3d073b4f`, `b4fb34e642d862be6949a5b2033a60c5b9fcae56119879583bb3eaf237620ee7`, `619895c0908c5c557a476151a9e06a63483254b7e0b814af084784ac07fd7cd6`, y `0e8d0b0bb781437b59942f8bae33204401bb116b32d40a4762aa33a2c174e1be`. Los hashes de FDF materializados constan en los 24 nodos de node-evidence.

Comando de inicialización en directorio temporal, con coverage=DISABLED y usando la FDF, lr-config y ejecución de la cadena archivada:
`wsl.exe -d Ubuntu -- bash -lc 'PYTHONPATH=/mnt/c/Users/Jairo/work/hubbardflow/src /home/jmc/.local/state/siestaflow/hubbard-response-env/bin/python - << "PY" ... initialize_campaign(...) ... PY'`

Salida observada: 2 sitios actuales (`NiLR0`, `NiLR1`, átomos 1 y 2), 24 run specs y coverage `DISABLED`. Las tuplas de átomo, modo y alpha coinciden con las 24 entradas archivadas, pero falla la igualdad estricta solicitada para `(site, atom, mode, alpha)`: el plan actual emplea `NiLR0@0:3:2` y `NiLR1@1:3:2`; el manifiesto y node-evidence usan `NiLR0` y `NiLR1`. Por instrucción R4, 20.9 se detiene sin cambios para forzar equivalencia. Al no coincidir el conjunto, no se intentó fabricar una comparación de hashes materializados actuales. CoO, MnO y Cu3N: `NOT_COVERED`, según R4. No se modificaron fixtures ni datos archivados.


## Rerun under author resolutions R1–R4 — final current branch check

The order resumed as requested: 20.2, 20.3, 20.4, 20.5, 20.8, 20.9, 20.11, 20.10. 20.2 completed in commit `f629220`. 20.3, 20.4, 20.5 and 20.9 reached their item-specific blockers recorded above; 20.8, 20.11 and 20.10 depend on stopped items. No source/test changes or item commits were made for those stopped items. R2 and R3 test-edit exceptions were not exercised because the separate 20.4 fixture conflict and the R3 translation-loss stop remain unresolved.

Full-suite command on current branch:
`.venv/Scripts/pytest.exe tests -q -rfE --continue-on-collection-errors` with `PYTHONPATH` set to this checkout's `src`.

Result: `21 failed, 1288 passed, 24 skipped, 2 warnings, 5 errors, 4 subtests passed in 276.22s`. The five collection errors and 20 original failure IDs are exactly the `BASELINE_FAILURES` listed in §0.2. One additional failure is new relative to that baseline:

- `tests/unit/test_scf_validation.py::test_materializer_rejects_missing_parent_assets_and_unsafe_restart` — expected an error matching `File.DM.Init`, received `NOT_ESTABLISHED: source FDF ladder identity cannot be bound: required FDF directive LatticeConstant is missing`.

Thus the suite is not baseline-clean; no item implementation was attempted to mask or repair this failure. TASK 21 focused command `.venv/Scripts/pytest.exe tests/unit/test_product_cli.py tests/unit/test_product_paths.py tests/unit/test_product_paths_portable.py tests/unit/test_product_admission.py tests/unit/test_product_execution.py -q` → `85 passed, 2 warnings in 133.11s`.

Final gates on this result: 70 scientific regression tests → `70 passed, 2 warnings`; `ruff check .` → `All checks passed!`; `ruff format --check .` → `90 files already formatted` (cache write warnings only; exit 0); `MYPYPATH=src mypy --strict` → `Success: no issues found in 90 source files`; `bash tools/check_v6_integrity.sh` → `V6 GATE OK`.

R4 archived materialized-input hash comparison was not reached: the required exact run-spec tuple comparison already differs in `site` (`NiLR0@0:3:2`/`NiLR1@1:3:2` current versus `NiLR0`/`NiLR1` archived). Per author instruction, stop without attempting a correction. CoO, MnO and Cu3N are `NOT_COVERED` for this revised 20.9 check.


### R6 / 20.2 corrective regression premise checks (before code)

| Premise | Result | Command and evidence |
|---|---|---|
| R6/P1 | TRUE | `Get-Content src/hubbardflow/siesta_backend/scf_ladder_inputs.py` and `rg -n -C 5 'resolve_fdf_includes|parse_effective_fdf|File.DM.Init|_one\(effective' ...` → `resolve_fdf_includes(source)` is followed by `parse_effective_fdf(source)` and only then `_one(effective, "File.DM.Init")`. |
| R6/P2 | TRUE | Venv Python called `canonical_fdf_label` on `File.DM.Init`, `file_dm_init`, and `FILE-DM-INIT` → all three produce `filedminit`. |
| R6/P3 | TRUE | `Get-Content src/hubbardflow/siesta_backend/fdf_labels.py` and `rg -n 'def resolve_fdf_includes|effective, _ = resolve_fdf_includes' src/hubbardflow/execution/campaign_v2.py src/hubbardflow/siesta_backend/scf_ladder_inputs.py` → canonical label helper exists and `bind_ladder_input` receives effective include-resolved text. |
| R6/P4 | TRUE | `.venv/Scripts/pytest.exe tests/unit/test_scf_validation.py::test_materializer_rejects_missing_parent_assets_and_unsafe_restart -q` → currently fails as R6 claims: expected `File.DM.Init`, actual `NOT_ESTABLISHED: source FDF ladder identity cannot be bound: required FDF directive LatticeConstant is missing`. |
| R6/P5 | TRUE | `Get-Content src/hubbardflow/siesta_backend/fdf_model.py` lines 144–170 → `_clean` strips text after `#`; `_directive_rows` selects first top-level token. R6 explicitly requires checking the first token on each effective line after comments are removed. |

Independent scientific audit is requested before implementation because this is a correction to the `[science]` item 20.2. No source or test has been changed yet.


R6 pre-implementation auditor: `RISK_COVERED`. The auditor confirmed that the check belongs after include expansion and before parsing, uses `#` comment semantics, ignores blank lines, and keeps `DM.UseSaveDM` and parent identity checks intact. No math, tolerance, estimator, or scientific selection behavior changes. Auditor also verified canonical spellings `File.DM.Init`, `file_dm_init`, and `FILE-DM-INIT` all map to `filedminit`, while the commented spelling has no directive token.


### R6 implementation and gates

Changed `bind_ladder_input` to inspect every include-resolved effective FDF line immediately after `resolve_fdf_includes`: remove `#` comments, take the first token, canonicalize it, and reject `filedminit` before `parse_effective_fdf`. Removed the old post-parse `_one` check. Added `test_noncanonical_file_dm_init_is_rejected_before_fdf_parsing` using `file_dm_init parent.DM`. The original `test_materializer_rejects_missing_parent_assets_and_unsafe_restart` was not edited.

- Focused: `.venv/Scripts/pytest.exe tests/unit/test_scf_ladder_inputs.py tests/unit/test_scf_validation.py::test_materializer_rejects_missing_parent_assets_and_unsafe_restart -q` → `17 passed, 2 warnings`.
- Full required suite: `.venv/Scripts/pytest.exe tests -q -rfE --continue-on-collection-errors` with current checkout `src` on `PYTHONPATH` → `20 failed, 1290 passed, 24 skipped, 2 warnings, 5 errors, 4 subtests passed in 216.00s`. The five collection errors and all 20 failing test IDs exactly match `BASELINE_FAILURES`; the additional SCF validation failure recorded above is gone. Exact IDs remain the §0.2 list.
- Scientific regressions: 70 passed, 2 warnings.
- Ruff: `All checks passed!`.
- Format: `90 files already formatted`.
- Configured strict mypy: `Success: no issues found in 90 source files`.
- New test strict mypy: `Success: no issues found in 1 source file`.
- V6: `V6 GATE OK`.

No pre-existing test assertion was edited. No FDF parser behavior outside the early safety guard changed.


### 20.3 / R7 premise checks before resuming the saved draft

| Premise | Result | Command and evidence |
|---|---|---|
| R7/P1 | TRUE | `Get-Content tools/fdebq_scf_ladder_campaign.py` around `build_ladder_runs` → current code checks `protocol.enabled`, then validates output/groups, and binds each source before checking assets; no protocol version gate is present in the current checked-in implementation. |
| R7/P2 | TRUE | `Get-Content tests/unit/test_scf_validation.py` lines 80–104 → `test_materialized_ladder_changes_only_tolerance_and_preserves_parent` calls `build_ladder_runs` with `policy()` and asserts 12 materialized v1 runs and parent DM copies. |
| R7/P3 | TRUE | `.venv/Scripts/pytest.exe tests/unit/test_scf_validation.py::test_materialized_ladder_changes_only_tolerance_and_preserves_parent tests/unit/test_scf_validation.py::test_materializer_rejects_missing_parent_assets_and_unsafe_restart -q` → both existing tests pass unchanged on the R6 result (`2 passed, 2 warnings`); `policy()` uses protocol version `synthetic-v1`. |
| R7/P4 | TRUE | Same command → the original unsafe-restart test passes after R6 without edits. Current code's `build_ladder_runs` still has no version rejection and checks per-source/security state before any protocol-version check because such a check is absent. |
| R7/P5 | TRUE | `git stash show --stat --include-untracked 'stash@{0}'` → saved 20.3 draft contains `scf_ladder_inputs.py`, `tools/fdebq_scf_ladder_campaign.py`, `scf_ladder.py`, `scf_ladder_models.py`, `tools/fdebq_validate_t0_t4.py`, `tests/unit/test_scf_ladder_v2.py`, and `T0_T4_RUNBOOK.md`. |

R7 requires security checks across all entries (including missing assets) before protocol-version rejection. Apply this explicitly while resuming the saved draft; preserve R6's early canonical unsafe-restart check in the rewritten `scf_ladder_inputs.py`. The existing v1 materialization assertion is eligible for a R5 edit; record its old/new assertions and the exact 20.3 clause after the edit is reviewed.


### 20.3 R5 authorized test edit — assertion record

Edited only the specifically authorized `tests/unit/test_scf_validation.py::test_materialized_ladder_changes_only_tolerance_and_preserves_parent`.

- Old assertion: using the `synthetic-v1` policy, `build_ladder_runs` succeeds; assert 12 generated runs, one shared parent-DM digest, copies of the DM and pseudopotential, and materialized `DM.Tolerance` values.
- New assertion: with safe, complete v1 inputs, `build_ladder_runs` raises `ScfLadderError` matching `SCF_LADDER_PROTOCOL_V1`, and creates no output directory.
- Replacing clause: 20.3 Change 1, “v1 records load as `NOT_ESTABLISHED` (`SCF_LADDER_PROTOCOL_V1`)”; R7 specifies that security preflight occurs first, so this test uses otherwise safe and complete inputs.

`test_materializer_rejects_missing_parent_assets_and_unsafe_restart` remains unedited and passes. Added a distinct v1 test showing that a missing asset is reported before the v1 protocol rejection.

R7 corrections made after auditor review: security preflight in `build_ladder_runs` before `require_evidence_v2`; the current R6 canonical guard is shared with the reference materializer and runs before parsing; v2 H tolerances strictly decrease in the existing DM-level order; T0–T4 validation visits groups in sorted order. The H-order condition is qualitative monotonic hardening from D9/§E.2; it introduces no numeric factor or threshold.


### 20.3 implementation and gates after R7

Resumed the saved v2 ladder draft and retained R6's canonical `File.DM.Init` check before parsing in both perturbed-run binding and reference materialization. `build_ladder_runs` now checks effective FDF safety, declared parent identity/path, and required assets for the inputs before `require_evidence_v2`; it also checks request-key and symmetric-grid structure before the protocol gate. A safe complete v1 request therefore reaches `SCF_LADDER_PROTOCOL_V1`, while an unsafe restart or missing asset is reported first. Added tests for the latter orderings. V2 levels now require strictly decreasing H tolerances in the same DM-sorted order, with no invented factor; T0–T4 groups are visited in sorted order.

Auditor: `RISK_COVERED`. Explicit R5 confirmation: `test_materialized_ladder_changes_only_tolerance_and_preserves_parent` was renamed to `test_materialization_rejects_legacy_v1_protocol`; only its v1-production success assertions were replaced. Independent checks for an existing output destination, incomplete symmetric grid, and alpha-zero rejection were retained. `test_materializer_rejects_missing_parent_assets_and_unsafe_restart` remains unchanged. The final reviewed v1 evidence test uses four safe FDFs plus existing parent/assets, so protocol rejection occurs after preflight.

- Focused SCF ladder modules: `61 passed, 2 warnings`.
- 70 scientific regression tests: `70 passed, 2 warnings`.
- Ruff: `All checks passed!`.
- Format: `91 files already formatted`.
- Configured strict mypy: `Success: no issues found in 91 source files`.
- Strict mypy on the two touched SCF test modules: `Success: no issues found in 2 source files`.
- V6: `V6 GATE OK`.

The original D5 estimator body remains byte-for-byte AST-identical to HEAD according to the auditor; parent references are captured/checked by the v2 draft before perturbation materialization. No SIESTA was executed.


### 20.4 premise checks after R8

| Premise | Result | Command and evidence |
|---|---|---|
| 20.4/P1 | TRUE | `.venv/Scripts/python.exe` probe importing `canonical_ion_bytes` plus `Get-Content src/hubbardflow/siesta_backend/semantic_ion_identity.py` → `relabel_ion_bytes` and `canonical_ion_bytes` exist; they normalize only the two audited fields and raise on unknown/ambiguous layouts. |
| 20.4/P2 | TRUE | `.venv/Scripts/python.exe` read-only byte probe of the two named frozen `.ion` files → each has 8119 lines; the only differing lines are 5 and 79. Frozen files were read only. |
| 20.4/P3 | TRUE | `rg -n "raw_sha256.*!=|SPECIES_IDENTITY_NOT_ESTABLISHED|generated_split_identity\\.v1" src/hubbardflow/siesta_backend/split_generated_identity.py tools/hubbardflow_verify_split_identity.py` → current receipt version is v1; raw SHA inequality adds `ION_BYTES_DIFFER` and produces `SPECIES_IDENTITY_NOT_ESTABLISHED`; CLI only returns 0 for raw-byte equality. |
| 20.4/P4 | TRUE | `.venv/Scripts/python.exe` read-only inspection of the named pair → both have `Fe # Symbol`, distinct `FeLR0`/`FeLR1` `# Label` values, and byte-identical pseudopotential header contents (`Fe pb nrl pcec ...`). |

R8 provides additional authorization for the previously conflicting existing receipt fixture. The `MnLR0`/`MnLR1` positive fixture will use `relabel_ion_bytes(_ion("Mn", 25), "Mn", alias)` so its header matches its filename; an explicit raw-identical but wrong-header case must return `MISMATCH`. R2 separately authorizes the FeLR0/FeLR1 real archive test to expect `MATCH`. No implementation had started when these premise checks were recorded.

### 20.4 R5 test edits — assertion record

| Existing test | Old assertion/fixture | New assertion/fixture | Replacing clause |
|---|---|---|---|
| `test_exact_receipt_roundtrip_and_cli` | All raw `.ion` files had identical bytes; receipt asserted `EXACT_ION_BYTES_MATCH` and identical raw SHA256 values. | Alias fixtures are generated with `relabel_ion_bytes`; receipt asserts `MATCH`, differing raw hashes, canonical receipt roundtrip, and label-line differences; CLI remains exit 0. | 20.4 verdict rule and R8: positive fixture aliases must have matching SIESTA header labels; raw SHA256 is diagnostic. |
| `test_real_archive_label_only_difference_is_never_a_positive` (R2) | The prior fixture relabelled `examples/Mn.ion`, then asserted `SPECIES_IDENTITY_NOT_ESTABLISHED` and `ION_BYTES_DIFFER`. | Renamed to `test_real_archive_label_only_difference_matches`; copies frozen FeLR0/FeLR1 into `tmp_path` and asserts `MATCH`, no reasons, canonical hashes equal and raw differing lines `(5, 79)`. | 20.4 acceptance “real pair FeLR0/FeLR1 → MATCH”; explicit R2 authorization. |
| `test_missing_duplicate_and_mismatch_fail_closed` | The physical-change fixture stored un-relabelled Mn bytes under alias filename and every readable byte mismatch expected `SPECIES_IDENTITY_NOT_ESTABLISHED`. | Physical fixture now starts from a correctly relabelled MnLR0 ion, changes only radial numeric data, expects `MISMATCH` and lists raw changed lines; missing/duplicate cases retain their not-established assertion. | 20.4/R8: impossible alias-header fixtures must be made valid; readable physical differences return `MISMATCH` and list differing lines. |
| `test_invalid_receipt_cannot_claim_match` | Changing an alias raw SHA256 while retaining its canonical match was asserted invalid. | Renamed to `test_raw_sha256_is_diagnostic_and_does_not_change_verdict`; changing the raw digest field does not change `MATCH`. | 20.4: “Raw sha256 values stay in the receipt as diagnostics”; explicit R8 authorization to adjust raw-SHA assertions. |

Added tests (not edits to existing assertions): raw-identical bytes with an alias-inconsistent header → `MISMATCH`; changed `# Symbol` on the frozen Fe fixture → `MISMATCH` with all differing lines listed; receipt deserialization rejects a `relabel_match` flag with a contradictory canonical digest. Auditor's initial finding was that R2 must use the actual frozen Fe pair and that deserialization must validate canonical hashes for `relabel_match`; both corrections and a regression test are included in the reviewed diff.

### 20.4 auditor and gates

Auditor final verdict: `RISK_COVERED`. It confirmed the real FeLR0/FeLR1 pair gives `MATCH` with raw differing lines `(5, 79)`, deserialization rejects contradictory canonical hashes for a positive flag, and raw SHA changes remain diagnostic. Auditor explicitly confirmed all four existing test edits in the table above meet R5/R2/R8.

- Focused receipt module: `.venv/Scripts/python.exe -m pytest tests/unit/test_split_generated_identity.py -q` → `20 passed, 2 warnings`.
- 70 scientific regressions: `.venv/Scripts/python.exe -m pytest tests/unit/test_lr_analysis_v2.py tests/unit/test_matrix_lr.py tests/unit/test_quantized_response.py tests/unit/test_u_certification.py -q` → `70 passed, 2 warnings`.
- Ruff: `.venv/Scripts/ruff.exe check .` → `All checks passed!`.
- Format: `.venv/Scripts/ruff.exe format --check .` → `91 files already formatted`.
- Strict mypy: `$env:MYPYPATH='src'; .venv/Scripts/mypy.exe --strict` → `Success: no issues found in 91 source files`; strict check of the touched source and test → `Success: no issues found in 2 source files`.
- V6: `bash tools/check_v6_integrity.sh` → `V6 GATE OK`.
