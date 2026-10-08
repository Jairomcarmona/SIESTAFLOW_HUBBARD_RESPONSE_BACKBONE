# TASK 23c — Hash Audit and D16.1 State

## Closure of the Received Fermi-Energy Decision

The user's decision implements `tol_Fermi_eV` without a default and separates
occupation/Fermi states. Tests cover recording without a declaration, the
inclusive boundary, physical excess with its own reason code, a declaration
below the combined print radius with a warning, serialization/reporting,
`RECORD_ONLY`, different DM bytes, and the archived MnO reference. The MnO
replay declares factor `1.0` only in its fixture config; no production default
was added. The initial implementation changed no goldens and ran no real
SIESTA. A later CI correction updates only the two provenance goldens detailed
in the following R5 section.

Literal final outputs from this pass (PYTHONPATH=src):

```text
python -m pytest -q tests/unit/test_reference_reproduction.py tests/unit/test_hash_traceability.py
63 passed, 2 warnings in 1.73s

python -m pytest -q tests/unit/test_campaign_shadow.py tests/unit/test_campaign_runner_execution_identity.py tests/unit/test_import_architecture.py
41 passed, 2 warnings in 24.04s

python -m pytest -q tests/unit/test_campaign_plan.py
45 passed, 2 warnings in 58.58s

python -m pytest -q tests/unit/test_product_cli.py -k fermi
5 passed, 37 deselected, 2 warnings in 3.77s

wsl.exe bash -lc 'cd /mnt/c/Users/Jairo/work/hf_task23c && PYTHONPATH=src python3 -m pytest -q tests/integration/test_runner_replay_mno_ts.py'
2 passed, 2 warnings in 135.59s (0:02:15)
```

The first combined reference/config/CLI suite reported `1 failed, 132 passed`
because the new test omitted an import of `planning_config_digest`. The import
was added without changing any assertion; the full configuration suite and new
CLI cases passed afterward. Both warnings are historical deprecations of
`adaptive_alpha`/`alpha_selection`.

```text
python -m ruff check <reference, backend, step, CLI, product_plan, shadow, and affected tests>
All checks passed!
python -m ruff format --check <the ten reference, CLI, configuration, and shadow modules/tests>
10 files already formatted
python -m mypy --strict --follow-imports=silent <the nine reference, CLI, product_plan, and shadow modules/tests>
Success: no issues found in 9 source files
bash tools/check_v6_integrity.sh
V6 GATE OK
git -c core.whitespace=cr-at-eol diff --check
```

The last command exits without output; historical CRLF is preserved in
`tests/unit/test_campaign_plan.py`.

**Additional audit closed:** blocks in `product_cli._verify_campaign_inputs`
for a declared/stored digest that differs, is absent, or malformed are class (a)
and were converted to `DigestWarning`. Each required copy is read and compared
with both provenance records only to record `ARTIFACT_DIGEST_ABSENT`,
`ARTIFACT_DIGEST_MALFORMED` or `ARTIFACT_DIGEST_MISMATCH`. An absent
frozen-config digest also does not block. Truly absent/unreadable files,
paths escaping the campaign, and structural/physical validation still fail for
their actual causes. Warnings are deduplicated, sorted, and persisted in
`product-input-traceability.json` inside the campaign, before the worker starts;
they are also retained in product/reference execution links/receipts.

Additional tests verify differing metadata, metadata absent even when keys are
missing, malformed values, FDF bytes changed by an innocuous comment, identical
copies without warnings, and required files absent or replaced by a directory.
The first Windows fixtures wrote the config copy with CRLF and caused two
failures due to an additional legitimate warning; the fixture was corrected to
copy the exact frozen bytes while preserving the exact assertions.

```text
python -m pytest -q tests/unit/test_product_cli.py -k 'fermi or digest_metadata or changed_copy or required_real_input or unchanged_product' --show-capture=no
18 passed, 37 deselected, 2 warnings in 8.85s
wsl.exe bash -lc 'cd /mnt/c/Users/Jairo/work/hf_task23c && PYTHONPATH=src python3 -m pytest -q tests/integration/test_product_reference_nio.py'
1 passed, 2 warnings in 5.84s
python -m ruff check src/hubbardflow/product_cli.py tests/unit/test_product_cli.py
All checks passed!
python -m ruff format --check src/hubbardflow/product_cli.py tests/unit/test_product_cli.py
2 files already formatted
python -m mypy --strict --follow-imports=silent src/hubbardflow/product_cli.py tests/unit/test_product_cli.py
Success: no issues found in 2 source files
bash tools/check_v6_integrity.sh
V6 GATE OK
git -c core.whitespace=cr-at-eol diff --check
```

