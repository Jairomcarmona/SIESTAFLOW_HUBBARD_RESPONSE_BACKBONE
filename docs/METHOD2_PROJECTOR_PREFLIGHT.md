# Method-2 Hubbard Projector Preflight

This preflight is a locality audit before a finite-difference LR-U campaign.
It does **not** calculate U, modify an FDF, or declare a parameter converged.

## Two steps

1. Materialize the exact `LABEL.dftu_proj` produced by the chosen SIESTA
   executable, PSML, and Method-2 FDF configuration for every projected
   species label. The materializer waits for each radial table to become
   stable and complete; it is not an SCF or LR run.
2. Audit the radial norm and the calculation geometry. The audit produces a
   JSON record for machines and a Markdown summary for review.

Example for a four-process local run (paths are illustrative):

```bash
python tools/materialize_method2_projector.py \
  --fdf runs/00_REFERENCE/siesta.fdf \
  --central-label MnLR00 \
  --pseudo-source pseudopotentials/Mn.psml \
  --pseudo-source pseudopotentials/K.psml \
  --pseudo-source pseudopotentials/O.psml \
  --pseudo-source pseudopotentials/H.psml \
  --siesta /path/to/siesta --ranks 4 --output-dir projector_probe

python tools/audit_method2_projector.py \
  --fdf runs/00_REFERENCE/siesta.fdf \
  --psml pseudopotentials/Mn.psml \
  --projector projector_probe/MnLR00.dftu_proj \
  --central-label MnLR00 \
  --json-out projector_audit.json --markdown-out projector_audit.md
```

## Interpretation

The file stores \(f_l=R_l/r^l\), so the audit derives `l` from the file header,
checks it against the effective projector block, and computes the norm as
\(r^{2l+2}|f_l(r)|^2\,dr\). It rejects incomplete or non-finite grids and
non-positive norms. The DAG also checks that the reference and each accepted
response contain complete generated `.dftu_proj` files for the same projected
alias labels, with radial profiles matching the reference. The verifier follows the
SIESTA 5.4.2 precedence: `DFTU.ProjectorGenerationMethod` overrides the legacy
`LDAU.ProjectorGenerationMethod`, `DFTU.CutoffNorm` overrides
`LDAU.CutoffNorm`, and an existing `%block LDAU.Proj` takes precedence over
`%block DFTU.Proj`. The method and norm defaults are 2 and 0.90. When a shell
uses automatic `rc` (below SIESTA's `1e-4` threshold), the effective norm is
part of its identity. The audit includes the optional `E vcte rinn` values and
the effective `lambda` (default 1); it rejects unsupported multi-shell and
implicit-`l` forms instead of partially parsing them.

PSML selection prefers exact `LABEL.psml` files and validates their atomic
number. If an exact label is absent, all candidates for its Z must have one
unique content identity; distinct plausible PSMLs for the same Z fail closed.
Preflight manifests record a SHA-256 of the complete FDF, effective projector
configuration, and selected PSML for every FDF species. A cached Gate-0 audit
is reused only while those inputs still match. A file containing multiple
radial projector blocks is rejected pending an explicit multi-shell audit, so
a partial first-shell report cannot pass.
The audit compares the
materialized projector with the minimum-image neighbour distances in the FDF,
and proposes only a short human-review sensitivity window. A radius is never
chosen because it yields a preferred U value. Full LR validation still requires
converged screened calculations, linearity, full-rank response matrices, and
an explicit sensitivity assessment.
