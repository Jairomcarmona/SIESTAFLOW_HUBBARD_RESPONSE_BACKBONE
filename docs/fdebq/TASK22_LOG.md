# TASK 22 — premises, edits, and gates log

## Base and branch

- `git fetch` → advanced `origin/codex/hubbardflow-rename` from `041adf8` to `299b8f0db44ba385c36d7b0fcef54639f1bcffb7`.
- `git rev-parse codex/hubbardflow-rename` → `241d009b92d39519b9a308284c783add94849625` (premise false only for the local ref; recorded in `BLOCKERS.md`).
- `git rev-parse origin/codex/hubbardflow-rename` and `git show -s --format='%H%n%s' 299b8f0` → `299b8f0db44ba385c36d7b0fcef54639f1bcffb7`, merge of PR #8. The TASK 22 branch was created directly from that verified commit.
- The initial documentation commit `3c0b8ca` contains only the specification copy and `AMENDMENTS_2.md`. The source and copy of `CODEX_TASK22_I5.md` matched at SHA-256 `C751DC106DFBB9BB99D2B54870FE4386668B5E4E367C096E9E51FBA5D1B82B79`.

## Baseline gates after the documentation commit

- `python -m pytest tests/unit/test_phase2_golden.py -q` → `4 passed`.
- `python -m pytest tests/unit/test_product_cli.py tests/unit/test_product_execution.py tests/unit/test_product_admission.py tests/unit/test_product_paths.py tests/unit/test_campaign_plan.py -q` → `109 passed`.
- 70 scientific regressions (`test_lr_analysis_v2.py`, `test_matrix_lr.py`, `test_quantized_response.py`, `test_u_certification.py`) → `70 passed`.
- `python -m pytest -q tests/unit/test_import_architecture.py` → `8 passed`.
- `python -m pytest tests -q -rfE --continue-on-collection-errors` → `1367 passed, 25 skipped, 20 xfailed, 4 subtests passed`; no active failures or collection errors.
- `ruff check .` → `All checks passed!`; `ruff format --check .` → `91 files already formatted`; `MYPYPATH=src mypy` → `Success: no issues found in 91 source files`; `bash tools/check_v6_integrity.sh` → `V6 GATE OK`.
- POSIX replay in WSL, with `PYTHONPATH=src python -m pytest tests/integration/test_runner_replay_nio_p5.py -q` → `7 passed` in 11.46 s. The first invocation without `PYTHONPATH=src` did not import the package; it was repeated with the correct environment and passed.

## 22.1 — verified premises

| Premise | Command run | Result |
|---|---|---|
| `_failed_receipt` stores only the digest; if stdout goes to a file, `CompletedProcess.stdout` is empty | `Get-Content src/hubbardflow/execution/runtime_adapters.py | Select-Object -First 150` | The original function constructed `NodeReceipt(node_id, FAILED_EXECUTION, digest)`; `run` redirected to handles and enabled `capture_output` only if both were absent. |
| The runner accepts `extra` and the store merges it into the node record | `Get-Content src/hubbardflow/execution/campaign_store.py | Select-Object -Skip 74 -First 18` | `**dict(extra or {})` in the record. |
| `status` prints `campaign_status`, and the worker state is the output object | `Select-String -Path src/hubbardflow/cli.py -Pattern 'campaign_status\|worker-state' -Context 2,4` | The `status` command calls `json.dumps(campaign_status(...))`; `campaign_status` loads `.siestaflow/worker-state.json`. |
| An execution failure finishes the heartbeat with FAILED state | `Select-String -Path src/hubbardflow/execution/campaign_runner.py -Pattern 'heartbeat.finish' -Context 2,5` | The failed-node path calls `heartbeat.finish("FAILED", failed_node=..., failure_state=...)`. |

TASK 22.1 test changes: `tests/unit/test_runtime_adapters.py` was extended for exit code 3 (`EXIT`), direct SIGTERM (`SIGNAL:SIGTERM`), launcher script with 143 (`PROBABLE_SIGNAL:SIGTERM`), synthetic OSError (`SYNTHETIC_OSERROR`), exit code 255 (`EXIT`), stdout/stderr queues limited to the last 20 lines, argv, legacy digest under partial redirection, and absence of `failure.json` on success. Windows skips the two cases depending on POSIX conventions; they run in CI/WSL. Conservative decision: when one stream is redirected, capture the other for `failure.json` and replay it to the parent stream after the process exits. The digest and validator object retain historical fields; only the timing/interleaving of diagnostic output changes.