The last command exits without output; no golden was modified.

## CI Correction and R5 Provenance Golden

The orchestrator's authorization limits this update to the new traceability
effects of 23c. Verified-dataset and receipt serializers omit
`traceability_warnings` when empty and preserve every real warning. No replay
assertion was relaxed, and physical results, the analysis golden, the I.5
golden, and the normalized checkpoint were unchanged. Only the following
goldens change:

| File | Previous SHA256 | New SHA256 |
|---|---|---|
| `tests/fixtures/replay_nio_p5/campaign_json_snapshot.json` | `5fa071aef8590afb309a2e1c1ddadcc5a53fafbd2656f08aba24860e5501a758` | `95940b5f8932e4816e6357bd0d82af9bdff50e6a81c007592a93e283dc966545` |
| `tests/fixtures/replay_nio_p5/campaign_manifest.sha256.json` | `af86fdfa99c330548b9729ccc4f7533f60f594068dbd0dcd61c17e9906e55cbf` | `9fb5894ff3a1c8534b09f6c44663506a737dbc706a4c9fdc4e8ed16049eb9374` |

The exact JSON diff has **8 snapshot paths** and **3 manifest-derived entries**.
The external generator checks an allowlist of those paths and rejects any
unrelated change before writing:

| Snapshot path | Before → after |
|---|---|
| `campaign.lock.coverage_qualification.traceability_warnings` | Absent → two `ARTIFACT_DIGEST_ABSENT` warnings for `reference.echoed_input_sha256` and `reference.parent_dm_sha256`, with recorded/observed null. |
| `campaign.lock.plan_digest` | `184359604f69ab92d9e39d2d7f23eefe0d4656657386d8a83ccf4a502d3b271d` → `ac361235e8776bdec3e2a74a9ad56b0287a3ba373be3f87df1affe6601eb6a17`. |
| `campaign.v2.json.input_files[1].sha256` (`campaign.lock`) | `d86108fbcf1d6e5d3206b98b512209e7c300368469c9fcbf750bb123d7588951` → `8f3638ecf293b2022a6924fced7b3bf89e802e02098be562d3f61b7860024754`. |
| `campaign.v2.json.input_files[10].sha256` (`resolved_perturbation_plan.json`) | `5814e24672c352e79a4f0808249cf1aa7e3a0072326ad77ee27817ee241458bb` → `80250feb2f911d017ef3177efe6939686c1f3a8fcac4294db63712605b544ff3`. |
| `campaign.v2.json.resolved_perturbation_plan_digest` | `184359604f69ab92d9e39d2d7f23eefe0d4656657386d8a83ccf4a502d3b271d` → `ac361235e8776bdec3e2a74a9ad56b0287a3ba373be3f87df1affe6601eb6a17`. |
| `resolved_perturbation_plan.json.coverage.traceability_warnings` | Absent → the two preceding reference warnings. |
| `resolved_perturbation_plan.json.reason_codes` | `[DISABLED_OR_FIXED, PARENT_DM_NOT_ESTABLISHED, REFERENCE_NOT_ADMISSIBLE]` → `[DISABLED_OR_FIXED, REFERENCE_NOT_ADMISSIBLE]`. Only the missing-digest reason is removed; missing physical evidence remains recorded. |
| `resolved_perturbation_plan.json.traceability_warnings` | Absent → four `ARTIFACT_DIGEST_ABSENT` warnings for `echoed_input_sha256`, `parent_dm_sha256`, `reference.echoed_input_sha256`, and `reference.parent_dm_sha256`, all with recorded/observed null. |

Normalized manifest entries:

| Entry | Previous hash → new hash |
|---|---|
| `campaign.lock` | `d86108fbcf1d6e5d3206b98b512209e7c300368469c9fcbf750bb123d7588951` → `8f3638ecf293b2022a6924fced7b3bf89e802e02098be562d3f61b7860024754` |
| `campaign.v2.json` | `561fb80c765aaa58c2c938710688b853ca2f5a091d824f6697f9c06020265f08` → `3edfba852e4fb1119611891d83ae9b5112c0b34277d6caf6e5b750f62edef194` |
| `resolved_perturbation_plan.json` | `96ed7660e4f951114e8b9dcd292ea822e10619dd962d2ad257e5ae5fa3893726` → `61ade263afb04e93cd32e15bcd746f0c18b35c9be98818694b0209f2bd38368c` |

Test adaptations authorized by the criterion change:

- `test_campaign_production` and `test_matrix_lr`: a differing declared DM
  digest now requires warning `PARENT_DM_DIGEST_MISMATCH`, exact copied bytes,
  and the observed digest, replacing the SHA-based block.
