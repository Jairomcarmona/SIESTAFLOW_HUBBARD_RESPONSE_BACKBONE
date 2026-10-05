# TASK 23 execution log

## Preparation

- Read the complete repository `AGENTS.md` before editing.
- `git fetch origin` completed. `git diff --quiet a1b3c31 origin/codex/hubbardflow-rename` returned 0 with no output; the TASK 22 merge was present.
- Created `fdebq/r7-task23-ts` from `origin/codex/hubbardflow-rename`.
- The supplied `CODEX_TASK23_TS.md` was copied byte for byte (source and destination SHA-256 `3b34b6670dff30601cbab6e47ed4d02308ff8db00bc64a4d40a4b6e1717246bf`). D14a–D14e were appended under `TASK 23` in `AMENDMENTS_2.md`. The docs-only commit is `632725e`.
- The docs-only diff was checked by `verificador_luna`. Post-commit gates: WSL NiO P5 replay 7 passed; golden 20.9 4 passed; product tests 110 passed; scientific regressions 70 passed; architecture 8 passed; `ruff check .` passed; `ruff format --check .` reported 91 files already formatted; `MYPYPATH=src mypy` succeeded on 91 files; V6 gate printed `V6 GATE OK`; full suite reported 1395 passed, 27 skipped, 20 xfailed, 4 subtests passed, 2 warnings.

## 23.1 — species identity from the global basis

### Premises checked before implementation

| Premise | Real command/evidence | Result |
|---|---|---|
| Identity required a known pseudo and an explicit `PAO.Basis` record. | `Get-Content src/hubbardflow/siesta_backend/fdf_model.py` around `species_identity`; the original status expression required both `pseudo_digest` and `basis_digest`. | Confirmed. |
| No repository FDF declares a `%block PAO.Basis`; repository block names match the audited set. | `rg -n -i '^\\s*%block\\s+pao\\.basis\\b' --glob '*.fdf'` had no matches. A repository-wide `rg` enumeration found only `atomiccoordinatesandatomicspecies`, `bandlines`, `bandpoints`, `chemicalspecieslabel`, `dftu.hubbard`, `dftu.proj`, `dftu.projector`, `dm.initspin`, `kgrid_monkhorst_pack`, and `latticevectors`. | Confirmed. |
| MnO source is the expected unperturbed reference FDF. | `Get-FileHash campaigns/mno_afmii_strict_lr_v3r2/results/response-matrix-foreground-recovery-v4/00_REFERENCE/siesta.fdf -Algorithm SHA256` | `3c86abab6daf4c0c00a10da6a7e060470e54bcc5364f70a0e2932285c24941e6`. |
| Old PAO parser dropped all fields on the first row after the label. | Read `parse_effective_fdf` around its `pao_basis_blocks` construction. | Confirmed: initialized each PAO entry with an empty row list. |
| Planning callers ignored the explicit lr-config map; runtime inventory must remain unchanged. | `rg -n 'species_identity\\(' src/hubbardflow/...` and source reads of `product_plan.py`, `campaign_plan.py`, and `campaign_inventory`. | Confirmed: product/campaign planning passed only parent directories; runtime `campaign_inventory` passes staged directories. |
| Archived MnO currently cannot establish identities; planning with a single Mn pseudo should make the translation plan usable. | Added regression using the archived FDF, explicit map for the 16 Mn labels plus O, and the archived `siesta.out`; it passes with 17 established identities, two 8-member classes, shadows MnLR02/MnLR03, 4 computed columns, 48 run specs, and `REVIEW/SHADOW_PENDING`. | Confirmed by `tests/unit/test_product_cli.py::test_mno_translation_shadow_product_plan_uses_single_file_species_map`. |
| Baseline focused parser/planner tests were clean. | `python -m pytest tests/unit/test_fdf_model.py tests/unit/test_campaign_plan.py -q` | 40 passed. |

No premise was false.

### Independent review and conservative choice

`auditor_cientifico` confirmed D14a is compatible with the coverage evidence contract and found no scientific choice blocking implementation. The read-only check also showed fallback pseudopotential selection depended on the caller's directory order when duplicate files disagreed. The implementation sorts search directories and treats conflicting copies of the selected suffix as `NOT_ESTABLISHED`; this is recorded as **decisión del implementador (conservadora)**. Explicit map entries remain authoritative, and a missing mapped file does not fall back to directory search.

