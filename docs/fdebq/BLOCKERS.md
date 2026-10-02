# FD-EBQ phase 2 blockers

## TASK 10 — Coverage qualification and diagnostic mode

TASK 10 is not implemented. The requested CoO golden diagnostic cannot be
produced from an admissible reference state using the data-source rules in the
author's amendments:

- `examples/tmo_campaigns/CoO_ref.out` contains local occupation matrices but
  does not print final per-atom Mulliken moments, so F5/reference admissibility
  is incomplete.
- CoO V6 outputs contain moments, mesh and termination, but no local occupation
  matrices. TASK 8 explicitly requires `occupation_spectra = NOT_AVAILABLE`;
  F7 is therefore `AMBIGUOUS` and cannot support reduction.
- Combining moments from the V6 output with spectra from the example output
  would join distinct outputs without a specified evidence-binding rule. No
  data were combined or inferred.

Consequently the specified CoO `2 -> 1` diagnostic would claim a candidate
equivalence that the available, author-approved evidence cannot establish.
TASK 10's required golden report and `ALL_SUBSPACES` fallback cannot both be
met for CoO until the reference-data policy or expected golden result is
amended.

The fallback text also says to expand a “small system” when its minimum orbit
is `|S|`, while the golden tests request a one-representative candidate for
CoO where the whole correlated set has two sites. It is unclear whether the
diagnostic should report the candidate count while selecting `ALL_SUBSPACES`
because the mandatory shadow removes the run-count savings, or whether the
one-representative golden result takes precedence.

No TASK 10 files or reports were added. No synthetic or cross-run data were
substituted for the missing CoO evidence. TASK 11 is independent and may
proceed.

## TASK 12 — Resolved perturbation plan

TASK 12 is blocked on TASK 10. The required frozen plan embeds
`CoverageQualification`; without the TASK 10 contract and its deterministic
fallback behavior, the planner cannot emit the requested schema or apply §P
without inventing a substitute coverage record. TASK 11 response reconstruction
is complete but does not provide that qualification type.

No TASK 12 implementation or plan digests were added. Revisit after the TASK 10
data-policy and fallback questions are resolved.

## TASK 13 — campaign_v2 integration

TASK 13 is blocked on TASK 12. Optional-site validation and resume-time plan
invalidation require a resolved inventory/coverage plan digest; implementing
the campaign path without the frozen plan would create an unverified second
source of campaign targets. The diagnostic fallback from TASK 10 is also
unavailable.

No production campaign behavior was changed. Revisit after TASK 10 and TASK 12
are complete.

## TASK 14 — Translation reduction with mandatory shadow

TASK 14 is blocked on TASK 10, TASK 12 and TASK 13. Shadow qualification and
expansion need the coverage classes, frozen per-column plans, and campaign DAG
inputs from those tasks. Changing `symmetry_reduction.py` or
`campaign_runner.py` before those contracts exist could alter the fixed or
diagnostic path without a way to verify the required byte-identical behavior.

No production reduction or runner changes were made. Revisit after TASK 10,
TASK 12 and TASK 13 are resolved.

## TASK 15 — Automatic species splitting admission

The opt-in backend materializer is implemented, but end-to-end campaign
admission remains unavailable. It returns `STAGED_PENDING_GENERATED_IDENTITY`
until the caller verifies SIESTA-generated alias `.ion` files; copied reference
files alone are not proof. TASK 13's campaign configuration gate is blocked,
so `lr-config.auto_split_species` is not wired to production.

The available CoO/NiO/MnO shared-label examples lack explicit `PAO.Basis`
blocks and fail the required identity preflight; archived production FDFs are
already split. No source file in the checkout supports the requested positive
real-FDF materialization test with the required explicit basis and reference
identity. Tests use synthetic FDFs for the positive preservation case and real
archives only for fail-closed read-only checks. No SIESTA-generated aliases
were invented or run.

The helper remains disabled by default and cannot mark a campaign ready. Revisit
the campaign gate after TASK 13 and when generated alias identity evidence is
available.
