# Stage U-A forensic audit

Branch reviewed: `codex/sync-product-20260929`  
Campaign evidence: frozen snapshot recorded before analysis on 2026-09-30.  
Scope: internal consistency of the four completed campaigns only.

## EXECUTIVE AUDIT VERDICT

The evidence identifies one common, reproducible software defect behind the MnO and CoO certificate failures: nominal analysis fitted the six alpha points committed by the active `±0.02 eV` window, while the certificate builder fitted all ten points present in `response_tokens.v1.json`. The first divergence is therefore `GRID_MISMATCH`, subtype `ACTIVE_WINDOW_CERTIFICATE_MISMATCH`. It occurs after token extraction and before inversion. All tested response tokens and source OUT hashes match; there is no observation, provenance, fit-weight, orientation, or raw/symmetrized mismatch. The frozen source manifests bind the observations to validated node receipts with required parent-DM loads, so restart provenance is intact for the response evidence audited here.

The regression failed before the fix. The minimal correction makes certification consume the active grid committed in `MATRIX_ANALYSIS`, and rejects incomplete or extra active-grid coverage. The historical failed certificates and every frozen campaign file remain byte-for-byte unchanged. New superseding certificate artifacts were built from the existing validated OUT/token evidence into this audit directory. Both certify, contain the unchanged nominal U values, and record the former digest, replacement digest, reason, and code identity.

NiO and FeO already had valid exact-rational certificates. Their adaptive `STOP_LIMIT_SENSITIVE` states came from the adaptive controller's fallback action predicate, not from a measured sensitivity exceeding a registered threshold, an exhausted budget, or a failed certificate. Their response/certificate consistency is validated. MnO still has a larger estimator sensitivity (about 21 and 31 meV/site); its internal consistency is now validated, but its absolute precision/sensitivity acceptance policy remains unset. No physical or literature comparison was made.

Frozen evidence: [campaign identities and commitments](frozen_evidence.json). Per-observation audit: [272-row response/token/source comparison](response_observation_comparison.csv). Fit weights: [256-row nominal/exact coefficient comparison](fit_weight_comparison.csv). Matrix containment: [all 16 MnO/CoO active-grid chi cells](matrix_containment_comparison.csv). Inverse containment: [all 8 exact-rational inverse-diagonal checks](inverse_containment_comparison.csv). Corrected certificate artifacts: [MnO](MnO_u_certificate.superseding.v2.json), [CoO](CoO_u_certificate.superseding.v2.json).

## COO FIRST-DIVERGENCE TRACE

The CoO UUID is `ae62285c-268f-48f9-9c0a-8b2064a3f192`. Frozen token digest is `226a43426f86da9569b43919f0e322260fbf03dab1748a222f791ba38f58c465`; the source-manifest, token-file, analysis, commitment, receipt, adaptive-state, old-certificate, and policy hashes all matched their frozen commitments. They still match after reanalysis. The old certificate's scientific digest is `5d6cf40d341f34df71efc3ea7e2e9264e49e68badeff1b53f061a7557982db73`.

The nominal route uses the final analysis artifact `results/alpha_rounds/round-02/analysis.v3.json`, whose active vector is `[-0.02,-0.01,-0.005,0.005,0.01,0.02] eV`, degree 3, and window `0.02 eV`. The token dataset also contains the full vector `[-0.06,-0.04,-0.02,-0.01,-0.005,0.005,0.01,0.02,0.04,0.06] eV`. The previous certifier consumed that ten-point vector. The first extra point is BARE, perturbed site `CoLR0` (J=0), observed site `CoLR0` (I=0), `alpha=-0.06 eV`, node `response:34bd13d63df29a69:r0:lr_s000_m0p06_bare_scf_base_parent_reference_adaptive_34bd13d63df29a69_base`; its validated OUT/token observation is identical on both routes but it is outside the committed active grid.

The first failed containment is BARE `chi0[0,0]`: nominal `-1.3553397759103294`; erroneous ten-point box approximately `[-1.35527214193101,-1.35520498478795]`. This precedes matrix inversion. All four BARE and four SCREENED nominal cells are contained by the exact six-point active-grid boxes. The corrected exact-rational certificate is `CERTIFIED`, uses the six active alphas, and leaves nominal U unchanged at `[5.818030435715443, 5.817951497770718] eV`. Its U intervals are approximately `[5.801893354,5.834209681]` and `[5.801814326,5.834130832] eV`; both nominal values lie inside. New digest `7b949a9b800c24f761a36618de8a258e3a98e709b185387eed1025a107957653` supersedes the old digest above.

