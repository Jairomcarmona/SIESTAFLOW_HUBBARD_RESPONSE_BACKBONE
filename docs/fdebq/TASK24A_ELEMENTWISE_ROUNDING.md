# TASK 24a — verified elementwise occupation print bounds

Base: `7204521c7657a3318c1fa86ed3100bb1464369f0`.
Branch: `codex/task24a-element-rounding`.

The v3 `siesta_occupations_total` analysis now retains each printed occupation
interval through the OLS slope functional and inverse propagation. The nominal
fit, chi0, chi, U, estimator selection, inversion policy and assessment
tolerances are unchanged. The v2 path and conditional empirical replica
envelopes retain their previous propagation.

## Bound and assumptions

For the fixed supplied alpha coordinates, exact rational OLS weights propagate
the occupation intervals. Input conversion from a printed decimal to binary64
is enclosed by the round-to-nearest cell; width conversion and summation are
enclosed as well. This concerns print quantization only and does not claim a
bound on SCF, truncation or physical error.

For a total assembled from multiple tokens, the campaign adapter adds the
exact difference between the retained float total and the sum of the lexical
certification tokens to its exact print half-width, then rounds that width
upward. This preserves nominal occupations and covers the independent token
conversions plus summation. Single-token widths remain unchanged because the
OLS interval already encloses that token's conversion cell.

Let M and H be the exact fitted response-box midpoint and element half-widths.
For a floating inverse preconditioner R treated as an exact rational matrix,
define `K = abs(I - R M) + abs(R) H`. With
`q = max_i sum_j K_ij < 1`, all matrices in the box are nonsingular. This strict
inequality is a mathematical contraction condition, not a new configurable
numerical threshold.

The first inverse perturbation term is `L = K abs(R)`. The complete series is
bounded entrywise by L plus a verified tail:

`tail_ij <= row_sum(K)_i * max_k L_kj / (1 - q)`.

The independent induced-infinity-norm bound
`max_i row_sum(L)_i / (1 - q)` is a cross-check and may intersect the entrywise
enclosure. Exact rational arithmetic is used for the defect, contraction,
first term and tail. The reported first-order print term is diagnostic; the
primary bound includes the defect and infinite remainder. No pseudoinverse,
regularization or numerical-singularity fallback is introduced.

Inverse diagonal intervals are subtracted for U. The final half-width around
the existing reported U also includes the displacement of its floating fit and
inverse from the rational enclosure. JSON numeric endpoints are rounded
outward after an exact comparison, and the exact response boxes are recorded.

The contraction is serialized as `verified_contraction_exact`, an exact
rational string used by deserialization and proof validation. Its outward
binary64 diagnostic can round to 1 even when the exact q is below 1, and is
never used to replace the exact predicate. A regression uses
`q = 18014398509481983/18014398509481984` and JSON round-trip.

Scientific reinspection found and then confirmed corrections for (1) the
multi-token conversion/sum enclosure, tested with `1.00001` and `2.00003`, and
(2) serialization of the exact near-one contraction. These defects were
corrected before commit. The compatibility subtree preserves the old norm
algorithm; in multi-token cases it consumes the corrected conservative widths
and need not be numerically identical to an old archived bound.

## Report fields

The existing primary `U_scalar_half_width_by_site_eV`, intervals and maximum
now use the elementwise bound in v3. `propagation_method`,
`elementwise_inverse_proof` and `elementwise_response_boxes_exact` expose its
method and evidence. `legacy_uniform_norm_bound` contains the complete old
norm-based output alongside it. Existing chi slope-width and scalar inverse
norm fields remain compatibility diagnostics; the elementwise proof contains
the new verified inverse evidence.

NiO archived-output replay, unchanged nominal U:

| Site | Primary elementwise half-width (eV) | Legacy uniform half-width (eV) |
|---|---:|---:|
| 0 | 0.005916555162289587 | 0.0118330619317529 |
| 1 | 0.005916506799580577 | 0.0118330619317529 |

The user-reported MnO M1 value is not an optimization target and is not
asserted here; no new physical campaign is executed.

