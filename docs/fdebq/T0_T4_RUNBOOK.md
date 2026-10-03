# TASK17: user-run SCF ladder and T0–T4 validation

Authoritative sources: `HUBBARDFLOW_FDRC_INDEPENDENT_REVIEW.md` §E, §J,
§K and `AMENDMENTS_2.md` D5. The implementation prepares inputs and checks
supplied evidence. No SIESTA run or prospective validation is included.

## Freeze the explicit protocol

Supply a `ScfLadderProtocol` JSON mapping with every field:
`version`, `enabled`, `levels` (three records with `level_id` and
`dm_tolerance` and `h_tolerance_ev`), `theta`, and `rho_max`. Use version
`scf-ladder-v2` (or `v2`). Both tolerances must be at least 1e-6 and exact
multiples of 1e-6, so the six-decimal SIESTA echo can prove them. DM tolerances
must strictly decrease;
theta must be positive and rho_max must lie in [0,1). There are no built-in
scientific values. Historical v1 records are `NOT_ESTABLISHED` with
`SCF_LADDER_PROTOCOL_V1`; `synthetic-v1` remains an algebraic test protocol and
cannot materialize or validate user-produced ladder evidence. Omit the policy or set `enabled=false` to keep the ladder
disabled. Explicit enablement and all numerical parameters enter its digest.

Preregister the candidate lattice, estimator family, kappa, tau_U, coverage
target, development systems and holdout classes together with this ladder.
Bind these to a frozen scientific protocol digest. Any later adjustment
requires a new version and new holdout. T0 synthetic fixtures use explicit
test values, which are not production profiles.

## Prepare and run the ladder

First prepare one alpha=0 reference for each of the three levels. These are
level-specific converged parents, not replicas used to infer a noise floor.
Each `LadderReferenceInput` contains `level_id`, `source_fdf`, and `assets`
(all required pseudopotential/basis files, explicitly listed). The source must
have no DFTU potential shift. The materializer writes `DFTU.PotentialShift false`
and the declared `SCF.DM.Tolerance` / `SCF.H.Tolerance` values.

```powershell
python tools/fdebq_scf_ladder_campaign.py references ladder_protocol.json ladder_references.json C:/Users/Jairo/work/scf_ladder_references
```

The tool writes three reference directories and
`scf_ladder_reference_receipt.json`. Run each reference yourself, with the
same pinned SIESTA build/backend, producing `siesta.out` and `<SystemLabel>.DM`
in its own reference directory. For example, in each directory, using WSL:

```bash
/path/to/pinned/siesta < input.fdf > siesta.out
```

Reference outputs must have normal completion and positive existing
`SCF Convergence by ... criterion` evidence, with no explicit failure.
Every reference and perturbed output must echo exactly the level's DM/H
values at six decimals and require both DM and H convergence (`T`). A missing
or mismatched echo gives `SCF_LEVEL_NOT_APPLIED`; inactive criteria give
`SCF_CRITERIA_NOT_ACTIVE`; missing reference convergence gives
`LEVEL_REFERENCE_NOT_CONVERGED`. The tool never runs SIESTA.

Then use two existing nonzero amplitudes a_s < a_l from the same column and
mode. Supply four `LadderRunInput` records **per level**, with identical signed
grids across levels (twelve per column/mode). Each record contains `site_id`,
`mode`, `alpha_ev`, `source_fdf`, `parent_dm`, `assets`, and explicit `level_id`.
`parent_dm` names the DM produced by that level's reference. The tool binds it
to the reference receipt and captures its bytes and SHA-256 at materialization
time. Parents within a level are identical; all three levels must have distinct
parent bytes, or preparation fails with `PARENT_LEVEL_NOT_DISTINCT`.

Sources already encode the exact requested site/mode/alpha. The backend binds
the literal DFTU label, unique atom and exact signed alpha, with all other shifts
zero. BARE passes the audited profile and retains `MaxSCFIterations 1`;
its level differences come from the three different parent DMs (D9), not from
converging its perturbed population. SCREENED preserves its existing input
contract and output failure/convergence checks. Inputs require
`DM.UseSaveDM true`; `File.DM.Init` is rejected.

```powershell
python tools/fdebq_scf_ladder_campaign.py runs ladder_protocol.json ladder_inputs.json C:/Users/Jairo/work/scf_ladder_user_runs --reference-receipt C:/Users/Jairo/work/scf_ladder_references/scf_ladder_reference_receipt.json
```

Outputs must be new directories outside the checkout. Includes are resolved;
all top-level `DM.Tolerance`, `SCF.DM.Tolerance`, and `SCF.H.Tolerance` directives
are removed and exactly one declared SCF DM and H tolerance is written.
Noncanonical managed spellings such as `scf_dm_tolerance` are rejected with
the required canonical spelling. Other criteria and BARE's iteration limit
are preserved. Receipts record DM/H convergence, EDM/FreeE/Harris declarations
and `MaxSCFIterations`; an undeclared family is explicitly `null`, never an
invented SIESTA default. They bind source/effective FDF, materialized FDF,
level reference FDF/output, parent DM and protocol hashes. The reference DM
is copied under the run's SystemLabel, with identical bytes. Run each prepared
input yourself in its directory, producing `siesta.out`. The overwritten run
DM must never be rehashed as its parent.

Validate these archived outputs before using their printed populations:

```powershell
python tools/fdebq_validate_t0_t4.py ladder_protocol.json C:/Users/Jairo/work/scf_ladder_user_runs/scf_ladder_receipt.json --validate-ladder --reference-receipt C:/Users/Jairo/work/scf_ladder_references/scf_ladder_reference_receipt.json
```

Exit 0 establishes the supplied ladder-input/output checks; exit 2 reports
`NOT_ESTABLISHED` and reason codes. No perturbed BARE convergence is required.
Archive the receipts, outputs and input/parent hashes. TASK13's complete
provenance checks remain required for production reuse; these inputs do not
enter production automatically. No alpha=0 replicas or inferred noise floors
are introduced.

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