### Changes and authorized tests

- `species_identity` now accepts the optional explicit pseudopotential map, evaluates the audited neutral-block/global-basis rule, recognizes basis headers in identity digests, and fails closed for an incomplete PAO block set or enabled/unknown `User.Basis` controls.
- The product and campaign planning callers pass the lr-config map; runtime inventory callers remain unchanged.
- Bumped `CAMPAIGN_PLANNER_VERSION` to `campaign-planner-v4`.
- Follow-up audit confirmed an empty `%block PAO.Basis` contains no species records; the implementation therefore tests parsed records (`bool(basis_by_label)`), not merely block presence.
- Tests added/updated: FDF identity cases in `test_fdf_model.py`; the authorized CoO identity expectation plus missing-O control in `test_symmetry_operations.py`; planner v4 literals/name in `test_campaign_plan.py`; MnO TS product-plan golden in `test_product_cli.py`; shared-pseudopotential staged inventory digest in `test_product_execution.py`.
- No test assertion outside these item-authorized behaviors was changed.

### Golden updates

- `docs/fdebq/task10_reports/{CoO,NiO,FeO,Cu3N}.json`: each changed only `reasons[]`, removing `SPECIES_IDENTITY_NOT_ESTABLISHED`. No strategy or `would_reduce_to` field changed.
  - CoO: `abb0d72429bddc3c79e2d6e128b3e6133225c3d24ed294c7b9d3d483171a219f` → `8d4a1c976fda9e0f5dd2c6ffa91dd9060e3025e8c85e9c11a0ce1755704517a6`.
  - NiO: `025eb503d31cdc579afc3d9a4ae5bec6e968369684c7ea55c392965d1155f8a5` → `50336a4aeb3769109c3a68825758fb55e27577546d44101723040441d3f02449`.
  - FeO: `e59300867a624a406b4d7ad7198fbdd8c730f788f3804aeae36a0867e675cab7` → `3f1f8d3cba95ad3a32ea6010befc10049d75894996dbb8860be4c12ae624c158`.
  - Cu3N: `5c435dbe3196a16538ee2f866761cfea1ea180eb44297fafb17d705b78513b8e` → `af3bd903e7a02e82e16db73527e77a97ac5a60145022ef31544b58eb9e21c600`.
- WSL replay manifest differences were exactly the three authorized paths: `campaign.lock`, `campaign.v2.json`, and `resolved_perturbation_plan.json`. Only identity/F2-derived content and hashes changed; analysis equivalence, Part A U and I.5 assertions remained unchanged. The separate JSON snapshot is diagnostic and was regenerated.
  - Manifest file SHA-256: `7644a7f7abda043e851a1bc1cd30e19ad3edffffe35ca77b080bd29e8ca656a9` → `af86fdfa99c330548b9729ccc4f7533f60f594068dbd0dcd61c17e9906e55cbf`.
  - Snapshot file SHA-256: `a3825081551d2fb1bf18d459c65ea0688b60cbcfcb7dabf1224676538a7b167b` → `5fa071aef8590afb309a2e1c1ddadcc5a53fafbd2656f08aba24860e5501a758`.
  - Manifest entries: `campaign.lock` `468dfbc57ffb5952a9713dd1a8289e8d3ebd0ca9b1c9ee3b0bb2979ef9c9d892` → `d86108fbcf1d6e5d3206b98b512209e7c300368469c9fcbf750bb123d7588951`; `campaign.v2.json` `b018826f0fecffb5355db50eb81f44271ba76b950f3e2a8b072988ea7e3a4367` → `561fb80c765aaa58c2c938710688b853ca2f5a091d824f6697f9c06020265f08`; plan `3d201d120b6257f41982bded0f5ac3518a4aa4d246e74bbc89a0b925630acd3a` → `96ed7660e4f951114e8b9dcd292ea822e10619dd962d2ad257e5ae5fa3893726`.

### Verification so far

