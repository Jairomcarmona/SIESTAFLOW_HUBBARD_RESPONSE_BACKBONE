# Method-2 Hubbard Projector Preflight

This preflight is a locality audit before a finite-difference LR-U campaign.
It does **not** calculate U, modify an FDF, or declare a parameter converged.

## Two steps

1. Materialize the exact `LABEL.dftu_proj` produced by the chosen SIESTA
   executable, PSML, and Method-2 FDF configuration. The materializer stops
   after this initialization artifact is present; it is not an SCF or LR run.
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

The audit computes the radial norm using \(r^2|R_l(r)|^2\,dr\), compares the
materialized projector with the minimum-image neighbour distances in the FDF,
and proposes only a short human-review sensitivity window. A radius is never
chosen because it yields a preferred U value. Full LR validation still requires
converged screened calculations, linearity, full-rank response matrices, and
an explicit sensitivity assessment.