Focused gates before commit: `python -m pytest tests/unit/test_runtime_adapters.py -q` on Windows → `6 passed, 2 skipped`; on POSIX WSL → `8 passed`; `ruff format --check` on new/edited files → passed; `ruff check` for unused imports/types → passed; `MYPYPATH=src mypy --strict src/hubbardflow/execution/runtime_adapters.py` → `Success: no issues found in 1 source file`.

## 22.2 — verified premises

- `Select-String` and reading `campaign_plan.py` confirmed `planner_version="campaign-planner-v3"` in planning.
- `verify_frozen_campaign_plan` read `resolved_perturbation_plan.json`, called `from_mapping`, and recomputed the plan in the same `try`; the `except` converted the error to `cannot resume frozen campaign plan: ...`.
- The test for a change to `campaign-planner-v2` will be added in item 22.2.

## 22.3 — premises verified with real NiO P5

- WSL checked 25 outputs and 25 `.EIG` files in `~/.local/state/siestaflow/campaigns/nio_p5_product_2/.siestaflow/attempts`: 1 reference, 12 BARE, 12 SCREENED.
- A read audit using the current selectors across 24 runs found that each selection corresponds to a parser event; two atoms, symmetric up/down matrices, and 25 rows per atom with five decimal places. Result: `{'bare': 12, 'screened': 12, 'reference': 1}`.
- `campaign_runner.py` and `observation_assembly.py` use `bare_profile.select_response(...).response_event` and `select_converged_screened_event(...)`, the same selectors used for evidence and U observations.
- `grep` of the real output showed `Occupations:`, `Mulliken Atomic Populations:`, and `siesta: Fermi = -4.508514` blocks; the moment parser reads the last complete Mulliken table.
- The `.EIG` format was read from real runs and validated against its blocks: the second line `64 2 23` means **64 bands, 2 spins, 23 k-points**; each point contains `64 × 2 = 128` energies. Energies are printed with nine mantissa decimals, so the absolute quantum depends on the exponent (`10^(exponent−9) eV`); it is not always `1e-9 eV`.
- `find tests/fixtures/replay_nio_p5 -name '*.EIG'` → `0`; replay espera G4 `NOT_AVAILABLE`.

Three literal lines from the reference `.EIG`:

```text
 -0.452324875E+01
         64 2         23
         1  -0.108718534E+03  -0.107059529E+03  -0.691704785E+02  -0.691578668E+02  -0.691460532E+02  -0.674318434E+02  -0.674274514E+02  -0.674117503E+02  -0.240555051E+02  -0.232498013E+02
```

### 22.3 — re-verification performed

| Premise | Actual command | Result |
|---|---|---|
| Each atom in the selected event has 25 symmetric up/down rows with five decimals | WSL reader over the 25 `nio_p5_product_2` outputs using `parse_hubbard_population_events` and BARE/SCREENED selectors; counts blocks/rows and compares transposed matrices | 1 reference, 12 BARE, 12 SCREENED; each selected event has 2 atoms, 25 rows per atom, and symmetric matrices. |
| The evidence event matches the U event | `rg -n 'select_response|select_converged_screened_event' src/hubbardflow/execution/campaign_runner.py src/hubbardflow/execution/observation_assembly.py` and actual comparison of selector/parser ranges | Both paths call the BARE profile selector and converged SCREENED selector; the 24 selected events match parsed events. |
| Final output contains printable Mulliken, Occupations, and Fermi data | WSL `grep` of real product `siesta.out`; `python -m pytest tests/unit/test_point_state_evidence.py -q` then consumes the real reference, BARE, and SCREENED outputs | Mulliken tables, `Occupations:` traces, and `siesta: Fermi = ...` are present. All three traces for each spin are within ≤`2.55e-5` of the printed line. |
| `.EIG` layout declares dimensions and supports decimal quantum | WSL `sed -n '1,12p'` of real `.EIG`; script counts block starts/energies; fixture tests | `64 2 23` = 64 bands × 2 spins × 23 k-points; 128 energies per k-point. Quantum is derived per token from the exponent. |
| Reference and two runs can be tested without accessing the local campaign | Compressed real reference, BARE, and SCREENED outputs in `tests/fixtures/i5_eig/*.xz`; `python -m pytest tests/unit/test_point_state_evidence.py -q` | `6 passed`, including reference state, BARE, SCREENED, missing EIG, truncated occupation block, and Mulliken table without terminator. |

