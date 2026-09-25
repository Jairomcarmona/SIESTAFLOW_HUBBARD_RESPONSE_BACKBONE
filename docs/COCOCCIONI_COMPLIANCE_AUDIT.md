# Cococcioni LR-U compliance audit

## Scope and verdict

This is a code-and-evidence audit against the methodological contract
`Cococcioni Linear-Response Hubbard (U)` supplied for this project, and the
finite-difference LR-cDFT formulation of Cococcioni and de Gironcoli.

**Overall status: PARTIAL.**  The implemented finite-difference matrix algebra
and the demonstrated BARE/SCREENED execution chain are compatible with the
method.  Two requirements remain scientifically unresolved for the current
SIESTA campaigns:

1. **LR-06 (BARE = \(\chi^0\)) is UNRESOLVED.**  The workflow selects a
   reproducible event from a two-iteration SIESTA calculation, but no native
   SIESTA semantic evidence proves that this event occurs after the first
   diagonalization of \(H_{KS}[\rho_0]+\alpha P\) and before rebuilding
   Hartree–XC from the perturbed density.
2. **LR-14 (supercell convergence) is NOT_YET_TESTED for the ordered
   birnessite result.**  A 32-atom ordered cell is not, by itself, evidence of
   the isolated-perturbation limit.

Consequently, results must be labelled **one-shot \(U_{LR}^{DFT}\)** for the
declared manifold, not self-consistent \(U_{scf}\), and not a
supercell-converged bulk value.

