# Scientific configuration decoupling plan

**Status:** Phases I–VII complete; verification limitations recorded

**Basis:** `SCIENTIFIC_DECOUPLING_INVENTORY.md` at the authorized active baseline

**Immutable oracle:** `scientific-v6-final` at `45cb53c5a98d9d55a163c05ca3b815a8ff9cfb7f`

## Objective

Remove implicit PBE and material-shaped assumptions from reusable implementation while keeping Hubbard-response mathematics, scientific policy, SIESTA behavior, campaign data, execution, and provenance in explicit layers. Preserve the V6 baseline as the immutable scientific semantic oracle.

Architecture work may change representation and dependency direction. It may not change the method or any V6 scientific result.

## Target model

1. **Scientific profile** — immutable, typed, versioned declaration of XC identity and validation status. The first qualified profile is explicit PBE. Other currently recognized XC families remain declared/recognized only unless repository evidence establishes and tests their method profile; do not imply qualification by accepting a family token.
2. **Campaign/material data** — material name, structure/site mapping, species labels, pseudopotentials, reference input identity, and alpha grid. Values select a case; they do not select hidden algorithms.
3. **Response-analysis policy** — explicit BARE/SCREENED role semantics, precision/event-selection contract, and certification policy. Generic LR math consumes normalized evidence and keeps existing formulas, thresholds, ordering, and rounding.
4. **SIESTA method/backend profile** — SIESTA release and response semantics, FDF and PSML validation/rendering, OUT parsing, population/event extraction, and version-specific precision. This is not the XC profile.
5. **Execution profile** — MPI/process limits, launcher, paths, scheduler/runtime. It carries no scientific defaults.
6. **Evidence/provenance** — source identities, hashes, receipts, and run records. Evidence binds inputs and outputs; it does not substitute for scientific validation.

## Migration and compatibility decisions

- Keep the v2 campaign/config and pointer readers compatible with their persisted schema identifiers.
- V2 records already require an explicit `functional`; migration may map only that declared value into a typed profile. A missing or unsupported value is an error, never an implicit PBE default.
- Keep the persisted campaign/config schema identifiers at v2 because the existing v2 functional field is explicit and sufficient for deterministic migration. Newly initialized campaigns add a typed, versioned `xc_profile` object; v2 records without it are migrated from their explicit `functional` field. If both fields occur, they must agree exactly. The key `xc_profile` distinguishes XC identity from the backend contract's existing SIESTA `scientific_profile`. Avoid mutating existing campaign records or frozen V6 artifacts.
- Keep the functional declaration singular in the new logical model. Validate/canonicalize FDF and PSML claims against it rather than treating their textual spellings as independent sources of truth.
- Treat the existing `siesta-5.4.2-potential-shift-hamiltonian-v1` as a backend/method profile identifier; do not repurpose it for XC.
- Keep reference FDF as the explicit source for backend-level physical settings that it already carries. Do not create redundant configuration copies of basis, mesh, k-grid, temperature, spin, or projectors without a demonstrated need.
- Preserve public CLI behavior where compatible; add explicit migration/admission errors where formerly implicit material or scientific defaults existed.

## Phases and gates

### Phase I — inventory (complete when reviewed against source)

Record the current coupling locations, ownership, immutable boundaries, and unresolved choices in `SCIENTIFIC_DECOUPLING_INVENTORY.md`. Gate: all proposed changes map to observed source or are identified as hypotheses; no frozen file is proposed for edit.

### Phase II — architecture and migration plan (this document)

Set ownership boundaries, compatibility behavior, schema direction, and ordered implementation/gates. Gate: explicit PBE identity does not silently promote other XC families; v2 functional is preserved; no scientific semantics move or change.

### Phase III — explicit scientific profile

Add typed/versioned XC profile and validation-status representation. Make PBE explicit in the active configuration path. Ensure unsupported/unqualified profile use fails clearly. Do not add new scientific profiles by inference.

Gate: schema round-trips profile identity; v2 migration requires and preserves its functional; existing PBE campaigns resolve to the same method identity.

### Phase IV — remove implicit material defaults

Make FDF builder species/projector/prefix values explicit. Separate reusable response configuration from campaign/material values and backend settings. Update active tests/examples/callers. Preserve fixture-specific numbers.

Gate: no production construction path silently substitutes Mn, a 3d projector, or a material label when omitted; generated FDF for existing fixture inputs remains semantically identical.

### Phase V — enforce single source and responsibility boundaries

Make campaign/profile admission the single logical source of XC identity and validate FDF/PSML declarations against it. Move SIESTA syntax parsing and version-specific response selection behind backend adapters. Have generic domain analysis consume validated immutable evidence values. Keep execution resource settings separate.

Gate: dependency direction is generic domain <- validated values; domain modules do not parse SIESTA files or import SIESTA selectors; backend owns those details.

### Phase VI — regression, static audit, and test coverage

Use the frozen V6 baseline only as a read-only oracle. Add/adjust tests for v2 migration, explicit PBE identity, rejection of missing profiles, explicit material/projector inputs, backend parsing contracts, dependency boundaries, and representative fixtures. Compare active generated inputs and derived semantics with the frozen oracle without launching SIESTA.

Gate: no unexplained semantic drift in V6 fixtures; no forbidden file changes; tests demonstrate both supported behavior and rejection paths.

### Phase VII — documentation and final verification