## Tests and R5 adaptation

New tests also cover the two independent token conversions/summation
counterexample and exact near-one contraction JSON round-trip. They cover
exact cubic synthetic truth, rational perturbations, input
order invariance, nonfinite rejection, singular and unsafe boxes, a 36-site
translation-reconstructed circulant response, 100 Monte Carlo occupation
rounding realizations and read-only frozen NiO matrices. Monte Carlo checks
the proof against samples; it is not used to define the bound.

The NiO integration comparison still compares the complete frozen Part A
report. Only the five named rounding scopes are projected to the explicit
legacy compatibility output: `$.printing_rounding_bounds`,
`$.primary.rounding_bound`, `$.same_grid_linear.rounding_bound`,
`$.window_results[*].rounding_bound`, and `$.printing_rounding_bound_eV`.
All chi/U, occupations, policies, states, I.5, stop/resume, manifest/snapshot
comparisons retain their invariants. Only the newly serialized
`verified_contraction_exact` numeric diagnostic is parsed as a rational and
compared with the existing replay numeric tolerances, since the preconditioner
can vary in its last bits across BLAS. No tolerance is changed; runtime
Fraction predicates, status/reason and other strings remain exact. A regression
checks tiny numeric differences, rejects a large difference and verifies other
strings still compare exactly. The scientific auditor recommended this scoped
replay representation adaptation. The complete new report is compared with
the updated replay golden. The scientific auditor conditionally approved this
R5 schema adaptation before it was implemented. The final post-fix diff and
R5/golden update were confirmed by the scientific auditor and verifier.

Only `tests/fixtures/replay_nio_p5/replay_analysis.v3.json` was updated, solely
in those rounding scopes. The exact 67-path old/new JSON difference record is
`TASK24A_GOLDEN_DIFF.json`. SHA256 old:
`b8cf931d85dc42bba00371af82b9ba973db3c5303c70be14356f455ac305bd3d`;
new: `07f93000d3fccf2fdb5a1f51c0a28a2e6f9764bdd56fbc3f145257ab648eeb81`.
Part A, I.5 golden, campaign manifest and snapshot are untouched.

Focused checks (with PYTHONPATH pointing to this worktree's src):

```text
python -m pytest -q tests/unit/test_elementwise_rounding.py tests/unit/test_lr_analysis_v2.py
28 passed, 2 warnings in 6.84s

python -m pytest -q tests/unit/test_lr_analysis_v2.py tests/unit/test_matrix_lr.py tests/unit/test_quantized_response.py tests/unit/test_u_certification.py tests/unit/test_import_architecture.py
78 passed, 2 warnings in 3.28s

python -m ruff check --isolated --target-version py312 --line-length 110 src/hubbardflow/domain/elementwise_rounding.py tests/unit/test_elementwise_rounding.py
All checks passed!

python -m ruff format --check src/hubbardflow/domain/elementwise_rounding.py tests/unit/test_elementwise_rounding.py
2 files already formatted

python -m mypy --strict --follow-imports=silent src/hubbardflow/domain/elementwise_rounding.py
Success: no issues found in 1 source file

Git Bash: bash tools/check_v6_integrity.sh
V6 GATE OK

WSL: PYTHONPATH=.../hf_task24a/src python3 -m pytest -q tests/integration/test_runner_replay_nio_p5.py
8 passed, 2 warnings in 43.36s
```

The Git Bash integrity gate is used because WSL git does not resolve the
Windows absolute gitdir stored by this worktree. The POSIX replay uses WSL and
only its fake SIESTA fixture. It completed all 27 nodes and retained the full
Part A, I.5, stop/resume, manifest and snapshot assertions.

## Residual limits

The row-sum contraction proof is sufficient but may be conservative; failure
to establish it reports an unbounded print box without changing the numerical
U calculation. These print boxes treat supplied alpha coordinates as fixed.
Print bounds do not establish total error or physical acceptance. Rational
proof arithmetic adds analysis cost for large dense matrices. Frozen V6
artifacts and `domain/u_certification.py` are unchanged.
