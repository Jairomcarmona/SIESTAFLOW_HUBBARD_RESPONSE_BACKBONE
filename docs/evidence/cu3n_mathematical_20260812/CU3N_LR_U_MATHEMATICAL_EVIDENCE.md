# Cu₃N finite-difference linear-response Hubbard (U): mathematical and numerical evidence

## Abstract

This report documents the complete mathematical reconstruction of the Cu₃N
linear-response Hubbard-(U) campaigns executed with SIESTA 5.4.2. The
occupation vectors were independently parsed from the native `siesta.out`
members of the evidence archive. The response matrices, their direct
inverses, the Hubbard kernel, and the site-resolved (U) values were then
reconstructed without using the packaged production result as an input.

The four campaigns are numerically well-conditioned and give
$U_\mathrm{Cu}=12.41$--$12.72$ eV for the declared Cu-3d projector
subspace. This is a protocol-specific result, not a universal material
constant.

## 1. Scope and provenance

The source archive is:

```text
cu3n_mathematical_evidence_20260812T210120Z.tar.gz
SHA256 76f5effd3d124d1723725a9f30d4ac17056b4d892f73b4c14c6028f96a87f11f
```

It contains 4 campaigns and 56 SIESTA calculations (13 per campaign). The
independent extraction tool is:

```text
tools/extract_cu3n_math_evidence.py
```

The machine-readable supplements are the four campaign JSON files in this
directory. They contain the complete occupation vectors, response columns,
raw and symmetrized matrices, direct inverses, Hubbard kernel, site-resolved
(U), convergence gates, and source member paths.

The review files are:

- `CU3N_PBE_LRU_SC222_RC3p0_V1.json`
- `CU3N_PBE_LRU_SC222_K333_RC3p0_V1.json`
- `CU3N_PBE_LRU_SC222_TZP_RC3p0_V1.json`
- `CU3N_PBE_LRU_SC333_K222_RC3p0_V1.json`

The archive itself remains the record needed to inspect the native FDF, OUT,
ERR, and `0_NORMAL_EXIT` files. The compact JSON supplements do not replace
those native outputs.

## 2. Declared calculation protocol

| quantity | SC222 baseline | SC222 k-grid | SC222 basis | SC333 |
|---|---:|---:|---:|---:|
| supercell | $2\times2\times2$ | $2\times2\times2$ | $2\times2\times2$ | $3\times3\times3$ |
| atoms | 32 | 32 | 32 | 108 |
| Hubbard Cu sites | 24 | 24 | 24 | 81 |
| basis | DZP | DZP | TZP | DZP |
| k-grid | $2\times2\times2$ | $3\times3\times3$ | $2\times2\times2$ | $2\times2\times2$ |
| $E_\mathrm{shift}$ | 0.005 Ry | 0.005 Ry | 0.005 Ry | 0.005 Ry |
| mesh cutoff | 200 Ry | 200 Ry | 200 Ry | 200 Ry |
| projector | Cu 3d | Cu 3d | Cu 3d | Cu 3d |
| projector method | 2 | 2 | 2 | 2 |
| $r_c$ | 3.0 Bohr | 3.0 Bohr | 3.0 Bohr | 3.0 Bohr |
| $\omega$ | 0.05 Bohr | 0.05 Bohr | 0.05 Bohr | 0.05 Bohr |
| perturbation | $\pm0.05$ eV | $\pm0.05$ eV | $\pm0.05$ eV | $\pm0.05$ eV |

The materialized reference FDFs report PBE, non-spin-polarized Cu₃N, and
`SCF.MustConverge T`. Reference and SCREENED calculations require normal
completion and SCF convergence. BARE calculations intentionally use the
non-self-consistent response protocol (`SCF.MustConverge F`, two SCF steps).

## 3. Observable and perturbation

For correlated site $I$, SIESTA prints the scalar projected occupation

\[
n_I = \operatorname{Tr}(P_I\rho),
\]

