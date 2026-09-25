# Scientific LR-U DAG Protocol

This protocol turns a validated Slurm allocation pattern into a resumable
scientific workflow. It does not change the finite-difference LR-U method or
introduce a pseudoinverse fallback.

```text
scientific FDF + PSML
  -> Method-2 subspace audit
  -> accepted reference SCF and parent DM
  -> child FDF materialization
  -> validated BARE and SCREENED responses
  -> direct LR algebra
  -> reproducible protocol evidence
```

## Resource model and site profile

The supplied template is an example five-node, 100-rank layout: five nodes with
twenty MPI ranks per node. It keeps one allocation and launches one full-rank
SIESTA FDF at a time. The Method-2 projector materialization is a small
initialization gate at the start of that allocation; it is terminated as soon
as the real `*.dftu_proj` exists.

The template is not a universal cluster claim. The public version deliberately
contains no partition, account, filesystem path, host name, or module name.
Before production use, copy `slurm/site_profile.local.example` to
`slurm/site_profile.local`, set only locally validated backend settings, and
submit with the appropriate local partition. The local profile is ignored by
Git. A site must independently validate its scheduler request and Hydra syntax.

## Gates and resume semantics

The state ledger is `results/scientific_dag_state.json`:

| Gate | Required scientific condition |
|---|---|
| `PROJECTOR_AUDIT` | Materialized Method-2 projector is PSML-compatible and passes the locality screen. |
| `REFERENCE` | Normal completion, converged SCF, semantic validation, reference-state hook when supplied, and parent DM. |
| `CHILDREN_MATERIALIZED` | Every manifest child has an FDF; an optional generator hook runs only after `REFERENCE`. |
| `RESPONSES` | Every BARE/SCREENED response has normal completion and mode-specific semantic validation; SCREENED must converge. |
| `ANALYSIS` | Campaign algebra reports `PASS` with full-rank `chi0` and `chi`. |
| `EVIDENCE` | Final result and compact protocol report are present. |

On a later Slurm allocation, valid artifacts are checked again. A valid stage is
skipped; an interrupted attempt is moved to `slurm/interrupted_attempts/` before
its run is retried. The scheduler allocation is not retained, but valid
scientific outputs are never deliberately overwritten.

## Installing in a campaign

The campaign must provide a `runs/manifest.json`, reference FDF,
`pseudopotentials/`, `scripts/validate_run.py`, and one algebra entry point:
`scripts/package_results.py` or `scripts/analyze.py`.

```bash
python tools/install_scientific_dag.py \
  --campaign-root /path/to/campaign \
  --result-file results/final/campaign_result.json

cd /path/to/campaign
bash -n slurm/submit_scientific_lru_dag.slurm
cp slurm/site_profile.local.example slurm/site_profile.local
# Edit only local module/executable settings; do not commit this file.
source slurm/site_profile.local
sbatch --wait --no-requeue --time=1:00:00 --partition local \
  -N1 -n4 --ntasks-per-node=4 -c1 --exclusive \
  --export=ALL,OMP_NUM_THREADS=1,SIESTAFLOW_EXECUTION_PROFILE=local_openmpi \
  slurm/submit_scientific_lru_dag.slurm
```

The validated local WSL profile uses Slurm partition `local`, one node, four
tasks and Open MPI 4.1.6 (`orterun`/`mpiexec`). The equivalent foreground
contract used by the MnO runner is `sbatch --wait --no-requeue -p local -N1
-n4 -c1 --exclusive --export=NONE,OMP_NUM_THREADS=1`; its Open MPI launch maps
four ranks onto the allocated host. The generic DAG uses `--export=ALL` so the
site profile and executable paths remain available inside the job.

For a cluster that has validated Intel Hydra placement, choose
`SIESTAFLOW_EXECUTION_PROFILE=slurm_hydra_5x20` in the site profile and submit
with its site-validated partition and time limit, plus `-N5 -n100
--ntasks-per-node=20 -c1`. Hydra placement is checked as 20 ranks on each of
the five allocated hosts. Neither profile is inferred from installed MPI
executables; an unset or unknown profile fails before the DAG starts.

The template has no hard-coded node, task, thread, or wall-time request. The
`sbatch` resource request and selected execution profile must agree; the job
checks the allocated node and task counts before running any preflight or
scientific calculation.

The MnO v3r2 folder is not currently a valid target for this generic installer.
Its top-level `runs/manifest.json` contains nine legacy ±0.05 cases, while the
locked response contract and `tools/run_mno_afmii_response_v3r2.py` define 29
nodes over seven alpha values; it also lacks generic `validate_run.py` and
analysis adapters. Do not install against those nine cases as a substitute for
the locked matrix protocol or write into archived `results/` directories. A
material-specific adapter over a separately staged 29-node manifest remains
open work.

The central Hubbard label is inferred from the first perturbed target in the
manifest. Override it with `--central-label` only when that inference is not
the desired representative for the preflight audit.

The material-specific campaign generator remains responsible for the FDF
physics. An optional `scripts/build_children_after_reference.py` hook may
create child FDF files after the accepted reference; the DAG does not invent
geometry, spin order, projector shells, or perturbation strengths.