- `test_product_execution`: an FDF comment/PSML whitespace changes only bytes;
  the simulated worker proceeds, run specs and the frozen-config copy remain
  exact, and the warning appears in the persisted link/file.
- `test_symmetry_operations`: an isolated `input_fdf_sha256` change is separated
  from physical negative cases. Classification preserves the symmetry and
  `CoverageQualification` retains `ARTIFACT_DIGEST_MISMATCH` with both digests.
  This FDF SHA is class (a), provenance only. The
  `identity_digest` per species/subspace remains class (b): it identifies the
  pseudopotential/basis/radials required by F2, and tests with different
  basis/ligand/environments still reject `ConditionStatus.DIFFERENT` in F2.
- New regressions demonstrate omission of empty warnings and persistence of
  real warnings in both dataset and checkpoint. Another test removes a real
  planning DM: a missing staged or source file fails with `FileNotFoundError`;
  a readable file with only its digest missing produces a warning. Removing
  `PARENT_DM_NOT_ESTABLISHED` never removes the required real file read or the
  node validator's generated-DM requirement.

Final outputs for this correction:

```text
python -m pytest -q tests/unit/test_campaign_production.py tests/unit/test_matrix_lr.py tests/unit/test_product_execution.py tests/unit/test_symmetry_operations.py tests/unit/test_observation_assembly.py
217 passed, 2 warnings in 25.84s
python -m pytest -q tests/unit/test_generic_executor.py tests/unit/test_observation_assembly.py tests/unit/test_product_admission.py tests/unit/test_import_architecture.py
45 passed, 2 warnings in 1.46s
python -m pytest -q tests/unit/test_product_cli.py -k missing_real_planning_reference_dm
1 passed, 55 deselected, 2 warnings in 1.48s
wsl.exe bash -lc 'cd /mnt/c/Users/Jairo/work/hf_task23c && PYTHONPATH=src python3 -m pytest -q tests/integration/test_runner_replay_nio_p5.py'
7 passed, 2 warnings in 11.82s
ruff check <campaign_files/generic_executor and affected product/symmetry/assembly/CLI tests>
All checks passed!
ruff format --check <the seven code/test files in this correction>
7 files already formatted
mypy --strict --follow-imports=silent <the six typed code/test files in this correction>
Success: no issues found in 6 source files
bash tools/check_v6_integrity.sh
V6 GATE OK
git -c core.whitespace=cr-at-eol diff --check
```

The last command exits without output. Ruff `--select F` on the two historical
test modules `test_campaign_production.py`/`test_matrix_lr.py` reports 10 prior
findings: unused imports (`tempfile`, `assign_afm_ordering`, four matrix LR
types) and four redefined imports from production_benchmarks. Those unrelated
findings were neither modified nor suppressed.

## Decision Rule

DM, output, and evidence SHA-256 values describe files or help retrieve records.
A digest disagreement is persisted as a warning and never declares a physical
difference. Path, existence, format/parsing, convergence, and semantic
identities remain independent conditions and can fail for their actual causes.
Node/reuse hashes only retrieve execution identities; byte equality does not
prove state equivalence.

## Usos de `parent_dm_sha256` y digests relacionados

