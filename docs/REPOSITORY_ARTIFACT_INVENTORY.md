# Inventario de artefactos pesados versionados

Inventario de solo lectura generado para TASK 25b. No se modificó ningún archivo dentro de `results/` ni `validation_observables_v6/`. Tamaños en bytes consultados en el árbol de trabajo; los 48 artefactos estaban presentes.

## Alcance y uso por pruebas

- Coincidencias: 48 archivos, 91,897,925 bytes (91.898 MB decimales). Tipos: .bands: 7, .hsx: 6, .psml: 18, siesta.out: 17.
- Referencia de ruta exacta en archivos de `tests/`: 0.
- Solo aparece el nombre de archivo sin demostrar vínculo a ese artefacto concreto: 25. Esto es común con `siesta.out`, nombre genérico compartido por las pruebas.
- Sin coincidencia textual en los archivos escaneados: 23. La búsqueda fue textual y no demuestra que una prueba no acceda indirectamente por glob, fixture parametrizado o rutas construidas.
- Método: archivos rastreados por `git ls-files results validation_observables_v6`; búsqueda textual dentro de `tests/` (`.py`, `.json`, `.md`, `.txt`, `.yaml`, `.yml`). Una coincidencia por nombre base no se cuenta como uso confirmado.

## Archivos

