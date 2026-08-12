# Public SLURM execution contract

This contract separates scientific workflow logic from private HPC site policy. It applies to the general orchestrator and Hubbard linear-response workflows. It deliberately excludes site names, partitions, routes, modules, architectures, allocation limits, users, accounts, and job identifiers.

## Boundaries

| Layer | Owns | Must not contain |
|---|---|---|
| Scientific campaign | inputs, FDFs, DAG, observations, scientific gates | site resources, accounts, modules, paths |
| Orchestrator | DAG resolution, work grouping, durable state | material-specific scheduler choices or private site policy |
| Site plugin | scheduler preflight, runtime preparation, allocation and MPI launch | scientific parameters and campaign identities |
| Private site catalog | concrete profiles and runtime evidence | public source-code requirements |

The public repository ships the interface and a non-operational template. A concrete site plugin is installed separately and is excluded from source control.

## Evidence is not configuration

A rendered package, a scheduler syntax acceptance, and a completed scientific run are distinct evidence. An agent cannot promote one to another.

| Evidence level | Agent permission |
|---|---|
| `VALIDATED_RUNTIME` | May propose the profile, subject to a compatible live snapshot and human authorization. |
| `OBSERVED` | Review only; never default. |
| `RENDERED_ONLY` | Never submit as validated. |
| `FAILED` | Reject until new runtime evidence exists. |
| `UNKNOWN` | Block. |

## Required inputs

The controller never invents inputs. It requires a workflow lock, a complete private profile, a read-only live scheduler snapshot, and explicit human authorization to submit. The workflow lock declares the DAG, inputs, transfers, required outputs, and their identities. A ZIP does not substitute for a lock.

The public template is [execution-profile.example.json](../production_benchmarks/execution-profile.example.json); the corresponding schema is [execution-profile.schema.json](schemas/execution-profile.schema.json). The implementation rejects the template because its evidence is `UNKNOWN`.

## Public plugin interface

```text
preflight(request) -> ValidatedProfile | Rejection
submit_allocation(profile, work_group) -> SchedulerJob
stage_run(parent_artifacts, run) -> StagedRun
launch_mpi(staged_run, ranks) -> ProcessHandle
observe(job_or_process) -> ExecutionState
```

`preflight` alone may query the scheduler, load the private runtime environment, or resolve the declared executable. It validates package integrity, wrapper syntax, and a scheduler test request before stopping for human authorization. Other layers receive only its validated data.

## DAG and parent artifacts

```json
{
  "nodes": ["REFERENCE", "RESPONSE", "ANALYZE"],
  "edges": [["REFERENCE", "RESPONSE"], ["RESPONSE", "ANALYZE"]],
  "parent_artifact": {"kind": "density-matrix", "producer": "REFERENCE", "required": true}
}
```

An edge advances only after its parent is `VALIDATED`. In Hubbard LR this means: a normal, converged reference produces a non-empty parent artifact; every child receives a fresh work copy; each child passes the semantics for its response mode; analysis starts only after every required observation is valid. Work grouping is a site optimization and never changes the DAG or FDFs.

## Controller and submission strategy

The rendered wrapper uses strict shell mode, resolves the package root from the scheduler submission directory with a safe fallback, prepares the declared environment, verifies the package, then starts **one Python controller**. The controller is never itself launched under MPI.

The controller creates isolated workspaces per attempt, retains durable state, validates parents before descendants, and records all terminal states. A site plugin may implement a single controller allocation, predeclared scheduler dependencies, or a persistent validated follow-up controller. It must never create a retrospective dependency after the parent has finished.

## Exact MPI placement contract

The site plugin resolves hosts from the granted allocation and validates unique-host count against the scheduler's granted node count. For a Hydra launcher, ranks must exactly equal:

```text
number of resolved hosts × declared processes per node
```

The public launcher builds an argument vector, not a shell string, with the declared bootstrap and a fresh UUID for every task. There is no silent fallback to a different launcher, static hosts, or login-node execution.

## Staging, outputs, and immutable evidence

- Inputs and parent artifacts are staged into an isolated attempt workspace.
- Parent evidence remains immutable; the work copy used by a calculation is recorded again after execution.
- Stdout and stderr are created exclusively. Existing outputs are not overwritten.
- The controller retains command, duration, exit code, declared outputs, semantic result, and a result manifest for every attempt.
- A scheduler `COMPLETED 0:0` is insufficient: output, convergence, artifacts, parser, and scientific gates must also pass.

## State model

```text
MATERIALIZED -> RUNNING -> VALIDATED
                     \-> FAILED_EXECUTION
                     \-> FAILED_OUTPUT_VALIDATION
                     \-> FAILED_SCIENCE
```

Any failed or blocked parent prevents descendants. Analysis has no partial, pseudoinverse, or fallback path unless the scientific workflow explicitly defines one.

## Public package gate

Every public package must include a workflow lock, scientific manifest, validators, dry-run path, LF shell files, and relative paths. It must exclude site names, scheduler policy, modules, executable locations, node details, users, accounts, jobs, scheduler logs, private catalogs, production DMs, and outputs unless intentionally released as scientific data.

The orchestrator writes a site-neutral execution plan with logical profile, DAG state, required artifacts, and opaque scheduler references. Concrete site information stays in a local execution record excluded from Git.
