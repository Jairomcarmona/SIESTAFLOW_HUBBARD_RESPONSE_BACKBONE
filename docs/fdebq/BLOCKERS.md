# FD-EBQ phase 2 blockers

## TASK 10 — Coverage qualification and diagnostic mode (RESUELTO)

The specification blockers are RESUELTO by author amendments D1/D2 in
`9a60d78` (`docs/fdebq/AMENDMENTS_2.md`). The implementation provides a pure
`CoverageQualification`, a single-output reference-admission adapter, diagnostic
JSON/Markdown reports, and deterministic golden contracts in `task10_reports/`.
Coverage qualification, single-output reference admission, diagnostic reporting and D2 savings are implemented in commit `1bba765`.

CoO/NiO/FeO examples and the available frozen V6 outputs produce
`REFERENCE_NOT_ADMISSIBLE -> ALL_SUBSPACES` with `EVIDENCE_INCOMPLETE`.
Missing data are never merged from separate outputs. D2 always reports
`would_reduce_to`; an orbit of two members remains explicit with `NO_SAVING`
because representative plus mandatory shadow costs two runs. Singletons remain
explicit. Diagnostic candidates are `CANDIDATE_PENDING_SHADOW`, never `PROVEN`.

Two archived-data limitations remain explicit rather than blocking the module:

- **Cu3N:** the named output echoes `DFTU.PotentialShift true`, a Cu1 record
  with U=1.7600 eV and J=0.1000 eV, and `DM.UseSaveDM true`; the supplied
  `Cu3N_ref.fdf` contains none of these records. Its input SHA256 is
  `bdac24b25c230ca8852c2619165490a4e215c5da5cc8e7623034959d00a8c8f8`; output
  SHA256 is `aa6c0b98135c3a3ebd086db7dab2d4d59da0b208947d7d67aaf1262b9755a628`.
  The non-polarized declaration is verified, but the output is perturbed and
  inconsistent with the input. D1 therefore excludes it; the source FDF also
  has no correlated inventory. The requested archived positive translation
  golden cannot be established. A non-polarized synthetic translation toy and
  a complete zero-shift synthetic backend pair cover the positive rule.
- **MnO:** `response-matrix-foreground-recovery-v4/00_REFERENCE` is an
  unperturbed, input-bound, admissible output with 32 moments and 16 local
  spectra. Its archived inputs omit explicit `PAO.Basis` and the directory lacks
  the label-specific pseudopotentials needed by TASK 7's semantic identity
  contract. Thus coverage remains `ALL_SUBSPACES` with
  `SPECIES_IDENTITY_NOT_ESTABLISHED`. The 16->2 / 16->1 candidate cases are
  covered by the TASK 9 geometry/state toy with flags off / spin flip on.

These are **decisión del implementador (conservadora)** under the general
principle of AMENDMENTS_2.md. Archived inputs/outputs and TASK 7–9 behavior are
unchanged. Full diagnostic reports are delivered in
`C:\Users\Jairo\work\fdebq_pr_notes\r2-task10-reports`.

## TASK 12 — Resolved perturbation plan (RESUELTO)

Resolved on `fdebq/r2-task12-plan`; implementation commit: **6f970bb**.
The pure planner embeds the complete TASK 10 qualification, projector inventory,
single-output reference/parent-DM identities, declared bands, resolved estimators
and their weights. Canonical JSON freezes deterministic experiments and omitted
column maps. Explicit fixed targets bypass reduction and reproduce the existing
campaign's site/mode/alpha experiment identities for CoO, NiO, MnO v3r2 and Cu3N.

Candidate translations retain compulsory shadows and state REVIEW until proven;
missing inventory/reference/parent-DM evidence lowers the plan to NOT_ESTABLISHED
while declared fixed experiments remain inspectable. CALIBRATED_GRID emits
CALIBRATION_NOT_ENABLED with no executable runs. Spin flip/rotations expand to
explicit columns at this task boundary. These are **decisión del implementador
(conservadora)** under AMENDMENTS_2.md. The fixed production path, certification,
TASK 10 code, archived evidence and frozen V6 artifacts are unchanged.

