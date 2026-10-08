R0 — DOMINANT-TERM ORDER (over the sequence of central slopes s_k)
- Differences d_k = s_{k+1} − s_k, with noise δ_k = ν_k + ν_{k+1}.
- For each consecutive triple of scales: theoretical ratio ρ_p = (a_{k+2}^p − a_{k+1}^p) / (a_{k+1}^p − a_k^p) for p = 1 and p = 2. In V6: ρ_1 = 1 and ρ_2 = 5/3, exact as fractions.
- If |d_k| ≤ δ_k or |d_{k+1}| ≤ δ_{k+1} (drift unresolved relative to noise): UNRESOLVED.
- If both are resolved but have opposite signs: INCONSISTENT.
- Otherwise, the observed interval is [lo, hi], where lo = (|d_{k+1}| − δ_{k+1}) / (|d_k| + δ_k) and hi = (|d_{k+1}| + δ_{k+1}) / (|d_k| − δ_k).
  - VERIFIED_2 if ρ_2 ∈ [lo, hi] and ρ_1 ∉ [lo, hi].
  - VERIFIED_1 if ρ_1 ∈ [lo, hi] and ρ_2 ∉ [lo, hi].
  - UNRESOLVED if both are inside.
  - INCONSISTENT only if hi < ρ₁.
  - UNRESOLVED in every other case (including intervals between ρ₁ and ρ₂ or above ρ₂).
    With precise data, higher-order terms can shift the observed ratio;
    this indicates pre-asymptotic behavior, not inconsistency. Use p_used = 1, conservatively.
- If there are multiple triples, the family status is the most conservative, in this order: INCONSISTENT > UNRESOLVED > VERIFIED_1 > VERIFIED_2. This is deterministic and does not depend on U.

ORDER USED AND MOMENT VARIABLE
- p_used = 2 only if the status is VERIFIED_2. For VERIFIED_1 or UNRESOLVED, p_used = 1 (conservative). For INCONSISTENT, exclude all candidates for the element with reason code ORDER_INCONSISTENT; if none remain, the element is NOT_ESTABLISHED.
- Apply R1 and R2 using the variable u = a^{p_used} instead of t = a²:
  - Leading moment: N = Σ w_k a_k^{p_used} (exact as fractions).
  - q = N^(k+1) / N^(k).
  - Compute R2 divided differences over u.
  With p_used = 2 this matches R1/R2 exactly as currently defined.
  With p_used = 1 in V6: central (0.02 vs 0.04) gives q = 2; central (0.04 vs 0.06) gives q = 3/2.
- Mandatory check: with n = n0 + χa + k·a|a| and zero noise, the central slope at a=0.02 gives τ = 0.02|k| and the one at a=0.04 gives τ = 0.04|k|, equal to the true bias (exact coverage in the zero-noise limit).

ESTIMATORS THAT CANCEL THE TERM IN t (M_1 = 0: Richardson, cubic least squares, and any j0 ≥ 2)
- These are candidates only if the status is VERIFIED_2. In every other status, exclude them with reason code ORDER_NOT_VERIFIED_FOR_ESTIMATOR. Reason: they do not cancel a k·a term; for example, Richardson leaves a bias k·a1·a2/(a1+a2).
- The R2 TAIL_UNRESOLVED rule continues to apply only to these estimators (j0 ≥ 2), not to central or linear estimators.

CLASSIFICATION
- VERIFIED_1 and UNRESOLVED do not by themselves limit the final status: the candidate remains eligible with p_used = 1. Record reason codes ORDER_1_VERIFIED or ORDER_UNRESOLVED_CONSERVATIVE_P1 as diagnostics.
- The rest of the classification (QUALIFIED, REVIEW, etc.) remains as specified in sections J and K of the review.

ADDITIONAL TESTS
1. k·a|a| with zero noise → VERIFIED_1, never VERIFIED_2; τ equals the true bias; Richardson and cubic estimators are excluded.
2. b1·a³ with zero noise → VERIFIED_2, p_used = 2.
3. A mixture b1·a³ + k·a|a| yielding a ratio outside both ρ values → INCONSISTENT and exclusion (fail-closed).
4. Drift below the noise level → UNRESOLVED, p_used = 1, candidate remains eligible.
5. Coverage ≥ 99% in 400 seeded trials for the non-analytic case with noise, over accepted cases.

KNOWN LIMITATION

