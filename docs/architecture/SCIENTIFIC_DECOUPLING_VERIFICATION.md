# Scientific configuration decoupling verification

**Disposition:** Phase I–VII gates complete, with repository-fixture limitations recorded.

**Worktree:** `C:/Users/Jairo/.codex/worktrees/hubbardflow-v6-freeze/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0`

**Branch:** `codex/hubbardflow-rename`

**Tested source base before finalization commit:** `397da82abd14512beb3c99cbb7eac576bbe77c10`

**Frozen oracle:** `scientific-v6-final` → `45cb53c5a98d9d55a163c05ca3b815a8ff9cfb7f`

## Implemented boundaries

- `domain/scientific_profile.py` defines the typed, versioned XC profile. PBE is qualified only by the explicit `hubbardflow.v6.pbe-reference@1` profile bound to `scientific-v6-final`; other recognized XC declarations remain `DECLARED_UNVALIDATED` and fail LR-U qualification.
- `schemas/xc_profile.v1.schema.json` defines the profile record. Campaign/config v2 identifiers remain unchanged. Legacy v2 migration requires the existing explicit `functional`; a missing declaration is an error, and a supplied `xc_profile` must agree with it.
- The XC profile is separate from the SIESTA backend `scientific_profile`. Campaign admission checks their applicable declarations and records the XC profile in generated campaign and analysis provenance.
- `LRScientificConfiguration` now requires explicit XC profile, projector, PAO, spin, alpha-grid, and response-fit configuration. Its configuration/reuse identities include the XC profile.
- FDF construction no longer supplies Mn, 3d projector, radius, omega, target-species, or split-prefix fallbacks. Material and projector inputs must come from callers.
- `siesta_backend/response_grid_semantics.py` owns SIESTA-specific FDF projector parsing, BARE/SCREENED event selection, and occupation precision. `execution/response_grid_context.py` reconstructs campaign context. The domain validator accepts injected adapters and no longer imports backend or execution modules.
- Numerical response and certification formulas, BARE/SCREENED meaning, conventions, thresholds, tolerances, rounding, V6 inputs, results, and qualification labels were not changed.

The active implementation remains SIESTA-specific where the input/output and execution contracts are SIESTA-specific. This work does not claim backend independence.

## Verification

Finalization used an isolated Python 3.12.13 environment with NumPy 1.26.4, jsonschema 4.26.0, and pytest 9.1.1. NumPy 1.26.4 satisfies the declared `numpy>=1.20.0,<2.0.0` constraint. The environment was installed from the current project metadata with `uv pip`; no dependency constraint or lockfile was changed. `uv sync --locked` is currently unavailable because the checked-in lock describes the prior `siestaflow-hubbard` 0.1.0 distribution and does not match the current `hubbardflow` 0.1.2 project metadata.

Focused decoupling regression suite:

```text
147 passed, 1 skipped
```

The three FDF-builder decoupling regressions colocated in `tests/unit/test_mno_independent_audit_regressions.py` were run by exact test ID and passed (3/3). Thus `FOCUSED_REGRESSION=PASS` and `DECOUPLING_REGRESSIONS=0`.

Broad suite, including collection errors rather than excluding those modules:

```text
715 collected, 5 collection errors
671 passed, 24 skipped, 20 failed
```

### Failure-classification appendix

