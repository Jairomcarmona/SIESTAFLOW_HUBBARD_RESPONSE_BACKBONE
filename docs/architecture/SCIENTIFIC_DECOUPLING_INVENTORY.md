# Scientific configuration decoupling inventory

**Status:** Phase I baseline inventory

**Inspected revision:** `397da82abd14512beb3c99cbb7eac576bbe77c10` (`codex/hubbardflow-rename`)

**Frozen oracle:** tag `scientific-v6-final`, commit `45cb53c5a98d9d55a163c05ca3b815a8ff9cfb7f`

This document records architectural coupling found in the active development tree. It does not authorize or describe a change to the scientific method. The V6 tag and all artifacts reachable from it remain immutable regression evidence.

## Scope and inspection method

The inspection followed the active scientific-decoupling goal and focused on implementation responsibility and configuration flow: campaign/config validation and loading, FDF rendering, domain configuration, response evidence parsing, analysis interfaces, tests, fixtures, and V6 history. It was a static source inspection; no SIESTA calculation or scientific result recomputation was performed.

The inventory distinguishes:
- **scientific identity and method**: XC functional/profile, response policy, projector/method semantics, and declared tolerances;
- **campaign/material data**: structure, sites, labels, pseudopotential mapping, input inventory, and selected alpha points;
- **SIESTA implementation**: FDF syntax, SIESTA version-specific response behavior, output parsing, and backend admission;
- **execution and evidence**: scheduler/runtime settings, hashes, receipts, and provenance;
- **generic analysis**: numerical response transformations and certification logic that should consume validated data without depending on a material or SIESTA text format.

## Findings

### 1. Functional identity is explicit in v2, but repeated across representations

`src/hubbardflow/execution/campaign_v2.py` defines `siestaflow.campaign.v2` and `siestaflow.lr_config.v2`, functional normalization/markers, `validate_reference_fdf`, and PSML functional checks. Campaign and LR config both carry `functional`; `campaign_runner.py` validates both against the reference FDF before running. The WSL initializer also checks its copied inputs. Therefore this path does not silently default a missing functional to PBE.

The remaining architectural issue is that a string family is duplicated across campaign JSON, LR config, FDF declarations, and pseudopotential metadata. It lacks a first-class, versioned profile identity with an explicit validation status. Current accepted family markers must not be interpreted as proof that every family has a validated Hubbard-response profile.

**Decoupling target:** make a typed/versioned XC scientific profile (`xc_profile`) the canonical declared identity; have admission validate FDF and pseudopotential declarations against it. Preserve v2 data as readable legacy input and never infer a missing v2 functional. Keep this distinct from the backend contract's SIESTA `scientific_profile` field.

### 2. The response method profile and XC profile are different responsibilities

The backend contract uses `siesta-5.4.2-potential-shift-hamiltonian-v1` for audited SIESTA response semantics. This is a SIESTA method/backend identity, not an XC identity. Keep it separate from any PBE (or other XC) profile. Do not merge either profile with execution resources or campaign/material identity.

### 3. One domain configuration combines independent concerns and scientific defaults

`src/hubbardflow/domain/convergence_engine.py::LRScientificConfiguration` combines material/site data, species and pseudopotential labels, basis and mesh, k-grid and supercell, projector settings, PAO basis settings, spin and alpha controls. It contains numeric/default values for method-2 projectors (n=3, l=2, rc=3 Bohr, omega=0.05 Bohr), PAO energy shift (0.02 Ry), split norm (0.15), split basis, and other controls. These values are meaningful method inputs, even when expressed as dataclass defaults.

**Decoupling target:** separate typed campaign/material data, XC identity, response-analysis policy, and backend/method inputs. Remove implicit scientific defaults from reusable construction paths; require explicit values at admission or preserve them through an explicitly named/versioned profile. Keep existing fixture values unchanged in the V6 semantic regression.

### 4. FDF construction has material-shaped fallback behavior

`src/hubbardflow/siesta_backend/fdf_builder.py` includes Mn-oriented fallbacks for species/projector construction and `materialize_split_species_fdf` defaults such as `target_species="Mn"` and `new_prefix="MnLR"`. The caller can omit values and receive material-specific behavior.

**Decoupling target:** make the target species, correlated labels, projector quantum numbers, radii, and generated prefix explicit inputs. FDF syntax and the SIESTA method-2 rendering remain backend responsibilities. Update active callers and tests to supply fixture data explicitly; do not alter the physical values or frozen inputs.

### 5. Generic analysis imports SIESTA-specific evidence concerns

`src/hubbardflow/domain/response_grid_reproducibility.py` reads campaign files and SIESTA-specific FDF/output evidence, and imports campaign-v2 utilities and backend selectors/precision. `src/hubbardflow/domain/lr_analysis_v2.py` consumes response-grid evidence types. This gives domain analysis a dependency on file formats and backend parsing.

**Decoupling target:** keep text parsing, version-specific occupation precision, and event selection in the SIESTA backend. Pass a validated immutable value object containing normalized observations and provenance into generic response-grid validation/analysis. Preserve the current criteria and data selection semantics.

### 6. Generic numerical kernels are already mostly material-neutral

