# TASK 22 — log de premisas, ediciones y gates

## Base y rama

- `git fetch` → avanzó `origin/codex/hubbardflow-rename` desde `041adf8` a `299b8f0db44ba385c36d7b0fcef54639f1bcffb7`.
- `git rev-parse codex/hubbardflow-rename` → `241d009b92d39519b9a308284c783add94849625` (premisa falsa solo para la referencia local; se registra en `BLOCKERS.md`).
- `git rev-parse origin/codex/hubbardflow-rename` y `git show -s --format='%H%n%s' 299b8f0` → `299b8f0db44ba385c36d7b0fcef54639f1bcffb7`, merge del PR #8. La rama TASK 22 se creó directamente desde ese commit verificado.
- El commit documental inicial `3c0b8ca` contiene solo la copia de la especificación y `AMENDMENTS_2.md`. La fuente y copia de `CODEX_TASK22_I5.md` coincidieron por SHA-256 `C751DC106DFBB9BB99D2B54870FE4386668B5E4E367C096E9E51FBA5D1B82B79`.

## Gates de línea base posteriores al commit documental

- `python -m pytest tests/unit/test_phase2_golden.py -q` → `4 passed`.
- `python -m pytest tests/unit/test_product_cli.py tests/unit/test_product_execution.py tests/unit/test_product_admission.py tests/unit/test_product_paths.py tests/unit/test_campaign_plan.py -q` → `109 passed`.
- 70 regresiones científicas (`test_lr_analysis_v2.py`, `test_matrix_lr.py`, `test_quantized_response.py`, `test_u_certification.py`) → `70 passed`.
- `python -m pytest -q tests/unit/test_import_architecture.py` → `8 passed`.
- `python -m pytest tests -q -rfE --continue-on-collection-errors` → `1367 passed, 25 skipped, 20 xfailed, 4 subtests passed`; sin errores activos ni errores de colección.
- `ruff check .` → `All checks passed!`; `ruff format --check .` → `91 files already formatted`; `MYPYPATH=src mypy` → `Success: no issues found in 91 source files`; `bash tools/check_v6_integrity.sh` → `V6 GATE OK`.
- Replay POSIX en WSL, con `PYTHONPATH=src python -m pytest tests/integration/test_runner_replay_nio_p5.py -q` → `7 passed` en 11.46 s. La primera invocación sin `PYTHONPATH=src` no importó el paquete; se repitió con el entorno correcto y pasó.

## 22.1 — premisas verificadas

| Premisa | Comando ejecutado | Resultado |
|---|---|---|
| `_failed_receipt` guarda solo digest; si stdout va a archivo `CompletedProcess.stdout` queda vacío | `Get-Content src/hubbardflow/execution/runtime_adapters.py | Select-Object -First 150` | La función original construía `NodeReceipt(node_id, FAILED_EXECUTION, digest)`; `run` redirigía a handles y activaba `capture_output` solo si ambos faltaban. |
| El runner acepta `extra` y el store lo mezcla en el registro del nodo | `Get-Content src/hubbardflow/execution/campaign_store.py | Select-Object -Skip 74 -First 18` | `**dict(extra or {})` en el record. |
| `status` imprime `campaign_status` y el estado del worker es el objeto de salida | `Select-String -Path src/hubbardflow/cli.py -Pattern 'campaign_status\|worker-state' -Context 2,4` | El comando `status` hace `json.dumps(campaign_status(...))`; `campaign_status` carga `.siestaflow/worker-state.json`. |
| Fallo de ejecución finaliza heartbeat con estado FAILED | `Select-String -Path src/hubbardflow/execution/campaign_runner.py -Pattern 'heartbeat.finish' -Context 2,5` | Camino de nodo fallido finaliza `heartbeat.finish("FAILED", failed_node=..., failure_state=...)`. |

Cambios de prueba de 22.1: se extendió `tests/unit/test_runtime_adapters.py` para salida 3 (`EXIT`), señal directa SIGTERM (`SIGNAL:SIGTERM`), script launcher con 143 (`PROBABLE_SIGNAL:SIGTERM`), OSError sintético (`SYNTHETIC_OSERROR`), código 255 (`EXIT`), colas stdout/stderr limitadas a las últimas 20 líneas, argv, digest legacy bajo redirección parcial y ausencia de `failure.json` al tener éxito. En Windows se saltan los dos casos que dependen del convenio POSIX; corren en CI/WSL. Decisión conservadora: con un único stream redirigido, se captura el otro para `failure.json` y se reproduce en el stream padre tras finalizar el proceso. El digest y el objeto del validador conservan los campos históricos; solo cambia el momento/intercalado de ese output diagnóstico.

Gates dirigidos antes del commit: `python -m pytest tests/unit/test_runtime_adapters.py -q` en Windows → `6 passed, 2 skipped`; en WSL POSIX → `8 passed`; `ruff format --check` en los archivos nuevos/editados → pasa; `ruff check` de imports/tipos no usados → pasa; `MYPYPATH=src mypy --strict src/hubbardflow/execution/runtime_adapters.py` → `Success: no issues found in 1 source file`.

## 22.2 — premisas verificadas

- `Select-String` y lectura de `campaign_plan.py` confirmaron `planner_version="campaign-planner-v3"` en la planificación.
- `verify_frozen_campaign_plan` leía `resolved_perturbation_plan.json`, llamaba `from_mapping` y recomputaba el plan dentro del mismo `try`; el `except` convertía el error a `cannot resume frozen campaign plan: ...`.
- La prueba de alteración a `campaign-planner-v2` se añadirá con el ítem 22.2.

## 22.3 — premisas verificadas con NiO P5 real

- WSL comprobó 25 salidas y 25 `.EIG` en `~/.local/state/siestaflow/campaigns/nio_p5_product_2/.siestaflow/attempts`: 1 referencia, 12 BARE, 12 SCREENED.
- Auditoría de lectura con los selectores actuales sobre las 24 corridas: cada selección corresponde a un evento del parser; dos átomos, matrices up/down simétricas y 25 filas por átomo con cinco decimales. Resultado: `{'bare': 12, 'screened': 12, 'reference': 1}`.
- `campaign_runner.py` y `observation_assembly.py` usan `bare_profile.select_response(...).response_event` y `select_converged_screened_event(...)`, los mismos selectores que se usarán para la evidencia y la observación de U.
- `grep` sobre la salida real mostró bloques `Occupations:`, `Mulliken Atomic Populations:` y `siesta: Fermi = -4.508514`; el parser de momentos lee la última tabla Mulliken completa.
- El formato `.EIG` se leyó de una corrida real: primera línea Fermi; segunda línea `64 2 23` (k, espín, bandas); las energías se imprimen en notación `E` con nueve decimales de mantisa (`1e-9 eV`). Ejemplos literales están en la sección de premisas 22.3 de la ejecución final.
- `find tests/fixtures/replay_nio_p5 -name '*.EIG'` → `0`; replay espera G4 `NOT_AVAILABLE`.


POSIX específicos de 22.1 en WSL: `PYTHONPATH=src python -m pytest tests/unit/test_runtime_adapters.py -q` → `8 passed` (incluye SIGTERM directo y launcher 143).