where (P_I) is the Cu-3d projector and (ho) is the one-particle density
matrix. A local perturbation is applied as

\[
\Delta V_\mathrm{ext}=\sum_J \alpha_J P_J.
\]

For these non-spin-polarized Cu₃N runs, the two values printed after
`Occupations:` are summed to obtain $n_I$. The parser verifies complete
24-site or 81-site Hubbard occupation events. It selects the second complete
event for every BARE output and the last complete event for REFERENCE and
SCREENED outputs.

## 4. Bare and screened response matrices

For a perturbation on site $J$, the independent-particle (BARE) and
self-consistent (SCREENED) response columns are evaluated by the centered
finite difference

\[
\chi^{0}_{IJ}
\equiv \left.\frac{\partial n_I}{\partial\alpha_J}\right|_0
\simeq
\frac{n_I^{\mathrm{BARE}}(+\alpha_J)-
      n_I^{\mathrm{BARE}}(-\alpha_J)}{2\alpha_J},
\]

\[
\chi_{IJ}
\equiv \left.\frac{\partial n_I}{\partial\alpha_J}\right|_0
\simeq
\frac{n_I^{\mathrm{SCREENED}}(+\alpha_J)-
      n_I^{\mathrm{SCREENED}}(-\alpha_J)}{2\alpha_J}.
\]

Here $2\alpha=0.10$ eV, so both matrices have units electrons/eV.

The campaigns explicitly perturb the three parent Cu sublattices X, Y, and
Z. For a supercell side $L$, site $I=(t,s)$ has translation index
$t=iL^2+jL+k$ and parent sublattice $s$ in {X,Y,Z}. If $T_t$ is the
permutation induced by translating the parent occupation vector, the complete
matrix is reconstructed as

\[
\chi^0_{:,3t+s}=T_t c_s^0,
\qquad
\chi_{:,3t+s}=T_t c_s,
\]

where $c_s^0$ and $c_s$ are the three explicitly measured finite-difference
columns. The raw matrices are retained. The reported matrices are

\[
\chi^0=\frac{\chi^0_\mathrm{raw}+(\chi^0_\mathrm{raw})^T}{2},
\qquad
\chi=\frac{\chi_\mathrm{raw}+\chi_\mathrm{raw}^T}{2}.
\]

The full numerical arrays are in the `matrices` object of each campaign JSON.
The corresponding Cu label, parent orientation, translation, and fractional
coordinate map are retained in the `site_map` object.

## 5. Hubbard kernel and reported $U$

The Cococcioni--de Gironcoli linear-response kernel is

\[
K=\left(\chi^0\right)^{-1}-\chi^{-1}.
\]

Because chi is in electrons/eV, K has units eV. The site-resolved
on-site parameters and the reported scalar are

\[
U_I=K_{II},
\qquad
U_\mathrm{Cu}=\frac{1}{N}\sum_{I=1}^{N}U_I.
\]

The off-diagonal $K_{IJ}$ values are retained as intersite response
couplings. The parser checks full rank before calling `numpy.linalg.inv` and
never uses a pseudoinverse or regularization.

## 6. Explicit numerical reconstruction (SC222 baseline)

The first three rows and columns of the reconstructed baseline matrices are:

\[
\chi^0_{0:3,0:3}=\begin{pmatrix}
-0.10314 & 0.00190 & 0.00190\\
 0.00190 &-0.10314 & 0.00190\\
 0.00190 & 0.00190 &-0.10314
\end{pmatrix}\;\mathrm{e/eV},
\]

\[
\chi_{0:3,0:3}=\begin{pmatrix}
-0.04462 & 0.00002 & 0.00002\\
 0.00002 &-0.04462 & 0.00002\\
 0.00002 & 0.00002 &-0.04462
\end{pmatrix}\;\mathrm{e/eV}.
\]

The corresponding kernel block is

\[
K_{0:3,0:3}=\begin{pmatrix}
12.6739439391&-0.1994107952&-0.1994612325\\
-0.1994107952&12.6739439391&-0.1994612325\\
-0.1994612325&-0.1994612325&12.6738889527
\end{pmatrix}\;\mathrm{eV}.
\]