- Focused parser/planner/symmetry/product modules: 151 passed, 2 warnings. The final added absent-mapped-file case was separately run in the 19-test FDF module, which passed.
- NiO P5 replay in WSL after the authorized golden update: 7 passed, 2 existing deprecation warnings.
- Coverage and 20.9 golden tests: 52 passed, 2 warnings.
- Legacy resume plus campaign planning tests: 29 passed, 2 warnings.
- `verificador_luna` approved the final scope, including the tested conservative conflict handling; `auditor_cientifico` found no scientific blocker.

### Post-commit gates for 23.1 (`7bf8ac6`)

- WSL NiO P5 replay: 7 passed; golden 20.9: 4 passed; product group: 112 passed; scientific regressions: 70 passed; architecture: 8 passed.
- `ruff check .`: passed; `ruff format --check .`: 91 files already formatted; `MYPYPATH=src mypy`: success on 91 files; V6 gate: `V6 GATE OK`.
- Full suite: 1404 passed, 27 skipped, 20 xfailed, 4 subtests passed, 2 warnings.
- No post-commit failures or additional edits were needed.

## 23.2 I.5 shadow state gate

### Premise checks

- `rg -n "def _complete_state_gate|_complete_state_gate\\(|state_gate_mapping\\(" src/hubbardflow tests/unit/test_campaign_shadow.py` confirmed that the production gate returned `False`, `_outcomes` and `analysis_data` called it without a runner, and the synthetic test oracle was `lambda: True`.
- `rg -n "covered=not adaptive|def state_gate_mapping|class StateGateReason" src/hubbardflow` confirmed that the direct-analysis caller excluded TS (`covered=False`), the mapping had no column-index filter, and the reason enum had no reconstructed-column code.
- Independent `auditor_cientifico` read-only checks on archived MnO A/B × both modes × all six signed α found 4/4 PASS verdicts; point checks were G1 PASS=24, G2 PASS=768, G3a PASS=768, G4 NOT_AVAILABLE=24. This confirms that D14b must block the archived points absent `.EIG` for a production shadow proof.
- The same audit checked real NiO fixtures with and without `.EIG`: with `.EIG`, all four pairs and their point checks pass; without it, all four diagnostic verdicts still PASS while G4 is NOT_AVAILABLE=24. `tests/fixtures/replay_nio_p5/replay_i5_state_gate.json` has the latter structure. A 16-column replay mapping also confirmed that unfiltered reconstructed columns appear as failures due to absent validated nodes.
- The auditor verified index correspondence at `campaign_runner.py` by mapping `plan.inventory.subspaces` to runner sites by index, while plan `site_id` and runner labels intentionally differ. No premise was false. The existing `_response_node` alpha locator tolerance (`1e-14`) was noted as pre-existing and outside this item.

### Conservative decisions and edits

- Keep `site_indices=None` behavior unchanged. With a filter, mark excluded columns as `NOT_ESTABLISHED/RECONSTRUCTED_FROM_REPRESENTATIVE` without evaluating their nodes.
- The shadow gate requires both modes for every computed/expanded runner label, verdict `PASS`, at least one amplitude and both signed point records, and rejects point checks `FAIL`, `NOT_AVAILABLE`, or `NOT_ESTABLISHED`. `NOT_DEFINED` and `NOT_APPLICABLE` remain allowed. Reject malformed and duplicate pairs. Exclude the separate G3 smoothness result as D14b directs.
- 23.2 test edits: added `tests/unit/test_shadow_state_gate.py` for synthetic all-pass, G4 unavailable, failure, missing pair, allowed NOT_DEFINED, duplicates, real NiO `.EIG` fixtures passing the gate, actual NiO replay golden rejection, and reconstructed index filtering; adapted only the authorized R5 oracle signature in `test_campaign_shadow.py` from `lambda: True` to `lambda *_: True`. No golden files changed.
- Production changes are limited to `state_gate_results.py`, `state_gate_step.py`, `campaign_shadow.py`, and `campaign_runner.py`: wire index filtering into the TS diagnostic, compute the gate from current runner evidence, and expose its result in `translation_shadow.complete_state_gate`.
- Focused checks: `python -m pytest -q tests/unit/test_shadow_state_gate.py tests/unit/test_campaign_shadow.py` → 30 passed, 2 pre-existing deprecation warnings; `ruff check` on the new test and state-gate modules passed; `ruff format --check` on the five non-legacy touched Python files passed; `MYPYPATH=src mypy --strict` on `state_gate_results.py`, `state_gate_step.py`, and `campaign_shadow.py` passed; `git diff --check` passed.
- POSIX replay in WSL: `PYTHONPATH=src python3 -m pytest -q tests/integration/test_runner_replay_nio_p5.py` → 7 passed, 2 pre-existing deprecation warnings. Its manifest/golden remained unchanged.
- `verificador_luna` reviewed the diff twice. The first pass requested the explicit real NiO `.EIG` satisfiability case; that test was added and passed. The second pass approved the scope and found no functional blocker. The full legacy `campaign_runner.py` has existing Ruff formatting and strict-mypy findings outside this item’s hunk; no broad formatting/type edits were made.

