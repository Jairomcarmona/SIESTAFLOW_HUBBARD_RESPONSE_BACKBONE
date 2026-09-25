# SIESTA BARE semantic verification protocol

## Why this protocol exists

In the Cococcioni finite-difference construction, \(\chi^0\) is not defined
as “the second SCF iteration.” It is the occupation response after applying
\(\alpha P_J\) to the converged reference Hamiltonian and **before** rebuilding
Hartree--XC from the perturbed density. Ordinary SIESTA output can identify
population events and SCF iteration numbers, but that alone does not prove the
internal ordering of Hamiltonian updates.

This protocol is the only permitted route to promote an observation from
`CANDIDATE_BARE` to `VERIFIED_BARE` in this repository.

## Preconditions

1. Use the exact SIESTA version, executable build and pseudopotential family
   intended for production.
2. Complete a converged reference SCF calculation and save its density matrix.
3. Record the hash of that parent density matrix and of both FDF files.
4. Use a small, representative cell and one correlated site for this semantic
   test. This is a control experiment, not a production \(U\) campaign.

## Required evidence

| Evidence | What it establishes |
|---|---|
| SIESTA version/build identifier and source revision used for inspection | the observed order belongs to the executable that will be used |
| reference input, parent-DM hash, and normal completion | unique \(\rho_\mathrm{ref}\) |
| BARE \(+\alpha\) and \(-\alpha\) FDFs with `DFTU.PotentialShift true`, explicit projector and `DFTU.FirstIteration` | declared perturbation \(\alpha P_J\) |
| native output line intervals for the selected population event | reproducible parser provenance |
| a source-level or sanctioned debug trace of the update order | proves the selected event precedes Hxc rebuild from the perturbed density |
| controlled comparison with the full SCREENED calculation | demonstrates that the BARE and screened branches are distinct |

## The decisive order assertion

For each sign of \(\alpha\), the evidence must establish this sequence:

\[
 \rho_\mathrm{ref}
 \;\longrightarrow\;
 H_{KS}[\rho_\mathrm{ref}]+\alpha P_J
 \;\longrightarrow\;
 \text{diagonalization and }n_I^{(0)}
 \;\longrightarrow\;
 \text{only afterwards may }V_{Hxc}[\rho]\text{ be rebuilt}.
\]

If the trace instead shows an Hxc rebuild before the selected population,
that observation is not \(n_I^{(0)}\) and must be rejected for \(\chi^0\),
even if the algebra is full rank and produces a numerically stable number.

## Implementation choices

- Prefer a documented SIESTA debug/logging mode if it emits the required order.
- Otherwise inspect the source corresponding to the deployed build and add a
  minimal, local diagnostic trace around potential construction,
  diagonalization, population evaluation and Hxc update. The diagnostic build
  must reproduce standard-build occupations to stated floating-point tolerance
  before it can certify the standard build.
- Never infer the order from `MaxSCFIterations`, mixer settings, or the
  occurrence index alone.

## Acceptance record

Store a short `bare_semantics.json` next to campaign evidence:

```json
{
  "status": "PASS | FAIL | UNRESOLVED",
  "siesta_version": "...",
  "executable_build_id": "...",
  "source_revision": "...",
  "reference_dm_sha256": "...",
  "selected_event_lines": {"plus": [0, 0], "minus": [0, 0]},
  "hxc_rebuild_excluded_before_selected_event": false,
  "trace_reference": "..."
}
```

The runtime verifier requires the stricter schema
`siestaflow-bare-semantics-v2`: in addition to the fields above it binds the
record to `executable_sha256`, `input_fdf_sha256`, `output_sha256`,
`trace_sha256`, a relative `trace_reference`, and four unique exact
`trace_markers` in this order: `reference_dm_loaded`,
`selected_population`, `perturbation_applied`,
`hxc_rebuild_after_selected_population`. The selected output line interval and
the parent-DM hash must match the current run. The verifier rereads the output
and rejects an abort or missing normal termination even if an attacker has
rebound its hash.

The sidecar is not an authority for its own grammar. The campaign policy must
provide an independent `BareTraceExpectation` with the audited source revision
and the exact four marker strings. A sidecar declaring another revision or a
different marker vocabulary is rejected. Standard SIESTA output does not
provide this expectation; in that case BARE remains unresolved rather than
being promoted to `VERIFIED_BARE`.

Only `PASS`, a nonempty `trace_reference`, and
`hxc_rebuild_excluded_before_selected_event=true` may populate
`ObservationContext.bare_hxc_rebuild_excluded` and
`bare_semantics_evidence_ref`.