Observation-level result: all CoO rows match across printed token, float-parsed token, exact decimal token, source OUT hash, response-token value, nominal observation, and exact certificate observation. There are no differing node IDs, alpha values, modes, or site pairs. The original CoO failure is classified `GRID_MISMATCH` / `ACTIVE_WINDOW_CERTIFICATE_MISMATCH`, not stale evidence or interval widening.

## MNO FIRST-DIVERGENCE TRACE

The MnO UUID is `2eefb3e5-db29-4656-ad6a-99d2f0566038`. Its frozen token digest is `4203f1aef647eaa22dde5bf0b6a410afdd150b6197a22622e49113fa430055e6`. Manifest, token, analysis, commitment/receipt, adaptive-state, old-certificate, and policy commitments matched before analysis and still match. The old certificate digest is `852ce7298eb5980df3a627794db2b01f5eaa890ee1b1a1555cdfbdd531b956ef`.

MnO has the same active six-point vector and ten-point token vector as CoO. The first excluded edge point is BARE, perturbed `MnLR0` (J=0), observed `MnLR0` (I=0), `alpha=-0.06 eV`, node `response:b5a71575343d562d:r0:lr_s000_m0p06_bare_scf_base_parent_reference_adaptive_b5a71575343d562d_base`. Its printed token is `4.839898` and its source OUT SHA-256 is `8a5d664651d30e182b58d91006ff6ec183a7a4196162fb3f184f683b7a5749c9`. This observation agrees exactly across source, tokens, and nominal extraction. The divergence is the certificate fit's inclusion of it and the other four out-of-window points.

The first failed containment is SCREENED `chi[0,0]`: nominal `-0.05196050420168215`; ten-point box `[-0.0519353231396400,-0.0518681659965777]`. The nominal is below the lower bound by about `2.5181e-5`. The four BARE cells are inside their ten-point boxes; the first failing matrix is SCREENED, before inversion. All eight cells are inside the six-point active-grid boxes. The corrected certificate is `CERTIFIED`; it leaves nominal U unchanged at `[11.117477005325092,11.115065146109803] eV`. Corrected U intervals are approximately `[11.068637186,11.166562302]` and `[11.066234042,11.164141664] eV`, each containing its nominal value. New digest `c00b19d484f7631891d17b6be9b03a36118dbea239f77aa45f0a48f00ae43237` supersedes the old digest above.

All 80 MnO observation rows agree across their source OUT, printed and parsed token, exact-decimal token, response-token entry, nominal observation, and certificate observation. No discrepancy occurs at the token stage. CoO and MnO independently exhibit the same first-divergence point: use of the full available token grid in certification instead of the final active grid in analysis. Primary classification for both: `GRID_MISMATCH`.

### Fit, weights, matrices, and inversion checks

For both materials and every matrix element, nominal and exact fits use degree 3 with columns `[1,x,x²,x³]`, `x=alpha/max(|alpha|)`, an intercept, and slope `c1/alpha_scale`. The active alpha vector is the same in both fits; exact arithmetic substitutes rational alphas and lexical decimal-token centers. Nominal fitting uses scaled Vandermonde least squares. The exact functional uses rational normal equations. Across active-grid weights, maximum `|w_float-w_rational|` is `3.197442310920451e-14`; for the ten-point grid it is `8.881784197001252e-15`. These are ordinary floating evaluation differences, not the source of the earlier containment failure. The CSV gives each alpha's float and rational slope weight for every cell on both grids. No `Fraction(float)`, double scaling, coefficient-order, intercept, or degree mismatch was found.