### Post-commit gates for 23.2 (`36b7796`)

- WSL NiO replay: 7 passed; 20.9 golden: 4 passed; product group: 112 passed; scientific gates (`test_matrix_lr.py`, `test_quantized_response.py`, `test_u_certification.py`): 54 passed; architecture: 8 passed.
- `ruff check .`: passed; `ruff format --check .`: 91 files already formatted; `MYPYPATH=src mypy`: success on 91 files; V6 gate: `V6 GATE OK`.
- Full suite: 1412 passed, 27 skipped, 20 xfailed, 2 warnings in 338.62s. No test failures.
- Golden files remained unchanged.

## 23.3 Product TS admission, parent DM, rejection policy, and dry-run

### Premise checks

- Checked the pre-item source at `a54e9bb` with `git show ... | rg`: `execution_admission` exposed only `ADMISSIBLE_LEGACY_EQUIVALENT`, accepted coverage only from `{DISABLED, DIAGNOSTIC}`, and rejected reduced columns; `product_execution_boundary` exempted only the legacy status; `product_command` launched only for that status and required `--name` whenever `--profile` was supplied. All matched the TASK 23.3 premises.
- Checked `wsl_campaign_init.py` at `a54e9bb` with `git show ... | rg`; both `planning_reference_output` and `planning_reference_dm` were copied into the initialized campaign. `product_cli._verify_campaign_inputs` independently verifies those frozen copies against the source hashes.
- Checked `campaign_runner.py` and `campaign_shadow.py` at `a54e9bb` with `git show ... | rg`: the runner called `reference_completed` after output validation without comparing the DM digest; failed shadows and rejected barriers called expansion directly. These premises were true.
- No premise was false. No real SIESTA campaign was run for 23.3. The main session ran the required POSIX MnO TS replay in WSL with fake SIESTA after implementation.

### Changes and focused verification

- Added an independent TS admission status and fail-closed reasons for inventory/reference/parent-DM/plan reasons/reduction/run-grid/site mapping/reference-DM filename, with no identity-only inventory exemption. The boundary and product command now recognize both admissible statuses while preserving the legacy branch. TS products freeze `shadow_rejection_policy: STOP` after CLI coverage merging; explicit `EXPAND` remains available and omitted keys remain absent on non-TS configs.
- The runner now compares the validated reference DM bytes with the frozen parent digest before `reference_completed`; mismatch records `PARENT_DM_NOT_REPRODUCED` and both digests, then the worker reports that reason and stops before perturbations. Under STOP, rejected shadows persist outcomes and the I.5 mapping, finish `FAILED/SHADOW_REJECTED`, and do not install an expanded DAG. Default runtime policy remains `EXPAND` for existing explicit campaigns.
- Added `run --dry-run`, which requires a profile, skips the name requirement, computes/freezes/reports admission and boundary, and skips campaign initialization and worker launch. Manifest-target commands reject the flag only when it is enabled.
- Added/updated authorized tests in product admission, product CLI, campaign config validation, and campaign shadow STOP behavior. No golden or replay fixture changed.
- Added `tests/integration/test_runner_replay_mno_ts.py` as the item-authorized POSIX integration replay. It adapts the external prototype with `tmp_path`, hashes and registers its fake executable, reuses the planning reference DM bytes, permutes the archived per-atom occupation blocks for shadow columns, and writes identical synthetic insulating band energies on every run. The config carries the declared `magnetic_moment_tolerance_muB: 0.1` I.5 continuity tolerance.
- WSL MnO TS replay: `PYTHONPATH=src /home/jmc/.cache/hubbardflow-task23-venv/bin/python -m pytest -q --basetemp=/tmp/task23-debug4 tests/integration/test_runner_replay_mno_ts.py` → 1 passed, 2 existing deprecation warnings, 59.41s. The production I.5 gate passed without monkeypatching; 49 fake SIESTA invocations completed, both shadows and `complete_state_gate` were `PROVEN`, reconstructed `chi0_raw`/`chi_raw` matched primary matrices at `atol=1e-12`, and U spread in both translation classes was ≤1e-9 eV.
- Focused targeted selection: `python -m pytest -q tests/unit/test_product_admission.py tests/unit/test_product_cli.py::test_legacy_run_still_delegates_to_existing_control tests/unit/test_product_cli.py::test_mno_translation_shadow_product_plan_uses_single_file_species_map tests/unit/test_product_cli.py::test_run_dry_run_requires_profile_but_never_launches tests/unit/test_campaign_plan.py::test_shadow_rejection_policy_is_optional_and_validated tests/unit/test_campaign_shadow.py::test_stop_policy_rejects_shadow_without_installing_expansion tests/unit/test_campaign_shadow.py::test_stop_policy_prepare_rejection_runs_once_and_does_not_expand` → 28 passed, 2 pre-existing deprecation warnings.