| Location / use | Class | Handling |
|---|---|---|
| `execution/campaign_plan.py`, `execution/product_plan.py`: capture the parent DM SHA | (a) file provenance | Recorded only; a missing digest does not prevent planning an admissible reference. |
| `domain/coverage_models.py`, `domain/perturbation_plan.py`, `domain/perturbation_planner.py`: transport/validation of parent digest | (a) provenance | Not used to admit or reject the plan. Admissibility still depends on convergence, inventory, and observed physical identities. |
| `execution/product_admission.py`: digest presence | (a) provenance | `PARENT_DM_REQUIRED` was removed as a blocker. |
| `product_cli._verify_campaign_inputs`: digests for source/config/pseudopotential/static/profile copies and manifest | (a) provenance | Mismatch/absence/format only warns; missing fields are read with `.get`. Actual file existence/readability and path confinement are verified. Warnings persist in the traceability file and links/receipt. |
| `execution/campaign_runner.py`: planned DM compared with observed DM | (b) recalculated state | BITWISE removed. Parsed occupations decide, as does Fermi's own energy tolerance only when declared; both digests are always retained. |
| `execution/campaign_shadow.py`, `execution/observation_assembly.py`: reference DM compared with digest inherited by observations | (a) traceability | Differences produce `PARENT_DM_DIGEST_MISMATCH` / `PARENT_DM_IDENTITY_MISMATCH`; they no longer veto a shadow or matrix. |
| `execution/campaign_files.py`: FDF, OUT, DM, and parent-DM copy compared with provenance | (a) file identity | Missing files or unsafe paths still fail. A different hash is returned as `hash_warnings` (`ARTIFACT_DIGEST_MISMATCH`, `PARENT_DM_DIGEST_MISMATCH`). |
| `execution/source_evidence.py`: hashes of OUT, DM, receipts, manifest, and canonical identity | (a) traceability | Mismatch is added to `traceability_warnings`. Reading, JSON, event selection, and numerical extraction remain validated; unreadable data or responses that cannot be re-extracted fail explicitly. |
| `execution/campaign_runner.py::_revalidate_reuse` and `_analysis_execution_identity` | (a) stored-evidence digest | Mismatches are recorded as warnings; node state, paths within the campaign/attempt, modes, and existing artifacts remain validated. |
| `domain/lr_analysis_v2.py`, `domain/matrix_lr.py`, `domain/scalar_lr.py`, `domain/observation_provenance.py` | (a) transport/report/reuse | Hashes appear as provenance; physics uses parsed occupations and responses. They are not used as physical-equivalence criteria. |
| `reporting/lr_u_report.py`, `reporting/product_report.py` | (a) reporting | Present planning/campaign SHA values as evidence, not acceptance criteria. |
| `domain/response_grid_reproducibility.py`: hashes of DM, OUT/FDF, receipts, analysis, lock, and dataset | (a) traceability/reconstruction | Mismatch remains in `traceability_warnings`; existence/path and semantic re-extraction are validated separately. Context, receipt, dataset, and numerical comparison retain their own contracts. |
| `domain/response_reuse.py`: parent, FDF, profile, projector, species, magnetism, and MPI identity | (a) provenance; physical context not represented | Equal/different/absent/malformed hashes yield the same `NOT_ESTABLISHED` decision when available semantic keys match; `PHYSICAL_CONTEXT_NOT_ESTABLISHED` requires direct recalculation. Semantic-key differences are classified separately as `PHYSICAL_IDENTITY_MISMATCH`. Identity v1 contains hashes only for missing physical values. |
| `execution/campaign_pilot_reuse.py`: output/receipt/identity | (a) provenance | Revalidates receipt readability, schema, and state; records warnings for all digests. A pilot is not reused without sufficient physical values, regardless of SHA. The independent selector is not yet connected to init/runner. |
| `siesta_backend/observation_selector.py`, `bare_semantics_evidence.py`, `bare_trace_provider.py`: reference/executable/FDF/OUT/trace | (a) provenance | Missing/malformed/different hashes are recorded as `ARTIFACT_DIGEST_ABSENT`, `ARTIFACT_DIGEST_MALFORMED`, `ARTIFACT_DIGEST_MISMATCH`, and parsing continues. Audited markers, ordering, uniqueness, interval, version, and termination remain semantic conditions. Context/receipt carries the warnings. |

## Other Hashes Reviewed

FDF/config/profile/pseudopotential digests identify inputs and provenance.
Digests of reports, locks, receipts, and datasets identify stored files. None
proves physical equality; their discrepancies must not become
`PARENT_STATE_NOT_EQUIVALENT`. Campaign, node, attempt, path, and mode identifiers
remain structural invariants (not SHA values). Canonical matrix/plan hashes
retrieve deterministic commitments; wherever they feed a physical decision,
they must be replaced by the observed value/state, while retaining the digest
as a reference.

## D16.1 and the Dimensional Fermi Decision

`BITWISE` was removed from the enum and configuration; the `RECORD_ONLY`
alternative does not grant equivalence, but retains rejection for a real
physical difference or incomplete identity. `PRINT_EQUIVALENT` requires an
explicit `parent_reproduction_factor` and a unique, positive `SCF.DM.Tolerance`
declared in the FDF to form the occupation radius
`max(sum of print half-widths, factor × SCF.DM.Tolerance)`. If either is
missing, `EQUIVALENCE_NOT_ASSESSED` is emitted and SHA does not cause rejection.

