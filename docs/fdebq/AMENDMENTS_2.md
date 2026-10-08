Resume PHASE 2 in C:\Users\Jairo\work\hubbardflow. Your report was correct: the blockers were specification gaps. I (the author) resolve them as follows; save this complete text as `docs/fdebq/AMENDMENTS_2.md` in the first commit. It governs `CODEX_TASKS_PHASE2.md`.

GENERAL PRINCIPLE: for any gap not covered by this text, choose the most conservative option (more perturbations or a lower state: REVIEW / NOT_ESTABLISHED), never an option that raises a state, and record it in the task note as "conservative implementer decision". Stop only if the sole possible outcome would raise a state or affect existing certification.

BASE: continue from the tip of `fdebq/task19-product-cli`. Do not rewrite history: create new stacked branches `fdebq/r2-taskNN-<slug>` (NN = 10, 12, 13, 14, 16, 17, 18, 19, and 15 last), and after each one update `docs/fdebq/BLOCKERS.md` to mark the blocker RESOLVED with the commit. Order: 10, 12, 13, 14, 16, 17, 18, 19, 15. The usual rules apply: V6 GATE OK before each commit, ruff, format, mypy, pytest, a per-task note in `C:\Users\Jairo\work\fdebq_pr_notes`, push without a PR, independent verifier, flags off by default, do not run SIESTA, do not weaken tests or invent thresholds.

D1. TASK 10, reference evidence. A reference is admissible ONLY if ONE SIESTA output, together with its input FDF (both bound by sha256), contains: normal termination; final per-atom Mulliken moments if the calculation is spin-polarized (for verified `Spin non-polarized`, moments are not required); and local occupation matrices. Never combine data from different outputs. If anything is missing: `REFERENCE_NOT_ADMISSIBLE`, strategy `ALL_SUBSPACES`, reason `EVIDENCE_INCOMPLETE`. An output with a perturbed site (α≠0) is not a reference.
 TASK 10 goldens: (a) CoO, NiO, and FeO from `examples/tmo_campaigns` and the outputs in `validation_observables_v6`: NEGATIVE golden = `REFERENCE_NOT_ADMISSIBLE` → `ALL_SUBSPACES` with the exact reason (this is a valid and expected result). (b) Cu3N (`examples/tmo_campaigns/Cu3N_ref.out`, non-polarized): POSITIVE golden for translations. (c) MnO v3r2: search `campaigns/mno_afmii_strict_lr_v3r2` for an unperturbed reference output (α=0, parent DM) containing both local occupations and Mulliken data; if it exists, positive golden (16→2 with flags off, 16→1 with ε=−1 as candidate only); if not, do NOT use per-alpha outputs as references: document the limitation and cover MnO with the TASK 9 synthetic toy. Remove the "CoO 2→1" and "MnO 16→1" goldens as automatic results.

D2. TASK 10, savings rule. Always report `would_reduce_to` (the count of candidate representatives). A class is effectively reduced only if, with the mandatory shadow, (representatives + shadows) < class members; if this does not save runs, perturb the entire class with reason `NO_SAVING`. Do not reduce size-1 orbits. Example: CoO with ε=−1 enabled is a 2→1 candidate but is fully perturbed because of `NO_SAVING`. The "small system" clause in §H means exactly this and nothing else.

D3. TASK 16, column aggregation. All I rows of a column (J, mode) share the same runs and therefore the same amplitude set. Choose the `ColumnPlan` estimator as follows: among candidates in the closed family (TASK 2) admissible in ALL observed rows, choose the one minimizing the maximum across I of the total absolute budget (e/eV); deterministic tie-break: smaller maximum amplitude, then fixed family order. If none is admissible in every row, the column remains unresolved for that round and requests more amplitudes from the grid; with no new candidates → `NOT_ESTABLISHED`. Production uses the `ColumnPlan` estimator for every row (do not choose per element); the best estimator per row remains report-only diagnostics.
 Round rule: first refine the column with the largest first-order contribution to the U bound (weights |A_KI A_JK| and |𝒜_KI 𝒜_JK| calculated from the estimated matrices, which are not U); add the next grid amplitude allowed by the monotone exclusion rule; stop with `QUALIFIED` if it passes gate D4, with `REVIEW` if the protocol's maximum rounds are exhausted, and with `NOT_ESTABLISHED` if no candidates remain.