The foundational formulation requires that the response be internally
consistent with the occupation-matrix definition; it also states that results
depend strongly on the definition of the localized orbitals. [Cococcioni and
de Gironcoli (2005)](https://doi.org/10.1103/PhysRevB.71.035105).  Modern DFPT
work likewise identifies projector choice and Hubbard parameters as coupled
choices. [Timrov, Marzari and Cococcioni (2022)](https://arxiv.org/abs/2203.15684).

## Requirement matrix

| Requirement | Status | Code / evidence | Finding and required action |
|---|---|---|---|
| LR-01 manifold explicit | PASS | `tools/build_k_birnessite_initial_lru.py:76-80`; `campaign.json` | Mn-3d, Method-2, \(r_c\), \(\omega\), sites and pseudos are declared. |
| LR-02 same manifold | PARTIAL | FDF generator uses one `DFTU.Proj` block for occupation and perturbation | Consistent inside the LR campaign. A production DFT+U input-fingerprint gate is not yet demonstrated. |
| LR-03 \(\alpha P_J\) | PASS | `tools/build_k_birnessite_initial_lru.py:76-80` | Only the target label receives signed `DFTU.Proj` potential shift; `DFTU.PotentialShift true`. |
| LR-04 signed perturbations | PASS | campaign manifests and evidence audit | Every target has \(+\alpha\) and \(-\alpha\). |
| LR-05 linear regime | PASS for birnessite validation; PARTIAL generically | `01_ALPHA_LINEARITY`; `production_benchmarks/lr_arithmetic.py:176-244` | 0.025/0.050/0.100 eV were tested. Generic three-point mode alone cannot establish a window. |
| LR-06 BARE definition | UNRESOLVED | `observation_selector.py:57-85`; generator BARE FDF at `tools/build_k_birnessite_initial_lru.py:83-84` | Selecting `scf_iteration == 2` / the second complete event with `MaxSCFIterations 2` is not proof of frozen-Hxc first response. A SIESTA semantic trace or controlled reference experiment is required. |
| LR-07 SCREENED definition | PASS | SCREENED FDF at `tools/build_k_birnessite_initial_lru.py:85-86`; archive audit | Full SCF is required; all 84 SCREENED runs in the validation archive have normal completion and no SCF nonconvergence marker. |
| LR-08 common reference | PARTIAL | DAG stages children from `runs/00_REFERENCE/00_REFERENCE.DM`; `DM.UseSaveDM true` | Same parent DM is copied operationally. The campaign archive does not preserve/check a per-child DM hash or prove the DM was accepted unchanged by SIESTA. |
| LR-09 global response | PASS | six occupations are parsed for every perturbation | Each perturbation records the occupation vector of all six Mn manifolds. |
| LR-10 complete matrices | PASS | `production_benchmarks/lr_arithmetic.py:111-158`; evidence appendix | Row \(I\)=observed site and column \(J\)=perturbed site; full 6x6 matrices are reconstructed. |
| LR-11 matrix inverse | PASS in production path | `production_benchmarks/lr_arithmetic.py:248-320` | Full-rank check then `numpy.linalg.inv`; no diagonal-only formula. |
| LR-12 signs and order | PASS | `production_benchmarks/lr_arithmetic.py:24-31, 305-306` | Central differences retain signs and use \(K=\chi_0^{-1}-\chi^{-1}\). |
| LR-13 on-site extraction | PASS | `production_benchmarks/lr_arithmetic.py:305-306`; evidence appendix | \(U_I=K_{II}\); off-diagonal kernel entries are retained. |
| LR-14 supercell limit | NOT_YET_TESTED | birnessite campaign metadata | No size series \(U(L)\) for the birnessite structure. Do not claim isolated-perturbation convergence. |
| LR-15 no artificial neutrality | PASS in production path | no row/column-sum transformation in `lr_arithmetic.py` | No neutralizing row/column projection is applied. |
| LR-16 symmetry reconstruction | NOT_APPLICABLE for birnessite | `no_symmetry_reduction: true` | All six Mn sites were explicitly perturbed; no equivalence claim is needed. Generic symmetry reconstruction requires its own proof. |
| LR-17 numerical QA | PASS for audited campaign | evidence audit and appendix | Alpha sensitivity, raw asymmetry, ranks, condition numbers and inverse residuals are preserved. Thresholds are implementation QA, not Cococcioni axioms. |
| LR-18 raw evidence | PASS | `docs/evidence_audit_k_birnessite_minimum_validation_20260815.json` | Raw/symmetrized matrices, inverses, kernels, selected occupations and native-output paths are retained. |
| LR-19 projector dependence | PASS conceptually | `04_PROJECTOR_RC2p5` evidence | \(r_c=2.5\) and 3.0 Bohr are reported as distinct manifolds, not averaged. |
| LR-20 no projector averaging | PASS | validation report | No average across radii is formed. |
| LR-21 frozen \(V_{Hub}\) for \(U_{scf}\) | NOT_APPLICABLE / UNRESOLVED | one-shot PBE campaign only | No prior DFT+U potential is present. SIESTA support for frozen pre-existing \(V_{Hub}\) has not been demonstrated. |
| LR-22 structure–U self-consistency | NOT_APPLICABLE | no DFT+U relaxation loop | Required only if claiming a relaxed self-consistent structure/U solution. |

## Evidence actually established

- The independent archive audit verifies SHA-256, 173 native outputs and 173
  normal-exit markers.
- Every required REFERENCE and SCREENED calculation passes its convergence
  gate; intentionally non-self-consistent BARE calculations are not mistaken
  for failed SCREENED calculations.
- Direct reconstruction reproduces stored \(\chi^0\), \(\chi\), \(K\), and
  \(U\) to \(10^{-9}\); each reconstructed matrix has rank six and modest
  condition number.
- The reported 3.0-Bohr result is therefore a reproducible
  \(U_{LR}^{DFT}[P_{\mathrm{Method\,2}}(3.0,0.05)]\), not an element-wide
  constant and not \(U_{scf}\).

## Architecture discrepancies requiring attention

### 1. Duplicated analysis paths

The Yoltla campaign generators embed standalone `ANALYZE` strings
(`tools/build_k_birnessite_initial_lru.py:113-151`), while the reusable
production implementation is `production_benchmarks/lr_arithmetic.py` and
`src/siestaflow_hubbard/domain/matrix_lr.py`.  They currently use the same
central-difference/direct-inversion equations, but are separate code paths.
This is a **traceability and regression risk**, not evidence of a wrong matrix
calculation.  Future campaign generators should import one tested production
analysis module rather than embed a second parser/arithmetic implementation.

### 1a. Inversion target is explicit in the reusable matrix engine

`src/siestaflow_hubbard/domain/matrix_lr.py` now takes and preserves
`matrix_for_inversion = raw | symmetrized`; rank, condition, inverse,
residuals, \(K\), and reported \(U\) use exactly that selected representation.
Raw and symmetric matrices remain distinct evidence. Materialized campaign
generators still need to import this common production path rather than keep a
separate embedded analysis string.

### 2. Pseudoinverse is prohibited in the LR source tree

The historical opt-in pseudoinverse fallback is fail-closed: enabling it now
raises an error, and an adversarial source-tree test rejects direct
pseudoinverse calls in `src/`. The production contract is direct inversion
only.

### 3. BARE semantic proof is the first physical priority

Do not replace LR-06 with a heuristic such as “two iterations means bare.”
The required test is a controlled SIESTA experiment plus parser provenance
showing event line ranges, SCF iteration, density/mixing state, and whether
the Hamiltonian has been rebuilt from perturbed density before the selected
occupation.  Until then the workflow is a **candidate finite-difference
implementation of \(\chi^0\)**, not a fully demonstrated Cococcioni BARE
implementation.

## Ordered next actions

1. Execute `SIESTA_BARE_SEMANTIC_VERIFICATION_PROTOCOL.md` with a minimal
   instrumented SIESTA run;
   either promote LR-06 to PASS or keep it UNRESOLVED.
2. Add a birnessite supercell-size series and compare the final diagonal
   \(U(L)\), not merely individual response entries.
3. Add a production-level projector fingerprint check between LR evidence and
   any subsequent DFT+U FDF.
4. Consolidate the campaign analysis onto the tested production module; add a
   regression fixture covering the semantic event selection.

No numerical result should be tuned to a literature value while resolving
these items.