The density-matrix tolerance is not applied to eV. Policy `tol_Fermi_eV` is
optional, explicitly declared, and has no default. Product CLI option
`--tol-fermi-ev` overrides configuration and records source `cli`; a JSON
declaration records source `config`. If absent, the difference, units, and
half-widths are retained under `fermi_equivalence=RECORDED_NOT_ASSESSED`; this
does not change the occupation decision. If declared, it is compared against
the maximum of its value and the sum of both print half-widths: the two rounded
data values contribute additive radii. A declaration below that sum emits typed
warning `FERMI_TOLERANCE_BELOW_PRINT_HALF_WIDTH`, preserves the declared value,
and records the effective radius. A physical excess emits
`PARENT_FERMI_NOT_EQUIVALENT`, distinct from the occupation reason, and directly
calculates all classes using that parent. `occupation_equivalence` and
`fermi_equivalence` are serialized and presented separately. `RECORD_ONLY` never
grants equivalence and retains already evaluated physical rejections.
Unavailable parsing produces `EQUIVALENCE_NOT_ASSESSED`; incomplete
atom/projector identity uses `PARENT_IDENTITY_NOT_ESTABLISHED`, and direct
fallback is limited to that atom's class (or all classes if the difference is
global).


## Corrections and Tests in This Pass

A difference in occupation greater than the declared radius invalidates the
reduction with `PARENT_STATE_NOT_EQUIVALENT`, even if Fermi's energy tolerance
remains unevaluated. Details identify atom, spin, element, difference, and
radius; pending comparisons are recorded separately. No DM tolerance is applied
to energy; occupation equivalence can establish the overall verdict without an
energy declaration, with the record-only Fermi state visible.

### Assertion Edits Authorized by the Steering and Orchestrator

| Test/case | Before | Now | Reason |
|---|---|---|---|
| `test_reference_reproduction`: two-quantum difference | `NOT_ASSESSED` because Fermi is absent | Detailed physical rejection even when Fermi is absent | Fix masking of an already assessable occupation difference; strengthens the invariant. |
| `test_response_reuse`: roundtrip and nine hash dimensions | `EXACT_MATCH` or `IDENTITY_MISMATCH` by SHA | `NOT_ESTABLISHED`, warning for different SHA; roundtrip and physical keys remain verified | Hash lacks sufficient physical values. |
| `test_response_reuse`: changed output and conflicting pilots | Exception for SHA/bytes | Warnings recorded, deterministic selection, no pilot reused | Recalculate directly without blocking the campaign. |
| `test_response_reuse`: changed receipt | Exception for receipt/identity digest | Explicit warnings and `NOT_ESTABLISHED`; new `FAILED`/`None` cases retain receipt-state rejection | SHA is traceability; schema/state are still revalidated. |
| `test_bare_trace_provider`: substituted executable | Exception for SHA | `VERIFIED` receipt with explicit warning; missing sidecar and collector still fail | Traceability is separate from the semantic contract. |
| `test_bare_trace_adversarial_audit`: innocuous append to artifacts/trace | Exception for SHA | Warning with field, reason, and observed digest | Changing bytes does not prove a physical difference. |
| `test_bare_trace_adversarial_audit`: order, duplicate/missing marker, aborted output, version/revision, forged vocabulary, incomplete schema | Semantic error | Same semantic-error assertions | Physical/structural criteria were unchanged. |

Cases were added for missing/malformed hashes in the five BARE and pilot fields,
occupation noise below the explicit radius, different DM with identical
numbers, the archived MnO adversarial case, and warning serialization. No golden
was changed.

Focused verification (worktree PYTHONPATH):

```
python -m pytest -q tests/unit/test_hash_traceability.py tests/unit/test_reference_reproduction.py tests/unit/test_response_reuse.py tests/unit/test_bare_semantics_evidence.py tests/unit/test_bare_trace_adversarial_audit.py tests/unit/test_import_architecture.py
103 passed, 2 warnings in 3.04s
```

## Closure Status for This Pass

The user's decision closes the energy policy: occupations decide, and Fermi
participates only with a declared eV tolerance. The inventory/source/effective
FDF traceability and calibration-evidence TODOs were closed.

### Additional Table by Decision Call Site

`(a)` identifies DM/file/evidence provenance and only warns. `(b)` identifies
the canonical species required by F2: it represents the pseudopotential and
radials, not the label or element. `(c)` is an operational/protocol contract
outside parent-equivalence assessment; it is retained within the scope confirmed
by the orchestrator. These latter checks may invalidate resume if the frozen
contract changes; they are not presented as D16 physical differences.

