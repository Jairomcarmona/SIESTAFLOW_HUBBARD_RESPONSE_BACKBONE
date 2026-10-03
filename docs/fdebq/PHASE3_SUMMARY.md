# FD-EBQ Phase 3 summary

## Items and decisions

| Item / commit | Premise | R5 edits | Conservative decisions |
|---|---|---|---|
| 3.0 — `b981c38` | Capture the Windows and WSL baseline before runner refactoring. | Recorded the same 20 failing test IDs, five collection-error files and four subtests in both environments. | Kept the historical failures as evidence; made no implementation changes. |
| 3.1 — `da48f23` | The real NiO P5 workflow needed a deterministic regression without invoking SIESTA in CI. | Added the hash-verified replay inputs, fixture executables, 27-node run/resume replay and normalized 220-file campaign manifest. | Reused archived outputs and asserted the Part A analysis; replay-only executables never run production SIESTA. |
| 3.2 — `f52d7c2` | CI needed to collect the whole suite while separating established missing-fixture/source failures. | Added the full-suite workflow, explicit test paths and `tests/known_failures.txt` with strict fixture-aware xfails and exact collection ignores. | Each xfail depends on its recorded missing path; the list may only shrink. No test assertion was weakened. |
| 3.3 — `0d0c68a` | Runner environment setup mutated process-global `os.environ` and subprocesses did not receive profile values explicitly. | Added an explicit environment mapping through local and Slurm execution, including `scontrol` and Slurm validation. | `env=None` preserves inherited subprocess behavior; process-global environment remains unchanged. |
| 3.4 — `dd394b1` | Record/checkpoint persistence was embedded in the runner and could retain a stale checkpoint after graph replacement. | Extracted `CampaignStore`; runner delegates persistence, and the store resolves the current checkpoint manager per operation. | Preserved record-before-checkpoint write order and existing campaign bytes. |
| 3.5 — `aa7ffe3` | Observation parsing, source verification and report dataset construction were coupled to `CampaignRunner`; shadow code used private runner methods. | Extracted `ObservationAssembler` and `campaign_files`; kept compatibility delegators/aliases; added real post-expansion assembly coverage and helper tests. | Passed live DAG/specs/records/checkpoint at each call. Did not change scientific analysis or thresholds. |

The separate Part A timing clarification is in commit `55bd9af`. It records
that available timestamps approximately contradict the proposed ordering that
the failed `siesta.out` stopped writing after `wsl.exe` returned. The exact
outer launch transcript and terminal-return timestamp were not preserved, so
the cause remains unproven.

## Runner size

At the 3.4 base (`dd394b1`), `campaign_runner.py` had 2,207 lines and 47
`CampaignRunner` methods. After 3.5 it has 1,892 lines and 49 methods. The two
additional methods are read-only properties for current verified-input hashes
and occupation precision; moved instance methods remain compatibility
delegators.

## Baseline comparison

The 3.0 baseline had 20 failures, five collection errors and four subtests in
each environment. Windows reported 1,350 passed and 24 skipped; WSL reported
1,354 passed and 20 skipped. Those same 20 failure IDs are now strict xfails
when their documented historical paths are absent; the five collection-error
files are ignored only under the recorded missing-source conditions.

After 3.5, Windows reported **1,355 passed, 25 skipped, 20 xfailed and 4
subtests**. WSL reported **1,360 passed, 20 skipped, 20 xfailed and 4
subtests**. There were no active test failures or collection errors. The
POSIX-only NIO P5 replay ran and passed in WSL; Windows skipped that replay.

## Gates and CI

Local acceptance passed: Ruff, Ruff format, configured strict mypy (91 source
files), strict mypy on the extracted modules and their unit test, architecture
tests, focused observation/shadow/parser tests, the NIO P5 replay and
`tools/check_v6_integrity.sh` (`V6 GATE OK`). No production SIESTA campaign
was run during Part B.

Branch `fdebq/r5-phase3-runner` was pushed to `origin`; no pull request was
opened. Backend admission contracts passed in [run 37126972301](https://github.com/Jairomcarmona/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE/actions/runs/37126972301).
The first full-suite run, [37126972331](https://github.com/Jairomcarmona/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE/actions/runs/37126972331),
failed when the POSIX replay worker returned exit code 1. The second run,
[37127386784](https://github.com/Jairomcarmona/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE/actions/runs/37127386784),
failed at the same assertion. Commit `350ee3d` added worker-state diagnostics;
the third run, [37127793277](https://github.com/Jairomcarmona/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE/actions/runs/37127793277),
showed `reference: FAILED_EXECUTION`, empty `siesta.out`/`siesta.err`, and no
`worker-error.json`. Both replay commands are launched directly, but Git
recorded their fixture files with mode `100644`, so GitHub's Linux checkout
could not execute them. The correction stages both fixtures as `100755` and
asserts their POSIX executable bits. The replay passes locally in WSL after
the mode change; CI for that correction was pending when this summary was
drafted.




The executable-mode correction reached CI in run [37128408454](https://github.com/Jairomcarmona/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE/actions/runs/37128408454): the replay now executes, but the golden manifest comparison found four environment-bound hashes differing because the fixture included absolute checkout paths. The replay comparison normalizes the repository root in JSON and text artifacts. Run [37129336376](https://github.com/Jairomcarmona/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE/actions/runs/37129336376) narrowed the remaining difference to rendered SHA-256 tokens in the Markdown report. Those repeated tokens are normalized while the underlying artifacts remain checked individually. The final workflow [37130085205](https://github.com/Jairomcarmona/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE/actions/runs/37130085205) passed: 1,360 passed, 20 skipped, 20 xfailed; lint, formatting, strict typing, import architecture, and V6 integrity also passed.

The documentation-only commit triggered run [37130568918](https://github.com/Jairomcarmona/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE/actions/runs/37130568918), which exposed cross-platform last-digit floating-point differences in the replay analysis comparison. An interim renderer-precision comparison was superseded after run [37131574963](https://github.com/Jairomcarmona/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE/actions/runs/37131574963) found a physical sensitivity value on a rounding boundary. The final category-aware comparator and its platform reproducibility tolerances are documented below.

The replay comparison now uses one recursive comparator for Part A and a frozen WSL analysis snapshot. It checks structure and categorical fields exactly, uses `math.isclose(rel_tol=1e-9, abs_tol=1e-12)` for physical floats and `math.isclose(rel_tol=1e-6, abs_tol=1e-12)` for diagnostics, and verifies replay U against its own per-site print-rounding half-width. These reproduce cross-platform numeric variation, not scientific cutoffs: measured maxima were 2.6e-11 relative for physical results and 1.4e-9 for ill-conditioned diagnostics (including NumPy 2.5). The derived analysis JSON and Markdown must exist and be non-empty but are omitted from the byte-hash manifest; the JSON is checked against `replay_analysis.v3.json` using the shared comparator. Other manifest JSON values remain byte-exact: planner estimator weights now use exact rational functionals and `campaign-planner-v3`, removing the CPU/BLAS-dependent plan hashes. `campaign_json_snapshot.json` records normalized JSON values so manifest failures print up to ten differing paths and their actual/expected values per JSON artifact. Comparator tests cover float tolerances, exact state/decision fields, missing nodes/rows, and bounded JSON mismatch diagnostics.
