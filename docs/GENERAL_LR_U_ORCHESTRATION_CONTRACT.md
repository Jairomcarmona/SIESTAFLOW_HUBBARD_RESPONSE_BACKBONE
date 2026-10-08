# General LR-U Orchestration Contract

## Purpose

This project implements a finite-difference linear-response workflow for a
SIESTA backend. It is not a collection of material-specific campaigns. The
scientific core receives an FDF structure, DFT+U subspaces, evidence for the
reference state, and a declared policy; the execution profile supplies the
scheduler and compute environment without entering the mathematics.

## Workflow and scientific gates

```text
FDF + PSML input
  -> subspace / provenance audit
  -> converged SIESTA reference and evidenced magnetic state
  -> provisional symmetry plan
  -> BARE and SCREENED perturbations with +/- alpha
  -> direct shadows of reducible classes
  -> authorization or explicit expansion
  -> chi0, chi, direct inversion, U, and final evidence
```

No gate can be replaced by a default value, an average, or a pseudoinverse.
Failure or incomplete evidence produces an explicit campaign outcome, never a
silent reduction.

## Core independent of backend and cluster

`domain.symmetry_reduction` defines:

- `SymmetryReductionPolicy`: perturbation amplitude and tolerances fixed
  **before** execution;
- `SymmetryReductionPlan`: representatives, shadows, and the four BARE/SCREENED
  responses with opposite signs for every required site;
- `ShadowObservation`: complete comparison of occupations, `chi0` and `chi`
  columns against the predicted transformation;
- `ReductionAuthorization`: authorization to reduce or expand rejected orbits
  into explicit perturbations.

It contains no chemical symbols, material names, paths, MPI commands, Slurm
partitions, or supercell assumptions. The same logic can be used with any
adapter that supplies canonical geometry, occupations, and verifiable magnetic
evidence.

## SIESTA adapter

The FDF adapter validates geometry, `DFTU.Proj` fields, and site indices.
Magnetic evidence is extracted from the final SIESTA output, not from
`DM.InitSpin`. If there is no reference evidence tied to the exact FDF hash,
the adapter generates an explicit plan.

By default, only operations with identity rotation are allowed. An orbital
rotation is not inferred from coordinates: the backend must certify that the
subspace and scalar occupation are invariant.

## Reduction and shadow test

An equivalence class is provisional. For every reducible class, the scheduler
deterministically selects a representative and a distinct member linked by an
allowed operation. It runs both with BARE/SCREENED and `+/- alpha`.

Reduction is authorized only if all four outputs are scientifically valid and
the occupation, `chi0`, and `chi` residuals fall below the published
thresholds. A failed shadow is not averaged: its entire orbit is explicitly
expanded into perturbations.

## Execution and resumption

The plan does not assume Slurm. An execution adapter materializes FDFs, orders
DAG nodes, and records each validated result. A private cluster profile can
run tasks sequentially within a large allocation or use another resource
model. Resumption may reuse only results whose provenance and validation
remain valid.

## Implementation status

The planning, authorization, and explicit expansion core is implemented and
tested locally. The SIESTA materializer now consumes a `PerturbationSpec` and
preserves the audited FDF while changing only the target site and BARE/SCREENED
controls. The backend-neutral scientific DAG represents the reference,
responses, shadow gate, and expansion after rejection.

## Implementation constraints and scope

The core now includes a resumable executor that is neutral to the scheduler. A
private execution adapter (`local` or `Slurm`) receives a ready node and must
return validated evidence; the core retains a JSON checkpoint tied to the
exact DAG hash. A different DAG cannot reuse it. A child node never starts
until all its parents are validated, and the first invalid terminal output
stops progress. This allows reuse of a reference or certified perturbation
without reusing results from another scientific policy.

The SIESTA adapter has a `SiestaCommandFactory` that materializes each
reference or perturbation in a new directory, copies only declared static
artifacts, preserves the reference FDF, and builds a Hydra command from an
already validated profile. The command uses explicit input, output, and error
paths, without a *shell* or one `sbatch` per node. The private allocation
wrapper remains responsible for loading modules; the core runs no module
commands and knows no cluster site.

The factory and validator do not yet authorize a production BARE campaign on
their own: a BARE certificate must be tied to the native output and trace
produced **after** that execution. Without a verifiable sidecar, the BARE node
fails closed. The outstanding implementation is a BARE evidence provider
that receives an approved native trace; it must not be replaced by heuristics
based on the number of SCF iterations.

Adaptive amplitude selection is represented by an explicit alternative DAG.
For nominal amplitude \(h\), it materializes
\(\{-2h,-h,-h/2,0,h/2,h,2h\}\): zero is the reference, and every nonzero
point contains its BARE and SCREENED branches. The linearity gate admits only
a common window that preserves the magnetic state, has resolved signal, and
passes the predeclared residual and slope-drift criteria. A normal SIESTA exit
alone does not authorize matrix inversion.

The adapter's currently certified capability is **scalar, collinear DFT+U
with one correlated subspace per site**. Non-collinear, SOC, multiple
subspaces per site, covariant orbital transformations, and DFT+U+V requests
are rejected before an FDF is materialized. This limitation prevents an
apparently successful result from being physically misinterpreted.

Expanding these capabilities requires dedicated adapters and tests with real
evidence:

1. crystallographic symmetry through a canonical library and magnetic symmetry
   based on the reference output, including representation of the orbital under
   each rotation;
2. extraction of complex spinor matrices for non-collinearity/SOC and
   covariance tests;
3. definition, perturbation, and assembly of intersite pairs for \(U+V\);
4. one local and one Slurm execution plugin to materialize FDFs, run the
   backend, and construct `NodeReceipt` only after validating outputs.

Historical campaign ZIPs remain integration fixtures and evidence, not
software rules or public cluster profiles.
