# HubbardFlow freeze and rename verification

## Scope and safety

This report tracks the V6 scientific freeze and the authorized repository/package rename in the dedicated worktree. Preflight found the original checkout at `C:\Users\Jairo\Downloads\SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0`, branch `codex/sync-product-20260929`, HEAD `7dafe8c828d0c5155a15bd595ce6779bdfe9c133`; it was dirty and was not modified. No SIESTA calculation was run, no PBE decoupling was started, and no unrelated architectural work was included.

The scientific freeze preserves existing V6 records and results. The subsequent rename changes project, distribution, import, and CLI branding only where compatible with the existing contracts. It does not change scientific outputs, U values, certificate metadata, qualification semantics, or historical identifiers.

## Provenance decisions carried through the rename

The freeze preserves both documented historical provenance gaps:

1. The CoO/MnO superseding V2 certificates record historical generator SHA-256 `611c8ff2b42349bfd4c6a16b56a265bb22553be64489a1f3edcecc227abf1184`, whose source is unavailable. The current tracked `u_certification_node.py` SHA-256 is `C991E0C95CAC2687237A7636E9F4F76B9ABC386F3CE91DDFDA1606FD2461DA9F`; it is not attributed as their generator.
2. V6 artifacts record Git SHA `03ccd5913abdc6dd0e9e2cb59c0bc7637562c267`, which is absent. Existing tag `stage-ub-v6-20260930` points to `03ccd5913abdc6dd0e9a2cb59c0bc7637562c267`; equivalence is not established. Neither the tag nor historical records were rewritten.

The full 18-file list and certificate hashes are in [`V6_ARTIFACT_INVENTORY.md`](V6_ARTIFACT_INVENTORY.md). Provenance coverage is partial, and the baseline is not fully historical-source-reconstructable.

## Freeze identity

```text
NEW_FREEZE_IDENTITY
  freeze_branch = codex/hubbardflow-v6-freeze
  commit_subject = freeze: scientific validation baseline V6
  tag = scientific-v6-final (annotated)
  verified_commit_sha = 45cb53c5a98d9d55a163c05ca3b815a8ff9cfb7f
  tag_target_sha = 45cb53c5a98d9d55a163c05ca3b815a8ff9cfb7f
  rename_branch = codex/hubbardflow-rename
  rename_base = 45cb53c5a98d9d55a163c05ca3b815a8ff9cfb7f
```

The new identity describes the frozen state as it exists now; it does not retroactively identify older records.

## Pre-rename identity and persisted-data handling

```text
project = SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE
distribution = siestaflow_hubbard (normalized by Python packaging as siestaflow-hubbard)
import = siestaflow_hubbard
CLI = siestaflow
```

Versioned persisted-data identifiers such as `siestaflow.campaign.v2`, `siestaflow.lr_config.v2`, `siestaflow-campaign-software-lock-v1`, and the `.siestaflow.json` pointer suffix remain stable. Frozen MnO campaign locks name the former distribution and source path; their exact old wheel and records remain unchanged. The current verifier resolves that path through the exact locked distribution without importing the old Python namespace as the active package. These identifiers are classified as `LEGACY_REFERENCE_ALLOWED` because they are stable persisted-format/provenance identities, not active project branding.

## Validation record

The 484-entry freeze manifest was verified against the staged payload before the freeze commit, but `*.sha256` is ignored and the manifest was therefore not included in the immutable tag tree. This was detected during final verification. The manifest is now retained as a tracked audit companion in this rename follow-up; a fresh blob-by-blob check against `scientific-v6-final` found 484 entries, zero missing blobs, and zero SHA-256 mismatches. All 18 artifacts carrying the absent historical Git SHA matched the original checkout byte-for-byte. The annotated `scientific-v6-final` tag resolves to the freeze commit above; the pre-existing `stage-ub-v6-20260930` tag remains at `03ccd5913abdc6dd0e9a2cb59c0bc7637562c267`. The manifest is not retroactively inserted into or used to rewrite the freeze tag.

The isolated scientific baseline preparation passed the canonical backend-contract test selection plus the FeO postprocessor regression: 94 tests passed and 4 subtests passed. A broader unfiltered pytest discovery attempt was not canonical and failed during collection on root scratch scripts, an outdated root test API, a missing archived NiO analysis script, and a missing optional module; this is a recorded unrelated collection issue. No SIESTA was run.

## Rename-phase verification

### Identity mapping and changed areas

| Previous active identity | Current identity |
|---|---|
| `SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE` | `HubbardFlow` |
| distribution `siestaflow_hubbard` | distribution `hubbardflow` |
| import namespace `siestaflow_hubbard` | import namespace `hubbardflow` |
| CLI `siestaflow` | CLI `hubbardflow` |

The package directory moved from `src/siestaflow_hubbard/` to `src/hubbardflow/`. Packaging metadata and console-script entry point are in `pyproject.toml`; active imports and references were updated across tests, examples, production benchmark helpers and tools. Active user guidance was updated in `README.md`, `docs/USER_MANUAL.md`, `docs/CLI_LOCAL_WSL_QUICKSTART.md`, and `examples/README.md`; CI source globs were updated in `.github/workflows/backend-contracts.yml`. `docs/history/PROJECT_RENAME.md` records the identity-only migration. The archived Yoltla guide remains labeled historical. Three files explicitly hashed by frozen MnO software locks were not edited.

