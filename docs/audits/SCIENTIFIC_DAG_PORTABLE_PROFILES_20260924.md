# Portable scientific-DAG profiles — 2026-09-24

## Implemented execution contract

`templates/slurm/submit_scientific_lru_dag.slurm` now requires one explicit
profile and validates the allocation before running Gate 0 or a scientific
calculation:

| Profile | Allocation | MPI launcher | Placement check |
| --- | --- | --- | --- |
| `local_openmpi` | 1 node, 4 tasks, 1 CPU/task | Open MPI (`orterun`, `mpiexec.openmpi`, or `mpiexec`) | 4 ranks on the one allocated host |
| `slurm_hydra_5x20` | 5 nodes, 100 tasks, 20 tasks/node, 1 CPU/task | Intel Hydra (`mpiexec.hydra`) | 20 ranks on each allocated host |

Node, task, and time requests are supplied to `sbatch`, so a profile is never
silently inferred from installed executables. The job rejects an unset or
unknown profile, a resource mismatch, or a task allocation with more than one
CPU. It sets `OMP_NUM_THREADS=1` before launching work. Open MPI uses the
single allocated host and `--map-by ppr:4:node`; Hydra retains its multi-host
bootstrap and per-node process count.

## Local WSL evidence

The read-only WSL probe reported Ubuntu 24.04.1, Slurm `23.11.4`, Open MPI
`4.1.6`, `/usr/bin/orterun`, and SIESTA `5.4.2` at
`/home/jmc/.local/siesta-5.4.2-openmpi/bin/siesta`. The `local` partition has
one node, 12 CPUs, and a one-hour time limit. It has no `mpiexec.hydra`.

Three bounded checks passed without running SIESTA:

- `bash -n templates/slurm/submit_scientific_lru_dag.slurm`.
- Open MPI `orterun --host HOST:4 --map-by ppr:4:node -np 4 /bin/hostname -s`
  produced four lines for the allocated WSL host.
- `srun --partition=local -N1 -n4 -c1 ... hostname` observed one node, four
  tasks, one CPU per task, and `OMP_NUM_THREADS=1` on each task. A matching
  `sbatch --test-only` request was accepted by Slurm.

The generic installer was exercised on an isolated fixture campaign with a
manifest, FDF, PSML, run validator, and analysis entry point. It installed the
portable template and helper tools without creating result files. A negative
fixture missing the analysis entry point failed before creating any deployment
files. Focused WSL tests passed: **25 passed** across installer, execution
contract, gate, and Method-2 tests.

## MnO v3r2 route and remaining P1-1 work

The archived MnO v3r2 campaign should not receive the generic DAG yet. Its
top-level `runs/manifest.json` lists nine legacy cases at ±0.05 eV, while the
locked `tools/run_mno_afmii_response_v3r2.py` protocol defines 29 nodes over
seven alpha values and owns its calibration, receipt, and analysis contract.
The campaign also lacks `scripts/validate_run.py` and a generic algebra
adapter. Running the installer against that folder fails before writing; its
existing manifests and archived `results/response-matrix-foreground-recovery-v4`
were left unchanged.

The current appropriate generic-DAG acceptance route is an isolated clean
fixture campaign. P1-1 remains open for MnO: first build and review a separate
staging campaign with a 29-node manifest and explicit adapters, then validate
its installation and interruption/restart behavior. Do not reinterpret the
nine-case legacy manifest as the locked response grid. No response runs, new U
calculation, or SCF were launched in this iteration. The five-node Hydra
profile is retained as the portable cluster contract, but cluster placement was
not exercised in this environment.
