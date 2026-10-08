# Independent Adversarial Review of FDRC-v1 (HubbardFlow)

**Objeto revisado:** `HUBBARDFLOW_FDRC_V1_METHOD_PROPOSAL.md` + `HUBBARDFLOW_FDRC_CONTEXT_FOR_INDEPENDENT_REVIEW.md`
**Code inspected:** branch `codex/hubbardflow-rename` @ `3c1398b0a591ea622ef9726cf2f92e536b6206e2` (authoritative); tag `scientific-v6-final` → commit `45cb53c5a98d9d55a163c05ca3b815a8ff9cfb7f` (read-only, as historical reference).
**Data used for illustration:** `results/stage-ub-v6-observables/coo-u-b-campaigns/stageubv6-coo-a0/lr_u_analysis.v3.json` (read-only; no V6 artifact was modified). All numerical calculations in this report are reproducible with the attached `fdrc_review_numerics.py`.
**Fecha:** 2026-10-01

> **Scope warning.** The CoO calculations are *post-hoc illustrations on a development system*, not validation. They are used to falsify or support assumptions, never to set thresholds or reinterpret the V6 CoO qualification.

---

## Executive summary

**Verdict: REPLACE the FDRC-v1 decision methodology.** Preserve its *measurement design* (symmetric pairs \(\pm a\), central differences, multiple scales, state gate, provenance), but replace its *qualification logic* (ratios \(C\), \(D\), nested windows, mandatory intersections, and noise floor from \(\alpha=0\) controls) with **estimator-specific error-budget qualification** (hereafter **FD-EBQ**, *Finite-Difference Error-Budget Qualification*).

Main findings, ordered by severity:

1. **Qualification must be estimator-specific, and FDRC-v1 is not.** FDRC-v1 analyzes the central slope \(s(a)\), but the V6 production estimator is the coefficient \(c_1\) of a cubic fit. These are distinct linear functionals of the same data, with different noise gains (on the V6 grid: \(\sum|w|=21.4\ \mathrm{eV^{-1}}\) for linear, \(58.3\ \mathrm{eV^{-1}}\) for cubic, and \(50\ \mathrm{eV^{-1}}\) for central at 0.02 eV) and different truncation-error orders (\(O(a^2)\) vs. \(O(a^4)\)). Qualifying a window "for the derivative" without specifying *which estimator* has no mathematical meaning.

2. **The model \(E(a)\sim C_{\rm num}/a + C_{\rm nl}a^2\) is incomplete where it matters most.** It omits error components *independent of \(a\)* (relative SCF error, reference-Hamiltonian/parent-DM bias). No multiscale diagnostic can detect them: in the synthetic test, a relative SCF bias of \(10^{-3}\) yields **0% coverage** while every multiscale diagnostic is green. Only an **SCF-tolerance ladder applied to the difference \(n(+a)-n(-a)\)** detects it.

3. **The replica-based noise floor at \(\alpha=0\) (already implemented in `domain/occupation_noise_calibration.py`) measures reproducibility, not accuracy.** At \(\alpha=0\), a restart from the converged DM converges with almost no iterations, so this systematically underestimates the error at \(\alpha\neq0\). The code itself acknowledges this (`transfer_to_nonzero_alpha_established: False`). It must not be the basis of the noise floor.

4. **BARE and SCREENED occupy opposite error regimes** (CoO V6): BARE is dominated by smooth truncation (drift ratio 1.645 versus the theoretical 1.667 for \(c_3a^2\); \(c_3\approx9.4\ \mathrm{e/eV^3}\)); SCREENED is noise-dominated (drifts \(\le10^{-4}\), ratios \(\pm4\), erratic signs). Requiring **a common window and a common estimator** forces a suboptimal compromise. Illustration: with the V6 estimator, two AFM sites equivalent by symmetry differ by 2.1 meV; using Richardson for BARE and a central difference at 0.02 eV for SCREENED, they differ by 1.1×10⁻⁵ eV.

5. **The even component is contaminated and irrelevant to the slope.** On a symmetric grid, the least-squares estimator of odd coefficients depends *only* on the odd part of the data. The even part measures curvature \(c_2\), \(c_4\) **and** a reference offset \(\delta_0\) (CoO BARE: \(\delta_0\approx\pm2\times10^{-5}\) e, about 40 print quanta). Therefore, FDRC-v1's \(C^m_J(a)\), full-fit residual tests, and `nonlinear_residual` criterion in `alpha_selection.py` penalize terms that **do not affect** \(\chi\).

6. **The V6 "model sensitivity" metric \(|U_{\rm cubic}-U_{\rm linear}|\) measures the known \(O(a^2)\) bias of the lower-order estimator, not uncertainty in the estimator being used.** In CoO, BARE is in a verified asymptotic regime; the linear–cubic difference is essentially \(c_3\sum_k w_k\alpha_k^3\) for the linear estimator. CoO's `REVIEW` qualification is plausibly an artifact of this metric. *This does not change the frozen V6 status*; it only indicates that FD-EBQ must not inherit this metric as uncertainty.

7. **FDRC-v1 does not use a free internal falsification test: reciprocity \(\chi_{IJ}=\chi_{JI}\)** (both \(\chi^0\) and \(\chi\) are symmetric in the exact theory). Two columns obtained from distinct perturbations provide two independent estimates of the same value. Current symmetrization hides this check.

8. **A common multi-site window is not a mathematical requirement.** Columns obtained on different grids are valid as long as each element carries its own error budget. Declaring `NOT_ESTABLISHED` when the intersection is empty rejects healthy heterogeneous systems.

9. **FDRC-v1 ignores three overlapping alpha-selection mechanisms already in the branch** (`alpha_selection.py`/`adaptive_alpha.py`, `adaptive_alpha_control.py`, and noise/replica calibration), two distinct classes named `AdaptiveAlphaPolicy`, hard-coded numeric defaults (0.02, 0.05, 10, 0.05), and a production controller (`campaign_runner._execute_adaptive_gate` → `decide_round`) that **stops based on U stability across rounds** using a historical counter. This violates two requirements of the task itself (do not use U as a selection criterion; make decisions independent of history).

10. **The `ResolvedPerturbationPlan` boundary is insufficient.** Because qualification depends on the estimator, SCF level, and mode, the object crossing this boundary must be a **`ResolvedResponseProtocol`**: grid by (site, mode), estimator by (site, mode), SCF level, and a reference to the budget evidence.

**Main scientific blocker:** the SCF component of the noise floor (absolute and, especially, relative/independent of \(a\)). Print quantization is already rigorously handled in the code.

---

## A. Reconstruction of the problem

Let \(\mathbf n^m(\boldsymbol\alpha)\in\mathbb R^N\) be the occupation vector for the \(N\) correlated subspaces in state \(m\in\{\mathrm{BARE},\mathrm{SCREENED}\}\), where \(\boldsymbol\alpha\) is the vector of potential shifts on the projectors. The scientific target is the Jacobian at the origin,
\[
\chi^m_{IJ}=\left.\frac{\partial n^m_I}{\partial\alpha_J}\right|_{\boldsymbol\alpha=0},
\qquad
U=(\chi^0)^{-1}-\chi^{-1},
\]
where \(\chi^0\) is the non-self-consistent response (the first diagonalization of \(H_{\rm ref}+\alpha P_J\) from the parent DM; profile `siesta542_bare_profile.py`) and \(\chi\) is the self-consistent response.

HubbardFlow cannot access the Jacobian: it can only evaluate \(\mathbf n^m\) at points \(\alpha_J=\pm a_k\) (one column \(J\) per perturbation, all rows \(I\) at once), and each evaluation is:

- **truncated** by printed output (standard SIESTA: `f12.6`, half-step \(5\times10^{-7}\) e per token);
- **inexact** due to incomplete SCF (finite tolerances, mixing history, restart from the parent DM);
- **commonly biased** by reference quality (\(H_{\rm ref}\), parent DM);
- **potentially discontinuous** if the point falls on another branch (orbital order, magnetic order, metastability).

