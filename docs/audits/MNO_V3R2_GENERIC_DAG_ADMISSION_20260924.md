# MnO v3r2 admission to the generic scientific DAG — 2026-09-24

## Decision

Do not create or advertise a runnable generic-DAG staging for the archived `response-matrix-foreground-recovery-v4` results. The archived inputs and receipts pass a useful source-consistency audit, but the campaign's real analysis contract is not the generic DAG Gate 4 contract. Converting either campaign status to generic `PASS` would change its scientific meaning. P1-1 remains open until the DAG can preserve and evaluate this campaign's own acceptance states and provenance, or a separately reviewed campaign-specific adapter does so without remapping outcomes.

No campaign, SIESTA run, or new response calculation was started for this review. No legacy `runs/manifest.json`, archived result, or file under `proyectohubbard/` was changed.

## Archived evidence checked

The response lock defines representatives A/B, targets `MnLR00`/`MnLR01`, seven alpha points (`-0.1` through `0.1`), BARE/SCREENED modes, and a 16-component response. The archived `response-receipt.json` contains 29 records: one reference and 28 responses.

The read-only audit found:

- All 28 response output hashes match their receipt records.
- All 28 archived FDFs match the campaign renderer's expected role, mode, target, alpha, and target-only Hubbard shift.
- All 476 response-run PSML files (17 per response) match the campaign source pseudopotentials and their species identities; all 448 projected profiles match the reference profiles.
- Recomputed occupations and moment signatures match all 28 receipt records.
- Every receipt's parent-DM hash identifies `00_REFERENCE/00_REFERENCE.DM`.

This supports consistency of the archived response set. It does not make its result acceptable under another analysis contract. The receipt also does not preserve the parent's input-DM bytes inside each completed child directory: SIESTA may replace the staged child DM with its output. The parent relationship is therefore supported by the receipt and runner provenance, not by treating each final child `.DM` as the original parent input.

## Why the generic DAG cannot accept the result

The generic analysis gate requires `status == PASS` and generic rank/dimension fields (`rank_chi0`, `rank_ch`, and `matrix_dimension`). The campaign's archived `analysis-result.json` is `FAIL` with `SCIENTIFIC_ANALYSIS_FAILED: MATRIX_STABILITY`. The corrected analysis artifact is `REPORTABLE_NUMERICAL_U_INTERVAL`; it reports 28 verified outputs but does not provide the generic PASS/rank contract. The signal-gate artifact is also `FAIL`. None can be translated into generic `PASS` without erasing the campaign's recorded acceptance criteria.

The repository's generic `runs/manifest.json` for this campaign still has 9 legacy entries, whereas the archived receipt has 29 records. The generic installer also expects generic run/algebra entrypoints that the strict v3r2 workflow does not expose as compatible adapters. Pointing the generic analysis hook directly at the strict runner would not satisfy Gate 4.

## Provenance required before a future staging

The archived set audited above is internally consistent, but the current receipt is not a complete input lock for a newly materialized DAG. The strict response runner's `verify()` does not check every campaign-defining field (including `campaign_id`, representatives, zero control, and reconstruction), and its own source hash is not fixed in the software lock. The receipt binds outputs, parent reference-DM identity, and SIESTA/MPI runtime hashes, but does not bind each record's FDF and PSML hashes or the worker/analyzer source. A future staging must hash-bind these per-node inputs and the full runner/analyzer/software lock, then fail closed on any mismatch.

The local execution probe reported by the independent audit found Slurm 23.11.4 on a one-node `local` partition, `srun -N1 -n4 hostname` working, and OpenMPI 4.1.6 `mpiexec -n4 hostname` working; `mpiexec.hydra` was not present. This describes a viable local four-rank OpenMPI launch path, not evidence that the archived response campaign or a generic DAG was executed through Slurm.

## Closure condition

Keep the archived 29-node campaign and its result statuses intact. Resume staging only after a campaign-specific acceptance interface can preserve `FAIL` and `REPORTABLE_NUMERICAL_U_INTERVAL` as distinct states, validate the complete 29-node graph and its exact inputs, and retain the required provenance. Do not produce a runnable-looking staging by manufacturing generic ranks or converting either status to `PASS`.