Dependency decision to keep the item compilable: in 22.3, `domain/state_gate.py` introduces only the frozen input records (`PointState`, `AtomPointState`, energies, and EIG availability) that the parser must return. Policy/verdict logic remains entirely reserved for commit 22.4.

Real fixtures added by 22.3 under `tests/fixtures/i5_eig/`: `.EIG.xz` and corresponding `siesta.out.xz` for the reference, BARE +0.04, and SCREENED −0.04; they remain outside `replay_nio_p5/`. Adding the three compressed outputs is the smallest conservative expansion that allows portable tests of selected events, traces, and real Mulliken data alongside `.EIG`; it does not change replay or golden. The replay fixture did not receive `.EIG` files.

The `verificador_luna` review found that a final Mulliken table without a closing separator could leave an earlier complete table as a fallback. The parser was fixed to reject that output, and `test_unterminated_final_mulliken_table_raises_typed_error` was added; the verifier confirmed the fix closes the finding and the log records all six focused tests.

### 22.3 gates before commit

- Focused: `python -m pytest tests/unit/test_point_state_evidence.py -q` → `6 passed`.
- POSIX replay in WSL: `PYTHONPATH=src python -m pytest tests/integration/test_runner_replay_nio_p5.py -q` → `7 passed`.
- Golden 20.9: `python -m pytest tests/unit/test_phase2_golden.py -q` → `4 passed`.
- Product: CLI, execution, admission, paths, and plan → `110 passed`.
- Scientific regressions: the four analysis/matrix/quantized/U modules → `70 passed`.
- Architecture: `8 passed`.
- Suite: `python -m pytest tests -q -rfE --continue-on-collection-errors` → `1377 passed, 27 skipped, 20 xfailed, 4 subtests passed`; no new failures.
- `ruff check .` → `All checks passed!`; `ruff format --check .` → `91 files already formatted`; `MYPYPATH=src mypy` → `Success: no issues found in 91 source files`; `bash tools/check_v6_integrity.sh` → `V6 GATE OK`.


22.1 POSIX-specific tests in WSL: `PYTHONPATH=src python -m pytest tests/unit/test_runtime_adapters.py -q` → `8 passed` (includes direct SIGTERM and launcher 143).

## Addendum: commit 22.1 gates (`c397fb1`)

- 20.9 golden: `4 passed`.
- Product/campaign tests: `109 passed`.
- 70 scientific regressions: `70 passed`.
- Architecture: `8 passed`.
- WSL POSIX replay: `7 passed`.
- Full suite: `1370 passed, 27 skipped, 20 xfailed, 4 subtests passed`.
- `ruff check .`, `ruff format --check .`, `MYPYPATH=src mypy`, and V6: all pass (`V6 GATE OK`).

## 22.2 — pre-implementation verification

Command `rg -n 'campaign-planner-v3|def verify_frozen_campaign_plan' src/hubbardflow/execution/campaign_plan.py` confirmed the literal version `campaign-planner-v3` and requested function. Direct inspection confirmed `from_mapping` and recomputation ran inside the `try`, whose `except` converted exceptions to `cannot resume frozen campaign plan: ...`. No golden is needed or changed.

Authorized edit added: `tests/unit/test_campaign_plan.py::test_resume_reports_explicit_planner_version_change` changes only the frozen plan version to `campaign-planner-v2` and requires the literal error `PLANNER_VERSION_CHANGED`, both versions, and the instruction to reinitialize. No existing assertions were edited.

Local item verification: `python -m pytest tests/unit/test_campaign_plan.py -q` → `28 passed`; `MYPYPATH=src mypy --strict src/hubbardflow/execution/campaign_plan.py` → `Success: no issues found in 1 source file`.

## 22.4 — scientific clarifications pending from the author