The inspected numerical modules (`matrix_lr.py`, `lr_analysis_v2.py`, `matrix_response_acceptance.py`, `u_matrix.py`, `u_certification.py`, `quantized_response.py`, `scalar_lr.py`, `alpha_selection.py`, and `adaptive_alpha_control.py`) show no evidence of PBE/material branches governing their algorithms. MnO mentions in scalar LR and material names in tests/benchmarks are fixture provenance or test data.

**Decoupling target:** retain numerical behavior; generalize only interfaces or fixture setup that embeds material assumptions. Do not refactor equations, rounding, acceptance criteria, thresholds, or certification semantics.

### 7. Material names in fixtures are not automatically core coupling

Tests include NiO, FeO, CoO, MnO, and Cu3N campaign/reference examples. These names are legitimate scientific fixtures. A fixture is a coupling defect only if production logic selects behavior by material identity where explicit data/profile should control it.

### 8. Persisted v2 identifiers are compatibility contracts

The repository uses versioned strings including `siestaflow.campaign.v2`, `siestaflow.lr_config.v2`, and the `.siestaflow.json` pointer convention. They are persisted interface identifiers. Keep v2 readers and their meaning stable. A new representation may use a new schema version and explicit migration, but do not globally rename or reinterpret existing records.

## Responsibility map

| Concern | Owning layer after decoupling | Boundary |
|---|---|---|
| XC identity and validation status | Typed scientific profile | Does not claim unvalidated XC families are scientifically qualified |
| Campaign/material/site/pseudopotential identity | Campaign data | Contains values, not material-specific algorithm branches |
| LR response and certification policy | Generic scientific policy | Preserves formulas, event roles, thresholds, and rounding |
| FDF/PSML/output syntax and SIESTA-version semantics | SIESTA backend | Adapter emits/validates explicit profile and campaign values |
| Scheduler, MPI, paths, runtime | Execution profile | Does not set scientific method defaults |
| Hashes, receipts, source records | Evidence/provenance layer | Records identities; does not decide physical validity |
| Linear response and U analysis | Generic domain | Consumes validated immutable domain/evidence values |

## Constraints and preserved evidence

- `scientific-v6-final` and the frozen V6 artifact set are immutable.
- No SIESTA execution, U/observable recomputation, or V6 artifact regeneration is in scope.
- No change to LR-U formulas, BARE/SCREENED semantics, matrix conventions, certification mathematics, thresholds, tolerances, U values, intervals, qualification labels, observables, projectors, or physical inputs.
- The historical source hash and recorded Git SHA gaps already documented in V6 remain visible and are not repaired or reinterpreted by this work.
- The existing SIESTA backend profile remains distinct from XC identity.
- This inventory makes no claim of backend independence; the current execution and response implementation is SIESTA-specific.

## Phase I exit assessment

The repository evidence supports a concrete architecture: typed scientific profile identity; explicit campaign/material and method inputs; explicit SIESTA adapters; generic analysis over validated data; a compatibility reader for v2 that requires its already-explicit functional; and frozen V6 semantic regression. No scientific ambiguity is required to decide these boundaries. Schema/API details should be versioned during implementation and checked against the existing CLI and campaign callers before migration.

## Implementation follow-up in the active decoupling worktree

The first implementation slice follows those findings:

- `domain/scientific_profile.py` now provides a typed XC profile; only the versioned PBE reference bound to `scientific-v6-final` is LR-qualified. Other recognized families remain declared-only and are rejected for this Hubbard-response execution path.
- Campaign v2/config v2 keeps its identifiers. New records carry an additive `xc_profile`; existing records migrate only from their explicit `functional`, and a supplied profile must match. The backend contract's SIESTA `scientific_profile` remains a separate field and meaning.
- `LRScientificConfiguration` now requires an XC profile and explicit projector, PAO, spin, alpha-grid, and response-fit values; its reuse identity includes the XC profile.
- `FdfBuilder` no longer inserts Mn, 3d, rc, omega, or basis-projector defaults. Species and method-2 values are explicit at the builder boundary.
- SIESTA FDF projector syntax, BARE/SCREENED selection, and printed occupation precision were moved to `siesta_backend/response_grid_semantics.py`. Campaign-file reconstruction now lives in `execution/response_grid_context.py`; the domain validator accepts those adapters and no longer imports execution or backend modules.

These are architectural changes only. Final static, test, and V6 manifest findings are recorded in `SCIENTIFIC_DECOUPLING_VERIFICATION.md`.

## Verification disposition

The phase gates are complete. The freeze-tag evidence and its two historical provenance gaps remain unchanged. At `scientific-v6-final`, the old-path `src/siestaflow_hubbard/execution/u_certification_node.py` snapshot has SHA-256 `C991E0C95CAC2687237A7636E9F4F76B9ABC386F3CE91DDFDA1606FD2461DA9F`; the active namespace-migrated source is a separate current implementation (SHA-256 at verification time: `5907DA0D5076758D4112CFE8ECA45062D88BEA08BD729FB781466C3D0C70E0CE`). Neither identity is the unavailable historical certificate generator hash `611c8ff2b42349bfd4c6a16b56a265bb22553be64489a1f3edcecc227abf1184`.