## TASK 13 — campaign_v2 integration (RESUELTO: inventory/lock; ABIERTA: runtime pilot reuse)

Inventory/lock integration resolved on `fdebq/r2-task13-campaign-v2`;
implementation commit: **b66e370**. TASK 13 remains partial while the
runtime pilot-reuse connection below is ABIERTA.
Campaign initialization uses the TASK 7 inventory to fill optional sites and
reject explicit atom/species mismatches. DISABLED, DIAGNOSTIC (default), and
TRANSLATION_SHADOWED are recorded alongside a frozen TASK 12 plan and
`campaign.lock`. The diagnostic lock retains the complete candidate qualification
while its executable plan includes every column. Resume rechecks FDF, reference,
parent-DM, species/static bytes, backend declarations, bands, policy, targets and
grid. All executable manifest fields must match normalized frozen lr-config,
including adaptive policy/flags, magnetic tolerance, observables, material and
scientific profile. Canonical input pointers and backend-contract campaign UUID
are also checked; a missing field fails closed. Golden initialization for CoO, NiO, MnO v3r2 and Cu3N preserves the legacy
fixed experiment identities and estimator selector.

Pilot reuse has a complete versioned identity and a deterministic execution
selector bound to unchanged output and validation-receipt bytes. The selector
is intentionally not consumed by init/runner: the existing campaign contract
has no declared pilot source or producer of the required complete reuse receipt.
That runtime connection is **ABIERTA** and pilot provenance remains
**NOT_ESTABLISHED**, with **no reuse**. A filename or legacy response-ID match
cannot supply the missing evidence. The API also binds
reference-node, observable, semantic species and MPI layout as required by the
FD-EBQ review §I.9. Missing reference output remains explicitly incomplete;
the empty-output digest is an absence marker with REFERENCE_NOT_ADMISSIBLE,
never evidence. Fixed legacy execution remains available with that conservative
qualification. This is **decisión del implementador (conservadora)** under
AMENDMENTS_2.md.

TASK 14 now supplies the shadow barrier and explicit expansion. The runtime
expands pending classes while the complete FDRC I.5 state gate remains absent;
its implementation status and conservative limitation are recorded below.
`auto_split_species` remains false by default and an opt-in fails closed with
STAGED_PENDING_GENERATED_IDENTITY pending TASK 15 admission. Existing adaptive
execution retains its legacy controller; the frozen static plan records the
declared seed and adaptive policy, without claiming calibrated qualification.

The expanded historical CLI regression still reports the existing missing
`campaigns/nio_afmii_pbe_restart_v3_20260927/inputs/reference_pbe.fdf` fixture.
AGENTS.md rule 8 applies; the test and historical data were not changed.

## TASK 14 — Translation reduction with mandatory shadow

**RESUELTO: software shadow loop; commit 5038065**, branch
`fdebq/r2-task14-shadow`. The runner consumes the frozen TASK 12/13 plan only
for `TRANSLATION_SHADOWED`. TASK 2's declared estimator and additive print
BOUND determine each comparison `|direct-reconstructed| <= B_dir+B_rep`.
Shadows inherit the representative ColumnPlan. Rejected classes expand every
member; valid receipts survive, invalid runs retain their failure evidence and
receive an explicit fallback retry. TASK 11 reconstructs full raw chi0/chi;
direct shadow observations and reconstruction maps remain in the report.
Resume verifies frozen plan identity, revalidates runs and replays the barrier.
DISABLED/DIAGNOSTIC continue through their original all-column path. The legacy
tolerance API remains isolated for compatibility and does not qualify this path.

