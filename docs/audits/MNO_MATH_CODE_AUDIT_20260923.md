# Focused Audit of Mathematics and Fixed Values: MnO

Date: 2026-09-23. The 28 archived BARE/SCREENED outputs and seven alpha
values were reread from
`campaigns/mno_afmii_strict_lr_v3r2/results/response-matrix-foreground-recovery-v4/`.
SIESTA was not run and frozen inputs were not modified.

## Is 11.532 eV an artifact of the inversion?

No evidence of that was found. Independent reconstruction from printed
occupation totals and the receipt's SHA-256 values gives the following checks
(eV):

| Operation on the same responses | Mean U |
|---|---:|
| Raw 16×16 matrices, direct inversion | 11.532055662576 |
| Symmetrized 16×16 matrices, direct inversion (published result) | 11.532055666425 |
| Diagonals only from both matrices, direct inversion | 11.654375296484 |
| Old rounded traces instead of native printed total | 11.531189060530 |

Symmetrization changes U by ~3.85×10⁻⁹ eV; the total contribution from
off-diagonal terms is −0.12232 eV; and the occupation-precision correction
changes U by +0.00087 eV. Spectral condition numbers of the raw matrices are
approximately 2.005 (BARE) and 1.254 (SCREENED). Fits over ±0.025, ±0.05, and
±0.10 eV give 11.5370, 11.5327, and 11.5321 eV. Thus, neither an ill-
conditioned inversion, symmetrization, nor old rounding explains an excess of
several eV. The internal factor of two in `dftu.F` on the
`DFTU.PotentialShift=true` branch multiplies `Ueff` by two to cancel the
`0.5` prefactor in the potential shift; with J=0, input alpha produces a
shift of alpha, not 2 alpha.

The 16×16 reconstruction from A/B representatives is a translation hypothesis
implemented in
`campaigns/mno_afmii_strict_lr_v3r2/scripts/lru_core.py:176`; this audit
checks the impact of its off-diagonal terms, not the physical symmetry of all
unmeasured columns. Removing those terms does not reduce U: it raises it to
11.654 eV.

## Mathematical defect in passing U to the functional

`tools/run_mno_afmii_response_quantized_v1.py` reads `printed_totals_e`, sums
the spins, and constructs a charge susceptibility.
`src/siestaflow_hubbard/domain/quantized_response.py:93` evaluates
`diag(inv(χ₀) − inv(χ))`; by construction, 11.532 eV is **scalar charge U**.
`campaigns/mno_afmii_strict_lr_v3r2/audits/uncertainty_assurance_20260923/prepare_physical_convergence.py:15`
sets `U_CENTRAL = 11.5321`, and line 40 inserts it without conversion into
the first `DFTU.Proj` record of the physical FDFs. With
`DFTU.PotentialShift=false`,
`third_party/siesta-5.4.2-source-audit/Src/dftu.F:682-713` interprets this
input as `Ueff = U-J` in a spin-resolved Dudarev potential.

Linscott et al., *Physical Review B* **98**, 235157 (2018), Sec. II B,
[full text](https://harvest.aps.org/v2/journals/articles/10.1103/PhysRevB.98.235157/fulltext),
show that scalar-response U combines interactions between spins and **does
not generally correspond** to the intra-spin parameter `Ueff=U−J`. This
makes the direct assignment used in the physical FDFs unjustified, but does
not show that scalar 11.532 eV was calculated incorrectly or determine a
replacement Ueff. Current data apply the same alpha to both spins and identify
only sums of spin-resolved response columns; they cannot reconstruct the full
matrix for independent spin perturbations. Table I of that paper reports
5.44 eV for Mn in MnO under its own method; it is not an interchangeable
numerical reference because it uses a different definition of χ₀, code, and
projectors. The ~10.88 eV value in the paper belongs to **oxygen** in MnO
(Table II), not Mn.

There is also a misleading label in
`src/siestaflow_hubbard/reporting/evidence_exporter.py:30,64`, which calls the
susceptibility inversion `U_eff` without demonstrating that correspondence.
In `src/siestaflow_hubbard/siesta_backend/fdf_builder.py:105-109,169-173`,
defaults `species="Mn", n=3, l=2, rc=3.0, omega=0.05` materialize generic
responses. These are hard-coded Mn 3d assumptions and must not be silently
applied to other materials; they did not produce this campaign's U, because
the campaign supplied its own projector.

Another fixed rule in the generic core,
`src/siestaflow_hubbard/domain/matrix_lr.py:208-219`, defines the internal
window as `|α|≤0.011 eV` and, if fewer than two points are available, replaces
the internal fit with the full fit. On a mesh such as MnO's (smallest nonzero
|α|: 0.025 eV), this makes the internal diagnostic identical to itself and
unable to detect window dependence. The audited campaign used its own analyzer
with windows of 0.025/0.05/0.10 eV, so this defect **did not produce** its
11.532 eV; it is a generality defect to fix in the core.

Minimal in-memory check: with MnO's seven alpha values and artificial
occupation `n(α)=1−0.05α−α³`, the core reports identical full and “internal”
slopes, −0.058125 e/eV, while the three actual central points give
−0.050625 e/eV. Only this algebraic check was run; no SIESTA.

## Bounded correction

Explicitly distinguish `U_scalar_charge` from `Ueff_Dudarev` in the result,
report, and transfer to FDF. Block automatic transfer of the former to the
latter in spin-polarized calculations until a compatible derivation or a
spin-resolved response with independent perturbations is available. Do not
replace 11.532 with 5.44 eV or a fitted value: the archived data do not
identify that parameter.
