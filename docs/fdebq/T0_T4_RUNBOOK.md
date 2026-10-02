# TASK17: user-run SCF ladder and T0–T4 validation

Authoritative sources: `HUBBARDFLOW_FDRC_INDEPENDENT_REVIEW.md` §E, §J,
§K and `AMENDMENTS_2.md` D5. The implementation prepares inputs and checks
supplied evidence. No SIESTA run or prospective validation is included.

## Freeze the explicit protocol

Supply a `ScfLadderProtocol` JSON mapping with every field:
`version`, `enabled`, `levels` (three records with `level_id` and
`dm_tolerance`), `theta`, and `rho_max`. Tolerances must strictly decrease;
theta must be positive and rho_max must lie in [0,1). There are no built-in
scientific values. Omit the policy or set `enabled=false` to keep the ladder
disabled. Explicit enablement and all numerical parameters enter its digest.

Preregister the candidate lattice, estimator family, kappa, tau_U, coverage
target, development systems and holdout classes together with this ladder.
Bind these to a frozen scientific protocol digest. Any later adjustment
requires a new version and new holdout. T0 synthetic fixtures use explicit
test values, which are not production profiles.

## Prepare and run the ladder

Use two existing nonzero amplitudes a_s < a_l from the same column and mode.
All four inputs must have the same reference DM identity. Each JSON
`LadderRunInput` record contains `site_id`, `mode`, `alpha_ev`, `source_fdf`,
`parent_dm`, and `assets` (all pseudopotential/basis input files needed by the
run, explicitly listed). Sources are already materialized production FDFs.
The backend reuses the authoritative FDF parser to bind the literal DFTU
label, unique atom and exact signed alpha, with all other shifts zero. BARE
must pass the existing audited input profile. SCREENED must explicitly declare
FirstIteration, saved DM, convergence-required and Hamiltonian mixing, with an
iteration limit different from the BARE one-diagonalization limit. Missing,
unsupported or conflicting evidence is NOT_ESTABLISHED before materialization;
SCREENED output convergence is still validated after the user's run. The tool
does not synthesize DFTU projector records. The parent must be `<SystemLabel>.DM`. Inputs must
contain `DM.UseSaveDM true`; `File.DM.Init` is rejected.

```powershell
python tools/fdebq_scf_ladder_campaign.py ladder_protocol.json ladder_inputs.json C:/Users/Jairo/work/scf_ladder_user_runs
```

The output must be a new directory outside the checkout. For each of the
four inputs, the tool resolves includes, preserves the parent DM and assets,
and materializes the three declared `DM.Tolerance` levels. The receipt binds
source/effective FDF, materialized FDF, parent DM and protocol hashes. These
inputs do not enter production automatically. TASK13's complete provenance
checks remain required for production reuse. Execute each run yourself using
the same SIESTA build/backend and scientific profile, then archive outputs,
the receipt, normal-completion/convergence evidence and input hashes.
There are no alpha=0 replicas or inferred noise floors.

Parse printed occupations and half widths into three `LadderEvidence`
records per observed row, with identical column/mode/row keys and endpoint
grids. `estimate_ladder` computes eta1/eta2 plus/minus print radii and the
author's exact contraction formulas. Under-resolution uses the declared
rho_max and retains REVIEW; non-contraction gives
NOISE_FLOOR_NOT_ESTABLISHED and REVIEW. The two-endpoint envelope only covers
[a_s,a_l]. SCF uncertainty is ESTIMATE throughout.

## Budget integration

`scf_element_report(series, envelope, protocol_estimator=..., kappa=...)`
adapts eps_abs_e/eps_rel into the unchanged TASK2 API. The additive per-point
radius is eps_abs_e + eps_rel*g(a); the paired-difference radius is twice that
quantity, and the central slope radius is the per-point radius divided by a.
R0, R1, R2 and neighbour falsification use print+SCF intervals. Estimator
weights propagate each contribution by sum of absolute weights, never RSS.
Returned TASK2 candidates retain their pure print BOUND; SCF estimates and
truncation estimates remain separate. Any order/tail evidence outside the
envelope is rejected conservatively rather than extrapolated.

