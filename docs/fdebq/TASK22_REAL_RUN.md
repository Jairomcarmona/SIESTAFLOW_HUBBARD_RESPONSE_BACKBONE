# TASK 22 — real NiO P5 run

## Identity and execution

- Frozen tip: `fdebq/r6-task22-i5`, `0a8a12f2244cf217d25047ea426c9578073ca00e`.
- New validation directory: `/home/jmc/hubbardflow_validation/task22_20261003_0a8a12f/`.
- Code frozen from that commit in `code/`; inputs copied from `/home/jmc/hubbardflow_validation/nio_p5_20261003/inputs/`.
- Campaign: `nio_p5_task22_0a8a12f`; id `99494d9a-5875-40d5-9b7e-8e60d2d2f5e1`.
- SIESTA `5.4.2`, four MPI ranks (`/usr/bin/orterun --host localhost:4 --map-by ppr:4:node -np 4 /home/jmc/.local/siesta-5.4.2-openmpi/bin/siesta`).
- Worker: PID `811`, final state `COMPLETED`, 27 validated nodes. Start `2026-10-03T22:52:53.061654Z`; last heartbeat `2026-10-03T22:57:41.580628Z`.
- The launch used `setsid nohup … < /dev/null > log 2>&1 &`. It was verified from a new WSL invocation with `ps`: the worker, `orterun`, and four SIESTA processes were still alive. The log is at `product/run.log` in the directory above.
- The copied execution profile changed only `wsl.workspace_root`, from the shared store to `.../task22_20261003_0a8a12f/campaigns`. This kept the manifests, nodes, and artifacts for this run under the newly authorized directory. The FDF, LR config, and other inputs were preserved byte for byte; the source paths declared by the LR config still point to the verified inputs.
- The execution request was `ADMISSIBLE_LEGACY_EQUIVALENT`; the plan retains `NOT_ESTABLISHED`, and no override was used. The run finished without `failure.json`.

## Input premises

The prepared FDF has SHA-256 `b4fb34e642d862be6949a5b2033a60c5b9fcae56119879583bb3eaf237620ee7`. Copies of NiLR0 and NiLR1 share SHA-256 `192eb05ffb64671715e570e2ca9a99a551cf15544984592082d43004f8554e06`; O has SHA-256 `224ded5c59176d9bcb76d19b7a4a68a48d5dffabf8b262f64d5760250e87c35e`. The compatibility registry has `5189620dfa1e8b6090cbdbb9c36c412835d16feb5c50bbc82b16c139d3bcff2e`; `siesta_version.txt` has SHA-256 `bb5a9b03dfaec9953401a7ef8db045149461047c44f15f9c5bf7758900b5f3ee`. The executable reported version `5.4.2`.

The campaign used 24 perturbations: two sites, BARE/SCREENED, and six signed amplitudes. The grid and values come from the versioned LR config; they were not selected based on U.

## I.5

JSON: `/home/jmc/hubbardflow_validation/task22_20261003_0a8a12f/campaigns/nio_p5_task22_0a8a12f/results/i5_state_gate.json`  
SHA-256: `d3eb4ce6e84ee319edc1e96c9fb9d81e3c7dfb88899b0c2eecfdfb04fff83f0c`
Schema `hubbardflow.i5_state_gate.v1`, policy `i5-state-policy-v1`.

| Site | Mode | Pair verdict | Admitted amplitudes (eV) | G4 |
|---|---|---|---|---|
| NiLR0 | BARE | PASS | 0.02, 0.04, 0.06 | APPLICABLE / PASS at all six points |
| NiLR0 | SCREENED | PASS | 0.02, 0.04, 0.06 | APPLICABLE / PASS at all six points |
| NiLR1 | BARE | PASS | 0.02, 0.04, 0.06 | APPLICABLE / PASS at all six points |
| NiLR1 | SCREENED | PASS | 0.02, 0.04, 0.06 | APPLICABLE / PASS at all six points |

At every point `G1`, `G2`, `G3a`, and `G4` returned PASS; no amplitude was excluded. G3 smoothness is `NOT_ESTABLISHED:SMOOTHNESS_REQUIRES_SCF_LADDER` under D13a; it does not change the verdicts of these pairs. There was no I.5 failure.

## Comparison of U with Part A

The full `primary` object from `lr_u_analysis.v3.json` was compared with the Part A result in `nio_p5_product_2`; the objects are identical. Scalar U:

| Site | Part A (eV) | Real run (eV) | Difference (eV) |
|---|---:|---:|---:|
| NiLR0 | 6.864267700049239 | 6.864267700049239 | 0 |
| NiLR1 | 6.864387475210124 | 6.864387475210124 | 0 |

The U matrix also matches exactly, entry by entry.
