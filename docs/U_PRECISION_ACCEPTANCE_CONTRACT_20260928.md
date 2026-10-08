# Numerical Precision Contract for U

**Predeclared tolerance for a future campaign:** ±0.02 eV per site in
`U_scalar_charge`. The campaign must explicitly freeze
`analysis_policy.u_precision_tolerance_eV: 0.02` before generating its
responses. This threshold defines a numerical precision target; it is not a
physical tolerance, DFT+U acceptance criterion, or reason to change alpha,
projectors, windows, SCF criteria, or estimator after observing U.

> **Portability status (2026-09-29):** the conditional calculations in this
> contract describe what would happen under its current acceptance formula;
> they do not authorize or establish a SIESTA modification as a product path.
> The experimental `f20.12` option requires changing/recompiling the
> executable and therefore does not meet the requirement to use supported
> standard installations. Local staging did not produce an accepted build
> receipt, and its binary was not run in a campaign. Extended precision is
> outside the portable path; this limit does not demonstrate that actual U
> error exceeds ±0.02 eV. For current status and paths, see
> [`INFORME_CONTEXTO_CUELLO_BOTELLA_U_20260929.md`](INFORME_CONTEXTO_CUELLO_BOTELLA_U_20260929.md).

## Evidence that must remain separate

- **Deterministic print rounding:** calculate it from the occupation tokens
  actually emitted and propagate their intervals through the fit and
  inversion. Review of the current `lr_analysis_v2.py` formula separates
  `B_round` from replica quantization, and also sums estimator/window
  envelopes and the conditional repeatability term. For P5,
  `B_round = 0.01183306193 eV`; the quantitative print term for replicas with
  `f12.6` is `B_replica,quant = 0.0118330619317529 eV`. Even assuming the
  empirical primary/replica spread is zero, the sum of those terms and the
  per-site envelopes is at least
  `B_total,NiLR0 = 0.027510528418052065 eV` and
  `B_total,NiLR1 = 0.02792425893343447 eV`, even after excluding any positive
  floor and setting observed spread to zero. Both exceed `0.02 eV`; under the
  current formula, stock-format quantization makes this threshold impossible
  even in the zero-spread case. The implementation applies
  `max(deterministic_floor_e, observed_spread)` before adding replica
  quantization; therefore a positive floor or spread can only increase these
  minima. Thus stock P5 is ineligible for the ±0.02 eV gate under this
  contract; this does not invalidate its numerical value as a diagnostic and
  is not a physical-acceptance judgment.
- **Extended `f20.12` precision (non-portable experiment):** the isolated
  patch `reserved_external_patches/siesta542-occupations-f20.12.patch` changes
  the format from `f12.6` to `f20.12` and reduces the decimal half-step by a
  factor of 10⁶ under the same propagation. Under the `B_total` formula fixed
  here, that change reduces the replica quantization term; it does not by
  itself guarantee that the total passes. The claim that `f20.12` is
  “necessary” is conditional only on retaining that formula and gate; it does
  not demonstrate physical necessity or that the conservative bound is the
  actual error. It also requires modifying and recompiling SIESTA, so it is
  **not an acceptable path for the portable product**. Local staging did not
  produce an accepted build receipt and the binary was not run in a campaign.
  The runner can validate a receipt linking the SHA-256 of the patch and
  executable, along with at least 12 decimals in each output, but that runner
  capability does not make the patch an approved path. Do not reinterpret
  historical `f12.6` outputs as if they had extended precision.
- **Model and window:** report sensitivity across estimators and windows
  separately. This diagnoses analysis dependence; it is not a mathematical
  error bound.
- **SCF and repeatability:** validate convergence and electronic state. An
  empirical envelope from full-mesh replicas describes reproducibility
  conditional on the observed protocol only; it is not a truth bound or
  probabilistic confidence statement. Do not transfer calibrations at α=0 to
  α≠0. The mesh calibration uses dataset schema v4 and result schema v2. Each
  receipt explicitly identifies the source campaign root; the dataset,
  analysis, `node-evidence.json`, FDF, OUT, and DM are linked by hashes. The
  reference also links its node ID/digest and attempt ID; each cell links node
  ID/digest, attempt ID, and coordinate. The validator compares
  perturbation/site, rereads the `DFTU.Proj` shift from the FDF, and
  re-extracts occupations from response and reference OUT files. Paths are
  confined to the source campaign root and execution attempt. Campaigns need
  distinct UUIDs, roots, and attempts; identical DM/OUT hashes are allowed if
  receipts prove independent attempts. Reusing an attempt or execution receipt
  does not pass. Datasets without this receipt do not yield a complete
  calibration.