| Call site | Class | Handling / rationale |
|---|---|---|
| `perturbation_plan_evidence.freeze_inventory`: inventory/effective-FDF SHA | a | Does not require format/presence; retains unique atom/site values and complete `ProjectorEvidence`. |
| `freeze_inventory`: species identity | b | Canonical pseudopotential/subspace identity used by F2; `require_sha256` remains when supplied. |
| `coverage.qualify_coverage`: inventory/source/OUT SHA | a | Validators that prevented classification of already-parsed physical evidence were removed. |
| `CoverageQualification.__post_init__/from_mapping`: inventory/effective-FDF SHA | a | Optional; warnings are computed and serialized when present. Classes, operation indices, and partition are validated. |
| `symmetry_operations.classify`: input/effective-FDF SHA | a | A difference warns in qualification; it no longer produces `EVIDENCE_BINDING_MISMATCH` or digest-based expansion. |
| `symmetry_operations.classify`, `SymmetryAtom`, `SymmetryModel`: species identity and canonical model contract | b/c | Preserve exact F2 species/pseudopotential identity and model schema. Equivalence is not inferred from labels. |
| `ResolvedPerturbationPlan._validate`: source/effective/inventory binding | a | Warning; compares the physical coverage reference by values and verifies protocols, run_specs, omissions, and reconstructions. |
| `ResolvedPerturbationPlan.from_mapping`: SHA metadata and derived fields | a/c | SHA values are optional; equality of semantic fields/bands/weights remains required. |
| Plan `CalibrationQualification`: evidence SHA and observed protocol digest | a | Warning in plan; tau, columns, estimator, and matrix retain their physical contract. |
| `perturbation_planner.resolve_perturbation_plan`: qualification protocol_sha256 | a | Mismatch only warns in plan; tau and declared columns/amplitudes are still checked. |
| `fdebq_models.CalibrationQualification`: evidence_sha256 | a | Optional/malformed values are allowed as metadata, with serialized warning; status/qualification, columns, and matrix are unchanged. Protocol SHA is a separate class (c) contract. |
| `ProductSnapshot.__post_init__/from_mapping`: inventory/source/input/FDF SHA | a | Compares inventory/coverage by semantic values; absence/format does not decide. Frozen-config hash discrepancy is recorded in detail. |
| `product_admission.execution_admission/_translation_shadowed_admission`: inventory.digest | a | Warnings in admission; status, physical inventory, sites, grid, reduction/shadow, and reference flags are still evaluated. |
| `campaign_v2.load_campaign_v2/verify_campaign_inventory`: input-files SHA/input_identity | a | Hash is optional; mismatch/format/absence warns. Real files, safe paths, and manifest structure are retained. Runner persists warnings and the report displays them. |
| `campaign_runner._analysis_execution_identity`: required evidence_digest | a | Node ID and `VALIDATED` are required; absent/malformed evidence_digest only warns. |
| `generic_executor.NodeReceipt/JsonDagCheckpoint`: evidence_digest | a | Optional metadata and serialized warnings; node_id/state/duplicates and operational DAG remain required. |
| `response_grid_reproducibility._fields/_digest/_validate_reference_execution`: DM/OUT/FDF/receipt SHA | a | SHA fields are optional; format/mismatch warn. Missing hash maps do not prevent re-extraction of real files. Independent attempts, modes, atoms, parsing, and physical data are verified. |
| `source_evidence.validate_source_manifest/extract_verified_response_tokens` and schema | a | SHA is optional; format/absence/mismatch warns. Finite JSON, semantic schema, file/path, `VALIDATED` nodes, parser, and numerics remain required. |
| `observation_provenance.validate_observation/validate_response_lot`: parent-DM/FDF/output/SCF-evidence SHA | a | Do not decide acceptance; warnings are recorded in the lot. Cartesian grid, roles, zero return code, SCF, and positive DM-read remain required. |
| `observation_provenance`: pseudo/subspace/projector/physical-model/runtime/selector/magnetic canonical identities | b/c | Represent physical identity or declared selection contract; outside the D16 recalculated-state gate. |
| `occupation_noise_calibration.validate_calibration_result`: expected-result/DM/receipt/replica-result SHA | a | Evidence SHA values are optional and warn; the statistic is re-derived while policy, independent jobs, paths, and count are retained. |
| `occupation_noise_calibration`: frozen lock/result-lock SHA | c | Preregistered recipe commitment; a recipe change does not admit a result under a different policy. |
| `adapter.prepare_canonical_dm` | a | Returns the observed digest; mismatch only triggers `RuntimeWarning` with reason code; `copy2`/file existence retain real errors. Retired path; does not authorize execution. |
| `campaign_plan.verify_frozen_campaign_plan` | c | Canonical plan/config/planner-version locks for resume, separate from the D16 physical gate. Retained. |
| `campaign_shadow` journal plan digest | c | Journal must belong to the same operational plan; retains the record-association gate. |
| `campaign_v2` resolved plan digest, `product_plan` lock, `ProductBoundary` receipt identity, `generic_executor` DAG digest | c | Canonical plan/runtime contracts; preserved, not physical equivalence. |
| `campaign_software_lock`, `backend_admission` | c | Ensure execution uses actually admitted/installed software; not replaced with D16 equivalence. |
| `campaign_split`, `semantic_split_models`, `split_generated_identity`, `scf_ladder_inputs` | b/c | Semantic identity/protocol for materializing generated inputs; outside the D16 judgment of observed DM/evidence. |
| `fdf_symmetry_adapter`: symmetry certificate binding | b/c | Operation certificate bound to the declared physical model; not evidence of parent reproduction. |
| `scf_validation`: T0–T4 protocol/evidence commitment | c | Formal validation of the independent scientific protocol; does not admit D16 parents or shadows. Retained in scope. |
| `u_certification_node`, `u_release_gate`, `downstream_u_admission`, `domain/u_certification.py` | c / protected | Historical scientific certification/release; not edited. The migrated node is part of the protected V6 baseline. |
| `reporting/lr_u_report`, `reporting/product_report`, `domain/lr_analysis_v2`, `matrix_lr`, `scalar_lr` | a | Only transport/render digests; they do not decide based on them. |