| Ruta | Bytes | Tipo | Referencia textual en pruebas | Archivo(s) de prueba encontrados |
|---|---:|---|---|---|
| `results/stage-ub-v6-observables/nio-bands-dft-prepared/NIO_PBE_REFERENCE.bands` | 475600 | `.bands` | sin coincidencia textual | — |
| `results/stage-ub-v6-observables/nio-bands-dft-prepared/siesta.out` | 436876 | `siesta.out` | solo nombre genérico presente; vínculo a este archivo no probado | tests/fixtures/lr06_siesta542_yoltla_extract.txt, tests/integration/test_runner_replay_mno_ts.py, tests/integration/test_runner_replay_nio_p5.py, tests/unit/test_bare_semantics_evidence.py (+19) |
| `results/stage-ub-v6-observables/nio-bands-dft_lru-prepared/NIO_PBE_REFERENCE.bands` | 475600 | `.bands` | sin coincidencia textual | — |
| `results/stage-ub-v6-observables/nio-bands-dft_lru-prepared/siesta.out` | 439191 | `siesta.out` | solo nombre genérico presente; vínculo a este archivo no probado | tests/fixtures/lr06_siesta542_yoltla_extract.txt, tests/integration/test_runner_replay_mno_ts.py, tests/integration/test_runner_replay_nio_p5.py, tests/unit/test_bare_semantics_evidence.py (+19) |
| `results/stage-ub-v6-observables/nio-full-bz-gap-search/16x32x32-dft/NIO_PBE_REFERENCE.bands` | 32505973 | `.bands` | sin coincidencia textual | — |
| `results/stage-ub-v6-observables/nio-full-bz-gap-search/16x32x32-dft/siesta.out` | 23061295 | `siesta.out` | solo nombre genérico presente; vínculo a este archivo no probado | tests/fixtures/lr06_siesta542_yoltla_extract.txt, tests/integration/test_runner_replay_mno_ts.py, tests/integration/test_runner_replay_nio_p5.py, tests/unit/test_bare_semantics_evidence.py (+19) |
| `results/stage-ub-v6-observables/nio-full-bz-gap-search/4x8x8-dft/NIO_PBE_REFERENCE.bands` | 508021 | `.bands` | sin coincidencia textual | — |
| `results/stage-ub-v6-observables/nio-full-bz-gap-search/4x8x8-dft/siesta.out` | 409712 | `siesta.out` | solo nombre genérico presente; vínculo a este archivo no probado | tests/fixtures/lr06_siesta542_yoltla_extract.txt, tests/integration/test_runner_replay_mno_ts.py, tests/integration/test_runner_replay_nio_p5.py, tests/unit/test_bare_semantics_evidence.py (+19) |
| `results/stage-ub-v6-observables/nio-full-bz-gap-search/4x8x8-dft_lru/NIO_PBE_REFERENCE.bands` | 508021 | `.bands` | sin coincidencia textual | — |
| `results/stage-ub-v6-observables/nio-full-bz-gap-search/4x8x8-dft_lru/siesta.out` | 410596 | `siesta.out` | solo nombre genérico presente; vínculo a este archivo no probado | tests/fixtures/lr06_siesta542_yoltla_extract.txt, tests/integration/test_runner_replay_mno_ts.py, tests/integration/test_runner_replay_nio_p5.py, tests/unit/test_bare_semantics_evidence.py (+19) |
| `results/stage-ub-v6-observables/nio-full-bz-gap-search/8x16x16-dft/NIO_PBE_REFERENCE.bands` | 4063349 | `.bands` | sin coincidencia textual | — |
| `results/stage-ub-v6-observables/nio-full-bz-gap-search/8x16x16-dft/siesta.out` | 2926938 | `siesta.out` | solo nombre genérico presente; vínculo a este archivo no probado | tests/fixtures/lr06_siesta542_yoltla_extract.txt, tests/integration/test_runner_replay_mno_ts.py, tests/integration/test_runner_replay_nio_p5.py, tests/unit/test_bare_semantics_evidence.py (+19) |
| `results/stage-ub-v6-observables/nio-full-bz-gap-search/8x16x16-dft_lru/NIO_PBE_REFERENCE.bands` | 4063349 | `.bands` | sin coincidencia textual | — |
| `results/stage-ub-v6-observables/nio-full-bz-gap-search/8x16x16-dft_lru/siesta.out` | 2927266 | `siesta.out` | solo nombre genérico presente; vínculo a este archivo no probado | tests/fixtures/lr06_siesta542_yoltla_extract.txt, tests/integration/test_runner_replay_mno_ts.py, tests/integration/test_runner_replay_nio_p5.py, tests/unit/test_bare_semantics_evidence.py (+19) |
| `results/stage-ub-v6-observables/run-records/feo-dft-lru-continuation-25pct/siesta.out` | 111335 | `siesta.out` | solo nombre genérico presente; vínculo a este archivo no probado | tests/fixtures/lr06_siesta542_yoltla_extract.txt, tests/integration/test_runner_replay_mno_ts.py, tests/integration/test_runner_replay_nio_p5.py, tests/unit/test_bare_semantics_evidence.py (+19) |
| `results/stage-ub-v6-observables/run-records/feo-dft_lru-mix001-both/siesta.out` | 118847 | `siesta.out` | solo nombre genérico presente; vínculo a este archivo no probado | tests/fixtures/lr06_siesta542_yoltla_extract.txt, tests/integration/test_runner_replay_mno_ts.py, tests/integration/test_runner_replay_nio_p5.py, tests/unit/test_bare_semantics_evidence.py (+19) |
| `results/stage-ub-v6-observables/run-records/feo-dft_lru-seedDM/siesta.out` | 122339 | `siesta.out` | solo nombre genérico presente; vínculo a este archivo no probado | tests/fixtures/lr06_siesta542_yoltla_extract.txt, tests/integration/test_runner_replay_mno_ts.py, tests/integration/test_runner_replay_nio_p5.py, tests/unit/test_bare_semantics_evidence.py (+19) |
| `results/stage-ub-v6-observables/run-records/feo-dft_lru/siesta.out` | 113171 | `siesta.out` | solo nombre genérico presente; vínculo a este archivo no probado | tests/fixtures/lr06_siesta542_yoltla_extract.txt, tests/integration/test_runner_replay_mno_ts.py, tests/integration/test_runner_replay_nio_p5.py, tests/unit/test_bare_semantics_evidence.py (+19) |
| `validation_observables_v6/coo/pbe/COOPBE.HSX` | 4057080 | `.hsx` | sin coincidencia textual | — |
| `validation_observables_v6/coo/pbe/CoLR0.psml` | 86808 | `.psml` | solo nombre genérico presente; vínculo a este archivo no probado | tests/unit/test_campaign_split.py, tests/unit/test_semantic_species_split.py |
| `validation_observables_v6/coo/pbe/CoLR1.psml` | 86808 | `.psml` | sin coincidencia textual | — |
| `validation_observables_v6/coo/pbe/O.psml` | 80687 | `.psml` | solo nombre genérico presente; vínculo a este archivo no probado | tests/integration/test_runner_replay_mno_ts.py, tests/unit/test_campaign_production.py, tests/unit/test_convergence_engine.py, tests/unit/test_fdf_model.py (+8) |
| `validation_observables_v6/coo/pbe/siesta.out` | 53337 | `siesta.out` | solo nombre genérico presente; vínculo a este archivo no probado | tests/fixtures/lr06_siesta542_yoltla_extract.txt, tests/integration/test_runner_replay_mno_ts.py, tests/integration/test_runner_replay_nio_p5.py, tests/unit/test_bare_semantics_evidence.py (+19) |
| `validation_observables_v6/coo/pbe_lru/COOLRU.HSX` | 4057080 | `.hsx` | sin coincidencia textual | — |
| `validation_observables_v6/coo/pbe_lru/CoLR0.psml` | 86808 | `.psml` | solo nombre genérico presente; vínculo a este archivo no probado | tests/unit/test_campaign_split.py, tests/unit/test_semantic_species_split.py |
| `validation_observables_v6/coo/pbe_lru/CoLR1.psml` | 86808 | `.psml` | sin coincidencia textual | — |
| `validation_observables_v6/coo/pbe_lru/O.psml` | 80687 | `.psml` | solo nombre genérico presente; vínculo a este archivo no probado | tests/integration/test_runner_replay_mno_ts.py, tests/unit/test_campaign_production.py, tests/unit/test_convergence_engine.py, tests/unit/test_fdf_model.py (+8) |
| `validation_observables_v6/coo/pbe_lru/siesta.out` | 76602 | `siesta.out` | solo nombre genérico presente; vínculo a este archivo no probado | tests/fixtures/lr06_siesta542_yoltla_extract.txt, tests/integration/test_runner_replay_mno_ts.py, tests/integration/test_runner_replay_nio_p5.py, tests/unit/test_bare_semantics_evidence.py (+19) |
| `validation_observables_v6/mno/lru_central/MNCL.HSX` | 2053720 | `.hsx` | sin coincidencia textual | — |
| `validation_observables_v6/mno/lru_central/MnLR0.psml` | 87061 | `.psml` | sin coincidencia textual | — |
| `validation_observables_v6/mno/lru_central/MnLR1.psml` | 87061 | `.psml` | sin coincidencia textual | — |
| `validation_observables_v6/mno/lru_central/O.psml` | 80687 | `.psml` | solo nombre genérico presente; vínculo a este archivo no probado | tests/integration/test_runner_replay_mno_ts.py, tests/unit/test_campaign_production.py, tests/unit/test_convergence_engine.py, tests/unit/test_fdf_model.py (+8) |
| `validation_observables_v6/mno/lru_central/siesta.out` | 51695 | `siesta.out` | solo nombre genérico presente; vínculo a este archivo no probado | tests/fixtures/lr06_siesta542_yoltla_extract.txt, tests/integration/test_runner_replay_mno_ts.py, tests/integration/test_runner_replay_nio_p5.py, tests/unit/test_bare_semantics_evidence.py (+19) |
| `validation_observables_v6/mno/lru_high/MNHI.HSX` | 2053720 | `.hsx` | sin coincidencia textual | — |
| `validation_observables_v6/mno/lru_high/MnLR0.psml` | 87061 | `.psml` | sin coincidencia textual | — |
| `validation_observables_v6/mno/lru_high/MnLR1.psml` | 87061 | `.psml` | sin coincidencia textual | — |
| `validation_observables_v6/mno/lru_high/O.psml` | 80687 | `.psml` | solo nombre genérico presente; vínculo a este archivo no probado | tests/integration/test_runner_replay_mno_ts.py, tests/unit/test_campaign_production.py, tests/unit/test_convergence_engine.py, tests/unit/test_fdf_model.py (+8) |
| `validation_observables_v6/mno/lru_high/siesta.out` | 50017 | `siesta.out` | solo nombre genérico presente; vínculo a este archivo no probado | tests/fixtures/lr06_siesta542_yoltla_extract.txt, tests/integration/test_runner_replay_mno_ts.py, tests/integration/test_runner_replay_nio_p5.py, tests/unit/test_bare_semantics_evidence.py (+19) |
| `validation_observables_v6/mno/lru_low/MNLO.HSX` | 2053720 | `.hsx` | sin coincidencia textual | — |
| `validation_observables_v6/mno/lru_low/MnLR0.psml` | 87061 | `.psml` | sin coincidencia textual | — |
| `validation_observables_v6/mno/lru_low/MnLR1.psml` | 87061 | `.psml` | sin coincidencia textual | — |
| `validation_observables_v6/mno/lru_low/O.psml` | 80687 | `.psml` | solo nombre genérico presente; vínculo a este archivo no probado | tests/integration/test_runner_replay_mno_ts.py, tests/unit/test_campaign_production.py, tests/unit/test_convergence_engine.py, tests/unit/test_fdf_model.py (+8) |
| `validation_observables_v6/mno/lru_low/siesta.out` | 50014 | `siesta.out` | solo nombre genérico presente; vínculo a este archivo no probado | tests/fixtures/lr06_siesta542_yoltla_extract.txt, tests/integration/test_runner_replay_mno_ts.py, tests/integration/test_runner_replay_nio_p5.py, tests/unit/test_bare_semantics_evidence.py (+19) |
| `validation_observables_v6/mno/pbe/MNO_PBE_REFERENCE.HSX` | 2053720 | `.hsx` | sin coincidencia textual | — |
| `validation_observables_v6/mno/pbe/MnLR0.psml` | 87061 | `.psml` | sin coincidencia textual | — |
| `validation_observables_v6/mno/pbe/MnLR1.psml` | 87061 | `.psml` | sin coincidencia textual | — |
| `validation_observables_v6/mno/pbe/O.psml` | 80687 | `.psml` | solo nombre genérico presente; vínculo a este archivo no probado | tests/integration/test_runner_replay_mno_ts.py, tests/unit/test_campaign_production.py, tests/unit/test_convergence_engine.py, tests/unit/test_fdf_model.py (+8) |
| `validation_observables_v6/mno/pbe/siesta.out` | 81899 | `siesta.out` | solo nombre genérico presente; vínculo a este archivo no probado | tests/fixtures/lr06_siesta542_yoltla_extract.txt, tests/integration/test_runner_replay_mno_ts.py, tests/integration/test_runner_replay_nio_p5.py, tests/unit/test_bare_semantics_evidence.py (+19) |

## Política propuesta

- Mantener en Git fixtures pequeños, recortados y suficientes para regresión, con procedencia documentada.
- Conservar salidas completas de SIESTA, `.HSX`, `.bands` y conjuntos grandes fuera del repositorio fuente; distribuirlos como release assets o en un archivo con DOI, con manifiesto y checksums.
- No borrar ni reescribir los artefactos históricos inventariados. Cualquier migración futura requiere revisión explícita de consumidores y un plan de preservación del archivo.
- Esta propuesta no cambia la integridad del baseline científico V6 ni autoriza cambios en los paths congelados.
