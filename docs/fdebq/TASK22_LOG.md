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
- El formato `.EIG` se leyó de corridas reales y se validó contra sus bloques: la segunda línea `64 2 23` significa **64 bandas, 2 espines, 23 puntos k**; cada punto contiene `64 × 2 = 128` energías. Las energías se imprimen con nueve decimales de mantisa, por lo que el quantum absoluto depende del exponente (`10^(exponente−9) eV`), no es siempre `1e-9 eV`.
- `find tests/fixtures/replay_nio_p5 -name '*.EIG'` → `0`; replay espera G4 `NOT_AVAILABLE`.

Tres líneas literales del `.EIG` de referencia:

```text
 -0.452324875E+01
         64 2         23
         1  -0.108718534E+03  -0.107059529E+03  -0.691704785E+02  -0.691578668E+02  -0.691460532E+02  -0.674318434E+02  -0.674274514E+02  -0.674117503E+02  -0.240555051E+02  -0.232498013E+02
```

### 22.3 — re-verificación ejecutada

| Premisa | Comando real | Resultado |
|---|---|---|
| Cada átomo del evento seleccionado tiene 25 filas simétricas up/down con cinco decimales | WSL: lector sobre las 25 salidas de `nio_p5_product_2`, usando `parse_hubbard_population_events` y los selectores BARE/SCREENED; cuenta bloques/filas y compara matrices transpuestas | 1 referencia, 12 BARE, 12 SCREENED; cada evento seleccionado tiene 2 átomos, 25 filas por átomo, matrices simétricas. |
| El evento de evidencia coincide con el evento de U | `rg -n 'select_response|select_converged_screened_event' src/hubbardflow/execution/campaign_runner.py src/hubbardflow/execution/observation_assembly.py` y comparación real de rangos del selector y parser | Ambos caminos llaman al selector profile BARE y al selector SCREENED convergido; los 24 eventos seleccionados coinciden con eventos parseados. |
| Salida final contiene Mulliken, Occupations y Fermi imprimibles | WSL `grep` de `siesta.out` del producto real; `python -m pytest tests/unit/test_point_state_evidence.py -q` luego consume referencia, BARE y SCREENED reales | Tablas Mulliken, trazas `Occupations:` y `siesta: Fermi = ...` presentes. Las tres trazas de cada espín quedan a ≤`2.55e-5` de la línea impresa. |
| El layout `.EIG` declara dimensiones y permite quantum decimal | WSL `sed -n '1,12p'` del `.EIG` real; script de conteo de inicios de bloque/energías; pruebas fixture | `64 2 23` = 64 bandas × 2 espines × 23 k; 128 energías por k. El quantum se deriva por token según el exponente. |
| Referencia y dos corridas pueden probarse sin acceder a la campaña local | Compresión de referencia, BARE y SCREENED reales hacia `tests/fixtures/i5_eig/*.xz`; `python -m pytest tests/unit/test_point_state_evidence.py -q` | `6 passed`, incluye estado de referencia, BARE, SCREENED, EIG ausente, bloque de ocupaciones truncado y tabla Mulliken sin terminador. |

Decisión de dependencia para mantener compilable el ítem: `domain/state_gate.py` introduce en 22.3 únicamente los records congelados de entrada (`PointState`, `AtomPointState`, energías y disponibilidad EIG) que el parser debe retornar. La lógica de política/veredicto sigue reservada íntegramente al commit 22.4.

Fixtures reales añadidas por 22.3 en `tests/fixtures/i5_eig/`: `.EIG.xz` y el `siesta.out.xz` correspondiente para referencia, BARE +0.04 y SCREENED −0.04; se mantienen fuera de `replay_nio_p5/`. Añadir las tres salidas comprimidas es la mínima ampliación conservadora que permite probar de forma portátil los eventos seleccionados, las trazas y el Mulliken reales junto a los `.EIG`; no altera replay ni golden. El replay fixture no recibió `.EIG`.

Revisión `verificador_luna` encontró que una última tabla Mulliken sin separador de cierre podía dejar como alternativa una tabla anterior completa. Se corrigió para rechazar esa salida y se añadió la prueba `test_unterminated_final_mulliken_table_raises_typed_error`; el verificador confirmó que la corrección cierra el hallazgo y que el log registra los seis tests focales.

### Gates de 22.3 antes del commit

- Focal: `python -m pytest tests/unit/test_point_state_evidence.py -q` → `6 passed`.
- Replay POSIX en WSL: `PYTHONPATH=src python -m pytest tests/integration/test_runner_replay_nio_p5.py -q` → `7 passed`.
- Golden 20.9: `python -m pytest tests/unit/test_phase2_golden.py -q` → `4 passed`.
- Producto: CLI, ejecución, admission, paths y plan → `110 passed`.
- Regresiones científicas: los cuatro módulos de análisis/matriz/quantized/U → `70 passed`.
- Arquitectura: `8 passed`.
- Suite: `python -m pytest tests -q -rfE --continue-on-collection-errors` → `1377 passed, 27 skipped, 20 xfailed, 4 subtests passed`; sin nuevos fallos.
- `ruff check .` → `All checks passed!`; `ruff format --check .` → `91 files already formatted`; `MYPYPATH=src mypy` → `Success: no issues found in 91 source files`; `bash tools/check_v6_integrity.sh` → `V6 GATE OK`.


POSIX específicos de 22.1 en WSL: `PYTHONPATH=src python -m pytest tests/unit/test_runtime_adapters.py -q` → `8 passed` (incluye SIGTERM directo y launcher 143).

## Addendum de gates del commit 22.1 (`c397fb1`)

- 20.9 golden: `4 passed`.
- Tests de producto/campaña: `109 passed`.
- 70 regresiones científicas: `70 passed`.
- Arquitectura: `8 passed`.
- WSL replay POSIX: `7 passed`.
- Suite completa: `1370 passed, 27 skipped, 20 xfailed, 4 subtests passed`.
- `ruff check .`, `ruff format --check .`, `MYPYPATH=src mypy` y V6: todos pasan (`V6 GATE OK`).

## 22.2 — verificación previa

Comando `rg -n 'campaign-planner-v3|def verify_frozen_campaign_plan' src/hubbardflow/execution/campaign_plan.py` confirmó la versión literal `campaign-planner-v3` y la función solicitada. Lectura directa de la función confirmó que `from_mapping` y el recálculo se ejecutaban dentro del `try`, cuyo `except` convertía excepciones en `cannot resume frozen campaign plan: ...`. No se requiere ni se cambia ningún golden.

Edición autorizada añadida: `tests/unit/test_campaign_plan.py::test_resume_reports_explicit_planner_version_change` cambia solo la versión del plan congelado a `campaign-planner-v2` y exige el error literal `PLANNER_VERSION_CHANGED`, ambas versiones y la instrucción de re-inicializar. No se editaron aserciones existentes.

Verificación local del ítem: `python -m pytest tests/unit/test_campaign_plan.py -q` → `28 passed`; `MYPYPATH=src mypy --strict src/hubbardflow/execution/campaign_plan.py` → `Success: no issues found in 1 source file`.