D4. TASK 16, gate in U space. Do NOT bound O(β²) analytically. Acceptance requires: (i) β⁰ < 1 and β < 1 (§I.7); (ii) evaluate U using the existing routines in `domain/u_certification.py` (import, DO NOT modify) on a `MatrixBox` expanded by the complete per-element budget (§I.8); the half-width of the U_KK interval must be ≤ τ_U (provided by the user, with no default). Label the result "qualification conditional on the error model", never "certified". If the `MatrixBox` API does not support per-element radii, stop and report it (do not modify the API).
 Without an SCF ESTIMATE component, calibrated mode cannot advance beyond REVIEW.

D5. TASK 17, SCF ladder. For each column and ladder amplitude a: Δ_L(a) = n_L(+a) − n_L(−a); η1 = |Δ_L0 − Δ_L1|, η2 = |Δ_L1 − Δ_L2|. R_i is the sum of print half-widths of the four printed values entering η_i. Bounds: η_i⁺ = η_i + R_i, η_i⁻ = max(η_i − R_i, 0).
 (a) η1⁻ > 0 (resolved): ρ̂ = η2⁺/η1⁻. If ρ̂ ≤ ρ_max: SCF_ESTIMATE(a) = θ·η1⁺/(1 − ρ̂). If ρ̂ > ρ_max: `NOISE_FLOOR_NOT_ESTABLISHED` (column limited to REVIEW).
 (b) η1⁻ = 0 (unresolved difference, including η1 = η2 = 0): ρ̂ = ρ_max (the protocol-declared value) and SCF_ESTIMATE(a) = θ·η1⁺/(1 − ρ_max), state `SCF_UNDER_RESOLVED`; the decision state is limited to REVIEW.
 θ and ρ_max come from the protocol (no code defaults; tests use explicit test values).
 Absolute/relative separation uses two measured amplitudes a_s < a_l (each with η⁺ and g = ½|Δ| as response magnitude): η_rel = max(0, (η_l − η_s)/(g_l − g_s)) if g_l − g_s > 0, and η_abs = max(0, η_s − η_rel·g_s); if g_l − g_s ≤ 0, the contribution is entirely absolute: η_abs = max(η_s, η_l), η_rel = 0. The envelope η(a) = η_abs + η_rel·g(a) applies only on [a_s, a_l]: a candidate with amplitudes outside that interval is inadmissible with reason `SCF_ENVELOPE_NOT_COVERED` (no extrapolation). Map to TASK 2 without changing its API: eps_abs_e (per point) = η_abs⁺-scaled/(2·(1−ρ̂))·θ, and eps_rel analogously, so the slope uncertainty is ε_Δ/(2a), where ε_Δ is the error in Δ (sum bound, not RSS). These quantities are ESTIMATE, never BOUND. No α=0 replicates as a noise floor.

D6. TASK 15. Keep it staged: `STAGED_PENDING_GENERATED_IDENTITY` is the correct state. Add `tools/hubbardflow_verify_split_identity.py` which, given the directory of a real SIESTA run with alias labels, compares each generated alias `.ion` to the original-label `.ion` by sha256 and emits the verdict (the user runs SIESTA; document this in the runbook). A positive test with a real repository FDF is not required: the synthetic case plus negative tests with real files are sufficient. Integrate `auto_split_species` into campaign admission when TASK 13 exists, always off by default.

