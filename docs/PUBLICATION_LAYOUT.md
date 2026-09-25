# Public repository layout and evidence boundary

This repository contains the reusable LR-U implementation, its scientific
contracts, and compact evidence needed to inspect published claims. It is not
an archive of native high-performance-computing workspaces.

## Canonical layout

| Location | Public purpose |
|---|---|
| `src/` | Importable domain and backend code. |
| `tools/` | Reusable command-line helpers: preflight, projector audit, staging and DAG state gates. |
| `templates/slurm/` | Portable scheduler templates and local-profile examples. |
| `tests/` | Unit tests and frozen numerical regression tests. |
| `docs/` | Method, mathematical evidence, execution protocol and limitations. |
| `examples/` | Small, source-controlled input-only examples. |

## Evidence policy

Publish compact reconstructions: input provenance when redistribution is
permitted, semantic occupations, response matrices, direct-inversion
diagnostics, final results and a human-readable mathematical report. The raw
native outputs remain the audit source, but should be stored as a separately
versioned research-data archive with a manifest and checksum.

Do not commit campaign workspaces, scheduler stdout/stderr, density matrices,
Hamiltonian files, ion files, temporary SIESTA files, downloaded archives, or
private site profiles. This avoids repository bloat and prevents accidental
publication of user names, paths, host names, scheduler configuration or data
that cannot be redistributed.

## Pseudopotentials

Before publishing an example that includes a pseudopotential, verify its
redistribution license and cite its source. A campaign can always use a local
`pseudopotentials/` directory without that directory being committed.

## Migration rule

Existing tracked historical artefacts are not removed or rewritten by this
policy. Removing them, moving them to a data release, or changing Git history
requires a separate reviewed maintenance change.