Any practical estimator is a linear functional of the data in one column,
\[
\hat\chi^m_{IJ}=\sum_k w_k\,n^m_I(\alpha_k),\qquad \sum_k w_k=0,\quad\sum_k w_k\alpha_k=1,
\]
and its error has three distinct components: (i) data error amplified by \(\sum_k|w_k|\); (ii) model (truncation) error controlled by moments \(\sum_k w_k\alpha_k^p\) above the canceled order; and (iii) errors that do not depend on the grid. The problem of "choosing \(\alpha\)" is really **choosing a (grid, estimator) pair for each column and mode, and demonstrating that the resulting error bound is sufficiently small for the stated precision of \(U\)**, without using the value of \(U\) as a quality signal.

This is the framing used throughout the report. It differs from FDRC-v1 in that (a) the estimator is part of the decision, (b) the tolerance comes from a declared requirement on \(U\), propagated through the actual matrices, and (c) errors independent of \(a\) are measured separately.

---

## B. Audit of FDRC-v1 assumptions

| # | Assumption (explicit or implicit) | Type | Assessment |
|---|---|---|---|
| B1 | There is an intermediate window in \(a\) where total error is small | Numerical | Correct **only** for components that depend on \(a\). Fails if an \(a\)-independent error dominates (§C.4). |
| B2 | Numerical occupation error can be summarized by one scalar \(\epsilon_n\) | Numerical/statistical | **False.** At least four components have different scaling: print quantization (exact bound), absolute SCF error (\(\propto1/a\) in the slope), relative SCF error (\(\propto|\chi|\), independent of \(a\)), and reference bias (independent of \(a\)). |
| B3 | That \(\epsilon_n\) can be estimated from deterministic replicas, \(\alpha=0\), etc. | Statistical | Deterministic replicas measure *path reproducibility*, not accuracy; a restart from converged DM at \(\alpha=0\) does not exercise SCF. See §E. |
| B4 | The central slope \(s(a)\) is the quantity to qualify | Mathematical | **False for production**: the V6 estimator is cubic \(c_1\). Qualification must apply to the functional actually used. |
| B5 | The even component detects nonlinearity/asymmetry | Mathematical | Detects even curvature and **reference offset \(\delta_0\)**, neither of which affects \(\hat\chi\) on a symmetric grid. Useful only as a state-anomaly detector. |
| B6 | Slope stability across scales (\(D\)) is evidence of linearity | Numerical | Agreement does not imply accuracy: (i) two noisy values may coincide by chance; (ii) common bias passes; (iii) it does not distinguish \(O(a)\) from \(O(a^2)\). Order verification and explicit bounds are needed. |
| B7 | Richardson is secondary | Numerical | The reverse is true. Richardson-type error estimation (with order verification) is the defensible core; the extrapolated estimator is a valid candidate when its order is verified. |
| B8 | A common BARE∩SCREENED window is required | Mathematical | Not mathematically required; runs are already separate nodes (`PerturbationSpec.mode`). See §F. |
| B9 | A common window across all sites is required | Mathematical | Not mathematically required. See §F. |
| B10 | Fixed thresholds \(S_{\min},D_{\max},C_{\max},R_{\max}\) | Statistical | Most should be **derived** quantities (gains, bounds) and a **declared** requirement (precision of \(U\)), not calibrated thresholds. Few genuine parameters remain (§K). |
| B11 | Calibration and matrix certifiability are independent | Architectural/mathematical | Partly. Do not *tune \(\alpha\)* to improve \(\kappa\), but conditioning **does determine the required accuracy** of \(\chi\). Separate "which windows are valid" (matrix-independent) from "what accuracy is needed" (matrix-dependent). |
| B12 | Electronic state can be verified with convergence and moments | Electronic state | Insufficient: orbital-order changes can preserve moments; moments legitimately change with \(\alpha\) (linear moment response). Inspect local occupation matrices and **smoothness**, not constancy. |
| B13 | Pilot runs differ from production runs | Architectural | In FD-EBQ, calibration evidence **is** production evidence; "promotion" reduces to the existing node-identity key (§I.9). |
| B14 | A V6 grid is a neutral seed | Validation | It introduces selection bias toward the four oxides. The seed should derive from a versioned grid plus a cheap BARE pilot. |
| B15 | The decision is a function of the evidence set | Architectural | Correct as a requirement, but **the existing controller violates it** (`stable_comparisons`, persisted refinement direction). |
| B16 | The \(\alpha=0\) reference is interchangeable with the parent | Electronic state | The central difference does not use \(n(0)\); the even pair does. Reference differences appear as \(\delta_0\) and must not be confused with curvature. |
| B17 | Responses are analytic at \(\alpha=0\) | Electronic state | False for metals at low electronic temperature and at phase boundaries: \(\alpha|\alpha|\) (odd) terms cause \(O(a)\) error. Order verification is required. |
| B18 | Any \(a\) can be represented | Numerical | The FDF is written with \(10^{-4}\) eV resolution (`_fdf_representable`). The amplitude grid must be exactly representable. |

---

## C. Mathematical analysis

### C.1 Even/odd decoupling (a result FDRC-v1 does not exploit)

For a symmetric grid \(\{\pm a_k\}\) (with or without \(\alpha=0\)) and polynomial basis \(\{\alpha^p\}\), the even and odd columns of the design matrix are orthogonal: \(\sum_{\pm,k}(\pm a_k)^{p}(\pm a_k)^{q}=0\) when \(p+q\) is odd. Therefore, for **any** least-squares fit (linear, cubic, or any degree) on a symmetric grid:
\[
\hat c_1=\text{function only of }\;o_k=\tfrac12[n(+a_k)-n(-a_k)].
\]
Consequences:

- \(n(0)\), \(c_2\), \(c_4\), and any reference offset **do not affect** \(\hat\chi\).
- A residual or \(R^2\) test on the full fit mixes even residuals (irrelevant) with odd residuals (relevant). In CoO BARE, the maximum residual of the V6 cubic fit (\(1.36\times10^{-5}\) e, 27 print quanta) is explained by the even term \(c_4\alpha^4\), with \(c_4\approx-7.8\), which the cubic fit does not model and which **does not contaminate** \(\hat c_1\).
- The `nonlinear_residual` criterion in `alpha_selection.py` (linear OLS residuals including even curvature) rejects windows for a reason irrelevant to \(\chi\).

### C.2 Every estimator is a functional; qualification belongs to that estimator

For the odd data, the problem reduces to the sequence of central slopes \(s_k=o_k/a_k\) with smooth model
\[
s(a)=\chi+b_1a^2+b_2a^4+\cdots\qquad(b_1=c_3,\ b_2=c_5).
\]
An estimator \(\hat\chi=\sum_k v_k s_k\) with \(\sum v_k=1\) has:
\[
\text{truncation}=\sum_{p\ge1} b_p\,\mu_p,\qquad \mu_p=\sum_k v_k a_k^{2p};
\qquad
\text{noise gain on }o:\ G=\sum_k|v_k|/a_k .
\]
- Central difference at \(a_k\): \(\mu_1=a_k^2\), \(G=1/a_k\) (for occupations: \(\sum|w|=1/a_k\cdot\) [two points with weight \(1/2a_k\)]).
- Richardson de dos escalas \((a_k,a_{k+1})\): \(\mu_1=0\), \(\mu_2=-a_k^2a_{k+1}^2\).
- V6 cubic on \(\{\pm0.02,\pm0.04,\pm0.06\}\): \(\mu_1=0\) exactly; \(\sum_k w_k\alpha_k^5=-3.99\times10^{-6}\); \(\sum|w|=58.3\ \mathrm{eV^{-1}}\).
- Linear OLS on the same grid: \(\sum w_k\alpha_k^3=2.8\times10^{-3}\); \(\sum|w|=21.4\ \mathrm{eV^{-1}}\).

**The V6 cubic is a disguised weighted Richardson estimator.** It removes \(b_1\) at the cost of about 2.7× the noise gain of the linear estimator. This is optimal when truncation dominates (CoO BARE) and suboptimal when noise dominates (CoO SCREENED). No diagnostic of \(s(a)\) that does not know \(v\) can qualify it.

### C.3 Audit of the proposed diagnostics