TASK16 `ColumnEvidence.scf_envelopes` supplies one envelope per observed row.
Do not also supply injected `scf_estimates`. The envelope includes its full
protocol/evidence and is recomputed before use. D3 minimax and D4 MatrixBox
budgets add the separated components. Complete resolved synthetic evidence
can reach conditional QUALIFIED; missing production state or T0–T4 evidence
still caps REVIEW. The campaign's CALIBRATED admission remains fail closed
pending its production I.5 state producer.

TASK14 `qualify_shadows(..., scf_estimates=...)` accepts explicit
`ScfResponseEstimate` records produced by `scf_response_estimate`. The recorded
print bounds remain unchanged; the two SCF radii add separately to their sum.
A partially supplied or under-resolved SCF model expands the class. Calls
without SCF evidence keep the existing print-only diagnostic behavior.

## T0–T4 program

| Case | User-produced evidence | Pass criteria |
| --- | --- | --- |
| T0 | Known chi/higher orders; quantization; absolute, relative and correlated SCF errors; common biases; alpha abs(alpha); branch jumps; nearly singular matrices | Preregistered coverage target; arrival-order and lattice-shift invariance; explicit truth and evidence hashes |
| T1 | Few-site self-consistent Hubbard model with analytic linear solution and controlled multistability | Known truth covered and invariant decisions; the validator conservatively applies the preregistered coverage target |
| T2 | Dense SIESTA amplitudes; very strict SCF; f20.12 build exclusively as high-precision validation reference; projector/perturbation adjoint check; energy accounting | Coverage target in development and blind holdout; no qualified reciprocity violation; agreement with blind expert review; frozen protocol hashes |
| T3 | Too-small/too-large amplitudes, loose SCF, unconverged parent, forced branch | Zero false PASS |
| T4 | Optional qualitative hp.x comparison of response trends | Explicit optional/required choice in validation protocol; different projectors preclude quantitative truth claims |

Holdout must include the classes in review §L (metal, heterogeneous system,
many-site system), with no retuning. Archive exact per-system coverage,
rejection and false-PASS counts; do not replace prospective evidence by the
synthetic unit-test results.

Supply `ValidationProtocol`: `version`, `coverage_target`,
`frozen_scientific_protocol_sha256`, `t4_required`. Supply a JSON array of
`ValidationMetrics` records with every field: `case`, `sample_count`,
`covered_count`, `false_pass_count`, `reciprocity_violation_count`,
`order_invariant`, `grid_shift_invariant`, `holdout`, `blind_review_agrees`,
`scientific_protocol_sha256`, `evidence_sha256`. Supply separate T2 development
and holdout records. Each evidence digest refers to an archived artifact;
the validator checks the record structure and criteria, not artifact contents
or the per-system scientific claims. Keep those artifacts reviewable.

```powershell
python tools/fdebq_validate_t0_t4.py validation_protocol.json validation_metrics.json > validation_result.json
```

Exit 0 means the supplied metrics pass; exit 2 means REVIEW. Archive the
result and its exact file SHA-256. The printed `result_sha256` hashes the
canonical inner result mapping; it differs from the file hash. TASK16's
`t0_t4_result_sha256` references the recorded result **file** digest, and the
complete ladder/protocol evidence is retained in the qualification digest.
The validator is a necessary input check, not a certification or automatic
authorization to enable CALIBRATED production. No real T0–T4 result digest is
supplied by this task.

Conservative implementation decisions: use the maximum measured endpoint rho
for both fitted components; reject uncovered order/tail evidence; apply the
declared coverage target to T1; require separate development and blind holdout
records. These only lower qualification and introduce no numerical thresholds.