**ABIERTA / NOT_ESTABLISHED: complete production state gate.** The existing
runtime verifies SCF and magnetic moment continuity, but lacks the occupation
spectra/occupied-subspace, gap/Fermi and smoothness gates required by FDRC I.5.
Therefore no production class may become PROVEN: even a passing print shadow
expands explicitly, with its comparisons retained and
`SCIENTIFIC_STATE_NOT_ESTABLISHED` recorded. No production flag bypasses this
gate. Synthetic tests inject a complete known state oracle and exercise both
PROVEN reconstruction and REJECTED_EXPANDED behavior. This is **decisión del
implementador (conservadora)** under AMENDMENTS_2's general principle, expressly
confirmed by the orchestrator. Missing parent-DM identity, precision or magnetic
continuity also expands; legacy adaptive rounds remain NOT_ESTABLISHED for this
route. TASK 13 operational pilot reuse remains ABIERTA / NOT_ESTABLISHED.

The certification module and downstream rank/condition/direct-inversion gates
remain intact. TASK 14 introduces no MatrixBox, SCF ESTIMATE, calibrated READY
claim, numerical threshold, SIESTA campaign or real-data validation claim.

## TASK 15 — Automatic species splitting admission

**RESUELTO: D6 software staging/admission; commit pendiente**, on
`fdebq/r2-task15-species-split` based on TASK19. `lr-config.auto_split_species`
is now wired to campaign initialization and product planning, default false.
Explicit true stages shared DFTU labels with full basis/projector/PP input
preservation and per-atom `DM.InitSpin`; it records
`STAGED_PENDING_GENERATED_IDENTITY`. The staging manifest binds the versioned
flag and all staged input hashes. Product plans freeze that evidence in their
campaign identity and check staged bytes on resume. No executable campaign
manifest or READY plan is created for this pending path; override remains
NOT_ESTABLISHED.

`tools/hubbardflow_verify_split_identity.py` emits a typed, versioned JSON
receipt for actual user-generated ions. Its positive verdict requires exact
raw SHA256 equality, failing closed on missing, duplicates and mismatches.
Label-normalized hashes are diagnostic only. The synthetic positive plus
read-only real archive negatives satisfy D6; a positive real FDF is no longer
a software prerequisite. See `SPECIES_SPLIT_RUNBOOK.md` for the exact command,
removal of copied ions from the user's separate run directory, and provenance.

**ABIERTO: validación real / admisión de ejecución.** No SIESTA generation was
performed or invented. Copied reference ions and canonical label equality
cannot demonstrate actual generated exact identity; ordinary renamed ion
bytes fail the raw comparison even if the canonical diagnostics agree. A
generated receipt cannot bypass the absent full I.5 state producer or other
TASK19 production boundaries. There is no receipt-to-production override.

## TASK 16 — Calibrated amplitudes and deterministic rounds

**RESUELTO: D3/D4 software core; commit 8e44282**, on
`fdebq/r2-task16-calibrated-rounds`. `MatrixBox` already accepts one independent
`Interval` per element; the certification module is unchanged. The versioned
protocol records the common representable lattice, seeds of at least four
amplitudes, maximum rounds, TASK2 falsification multiplier, explicit user
`tau_u_ev`, SCF level and optional T0–T4 result digest (explicit null when absent).
Each column selects a TASK2 candidate admissible in every row by minimizing the
maximum full additive absolute budget. Ties use maximum amplitude, fixed family
order, full amplitude tuple, then polynomial degree. Diagnostic row choices
cannot populate production matrices. The emitted ColumnPlan uses the common
functional for every row and mandatory shadows inherit the representative plan.

Round barriers precede analysis. Failed amplitudes exclude that scale and every
larger scale. When the matrix is resolved, the next column is ranked by the
maximum over K of its first-order influence contribution, separately for BARE
and SCREENED; ties use site and mode order. The next unused permitted lattice
level is requested in ascending lattice order. Missing common candidates are
unresolved; without an estimated full matrix their influence cannot be computed,
so sorted unresolved-column order is the **decisión del implementador
(conservadora)**. The round count is derived from the cumulative completed seed
plus one new column-level per subsequent round, rather than success counters.
Exhausted lattice gives NOT_ESTABLISHED; exhausted protocol rounds gives REVIEW.