The uses of the parent/shadow/reuse/BARE backend modules in the initial table
remain warning-only. The scan used `rg` for `sha256`, `digest`, comparisons,
and `require_sha256` in domain/execution/backend/reporting. V6 and certification/
release gates were not edited.

### Additional Test Edits

| Case | Before | Now / reason |
|---|---|---|
| `test_coverage`: effective-FDF SHA binding | `ALL_SUBSPACES`/`EVIDENCE_BINDING_MISMATCH` | Same strategy/classes/computed_columns as identical evidence; warning. Fallbacks for missing evidence, perturbation, species/operation, and syntax remain. |
| `test_perturbation_plan`: source/effective/inventory SHA | Error | Same statuses/runs/reconstructions and warnings; changed bands/weights still error. |
| `test_product_admission`: snapshot digest | Digest-based block | Physical case retained by changing `atomic_number`; new SHA cases only warn. Fixture uses complete `ProjectorEvidence`/`CorrelatedSubspace` to compare values. |
| `test_perturbation_planner`: parent-DM SHA absent | `NOT_ESTABLISHED` | Direct `READY` with warning; a truly inadmissible reference remains `NOT_ESTABLISHED` with full runs. |
| `test_observation_provenance_integration`: different parent SHA | Mixtures error | `compatible_for_analysis` with warning; incomplete grid and incorrect SCF state still error. |
| New cases in `test_source_evidence`, `test_campaign_plan`, `test_generic_executor`, `test_fdebq_rounds`, `test_occupation_noise_calibration`, `test_hash_traceability` | No absence/malformed coverage | Identical re-extraction/physical state for absent/malformed SHA; real errors for missing file, receipt without node ID, changed occupation/canonical identity, or altered statistic. |

The timeout and Hypothesis limit were unchanged. An intermediate run exceeded
the 200 ms deadline because plan warnings traversed the entire model twice; the
code was optimized to inspect metadata only, and the 15 plan tests were rerun:
`15 passed, 2 warnings in 4.65s`.

Final expanded pass (including the provider and previously modified consumers):

```
python -m pytest -q tests/unit/test_hash_traceability.py tests/unit/test_reference_reproduction.py tests/unit/test_response_reuse.py tests/unit/test_bare_semantics_evidence.py tests/unit/test_bare_trace_adversarial_audit.py tests/unit/test_bare_trace_provider.py tests/unit/test_import_architecture.py tests/unit/test_observation_assembly.py tests/unit/test_product_admission.py tests/unit/test_campaign_shadow.py tests/unit/test_source_evidence.py
170 passed, 4 skipped, 2 warnings in 16.45s
```

Literal output from final gates:

```
git diff --check
# no output, exit 0
bash tools/check_v6_integrity.sh
V6 GATE OK
ruff check --isolated --target-version py312 --line-length 110 <hash_traceability, response_reuse, campaign_pilot_reuse y sus tests editados>
All checks passed!
ruff format --isolated --line-length 110 --check <same six files>
6 files already formatted
mypy --strict --follow-imports=silent src/hubbardflow/domain/hash_traceability.py src/hubbardflow/domain/response_reuse.py src/hubbardflow/execution/campaign_pilot_reuse.py
Success: no issues found in 3 source files
```

The four skipped tests are POSIX/integration tests conditioned on Windows in
the source_evidence suite; SIESTA was not run. The warnings are the two existing
deprecations of alpha_selection/adaptive_alpha. No commit, push, PR, or branch
change was made in this pass.


## Final Evidence for the Expansion