The independent scientific auditor reviewed TASK 22 §22.4, D13a–c, and sections I, J, K, M, and O of the review. Before implementing 22.4, the author must resolve the following two rules; no 22.4 logic was changed.

### G2 question: which margin defines the reference k

**Specification text.** `CODEX_TASK22_I5.md:176–183` defines `k` from the reference spectrum and, in addition to a unique/resolved gap, requires that “the margin ε below is < 1/2”. However, the only formula for `ε`, at `:191–193`, depends on both `Δ_ref` and `Δ_pt`; `Δ_pt` belongs to a specific amplitude point. Then `:184–189` again uses point properties to decide whether it fails.

**Possible interpretations and verdict change.**

1. Define `k` using a reference-only margin, equivalent to comparing the reference with itself: `ε_ref = 2·[W/(Δ_ref−2W) + W/(Δ_ref−2W)] = 4W/(Δ_ref−2W)`. If `ε_ref < 1/2`, fix `k`; then evaluate the full margin for each reference–point pair. In the audited example, the point has a unique split at the same index and identical basis (`c=1`), but the full margin exceeds 1/2, so the result is `SUBSPACE_AMBIGUOUS` (diagnostic failure).
2. Apply the full point-dependent `ε` literally to the definition of `k`. In the same example, `ε<1/2` does not define `k`; the result becomes `NOT_DEFINED`, which the rule declares non-failing. This reading can hide exactly the point ambiguity at issue.

**Numerical example verified by the auditor:** `W=2.5e−5`, `Δ_ref=0.1`, `Δ_pt=1.1e−4`, point's second gap `1e−6`, identical basis (`c=1`). Comparing the reference with itself gives `ε_ref=0.00100050025`; the pair margin gives `ε=0.83383358346`. Thus, the two readings yield `SUBSPACE_AMBIGUOUS` versus `NOT_DEFINED`. Specification evidence: `CODEX_TASK22_I5.md:176–193`; the calculation is recorded in the independent TASK 22 scientific audit.

**Decision required:** confirm whether the definition criterion uses `ε_ref = 4W/(Δ_ref−2W)` and whether an insufficient full margin at a point yields `SUBSPACE_AMBIGUOUS`, or specify another rule.

### G4 question: E_F source and precision relative to `.EIG` q

**Specification text.** `CODEX_TASK22_I5.md:139–140` places `E_F` in `PointState`; premise `:131–132` identifies the stdout Fermi (`siesta: Fermi = ...`); but G4 at `:202–208` compares levels and counts bands relative to “own E_F” using a threshold of one `.EIG` print quantum. The specification does not say how to combine the lower precision of stdout E_F with the quantum of `.EIG` energies.

**Possible interpretations and verdict change.**

1. Use stdout E_F (currently read by `point_state_evidence.py:244–249`) and compare distance using only the literal `q_EIG` from `:203` and `:207`. This can treat a level as resolved where interpretation 2 yields `BAND_COUNT_AMBIGUOUS`.
2. Use the `.EIG` header E_F and its printed precision for G4; alternatively, keep stdout E_F and expand the ambiguous region to include its half-width (`5e−7 eV` in the example). The boundary band is considered `BAND_COUNT_AMBIGUOUS`, rather than resolved and potentially `PASS`/`BAND_COUNT_CHANGED`.

**Real evidence.** In `tests/fixtures/i5_eig/bare_p0p04.EIG.xz`, the first line is `-0.450851397E+01` = `−4.508513970 eV`. The corresponding output prints `siesta: Fermi = -4.508514` = `−4.508514 eV`; they differ by `3e−8 eV`. The output half-width is `5e−7 eV`, larger than the quantum for an eigenvalue near that E_F, `1e−8 eV`. The NiO run has a wide gap; the issue affects interpretation in boundary cases. A possible `.EIG`-formatted level, `−0.450851396E+01` = `−4.508513960 eV`, with `q_EIG=1e−8`, is `4e−8` from stdout E_F (resolved under interpretation 1), but exactly `1e−8` from the `.EIG` header (ambiguous if the boundary is inclusive). Format and Fermi evidence are recorded in this log; the current parser calculates distances using stdout E_F (`point_state_evidence.py:231, 244–249`).

