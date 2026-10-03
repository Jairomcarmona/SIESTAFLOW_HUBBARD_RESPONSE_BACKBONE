# NiO P5 SIESTA output inventory (I.5)

Inspected the completed, real campaign `nio_p5_product_2` under
`/home/jmc/.local/state/siestaflow/campaigns/nio_p5_product_2`. The selected
perturbations are `NiLR0`, alpha = -0.06 eV, one BARE and one SCREENED run.
Both are validated with `0_NORMAL_EXIT`; SIESTA 5.4.2 used four Open MPI
ranks.

## Files produced

Both run directories contain `0_NORMAL_EXIT`, `BASIS_ENTHALPY`,
`BASIS_HARRIS_ENTHALPY`, `CLOCK`, `FORCE_STRESS`, `INPUT_TMP.<pid>`,
`MESSAGES`, `NIO_PBE_REFERENCE.DM`, `NON_TRIMMED_KP_LIST`,
`NiLR0.dftu_proj`, `NiLR0.ion`, `NiLR0.ion.xml`, `NiLR0.psml`,
`NiLR1.dftu_proj`, `NiLR1.ion`, `NiLR1.ion.xml`, `NiLR1.psml`, `O.ion`,
`O.ion.xml`, `O.psml`, `OUTVARS.yml`, `PARALLEL_DIST`, `TIMES`, a timestamped
`fdf.*.log`, `siesta.err`, `siesta.fdf`, and `siesta.out`.

Both produce `<system_label>.BASIS_ENTHALPY`, `.BONDS`, `.BONDS_FINAL`, `.DM`,
`.EIG`, `.FA`, `.KP`, `.ORB_INDX`, `.STRUCT_OUT`, `.XV`, `.alloc`, `.bib`, and
`.times`. The SCREENED output additionally has `<system_label>.HSX`. The run
labels are `lr_s000_m0p06_bare` and `lr_s000_m0p06_screened` respectively.

## `siesta.out` blocks

Line numbers below refer to the selected BARE output. The corresponding
SCREENED output has the same blocks, shifted by one line in the initial
occupation section.

| Block | Example line | Evidence |
|---|---:|---|
| FFT mesh and cutoff | 1010 | `InitMesh: MESH = 48 x 24 x 24 = 27648` |
| Spin-resolved Hubbard projector occupation matrices by atom/site | 1018 | `hubbard_term: atom, species: 1 1`; the following 5×5 matrix has separate up/down columns |
| Spin-resolved total occupations | 1045 | `Occupations: 4.906378 3.532831 8.439209` (up, down, total) |
| Fermi–Dirac occupations applied | 1078 | `stepf: Fermi-Dirac step function` |
| SCF iteration table and final printed residuals | 1165–1167 | Header at 1165, row at 1166, total spin moment at 1167; this run reports one SCF iteration |
| Geometric-step `dDmax` / `dHmax` | 1170 | `Geom step, scf iteration, dDmax, dHmax: 0 1 0.005574 0.017121` |
| Mulliken populations by spin | 1257–1259 | `mulliken: Atomic and Orbital Populations:` and `mulliken: Spin UP` (Spin DOWN follows) |
| Fermi energy | 1374 | `siesta: Fermi = -4.547981` eV |
| Normal completion | 1490 | `Job completed` |

No eigenvalue list is printed in this `siesta.out`. SIESTA produced the
`<system_label>.EIG` eigenvalue artifact in each run directory; the output
mentions the band-structure energy at line 1359, not the eigenvalue list.

Inspected stdout paths:

- BARE: `.siestaflow/attempts/a9b894b5b55ba9409a6b/attempt-1791024507287507793-9981d124/response_lr_s000_m0p06_bare_a9b894b5b55b/siesta.out`
- SCREENED: `.siestaflow/attempts/365d9074957c7d4a53a6/attempt-1791024512703838316-6eea6535/response_lr_s000_m0p06_screened_365d9074957c/siesta.out`
