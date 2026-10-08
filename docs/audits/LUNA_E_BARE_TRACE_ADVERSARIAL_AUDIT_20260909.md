# Luna E — adversarial audit of BARE traces

## Scope

This change contains only synthetic fixtures and unit tests. It is not physical
evidence, does not run SIESTA/MPI/Hydra/Slurm, and does not modify campaigns,
FDFs, profiles, or production code.

The test suite attacks the `siestaflow-bare-semantics-v2` contract at two
levels:

1. integrity of the native sequence (`DM → selected population → perturbation
   → Hxc reconstruction`);
2. provenance of artifacts bound by SHA-256 (executable, DM, FDF, output, and
   trace).

## Covered cases

- duplicated marker;
- missing marker or partial combination;
- events out of order;
- modified executable;
- modified parent DM;
- modified FDF;
- modified `siesta.out`;
- modified trace without updating its hash;
- `MPI_Abort`/abnormal termination even when the output hash is updated;
- SIESTA version different from the certified version;
- marker vocabulary replaced by four arbitrary strings;
- partial schema missing provenance fields.

In all these cases, except for the two explicit limitations below, the
verifier must raise `BareSemanticEvidenceError`; therefore,
`VerifiedBareEvidence` cannot be obtained.

## Review result

Tests show that a trace cannot retain a valid certificate if any bound artifact
changes or the event sequence is broken. Updating `trace_sha256` does not hide
invalid ordering, a repeated event, a missing marker, or abnormal termination.

## Terra's post-audit correction

The audit identified three gaps, and Terra fixed them at the verifier
boundary. The adversarial suite no longer marks these cases `xfail`:

1. `BareTraceExpectation` is supplied by the campaign contract, not by the
   sidecar. It fixes both `source_revision` and the four exact markers.
   Altered revisions or vocabularies are rejected.
2. The verifier rereads `siesta.out` even when its hash matches, and rejects
   `MPI_Abort`, `ABNORMAL_TERMINATION`, or the absence of normal
   termination.
3. `SiestaOutputValidator` does not authorize a BARE node unless the policy
   declares an audited expectation.

This strengthens the verification contract but does not invent a trace for a
standard binary. Without an identifiable revision and an audited native
grammar, the decision remains `CONTRACT GAP`, not `PASS`.

## Real evidence required for a later test

At minimum, real BARE certification requires:

- `siesta.out` and `siesta.err` from the same run;
- exact FDF and hash;
- exact parent DM and hash;
- identifiable executable and version/build;
- versioned native trace with the four unique, ordered events;
- sidecar generated without overwriting and bound to all hashes;
- DAG manifest relating node, perturbation, and artifacts.

A normal output or zero return code does not replace the native trace.
