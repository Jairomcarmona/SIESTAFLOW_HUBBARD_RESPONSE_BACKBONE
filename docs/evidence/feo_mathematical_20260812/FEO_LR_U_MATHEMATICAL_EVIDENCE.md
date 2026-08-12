# FeO finite-difference linear-response Hubbard U: mathematical evidence

## Scope and source record

This supplement independently reconstructs the FeO PBE linear-response
calculation from native SIESTA output.  Its source is
`feo_pbe_lru_sc222_mathematical_evidence_20260812T224709Z.tar.gz`:

```text
SHA-256 d2808bc34cb1f1fc69a71e233a8d3529ebecf425cdbb88e9013a8bd79af80690
```

The hash agrees with the provided sidecar.  The archive contains nine physical
SIESTA calculations (one reference, four BARE, four SCREENED), their FDFs,
native `siesta.out`/`siesta.err`, and `0_NORMAL_EXIT` markers.  The complete
numerical supplement is
[`../../evidence_audit_feo_20260812.json`](../../evidence_audit_feo_20260812.json).

## Observable, finite difference, and matrix construction

For Fe Hubbard site \(I\), let \(n_I=\mathrm{Tr}(P_I\rho)\) be the scalar
Fe-3d projected occupation printed by SIESTA.  A local external perturbation
\(\alpha_JP_J\), with \(\alpha=\pm0.05\) eV, gives the centered responses

\[
 \chi^0_{IJ}=\frac{n_I^{\mathrm{BARE}}(+\alpha_J)-
 n_I^{\mathrm{BARE}}(-\alpha_J)}{0.10\ \mathrm{eV}},\qquad
 \chi_{IJ}=\frac{n_I^{\mathrm{SCREENED}}(+\alpha_J)-
 n_I^{\mathrm{SCREENED}}(-\alpha_J)}{0.10\ \mathrm{eV}}.
\]

The two explicitly perturbed AFM sublattices A and B generate two response
columns; eight translational replicas reconstruct the \(16\times16\) raw
matrices.  The reported matrices are symmetrized as
\(M=(M_\mathrm{raw}+M_\mathrm{raw}^{T})/2\).  Direct inversion then gives

\[
 K=(\chi^0)^{-1}-\chi^{-1},\qquad U_I=K_{II},\qquad
 U_\mathrm{Fe}=\frac1{16}\sum_IU_I.
\]

No pseudoinverse or regularization is used.

## Native-output selection and validation gates

The independent streaming parser found a complete 16-site occupation event in
every native output.  It selected the **second** complete event in BARE runs
and the **last** complete event in REFERENCE/SCREENED runs.  All nine runs had
normal SIESTA completion.  The reference and four SCREENED runs had no SCF
non-convergence or abnormal-termination marker.  All four BARE runs contain
the expected `SCF_NOT_CONV` marker, which is permitted by this deliberately
non-self-consistent BARE protocol.

The reference magnetic-state check obtained eight A-sublattice moments of
\(+3.641242\,\mu_B\), eight B-sublattice moments of
\(-3.641396\,\mu_B\), and total Fe moment \(-0.001232\,\mu_B\).  Thus the
reference is compensated AFM-II to the reported precision.

## Explicit numerical reconstruction

The first two rows and four columns of the independently reconstructed,
symmetrized matrices are

\[
\chi^0_{0:2,0:4}=\begin{pmatrix}
-2.441170& 0.100580&0.350560&0.100155\\
 0.100580&-2.440920&0.100155&0.350380
\end{pmatrix}\ \mathrm{e/eV},
\]

\[
\chi_{0:2,0:4}=\begin{pmatrix}
-0.142160&0.004025&0.009040&0.004050\\
 0.004025&-0.142160&0.004050&0.009040
\end{pmatrix}\ \mathrm{e/eV},
\]

\[
K_{0:2,0:4}=\begin{pmatrix}
 6.41023983&-0.07678731& 0.15417433&-0.07566684\\
-0.07678731& 6.41013793&-0.07566684& 0.15412829
\end{pmatrix}\ \mathrm{eV}.
\]

The full raw and symmetrized \(\chi^0\), \(\chi\), direct inverses, kernel,
site-resolved \(U\), native member paths, selected occupation vectors, and
response columns are preserved without truncation in the linked JSON
supplement.
The same final matrices and selected occupation vectors are typeset for
human review in the
[`FEO_COMPLETE_NUMERICAL_APPENDIX.md`](FEO_COMPLETE_NUMERICAL_APPENDIX.md).

## Acceptance results

| quantity | independently reconstructed value |
|---|---:|
| matrix dimension | 16 |
| rank(\(\chi^0\)) | 16 |
| rank(\(\chi\)) | 16 |
| cond(\(\chi^0\)) | 20.54373176098966 |
| cond(\(\chi\)) | 1.8959902361022125 |
| \(\lVert(\chi^0)^{-1}\chi^0-I\rVert\) | \(3.467243341686369\times10^{-15}\) |
| \(\lVert\chi^{-1}\chi-I\rVert\) | \(7.75166631348102\times10^{-16}\) |
| \(U_A\) mean | 6.410239833103002 eV |
| \(U_B\) mean | 6.410137925949487 eV |
| \(U_\mathrm{Fe}\) mean | **6.4101888795262445 eV** |

These results establish numerical execution of the declared Fe-3d,
PBE, finite-difference LR-U protocol.  They do not by themselves establish a
unique experimentally transferable Hubbard parameter: physical validation
requires comparing PBE+U observables under this exact projector definition.

## Reproduction

From the repository root:

```text
python tools/audit_lr_evidence_tar.py <evidence-tar.gz> --output docs/evidence_audit_feo_20260812.json
```

The auditor streams the compressed archive, parses native output, applies the
declared selectors and gates, reconstructs the matrices, and calls direct
`numpy.linalg.inv` only after the matrices are full rank.