With 3 amplitudes, a mixture of a non-analytic k·a|a| term and an analytic term
of opposite sign can cancel in the observed ratio and is not covered by this
diagnostic (synthetic coverage of about 0.84; about 0.92 with 5 amplitudes).
The calibrated Phase 2 protocol must use at least 4 amplitudes.

NOTATION. Scales t_k = a_k² (eV²), k=1..K in ascending order. Central slopes s_k = [n(+a_k) − n(−a_k)] / (2 a_k), with noise radius ν_k (bound). Model: s_k = χ + Σ_{j≥1} b_j t_k^j. Every estimator in the family is E = Σ w_k s_k with Σ w_k = 1. Moments M_j = Σ w_k t_k^j, computed exactly with fractions (fractions.Fraction), without tolerances. Truncation bias = Σ_j b_j M_j. j0 = first j with M_j ≠ 0 (exact comparison). Propagated noise: ν_E = Σ |w_k| ν_k.

RULE R1 (there is a neighboring estimator in the same family). Let E_k and E_{k+1} be consecutive, with the same j0 and M^(k)_{j0}, M^(k+1)_{j0} having the same sign. Let q = M^(k+1)_{j0} / M^(k)_{j0}. If q ≤ 1, the candidate is unusable (explicit reason code). If q > 1:
  Δ = E_k − E_{k+1}
  τ_k = ( |Δ| + ν_{E_k} + ν_{E_{k+1}} ) / (q − 1)   [truncation ESTIMATE, not BOUND]
Exact examples on the V6 grid (a = 0.02, 0.04, 0.06; t = 4e-4, 16e-4, 36e-4):
  - central a=0.02 vs 0.04: q = 4 (denominator 3).
  - central a=0.04 vs 0.06: q = 9/4 (denominator 5/4).
  - Richardson(0.02,0.04) vs Richardson(0.04,0.06): M_2 = −t1·t2 and −t2·t3, q = 9 (denominator 8, NOT 15 or r⁴−1 with r=2).
On a geometric grid with ratio r, Richardson gives q = r⁴ and reproduces the old r⁴−1; add this case as a regression test.

RULE R2 (no neighbor, or the estimator uses all scales, e.g. linear OLS or the protocol's cubic least squares). Let D_j(window) be the order-j divided difference of s_k over j+1 consecutive scales, with noise radius δ_j propagated using the absolute values of its coefficients. Then:
  τ = |M_{j0}| · max_{windows} ( |D_{j0}| + δ_{j0} )   [ESTIMATE]
Taking the maximum over all available windows is a deterministic, conservative rule; it does not depend on U or any selection.
If there are no K ≥ j0+2 scales to verify the order, mark the candidate with reason code TAIL_UNRESOLVED (diagnostic). A candidate with TAIL_UNRESOLVED cannot reach QUALIFIED; at most it can reach REVIEW. This is my explicit decision, reversible by the user.
Examples on V6:
  - Linear OLS of 6 points: j0 = 1, M_1 = (0.02⁴+0.04⁴+0.06⁴)/(0.02²+0.04²+0.06²) = 0.0028 eV² exactly (verify using fractions). For n(a) = n0 + χ a + b1 a³ the bias is M_1·b1, and the bound can NEVER be zero when M_1 ≠ 0.
  - Protocol cubic (least squares with basis {a, a³}): M_1 = 0 exactly (it reproduces a³), j0 = 2. Calculate and report M_2 using fractions.

ADDITIONAL REQUIRED TESTS for TASK 2:
  1. Synthetic data n = n0 + χ a + b1 a³: linear OLS must give a bound ≥ |M_1·b1| and cover the truth; cubic and Richardson must give M_1 = 0 exactly.
  2. Richardson V6 with synthetic data and known b2: q = 9 and the estimate must lie within the tolerance of its own formula relative to the true bias.
  3. Regression on a geometric grid (q = r⁴).
  4. Exact detection of j0 using fractions, without numerical tolerances.
  5. Input-order invariance and rejection of non-finite data, as in the other tests.

SUPPLEMENTAL CLARIFICATION — TAIL_UNRESOLVED

Candidates with TAIL_UNRESOLVED remain visible in the report with their τ and reason code, but are NOT eligible for `best` while at least one eligible candidate without TAIL_UNRESOLVED exists. If NO eligible candidate without TAIL_UNRESOLVED remains, choose `best` among the TAIL_UNRESOLVED candidates using the same deterministic rule as always, and the element result is at most REVIEW, with reason code TAIL_UNRESOLVED. Adding TAIL_UNRESOLVED candidates can never worsen an element status that would otherwise be QUALIFIED: add a test for this monotonicity.