| FDRC-v1 diagnostic | Defect |
|---|---|
| 7.1 Signal resolution \(\|\mathbf n(+a)-\mathbf n(-a)\|\) vs. floor | Sound in spirit, but must be applied to **estimator gain** and per element, not the column norm (small cross-elements remain unresolved even when the norm is resolved). |
| 7.2 \(\pm\alpha\) consistency | Equivalent to the even component; see below. |
| 7.3 \(C^m_J(a)=\|e\|/(\|o\|+E_{\rm floor})\) | Contaminated by \(\delta_0\) (reference offset) and \(c_2a^2\), neither relevant to \(\hat\chi\). At small amplitude, \(\delta_0\) dominates: \(C\) spikes precisely where the slope is best. CoO BARE: \(\delta_0\approx2\times10^{-5}\) e vs. \(o(0.02)\approx2.7\times10^{-2}\) e. |
| 7.4 Drift \(D^m_J(a_p,a_q)\) normalized by \(S^m_J\) | Does not distinguish noise from truncation; threshold \(D_{\max}\) has no derivation; column normalization hides cross-elements; does not identify order. |
| 7.5 Nested windows \(W_1,W_2,W_3\) | Redundant and strongly correlated (they share points); "coherence" without a bound has no interpretation. |
| 7.6 State | Necessary but underspecified (§I.5). |
| 8 Richardson secondary | Should be primary as an **error estimate** with order verification. |

### C.4 The correct error model

For the printed occupation \(\tilde n_I(\alpha)\) at point \(\alpha\):
\[
\tilde n_I(\alpha)=n_I(\alpha)+\underbrace{\rho_I(\alpha)}_{\text{print quantization}}+\underbrace{r^{\rm abs}_I(\alpha)}_{\text{SCF abs.}}+\underbrace{r^{\rm rel}_I(\alpha)}_{\text{SCF rel.}}+\underbrace{\beta_I(\alpha)}_{\text{reference}},
\]
where \(|\rho_I|\le q_I\) (exact, from the tokens), \(|r^{\rm abs}|\le\varepsilon_{\rm abs}\), \(|r^{\rm rel}|\le\varepsilon_{\rm rel}|n_I(\alpha)-n_I(0)|\), and \(\beta\) is a **smooth** function of \(\alpha\) (e.g. the effect of an unconverged \(H_{\rm ref}\) across the family of BARE runs). The estimator error is then
\[
|\hat\chi-\chi|\ \le\ \underbrace{G\,q}_{\text{1/a}}+\underbrace{G\,\varepsilon_{\rm abs}}_{\text{1/a}}+\underbrace{\varepsilon_{\rm rel}\,\textstyle\sum_k|v_k|\,|s_k|}_{\text{independiente de }a}+\underbrace{|\textstyle\sum_p b_p\mu_p|}_{\text{truncamiento}}+\underbrace{|\partial_\alpha\beta|}_{\text{independiente de }a}.
\]
Only terms 1, 2, and 4 have the form \(C/a+Ca^2\). **Terms 3 and 5 are invisible to any multiscale analysis**: they shift all slopes equally. Therefore, even a perfectly implemented FDRC-v1 can return PASS with arbitrary error. This is not theoretical: the synthetic test (Appendix) has 0.000 coverage with relative bias \(10^{-3}\).

Empirical observation for CoO SCREENED: irregular drifts grow with \(a\) (\(\sim10^{-5}\) between 0.02–0.04, \(\sim10^{-4}\) between 0.04–0.06) with erratic sign, and the reciprocity residual \(|\hat\chi_{01}-\hat\chi_{10}|\) rises from \(0\) at 0.02 eV to \(4.2\times10^{-5}\) at 0.06 eV, above the pair's print bound (\(2q/a=1.7\times10^{-5}\)). This is neither smooth truncation (there is no coherent sign) nor print noise; it is consistent with SCF error that grows with perturbation size, reinforcing the need for the relative term.

---

## D. Numerical-analysis assessment

**Truncation.** For a central difference, \(T(a)=b_1a^2+O(a^4)\). For Richardson/cubic, \(T=O(a^4)\). The order is reliable only if **verified** in the data: on a geometric grid with ratio \(r\), drifts \(d_k=s_{k+1}-s_k\) satisfy \(d_{k+1}/d_k\to r^{p}\) in the asymptotic regime (\(p=2\) analytic, \(p=1\) with an odd \(\alpha|\alpha|\) term). CoO BARE: ratio 1.645 versus expected 1.667 (arithmetic grid 2:4:6) → verified asymptotic regime, \(b_1\approx9.4\ \mathrm{e/eV^3}\), matching the V6 cubic's \(c_3=9.34\).

**Data error.** The print bound propagates exactly: \(\sum_k|w_k|q_k\) (already implemented in `quantized_response.fit_centered_linear_response` and `u_certification.propagate_linear_occupation_tokens`). SCF components have no rigorous bound; they require measurement (§E).

**Optimal scale (illustrative, CoO only).** Minimize \(q/a+|b_1|a^2\): \(a^\*=(q/2|b_1|)^{1/3}\).
- BARE: \(a^\*\approx3\times10^{-3}\) eV with a central difference; alternatively, larger amplitudes with Richardson (residual \(\sim2\times10^{-4}\) between the two available extrapolations).
- SCREENED: \(|b_1|\lesssim0.05\) (unresolved) → \(a^\*\gtrsim0.017\) eV.

Thus, **in the same material, optimal BARE and SCREENED scales differ by a factor of about \(6\)** and also favor different estimators. This is the underlying numerical reason not to impose a common window/estimator (§F).

**Conditioning.** The required accuracy of \(\chi\) depends on the matrix. Linearizing \(U_{KK}\):
\[
\delta U_{KK}=-\big[(\chi^0)^{-1}\delta\chi^0(\chi^0)^{-1}\big]_{KK}+\big[\chi^{-1}\delta\chi\,\chi^{-1}\big]_{KK},
\qquad
\frac{\partial U_{KK}}{\partial\chi_{IJ}}=(\chi^{-1})_{KI}(\chi^{-1})_{JK}.
\]
For CoO, \(\partial U_{00}/\partial\chi_{00}=87.5\), \(\partial U_{00}/\partial\chi_{01}\approx25.9\), and \(\partial U_{00}/\partial\chi^0_{00}=-12.5\) (units eV²/e). An error of \(10^{-4}\) e/eV in \(\chi_{00}\) is about 9 meV in \(U\). The eigenvalues of \(\chi^0\) are \(-2.56\) and \(-0.150\): the \((1,1)\) mode amplifies errors by about 17×.

Two finer points:
- **Truncation** errors are structured and signed (the \(b_1\) matrix has the same pattern as \(\chi^0\)); in CoO, the linear estimator's bias in \(\chi^0\) (~0.026) produces only ~0.017 eV in \(U\) due to cancellation. Summing elementary bounds in absolute value is about 10× too pessimistic for truncation. **Noise**, by contrast, must propagate in absolute value.
- Linearization is valid only if \(\beta=\|\chi^{-1}\|_2\|\Delta\chi\|_2<1\), with \(\Delta\chi\) equal to the **full budget**, not print error alone (`inverse_rounding_bound` currently uses print error only).

**Scale selection.** Use a versioned geometric grid representable at \(10^{-4}\) eV (e.g. illustrative \(\{0.005,0.01,0.02,0.04,0.08\}\); no value in this report is a recommended threshold). The formulas in §I allow variable ratios, so representability does not require exactly \(r=2\).

---

## E. Noise-floor solution

### E.1 Principles

1. **Measure the error in the quantity entering the estimator**: the difference \(\Delta(a)=n(+a)-n(-a)\), not isolated \(n\). The errors at \(+a\) and \(-a\) are correlated (same parent, same mixing history) and may cancel or add; measuring \(\Delta\) captures this.
2. **Separate components with different scaling** (§C.4) instead of using one scalar \(\epsilon_n\).
3. **Distinguish bounds from estimates.** Print error has a bound; SCF error has only an a-posteriori estimate, which needs a validated safety factor.
4. **Do not treat deterministic errors as variances**: combine by adding bounds, not by RSS.

### E.2 Recommended procedure

