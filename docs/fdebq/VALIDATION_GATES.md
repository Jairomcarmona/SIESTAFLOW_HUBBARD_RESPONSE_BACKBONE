# Feature validation gates (TASK18 / AMENDMENTS_2 D7)

An explicit flag permits scientific **candidates**; it is not a validation
result. `allow_spin_flip` and `allow_rotations` default to `false` in the
campaign contract and `coverage-policy-v1`. They can be supplied at the top
level of lr-config or in a complete `coverage_policy`; conflicting declarations
are rejected. The normalized policy, including both flags, enters the coverage
and plan digests and the campaign lock. No example enables either flag.

## Evidence required before production admission

The following table describes the scientific gates in planning review §R and
D7. All results must be supplied by the user from real runs; software tests do
not satisfy V2, real V3 or V4. The exact policy and protocol must be frozen
before validation, including the development/holdout split and success criteria.

| Feature | V1 | V2 prospective result | V3 negative result | V4 holdout result | Current implementation |
|---|---|---|---|---|---|
| Translation ε=+1 | Retrospective scalar row/column reconstruction | MnO + Cu3N representatives and mandatory shadows; every row and both modes within additive FD-EBQ budgets including SCF ESTIMATE | Controls verify bands, identities and fallback | Frozen holdout demonstrates generalization | TASK14 shadow runs can be prepared; absent full I.5 state evidence expands the class |
| `allow_spin_flip` | Retrospective spin-summed permutation evidence; CoO 2→1 and MnO 16→1 remain candidates | Same prospective shadows with global ε=−1; F1–F8 including spin-swapped F5/F7 and spin-independent scalar contract F6; both modes pass full additive budgets | Zero false acceptances on ferrimagnet, orbital order, defect/slab, gray-band geometry, differing bases, SOC/noncollinear and equal-|m|/different environment; flags on and off | Frozen holdout tests generalization; does not replace required V1/V2/V3 | Opt-in is recorded; candidate classes using ε=−1 expand and plan is at most REVIEW |
| `allow_rotations` | Supporting reconstruction evidence, where available | Rotation-specific `EXACT_IN_CONTINUUM_ONLY` shadows; F1–F8, complete Method-2 shell and invariant effective k-mesh; recorded egg-box discrepancy and comparison with TASK14 additive budgets, without a new tolerance | Zero false acceptances, including rotation-specific F4/F7 and broken all-atom geometry controls | Frozen holdout tests generalization; does not replace required V2/V3/egg-box quantification | Opt-in is recorded; rotation classes expand and plan is at most REVIEW; `egg_box_quantification=NOT_QUANTIFIED` |
| Optional shadow | Supporting V1 evidence | Passed mandatory-shadow validation | Zero false acceptances | §R requires passed V4 before an explicit optional-shadow policy | Unsupported: `ShadowPolicy.MANDATORY` remains the only policy |
| CALIBRATED_GRID | Supporting evidence only | V2 does not replace FD-EBQ T0–T4 | V3 does not replace T3 | Frozen FD-EBQ holdout required by independent review §P.6 | Explicit `alpha_strategy` / calibration protocol required; missing T0–T4 or I.5 cannot produce READY |

V4 is the gate for considering an optional-shadow policy, not permission to
remove the mandatory shadow in this implementation. The spin-flip admission
requirements are V1/V2/V3; rotation requirements are V2/V3 plus the specific
egg-box evidence. V4 additionally establishes holdout generalization (§R).

## Required digests for every result

Each V2/V3/V4 result needs its own immutable artifact and file SHA-256, the
canonical coverage-policy and response/calibration-protocol digests, source and
effective FDF hashes, inventory/semantic-species digests, reference input/output
and parent DM hashes, backend executable/version/profile identity, parser
version, and the resolved plan digest. Bind each run to exact target, signed
alpha, mode and SCF profile; filenames are not reuse evidence. Bind raw outputs,
printed half-widths, SCF ESTIMATE ladder evidence and the full I.5 state evidence
to their hashes. V3 includes every rejected control and a zero-false-acceptance
count. V4 includes the preregistered holdout identity and proves the protocol
was frozen before evaluating the holdout, with no subsequent adjustment.

V2 rotation evidence additionally names each operation/permutation and retains
direct/reconstructed responses, discrepancies, their separate print BOUND and
SCF ESTIMATE components, and the additive sum. An egg-box discrepancy beyond
that sum rejects and expands the **whole** class. No tolerance is calibrated
from that discrepancy and U is not consulted.

## Missing runtime contract: conservative admission

**No prospective V2, real V3 or V4 result digest is available in this stack.**
The runtime I.5 producer and a validated result-admission API are not yet
available. Merely providing a hash/string or setting a flag cannot establish
their content. This task therefore does not add a hash-only bypass or a
`QUANTIFIED` status. A complete future admission contract must validate and
bind the above artifacts before granting any stronger state.

Decision of the implementer (conservative): retain candidates in diagnostic
coverage, expand classes using spin flips or rotations in the execution plan,
and cap an enabled feature policy at REVIEW (missing reference/inventory/DM
still gives NOT_ESTABLISHED). Even an injected synthetic shadow that agrees
within the budget cannot promote these features without prospective validation.
The shadow adapter accepts their scalar permutations for falsification and
expands failures; production admission still uses all affected direct columns.

## Plan compatibility

Schema `hubbardflow.resolved_perturbation_plan.v1` gains the explicit enum field
`egg_box_quantification`, with the single admissible value `NOT_QUANTIFIED`.
An older v1 mapping without this field is read conservatively with that value.
Its canonical digest changes: an existing campaign lock must fail resume rather
than silently omit the new provenance. Unknown fields, fabricated quantification
states, conflicting policy declarations and inconsistent evidence are rejected.

No real SIESTA run was executed for TASK18. CoO's archived reference limitations
remain documented by D1; the MnO toy is a synthetic candidate control, not a
prospective result. CALIBRATED retains the TASK16/17 contract; there is no separate
`allow_calibrated_alpha` switch to silently enable it.