Document profiles, schema migration, responsibility boundaries, compatibility behavior, and verification evidence. Produce `SCIENTIFIC_DECOUPLING_VERIFICATION.md` with changed-file scope, test/static-audit results, V6 semantic comparison, and explicit limitations. Verify tag object/target and frozen artifacts remain unchanged; report historical provenance gaps without upgrading reproducibility claims.

Gate: working tree diff contains only authorized active implementation/tests/docs/config changes; no SIESTA was run; freeze identity and V6 scientific content remain intact.

## Verification strategy

- Inspect changed-file scope against the frozen tag before and after implementation.
- Run focused unit tests for each new profile, migration, rendering, and backend boundary, then the repository test suite using an available declared development environment.
- Compare deterministic generated FDF/config semantics and selected analysis outputs against committed fixtures and the frozen V6 oracle. Never create new electronic-structure data for this check.
- Run static import/dependency scans to verify generic domain code no longer imports backend parsing or campaign file I/O.
- Do not recalculate or rewrite frozen reports, certificates, run records, input files, or provenance hashes.
- Do not run SIESTA, launch campaign nodes, recompute U/observables, begin J/V, add another engine, or start product/JOSS consolidation.

## Concrete module and test map

| Phase | Add/migrate | Keep SIESTA-specific | Focused checks |
|---|---|---|---|
| Explicit profile | Add `domain/scientific_profile.py`; migrate normalization/admission in `execution/campaign_v2.py`; emit the profile in `execution/wsl_campaign_init.py` and analysis provenance in `execution/campaign_runner.py` | FDF and PSML spelling validation stays in campaign/backend admission | `tests/unit/test_scientific_profile.py`; campaign v2 missing/mismatch and old-record migration cases |
| Material decoupling | Make target species and method-2 projector values mandatory in `siesta_backend/fdf_builder.py`; update active call sites and fixtures | Serialization of DFTU.Proj remains SIESTA-specific | `tests/test_fdf_builder_safe_materialization.py`, `tests/backend/test_fdf_builder.py`, projector/materializer tests |
| Evidence boundary | Separate campaign file reconstruction and SIESTA event/precision parsing from generic response-grid validation; use normalized immutable evidence values | `siesta_backend/occupation_precision.py`, SIESTA profiles, event parser, and screened selector stay backend-owned | response-grid reproducibility tests, analysis boundary/import tests |
| Regression/audit | Add explicit profile/render semantic regression for frozen NiO, FeO, CoO, MnO and import/static scans | Frozen inputs, reports, and certificates remain read-only oracle data | profile/render integration tests, frozen-manifest verification, certification/provenance suite |

The files above are the intended first migration surface, not permission to move fields mechanically. A field moves only when its responsibility is supported by the source and existing FDF/campaign evidence. Existing campaign execution/profile schema, CLI pointer, scientific math and freeze-history formats remain compatible unless a test-backed necessity and explicit version boundary are established.

## Stop conditions and decision log

Stop and report if an implementation requires changing scientific formulas, BARE/SCREENED semantics, matrix conventions, certification math, thresholds/tolerances, V6 U values/intervals/labels/observables/projectors/physical inputs; if V6 artifacts would need edits; if a v2 migration cannot be determined from explicit repository data; or if two materially incompatible public schema/API designs remain equally defensible. Do not resolve such a condition by silently guessing or weakening qualification.

**Decision from current evidence:** v2 functional is explicit, versioned identifiers are established, and backend profile identity is separately represented. The inventory supports the migration and ownership decisions above; no open scientific ambiguity blocks Phase III. Implementation must still verify all call sites and API compatibility before landing changes.

## Phase gate results in the authorized active worktree

| Phase | Current state | Evidence/remaining gate |
|---|---|---|
| I: inventory | Complete | Coupling sites were mapped to source and the proposed edit scope excludes frozen reports, certificates, inputs, and run records. |
| II: architecture and migration plan | Complete | v2 readers migrate only from their explicit `functional`; XC and SIESTA backend profiles remain separate. |
| III: explicit XC profile | Complete | Typed/versioned PBE profile and schema added; absent functional is rejected; declared-only XC profiles cannot enter the qualified LR-U path. |
| IV: material defaults | Complete | FDF builder requires target species and method-2 projector values; active callers and fixtures provide those values explicitly. |
| V: single source and backend boundary | Complete | Campaign admission checks explicit profile consistency; response-grid domain code receives source-context and response-cell adapters, with SIESTA text semantics owned by the backend. |
| VI: regression, static audit, tests | Complete with checkout limitations | Supported Python 3.12 / NumPy 1.26.4 focused suite: 147 passed, 1 skipped, plus 3 targeted FDF decoupling regressions passed. Broad suite: 671 passed, 24 skipped, 20 failed, 5 collection errors; all remaining outcomes are classified as preexisting missing fixtures or the absent legacy namespace. The V6 manifest/tag audit found no changed blobs or worktree overlap; one old source path is absent from current HEAD after namespace migration but remains in the freeze tag. |
| VII: documentation and final verification | Complete with limitations stated | See `SCIENTIFIC_DECOUPLING_VERIFICATION.md`. No SIESTA was run; provenance gaps remain explicitly partial and unresolved. |

The broad-suite fixture failures and dependency-environment detail are recorded in the verification report. They were not hidden by weakening assertions, fabricating campaign artifacts, or modifying frozen V6 evidence.