D7. TASK 18. Implement it end to end with flags off by default. Egg-box: add no tolerance or new parameter; rotations (`EXACT_IN_CONTINUUM_ONLY`) require a shadow compared against TASK 14 budgets, so an egg-box effect appears as a shadow failure and expands the class. The plan records `egg_box_quantification = NOT_QUANTIFIED` until the user provides the specific V2 validation. `VALIDATION_GATES.md` documents which results (V2, V3, V4, with digests) enable each flag; do not fabricate results.

D8. TASK 12, 13, 14, 19. No specification changes, except that they are now implementable once D1 and D2 produce a complete `CoverageQualification`. TASK 19: if any dependency remains unmet, provide the `plan` and `run`/`submit` commands as far as the contract allows, with explicit `NOT_ESTABLISHED` state, rather than omitting them.

CLOSEOUT: update `PHASE2_SUMMARY.md` (table of task, branch, commit, tests, state, RESOLVED/OPEN blockers) and respond with that table. Do not merge into the base branch.
## Phase 2 close

### §4. Decisiones del autor (D9–D12)

- **D9 (SCF ladder).** Review §E.2 is authoritative over TASK 17.
  - Levels harden both the DM and the H tolerance, and each level has its own α=0 reference and
    parent DM.
  - For BARE, the level difference comes only from the parent DM (`MaxSCFIterations 1`). The D5
    formulas apply with three parent levels.
  - This extends §E.2, which describes BARE with two levels as an indicator. The third level gives
    the contraction check at the cost of two cheap BARE runs per amplitude.
- **D10 (species identity).** The verdict is width-preserving label normalization plus a diff
  confined to the label lines, not raw sha256 equality. The real pair FeLR0/FeLR1 is the positive
  control.
- **D11 (frozen Phase-2 plans).**
  - No Phase-2 campaign has run with SIESTA (checked in 0.2.5).
  - Plans frozen under `campaign-planner-v1` are not migrated: resume fails with
    `PLANNER_VERSION_CHANGED`, and the user re-initializes.
  - Plan content must not depend on optional packages.
- **D12 (product execution).**
  - A plan with no reduction, a fixed explicit grid and no adaptive policy is executable through
    the legacy runner. Its scientific content is the legacy V6-validated path.
  - I.5 and pilot reuse are requirements only for reduced or calibrated plans.

### Phase 2 close — resoluciones R1–R4

- **R1 (20.2).** “Is read” means “recognized.” `Chemical_Species_Label` is recognized and rejected with `NONCANONICAL_MANAGED_LABEL`, with a message that gives the canonical spelling `ChemicalSpeciesLabel`. For the positive read test, use a label outside the managed-label set recorded in the phase-close log, and record the selected label there. The rest of 20.2 is unchanged.
- **R2 (20.4).** Editing `tests/unit/test_split_generated_identity.py::test_real_archive_label_only_difference_is_never_a_positive` is authorized because it encodes the D6 rule replaced by D10. Rename it to `test_real_archive_label_only_difference_matches` and expect `MATCH` for the real `FeLR0`/`FeLR1` pair.
- **R3 (20.5).** (a) Editing `tests/unit/test_symmetry_operations.py::test_f8_records_incommensurate_translation_without_excluding_candidate` is authorized. With translation t=1/4 and `InitMesh=(3,3,3)`, retain the operation as a candidate and classify it `EXACT_IN_CONTINUUM_ONLY`, not `EXACT_TRANSLATION`. Keep the test name. (b) Remove `spglib` from planning as specified. The internal enumeration's missed rotation candidates for non-orthogonal cells can only reduce savings: rotations default off and are never reduced in production without V2 validation. Record the known Phase 3 limitation as “rotation enumeration independent of spglib for non-orthogonal lattices” in `BLOCKERS.md`; do not classify it as `RISK_UNCOVERED`. Verify and log that translations do not lose candidates; stop if one does.
- **R4 (20.9).** The only compatible archive chain is `campaigns/nio_pbe_p5_20260928/` (`campaign.v2.json`, `lr-config.json`, and node evidence). Redefine 20.9 to initialize, with current code and `coverage=DISABLED`, from the reference FDF and lr-config located via that campaign manifest. Compare the `(site, atom, mode, alpha)` set with the manifest and node evidence; also compare materialized-input hashes if node evidence records them. Record CoO, MnO, and Cu3N as `NOT_COVERED`; their equivalence is covered by the TASK 13 golden and TASK 21 test. If NiO P5 does not reproduce exactly, do not modify anything; stop and report the difference.


