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
sbatch --partition "$SIESTAFLOW_PARTITION" slurm/submit_scientific_lru_dag.slurm
```

If the site has no partition selector, omit the `--partition` argument. The
five-node / 100-rank request remains an example profile: change it only after a
site-level placement validation, keeping the script's `NODES`, `RANKS` and
`PPN` checks consistent with the scheduler request.

The central Hubbard label is inferred from the first perturbed target in the
manifest. Override it with `--central-label` only when that inference is not
the desired representative for the preflight audit.

The material-specific campaign generator remains responsible for the FDF
physics. An optional `scripts/build_children_after_reference.py` hook may
create child FDF files after the accepted reference; the DAG does not invent
geometry, spin order, projector shells, or perturbation strengths.