```
# source_evidence + perturbation_plan_evidence + response_grid_reproducibility_independence
20 passed, 4 skipped, 2 warnings in 2.08s
# observation_provenance + occupation_noise_calibration (includes optional DM/evidence receipt fixture)
16 passed in 0.71s
# fdebq_rounds + hash_traceability + generic_executor
43 passed, 2 warnings in 7.07s
# campaign_plan + campaign_runner_execution_identity + generic_executor + product_admission + source_evidence + observation_provenance + occupation_noise_calibration + hash_traceability + import_architecture
123 passed, 4 skipped, 2 warnings in 67.54s
```

The initial broad suite of twelve modules had old hash assertions and was
interrupted after focused results were shared, at the orchestrator's request.
Another coverage/plan/planner run reached `70 passed` before the historical
missing parent-DM assertion (since adapted and documented). The last rerun of
those three modules was interrupted to free the writer, with no new failures
printed. The broad suite is not declared fully green.


## Corrections from the Final D16.1 Audit

- Occupation comparison calculates the radius for each element as the
  sum of the half-widths of its two decimal tokens. For that element it applies
  `max(element_print_radius, factor * SCF.DM.Tolerance)`. Lower precision in
  another element or atom never expands this element's tolerance.
  `occupation_tolerance_e` retains the maximum only as an informational summary;
  `occupation_tolerances_e` records every effective radius used.
- `affected_atom_indices` retains all atoms with physical differences; expansion
  uses this typed field. It does not parse the first atom from a diagnostic
  string. Incomplete global identity, legacy data without typed scope, or
  unlocatable indices cause direct calculation of all reduced classes for that
  parent.
- The report shows both digests, maximum differences, effective occupation
  radii, declared SCF tolerance, and factor. Fermi records its own state,
  difference, print half-widths, declared/effective tolerance, source, and
  warnings. Without a declaration it uses `RECORDED_NOT_ASSESSED` and does not
  change the parent verdict.
- Revalidating a resume saves `node-evidence.json` even when all nodes remain
  validated: hash warnings do not depend on invalidation to persist.

New tests: heterogeneous precision within one atom (a `0.5` token does not hide
the `0.00002` difference in another element); recording two physically distinct
atoms; expansion of two classes and global expansion for incomplete identity;
unevaluated tolerances and Fermi in Markdown; warnings persisted without
invalidations. The archived MnO adversarial test and noise/different-DM tests
remain active. No golden was updated.

Literal output from focused verification:

```text
70 passed, 2 warnings in 18.90s
All checks passed!
All checks passed!
3 files already formatted
Success: no issues found in 5 source files
V6 GATE OK
```

Commands: pytest with explicit paths for `test_reference_reproduction.py`,
`test_campaign_shadow.py`, `test_campaign_runner_execution_identity.py` y
`test_import_architecture.py`; ruff check y format de referencia y adaptador;
ruff check for shadow tests; mypy strict with follow-imports=silent for the five
reference and shadow modules/tests. Ruff F on the legacy runner reports eleven
pre-existing findings (historical imports and one f-string); its APIs were not
changed and those imports were not removed in this correction.


The final review corrects `RECORD_ONLY`: it never grants equivalence, but an
occupation exceeding the effective tolerance and an incomplete identity still
invalidate the parent's reduction with the physical reason code. Tests cover
both paths (domain comparator and parser) and retain no rejection for noise
within tolerance or different DM bytes. `CODEX_TASK23_TS.md` is updated to
remove the bitwise option and DM reason code, document direct calculation by
physical scope, and record the user's dimensional decision for Fermi.

### TASK 23c-bis — Accepted Clarification of `RECORD_ONLY`

The task's initial wording (“record without deciding”) is intentionally refined
for this mode: `RECORD_ONLY` never declares physical equivalence or approves a
TS reduction. It does retain rejection and direct calculation when a measured
physical difference is outside tolerance or atom/projector identity is
incomplete. This interpretation is accepted as the safer criterion because
the mode must not turn negative physical evidence into permission to reduce.
This decision depends on occupations and physical identity, never SHA/digests;
hashes remain warnings and traceability only.


Literal output after correcting RECORD_ONLY (pytest with five explicit modules
for reference, shadow, runner identity, hash traceability, and architecture):

```text
89 passed, 2 warnings in 16.73s
All checks passed!
3 files already formatted
Success: no issues found in 5 source files
V6 GATE OK
```

`git diff --check` exits without output. The `test_campaign_plan.py` diff is
minimized by preserving the bytes of historical lines and adding only the
existing configuration/traceability cases; no assertions are weakened.

The explicit suite `tests/unit/test_campaign_plan.py` passed:

```text
39 passed, 2 warnings in 45.33s
```