### Phase 2 close — resoluciones R5–R10

- **R5 (general rule for editing tests).** An existing test may be edited only if its assertion encodes exactly the behavior explicitly replaced by the item: the v1 ladder protocol, raw-SHA verdict, F8 having no effect on exactness, or fixtures representing inputs declared impossible by the new rule. For each edit, record the old assertion, new assertion, and replacing clause in `PHASE2_CLOSE_LOG.md`. `auditor_cientifico` must confirm the edit before the commit together with the item. If any other test fails, the code is wrong and that test must not be edited.
- **R6 (20.2 regression; separate first commit).** In `scf_ladder_inputs.py`, immediately after `resolve_fdf_includes`, reject any effective line whose first token after comments are removed and `canonical_fdf_label` is applied is `filedminit`. Do this before `parse_effective_fdf` and any protocol check; remove the later check through `_one`. Fix code, not `test_materializer_rejects_missing_parent_assets_and_unsafe_restart`; add coverage for `file_dm_init parent.DM`. Verify in this environment that the test passes and the full suite returns exactly to `BASELINE_FAILURES`.
- **R7 (20.3).** In `build_ladder_runs`, first run the safety checks for every input (`File.DM.Init`, missing assets), then validate the protocol version (`v1` → `SCF_LADDER_PROTOCOL_V1`). `test_materializer_rejects_missing_parent_assets_and_unsafe_restart` must pass unchanged; if it fails, stop. Apply R5 to `test_materialized_ladder_changes_only_tolerance_and_preserves_parent`, which expresses the replaced v1 protocol.
- **R8 (20.4).** Apply R5 to `test_exact_receipt_roundtrip_and_cli`: create valid aliases with `relabel_ion_bytes(_ion("Mn", 25), "Mn", "MnLR0")` and `"MnLR1"`; retain the positive receipt and exit code 0. Adjust raw SHA256 assertions and receipt state as appropriate. Add a test where identical raw bytes have a header that does not match the alias and expect `MISMATCH`.
- **R9 (20.5; corrects R3).** Do not lose translations classifiable as `EXACT_TRANSLATION`: exact rational mapping commensurate with the mesh. Without spglib, use `_ring((0.8,)*4)` and `_ring((0.8,)*8)` to verify all k/4 and k/8 translations appear; the author reports that they currently do. The near-symmetry displaced by `0.75*tau` is never exact and cannot reduce; losing it only removes an `AMBIGUOUS` expansion trigger. This is accepted because reduction requires an exact operation and mandatory shadow, while I.5 prevents production reductions. Record in `BLOCKERS.md` the Phase 3 limitation “near-symmetry detection without spglib”, which must be resolved before enabling reductions in TASK 22. Apply R5 to the F8 test.
- **R10 (20.9).** Plan IDs (`label@atom:n:l`, atom index base 0) and manifest IDs (DFTU label and `atom_index` base 1) are distinct namespaces: `inventory_sites` applies `atom_index + 1`. In manifest space, compare the `sites` and node identities from a newly initialized DAG with the archived manifest and node evidence for NiO P5, using `(label, atom_index, mode, alpha)`. If they do not match exactly, stop and report. The 20.3 draft and full NiO P5 initialization depend on files available in the agent environment; if anything does not match, stop without improvising.

## TASK 22

### D13a — G3 smoothness deferred