### Legacy-name audit

The case-insensitive text scan identified 419 files containing one or more old-name tokens. Their remaining occurrences are classified as follows:

| Classification | Remaining occurrence groups | Handling |
|---|---|---|
| `HISTORICAL_FROZEN_ALLOWED` | V6 reports, run records, raw/derived scientific evidence, V6 diagnostic export, archived LR-U benchmarks and campaign records, frozen schemas/fixtures, the transferred release bundle, dated research scratch/results, historic direct-SIESTA WSL scripts, and exact source paths/tools named by frozen campaign locks | Preserved as historical or provenance-bearing content; no active identity is inferred from these names. The 18 records with the absent historical Git SHA are itemized in [`V6_ARTIFACT_INVENTORY.md`](V6_ARTIFACT_INVENTORY.md). |
| `LEGACY_REFERENCE_ALLOWED` | Versioned `siestaflow.*` / `siestaflow-*` schema IDs, `.siestaflow` campaign-control directory and `.siestaflow.json` pointer suffix, explicit old-lock compatibility handling, this rename record, the archived Yoltla guide, and the pre-existing GitHub draft-PR URL in README | Retained because these are persisted-data/provenance identifiers, explicit migration history, archived instructions, or the existing external link. They are not active project branding or a CLI alias. |
| `ACTIVE_REFERENCE_ERROR` | Active imports from `siestaflow_hubbard`, `siestaflow` CLI invocations, active distribution/import/CLI metadata, current examples and user-facing branding | **0 found.** The scoped active-code and current-guide search returned no old-namespace imports or old CLI invocations. |

SIESTA engine terminology (`SIESTA`, FDF, SIESTA adapters/parsers/restarts and SIESTA-specific DFT+U behavior) remains accurate and unchanged. The README states that HubbardFlow is independent, is not part of/maintained by/officially affiliated with the SIESTA project, and currently uses SIESTA as its electronic-structure engine.

### Verification outcomes

- **Frozen data:** [`SCIENTIFIC_BASELINE_V6.sha256`](SCIENTIFIC_BASELINE_V6.sha256) has 484 entries. Each expected SHA-256 was checked against the exact Git blob named by `scientific-v6-final`: 484 present, 0 mismatches (`FROZEN_V6_HASH_MISMATCHES=0`). The post-rename tree preserves every frozen evidence path; its sole expected path/content exception is the tracked implementation file relocated and namespace-migrated from the old package directory. The freeze tag retains the exact snapshot. The CoO/MnO certificate hashes remain unchanged. `FINAL_SIESTA_VALIDATION_REPORT_V6.md` and `validation_observables_v6/observable_validation_v6.json` retain the terminal status rows and closure flags recorded in the freeze baseline.
- **Tests:** the successful rename-phase run used `python -m pytest tests/unit/test_backend_compatibility.py tests/unit/test_backend_identity.py tests/unit/test_backend_admission.py tests/unit/test_backend_admission_plugin.py tests/unit/test_lr_campaign_contract.py tests/unit/test_siesta542_bare_profile.py tests/unit/test_siesta_output_validator.py tests/unit/test_siesta_command_factory.py tests/unit/test_siesta_production_runtime.py tests/unit/test_local_lr_gate_smoke.py tests/unit/test_symmetry_materializer.py tests/test_symmetry_reduction_proposal.py tests/unit/test_campaign_software_lock.py tests/unit/test_feo_band_postprocessor.py -q -p no:cacheprovider`; result: **97 passed, 4 subtests passed**. A repeat during final closeout could not start because the available system and bundled Python runtimes lack `pytest`; no package was installed and no test was skipped to claim a pass.
- **Import and CLI:** the successful rename-phase smoke used `PYTHONPATH=src python -c "import hubbardflow; print(hubbardflow.__file__)"`, `PYTHONPATH=src python -m hubbardflow.cli --help`, and direct dispatch of `hubbardflow.cli:main` with `--help`; all passed at that validation point. This closeout could not repeat the import/CLI smoke because the available Python runtimes lack NumPy, an imported runtime dependency. No old `siestaflow_hubbard` import shim was added.
- **Packaging:** `NOT_APPLICABLE`. The local wheel attempt reached metadata preparation but `setuptools.build_meta` was unavailable, and no cached build backend was available. No dependency download or installation and no publication was attempted.
- **Tags and identities:** `scientific-v6-final^{}` is `45cb53c5a98d9d55a163c05ca3b815a8ff9cfb7f`; `stage-ub-v6-20260930^{}` remains `03ccd5913abdc6dd0e9a2cb59c0bc7637562c267`. The historical recorded SHA `03ccd5913abdc6dd0e9e2cb59c0bc7637562c267` remains absent and not equated to the tag target. The original dirty checkout remains on its original branch and HEAD; all rename edits were made in the isolated worktree.
- **Scientific regression barrier:** no scientific values, formulas, thresholds, inputs, certificates, qualification decisions, or scientific outputs were changed. No SIESTA calculation was run. PBE decoupling, J/V work, multi-backend refactoring, remote repository rename, and consolidation were not started. `SCIENTIFIC_REGRESSION=UNCHANGED`; `READY_FOR_PBE_DECOUPLING_REVIEW=YES`.

The final rename commit is `refactor: rename project to HubbardFlow`, based directly on the verified freeze commit. Its SHA and clean-tree state are reported in the completion summary.