The complete 24x24 and 81x81 matrices are not truncated; they are stored in
the per-campaign JSON supplements.

## 7. Acceptance and convergence diagnostics

The mathematical acceptance conditions are:

1. normal SIESTA completion for every run;
2. converged SCF for REFERENCE and every SCREENED run;
3. a complete semantic occupation vector for every run;
4. `rank(chi0) = rank(chi) = N`;
5. direct-inversion residuals reported and numerically small.

All four campaigns satisfy these conditions. The 24 BARE runs contain the
expected `SCF_NOT_CONV` marker because BARE is deliberately run with the
non-self-consistent response settings. None of the four reference runs or 24
SCREENED runs contains a convergence or abnormal-termination marker.

| campaign | $U_\mathrm{Cu}$ (eV) | rank($\chi^0$) | rank($\chi$) | cond.($\chi^0$) | cond.($\chi$) | residuals |
|---|---:|---:|---:|---:|---:|---|
| SC222 DZP, 2x2x2 | 12.6739256103 | 24 | 24 | 1.38407 | 1.04189 | (1.1\times10^{-15},1.3\times10^{-15}) |
| SC222 DZP, 3x3x3 | 12.7085110520 | 24 | 24 | 1.37535 | 1.03453 | (2.3\times10^{-15},1.1\times10^{-15}) |
| SC222 TZP, 2x2x2 | 12.4122870790 | 24 | 24 | 1.38548 | 1.04653 | (9.8\times10^{-16},3.3\times10^{-15}) |
| SC333 DZP, 2x2x2 | 12.7238655441 | 81 | 81 | 1.37266 | 1.03101 | (4.8\times10^{-15},2.6\times10^{-15}) |

Relative to the SC222 DZP baseline, the changes are:

- k-grid 2x2x2 to 3x3x3: approximately (+0.27\%\);
- DZP to TZP: approximately (-2.06\%\);
- SC222 to SC333: approximately (+0.39\%\).

These are numerical stability observations under the declared protocol, not
an assertion that the Cu-3d subspace is physically unique.

The supplements also retain the singular-value spectra and the relative
Frobenius antisymmetry of each raw response matrix. These diagnostics make the
rank and symmetrization decisions independently inspectable rather than
implicit in the reported scalar (U).

## 8. Reproduction

From the repository root:

```bash
python tools/extract_cu3n_math_evidence.py \
  cu3n_mathematical_evidence_20260812T210120Z.tar.gz \
  --output-dir docs/evidence/cu3n_mathematical_20260812
```

The parser performs one sequential pass over the compressed TAR, parses native
SIESTA outputs, reconstructs the matrices, checks convergence/rank, computes
the direct inverses, and compares scalar diagnostics with the packaged result
JSON. No SIESTA execution is required for this audit.

The SIESTA executable identified in the native header is version 5.4.2 with
MPI parallelization. Site-specific filesystem paths and hostnames are not
part of this public report.

## 9. Limitations and publication claim

This evidence establishes that the declared SIESTA outputs produce a complete,
well-conditioned, directly invertible finite-difference response calculation
and that the reconstruction is reproducible from native output.

It does not establish that $U_\mathrm{Cu}\approx12.7$ eV is a universal Cu₃N
parameter. The result depends on PBE, pseudopotentials, basis, mesh cutoff,
k-grid, supercell, Cu-3d projector, $r_c$, $\omega$, and the occupation
definition. A physical paper must also state the projector/subspace choice,
discuss Cu-3d/N-2p hybridization, and validate the effect of (U) on the
reported observable (for example bands, PDOS, or dielectric response).

The mathematical result follows the finite-difference linear-response
construction of Cococcioni and de Gironcoli, *Phys. Rev. B* **71**, 035105
(2005), DOI: [10.1103/PhysRevB.71.035105](https://doi.org/10.1103/PhysRevB.71.035105).