For the corrected six-point route, all eight raw nominal chi values per material are inside their exact rational slope intervals; see the matrix comparison CSV for exact bounds and center slopes. Analysis passes the raw `matrix_used_chi0` and `matrix_used_chi` into nominal inversion. Certificate reconstruction indexes observed site as row I and perturbed site as column J and uses those same raw components. CoO is not exactly symmetric: raw `chi0[0,1]=1.2056655462185077` and `chi0[1,0]=1.2056957983193168`; the corresponding active exact-fit centers preserve that order. Symmetrized CoO would instead give both off-diagonal values about `1.2056806722689122`, which does not match the matrices actually used. No transpose or symmetrization mismatch exists.

After corrected chi containment, exact-rational inversion certifies regularity and U enclosure. Independent exact-rational interval division also puts all four nominal inverse diagonals per material inside determinant-derived inverse-diagonal enclosures (8/8 checks; see inverse CSV). The nominal U values are inside their respective certified U intervals, as verified by the certificate builder. The old failed certificates stopped before inversion; no inference about their old inverse intervals was needed. No interval was widened, and no float tolerance was added.

## NIO ADAPTIVE STATE TRACE

The NiO UUID is `d6d58dfd-8525-4d7f-b72c-5bbe679ec95f`. Its source, token, analysis, receipt/commitment, adaptive-state, certificate, and policy hashes matched the frozen commitments. Certificate remains `CERTIFIED`, method `exact_rational_2x2`; chi0 and chi conditions are `1.744884` and `1.022312`. Nominal U remains `[6.861874364188249,6.861874364188249] eV`. The adaptive state is `STOP_LIMIT_SENSITIVE`, which here records that the next action predicate was not satisfied; it does not state that measured sensitivity exceeded a configured tolerance.

| round | full grid (eV) | active window / points / estimator | U site 0 / site 1 (eV) | model sensitivity (eV/site) | window sensitivity (eV) | comparison / stability | budget remaining | stop reason |
|---|---|---|---|---|---|---|---:|---|
| 0 | `±0.02, ±0.04, ±0.06` | `0.06`; 6; degree-3 polynomial | `6.864267700049239 / 6.864387475210124` | `0.002470866 / 0.002737619` | `0.001373539 / 0.001520516` | no prior round; 0 stable comparisons | 16 | shrink predicate passed |
| 1 | `±0.01, ±0.02, ±0.04, ±0.06` | `0.04`; 8; degree-3 polynomial | `6.861874364188249 / 6.861874364188249` | `0.001110279 / 0.001110279` | `0.000685526 / 0.000685526` | `ΔU=0.002513111 ≤ tol=0.068618744`; 1 stable comparison | 8 | `decision_predicate_or_threshold_not_satisfied` |

The policy had `tol_abs=0.05 eV`, `tol_rel=0.01`, sensitivity-delta tolerance `0.05 eV`, truncation threshold `0.001 eV`, maximum two refinement rounds, budget 41, and no alpha ceiling. At round 1, the U comparison passed and sensitivity was non-adverse, but `next_stable=1`, below the required two consecutive comparisons. Truncation `0.000685526 ≤ 0.001` did not trigger shrink; there was no expansion ceiling. With round 1 below the max-refinement limit and eight nodes still available, neither the maximum-round nor budget branch fired. The fallback condition `refine_direction is None` produced the stop. This is protocol-action boundary B, not A, C, D, or evidence of E as a numeric decision. The policy's absolute U-precision and sensitivity-acceptance fields were unset.

The controller's stable predicate requires a previous U, equivalent fit signature, `ΔU ≤ max(tol_abs, tol_rel×max|U|)`, branch consistency, usable matrix, and sensitivity no worse than prior sensitivity plus its declared delta tolerance. Two consecutive passing comparisons are required. About 1 meV sensitivity does not bypass that count. `CERTIFIED` proves decimal-token interval propagation, matrix regularity, and a U enclosure under the stated independent BARE/SCREENED token-set assumption. It does not prove adaptive stability, repeatability, physical validity, or experimental accuracy.

## FEO ADAPTIVE STATE TRACE

FeO UUID: `d1697a97-dd54-40d3-98c7-a17ed8de82dc`. Frozen provenance hashes match. Certificate remains `CERTIFIED`, exact-rational 2×2; nominal U `[5.638281766243177,5.638315883828983] eV`; chi0 condition `23.59710`, chi condition `1.857604`.