**Decision required:** specify whether G4 uses stdout E_F, the `.EIG` header, or includes a margin for E_F uncertainty; also confirm whether the one-quantum boundary is inclusive.

Do not implement G2/G4 or proceed to 22.5/22.6 until the author responds. The review also emphasizes that a TASK 22 `PASS` certifies only the implemented checks: G3 smoothness remains `NOT_ESTABLISHED` under D13a, and no claim will be made about SCF exactness, hysteresis, or energy consistency.

### Author resolution and 22.4 implementation

The author resolved both rules in `AMENDMENTS_2.md` as R11 and R12 (commit `72539b8`). The independent scientific auditor confirmed that these resolutions close the ambiguities and leave no scientific blocker for 22.4.

- **R11/G2:** `k` depends only on the reference: `ε_ref = 4W/(Δ_ref−2W)`, with `Δ1−Δ2 > 4W`, `Δ1 > 4W`, and `ε_ref < 1/2`; if these fail, G2 is `NOT_DEFINED` for that atom/spin. Evaluate the full margin at each point. `ε ≥ 1/2` or a non-unique point separation yields `SUBSPACE_AMBIGUOUS`; if the margin remains valid, strict criteria `c−ε > 1/2` and `c+ε < 1/2` define PASS and `ORBITAL_ORDER_CHANGED`; all other cases are ambiguous. Test `test_r11_reference_defined_k_and_point_margin_is_ambiguous` includes `W=2.5e−5`, `Δ_ref=0.1`, `Δ_pt=1.1e−4`, `c=1` and verifies `SUBSPACE_AMBIGUOUS`.
- **R12/G4:** use E_F and quantum from the `.EIG` header; each eigenvalue retains its token and individual quantum. A band is ambiguous at the inclusive boundary `|ε−E_F| ≤ q(ε)/2+q(E_F)/2`. Reference applicability uses the same rule. Stdout E_F only checks consistency with tolerance stdout half-width + `q(E_F EIG)/2`; an excess yields `NOT_ESTABLISHED:EIG_STDOUT_FERMI_MISMATCH`. Tests cover the auditor's boundary example and the `bare_p0p04` consistency check (difference `3e−8`, tolerance `5e−7+5e−9`).

22.4 edits: `domain/state_gate.py` (input records/wrapper), pure modules `domain/state_gate_eval.py` and `domain/state_gate_results.py`, parser `siesta_backend/point_state_evidence.py`, `tests/unit/test_state_gate.py`, and 50 compressed fixtures from the NiO P5 campaign (reference plus 24 BARE/SCREENED points) in `tests/fixtures/i5_real_nio/`. No goldens or replay fixtures were edited. SIESTA was not run as part of 22.4.

`verificador_luna` reviewed the 22.4 diff. It found that a point with a shifted maximum gap and ε≥1/2 at the reference index must be `SUBSPACE_AMBIGUOUS` under R11; precedence was fixed (first non-unique split, then reference-k margin, then k change), and `test_r11_ambiguous_reference_index_margin_precedes_moved_gap_reason` was added. On the second review, it confirmed the defect was closed and the additional R12 tests for the inclusive reference boundary and `bare_p0p04` match the author's resolution; no blockers remain.

Final focused verification before commit: `python -m pytest tests/unit/test_point_state_evidence.py tests/unit/test_state_gate.py -q` → `24 passed` (2 existing deprecation warnings); `ruff check` on the five item Python files → `All checks passed!`; `ruff format --check` → `5 files already formatted`; `MYPYPATH=src mypy --strict` on the four source modules → `Success: no issues found in 4 source files`.

At this item's commit, all mandatory §0 gates will be rerun and recorded. A global `PASS` remains diagnostic of the implemented checks: G3 remains `NOT_ESTABLISHED:SMOOTHNESS_REQUIRES_SCF_LADDER`; no claim will be made about SCF exactness, hysteresis, or energy consistency.

### Correction found by post-commit 22.4 gates

