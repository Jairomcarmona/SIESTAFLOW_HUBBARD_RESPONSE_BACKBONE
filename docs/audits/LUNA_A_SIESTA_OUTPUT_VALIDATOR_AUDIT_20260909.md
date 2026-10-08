# Luna A — SIESTA output adapter audit

## Scope

This change adds only an artifact validator for SIESTA nodes. It does not run
SIESTA, MPI, Hydra, or Slurm and does not modify launchers, campaigns,
materializers, or site profiles.

## Implemented safeguards

- The node must have an explicit FDF, output, and DM contract, with paths
  relative to the node directory.
- Absolute paths, `..` escapes, missing files, and empty files are rejected.
- A normal output without scientific evidence does not authorize the node.
- SCREENED outputs with `SCF_NOT_CONV`, abnormal termination, `MPI_Abort`,
  pseudopotential errors, or `FATAL` are rejected. `SCF_NOT_CONV` may appear in
  BARE only if the semantic sidecar proves it corresponds to intentional
  termination with fixed Hxc; the marker alone is not accepted.
- A reference requires magnetic evidence already validated by the existing
  SIESTA 5.4 parser, or an explicit and verified declaration of a
  non-polarized state.
- A SCREENED node requires normal termination, no unconverged-SCF markers, and
  a nonempty DM.
- A BARE node requires the existing versioned semantic sidecar, bound by
  SHA-256 to the executable, reference DM, FDF, output, and native trace. BARE
  is not inferred from `MaxSCFIterations`.
- Unknown modes, including SOC, non-collinearity, and uncertified variants,
  are rejected.
- The receipt contains a node digest, logical command, and artifact hashes;
  the validator also exposes structured provenance to the runtime.

## Focused tests

Executed without SIESTA/MPI/Slurm:

```text
python -m pytest tests/unit/test_siesta_output_validator.py \
  tests/unit/test_runtime_adapters.py \
  tests/unit/test_reference_magnetic_evidence.py \
  tests/unit/test_bare_semantics_evidence.py -q -p no:cacheprovider
18 passed
```

Tests cover valid SCREENED output, missing DM, explicit non-polarized
reference, unknown mode, and invalid BARE sidecar, as well as regressions for
existing parsers and adapters.

## Deliberate limitations

This is not yet a complete production executor: the runtime must implement
`CommandFactory` and produce the declared artifacts. It also does not enable
SOC, non-collinearity, multiple subspaces, or (U+V). The Yoltla test can only
be authorized after Terra integrates this validator into an isolated profile
and reviews the diff.
