# HPC profiles

An execution profile is an explicit runtime contract, not a scientific policy.
Campaign inputs, projector definitions, response grids, and analysis criteria
belong to the campaign. Scheduler resources, software environment, MPI launch,
and retry limits belong to the execution profile.

## Public interface

The public Slurm shape is defined by
[`execution-profile.schema.json`](../schemas/execution-profile.schema.json)
and the execution contract in
[`HPC_SLURM_EXECUTION_CONTRACT.md`](../HPC_SLURM_EXECUTION_CONTRACT.md). A
profile declares:

- `target` and its evidence state;
- scheduler selectors such as partition and optional account/QoS;
- allocation size, CPU count, memory, walltime, concurrency, shutdown margin,
  and termination grace;
- module/environment preparation, the SIESTA executable, exclusive-resource
  policy, and a typed MPI launcher;
- maximum attempts and whether converged SCF is required.

The profile must be validated against the actual runtime and scheduler before
submission. `UNKNOWN`, `RENDERED_ONLY`, or merely historical settings are not
runtime validation. The public repository ships the schema and contract; a
concrete site plugin and its credentials, paths, partitions, modules, and
resource policy stay in site-local configuration.

## Yoltla as a site example

The archived [`Yoltla deployment guide`](../YOLTLA_DEPLOYMENT.md) identifies
Yoltla as a Slurm site. It describes an older direct-script interface and is
retained as historical context; its partition, module, MPI, and resource
examples are not a current production profile. To configure a current Yoltla
run, the site administrator supplies those concrete values in the Slurm
profile and the site plugin validates them against a live allocation. The
scientific campaign and its FDF remain unchanged by that mapping.

| Profile section | Site-provided value |
|---|---|
| `slurm` | Current partition and, if required, account/QoS |
| `allocation` | Requested nodes, CPUs, memory, walltime, concurrency, and shutdown/termination margins |
| `runtime` | Current module commands, executable location, environment, exclusivity, and MPI launcher/bootstrap |
| `task_policy` | Attempt limit and SCF-convergence requirement declared for the workflow |

This table is the interface mapping, not a runnable Yoltla profile. No current
site-specific values are published here.

## No-cluster validation path

Use `hubbardflow.synthetic_backend` for controlled numerical regressions and
the `tests/algebraic/test_synthetic_recovery.py` and
`tests/unit/test_campaign_runner_synthetic.py` suites for software checks that
do not need a cluster. Synthetic populations and injected noise make these
tests repeatable. They do not certify SIESTA output semantics, a site plugin,
or a scheduler/MPI configuration; those need their corresponding execution
evidence.
