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

## 22.4 — aclaraciones científicas pendientes para el autor

El auditor científico independiente revisó TASK 22 §22.4, D13a–c y las secciones I, J, K, M y O de la revisión. Antes de implementar 22.4, el autor debe resolver las dos reglas siguientes; no se modificó lógica de 22.4.

### Pregunta G2: qué margen define el k de referencia

**Texto de la especificación.** `CODEX_TASK22_I5.md:176–183` define `k` desde el espectro de referencia y pide, además de un gap único/resuelto, que “the margin ε below is < 1/2”. Pero la única fórmula de `ε`, en `:191–193`, depende de ambos `Δ_ref` y `Δ_pt`; `Δ_pt` pertenece a un punto de amplitud concreta. Luego `:184–189` vuelve a usar propiedades del punto para decidir si falla.

**Interpretaciones posibles y cambio de veredicto.**

1. Definir `k` con un margen solo de referencia, equivalente a compararla consigo misma: `ε_ref = 2·[W/(Δ_ref−2W) + W/(Δ_ref−2W)] = 4W/(Δ_ref−2W)`. Si `ε_ref < 1/2`, se fija `k`; después se evalúa el margen completo de cada par referencia–punto. En el ejemplo auditado, el punto tiene split único en el mismo índice y bases idénticas (`c=1`), pero el margen completo supera 1/2, por lo que el resultado es `SUBSPACE_AMBIGUOUS` (fallo diagnóstico).
2. Aplicar literalmente a la definición de `k` el `ε` completo que depende del punto. Con el mismo ejemplo, el requisito `ε<1/2` no define `k`; el resultado pasa a `NOT_DEFINED`, que la regla declara no-fallante. Esta lectura puede ocultar precisamente una ambigüedad del punto.

**Ejemplo numérico verificado por el auditor:** `W=2.5e−5`, `Δ_ref=0.1`, `Δ_pt=1.1e−4`, segundo gap del punto `1e−6`, bases idénticas (`c=1`). La comparación de referencia consigo misma da `ε_ref=0.00100050025`; el margen del par da `ε=0.83383358346`. Por ello las dos lecturas producen `SUBSPACE_AMBIGUOUS` frente a `NOT_DEFINED`. Evidencia de la especificación: `CODEX_TASK22_I5.md:176–193`; el cálculo está registrado en la auditoría científica independiente de TASK 22.

**Decisión requerida:** confirmar si el criterio de definición usa `ε_ref = 4W/(Δ_ref−2W)` y si un margen completo insuficiente en un punto produce `SUBSPACE_AMBIGUOUS`, o especificar otra regla.

### Pregunta G4: origen y precisión de E_F respecto a q de `.EIG`

**Texto de la especificación.** `CODEX_TASK22_I5.md:139–140` pone `E_F` en `PointState`; la premisa `:131–132` identifica el Fermi de stdout (`siesta: Fermi = ...`); pero G4 en `:202–208` compara niveles y cuenta bandas respecto al “own E_F” con umbral de un quantum de impresión `.EIG`. La especificación no dice cómo combinar la precisión, menor, del E_F de stdout con el quantum de las energías `.EIG`.

**Interpretaciones posibles y cambio de veredicto.**

1. Usar el E_F de stdout (actualmente leído por `point_state_evidence.py:244–249`) y comparar la distancia con solo `q_EIG` literal de `:203` y `:207`. Esto puede considerar resuelto un nivel que en la interpretación 2 es `BAND_COUNT_AMBIGUOUS`.
2. Usar el E_F del encabezado `.EIG` y su precisión impresa para G4; alternativamente, conservar E_F de stdout y ampliar la región ambigua para cubrir también su semiancho (`5e−7 eV` en el ejemplo). La banda fronteriza se considera `BAND_COUNT_AMBIGUOUS`, en vez de resuelta y potencialmente `PASS`/`BAND_COUNT_CHANGED`.

**Evidencia real.** En `tests/fixtures/i5_eig/bare_p0p04.EIG.xz`, la primera línea es `-0.450851397E+01` = `−4.508513970 eV`. La salida correspondiente imprime `siesta: Fermi = -4.508514` = `−4.508514 eV`; difieren `3e−8 eV`. El semiancho de la salida es `5e−7 eV`, mayor que el quantum de un eigenvalor cercano a ese E_F, `1e−8 eV`. NiO de esta corrida tiene el gap amplio; el problema afecta la interpretación en casos frontera. Ejemplo de nivel posible con formato `.EIG`, `−0.450851396E+01` = `−4.508513960 eV`, `q_EIG=1e−8`: dista `4e−8` del stdout E_F (resuelto bajo interpretación 1), pero exactamente `1e−8` del encabezado `.EIG` (ambiguo si el límite es inclusivo). Evidencia de formato y Fermi registrados en este log; el parser actual calcula distancias con stdout E_F (`point_state_evidence.py:231, 244–249`).

**Decisión requerida:** especificar si G4 toma E_F del stdout, el encabezado `.EIG`, o incluye un margen por la incertidumbre del E_F; confirmar también el tratamiento inclusivo en la frontera de un quantum.

