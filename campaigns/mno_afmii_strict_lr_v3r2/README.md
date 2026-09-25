# MnO AFM-II strict linear-response campaign (v3r2)

This is a new, pre-execution MnO campaign. It preserves the Cu campaigns and
does not inherit physical observations from v3/v3r1: their interrupted 309--318
calibration chains are forensic evidence only. It freezes the same physical
geometry, FDF controls, pseudopotentials, response grid, and analysis gates.

## Material selection

The frozen input is AFM-II rocksalt MnO in a 2x2x2 magnetic supercell (32
atoms: 16 Mn and 16 O), PBE, DZP, 200 Ry real-space mesh, and a 3x3x3 k-grid.
Mn 3d is addressed through Method-2 DFT+U projectors with CutoffNorm 0.90.
This is the production candidate because it represents an antiferromagnetic
correlated oxide with a localized Mn 3d shell. The two-atom MnO files under
`examples/` and `scratch/phase4_val/` are expressly smoke inputs (SZ, 150 Ry,
one k point) and are evidence of parser/runtime behavior only; they cannot
seed or certify this result.

## Strict v2 contract

The campaign has a fresh reference DM per replica. BARE(alpha=0) and
SCREENED(alpha=0) are separate controls with the same parent DM. Five
independent zero-shift replicas establish intramode repeatability; any BARE--
SCREENED or reference--mode offset is diagnostic only. Response execution is
blocked until this calibration is admitted.

The fixed response grid is -0.10, -0.05, -0.025, 0.0, +0.025, +0.050 and
+0.100 eV for each response mode. The two AFM representative sites MnLR00
(A) and MnLR01 (B) are perturbed; their translated responses reconstruct the
16-site matrix. A value of U is reportable only after a common alpha window,
mode linearity, full rank, and direct inversion succeed. There is no fallback
to a pseudoinverse, regularization, or a numeric noise literal.

## Status

`runs/` contains the frozen AFM-II input provenance only. Results are absent
until the new runner has created independently hashed evidence.

## Execution recovery

The interrupted job 320 is retained under
`results/calibration-replicas-admissible/` as excluded evidence because it was
submitted without the required `OMP_NUM_THREADS=1`.  The only admissible
recovery preflight is `calibration-replicas-admissible-foreground-v3/`: it uses
the shared four-rank Slurm contract (`sbatch --wait` and
`--no-requeue` and `--export=NONE,OMP_NUM_THREADS=1`) for five new independent replicas.  It has
the identical frozen physical input and cannot reuse job 320 or prior receipts.