D4 acceptance requires both strict spectral beta gates and exact existing U
interval evaluation on the full elementwise print+truncation+SCF box, with each
U diagonal half width at most the declared tau. The artifact label is exactly
"calificación condicional al modelo de error". Missing/under-resolved SCF,
incomplete scientific state or absent T0–T4 digest caps REVIEW. Reciprocal-budget
falsification also caps REVIEW, retaining raw selected matrix entries.
Synthetic known-state/SCF models exercise QUALIFIED with an explicitly synthetic
validation digest; no archived or prospective SIESTA validation is claimed.

**ABIERTA / NOT_ESTABLISHED: production evidence producer and dynamic wiring.**
The runtime lacks the complete I.5 state gate (occupation spectra/subspaces,
gap/Fermi, smoothness); TASK17 must supply the SCF model/envelope and user-run
T0–T4 evidence. CALIBRATED/CALIBRATED_GRID config admission validates the explicit
protocol, then fails with SCIENTIFIC_STATE_NOT_ESTABLISHED before the legacy
U-stability controller. Pure planner callers can inject a resolved qualification
and protocol, which are frozen into the plan digest, but the executable plan
remains REVIEW pending production validation. No production flag promotes READY.
This boundary is the **decisión del implementador (conservadora)**, confirmed by
the orchestrator. The fixed/explicit production paths and frozen V6 remain intact.

TASK17 candidate providers must distinguish SCF ESTIMATE from print BOUND and
must not extrapolate an uncovered envelope: missing candidate estimates in a
partially populated SCF record are inadmissible. TASK2 currently verifies order
and tail using print-only decompositions; the TASK17 integration must retain
REVIEW unless its complete SCF-aware model is established. No hidden numerical
threshold, pseudoinverse, regularization or SIESTA campaign was introduced.

## TASK 17 — SCF tolerance ladder (D5 blockers RESUELTOS)

Branch: `fdebq/r2-task17-scf-ladder`. Commit: e2a7a88.
The author resolves the two scientific gaps in `AMENDMENTS_2.md` D5. The
implementation uses the exact eta plus/minus print intervals and contraction
formula. Under-resolution, including two zero differences, uses the declared
rho_max and caps REVIEW. Failed contraction yields
NOISE_FLOOR_NOT_ESTABLISHED and REVIEW. Theta, rho_max and every SCF tolerance
are explicit versioned/digest-bound protocol values, with no production profile.

Two endpoints supply the explicit absolute/relative envelope; no extrapolation
is allowed. The maximum endpoint rho scales both components: **decisión del
implementador (conservadora)**. Uncovered order/tail evidence is also rejected
conservatively. TASK2's API and phase-one models are unchanged; the adapter
feeds their R0/R1/R2 and neighbour gates the complete print+SCF intervals, then
separates the pure print BOUND from the SCF ESTIMATE. TASK16 consumes one
measured envelope per observed row and can qualify complete synthetic models;
missing state or T0–T4 still limits REVIEW. TASK14 accepts a documented explicit
SCF component and expands on incomplete/under-resolved supplied SCF evidence.

Tools prepare same-parent DM.Tolerance inputs, without invoking SIESTA, and
check user-produced T0–T4 metrics against a preregistered validation protocol.
Source FDFs are independently bound to their exact DFTU label, unique atom,
signed alpha and explicit BARE/SCREENED input contract before any file is
materialized. Mismatched or incomplete metadata returns NOT_ESTABLISHED.
Independent verification corrections make SCF_UNDER_RESOLVED return REVIEW
even when D4 fails and further amplitudes exist or the lattice is exhausted.
The runbook documents exact schemas, commands, high-precision reference,
holdout and digest requirements. Synthetic tests include 400 noisy known-truth
responses per absolute, relative and mixed regime; they are not prospective
SIESTA validation. T4 remains explicitly optional per the scientific review.

**ABIERTA / NOT_ESTABLISHED: production state and prospective T0–T4 evidence.**
The runtime I.5 state-evidence producer remains unavailable and is outside this
task. No real result file/hash is manufactured; CALIBRATED admission and the
existing planner REVIEW cap remain intact. Pure model qualification does not
claim production READY. Frozen V6 and direct-inversion certification are intact.

## TASK 18 — Spin flip, rotations, and V3 controls