No implementar G2/G4 ni avanzar a 22.5/22.6 hasta recibir estas respuestas del autor. La revisión también recalca que un `PASS` de TASK 22 solo certificará los controles implementados: G3 suavidad queda `NOT_ESTABLISHED` por D13a, y no se afirmarán exactitud SCF, histéresis ni consistencia energética.

### Resolución del autor y ejecución de 22.4

El autor resolvió ambas reglas en `AMENDMENTS_2.md` como R11 y R12 (commit `72539b8`). El auditor científico independiente confirmó que las resoluciones cierran las ambigüedades y que no queda bloqueo científico para 22.4.

- **R11/G2:** `k` depende solo de la referencia: `ε_ref = 4W/(Δ_ref−2W)`, junto con `Δ1−Δ2 > 4W`, `Δ1 > 4W` y `ε_ref < 1/2`; si falla, G2 es `NOT_DEFINED` para ese átomo/espín. En cada punto se evalúa el margen completo. `ε ≥ 1/2` o separación no única del punto produce `SUBSPACE_AMBIGUOUS`; con margen restante, los criterios estrictos de `c−ε > 1/2` y `c+ε < 1/2` definen PASS y `ORBITAL_ORDER_CHANGED`, y los demás casos son ambiguos. La prueba `test_r11_reference_defined_k_and_point_margin_is_ambiguous` incluye el ejemplo `W=2.5e−5`, `Δ_ref=0.1`, `Δ_pt=1.1e−4`, `c=1` y verifica `SUBSPACE_AMBIGUOUS`.
- **R12/G4:** se usa el E_F y quantum del encabezado del `.EIG`; cada eigenvalor conserva su token y quantum individual. La banda es ambigua con límite inclusivo `|ε−E_F| ≤ q(ε)/2+q(E_F)/2`. La aplicabilidad de referencia usa la misma regla. El E_F de stdout solo comprueba consistencia con tolerancia semiancho(stdout)+q(E_F EIG)/2; un exceso da `NOT_ESTABLISHED:EIG_STDOUT_FERMI_MISMATCH`. Pruebas incluidas para el ejemplo fronterizo del auditor y para el chequeo de consistencia de `bare_p0p04` (diferencia `3e−8`, tolerancia `5e−7+5e−9`).

Ediciones 22.4: `domain/state_gate.py` (records de entrada/wrapper), módulos puros `domain/state_gate_eval.py` y `domain/state_gate_results.py`, parser `siesta_backend/point_state_evidence.py`, `tests/unit/test_state_gate.py` y 50 fixtures comprimidos de la campaña NiO P5 (referencia más los 24 puntos BARE/SCREENED) en `tests/fixtures/i5_real_nio/`. No se editaron golden ni fixtures del replay. No se ejecutó SIESTA como parte de 22.4.

El `verificador_luna` revisó el diff 22.4. Detectó que un punto con gap máximo desplazado y ε≥1/2 en el índice de referencia debía ser `SUBSPACE_AMBIGUOUS` según R11; se corrigió la precedencia (primero split no único, después margen en k de referencia, y luego cambio de k) y se añadió `test_r11_ambiguous_reference_index_margin_precedes_moved_gap_reason`. En la segunda revisión confirmó que el defecto quedó cerrado y que las pruebas adicionales R12 del límite inclusivo de referencia y de `bare_p0p04` corresponden a la resolución del autor; sin bloqueos pendientes.

Verificación focal final antes del commit: `python -m pytest tests/unit/test_point_state_evidence.py tests/unit/test_state_gate.py -q` → `24 passed` (2 advertencias deprecadas existentes); `ruff check` sobre los cinco archivos Python del ítem → `All checks passed!`; `ruff format --check` → `5 files already formatted`; `MYPYPATH=src mypy --strict` sobre los cuatro módulos fuente → `Success: no issues found in 4 source files`.

En el commit de este ítem se volverán a ejecutar y registrar todos los gates obligatorios del §0. Un `PASS` global sigue siendo diagnóstico de los controles implementados: G3 permanece `NOT_ESTABLISHED:SMOOTHNESS_REQUIRES_SCF_LADDER`; no se afirmará exactitud SCF, histéresis ni consistencia energética.

### Corrección detectada por los gates post-commit 22.4

La primera pasada post-commit detectó que el import diferido de `state_gate_eval` aún cuenta como ciclo arquitectónico entre `domain/state_gate.py` y `domain/state_gate_eval.py`. Se separaron los records de entrada a `domain/state_gate_types.py`; el evaluador y el parser SIESTA importan esos records directamente, y `state_gate.py` conserva la fachada pública. `tests/unit/test_point_state_evidence.py tests/unit/test_state_gate.py tests/unit/test_import_architecture.py` → `32 passed`; ruff indicó solo formato/imports en los archivos reestructurados, ya corregidos. `verificador_luna` revisó esta separación y confirmó que mantiene fields/validaciones, rompe el ciclo y deja commit-ready. No se ejecutó SIESTA.

La primera invocación del replay en WSL falló por llamar `python` (no instalado allí); se verificó `/usr/bin/python3` y `/usr/bin/pytest`. Se repetirá como `python3 -m pytest` en la siguiente pasada completa; esto fue un problema de intérprete de la invocación, no una premisa falsa del ítem.
