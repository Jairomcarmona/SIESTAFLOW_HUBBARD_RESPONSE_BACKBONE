# Phase 2 blockers

## TASK 7 — FDF model and subspace inventory

**Status: BLOCKED — specification contradiction.**

`CODEX_TASKS_PHASE2.md`, TASK 7, explicitly requests parsing `LatticeParameters` as one of the supported lattice forms. The authoritative `HUBBARDFLOW_PERTURBATION_PLANNING_REVIEW.md`, §C.3, explicitly lists `LatticeParameters` among syntax outside the audited subset and requires `NOT_SUPPORTED`/fail-closed behavior. The same input therefore cannot both be accepted as supported and rejected as unsupported.

No parser or inventory implementation was added for TASK 7. Choosing either behavior would contradict one of the supplied specifications. Resolve the conflict by amending either TASK 7 or §C.3 before implementation. Downstream tasks that require `FdfModel` or `CorrelatedSubspaceInventory` remain dependent on this blocker; independent tasks may proceed.