G3 smoothness (§I.5.5) is deferred. Its rigorous form requires the SCF ladder error (“print + ladder”), which has no production evidence yet (T0–T4). With only print bounds and three amplitudes, `verify_order` cannot detect jumps at the largest amplitude or symmetric jumps, and it false-alarms on Sz under realistic SCF noise. The audit verified both by probe. Report G3 as `NOT_ESTABLISHED: SMOOTHNESS_REQUIRES_SCF_LADDER`. Replace it with threshold-free per-point checks for discrete branch changes: G2 subspace, G2b occupation count, G3a moment sign, and G4 band count.

### D13b — G2 includes fully occupied channels

G2 also applies to fully occupied channels, such as the NiO majority-spin t2g/eg split. A reordering is a real change of orbital polarization; report it as a diagnostic.

### D13c — deviations recorded, not implemented

Record these deviations without implementing them in TASK 22:

- §I.5.1 dDmax/dHmax and iteration outliers (G1 uses node validation only).
- §I.5.3 total-moment quantization.
- §I.5.6 hysteresis.
- §I.5.7 Hellmann–Feynman.

### R11 — reference margin for defining k in G2

`k` is a property of the reference only. It is defined using the reference's margin against itself,
`ε_ref = 4W/(Δ_ref − 2W)`, and requires `Δ₁ − Δ₂ > 4W`, `Δ₁ > 4W`, and `ε_ref < 1/2`. If any condition is unmet, the result is `NOT_DEFINED` for that atom and spin.

At each point, apply the full margin
`ε = 2[W/(Δ_ref − 2W) + W/(Δ_pt − 2W)]`:

- If `ε ≥ 1/2`, or the point's separation is not unique (`Δ₁ − Δ₂ ≤ 4W` at the point), the result is `SUBSPACE_AMBIGUOUS` and fails closed.
- Otherwise, it passes if `c − ε > 1/2`; it is `ORBITAL_ORDER_CHANGED` if `c + ε < 1/2`; every other case is `SUBSPACE_AMBIGUOUS`.
- A point ambiguity is never converted to `NOT_DEFINED`.

The required test uses `W=2.5e−5`, `Δ_ref=0.1`, `Δ_pt=1.1e−4`, `c=1` and must produce `SUBSPACE_AMBIGUOUS`.

### R12 — E_F and the `.EIG`-specific precision in G4

G4 uses the E_F in each run's `.EIG` header, not the stdout E_F. Every `.EIG` energy, including E_F, has its own quantum `q`, one unit in the last printed mantissa digit at that exponent.

- An eigenvalue is ambiguous when `|ε − E_F| ≤ q(ε)/2 + q(E_F)/2`; equality is included and yields `BAND_COUNT_AMBIGUOUS`. Reference applicability uses the same rule: if a reference eigenvalue is ambiguous, G4 is `NOT_APPLICABLE`.
- The stdout E_F is used only as a consistency check. If `|E_F_stdout − E_F_EIG| > (stdout half-width) + q(E_F_EIG)/2`, the point evidence is inconsistent and G4 is `NOT_ESTABLISHED`, with reason `EIG_STDOUT_FERMI_MISMATCH`.
- The test of level `−0.450851396E+01` against E_F `−0.450851397E+01` must produce `BAND_COUNT_AMBIGUOUS`.
- The real `bare_p0p04` output passes the check: Fermi difference `3e−8 eV`, within `5e−7 + 5e−9 eV`.

## TASK 23

### D14a. Species identity without explicit `PAO.Basis`

In one FDF, every species without a `PAO.Basis` record gets its basis from the global `PAO.*` directives, which are shared by construction. Such a species is `ESTABLISHED` when its pseudopotential bytes are known and the FDF has no block outside an audited species-neutral list and no user-supplied basis (`User.Basis`). Any other block makes every species `NOT_ESTABLISHED` (fail closed): HubbardFlow cannot tell whether an unknown block is species-scoped. The explicit lr-config pseudopotential map is the identity source when present; directory search by `<label>.psml` remains the fallback.

