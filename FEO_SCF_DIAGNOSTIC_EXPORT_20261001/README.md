# FeO SCF diagnostic export

Read-only diagnostic package for baseline commit `03ccd5913abdc6dd0e9e2cb59c0bc7637562c267`, tag `stage-ub-v6-20260930`; SIESTA 5.4.2. Contains copies of source FDFs, outputs, runner error streams when present, run records and referenced PSML files. No original file was edited and no SIESTA calculation was run to prepare this package. DM binary files were not copied.

## Contents

- `feo_pbe/seedDM_converged/`: converged FeO PBE run.
- `feo_pbe/mix001_both_DM_source/`: PBE run that produced the DM used by the converged seed.
- `feo_lru_original/`, `feo_lru_mix001/`, `feo_lru_seedDM/`, `feo_lru_continuation_25pct/`: all four non-converged FeO LR-U runs.
- `nio_lru_control/`: converged NiO LR-U control.
- `FDF_PARAMETER_COMPARISON.md`: literal FDF values, DFTU.Proj transcription, restart evidence, SCF minima and final values.
- `SCF_HISTORY_COMPARISON.csv`: each tenth iteration plus the final 20 consecutive iterations for each failed FeO LR-U run.
- `FDF_DIFFS.md`: full unified text diffs for all four requested pairs.

`siesta.err` is the captured standard-error stream saved by the runner. No separate file literally named `stderr` was present in the source folders. A missing FDF keyword is shown as `NOT_EXPLICIT_IN_FDF`; no implicit default is supplied. For DM presence before launch, `UNKNOWN` means the run record has no prelaunch DM snapshot or seed path; post-run directory presence is not treated as prelaunch evidence.

## Source folders

Copied from `/home/jmc/.local/state/siestaflow/stage-u-b-v6-20260930/observables/`. Relative folder names above identify each original campaign folder.
