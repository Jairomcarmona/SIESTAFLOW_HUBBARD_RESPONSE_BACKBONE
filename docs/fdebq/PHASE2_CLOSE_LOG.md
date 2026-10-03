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