### D14b. The shadow state gate is I.5

`CampaignShadow._complete_state_gate` is True iff, for every computed column (representatives, shadows, expanded columns) and both modes, the I.5 verdict is `PASS` and no check in any point has outcome `FAIL`, `NOT_AVAILABLE` or `NOT_ESTABLISHED`. `NOT_DEFINED` and `NOT_APPLICABLE` are allowed. G3 smoothness stays `NOT_ESTABLISHED` (D13a) and does not block: smoothness concerns the estimator, which is the same for direct and reduced campaigns. The shadow comparison is the direct empirical test of translation equivalence. Unlike the diagnostic verdict, G4 `NOT_AVAILABLE` (missing `.EIG`) blocks here.

### D14c. The parent DM must reproduce bit for bit

The TS plan binds the planning reference DM. The campaign reruns the reference with the same machinery. If its DM bytes differ, the campaign stops at once with `PARENT_DM_NOT_REPRODUCED`. It never silently expands to all columns. For the same reason, a product TS campaign stops with `SHADOW_REJECTED` instead of expanding (23.3). Evidence: the NiO reference DM `f7fca191…` appears identically in two independent campaigns on the user's laptop: `campaigns/nio_pbe_adaptive_20260928` and the product campaign `nio_p5_product_2` recorded in `tests/fixtures/real_nio_p5_rerun`.

### D14d. The planning reference comes from `hubbardflow reference`

It runs only the reference node of an ordinary direct campaign. There is no pilot reuse and no adoption of foreign outputs. The reference campaign can later be resumed as a full direct campaign.

### D14e. Deferred

The following wait for TASK 24:

- near-symmetry refinement for relaxed or non-rational coordinates (they stay `ALL_SUBSPACES`, which is safe);
- I.5 for non-polarized outputs (the parser fails on them today; see 23.7);
- rotations and spin flip;
- an automatic one-command `run` that chains `reference`.

### D16. Parent reference equivalence at print precision

D16 substitutes for D14c; the other D14 decisions remain in force. A TS campaign reference must be state-equivalent at print precision to the planning reference. Record both DM digests and the equivalence result.

### D16.1. Physical parent comparison with independent Fermi policy

DM and artifact digests are traceability only: record discrepancies as warnings,
never decide parent acceptance or translation reduction from them. `BITWISE`
is removed. Occupation matrices of the last converged population event use a
per-element tolerance `max(sum of both print half-widths, f * SCF.DM.Tolerance)`.
The factor `f` is explicitly declared as `parent_reproduction_factor`; neither
it nor a missing FDF tolerance is inferred. Missing occupation tolerance evidence
is `EQUIVALENCE_NOT_ASSESSED` without a hash veto. A real occupation difference
or incomplete atom/projector identity invalidates only the affected reduction
using that parent and schedules direct columns, with the physical reason recorded.

Fermi energy never inherits SCF.DM.Tolerance. Optional declared `tol_Fermi_eV`
has no default; product CLI `--tol-fermi-ev` overrides lr-config and freezes the
source. If declared, use `max(tol_Fermi_eV, sum of both Fermi print half-widths)`
and warn `FERMI_TOLERANCE_BELOW_PRINT_HALF_WIDTH` when the declaration is smaller.
An excess uses the distinct reason `PARENT_FERMI_NOT_EQUIVALENT`. If undeclared,
Fermi only records its difference in eV and print half-widths; it cannot change
the occupation verdict. Always record both DM digests, maximum occupation
difference, Fermi difference, declared/effective tolerances, sources and warnings.
Report `occupation_equivalence` (`EQUIVALENT`, `NOT_EQUIVALENT`, `NOT_ASSESSED`)
separately from `fermi_equivalence` (`EQUIVALENT`, `NOT_EQUIVALENT`,
`RECORDED_NOT_ASSESSED`). `RECORD_ONLY` never grants equivalence and preserves
assessed physical and identity rejections.