**RESUELTO: implementation gaps under AMENDMENTS_2 D7. Commit `81b5f85` on `fdebq/r2-task18-spin-rotations`.**

Both flags now traverse config normalization, CoveragePolicy, diagnostic
coverage, the frozen plan/digest and campaign locks. They default false;
conflicting top-level/nested declarations fail closed. Existing F5/F6/F7 spin
swap and scalar permutation rules are retained. Rotation shadows use TASK14's
additive budgets and expand the whole class on egg-box discrepancy. Synthetic
negative controls cover flags on/off, ferrimagnet, orbital order, slab/defect,
gray-band geometry, differing bases, SOC/noncollinear and equal-|m|/different
environment. Plan v1 records `egg_box_quantification=NOT_QUANTIFIED`; old v1
snapshots read conservatively but their locks invalidate because provenance
changed. No thresholds or fictitious result hashes were introduced.

**ABIERTA / NOT_ESTABLISHED: prospective V2, real V3, V4 and runtime I.5.**
`VALIDATION_GATES.md` records the exact scientific gates and artifact/digest
requirements. Their production admission API is incomplete. **decisión del
implementador (conservadora)**: explicit true permits diagnostic candidates,
expands feature classes in the plan and caps the enabled policy at REVIEW;
incomplete reference evidence remains NOT_ESTABLISHED. Passing a synthetic
shadow does not establish real validation or grant PROVEN for these features.
The product defaults stay off, shadows mandatory; CALIBRATED keeps TASK16/17's
existing fail-closed admission. No SIESTA campaigns were started.

## TASK 19 — Product CLI and execution admission

**RESUELTO: product CLI core; commit `74ea767`**, branch
`fdebq/r2-task19-product-cli`. AMENDMENTS_2 D8 is implemented:
`hubbardflow plan`, `run system.fdf` and `submit system.fdf --partition ...`
exist and reach the available contract boundary. Planning delegates to TASK
7–13, writes the actual frozen TASK 12 plan when inputs permit, preserves its
exact domain state, and records a separate immutable campaign identity/lock.
Without a declared LR config it writes an inventory/optional reference-coverage
diagnostic with `NOT_ESTABLISHED / LR_CONFIG_REQUIRED`; no protocol is invented.
Run/submit consume and verify the frozen serialization, identities and current
inputs before writing admission receipts. A user override reason and explicit
SLURM partition/account enter those receipts. Legacy campaign commands retain
their existing runner. USER_GUIDE.md documents commands, schemas, states,
flags, provenance, invalidation and reports.
Product destinations reject every frozen manifest path, all AGENTS V6
directories, `FINAL_SIESTA_VALIDATION_REPORT_V6.md`, and
`production_benchmarks_v6.zip*` roots/descendants. Canonical sidecars cannot
collide with a manifest file; unavailable or malformed manifests fail closed.

**ABIERTA / NOT_ESTABLISHED: upstream production dependencies.** The complete
I.5 runtime producer (occupation spectra/subspace, gap/Fermi, smoothness) is
absent; TASK 13 has no operational pilot source/complete reuse receipt;
CALIBRATED lacks admitted runtime evidence and recorded T0–T4 validation;
TASK 15 requires generated alias species identity. Product execution therefore
stops before materialization/DAG/local-MPI/SLURM launch with explicit reasons,
even for a static READY plan or a recorded non-READY override. No override
manufactures scientific evidence. This boundary is **decisión del implementador
(conservadora)** under AMENDMENTS_2 D8/general principle.

Reports expose inventory, F1–F8 evidence and mandatory shadows, candidate and
execution coverage, per-(column, mode) alpha/estimator/SCF protocol and all plan
digests. χ0/χ, matrix gates, U, budgets and downstream qualification remain
NOT_ASSESSED while blocked; no certificate is claimed. Synthetic 2/4-site and
archived fixed-grid tests verify plan equivalence, frozen-plan consumption,
identity invalidation and simulator prohibition. Full fake-SIESTA execution
and kill/restart are deferred with the unavailable production chain. No
SIESTA campaigns were started.