| Classification | Count | Items and cause |
|---|---:|---|
| `DECOUPLING_REGRESSION` | 0 | No failures in the focused decoupling suite or the three targeted FDF-builder regressions. |
| `PREEXISTING_MISSING_FIXTURE` | 14 outcomes (12 failures, 2 collection errors) | Failures: `tests/test_cli_and_manifest.py::test_cli_audit_fdf_reports_repository_nio_pbe_spin_and_dftu` (missing NiO reference FDF); `tests/unit/test_cu1_archived_occupation_v3.py::test_archived_cu1_occupations_v3_builds_verified_dataset_without_authorizing_u` (missing archived artifact manifest); `tests/unit/test_cu3n_symmetry_shadow_package.py::test_fdf_mutation_changes_only_the_declared_target_shift` (missing shadow FDF); all three tests in `tests/unit/test_cu_one_atom_noise_calibrated_campaign.py` (missing campaign lock files); all six cases in `tests/unit/test_fdf_symmetry_adapter.py` (missing NiO/MnO/FeO/Cu3N FDFs); collection of `tests/test_nio_polynomial_analysis.py` (missing `campaigns/nio_afmii_four_atom_lru_v2_20260926/scripts/analyze_nio_lru_v3.py`); collection of `tests/test_nio_shared_lru_regression.py` (missing `lru_core.py`). |
| `PREEXISTING_MISSING_OPTIONAL_DEPENDENCY` | 11 outcomes (8 failures, 3 collection errors) | Current supported environment installs `hubbardflow`, not the absent legacy `siestaflow_hubbard` namespace referenced by archived scripts. Failures: `tests/test_hubbard_parameter_semantics.py::test_scalar_charge_result_cannot_feed_dudarev_input`, `::test_physical_fdf_replaces_the_saved_u_entry_with_explicit_ueff`; `tests/unit/test_mno_foreground_preflight.py::test_mno_preflight_reuses_canonical_foreground_slurm_contract`; five import-dependent cases in `tests/unit/test_mno_independent_audit_regressions.py` (the three SCREENED reanalysis rejection tests, archived-value check, and quantized-analysis test). Collection errors: `tests/adversarial/test_method2_reference.py`, `tests/adversarial/test_phase4_alpha0_control.py`, and `tests/unit/test_stage_ub_baseline_summary.py`, each blocked by the same absent namespace. |
| `ENVIRONMENT_ERROR` | 0 test outcomes | The NumPy 2.4.6 interpreter was not used for acceptance. The stale `uv.lock` prevented `uv sync --locked`, so the supported environment was installed directly from unchanged `pyproject.toml` constraints. |
| `UNKNOWN` | 0 | All broad-suite failures and collection errors above have a specific missing fixture or legacy namespace cause. |

Missing fixtures and the legacy namespace were not reconstructed, restored, or used to weaken/delete tests. These failures are outside the decoupling surface; their importing scripts/tests are unchanged by this work.

The focused tests imported and exercised changed code; AST/import checks and `git diff --check` passed. The static dependency scan found no imports from `hubbardflow.execution` or `hubbardflow.siesta_backend` in `src/hubbardflow/domain`. Remaining material names in reusable source are comments/docstrings or fixture descriptions, not material-keyed algorithm branches. PBE family identity and aliases are centralized in `domain/scientific_profile.py`.

## Frozen V6 integrity and provenance

The read-only artifact audit used `docs/history/SCIENTIFIC_BASELINE_V6.sha256` and Git object trees:

```text
manifest entries = 484
missing from scientific-v6-final = 0
tag/HEAD blob mismatches on shared paths = 0
working-tree SHA-256 mismatches among present manifest files = 0
working-tree status overlaps with manifest paths = 0
```

One manifest path, `src/siestaflow_hubbard/execution/u_certification_node.py`, is absent from current HEAD after the project namespace migration. It is present in `scientific-v6-final`; its frozen blob SHA-256 is `C991E0C95CAC2687237A7636E9F4F76B9ABC386F3CE91DDFDA1606FD2461DA9F`. The active source is now `src/hubbardflow/execution/u_certification_node.py`, with SHA-256 `5907DA0D5076758D4112CFE8ECA45062D88BEA08BD729FB781466C3D0C70E0CE` at verification time. That current implementation identity is distinct from the freeze snapshot and is not attributed as the certificate generator.

The two existing historical gaps remain visible and unresolved:

1. CoO/MnO superseding V2 certificates record historical generator SHA-256 `611c8ff2b42349bfd4c6a16b56a265bb22553be64489a1f3edcecc227abf1184`; that source is unavailable. The current implementation is not represented as its generator.
2. V6 reports record Git SHA `03ccd5913abdc6dd0e9e2cb59c0bc7637562c267`, absent from the repository. The existing `stage-ub-v6-20260930` tag targets `03ccd5913abdc6dd0e9a2cb59c0bc7637562c267`; equivalence is not established.

Neither provenance gap was rewritten or upgraded to full historical-source reproducibility. No frozen certificate, report, run record, input, result, or tag was modified. The `scientific-v6-final` tag remains at `45cb53c5a98d9d55a163c05ca3b815a8ff9cfb7f`.

## Scope and final state

- No SIESTA calculation or campaign node was launched.
- No U, observable, or scientific result was recomputed.
- No formula, scientific threshold, V6 qualification, or physical input changed.
- Only active non-frozen source, tests, schema, and architecture documentation in the isolated worktree were changed.
- No J/V implementation, alternate electronic-structure engine, or product/JOSS consolidation was started.

**Result:** scientific configuration decoupling is implemented and verified to the extent supported by this checkout. The focused suite is green; complete historical fixture coverage remains unavailable and is explicitly reported above.
