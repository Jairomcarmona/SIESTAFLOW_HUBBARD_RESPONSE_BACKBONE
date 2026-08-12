# β-MnO₂ LR-U adversarial evidence audit

## Scope

This audit challenges the numerical result with checks that are independent
of merely reading the campaign's final result JSON.  It uses the native
SIESTA archive
`beta_mno2_pbe_lru_sc222_mathematical_evidence_20260812T230910Z.tar.gz`.

```text
SHA-256 b4b0a0c388ccfeab51de352b2f4c74124ea7c9c98916f4da7ee93e105303bd1c
```

## Findings

| challenge | independent evidence | result |
|---|---|---|
| archive identity | SHA-256 against supplied sidecar | PASS |
| run coverage | 9 FDF, 9 native OUT, 9 ERR, 9 normal-exit markers | PASS |
| perturbation sign/site | FDF blocks place \(-0.0500\) and \(+0.0500\) eV only on MnLR00 (A) or MnLR01 (B) | PASS |
| common initial state | all eight children declare `00_REFERENCE/00_REFERENCE.DM` | PASS |
| convergence gates | REFERENCE and all four SCREENED outputs have no `SCF_NOT_CONV`, abnormal termination, or MPI abort marker | PASS |
| BARE semantics | all four BARE outputs use two SCF iterations, `SCF.MustConverge F`, and their expected `SCF_NOT_CONV` is permitted | PASS |
| semantic extraction | every accepted run contains a complete 16-site occupation vector; BARE selects event 2 and REFERENCE/SCREENED the final event | PASS |
| response reconstruction | \(\chi^0\) and \(\chi\) are full-rank 16x16 matrices after the declared translation reconstruction and symmetrization | PASS |
| inverse stability | cond(\(\chi^0\)) = 1.4802816659875395; cond(\(\chi\)) = 1.0800691742326929 | PASS |
| direct inversion | residuals are \(9.0493\times10^{-16}\) and \(9.6211\times10^{-16}\); no pseudoinverse or regularization | PASS |
| result replication | native-OUT reconstruction: 6.876309215699443 eV; campaign artifact: 6.876309215699445 eV; difference \(1.78\times10^{-15}\) eV | PASS |
| site-value replication | maximum difference across all 16 diagonal values: 0.0 eV | PASS |
| magnetic reference | A moments \(+2.633562\,\mu_B\), B moments \(-2.633431\,\mu_B\), net \(+0.001048\,\mu_B\) | PASS |

## Response sanity check

The target-site slopes reconstructed from the native occupations are

\[
\left.\frac{\partial n_A}{\partial\alpha_A}\right|_{\rm BARE}
=-0.61115\ \mathrm{e/eV},\quad
\left.\frac{\partial n_A}{\partial\alpha_A}\right|_{\rm SCREENED}
=-0.11736\ \mathrm{e/eV},
\]

\[
\left.\frac{\partial n_B}{\partial\alpha_B}\right|_{\rm BARE}
=-0.61124\ \mathrm{e/eV},\quad
\left.\frac{\partial n_B}{\partial\alpha_B}\right|_{\rm SCREENED}
=-0.11737\ \mathrm{e/eV}.
\]

The screened-to-bare target response ratios are 0.19203 (A) and 0.19202
(B). They have the expected common sign and comparable sublattice response;
there is no evidence here of a site-indexing or perturbation-sign inversion.

## Scientific boundary

This audit establishes that the archived SIESTA outputs correctly implement
the declared finite-difference LR-U calculation and that the scalar follows
from complete, well-conditioned matrices. It does not establish that this
protocol-specific value is fully converged with respect to supercell, k-grid,
basis, or projector radius, nor that it is automatically transferable to
other properties or structures.