## Retrospective P5 reanalysis

The CLI `tools/package_response_grid_replica.py --mode reanalyze-primary`
allows evaluation of the existing fixed-grid P5 using an explicitly specified
tolerance via `--target-tolerance-eV`, together with a validated lock and
calibration result. The primary is checked again from its hash-verified
artifacts, and an analysis/report is written to a new sidecar outside the
campaign folder. P5 is not counted as a replica and its historical artifacts
are not modified. The CLI treats the tolerance as preregistered only if both
fields (`sensitivity_tolerance_eV` and `u_precision_tolerance_eV`) in the
policy saved with the campaign already match the explicit value.

If those fields do not match, diagnostics are retained, but the gate state is
forced to `RETROSPECTIVE_THRESHOLD_NOT_PREREGISTERED` and
`precision_gate_eligible` is `false`, even if retrospective calculation falls
within the threshold. If they match, the evaluation may be eligible for the
protocol's numerical-reproducibility gate, never for physical acceptance.
Matching fields do not alter the analysis or historical artifacts; they only
determine whether the sidecar can be eligible for the gate.

This threshold is **declared by the user for retrospective evaluation**. It
was not preregistered for P5, and reanalysis cannot change that fact. Any
conditional result would describe only numerical reproducibility under the
validated empirical protocol; it would not be physical acceptance or a total
error guarantee. This description does not announce a precision pass.

Available NiO SCF evidence includes 12 SCREENED outputs with `TDM=1e-5` and
`TH=1e-4 eV`. The post hoc difference between converged and final terminal
records was observed as a diagnostic drift of 8.224 meV/site. This is observed
terminal sensitivity, not a bound or an independent repeatability calibration.
Independent full-mesh replica evidence is still missing to evaluate the
SCF/repeatability component under this contract.

### Retrospective P5–adaptive-v2 comparison

The fixed-grid P5 campaign and adaptive NiO v2 campaign have distinct UUIDs,
roots, and execution attempts, but share the same reference DM SHA. Both used
mesh `[-0.06, -0.04, -0.02, 0.02, 0.04, 0.06] eV`, PBE functional, and policy
`polynomial`, degree 3, raw matrix, and `minimum_residual_dof=1`. Identical DM
is compatible with deterministic execution; operational independence is
supported by campaign and node receipts with distinct UUID/root/attempts, not
by requiring distinct bytes for the physical state.

The receipts record these identical hashes in both campaigns:

| Shared input | SHA-256 |
|---|---|
| Reference FDF | `b4fb34e642d862be6949a5b2033a60b5c9fcae56119879583bb3eaf237620ee7` |
| Execution profile | `fbc9ff5ae47a6791d0e1ff962b6070f8690f1ffef475bafd8784a7388d755ae1` |
| `software/siesta_version.txt` | `bb5a9b03dfaec9953401a7ef8db045149461047c44f15f9c5bf7758900b5f3ee` |
| `backend_compatibility.json` | `5189620dfa1e8b6090cbdbb9c36c412835d16feb5c50bbc82b16c139d3bcff2e` |
| Ni pseudopotential | `192eb05ffb64671715e570e2ca9a99a551cf15544984592082d43004f8554e06` |
| O pseudopotential | `224ded5c59176d9bcb76d19b7a4a68a48d5dffabf8b262f64d5760250e87c35e` |

Both declare SIESTA 5.4.2, the same executable path, and the same version
text. No executable binary hash was archived; therefore, these matching
inputs and metadata do not constitute formal executable calibration and do
not change the adaptive round's diagnostic classification.

Adaptive round 00 remains a **diagnostic**, not a replica admitted by the
calibrator: its campaign is adaptive and its historical analysis uses schema
v2, whereas the replica packager requires a fixed-grid campaign and v3
analysis. It was not counted or used to construct a repeatability envelope.

Reconstructed per-site values were:

| Source and method | NiLR0 (eV) | NiLR1 (eV) |
|---|---:|---:|
| Adaptive round-00, historical v2 analysis | 6.884591569153939 | 6.885789004356711 |
| Adaptive round-00, v3 re-extraction of the same OUT files | 6.854048120360063 | 6.854167895520947 |
| P5, v3 analysis | 6.864267700049239 | 6.864387475210124 |

Rereading the same adaptive OUT files with the current event selector and
`Occupations:` parser and v3 analysis reduces the P5–adaptive difference to
10.219579689 meV/site for both sites, compared with the historical gap of
20.324/21.402 meV. Deterministic print bounds propagated by v3 are
11.833061932 meV for P5 and 11.834222998 meV for adaptive. The 10.220 meV
residual is within those bounds: this comparison alone does not identify an
independent SCF/repeatability component.

The change from adaptive v2 to v3 on the same OUT files shifts U by
30.543448794 meV (NiLR0) and 31.621108836 meV (NiLR1). This is a difference in
data source/observable interpretation (`matrix_trace` v2 versus
`siesta_occupations_total` v3), not SCF noise. Therefore, the original gap
must not be attributed to between-campaign variation without first
separating this extraction change. No row in this comparison constitutes
calibration, tolerance acceptance, or physical acceptance.

The comparison can be reproduced without writing to the campaigns: read the
existing manifests, analyses, and `node-evidence.json` receipts; verify hashes
for manifest, analysis, node evidence, FDF, OUT, and DM, as well as each
source's UUID, root, node ID, evidence digest, and attempt; check the mesh and
analysis context; re-extract occupations from the OUT files using
`Siesta542PotentialShiftHamiltonianProfile.select_response(...).response_event`
for BARE and `select_converged_screened_event(...)` for SCREENED; obtain values
and intervals with `read_printed_occupation_precision(...)`; and pass the
reconstructed observations to `analyze_verified_lr` with the declared v3
policy. Keep original files intact and write any future analysis only to a
sidecar. Paths are taken from receipts relative to each root; they do not
depend on machine-specific absolute paths.

The fixed protocol requires three more complete replicas. At 25 nodes per
mesh, the budget is **75 nodes**. A new primary campaign, with tolerances
frozen before execution, requires another 25: **100 nodes total** for a
prospective path with a preregistered primary and three replicas. P5 can be
reanalyzed as an exploratory primary and avoids repeating those 25 nodes for
that retrospective evaluation, but it does not replace the preregistered
primary for a future numerical-acceptance path. P5 is not counted as a
replica, and coverage or independence requirements are not reduced.

For future campaigns and replicas, tolerance, analysis policy, and
SCF/repeatability protocol must be frozen before calculations run. Retrospective
P5 evaluation does not replace preregistration.

To evaluate the total target, a future campaign must declare before
calculation a model/window envelope for each site and an SCF repeatability
protocol. The proposed conservative composition is

```text
B_total,s = B_round,s + E_estimator,s + E_window,s + E_SCF/repro,s
```

A numerical pass requires all four terms to be available,
`analysis_policy.sensitivity_tolerance_eV` to be preregistered, and
`B_total,s <= 0.02 eV` for **each** site. It is not sufficient for each
component individually to be below 0.02 eV. If a model/window or
SCF/repeatability envelope is empirical, the result must be labeled
**conditional on the observed protocol**, never as a mathematical or
probabilistic guarantee. If any term is only a diagnostic without a defensible
predeclared envelope, the total remains unestablished; do not add that
diagnostic as if it were a bound.

The analyzer composes these terms per site and may emit
`CONDITIONALLY_REPRODUCIBLE_WITHIN_TOTAL_TOLERANCE` only when all are available,
the sensitivity threshold is preregistered, state/SCF evidence exists, and the
total meets the criterion. The SCF/repeatability portion is propagated while
excluding primary rounding to avoid double-counting; it includes replica
quantization and primary/replica spread. Even if the conditional state passes,
`total_numerical_U_interval` remains `NOT_ESTABLISHED`: empirical envelopes are
not bounds on true error. Nor does that state imply physical acceptance.

The sidecar reanalysis may retrospectively reevaluate historical P5, but does
not modify its data, manifests, JSON, or original reports. It also does not
establish physical acceptance of any U value. The revised partial P5 sum is
reported here to document the remaining margin; it does not modify P5
artifacts.
