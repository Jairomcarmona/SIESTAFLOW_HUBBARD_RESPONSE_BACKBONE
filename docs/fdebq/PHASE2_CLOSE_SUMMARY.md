# Phase 2 close summary

Branch: `fdebq/r3-task20-fixes`
Base: `84b8eb6` (`origin/fdebq/r2-task15-species-split`)

| Item | Status | Auditor / verification | Tests added or edited | Commit |
|---|---|---|---|---|
| 20.1 | Complete | Focused 30 passed; 70 scientific regressions; static gates; V6 passed | Added campaign runner resume tests | Earlier commit on branch |
| 20.2 | Complete after R1 | Auditor `RISK_COVERED`; focused 107 passed, 70 regressions; static gates; V6 passed; label census recorded | Positive read uses unmanaged `Long_Output`; no existing tests edited | `f629220` |
| 20.3 | Stopped | Auditor `RISK_COVERED`; focused gate had two existing-test/spec conflicts | No tests edited; draft code remains in stash | None |
| 20.4 | Stopped | R2 authorizes named real-archive test, but a second synthetic test expects raw-identical invalid aliases to MATCH, contrary to canonical identity | No tests edited | None |
| 20.5 | Stopped | Auditor `RISK_UNCOVERED`: a valid in-band translation candidate is lost by internal enumeration | R3(a) named test edit not attempted; no tests edited | None |
| 20.6 | Complete | Focused 74 passed; POSIX subset 13 passed; V6 and static gates passed | Updated named `test_every_manifest_path_is_rejected_read_only` under the task exception | Earlier commit on branch |
| 20.7 | Complete | Focused 10 passed; static gates and V6 passed | Added product-option rejection coverage | Earlier commit on branch |
| 20.8 | Dependency stopped | Depends on blocked 20.3 and 20.5 | None | None |
| 20.9 | Stopped by R4 | NiO P5 initialization yields 24 rows, but exact `(site, atom, mode, alpha)` differs; CoO/MnO/Cu3N `NOT_COVERED` | No fixtures generated | None |
| 20.11 | Dependency stopped | Requires the 20.5 `campaign-planner-v2` plan | None | None |
| 20.10 | Dependency stopped | Requires 20.5 spglib removal; architecture test not run | None | None |
| TASK 21 | Product-focused gates pass; full suite has one new failure | Product suite 85 passed; 70 regressions passed; Ruff, format, mypy strict and V6 passed | Existing product test suite | Earlier commit on branch |

## Premises false and uncovered risks

No false premise was recorded in the resumed items. 20.5 has an uncovered scientific risk: internal translation enumeration loses the valid t=0.25 candidate described in the execution log. Rotation enumeration without spglib on non-orthogonal lattices is a known conservative Phase 3 savings limitation per R3(b), not an uncovered risk. NiO P5 20.9 stopped on an exact site-ID mismatch under R4. 20.4 and 20.3 are existing-test/specification conflicts; they are not scientific audit verdicts.

## Final test failures compared with BASELINE_FAILURES

The full command was `pytest tests -q -rfE --continue-on-collection-errors` with this checkout's `src` on `PYTHONPATH`. It reported 21 failed, 1288 passed, 24 skipped, 5 collection errors and 4 subtests passed. All five collection errors and all 20 baseline failed test IDs are unchanged. One new failure is present:

- `tests/unit/test_scf_validation.py::test_materializer_rejects_missing_parent_assets_and_unsafe_restart` — expected `File.DM.Init`, received `NOT_ESTABLISHED: source FDF ladder identity cannot be bound: required FDF directive LatticeConstant is missing`.

Therefore the final failure set is not a subset of `BASELINE_FAILURES`. The full exact baseline failure and collection-error lists remain in `PHASE2_CLOSE_LOG.md` §0.2.
