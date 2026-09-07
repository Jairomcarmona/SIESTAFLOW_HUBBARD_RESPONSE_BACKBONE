# β-MnO₂ finite-difference linear-response Hubbard U: mathematical evidence

## Source record

The reconstruction uses native output in
`beta_mno2_pbe_lru_sc222_mathematical_evidence_20260812T230910Z.tar.gz`.

```text
SHA-256 b4b0a0c388ccfeab51de352b2f4c74124ea7c9c98916f4da7ee93e105303bd1c
```

The SHA-256 matches the supplied sidecar. The archive contains nine physical
SIESTA calculations, their FDFs, `siesta.out`, `siesta.err`, normal-exit
markers, campaign scripts, Slurm record, and raw campaign artifacts.

## Mathematical reconstruction

For projected Mn-3d occupation \(n_I=\mathrm{Tr}(P_I\rho)\), the centered
finite-difference columns used \(\alpha=\pm0.05\) eV:

\[
\chi^0_{IJ}=\frac{n_I^{\mathrm{BARE}}(+\alpha_J)-n_I^{\mathrm{BARE}}(-\alpha_J)}{0.10\ \mathrm{eV}},\qquad
\chi_{IJ}=\frac{n_I^{\mathrm{SCREENED}}(+\alpha_J)-n_I^{\mathrm{SCREENED}}(-\alpha_J)}{0.10\ \mathrm{eV}}.
\]

Explicit A/B response columns are translated over the eight supercell
translations to form the raw \(16\times16\) matrices. The reported matrices
are \(M=(M_{\rm raw}+M_{\rm raw}^{T})/2\). Direct inversion gives

\[
K=(\chi^0)^{-1}-\chi^{-1},\qquad U_I=K_{II},\qquad
U_{\rm Mn}=\frac1{16}\sum_IU_I.
\]

No pseudoinverse or regularization is used.

## Native-output gates

The independent parser finds a full 16-site semantic Hubbard occupation event
in every output. It selects the second complete event for BARE and the last
complete event for REFERENCE and SCREENED. All nine runs have normal SIESTA
completion. REFERENCE and all SCREENED outputs have no non-convergence or
abnormal-termination marker. The four BARE outputs carry `SCF_NOT_CONV`, as
expected and permitted for the non-self-consistent BARE response protocol.

## Acceptance results

| quantity | independently reconstructed value |
|---|---:|
| matrix dimension | 16 |
| rank(\(\chi^0\)) | 16 |
| rank(\(\chi\)) | 16 |
| cond(\(\chi^0\)) | 1.4802816659875395 |
| cond(\(\chi\)) | 1.0800691742326929 |
| \(\lVert(\chi^0)^{-1}\chi^0-I\rVert\) | \(9.049262160060089\times10^{-16}\) |
| \(\lVert\chi^{-1}\chi-I\rVert\) | \(9.62112949493216\times10^{-16}\) |
| \(U_A\) mean | 6.876561970501046 eV |
| \(U_B\) mean | 6.876056460897843 eV |
| \(U_{\rm Mn}\) mean | **6.876309215699443 eV** |

The complete selected occupations, response columns, raw and symmetrized
matrices, direct inverses, kernel, and sixteen diagonal values are typeset in
[`BETA_MNO2_COMPLETE_NUMERICAL_APPENDIX.md`](BETA_MNO2_COMPLETE_NUMERICAL_APPENDIX.md).
The unrounded machine-readable values and archive member paths remain in the
linked JSON supplement.
