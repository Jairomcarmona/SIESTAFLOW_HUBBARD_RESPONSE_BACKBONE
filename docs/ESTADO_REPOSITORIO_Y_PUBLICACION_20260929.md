# Repository Status and Distance from GitHub

**Inspection and publication date:** 2026-09-29. **Scope:** checkout review,
remote-branch verification, file selection, local commit, and publication to a
GitHub branch with a draft PR.

## Immediate conclusion

The SIESTAFLOW closeout work was consolidated on branch
`codex/sync-product-20260929`, which contains implementation 0.1.2, tests,
documentation, and selected NiO results. The branch is published on GitHub via
[draft PR #4](https://github.com/Jairomcarmona/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE/pull/4),
based on `fix/mno-audit-20260925`. **`main` does not yet contain these changes**;
anyone analyzing the code must open the branch or the PR diff.

The starting local branch was `fix/mno-audit-20260925` at
`e53a6b0266bd83e8e41589973c59eb251ce034a7`. A read-only `git ls-remote` query
from the authorized environment confirmed that same SHA for the remote branch
and `bc2d1d0fccb4670476bac22c852476315a660e58` for `main`. A new branch was
prepared from `fix/mno-audit-20260925` so its product diff could be reviewed
separately from earlier PRs.

## Inventory before file selection

| Category | Observed state | Relevance |
|---|---|---|
| Git-tracked files with local modifications | 28 in the complete checkout, including `README.md`, `docs/USER_MANUAL.md`, `pyproject.toml`, CLI, runners, analysis, and tests | They contain part of the 0.1.2 delivery behavior; they are not in `HEAD`. |
| Untracked product modules | 8 under `src/siestaflow_hubbard/`: adaptive control, LR analysis, mesh reproducibility, runner, campaign v2, initialization and WSL supervisor, U report | This is essential code for what the new documentation describes. |
| Untracked tests | 15 under `tests/` in the targeted inspection | They include v3 analysis, runner, adaptation, and reproducibility; they require selection and review before publication. |
| Untracked Markdown documents | At least 16 under `docs/` before this inventory, including the product charter, P0–P6 log, precision contract, quickstart, and context report | The record intended for delivery to ChatGPT cannot be obtained by reading only the remote branch. |
| Local untracked NiO inputs and results | 18 files visible in the targeted folders `campaigns/nio_pbe_adaptive_20260928` and `campaigns/nio_pbe_p5_20260928` | Distinguish inputs/configuration from versioned results; the real P5 OUT/DM files are in WSL and must not be replaced by an incomplete copy. |
| Local wheel | `dist/siestaflow_hubbard-0.1.2-py3-none-any.whl` exists | The wheel’s existence does not prove that the corresponding source code is published on GitHub. |

The local commit selected 73 files. It excluded the modified ZIP, temporary
files, campaigns unrelated to the NiO closeout, and other untracked files. The
included NiO results are locally versioned files; the real P5 OUT/DM files
remain at the documented WSL path and were not replaced with an incomplete
copy.

### Selection verification

- First focused selection of v3 analysis, reproducibility, runner, and CLI:
  **35 passed**.
- Second selection of adaptation, occupation, Cu1, benchmarks, and NiO:
  **40 passed, 2 failed** because test calls treated instance methods as class
  methods. `implementador_luna` fixed only the calls in the two affected files;
  those **8 tests passed** afterward.
- The initial pytest attempts inside the sandbox could not create their
  temporary directory; the same selections were run with a new basetemp in the
  workspace using the authorized environment. No test ran SIESTA.
- The SHA-256 hash of the experimental `f20.12` patch matches the constant
  recorded in the runner. That check validates only file identity; it does not
  make this a portable product path.

Rebuilding the wheel from the prepared commit and exhaustively reviewing remote
CI remain pending. The P6 log retains validation of the wheel built during the
September 28 closeout.

## Scientific and operational status that must accompany publication

The [final P0–P6 log](P0_EXECUTION_20260928.md) documents operational `PASS`
for P0–P6, a scientific Sol audit marked `READY` before P5, one 25-node P5 NiO
campaign, and a 0.1.2 wheel installed on Windows and WSL. Its terminal state is
**`PRODUCT_BLOCKED`**, because the P5 value remains
`NUMERICAL_CANDIDATE_UNASSESSED` / `NOT_ESTABLISHED` relative to the scientific
objective required by the user. The [bottleneck report](INFORME_CONTEXTO_CUELLO_BOTELLA_U_20260929.md)
explains the magnitudes and investigation paths; it does not reopen or approve
a campaign.

Publishing only `README.md` or only the new documents would suggest that GitHub
contains the CLI/v3 analysis they reference. Publishing without the terminal
status would suggest that wheel 0.1.2 implies `PRODUCT_READY`. Both readings
would be inaccurate.

## Minimum coherent unit for a GitHub update

1. **Source code and packaging:** select the modifications under
   `src/siestaflow_hubbard/`, `pyproject.toml`, and the new modules actually
   imported by the public 0.1.2 path; check their import and dependency
   relationships. Record any out-of-scope experimental component.
2. **Tests and evidence:** include the relevant tests for those modules and the
   P0–P6 log with the already documented artifact hashes. Refer to large,
   immutable data and its location without fabricating an incomplete campaign
   file or rewriting historical reports.
3. **User documentation:** include `README.md`, manual, quickstart, changelog,
   product charter, precision contract, and context report with the
   `PRODUCT_BLOCKED` status visible and the portable scope of standard SIESTA.
4. **Review of the selected set:** inspect the final diff and its size, exclude
   build staging and temporary files, and verify that the described 0.1.2
   version can be built from the published sources.
5. **Publication:** the first `git push` was rejected by automatic review
   because the repository is public and explicit authorization to export this
   exact set was still missing. The user later authorized the commit; the branch
   was pushed and [draft PR #4](https://github.com/Jairomcarmona/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE/pull/4)
   was opened. The PR is available for review; it is not merged into `main`.

## Scientific limit for that update

Publishing the repository does not change the scientific result. The
experimental `f20.12` printing path requires a recompiled SIESTA and is outside
the portable product. Alpha, SCF, window, projector, estimator, and criterion
are not changed to obtain a desired U. The ±0.02 eV target is operational and
post hoc; the conservative bound exceeding that value prevents certification
under the current contract, but does not prove that the actual U error exceeds
it.
