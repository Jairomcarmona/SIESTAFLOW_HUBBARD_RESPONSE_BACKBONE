# Inventory of Large Versioned Artifacts

Read-only inventory generated for TASK 25b. No files under `results/` or
`validation_observables_v6/` were modified. Sizes in bytes were read from the
working tree; all 48 artifacts were present.

## Scope and test usage

- Matches: 48 files, 91,897,925 bytes (91.898 decimal MB). Types: .bands: 7, .hsx: 6, .psml: 18, siesta.out: 17.
- Exact path references in `tests/` files: 0.
- Filename appears without proving a link to this specific artifact: 25. This is common for `siesta.out`, a generic filename shared by tests.
- No textual match in scanned files: 23. The search was textual and does not prove that a test does not access an artifact indirectly through a glob, parameterized fixture, or constructed path.
- Method: files tracked by `git ls-files results validation_observables_v6`; text search within `tests/` (`.py`, `.json`, `.md`, `.txt`, `.yaml`, `.yml`). A basename match is not counted as confirmed usage.

## Files

| Path | Bytes | Type | Text reference in tests | Test file(s) found |
|---|---:|---|---|---|
| `results/stage-ub-v6-observables/nio-bands-dft-prepared/NIO_PBE_REFERENCE.bands` | 475600 | `.bands` | no textual match | — |
| `results/stage-ub-v6-observables/nio-bands-dft-prepared/siesta.out` | 436876 | `siesta.out` | generic filename only; link to this specific artifact unverified | tests/fixtures/lr06_siesta542_yoltla_extract.txt, tests/integration/test_runner_replay_mno_ts.py, tests/integration/test_runner_replay_nio_p5.py, tests/unit/test_bare_semantics_evidence.py (+19) |
| `results/stage-ub-v6-observables/nio-bands-dft_lru-prepared/NIO_PBE_REFERENCE.bands` | 475600 | `.bands` | no textual match | — |
| `results/stage-ub-v6-observables/nio-bands-dft_lru-prepared/siesta.out` | 439191 | `siesta.out` | generic filename only; link to this specific artifact unverified | tests/fixtures/lr06_siesta542_yoltla_extract.txt, tests/integration/test_runner_replay_mno_ts.py, tests/integration/test_runner_replay_nio_p5.py, tests/unit/test_bare_semantics_evidence.py (+19) |
| `results/stage-ub-v6-observables/nio-full-bz-gap-search/16x32x32-dft/NIO_PBE_REFERENCE.bands` | 32505973 | `.bands` | no textual match | — |
| `results/stage-ub-v6-observables/nio-full-bz-gap-search/16x32x32-dft/siesta.out` | 23061295 | `siesta.out` | generic filename only; link to this specific artifact unverified | tests/fixtures/lr06_siesta542_yoltla_extract.txt, tests/integration/test_runner_replay_mno_ts.py, tests/integration/test_runner_replay_nio_p5.py, tests/unit/test_bare_semantics_evidence.py (+19) |
| `results/stage-ub-v6-observables/nio-full-bz-gap-search/4x8x8-dft/NIO_PBE_REFERENCE.bands` | 508021 | `.bands` | no textual match | — |
| `results/stage-ub-v6-observables/nio-full-bz-gap-search/4x8x8-dft/siesta.out` | 409712 | `siesta.out` | generic filename only; link to this specific artifact unverified | tests/fixtures/lr06_siesta542_yoltla_extract.txt, tests/integration/test_runner_replay_mno_ts.py, tests/integration/test_runner_replay_nio_p5.py, tests/unit/test_bare_semantics_evidence.py (+19) |
| `results/stage-ub-v6-observables/nio-full-bz-gap-search/4x8x8-dft_lru/NIO_PBE_REFERENCE.bands` | 508021 | `.bands` | no textual match | — |
| `results/stage-ub-v6-observables/nio-full-bz-gap-search/4x8x8-dft_lru/siesta.out` | 410596 | `siesta.out` | generic filename only; link to this specific artifact unverified | tests/fixtures/lr06_siesta542_yoltla_extract.txt, tests/integration/test_runner_replay_mno_ts.py, tests/integration/test_runner_replay_nio_p5.py, tests/unit/test_bare_semantics_evidence.py (+19) |
| `results/stage-ub-v6-observables/nio-full-bz-gap-search/8x16x16-dft/NIO_PBE_REFERENCE.bands` | 4063349 | `.bands` | no textual match | — |
| `results/stage-ub-v6-observables/nio-full-bz-gap-search/8x16x16-dft/siesta.out` | 2926938 | `siesta.out` | generic filename only; link to this specific artifact unverified | tests/fixtures/lr06_siesta542_yoltla_extract.txt, tests/integration/test_runner_replay_mno_ts.py, tests/integration/test_runner_replay_nio_p5.py, tests/unit/test_bare_semantics_evidence.py (+19) |
| `results/stage-ub-v6-observables/nio-full-bz-gap-search/8x16x16-dft_lru/NIO_PBE_REFERENCE.bands` | 4063349 | `.bands` | no textual match | — |
| `results/stage-ub-v6-observables/nio-full-bz-gap-search/8x16x16-dft_lru/siesta.out` | 2927266 | `siesta.out` | generic filename only; link to this specific artifact unverified | tests/fixtures/lr06_siesta542_yoltla_extract.txt, tests/integration/test_runner_replay_mno_ts.py, tests/integration/test_runner_replay_nio_p5.py, tests/unit/test_bare_semantics_evidence.py (+19) |
| `results/stage-ub-v6-observables/run-records/feo-dft-lru-continuation-25pct/siesta.out` | 111335 | `siesta.out` | generic filename only; link to this specific artifact unverified | tests/fixtures/lr06_siesta542_yoltla_extract.txt, tests/integration/test_runner_replay_mno_ts.py, tests/integration/test_runner_replay_nio_p5.py, tests/unit/test_bare_semantics_evidence.py (+19) |
| `results/stage-ub-v6-observables/run-records/feo-dft_lru-mix001-both/siesta.out` | 118847 | `siesta.out` | generic filename only; link to this specific artifact unverified | tests/fixtures/lr06_siesta542_yoltla_extract.txt, tests/integration/test_runner_replay_mno_ts.py, tests/integration/test_runner_replay_nio_p5.py, tests/unit/test_bare_semantics_evidence.py (+19) |
| `results/stage-ub-v6-observables/run-records/feo-dft_lru-seedDM/siesta.out` | 122339 | `siesta.out` | generic filename only; link to this specific artifact unverified | tests/fixtures/lr06_siesta542_yoltla_extract.txt, tests/integration/test_runner_replay_mno_ts.py, tests/integration/test_runner_replay_nio_p5.py, tests/unit/test_bare_semantics_evidence.py (+19) |
| `results/stage-ub-v6-observables/run-records/feo-dft_lru/siesta.out` | 113171 | `siesta.out` | generic filename only; link to this specific artifact unverified | tests/fixtures/lr06_siesta542_yoltla_extract.txt, tests/integration/test_runner_replay_mno_ts.py, tests/integration/test_runner_replay_nio_p5.py, tests/unit/test_bare_semantics_evidence.py (+19) |
| `validation_observables_v6/coo/pbe/COOPBE.HSX` | 4057080 | `.hsx` | no textual match | — |
| `validation_observables_v6/coo/pbe/CoLR0.psml` | 86808 | `.psml` | generic filename only; link to this specific artifact unverified | tests/unit/test_campaign_split.py, tests/unit/test_semantic_species_split.py |
| `validation_observables_v6/coo/pbe/CoLR1.psml` | 86808 | `.psml` | no textual match | — |
| `validation_observables_v6/coo/pbe/O.psml` | 80687 | `.psml` | generic filename only; link to this specific artifact unverified | tests/integration/test_runner_replay_mno_ts.py, tests/unit/test_campaign_production.py, tests/unit/test_convergence_engine.py, tests/unit/test_fdf_model.py (+8) |
| `validation_observables_v6/coo/pbe/siesta.out` | 53337 | `siesta.out` | generic filename only; link to this specific artifact unverified | tests/fixtures/lr06_siesta542_yoltla_extract.txt, tests/integration/test_runner_replay_mno_ts.py, tests/integration/test_runner_replay_nio_p5.py, tests/unit/test_bare_semantics_evidence.py (+19) |
| `validation_observables_v6/coo/pbe_lru/COOLRU.HSX` | 4057080 | `.hsx` | no textual match | — |
| `validation_observables_v6/coo/pbe_lru/CoLR0.psml` | 86808 | `.psml` | generic filename only; link to this specific artifact unverified | tests/unit/test_campaign_split.py, tests/unit/test_semantic_species_split.py |
| `validation_observables_v6/coo/pbe_lru/CoLR1.psml` | 86808 | `.psml` | no textual match | — |
| `validation_observables_v6/coo/pbe_lru/O.psml` | 80687 | `.psml` | generic filename only; link to this specific artifact unverified | tests/integration/test_runner_replay_mno_ts.py, tests/unit/test_campaign_production.py, tests/unit/test_convergence_engine.py, tests/unit/test_fdf_model.py (+8) |
| `validation_observables_v6/coo/pbe_lru/siesta.out` | 76602 | `siesta.out` | generic filename only; link to this specific artifact unverified | tests/fixtures/lr06_siesta542_yoltla_extract.txt, tests/integration/test_runner_replay_mno_ts.py, tests/integration/test_runner_replay_nio_p5.py, tests/unit/test_bare_semantics_evidence.py (+19) |
| `validation_observables_v6/mno/lru_central/MNCL.HSX` | 2053720 | `.hsx` | no textual match | — |
| `validation_observables_v6/mno/lru_central/MnLR0.psml` | 87061 | `.psml` | no textual match | — |
| `validation_observables_v6/mno/lru_central/MnLR1.psml` | 87061 | `.psml` | no textual match | — |
| `validation_observables_v6/mno/lru_central/O.psml` | 80687 | `.psml` | generic filename only; link to this specific artifact unverified | tests/integration/test_runner_replay_mno_ts.py, tests/unit/test_campaign_production.py, tests/unit/test_convergence_engine.py, tests/unit/test_fdf_model.py (+8) |
| `validation_observables_v6/mno/lru_central/siesta.out` | 51695 | `siesta.out` | generic filename only; link to this specific artifact unverified | tests/fixtures/lr06_siesta542_yoltla_extract.txt, tests/integration/test_runner_replay_mno_ts.py, tests/integration/test_runner_replay_nio_p5.py, tests/unit/test_bare_semantics_evidence.py (+19) |
| `validation_observables_v6/mno/lru_high/MNHI.HSX` | 2053720 | `.hsx` | no textual match | — |
| `validation_observables_v6/mno/lru_high/MnLR0.psml` | 87061 | `.psml` | no textual match | — |
| `validation_observables_v6/mno/lru_high/MnLR1.psml` | 87061 | `.psml` | no textual match | — |
| `validation_observables_v6/mno/lru_high/O.psml` | 80687 | `.psml` | generic filename only; link to this specific artifact unverified | tests/integration/test_runner_replay_mno_ts.py, tests/unit/test_campaign_production.py, tests/unit/test_convergence_engine.py, tests/unit/test_fdf_model.py (+8) |
| `validation_observables_v6/mno/lru_high/siesta.out` | 50017 | `siesta.out` | generic filename only; link to this specific artifact unverified | tests/fixtures/lr06_siesta542_yoltla_extract.txt, tests/integration/test_runner_replay_mno_ts.py, tests/integration/test_runner_replay_nio_p5.py, tests/unit/test_bare_semantics_evidence.py (+19) |
| `validation_observables_v6/mno/lru_low/MNLO.HSX` | 2053720 | `.hsx` | no textual match | — |
| `validation_observables_v6/mno/lru_low/MnLR0.psml` | 87061 | `.psml` | no textual match | — |
| `validation_observables_v6/mno/lru_low/MnLR1.psml` | 87061 | `.psml` | no textual match | — |
| `validation_observables_v6/mno/lru_low/O.psml` | 80687 | `.psml` | generic filename only; link to this specific artifact unverified | tests/integration/test_runner_replay_mno_ts.py, tests/unit/test_campaign_production.py, tests/unit/test_convergence_engine.py, tests/unit/test_fdf_model.py (+8) |
| `validation_observables_v6/mno/lru_low/siesta.out` | 50014 | `siesta.out` | generic filename only; link to this specific artifact unverified | tests/fixtures/lr06_siesta542_yoltla_extract.txt, tests/integration/test_runner_replay_mno_ts.py, tests/integration/test_runner_replay_nio_p5.py, tests/unit/test_bare_semantics_evidence.py (+19) |
| `validation_observables_v6/mno/pbe/MNO_PBE_REFERENCE.HSX` | 2053720 | `.hsx` | no textual match | — |
| `validation_observables_v6/mno/pbe/MnLR0.psml` | 87061 | `.psml` | no textual match | — |
| `validation_observables_v6/mno/pbe/MnLR1.psml` | 87061 | `.psml` | no textual match | — |
| `validation_observables_v6/mno/pbe/O.psml` | 80687 | `.psml` | generic filename only; link to this specific artifact unverified | tests/integration/test_runner_replay_mno_ts.py, tests/unit/test_campaign_production.py, tests/unit/test_convergence_engine.py, tests/unit/test_fdf_model.py (+8) |
| `validation_observables_v6/mno/pbe/siesta.out` | 81899 | `siesta.out` | generic filename only; link to this specific artifact unverified | tests/fixtures/lr06_siesta542_yoltla_extract.txt, tests/integration/test_runner_replay_mno_ts.py, tests/integration/test_runner_replay_nio_p5.py, tests/unit/test_bare_semantics_evidence.py (+19) |

## Proposed policy

- Keep small, trimmed Git fixtures sufficient for regression, with documented provenance.
- Keep complete SIESTA outputs, `.HSX`, `.bands`, and large datasets outside the source repository; distribute them as release assets or in an archive with a DOI, manifest, and checksums.
- Do not delete or rewrite the inventoried historical artifacts. Any future migration requires explicit review of consumers and an archive-preservation plan.
- This proposal does not change the integrity of the V6 scientific baseline or authorize changes to frozen paths.