| round | full grid (eV) | active window / points / estimator | U site 0 / site 1 (eV) | model sensitivity (eV/site) | window sensitivity (eV) | comparison / stability | budget remaining | stop reason |
|---|---|---|---|---|---|---|---:|---|
| 0 | `±0.02, ±0.04, ±0.06` | `0.06`; 6; degree-3 polynomial | `5.638281766243177 / 5.638315883828983` | `0.000640554 / 0.000682422` | `0.000435924 / 0.000454471` | no prior round; 0 stable comparisons | 16 | `decision_predicate_or_threshold_not_satisfied` |

There is no previous U, so `ΔU` is absent and `stable_now` is false. The measured truncation value is below `0.001 eV`, so there is no shrink. The round is below the two-refinement maximum, budget remains, and no alpha expansion ceiling is configured. Therefore `refine_direction` remains null and the same fallback predicate produces `STOP_LIMIT_SENSITIVE`. It means a permitted refinement/stability action could not be selected from the declared predicates; it is not a measured high-sensitivity stop and not budget exhaustion.

FeO determinant and enclosure audit:

| matrix | central determinant | certified determinant range | distance of range from zero | inverse diagonal interval widths |
|---|---:|---:|---:|---:|
| `chi0` | `0.4652444037861013` | `[0.4650511239019589, 0.46543768367047744]` | `0.4650511239019589` | `0.0029586688509`, `0.0029586405035` |
| `chi` | `0.012570686991372116` | `[0.012561772986740993, 0.012579600996000253]` | `0.012561772986740993` | `0.0086200762955` each |

The resulting U interval widths are `0.0115787451464` and `0.0115787167990 eV`. Both determinants are bounded away from zero, and both inverse and U intervals are finite and narrow relative to their central values. The `chi0` condition number is a sensitivity indicator, but it did not threaten certified regularity or make the certificate fail.

## MNO MODEL-SENSITIVITY ANALYSIS

The reported final-round model sensitivity compares the primary cubic polynomial estimator with a linear estimator on the same active `±0.02 eV` window (six points); it is not a comparison between two different alpha windows. The cubic U is `[11.117477005325092,11.115065146109803] eV`; the same-grid linear U is `[11.138653720801203,11.14580362856467] eV`. Absolute differences are `0.02117671547611` and `0.03073848245487 eV/site`.