The first post-commit pass found that the deferred import of `state_gate_eval` still counted as an architecture cycle between `domain/state_gate.py` and `domain/state_gate_eval.py`. Input records were split into `domain/state_gate_types.py`; the evaluator and SIESTA parser import those records directly, while `state_gate.py` retains the public facade. `tests/unit/test_point_state_evidence.py tests/unit/test_state_gate.py tests/unit/test_import_architecture.py` → `32 passed`; ruff reported only formatting/import issues in the restructured files, which were fixed. `verificador_luna` reviewed the split and confirmed it preserves fields/validation, breaks the cycle, and is commit-ready. SIESTA was not run.

The first WSL replay invocation failed because it called `python` (not installed there); `/usr/bin/python3` and `/usr/bin/pytest` were verified. The next full pass will use `python3 -m pytest`; this was an invocation interpreter issue, not a false item premise.

## Full post-commit 22.4 gates (tip `80e2f3b`)

The first pass found and prompted the architecture fix above. After amending the same commit, the full pass was clean: POSIX replay in WSL (`PYTHONPATH=src python3 -m pytest tests/integration/test_runner_replay_nio_p5.py -q`) → `7 passed`; golden 20.9 → `4 passed`; product → `110 passed`; scientific regressions → `70 passed`; architecture → `8 passed`; `ruff check .` → `All checks passed!`; `ruff format --check .` → `91 files already formatted`; `MYPYPATH=src mypy` → `Success: no issues found in 91 source files`; V6 → `V6 GATE OK`; suite → `1395 passed, 27 skipped, 20 xfailed, 2 warnings, 4 subtests passed`. The first WSL call used `python`, which was not installed; the correct repeat used `python3`.

## 22.5 — premises, changes, and verification

Premises verified with actual reads/commands:

- `rg -n 'def _execute_analysis|def _adaptive_final_artifacts|def render_campaign_report|write_lr_u_report|_campaign_file_manifest|_campaign_json_snapshot' ...` located analysis writing followed by report generation in `_execute_analysis`, adaptive artifacts, and rerendering through `hubbardflow report`.
- `rg -n 'command.*cwd|stdout_path|def _matching_response_node|def _reference_node' src/hubbardflow/execution/campaign_runner.py` confirmed records retain `command.cwd`, stdout/FDF paths, and reference/response node selectors.
- `Get-Content src/hubbardflow/execution/campaign_shadow.py` confirmed `_complete_state_gate()` still returns `False`; `CampaignRunner` distinguishes `adaptive_policy` and `shadow`, allowing `PATH_NOT_COVERED` in both paths.
- `rg -n 'lr_u_analysis.v3.json|LR_U_REPORT.v3.md' tests/integration/test_runner_replay_nio_p5.py` confirmed prior manifest and snapshot entries; replay already validates the analysis golden. No premises were false and the manifest was not regenerated.

The new `execution/state_gate_step.py` builds states only from validated receipts, stdout/FDF, and `.EIG` located by `SystemLabel` in `command.cwd`. I.5 output is written to `results/i5_state_gate.json`, separate from analysis and `node-evidence.json`. Adaptive and shadow paths write `NOT_ESTABLISHED:PATH_NOT_COVERED`; read/evaluation/persistence errors remain an unestablished diagnostic and do not interrupt U analysis. The renderer consumes an optional mapping, and `render_campaign_report` rereads the JSON to preserve the section when rerendering.

Authorized test edits: `tests/integration/test_runner_replay_nio_p5.py` excludes `results/i5_state_gate.json` from the file hash and general snapshot, compares it with the new `replay_i5_state_gate.json` using the existing comparator, and requires four PASS pairs, G4 NOT_AVAILABLE, and the section to remain present after rerendering. New golden (no previous hash existed): SHA-256 `326f5f63ecc590d27350493ed28636dfe9a6f8bceb369902124581b61f430404`; no other golden was changed.

Tests before commit 22.5: focused state/parser/report → `40 passed`; POSIX replay in WSL → `7 passed`; `ruff check .` → passed; `ruff format --check .` → 91 files; `MYPYPATH=src mypy` → 91 modules without issues; `mypy --strict` on the new step and records → no issues.

Independent review of 22.5 found that the report hash in `node-evidence.json` would change because of the new section, even though I.5 did not edit that file directly. The fix keeps `report_sha256` as the digest of the canonical analytical report `render_lr_u_report(analysis)` without the diagnostic appendix; this is the same content/hash as before the item. The final Markdown file includes I.5, while `i5_state_gate.json` remains separate. A replay assertion was added to verify that the `matrix-analysis` field matches the canonical render without I.5. `verificador_luna` confirmed the adjustment closes the finding: analysis and node evidence remain comparable/covered, while the new diagnostic is compared against its separate golden. SIESTA was not run.

