# FD-EBQ phase 2 blockers

## TASK 10 — Coverage qualification and diagnostic mode (RESUELTO)

The specification blockers are RESUELTO by author amendments D1/D2 in
`9a60d78` (`docs/fdebq/AMENDMENTS_2.md`). The implementation provides a pure
`CoverageQualification`, a single-output reference-admission adapter, diagnostic
JSON/Markdown reports, and deterministic golden contracts in `task10_reports/`.
Coverage qualification, single-output reference admission, diagnostic reporting and D2 savings are implemented in commit `1bba765`.

CoO/NiO/FeO examples and the available frozen V6 outputs produce
`REFERENCE_NOT_ADMISSIBLE -> ALL_SUBSPACES` with `EVIDENCE_INCOMPLETE`.
Missing data are never merged from separate outputs. D2 always reports
`would_reduce_to`; an orbit of two members remains explicit with `NO_SAVING`
because representative plus mandatory shadow costs two runs. Singletons remain
explicit. Diagnostic candidates are `CANDIDATE_PENDING_SHADOW`, never `PROVEN`.

Two archived-data limitations remain explicit rather than blocking the module:

- **Cu3N:** the named output echoes `DFTU.PotentialShift true`, a Cu1 record
  with U=1.7600 eV and J=0.1000 eV, and `DM.UseSaveDM true`; the supplied
  `Cu3N_ref.fdf` contains none of these records. Its input SHA256 is
  `bdac24b25c230ca8852c2619165490a4e215c5da5cc8e7623034959d00a8c8f8`; output
  SHA256 is `aa6c0b98135c3a3ebd086db7dab2d4d59da0b208947d7d67aaf1262b9755a628`.
  The non-polarized declaration is verified, but the output is perturbed and
  inconsistent with the input. D1 therefore excludes it; the source FDF also
  has no correlated inventory. The requested archived positive translation
  golden cannot be established. A non-polarized synthetic translation toy and
  a complete zero-shift synthetic backend pair cover the positive rule.
- **MnO:** `response-matrix-foreground-recovery-v4/00_REFERENCE` is an
  unperturbed, input-bound, admissible output with 32 moments and 16 local
  spectra. Its archived inputs omit explicit `PAO.Basis` and the directory lacks
  the label-specific pseudopotentials needed by TASK 7's semantic identity
  contract. Thus coverage remains `ALL_SUBSPACES` with
  `SPECIES_IDENTITY_NOT_ESTABLISHED`. The 16->2 / 16->1 candidate cases are
  covered by the TASK 9 geometry/state toy with flags off / spin flip on.

These are **decisión del implementador (conservadora)** under the general
principle of AMENDMENTS_2.md. Archived inputs/outputs and TASK 7–9 behavior are
unchanged. Full diagnostic reports are delivered in
`C:\Users\Jairo\work\fdebq_pr_notes\r2-task10-reports`.

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

## TASK 16 — Calibrated amplitudes and deterministic rounds (blocked)

TASK 16 cannot be implemented without two scientific decisions:

- §J S7 selects a best estimator per `(J, mode, I)`, while the required
  `ColumnPlan` holds one estimator for `(J, mode)`. The specification does not
  define how row-wise error budgets are aggregated to choose a single column
  estimator or how that same aggregation drives the round machine.
- §I.7 accepts by first-order `u_influence` plus an unspecified `O(β²)` term.
  TASK 16 asks for acceptance against user-supplied `tau_U`, but gives no
  remainder bound or rule relating the existing enlarged-matrix-box method in
  §I.8 to this gate. Choosing either would invent scientific policy.

The TASK 16 implementation agent stopped before writing code. No estimator,
amplitude, or acceptance decisions were made. The planner/campaign wiring is
also unavailable because TASK 12/13 are blocked; that dependency alone would
permit documenting a wiring blocker, but does not resolve the core scientific
ambiguities. The author was asked to define the row aggregation and remainder
rule, or explicitly limit calibrated mode to diagnostics without READY.

## TASK 17 — SCF tolerance ladder (blocked)

The ladder contraction test allows the case where both successive differences
are at print resolution (§E.2 and §J/S4 of the FD-EBQ review), but the
specification does not define `rho_hat` or the SCF `ESTIMATE` for that case,
including `eta1 = eta2 = 0` or differences unresolved within their print
radii. The expression `theta * eta1 / (1 - rho_hat)` is not identifiable
there; choosing zero, `rho_max`, or another radius would invent a scientific
rule.

The review also calls for splitting absolute and relative components by small
and large amplitudes (§E.2–E.3), but does not specify the transformation from
the measured ladder values to those components or an envelope for unmeasured
amplitudes. The author was asked to define the under-resolution output/radius
and the exact component-splitting rule. No code, synthetic evidence, or SIESTA
run was produced for TASK 17.

## TASK 18 — Spin flip, rotations, and V3 controls (blocked)

The isolated TASK 9 candidate classifier already has digest-bound
`allow_spin_flip` and `allow_rotations` flags (both default false), and tests
synthetic F5/F6/F7 counterexamples. TASK 18 requires end-to-end flag admission,
candidate classes, reconstruction, and mandatory shadows. Those require
`CoverageQualification` (TASK 10), the frozen plan (TASK 12), campaign wiring
(TASK 13), and shadow execution (TASK 14), all blocked above. There is no
contract here to promote `OperationClassification.accepted` from a candidate
to a reduction decision; it explicitly is not PROVEN.

TASK 18 also requires explicit egg-box quantification in the plan for
`EXACT_IN_CONTINUUM_ONLY` rotations. The current operation model records only
that exactness label and TASK 12's plan schema is unavailable. Finally, V2
prospective shadows, V3 real negative controls, and V4 holdout are user-run
validation gates; their result digests do not exist and cannot be fabricated
for `VALIDATION_GATES.md`. CoO's approved TASK 8 evidence leaves F7
`NOT_AVAILABLE`/`AMBIGUOUS`, and the V1 MnO permutation is not F1–F8 evidence.

Existing classifier candidate tests are retained as TASK 9 coverage. No
end-to-end acceptance or flag-enablement claim is made; flags remain off.

## TASK 19 — Product CLI and final report (blocked)

`hubbardflow plan` requires the inventory, reference evidence, coverage
qualification, and frozen `ResolvedPerturbationPlan`; TASK 10 and TASK 12 are
blocked. `run` and `submit` additionally require campaign plan consumption,
mandatory-shadow execution, and the existing full downstream chain; TASK 13
and TASK 14 are blocked. Adding CLI commands without these contracts would
create a second, incomplete production path and could not satisfy the READY
gate, provenance, resume, or V6 golden requirements. No product commands were
added. Revisit after the upstream contracts and validations are resolved.
