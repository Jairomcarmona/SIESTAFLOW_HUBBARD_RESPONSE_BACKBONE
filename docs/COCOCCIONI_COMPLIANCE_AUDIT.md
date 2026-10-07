# Cococcioni LR-U compliance audit

## Scope and verdict

This is a code-and-evidence audit against the methodological contract
`Cococcioni Linear-Response Hubbard (U)` supplied for this project, and the
finite-difference LR-cDFT formulation of Cococcioni and de Gironcoli.

**Overall status: PARTIAL.**  The implemented finite-difference matrix algebra
and the demonstrated BARE/SCREENED execution chain are compatible with the
method.  LR-06 is now **PASS for the source-audited SIESTA 5.4.2 PotentialShift
profile**, based on the native Yoltla output and end-to-end selector test
recorded below. This verifies the profile's BARE event selection; it does not
certify every historical campaign or grant the separate legacy
`VERIFIED_BARE` certificate. LR-14 (supercell convergence) remains
**NOT_YET_TESTED** for the ordered birnessite result. A 32-atom ordered cell
is not, by itself, evidence of the isolated-perturbation limit.

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
| LR-06 BARE definition | PASS for the source-audited SIESTA 5.4.2 PotentialShift profile | Native Yoltla output SHA-256 `f28dbe35ff17734f9291676dccf9592e4cc0d09049d6192237be82ea4786eb20`; trace SHA-256 `3c909d4e94a34c7685cb31f89ca1193098a4eb7ba5b50396fd5266d41b186028`; `src/hubbardflow/siesta_backend/siesta542_bare_profile.py::Siesta542PotentialShiftHamiltonianProfile.select_response`; `tests/unit/test_lr06_trace_excerpt.py` | The real 48-atom 4x4 BARE output selects the event at native line 4546 (trace line 101), with occupations `3.731167 / 0.965385 / 4.696552`, after `stepf` at native line 4516 (trace line 71) and before indented `scf: 1` at native line 4575 (trace line 130). The earlier summary at trace line 67 is the pre-perturbation event and is not selected. `SCF_NOT_CONV` at trace line 133 is expected with `MaxSCFIterations 1`. The SIESTA 5.4.2 binary SHA-256 is `c69519dc7296ca8f9e454303947084ee246efd609be4bc05244a31a91b82e37e`. The full output is cited by digest and is not included; the fixture stores only the selector-relevant excerpts. |
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
- The full native Yoltla output has SHA-256
  `f28dbe35ff17734f9291676dccf9592e4cc0d09049d6192237be82ea4786eb20` and
  was checked with `Siesta542PotentialShiftHamiltonianProfile.select_response`.
  Its selected response summary is native output line 4546 (trace line 101),
  after `stepf` at line 4516 (trace line 71) and before the first indented
  `scf: 1` at line 4575 (trace line 130). It selects
  `3.731167 / 0.965385 / 4.696552`; the old `3.721022 / 0.952897 / 4.673919`
  block at trace line 67 is the parent event. The one-iteration run's
  `SCF_NOT_CONV` at trace line 133 is expected. The selected event and parent
  event parse from a 105-line fixture of exact output excerpts; the full
  `siesta.out` is not checked in.

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

### 3. BARE semantic proof uses the production profile

Do not replace LR-06 with a heuristic such as “two iterations means bare.”
The stale audit finding referred to the historical ordinal selector and
`MaxSCFIterations 2`. The production path is
`Siesta542PotentialShiftHamiltonianProfile.select_response`, which requires
the SIESTA 5.4.2 Hamiltonian-mixing signature, a complete pre-perturbation
population event, and exactly one populated event between `stepf` and the
first `scf: 1`. The real Yoltla 4x4 trace passes this path with the expected
occupation at trace line 101. `SCF_NOT_CONV` is expected for this one-iteration
BARE run and does not invalidate the selected event. The legacy ordinal BARE
methods in `observation_selector.py` remain disabled and are not the active
production selector. This evidence promotes LR-06 for that audited profile;
it does not retroactively certify historical runs or issue the separate
`VERIFIED_BARE` certificate.

## Ordered next actions

1. Add a birnessite supercell-size series and compare the final diagonal
   \(U(L)\), not merely individual response entries.
2. Add a production-level projector fingerprint check between LR evidence and
   any subsequent DFT+U FDF.
3. Consolidate the campaign analysis onto the tested production module; add a
   regression fixture covering the semantic event selection.

No numerical result should be tuned to a literature value while resolving
these items.
