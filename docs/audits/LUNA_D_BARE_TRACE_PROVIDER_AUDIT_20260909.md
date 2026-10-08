# Luna D — BARE evidence provider

## Scope

This adds a validation-only interface for an existing native BARE trace and
its versioned sidecar. Validation reuses the `siestaflow-bare-semantics-v2`
verifier, which binds the sidecar to the hashes of the executable, parent DM,
FDF, output, and trace, and requires the four native events in the certified
order.

## Safeguards

- SIESTA is neither executed nor modified.
- A `PASS` sidecar is not created from `SCF.MustConverge`, exit codes,
  iteration count, or ordinary `siesta.out` text.
- `collect()` fails closed: a trace can only come from an audited native
  backend or versioned external evidence.
- Replacing the executable, DM, FDF, output, sidecar, or trace invalidates the
  request.
- No factory, output validator, FDF, DAG, Slurm, or campaign files are modified.

## Focused tests

`tests/unit/test_bare_trace_provider.py` covers hash-bound acceptance,
executable replacement, a missing sidecar, and rejection of implicit
collection. Tests use synthetic fixtures only; they are not physical evidence.

## Explicit limitation

The standard SIESTA installation is not assumed to produce the
`TRACE: LR_BARE ...` markers. BARE remains blocked for production until an
actual, versioned native trace is available.