### Post-commit gates for 23.3

- Focused golden/product/scientific/architecture selection: 240 passed, 2 existing deprecation warnings.
- WSL replay selection (`test_runner_replay_nio_p5.py` and `test_runner_replay_mno_ts.py`): 8 passed, 2 existing deprecation warnings. MnO TS completed 49 fake SIESTA invocations; the integration assertions confirmed both shadows and the complete I.5 gate were `PROVEN`.
- `ruff check .` passed; `ruff format --check .` reported 91 files already formatted; `bash tools/check_v6_integrity.sh` printed `V6 GATE OK`.
- First `MYPYPATH=src mypy --strict` run found six annotation errors in the newly changed TS admission/tests. Fixed the None narrowing and test doubles/casts; rerun passed with `Success: no issues found in 91 source files`.
- Affected product/shadow tests after the typing fixes: 80 passed, 2 existing deprecation warnings.
- Full suite on the amended 23.3 code: `python -m pytest tests --continue-on-collection-errors` → 1424 passed, 28 skipped, 20 xfailed, 2 existing deprecation warnings in 374.31s. No new failures or known-failure changes.

## 23.4 `hubbardflow reference`

### Premise checks

- `rg -n 'def run_campaign_worker|def advance|mode ==' src/hubbardflow/execution/campaign_runner.py` confirmed that `run_campaign_worker` passes its mode to `advance`, where the prior worker distinguished only `run` and `resume`; premise true.
- `rg -n 'copy2\(self.layout.reference_fdf|reference_dm_name|stdout_path' src/hubbardflow/siesta_backend/command_factory.py src/hubbardflow/execution/campaign_runner.py` confirmed verbatim reference-FDF copying, `layout.reference_dm_name` for the reference DM, and recorded `stdout_path`; premise true.
- `rg -n 'reference_dm_name|reference.DM|required DM artifact' src/hubbardflow/execution/campaign_v2.py src/hubbardflow/siesta_backend/output_validator.py` confirmed the `reference.DM` default and post-run required-artifact validation; premise true. The public shared DM-name helper now rejects mismatches before campaign initialization or worker execution.
- No premise was false. No golden was edited.

### Changes and verification

