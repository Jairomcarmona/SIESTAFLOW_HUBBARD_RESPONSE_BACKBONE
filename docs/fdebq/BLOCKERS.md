# Phase 2 blockers

## TASK 7 — FDF model and subspace inventory

**Status: BLOCKED — specification contradiction.**

`CODEX_TASKS_PHASE2.md`, TASK 7, explicitly requests parsing `LatticeParameters` as one of the supported lattice forms. The authoritative `HUBBARDFLOW_PERTURBATION_PLANNING_REVIEW.md`, §C.3, explicitly lists `LatticeParameters` among syntax outside the audited subset and requires `NOT_SUPPORTED`/fail-closed behavior. The same input therefore cannot both be accepted as supported and rejected as unsupported.

No parser or inventory implementation was added for TASK 7. Choosing either behavior would contradict one of the supplied specifications. Resolve the conflict by amending either TASK 7 or §C.3 before implementation. Downstream tasks that require `FdfModel` or `CorrelatedSubspaceInventory` remain dependent on this blocker; independent tasks may proceed.

## TASK 8 — reference state evidence

**Status: BLOCKED — required real archived fixtures are missing, and the canonical FDF inventory from TASK 7 is blocked.**

TASK 8 requires regression tests against archived CoO V6, NiO V6, MnO v3r2, Cu3N, and FeO diagnostic SIESTA outputs. The CoO V6 and NiO V6 campaign outputs were not found in this checkout. Generic CoO/NiO examples and `examples/tmo_campaigns/Cu3N_ref.out` do exist; the latter is a completed SIESTA output with projector-occupation matrices, so Cu3N is not blocked by file absence. The available representative NiO audit output is not the requested NiO V6 campaign fixture. The MnO v3r2 reference output and FeO diagnostic exports exist. Building the required per-correlated-subspace evidence also depends on the canonical FDF model/inventory from blocked TASK 7; duplicating DFTU/FDF parsing here would violate the single-parser requirement.

No TASK 8 implementation was added, and no tests were weakened or replaced with fabricated outputs. Provide the missing campaign outputs and resolve TASK 7's `LatticeParameters` contradiction before retrying.