| Component | Measurement | Status |
|---|---|---|
| Print quantization \(q\) | Exact printed tokens per point (`siesta_backend/occupation_precision.py`; `read_printed_matrix_trace_precision` or `read_printed_occupation_precision`, **do not mix observables** across points) | Rigorous bound. Already implemented. |
| Absolute and relative SCF error (SCREENED) | **SCF-tolerance ladder on \(\Delta(a)\).** For each column \(J\), at the smallest and largest amplitude to be used, repeat \(\pm a\) at levels \(L_0\) (production), \(L_1\), \(L_2\) (tighten DM.Tolerance and H tolerance by a declared factor), each level with its own parent reference at that level. \(\eta_1=\|\Delta_{L_0}-\Delta_{L_1}\|\), \(\eta_2=\|\Delta_{L_1}-\Delta_{L_2}\|\). If \(\eta_2\le\hat\rho\,\eta_1\) with \(\hat\rho<1\) (contraction), or both are at print precision, estimate the error at \(L_0\) as \(\theta\,\eta_1/(1-\hat\rho)\). Comparing small and large amplitudes separates absolute (constant \(\eta\)) from relative (\(\eta\propto a\)) error. | A-posteriori estimate; \(\theta\) requires validation (§K). No contraction → `NOISE_FLOOR_NOT_ESTABLISHED`. |
| Reference bias (BARE) | BARE \(\pm a\) from a parent DM at level \(L_1\) versus \(L_0\); also, the even-component fit \(e_k=\delta_0+c_2a_k^2+c_4a_k^4\) estimates \(\delta_0\) (parent non-self-consistency) at no additional cost | Estimate; \(\delta_0\) is an indicator, not a bound. |
| Computational path | Restart from an alternative DM within the basin (e.g. from a neighboring amplitude), and change MPI decomposition | **Validation only** or triggered by state ambiguity; measures path sensitivity/multistability. |
| \(\alpha=0\) replicas | Retain as a determinism smoke test | **Do not** use as a noise floor. |

Reusable existing infrastructure: the controller already has a *strict SCF probe* concept (`v_base_electron` vs `v_strict_electron` in `adaptive_alpha_control.py`), and `lr_dag.build_adaptive_campaign_dag` already keys nodes by (site, \(\alpha\), mode, SCF level, reference node) with a shared strict reference. FD-EBQ changes its **use**: the probe stops being a heuristic trigger and becomes a mandatory measurement with contraction verification.

Indicative additional cost per column: 4–8 SCREENED runs (two levels × two amplitudes × \(\pm\)), 2 inexpensive BARE runs, plus one reference per level shared by all columns.

### E.3 Combination

\[
\varepsilon_I(\alpha)=q_I(\alpha)+\theta\big[\hat\eta^{\rm abs}_I+\hat\eta^{\rm rel}_I\,|\tilde n_I(\alpha)-\tilde n_I(0)|\big]\ (+\,s^{\rm path}_I\ \text{if measured}).
\]

### E.4 Internal falsification of the noise floor

- **Reciprocity:** \(|\hat\chi_{IJ}-\hat\chi_{JI}|\le\kappa(B_{IJ}+B_{JI})\) for every perturbed \(I\ne J\).
- **Declared equivalence:** if and only if the symmetry module (`domain/symmetry_reduction.py`, with its shadow gate) declares sites equivalent based on evidence, \(|\hat\chi_{II}-\hat\chi_{KK}|\) must fall within the budgets. Equivalence is not inferred; only a declared equivalence is *used*.

Warning from the synthetic test: internal consistency across scales **does not reliably rescue** an underestimated noise floor (coverage 0.98 with conservative order verification, 0.58 without it). Reciprocity adds power, but **the SCF ladder is not optional**.

**Prerequisite to using reciprocity as a gate:** verify once (validation T2) that in SIESTA 5.4.2 the occupation operator and `DFTU.PotentialShift` perturbation operator are the same projector (adjoint pair). The CoO data support this (BARE: \(1.201775\) vs. \(1.201775\)), but one case is not proof.

---

## F. Multi-site and BARE/SCREENED analysis

### F.1 A common window for \(\chi^0\) and \(\chi\)? **No.**

- **Mathematics:** \(\chi^0\) and \(\chi\) are derivatives at the origin of two different functions. The definition of \(U\) does not require evaluating them at the same amplitude; the \(a\to0\) limit is independent for each.
- **Assumed error cancellation:** there is no general argument that \(O(a^2)\) errors in \(\chi^0\) and \(\chi\) cancel in \((\chi^0)^{-1}-\chi^{-1}\); the \(b_1\) coefficients belong to different functions and differ by two orders of magnitude in CoO. Do not assume cancellation; it can be *measured* during validation.
- **Numerics:** opposite regimes (§D). A common window is suboptimal for both.
- **Cost:** BARE and SCREENED are already separate nodes (`PerturbationSpec.mode`); different amplitudes add no runs.

**Rule:** qualify each pair \((J,m)\) separately. Use a common grid if both modes qualify on the same subset (default: simplicity and comparability with V6); otherwise use mode-specific grids, recorded in provenance. Never return `NOT_ESTABLISHED` solely because the intersection is empty.

### F.2 A common grid for all sites? **Not required; it is a simplicity preference.**

Columns obtained on different grids are mathematically valid if:

1. they share **the same reference** (same parent DM, same SCF level for the reference)—the matrix must be the Jacobian at one point;
2. **SCF levels are not mixed within a column estimator**; one level per campaign is recommended across columns (simplifies the budget, and the current code already prohibits mixing);
3. each element carries its own **error budget** (\(B_{IJ}\));
4. the **reciprocity gate** is applied across columns—with different grids it becomes an even stronger cross-check because truncation differs;
5. the inversion policy (raw vs. symmetrized) remains declared; with different grids, raw antisymmetry reflects different truncation and must remain within the budgets.

**Minimum provenance per \((J,m)\):** amplitudes used, estimator (identifier + weights), SCF level, budget components (\(q\), \(\eta\), truncation with verified order), and gate states.

**v1 recommendation:** use a common grid by default; if the intersection is empty and each column qualifies independently, return `QUALIFIED_HETEROGENEOUS` (not `NOT_ESTABLISHED`). The only legitimate reason not to implement this in the first iteration is the data-model change (§M), not mathematical correctness.

### F.3 Cross-responses near zero

Per-element relative criteria are the wrong metric. The correct weight of an error in \(\chi_{IJ}\) is its influence on \(U\), \(|(\chi^{-1})_{KI}(\chi^{-1})_{JK}|\), which **does not depend on the size of \(\chi_{IJ}\)**. In FD-EBQ:

- Express each element's error in absolute units (e/eV): \(B_{IJ}=N_{IJ}+T_{IJ}+\ldots\).
- Decide acceptance in U-space: \(\delta U_{KK}\le\sum_{IJ}|A_{KI}A_{JK}|B^0_{IJ}+|\mathcal B_{KI}\mathcal B_{JK}|B_{IJ}\le\tau_U\) (with \(A=(\chi^0)^{-1}\), \(\mathcal B=\chi^{-1}\)), plus \(\beta<1\).
- Report a cross-element with \(|\hat\chi_{IJ}|<B_{IJ}\) as "unresolved relative to zero" without failing it, if its influence on \(U\) fits within the budget.

---

## G. Failure modes (adversarial counterexamples)