- Added the `reference` product command. It requires a frozen LR config and profile, admits only `ADMISSIBLE_LEGACY_EQUIVALENT`, initializes a normal direct campaign, executes worker mode `reference`, and archives the validated stdout/DM plus a receipt with the required hashes and provenance. It refuses TS coverage, foreign reference inputs, dry-run and a DM filename inconsistent with the FDF. The shared DM-name helper is used by both TS admission and this command.
- `CampaignRunner.advance("reference")` stops after a validated reference receipt with `STOPPED/reference_only`; unvalidated reference receipts go through the existing failed-node handling. A synthetic resume remains the ordinary full direct run. Added user-guide examples for `reference` then TS `run`, the meaning of `PARENT_DM_NOT_REPRODUCED`, and when to select `DISABLED`.
- Added authorized unit tests in `test_campaign_runner_synthetic.py` and `test_product_cli.py`, and the item-authorized POSIX NiO integration `test_product_reference_nio.py`. The first new failure fixture used nonexistent `NodeState.FAILED`, and then omitted `runner.shadow`; both fixture-only issues were corrected to `FAILED_EXECUTION` and `shadow=None`. The final synthetic file result is 5 passed. No existing assertion was weakened.
- Focused unit selection: `python -m pytest -q tests/unit/test_campaign_runner_synthetic.py tests/unit/test_product_cli.py tests/unit/test_cli_legacy_product_options.py tests/unit/test_product_admission.py` → 73 passed, 2 pre-existing warnings. The added failed-reference test was added afterward and separately passed in the final 5-test synthetic file run.
- Final POSIX replay in WSL: `PYTHONPATH=src /home/jmc/.cache/hubbardflow-task23-venv/bin/python -m pytest -q --basetemp=/tmp/task23-reference-final tests/integration/test_product_reference_nio.py` → 1 passed, 2 pre-existing deprecation warnings. It verifies exactly one fake SIESTA execution, DM SHA256 `f7fca191f941bbda5ee38eb361096aa8a802dfd410e12aaa680f39f3cf2193ef`, exact fixture stdout bytes, and TS follow-up admission with the same parent DM.
- `verificador_luna` reviewed the diff twice. The first review identified failed-reference routing; after preserving the usual FAILED path and adding its regression test, the second review approved the diff. `ruff check .`, `ruff format --check .` (91 files), `MYPYPATH=src mypy --strict` (91 source files), and `git diff --check` passed. No test golden changes.

### Post-commit gates for 23.4 (the final amend changes only this log)

- WSL POSIX replays: NiO P5, MnO TS and product reference → 9 passed, 2 existing deprecation warnings.
- Golden/product/scientific/architecture selection: `test_phase2_golden.py`, product CLI/execution/admission/paths/plan, matrix, quantized response, U certification and architecture → 191 passed, 2 existing warnings.
- `ruff check .` passed; `ruff format --check .` reported 91 files already formatted; `MYPYPATH=src mypy --strict` succeeded on 91 files; V6 gate printed `V6 GATE OK`.
- Full suite: `python -m pytest tests --continue-on-collection-errors` → 1430 passed, 29 skipped, 20 xfailed, 2 existing deprecation warnings in 359.29s. No new failures or known-failure changes.

## 23.5 Compact planning report and reason-derived actions

### Premise checks

- `rg -n 'canonical\(snapshot\.planning\.to_mapping\(\)\)|Production requires the complete FDRC I.5 state producer|Pilot reuse awaits' src/hubbardflow/reporting/product_report.py` confirmed the complete planning JSON was embedded and the I.5/pilot statements were unconditional static text; both premises true.
- `$base = Join-Path $env:TEMP 'task23-235-premise'; python -m pytest -q --basetemp $base tests/unit/test_product_cli.py::test_mno_translation_shadow_product_plan_uses_single_file_species_map` passed against the archived MnO inputs. `Get-Item ...\test_mno_translation_shadow_pr0\product\plan_report.md | Select-Object Length` reported 3,145,305 bytes. The test confirms 16 Mn sites, two translation classes, four computed columns and 48 run specs; no SIESTA was run.
- `rg -n 'Production requires the complete FDRC I.5 state producer|Pilot reuse awaits|Actions required' tests` found no pre-existing test assertion for the removed static prose, so no old expected strings needed edits.
- No premise was false. No JSON artifact, frozen plan, or digest changed.

### Changes and verification

