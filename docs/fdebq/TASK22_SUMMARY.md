# TASK 22 — closeout summary

## Commits by item

| Item | Commit |
|---|---|
| Preparation and D13a–c decisions | `3c0b8ca` |
| 22.1 — exit codes and evidence for failed runs | `c397fb1` |
| 22.2 — explicit planner-version error | `d044deb` |
| 22.3 — parser and I.5 state records | `b54a74c` |
| Scientific questions log | `386dd52` |
| Author's R11/R12 | `72539b8` |
| 22.4 — state gates and tests | `80e2f3b` |
| 22.5 — integration, report, and replay | `0a8a12f` |
| 22.6 — real run and WSL guide | this commit: `docs: record TASK 22 real NiO validation` |

## Test and golden changes

- 22.1 expanded `tests/unit/test_runtime_adapters.py` for nonzero exit, signals/launcher, OSError, stdout/stderr limits, and the failure receipt. POSIX cases were verified in WSL.
- 22.2 added `test_resume_reports_explicit_planner_version_change` in `tests/unit/test_campaign_plan.py`.
- 22.4 added `tests/unit/test_state_gate.py`, tests for R11/R12, and compressed stdout/`.EIG` fixtures from the reference and real NiO points.
- 22.5 updated the replay and added `tests/fixtures/replay_nio_p5/replay_i5_state_gate.json`, SHA-256 `326f5f63ecc590d27350493ed28636dfe9a6f8bceb369902124581b61f430404`. The manifest was not regenerated. No test or golden edits were made in 22.6.

## Conservative decisions

- R11 defines `k` from the reference only and returns `SUBSPACE_AMBIGUOUS` if the point margin is insufficient; R12 uses E_F and the printed quantum in `.EIG`, with an inclusive comparison and a separate check against stdout.
- G3 smoothness remains `NOT_ESTABLISHED:SMOOTHNESS_REQUIRES_SCF_LADDER` under D13a. I.5 remains diagnostic.
- In the real run, only the copied profile changed `wsl.workspace_root` to the new campaign directory so artifacts would remain there.

## Execution and gates

The real campaign in item 22.6 finished COMPLETED, with no `failure.json`; four I.5 pairs PASS, G4 APPLICABLE/PASS, and U identical to Part A (ΔU=0 for both sites). Details and hashes are in [TASK22_REAL_RUN.md](TASK22_REAL_RUN.md).

The local post-commit 22.6 gates are recorded in `TASK22_LOG.md`: replay 7, golden 4, product 110, regressions 70, architecture 8, ruff/format/mypy, V6 `OK`, and suite `1395 passed, 27 skipped, 20 xfailed, 4 subtests`. The final tip is published without a PR and verified with two consecutive green CI runs using `gh run rerun`; their links are provided in the closeout report.