Both fits are eligible: cubic has 6 points and 2 residual degrees of freedom; linear has 6 points and 4 residual degrees of freedom. Cubic residual RMS by matrix element is approximately `2.44e-7, 7.24e-7, 1.38e-7, 3.06e-8, 3.06e-8, 1.38e-7, 7.48e-7, 2.44e-7`; same-grid linear RMS is approximately `1e-7` to `1.1e-6`. The fitted cubic coefficients are nonzero across the matrix (about `0.0392–0.0784` for BARE and `0.1569–0.2353` for SCREENED in the fit's reported units), indicating a smooth alpha-dependent odd component/curvature in these sampled responses. Residuals are small in occupation-response units while inverse-derived U differs by 21–31 meV/site. This is empirical estimator dependence at the existing printed precision; it is not a stochastic uncertainty estimate and no new alpha points were used.

The independent window-stability estimator compares eligible linear fits on `±0.01 eV` (4 points, 2 residual DOF) and `±0.02 eV` (6 points, 4 residual DOF). The narrower-window result is `[11.125527870172917,11.125527870172917] eV`; the wider-window linear result is `[11.138653720801203,11.14580362856467] eV`, differing by `0.013125851` and `0.020275758 eV`. The two-point `±0.005 eV` window has zero residual degrees of freedom and is excluded. The sensitivity is explained as estimator dependence/curvature, but the campaign has no predeclared absolute U-precision or sensitivity-acceptance tolerance. Classification: `MODEL_SENSITIVITY_EXPLAINED`, with a separate `PROTOCOL_REVIEW_REQUIRED` before any future numerical acceptance decision.

## CODE DEFECTS FOUND

One defect was reproduced: `_derive_boxes` grouped and fitted every token alpha while `certify_campaign` had access to, but did not use, the committed `analysis_alpha_grid_eV`. The synthetic regression demonstrates a nominal slope near 5.08 outside the full-grid interval `[1117597/220000,1117603/220000]`, but inside the active-grid interval. The production evidence gives the CoO and MnO first-failing cells and bounds recorded above. Primary classification for those failed certificates is `GRID_MISMATCH`; it is not `EXPECTED_NUMERICAL_DIFFERENCE_BUT_INTERVAL_TOO_NARROW` because exact active-grid boxes contain every nominal matrix entry without widening.

No stale evidence, OUT/token mismatch, fit-weight mismatch, float/rational bug, orientation bug, raw/symmetrized mismatch, interval-propagation bug, inversion bug, or certificate-writer bug was found. NiO and FeO's `STOP_LIMIT_SENSITIVE` names are easy to overread, but their state values follow the controller's declared fallback predicate.

## FIXES APPLIED

The certification builder now selects exactly the rationalized active alpha vector committed by `MATRIX_ANALYSIS`, checks that the token dataset covers the required grid consistently, and records the certification grid and active-grid implementation identity in new certificates. Legacy `u-certification-rational-v1` certificates retain their historical full-grid reconstruction path so their source-chain verification remains possible. The repair is local; no science parameters, inputs, campaign artifacts, or nominal analysis values changed.

Old MnO and CoO certificate files were preserved. Replacement wrappers in this directory include `supersedes`, reason, old and new scientific digests, and code identity (HEAD plus SHA-256 of the working-tree certification module). New digests: MnO `c00b19d484f7631891d17b6be9b03a36118dbea239f77aa45f0a48f00ae43237`; CoO `7b949a9b800c24f761a36618de8a258e3a98e709b185387eed1025a107957653`. Both certificates report `CERTIFIED`, exact-rational 2×2 inversion, unchanged nominal U, and unchanged source-analysis/token/manifest commitments.

## REGRESSION TESTS

The minimal active-grid regression failed before the code change, showing that a six-point nominal result was outside the ten-point certificate box and inside the six-point box. After the change, the two focused regression tests passed. Certification tests: **27 passed**. Adaptive, provenance, DAG, and integration tests: **43 passed**. The legacy-certificate verifier retains the historical full-grid reconstruction route.

## FULL SUITE

`compileall -q src` completed without error. The final `PYTHONPATH=src pytest -q tests` run reported **760 passed, 20 skipped, 2 failed**. Both failures are in unrelated proposed JSON state-store lock tests (`test_failure_after_receipt_leaves_no_committed_task` and `test_stale_revision_rejected_without_overwrite`); they fail the store's `st_nlink == 1` check for temporary files created under `tests/` on the WSL `/mnt/c` mount. The prior full run had 761 passed, 20 skipped, and one failure from the same class. A single isolated stale-revision test also failed once on `/mnt/c`, while a separate isolated recovery test passed. I copied only the two tests and their minimal source dependencies to WSL `/tmp`; both then passed (**2 passed**). This identifies an environment/mount-dependent limitation in unrelated code; the certification and adaptive/provenance/DAG/integration suites all passed in the workspace.

The scoped whitespace check for `u_certification_node.py` and `test_u_certification_pipeline.py` was clean. A workspace-wide `git diff --check` exited 1 because it reports more than 8,000 whitespace warnings in unrelated pre-existing modified/untracked repository content. No warning was found in the two files changed for this fix.

## PER-MATERIAL VERDICTS

### NiO

**INTERNAL CONSISTENCY:** `VALIDATED`  
**CERTIFICATE STATUS:** `CERTIFIED` (unchanged; exact-rational 2×2)  
**ADAPTIVE STATUS:** `STOP_LIMIT_SENSITIVE` — fallback because the second consecutive stable comparison was not reached and no further declared action applied.  
**ROOT ISSUE:** no campaign-data defect; adaptive completion did not establish its two-comparison stop predicate.  
**NEXT ACTION:** `READY_FOR_REPEATABILITY_REVIEW`.

### MnO

**INTERNAL CONSISTENCY:** `VALIDATED` using the corrected superseding certificate; the preserved historical certificate remains `CERTIFICATE_NOT_ESTABLISHED`.  
**CERTIFICATE STATUS:** corrected artifact `CERTIFIED`; nominal U unchanged.  
**ADAPTIVE STATUS:** `STOP_STABLE` — two consecutive equivalent-round comparisons passed, not numerical U acceptance.  
**ROOT ISSUE:** historical certificate used ten alphas while nominal analysis used six; separately, same-grid cubic-vs-linear U sensitivity is `0.021177/0.030738 eV/site` with no absolute acceptance threshold.  
**NEXT ACTION:** `PROTOCOL_REVIEW_REQUIRED`.

### FeO

**INTERNAL CONSISTENCY:** `VALIDATED`  
**CERTIFICATE STATUS:** `CERTIFIED` (unchanged; exact-rational 2×2)  
**ADAPTIVE STATUS:** `STOP_LIMIT_SENSITIVE` — no previous round existed for a stable comparison; truncation did not trigger refinement, so the fallback predicate stopped.  
**ROOT ISSUE:** no data defect; the stop does not report high measured sensitivity, and the determinant/inverse intervals certify regularity despite the `chi0` condition number.  
**NEXT ACTION:** `READY_FOR_REPEATABILITY_REVIEW`.

### CoO

**INTERNAL CONSISTENCY:** `VALIDATED` using the corrected superseding certificate; the preserved historical certificate remains `CERTIFICATE_NOT_ESTABLISHED`.  
**CERTIFICATE STATUS:** corrected artifact `CERTIFIED`; nominal U unchanged.  
**ADAPTIVE STATUS:** `STOP_STABLE` — two consecutive equivalent-round comparisons passed; the `0.001235130 eV` last-round variation is below the configured U-comparison tolerance, not an accuracy guarantee.  
**ROOT ISSUE:** historical certificate fit the full ten-point token grid instead of the six-point active analysis grid.  
**NEXT ACTION:** `READY_FOR_REPEATABILITY_REVIEW`.

`STOP_STABLE ≠ NUMERICAL_U_ACCEPTANCE`. It compares successive eligible adaptive rounds under the configured U-delta, branch, matrix-usability, fit-signature, and non-adverse-sensitivity predicates. It does not compare against an absolute precision criterion or establish repeatability, physical validity, or external accuracy.

## READY-FOR-REPEATABILITY MATRIX

| Material | Nominal/certificate consistency | Certificate | Adaptive state | Exact meaning of adaptive state | Primary issue | Next action |
|---|---|---|---|---|---|---|
| NiO | Validated | `CERTIFIED` | `STOP_LIMIT_SENSITIVE` | one stable comparison; no further declared action | action-predicate fallback, not high sensitivity | `READY_FOR_REPEATABILITY_REVIEW` |
| MnO | Validated after superseding fix | new `CERTIFIED`; old failure preserved | `STOP_STABLE` | two consecutive equivalent-round comparisons | `GRID_MISMATCH` fixed; estimator sensitivity needs acceptance protocol | `PROTOCOL_REVIEW_REQUIRED` |
| FeO | Validated | `CERTIFIED` | `STOP_LIMIT_SENSITIVE` | no prior-round comparison; fallback after no shrink predicate | action-predicate fallback; certified matrix regularity | `READY_FOR_REPEATABILITY_REVIEW` |
| CoO | Validated after superseding fix | new `CERTIFIED`; old failure preserved | `STOP_STABLE` | two consecutive equivalent-round comparisons | `GRID_MISMATCH` fixed | `READY_FOR_REPEATABILITY_REVIEW` |

## ADDITIONAL CALCULATIONS THAT MAY BE NEEDED LATER

No additional calculation is needed to resolve this internal-consistency audit. The next work is protocol review of MnO's estimator/precision acceptance and, if later authorized under that protocol, repeatability review of the ready materials. A future calculation decision must be made only after defining what result would change the decision. No calculation, repeatability run, observable, new alpha, SIESTA, MPI, or HPC work was performed here.

## FINAL AUDIT STATUS

`AUDIT_PASS_WITH_SCIENTIFIC_REVIEW_ITEMS` — the certificate plumbing defect is fixed and independently reproduced. The code-focused suites pass; the full test collection has two unrelated mount-sensitive lock-test failures that pass from `/tmp`. Scientific review remains for MnO sensitivity and the unset absolute precision policy. No merge, production release, or scientific-input modification occurred.

NO_NEW_SIESTA_RUNS  
NO_REPEATABILITY_RUNS  
NO_OBSERVABLE_RUNS  
HPC_NOT_USED