- Replaced embedded planning/coverage JSON with translation-class and operation-summary tables (total/accepted counts, exactness-class counts and first failing condition counts). The report links to `resolved_perturbation_plan.json` and `product_plan.json`, displays execution-admission status/reasons from its serialized boundary, and keeps full evidence untouched.
- Replaced static action prose with steps derived from product, inventory, plan, coverage and admission reason codes. Species-identity guidance names missing/mismatched pseudopotentials, blocks outside the species-neutral allowlist, and enabled `User.Basis` directives as causes to check; the frozen report contract does not retain which specific cause applied. An admissible TS boundary reports that the command is ready with `--profile`.
- F-condition failures are counted separately from rejected operations whose conditions did not fail, so policy reasons are not mislabeled as failed conditions. Updated only the authorized MnO product-CLI test to compare the complete exactness and first-failure tables with the typed qualification, along with report size, classes, links, admission and fenced-block checks. No prior assertion was weakened and no golden was edited.
- `python -m pytest -q tests/unit/test_product_cli.py::test_mno_translation_shadow_product_plan_uses_single_file_species_map` → 1 passed, 2 existing warnings. `ruff check` and `ruff format --check` on report/test passed; `MYPYPATH=src mypy --strict src/hubbardflow/reporting/product_report.py` passed; `git diff --check` passed. `verificador_luna` reviewed the diff and approved after these corrections.

### Post-commit gates for 23.5 (the final amend changes only this log)

- WSL POSIX replays: NiO P5, MnO TS and product reference → 9 passed, 2 existing deprecation warnings. The MnO TS replay passed, satisfying the prerequisite for item 23.6.
- Golden/product/scientific/architecture selection, including product-report atomic tests → 193 passed, 2 existing warnings.
- `ruff check .` passed; `ruff format --check .` reported 91 files already formatted; `MYPYPATH=src mypy --strict` succeeded on 91 files; V6 gate printed `V6 GATE OK`.
- Full suite: `python -m pytest tests --continue-on-collection-errors` → 1430 passed, 29 skipped, 20 xfailed, 2 existing deprecation warnings in 351.91s. No new failures or known-failure changes.

## 23.6 — MnO real campaign PAUSADO

- Campaign: `/home/jmc/hubbardflow_validation/mno_ts_20261004/campaigns/mno_ts/campaign.v2.json`; frozen runtime imported `/home/jmc/hubbardflow_validation/code_1623d91/src/hubbardflow/__init__.py` with `PYTHONPATH=/home/jmc/hubbardflow_validation/code_1623d91/src`. Campaign ID `2ae5987c-67fd-4a7a-9e14-45d2edc751a0`.
- Safe-stop request issued with `hubbardflow stop` at **2026-10-05T03:18:21Z / 2026-10-04 21:18:21 -0600**. The status snapshot at the request had 22/48 response nodes complete (23 completed DAG nodes including `reference`), active node `response:lr_s001_p0p05_screened`, and that node was in SCF iteration 5. The CLI requests a stop at a node boundary, so the active node was allowed to finish and no following response node was started.
- Exact safe-stop result: `status=STOPPED`, `stop_reason=safe_stop_requested`, `active_node=null`, `current_node_state=VALIDATED`, `heartbeat_utc=2026-10-05T03:53:18Z / 2026-10-04 21:53:18 -0600`. There are 24 completed DAG nodes including `reference`, hence **23/48 response nodes validated**. The just-finished node was `response:lr_s001_p0p05_screened`; its `siesta.out` contains 10 SCF iterations and ends `4-OCT-2026 21:53:18`. At the final boundary no response node was in progress. Total campaign wall time from recorded start to stop was 65,509.63 s (18 h 11 min 49.63 s).
- A new WSL shell at 2026-10-04T21:57:09-06:00 queried `hubbardflow status`: it still reported the same `STOPPED` state, 23/48 response nodes, and no active node. The fresh-shell process scan had no SIESTA (`siesta`), MPI launcher (`orterun`), or campaign worker; its only textual match was the shell running the status/process query itself. The status heartbeat and validated node output also show that no subsequent node was launched.
- Previously recorded setup evidence remains: reference DM SHA-256 `c8fae5a1f51f7b256bc9e474feab80155f4b3665ba8599f9f8516620ff0587d1`, matching the planning reference DM and differing from archived parent DM `65d418d1a21b4b4052d41d68554639fc4bc4682566bb780c0d072fd4cfe5eb47`; the MnO TS plan had 2 classes, 4 computed columns and 48 response runs. The POSIX MnO TS replay prerequisite passed in 23.3.
- This is a **PAUSA**, not a campaign validation verdict. Real-campaign gates a–e have not been evaluated, no real-campaign U table or TS fixture was produced, and the campaign was not resumed. Do not classify this as `TS_NOT_VALIDATED`.