| # | Scenario | FDRC-v1 | FD-EBQ |
|---|---|---|---|
| G1 | Common relative SCF bias across all amplitudes (loose tolerance) | **False PASS**: all scales agree | Detected by SCF ladder; equally blind without it (synthetic coverage: 0) |
| G2 | Noise floor estimated from \(\alpha=0\) replicas that converge in one iteration | **False PASS** with underestimated \(\epsilon\) | Do not use \(\alpha=0\) replicas; use a ladder at \(\alpha\neq0\) |
| G3 | Two noisy slopes coincide by chance at a large scale | PASS (small D) | Explicit bound \(B\) is large → fails \(\tau_U\) |
| G4 | Metal/phase boundary: odd \(\kappa\alpha|\alpha|\) term (\(O(a)\) error) | Small drift → PASS; incorrect order-2 Richardson | Order verification → conservative \(p=1\) bound (synthetic coverage: 1.0) |
| G5 | BARE with appreciable \(\delta_0\) (parent not fully self-consistent) | Large \(C(a)\) at small amplitude → rejects the best scale | Fit and report \(\delta_0\); it does not affect \(\hat\chi\) |
| G6 | Heterogeneous sites (e.g. octahedral/tetrahedral Fe; TM + 4f) | Empty intersection → `NOT_ESTABLISHED` | Per-column grids → `QUALIFIED_HETEROGENEOUS` |
| G7 | Strongly coupled \(\chi^0\) (small eigenvalue, as in CoO 0.150 vs. 2.56) | Column normalization dominated by diagonal → PASS although \(U\) is inaccurate | Influence-propagated requirement and \(\beta<1\) |
| G8 | Orbital-order change at \(+a\) with equal moments | Moments within 0.05 μB → passes gate | Local occupation-matrix eigenvalues/eigenvectors; jump in even component |
| G9 | Moment responds linearly to \(\alpha\) beyond an absolute tolerance (soft magnets) | Absolute `magnetic_tolerance` rejects a healthy case | Gate evaluates **smoothness**, not constancy |
| G10 | \(\pm a\) fall into different orbital-order minima (degeneracy) | Large odd component → interpreted as large response | Subspace overlap with reference; jump in even component |
| G11 | Cubic fit with 1–2 residual degrees of freedom and SCF noise | Small residual (overfit) → apparent "linearity" | Explicit cubic noise gain (58/eV) enters \(B\) |
| G12 | Tasks finish in different order; refinement uses a historical counter | Explicit risk; current controller violates this | Round barrier + decision \(f(\mathcal E,\text{protocol})\) |
| G13 | Amplitude not representable in FDF (rounding to \(10^{-4}\) eV) | Not considered | Versioned grid is representable by construction |
| G14 | Observable is mixed across points (summary `Occupations:` vs. matrix trace) | Not considered | Observable identity is part of evidence key |
| G15 | Window selected as the minimum bound among many (winner's curse) | — | Small, predeclared candidate set; require consistency with neighbors |

---

## H. Verdict on FDRC-v1

**Replace.**

Rationale: the components that determine the result—noise floor, \(C\)/\(D\) metrics, nested windows, mandatory intersections, thresholds to calibrate, secondary Richardson, treating the estimator as external—are precisely the defective components (§B, §C, §G). What survives (symmetric pairs, central differences at multiple scales, state gate, determinism as a requirement, provenance, identity-based reuse) is the measurement design and infrastructure, which FD-EBQ reuses. This is not "retain with major modifications" because the decision theory changes in kind: from "agreement among diagnostics with thresholds" to "an error bound for the specific estimator against a declared requirement."

---

## I. Recommended final methodology (FD-EBQ)

### I.1 Data and notation

For each column \(J\), mode \(m\), row \(I\), and amplitude \(a_k\) from a versioned grid \(\mathcal L=\{a_1<\dots<a_K\}\):
\[
o_k=\tfrac12[\tilde n_I(+a_k)-\tilde n_I(-a_k)],\quad s_k=o_k/a_k,\quad e_k=\tfrac12[\tilde n_I(+a_k)+\tilde n_I(-a_k)]-\tilde n_I(0).
\]
Error de datos de \(s_k\) (de §E): \(\nu_k=\big(\varepsilon(+a_k)+\varepsilon(-a_k)\big)/(2a_k)\).

### I.2 Order verification

Define drifts \(d_k=s_{k+1}-s_k\) with uncertainty \(\delta_k=\nu_k+\nu_{k+1}\). A drift is **resolved** if \(|d_k|>\delta_k\). For two consecutive resolved drifts of the same sign, the admissible ratio is the interval
\[
\Big[\tfrac{|d_{k+1}|-\delta_{k+1}}{|d_k|+\delta_k},\ \tfrac{|d_{k+1}|+\delta_{k+1}}{|d_k|-\delta_k}\Big]\ \ni\ \rho_p\equiv\frac{a_{k+2}^{p}-a_{k+1}^{p}}{a_{k+1}^{p}-a_{k}^{p}}
\]
(for a geometric grid with ratio \(r\), \(\rho_p=r^p\); for the V6 arithmetic grid, \(\rho_2=20/12\)). Order 2 is verified if the interval contains \(\rho_2\) and excludes \(\rho_1\); order 1 if it contains \(\rho_1\); **inconsistent** (neither) means those scales are excluded. If the drifts are unresolved, the order is not identifiable and the conservative bound \(p=1\) is used.

### I.3 Candidate estimators (closed, predeclared family)

1. **Central** en \(a_k\): \(\hat\chi=s_k\),
\[
B^{\rm C}_k=\nu_k+\frac{|d_k|+\delta_k}{r^{p_k}-1},\qquad p_k=\begin{cases}2&\text{order 2 verified}\\1&\text{otherwise}\end{cases}
\]
2. **Richardson** \((a_k,a_{k+1})\), only if order 2 is verified: \(\hat\chi=\frac{a_{k+1}^2s_k-a_k^2s_{k+1}}{a_{k+1}^2-a_k^2}\), with bound
\[
B^{\rm R}_k=N_k+\frac{|\hat\chi^{\rm R}_{k+1}-\hat\chi^{\rm R}_k|+N_k+N_{k+1}}{r^4-1},\quad N_k=\frac{a_{k+1}^2\nu_k+a_k^2\nu_{k+1}}{a_{k+1}^2-a_k^2}.
\]
3. **Protocol estimator** (e.g. V6 cubic) with weights \(w\): \(B=\sum|w_k|\varepsilon_k+|\sum_k w_k\alpha_k^5|\cdot\overline{|b_2|}\), with \(\overline{|b_2|}\) bounded from the second divided difference of \(s\) in \(t=a^2\). This allows the FIXED protocol to be **qualified** without changing it.

### I.4 Falsification gates (no free thresholds except \(\kappa\))

- **Neighbor consistency:** a candidate is admissible only if \(|\hat\chi_E-\hat\chi_{E'}|\le\kappa(B_E+B_{E'})\) for its family neighbors.
- **Reciprocity** (§E.4) and **declared equivalence**.
- **Even component:** \(e_k=\delta_0+c_2a_k^2+c_4a_k^4\) must fit within \(\varepsilon\); an anomalous residual at one point flags that point for the state gate (it does not directly affect \(\hat\chi\)).

### I.5 STATE_CONSISTENCY_GATE

Inspect each point \((J,m,\pm a_k)\) against the reference:

1. **SCF convergence** (flag, final dDmax/dHmax versus the level tolerance, iteration count; iteration-count outliers relative to amplitude).
2. **Local occupation matrices** \(n^{\sigma}_{mm'}\) for each subspace: ordered eigenvalues and **overlap of occupied subspaces** with the reference (detects orbital-order changes at constant moment).
3. **Moments** per site (vector if non-collinear) and total; in insulators, the total moment is quantized.
4. **Gap/HOMO-LUMO or Fermi level** (gap closure ⇒ change of character).
5. **Smoothness**, not constancy: each state observable must admit a low-order polynomial model in \(\alpha\) within its own error (print quantization + ladder); an isolated jump is a branch change.
6. **Optional (triggered validation):** hysteresis—restart \(\pm a_k\) from the neighboring-amplitude DM rather than the parent; difference > budget ⇒ multistability.
7. **Conditional:** energy–occupation consistency (Hellmann–Feynman, \(E(+a)-E(-a)\approx\int n_J\,d\alpha\)) **only** after verifying what is included in the energy printed by SIESTA with `DFTU.PotentialShift`.

Cause classification:

| Signal | Diagnosis |
|---|---|
| Smooth, order verified, gates pass | Ordinary finite-difference nonlinearity |
| Non-convergence, non-contracting ladder, anomalous iteration counts | SCF instability |
| Jump in eigenvalues/subspaces or moments, hysteresis | Metastable branch / magnetic-state change |
| Stable order \(p\approx1\) or no asymptotic regime at any resolvable scale | Physical discontinuity / non-analyticity: **no derivative exists at that scale** → STOP |

**Monotonicity rule:** if a point fails the gate at \(a_k\), exclude that amplitude and all larger amplitudes for that column and mode.

### I.6 Per-column selection

Among admissible candidates, choose \(E^\*=\arg\min_E B_E\), with deterministic tie-breaking (smallest maximum amplitude, then family in fixed order). Selection sees only bounds, never \(U\).

### I.7 Propagated requirement and matrix gate

With the estimated matrices: \(\beta^0=\|(\hat\chi^0)^{-1}\|_2\|\mathbf B^0\|_2<1\), \(\beta=\|\hat\chi^{-1}\|_2\|\mathbf B\|_2<1\); and per site,
\[
\delta U_{KK}\le\sum_{I,J}\Big(|A_{KI}A_{JK}|B^0_{IJ}+|\mathcal B_{KI}\mathcal B_{JK}|B_{IJ}\Big)+O(\beta^2)\ \le\ \tau_U .
\]
\(\tau_U\) is a **user-declared scientific requirement** (such as the ±0.02 eV in the existing contract), not a calibrated parameter. If it is not met, the only allowed remedies are those that **reduce bounds** (tighten SCF, use higher output precision during validation, add scales within the valid region); never search for another window to improve \(\kappa\).

### I.8 Separation from existing certification

The current interval certification (`domain/u_certification.py`: rational 2×2, Krawczyk, Neumann) is **not modified** and continues to certify print-quantization propagation. FD-EBQ may emit, as a **separate artifact**, a second evaluation using the same routines on a `MatrixBox` expanded to the full budget, labeled *qualification conditional on the error model*, never as certification.

### I.9 Pilot-to-production reuse

In FD-EBQ, ladder runs **are** production evidence; there is no separate pilot phase unless the user explicitly declares a subset (inferring one is prohibited). Reuse is keyed by exact identity:

- digest of the **effective** FDF (including \(\alpha\), site, mode, SCF tolerances, BARE profile);
- byte digest of the parent DM and reference node;
- SIESTA binary identity (hash + version) and backend profile identity;
- digests de pseudopotenciales y huella de proyectores;
- observable/parser identity (`siesta_occupations_total` versus matrix trace) and its version;
- nivel SCF;
- MPI decomposition: record it; treat it as non-identity until path validation demonstrates equivalence below \(q\).

A strict-level run is **not** reusable in a base-level estimator. The current key in `build_adaptive_campaign_dag` (site, \(\alpha\), mode, SCF level, reference) already covers most of this.

### I.10 Output states

`QUALIFIED`, `QUALIFIED_HETEROGENEOUS`, `REVIEW` (valid evidence, budget > \(\tau_U\), or only a partially established noise floor), `NOT_ESTABLISHED` (no admissible estimator on the grid), `NOT_DIFFERENTIABLE_AT_SCALE`, `FAIL` (invalid/incomplete evidence). Artifact name: **Response Error-Budget Qualification**—not "certificate".

---

## J. Complete algorithm

```text
INPUT  protocol P (versioned): lattice L, ratio data, estimator family F, SCF levels {L0,L1,L2},
                               tightening factors, theta, kappa, rho_max, budget limits
       requirement tau_U (user-declared), correlated-subspace inventory S, reference R(L0)
STATE  evidence set E = set of validated records keyed by
       (site, mode, alpha, scf_level, reference_node, observable_id, run_identity_digest)

S0  PREFLIGHT
    - every a in L representable at FDF precision        else FAIL(lattice_not_representable)
    - S from FDF, no inferred equivalences              else FAIL(inventory)
    - observable_id fixed for the campaign              else FAIL(observable_mixing)

S1  SEED ROUND (pure function of P)
    - BARE: all columns J, amplitudes L_seed_bare (cheap, wide)
    - SCREENED: all columns J, amplitudes L_seed_scr
    - SCF ladder nodes: for each J, SCREENED +-a at levels L1,L2 for a in {min, max of L_seed_scr};
      BARE +-a_min from reference R(L1); references R(L1), R(L2)
    -> request set Q0 = g0(P)

LOOP over rounds t = 0,1,...  (barrier: analysis starts only when all Q_t are terminal)
S2  EXECUTE Q_t, add validated records to E (failed runs recorded as failed, never retried silently)

S3  STATE GATE  (per J, m, point)  -> exclusion set X(E)
    - monotone rule: failure at a_k excludes a >= a_k for that (J, m)
    - if reference itself fails consistency                         -> FAIL(reference_state)
    - if every amplitude of some (J, m) excluded and smallest a in L reached
                                                                    -> NOT_DIFFERENTIABLE_AT_SCALE(J,m)

S4  NOISE FLOOR (per J, m)
    - q from tokens (exact)
    - ladder: eta1, eta2 on Delta(a); contraction eta2 <= rho_max * eta1 or both <= print level
        ok   -> eps_abs, eps_rel = theta * eta1/(1 - rho_hat) split by small/large amplitude
        else -> mark NOISE_FLOOR_NOT_ESTABLISHED(J, m)  (decision capped at REVIEW)
    - BARE: reference bias from R(L1) vs R(L0); delta0 from even-part fit (reported)

S5  BUDGETS (per J, m, I) on E \ X
    - s_k, nu_k, drifts, order verification (I.2)
    - candidates in F with B_E (I.3); include protocol estimator if declared

S6  FALSIFICATION
    - neighbour consistency (kappa)           -> drop inconsistent candidates
    - reciprocity for I != J                  -> violation: mark BUDGET_FALSIFIED(I,J) => REVIEW
    - declared-equivalence residuals          -> same

S7  COLUMN QUALIFICATION
    - choose E* = argmin B_E (deterministic tie-break)
    - column qualified if every I has an admissible E*

S8  MATRIX / REQUIREMENT
    - beta0, beta < 1 with full budgets       else MATRIX_NOT_RESOLVED
    - deltaU_KK <= tau_U for all K            else REQUIREMENT_NOT_MET

S9  NEXT ROUND  Q_{t+1} = g(E, P)  (pure function; no history counters)
    for each (J, m) not qualified, in fixed sorted order:
      a) noise-limited (smallest usable B dominated by nu, larger amplitudes not excluded)
           -> add next larger lattice level for (J,m) if not excluded and exists
      b) truncation-limited (B dominated by truncation, order verified)
           -> add next smaller lattice level if exists
      c) order unresolved but drifts resolved -> add one level adjacent to the resolved pair
      d) REQUIREMENT_NOT_MET with B dominated by SCF term
           -> request next stricter SCF level for the whole campaign (all columns, one level)
              only if declared in P; otherwise stop
      e) none applicable -> no addition for (J,m)
    if Q_{t+1} empty or budget exhausted -> exit loop

S10 DECISION (pure function of E and P)
    FAIL                         if any invalid/incomplete evidence or protocol violation
    NOT_DIFFERENTIABLE_AT_SCALE  if any (J,m) so marked
    NOT_ESTABLISHED              if some (J,m) has no admissible estimator
    REVIEW                       if NOISE_FLOOR_NOT_ESTABLISHED, BUDGET_FALSIFIED,
                                 MATRIX_NOT_RESOLVED or REQUIREMENT_NOT_MET
    QUALIFIED_HETEROGENEOUS      if all qualified but grids/estimators differ by (J,m)
    QUALIFIED                    otherwise
    emit ResolvedResponseProtocol + ResponseErrorBudgetQualification (+ evidence digest of E)
```

**Determinism.** (i) \(\mathcal E\) is an unordered set and all functions \(f\), \(g\) read it in key order; (ii) round barrier: completion order within a round has no effect; (iii) no historical counters—two campaigns that collect the same \(\mathcal E\) through different paths produce the same decision; (iv) a finite grid and monotone additions guarantee termination; (v) tie-breaking is deterministic.

---

## K. Threshold strategy

| Quantity | Nature | How it is established |
|---|---|---|
| \(q\) | Derived | Exact from tokens. No threshold. |
| \(G\), \(\mu_p\), weights | Derived | Algebraic from the grid and estimator. No threshold. |
| \(\eta\), \(\hat\rho\) | Measured | SCF ladder per campaign. |
| \(\tau_U\) | **Declared requirement** | Set by the user for scientific reasons before seeing results; not calibrated. |
| \(\theta\) (ladder safety factor) | **Parameter to validate** | Choose the smallest value that achieves the preregistered coverage target against the high-precision reference (T2) on development systems; freeze it; evaluate on holdout. |
| \(\rho_{\max}\) (acceptable contraction) | **Parameter to validate** | Same as \(\theta\); also verify on T0 with known contraction. |
| \(\kappa\) (consistency/reciprocity) | Parameter | Default 1 (strict intervals); increase only with evidence that bounds are conservative, never to make cases pass. |
| Order policy | No free parameter | Strict intervals (§I.2). |
| State-gate smoothness | Derived + validate | Error in state observables (print quantization + ladder); the admitted polynomial order is fixed in the protocol and validated on induced branch-change cases. |
| Grid \(\mathcal L\), run budget | Protocol constants | Representability + cost; validate insensitivity by shifting the grid (T2). |

Process: preregister (\(\theta,\rho_{\max},\kappa\), grid, estimator family, coverage target); calibrate only on T0 + development systems; freeze with a version; evaluate on holdout without retuning. Any later change ⇒ a new version and new holdout. Historical V6 thresholds remain unchanged and are not reused as FD-EBQ parameters.

---

## L. Validation program

**T0 — Synthetic with known truth** (use `synthetic_backend/`: `population_generator.py`, `noise_injection.py`). Analytic \(n(\alpha)\) functions with known \(\chi\), \(b_1\), \(b_2\); exact print noise; absolute and relative SCF noise, correlated between \(\pm a\); common bias; \(\alpha|\alpha|\) terms; one-sided branch jumps; nearly singular matrices. Metrics: coverage (truth within \(B\)), false-PASS rate, healthy-case rejection rate, determinism under arrival-order permutation.

**T1 — Internal mean-field model** (fast, self-consistent few-site Hubbard): analytic derivative through a linear solve, multisite, controllable conditioning, controllable multistability.

**T2 — High-precision SIESTA reference (core validation).** For each system: dense amplitude ladder, very strict SCF, and **the build with `f20.12` output** (`reserved_external_patches/`) used **only as a validation reference**, never as a product. Compare the FD-EBQ decision and bound using standard output against the high-precision "truth". Include reciprocity checks and energy accounting for `DFTU.PotentialShift`.

**T3 — Induced negative controls.** Deliberately too-small and too-large amplitudes, loose SCF, unconverged parent DM, forced branch: all must be flagged (false PASS = 0).

**T4 — Cross-code comparison (optional, weak).** Qualitative comparison with DFPT (`hp.x`) of \(\chi^0,\chi\) trends only; the projectors differ, so this is not a quantitative reference.

**Minimum benchmark classes** (development = NiO, FeO, CoO, MnO; all others holdout):

| Class | Possible examples | What it stresses |
|---|---|---|
| Wide-gap AFM oxide | NiO (dev) | Easy control case |
| Orbital degeneracy / branches | CoO, FeO (dev); a Jahn–Teller system (LaMnO₃ or KCuF₃) holdout | State gate |
| Small screened response | MnO (dev); d¹⁰ or d⁰ (ZnO, TiO₂) holdout | Noise limit |
| Metal | bcc Fe or metallic Ni; SrVO₃ | Non-analyticity, smearing |
| Inequivalent sites | Fe₃O₄ (oct/tet) or a spinel | Per-column grids |
| Many sites | NiO supercell with 8–16 sites; a defect | Scaling, conditioning |
| Different projector (4f) | CeO₂ | Projector generality |
| Nearly singular matrix | Deliberately constructed pair of strongly coupled sites | Matrix gate |

**Preregistered success criteria:** coverage ≥ declared target on T0 and T2; false PASS = 0 on T3; no reciprocity violations in `QUALIFIED` cases; decisions invariant under arrival-order permutation and grid translation; agreement with blind expert review on holdout cases. Never require agreement of \(U\) with experiment or literature.

---

## M. HubbardFlow integration

### M.1 Existing components (not mentioned by FDRC-v1)

| File | What it does | Disposition |
|---|---|---|
| `domain/alpha_selection.py` | Seven-point gate, three nested OLS windows, defaults `residual_relative=0.02`, `slope_relative=0.05`, `min_signal_to_noise=10`, `magnetic_tolerance=0.05` | **Deprecate.** Invented thresholds; residual includes even component; magnetism judged by constancy. Used only by historical `tools/` and tests. |
| `domain/adaptive_alpha.py` | Wrapper around the previous module; defines **another** `AdaptiveAlphaPolicy` | **Deprecate** (name collision with the one in `adaptive_alpha_control.py`). |
| `domain/adaptive_alpha_control.py` | Round controller; `STOP_STABLE` based on stable \(U\) across two comparisons; historical `stable_comparisons`; "truncation metric" in eV of \(U\) | **Replace decision logic** with \(f(\mathcal E,P)\); retain node budget, representability, and SCF-probe concept. |
| `execution/campaign_runner.py::_execute_adaptive_gate` | Calls `decide_round` with \(U\) metrics | Change the call to the new qualification function. |
| `execution/lr_dag.py::build_adaptive_campaign_dag` | Cumulative DAG, nodes per (site, \(\alpha\), mode, SCF level, reference) | **Reuse** as-is for rounds and the SCF ladder. |
| `domain/occupation_noise_calibration.py` | Replicas at \(\alpha=0\) | Keep as a determinism test, not as a noise floor. |
| `domain/response_grid_reproducibility.py`, `lr_analysis_v2._response_grid_empirical_widths` | Envelope of full-grid replicas | Keep as path evidence (validation). |
| `siesta_backend/occupation_precision.py` | Exact quantization | **Reuse** (q). |
| `domain/quantized_response.py` | Print-quantization propagation, \(\beta\) | Add a companion function for the full budget; do not modify existing functions. |
| `domain/u_certification.py` | Interval certification | **Do not touch.** |
| `domain/matrix_lr.py::ResponseObservation` | Couples BARE and SCREENED at the same \(\alpha\) | See M.3. |
| `domain/lr_analysis_v2.py::_validate_observations` | Requires "every perturbed site must use the same alpha grid" | Generalize for the new path; retain for FIXED. |
| `execution/campaign_v2.py::validate_lr_config` | Single global `alpha_grid_ev` | Add a `perturbation_strategy` block. |

### M.2 Minimal boundary

```text
FDF → preflight → subspace inventory
    → [response_strategy: FIXED_PROTOCOL_GRID | USER_EXPLICIT_GRID | CALIBRATED]
    → ResolvedResponseProtocol  (per (J,m): amplitudes, estimator id + weights, SCF level;
                                 reference identity; observable id; protocol version)
    + ResponseErrorBudgetQualification (may be NOT_ASSESSED for FIXED/USER)
    → production DAG (lr_dag) → χ0/χ via declared estimators → U → existing certification
```

**Audit of the abstraction "the rest of the system should not need to know where the plan came from":** it is sound **only** if the object carries the estimator, SCF level, and grids for each \((J,m)\). A `ResolvedPerturbationPlan` carrying amplitudes alone forces the analysis to choose the estimator independently (`LRAnalysisPolicy` in the campaign), making the qualification meaningless. Additional recommendation: also calculate the budget for FIXED and USER (in diagnostic mode), so downstream handling is uniform and V6 can be *described* in the same terms without changing it.

### M.3 New modules (pure domain, no I/O)

- `domain/response_error_budget.py`: odd/even decomposition, \(s_k\), \(\nu_k\), order verification, candidates and bounds, estimator weights (including V6 cubic), reciprocity, influence propagation.
- `domain/scf_tolerance_ladder.py`: \(\eta\), contraction, absolute/relative separation, states.
- `domain/response_state_gate.py`: state gate over already-parsed evidence (eigenvalues/subspaces of local matrices, moments, convergence, gap).
- `domain/response_qualification.py`: \(f(\mathcal E,P)\) and \(g(\mathcal E,P)\) (decision and next round), returning `ResponseErrorBudgetQualification`.
- `domain/response_protocol.py`: `ResolvedResponseProtocol` (frozen, serializable dataclass with digest).
- Data model: `ResponseColumnRecord` per \((J,m,\alpha,\text{level})\)—decouples modes. Adapter to `ResponseObservation` only for the existing FIXED path.
- Backend: extend the parser (`siesta_backend/event_parser.py`, `parser_models.py`) to expose full local occupation matrices and per-run convergence data, if not already available.

---

## N. Preservation requirements

1. Tag `scientific-v6-final` / commit `45cb53c…`, all its artifacts and hashes (`MANIFEST.sha256`, `production_benchmarks_v6.zip*`, `validation_observables_v6/`, `results/stage-ub-v6-observables/`).
2. V6 qualifications (NiO/FeO ACCEPTED, CoO REVIEW, MnO PROTOCOL_REVIEW_REQUIRED) and their thresholds; this report does not reinterpret them.
3. Definition of \(\chi^0\) (profile `siesta-5.4.2-potential-shift-hamiltonian-v1`), \(\chi\), and \(U=(\chi^0)^{-1}-\chi^{-1}\); direct inversion; no pseudoinverse or regularization.
4. `domain/u_certification.py` and its semantics (print quantization → intervals → certification).
5. Restart route `DM.UseSaveDM true` and parent DM identity; do not introduce `File.DM.Init`.
6. Bitwise-reproducible FIXED_PROTOCOL_GRID path (same cubic estimator, same grid, same analysis), including the `_validate_observations` restrictions on that path.
7. Prohibition on inferring site equivalences.

---

## O. Implementation sequence

**Safe to implement immediately**
- `ResolvedResponseProtocol` and `perturbation_strategy` block (FIXED/USER/CALIBRATED as an enum; CALIBRATED disabled) with grids and estimator per \((J,m)\).
- Decouple modes in the data model (record per column-mode), with an adapter for the FIXED path.
- `response_error_budget.py` in **diagnostic mode**: weights, gains, moments, drifts, order verification, reciprocity, \(\delta_0\). Run it on existing campaigns as a *sidecar* (written outside V6 directories).
- Complete reuse identity key (§I.9) on the current `lr_dag` key.
- Explicitly deprecate `alpha_selection.py`/`adaptive_alpha.py` and resolve the `AdaptiveAlphaPolicy` name collision.
- Remove `STOP_STABLE` based on \(U\) stability and the historical `stable_comparisons` counter from the decision path (it may remain as a reported diagnostic).
- Make the SCF ladder a **DAG node type** (on-demand execution), without yet affecting automatic decisions.

**Requires scientific validation first**
- Use of the SCF ladder as a noise floor (\(\theta\), \(\rho_{\max}\)).
- Reciprocity as a gate (verify the adjoint operator in SIESTA 5.4.2).
- State gate using eigenvalues/subspaces and a smoothness criterion.
- Automatic minimum-bound selection and the complete CALIBRATED strategy.
- Heterogeneous per-column grids in production.
- Energy–occupation consistency.
- Evaluation of the full budget with Krawczyk as a separate artifact.

**Should not be implemented**
- Noise floor based on replicas at \(\alpha=0\).
- Thresholds \(D_{\max}\), \(C_{\max}\), \(R_{\max}\), \(R^2\), or full-fit residuals as linearity criteria.
- Mandatory BARE∩SCREENED or inter-site intersection as a failure condition.
- Any stopping or selection criterion based on \(U\) (value, stability across rounds, or linear–cubic sensitivity as uncertainty).
- Window selection to improve \(\kappa\) or invertibility.
- Calibration on an automatically inferred subset of "representative" sites.
- The `f20.12` build as a product path.

---

## P. Final recommendation

1. **Is automatic finite-difference calibration defensible?** Yes, **conditionally** on: (a) estimator-specific qualification; (b) a noise floor measured with an SCF ladder on the \(\pm a\) difference and contraction verification; (c) order verification; (d) a declared requirement on \(U\) propagated through the matrices; (e) T0/T2/T3 validation with holdout. Without (b), it is not: errors independent of \(a\) are beyond the reach of any multiscale logic. DFPT is not required.

2. **Is FDRC-v1 the right design?** No. Its measurement design is good; its decision theory is not.

3. **What replaces it?** FD-EBQ (§I–§J): an error budget per \((J,m,I)\) for a closed estimator family (central, Richardson with verified order, protocol estimator), with internal falsification (neighbors, reciprocity, declared equivalences), a smoothness-based state gate, minimum-bound selection, acceptance in U-space against \(\tau_U\), grids and estimators per mode and column, and a barrier-based decision \(f(\mathcal E,P)\).

4. **What is the largest scientific blocker?** Bounding the SCF component of the error—especially the relative component independent of \(a\)—from a tolerance ladder, and demonstrating against a high-precision reference (T2) that the estimate \(\theta\eta_1/(1-\hat\rho)\) covers the true error.

5. **Design the methodology before consolidation?** **Design the contract now: yes**. The current data model (modes coupled in `ResponseObservation`, a mandatory common grid in `lr_analysis_v2`, global `alpha_grid_ev` in `campaign_v2`) embeds precisely the constraints rejected by this review, and consolidating on top of it would freeze them. **Enable the automatic selector: no**; that must wait for validation. Consolidation should also reduce the three existing mechanisms for \(\alpha\) to one.

6. **Minimum evidence before enabling the selector for users:**
   - T0: coverage ≥ the preregistered target over the full adversarial suite, with determinism under permutation.
   - T2: on all development systems **and** at least one holdout representative from each class in §L (including a metal, a heterogeneous system, and a many-site system), the high-precision truth falls within the bound in every qualified case.
   - T3: zero false PASS results.
   - No reciprocity violations in `QUALIFIED` cases; operator reciprocity verified in SIESTA 5.4.2.
   - Freeze and version parameters \(\theta,\rho_{\max},\kappa\) before evaluating the holdout.
   - Until then, CALIBRATED operates only in **advisory** mode: it produces a budget report and proposal, and the user signs off on the choice as USER_EXPLICIT_GRID.

---

## Appendix 1 — Illustrative reanalysis of CoO V6 (development, post-hoc)

**Central-slope drifts** (grid 0.02/0.04/0.06 eV; for pure \(b_1a^2\), the ratio is \(20/12=1.667\)):

| Quantity | \(s(0.02)\) | \(s(0.04)\) | \(s(0.06)\) | Ratio | Regime |
|---|---|---|---|---|---|
| BARE \(\chi^0_{00}\) | −1.351575 | −1.340237 | −1.321592 | 1.645 | Smooth truncation, order 2 verified |
| BARE \(\chi^0_{10}\) | 1.201775 | 1.190037 | 1.170808 | 1.638 | Same |
| SCREENED \(\chi_{00}\) | −0.117175 | −0.117163 | −0.117108 | 4.3 | Noise; erratic sign/ratio |
| SCREENED \(\chi_{10}\) vs \(\chi_{01}\) | 0.034650 / 0.034650 | 0.034662 / 0.034675 | 0.034617 / 0.034575 | — | Exact reciprocity at 0.02; residual \(4.2\times10^{-5}\) a 0.06 > \(2q/a\) |

**BARE even component:** \(e(a)=\delta_0+c_2a^2+c_4a^4\), with \(\delta_0=+1.9\times10^{-5}\) (site 0) and \(-2.1\times10^{-5}\) (site 1), \(c_2\approx0.35\), \(c_4\approx-7.8\).

**\(U\) per site (eV) with different estimators** (sites equivalent under AFM symmetry):

| Estimator | \(U_0\) | \(U_1\) | \(|U_0-U_1|\) |
|---|---|---|---|
| Central 0.02 (both modes) | 5.81843 | 5.81843 | <10⁻¹⁴ |
| Central 0.06 | 5.83906 | 5.84104 | 2.0×10⁻³ |
| Linear OLS 6 pt | 5.83431 | 5.83528 | 9.7×10⁻⁴ |
| **6-point cubic (V6)** | 5.81715 | 5.81502 | 2.1×10⁻³ |
| BARE Richardson / SCREENED central 0.02 | 5.81609 | 5.81610 | 1.1×10⁻⁵ |
| BARE cubic / SCREENED central 0.02 | 5.81691 | 5.81688 | 2.3×10⁻⁵ |

Interpretation: the asymmetry between equivalent sites under the V6 estimator results from amplifying SCREENED noise with an estimator designed to eliminate truncation; treating each mode according to its regime removes it. **Recalculation or reclassification of CoO is not proposed.**

## Appendix 2 — Synthetic coverage test (400 trials per case)

| Case | Accepted | Coverage | Median relative bound | Selected estimator |
|---|---|---|---|---|
| BARE-like, print quantization only | 400 | 1.000 | 1.2×10⁻⁴ | Richardson |
| SCREENED-like, SCF abs. conocido | 400 | 1.000 | 2.6×10⁻³ | Central |
| SCREENED-like, SCF rel. conocido | 400 | 1.000 | 3.9×10⁻³ | Central |
| SCREENED-like, SCF abs. **asumido 0** | 400 | 0.983 | 8.5×10⁻⁴ | Central |
| **Common relative SCF bias** | 400 | **0.000** | 7.5×10⁻⁴ | Central |
| Non-analytic odd term \(\kappa\alpha|\alpha|\) | 400 | 1.000 | 8.5×10⁻³ | Central (order 1) |

Without order verification, coverage was 0 for the non-analytic case and 0.58 for the underestimated-noise-floor case. Coverage for the common-bias case remains 0 under any multiscale logic: this is the operational demonstration of the main blocker.

## Appendix 3 — Reproduction

```bash
git checkout codex/hubbardflow-rename
python fdrc_review_numerics.py \
  results/stage-ub-v6-observables/coo-u-b-campaigns/stageubv6-coo-a0/lr_u_analysis.v3.json
```