## 22.6 — real run and documentation

Premises checked with actual WSL commands before execution: `ls -ld` and `find` on `nio_p5_20261003/inputs` confirmed the FDF, LR config, profile, pseudopotentials, and software registry; `sha256sum` verified the FDF (`b4fb34e...`), Ni and O PSML files (`192eb05f...`, `224ded5c...`), compatibility registry (`5189620d...`), and version text (`bb5a9b03...`). The binary's `siesta --version` reported 5.4.2, and `/usr/bin/mpiexec.openmpi` existed. Part A was read directly from `~/.local/state/siestaflow/campaigns/nio_p5_product_2/results/lr_u_analysis.v3.json`; `primary.U_by_site_eV` was 6.864267700049239 and 6.864387475210124 eV. No premises were false.

A new directory, `~/hubbardflow_validation/task22_20261003_0a8a12f`, was created; `git archive 0a8a12f2244cf217d25047ea426c9578073ca00e` was extracted there, and the verified inputs were copied. To keep the campaign, worker, and results inside this directory, only `wsl.workspace_root` was changed in the local copy of `execution_profile.json`; the source input set remained intact. This conservative relocation is recorded as an operational decision. Planning produced 24 run specs from the fixed grid. Execution admission was `ADMISSIBLE_LEGACY_EQUIVALENT`, with no override; the plan remained `NOT_ESTABLISHED`.

It was launched with `setsid nohup ... < /dev/null > product/run.log 2>&1 &`; a new WSL invocation found worker PID 811 alive, along with `orterun` and four SIESTA processes. Campaign `nio_p5_task22_0a8a12f`, id `99494d9a-5875-40d5-9b7e-8e60d2d2f5e1`, using SIESTA 5.4.2/MPI×4, completed with 27 validated nodes. Worker state gives UTC start `2026-10-03T22:52:53.061654Z` and end `2026-10-03T22:57:41.580628Z`. There is no `failure.json`.

The real I.5 JSON is at `~/hubbardflow_validation/task22_20261003_0a8a12f/campaigns/nio_p5_task22_0a8a12f/results/i5_state_gate.json`, SHA-256 `d3eb4ce6e84ee319edc1e96c9fb9d81e3c7dfb88899b0c2eecfdfb04fff83f0c`. The JSON summarizes the four NiLR0/NiLR1 × BARE/SCREENED pairs: all four PASS, amplitudes 0.02/0.04/0.06 eV admitted, none excluded, and G4 APPLICABLE/PASS at all six points per pair. G1/G2/G3a/G4 passed at every point. The full output is not copied into the repository; the external artifact remains in the authorized directory. G3 smoothness remains NOT_ESTABLISHED under D13a. The I.5 failure stop condition did not trigger.

Real run/Part A comparison: the complete `primary` objects from both analysis JSON files were read; they are identical. NiLR0 U is 6.864267700049239 eV and NiLR1 U is 6.864387475210124 eV in both, with ΔU=0. The U matrix is also identical entry by entry. Reproducible report: `TASK22_REAL_RUN.md`.

Item edits: only `TASK22_REAL_RUN.md`, this log, and the “Long campaigns from WSL” section of `USER_GUIDE.md`. No tests or goldens were edited in 22.6. No premises were false.

Post-commit 22.6 gates (documentation tip `71471ee` before the closeout summary): POSIX replay in WSL → `7 passed`; Phase 2 / 20.9 golden → `4 passed`; product/campaign → `110 passed`; scientific regressions → `70 passed`; architecture → `8 passed`; `ruff check .` → `All checks passed!`; `ruff format --check .` → `91 files already formatted`; `MYPYPATH=src mypy` → `Success: no issues found in 91 source files`; `bash tools/check_v6_integrity.sh` → `V6 GATE OK`; `python -m pytest tests -q -rfE --continue-on-collection-errors` → `1395 passed, 27 skipped, 20 xfailed, 2 warnings, 4 subtests passed` in 284.28 s. There were no new failures.
