# TASK 23c — auditoría de hashes y estado D16.1

## Cierre de la decisión energética recibida

La decisión del usuario implementa `tol_Fermi_eV` sin default y separa los
estados de ocupación/Fermi. Las pruebas cubren registro sin declaración, límite
inclusivo, exceso físico con motivo propio, declaración inferior al radio de
impresión combinado con advertencia, serialización/reporte, `RECORD_ONLY`, DM
de bytes distintos y referencia MnO archivada. El replay MnO declara factor
`1.0` exclusivamente en su config de fixture; no se agregó default productivo.
No se cambió ningún golden ni se ejecutó SIESTA real.

Salidas literales finales de esta pasada (PYTHONPATH=src):

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

La primera suite conjunta de referencia/config/CLI informó `1 failed, 132 passed`
por un import omitido de `planning_config_digest` en la prueba nueva. Se añadió
el import, sin modificar ninguna aserción; la suite completa de configuración
y los casos CLI nuevos pasaron después. Las dos advertencias son de deprecación
histórica de `adaptive_alpha`/`alpha_selection`.

```text
python -m ruff check <referencia, backend, step, CLI, product_plan, shadow y pruebas afectadas>
All checks passed!
python -m ruff format --check <los diez módulos/pruebas de referencia, CLI, configuración y shadow>
10 files already formatted
python -m mypy --strict --follow-imports=silent <los nueve módulos/pruebas de referencia, CLI, product_plan y shadow>
Success: no issues found in 9 source files
bash tools/check_v6_integrity.sh
V6 GATE OK
git -c core.whitespace=cr-at-eol diff --check
```

El último comando termina sin salida; se preserva CRLF histórico en
`tests/unit/test_campaign_plan.py`.

**Auditoría adicional cerrada:** los vetos de `product_cli._verify_campaign_inputs`
por digest declarado/almacenado distinto, ausente o malformado son clase (a)
y se convirtieron a `DigestWarning`. Cada copia requerida se lee y se contrasta
con ambas procedencias solamente para registrar `ARTIFACT_DIGEST_ABSENT`,
`ARTIFACT_DIGEST_MALFORMED` o `ARTIFACT_DIGEST_MISMATCH`. El digest de config
congelada ausente tampoco veta. Archivos realmente ausentes/ilegibles, paths que
escapan de la campaña y validación estructural/física siguen fallando por su causa.
Las advertencias se deduplican, ordenan y persisten en
`product-input-traceability.json` dentro de la campaña, antes del arranque del
worker; también se retienen en links/receipt de ejecución de producto/referencia.

Pruebas adicionales verifican metadatos distintos, ausentes incluso sin claves,
malformados, bytes de FDF alterados por un comentario inocuo, copias idénticas sin
warnings y archivos obligatorios ausentes o sustituidos por un directorio. Las
primeras fixtures Windows escribían la copia de config con CRLF y originaron
dos fallos por una advertencia adicional legítima; se corrigió la fixture para
copiar los bytes congelados exactos, conservando las aserciones exactas.

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

El último comando termina sin salida; no se modificó golden.

## Regla de decisión

Los SHA-256 de DM, salidas y evidencia describen archivos o sirven para recuperar
registros. Un desacuerdo de digest se persiste como advertencia y nunca declara
una diferencia física. La ruta, existencia, formato/parseo, convergencia y las
identidades semánticas siguen siendo condiciones propias y pueden fallar por su
causa real. Los hashes de nodos/reutilización solo recuperan identidades de
ejecución; la igualdad de bytes no demuestra equivalencia de estado.

## Usos de `parent_dm_sha256` y digests relacionados

| Ubicación / uso | Clase | Tratamiento |
|---|---|---|
| `execution/campaign_plan.py`, `execution/product_plan.py`: capturan el SHA del DM padre | (a) procedencia de archivo | Solo se registra; la ausencia del digest no impide planificar una referencia admisible. |
| `domain/coverage_models.py`, `domain/perturbation_plan.py`, `domain/perturbation_planner.py`: transporte/validación de digest padre | (a) procedencia | No se usa para admitir ni rechazar el plan. La admisibilidad aún depende de convergencia, inventario e identidades físicas observadas. |
| `execution/product_admission.py`: presencia del digest | (a) procedencia | Se eliminó `PARENT_DM_REQUIRED` como bloqueo. |
| `product_cli._verify_campaign_inputs`: digests de copias fuente/config/pseudopotenciales/estáticos/perfil y manifest | (a) procedencia | Mismatch/ausencia/formato sólo advierte; campos ausentes se leen con `.get`. Se verifica la existencia/lectura real y confinamiento del path. Warnings persistidos en archivo de trazabilidad y links/receipt. |
| `execution/campaign_runner.py`: DM del plan frente a DM observado | (b) estado recalculado | BITWISE eliminado. Deciden las ocupaciones parseadas y, solo si se declara, la tolerancia energética propia de Fermi; siempre se conservan ambos digests. |
| `execution/campaign_shadow.py`, `execution/observation_assembly.py`: DM de referencia frente al digest heredado por observaciones | (a) trazabilidad | Diferencias generan `PARENT_DM_DIGEST_MISMATCH` / `PARENT_DM_IDENTITY_MISMATCH`; ya no vetan una sombra ni una matriz. |
| `execution/campaign_files.py`: FDF, OUT, DM y copia del DM padre frente a provenance | (a) identidad de archivos | Archivos ausentes o rutas inseguras siguen fallando. Hash distinto se devuelve como `hash_warnings` (`ARTIFACT_DIGEST_MISMATCH`, `PARENT_DM_DIGEST_MISMATCH`). |
| `execution/source_evidence.py`: hashes de OUT, DM, recibos, manifest e identidad canónica | (a) trazabilidad | Mismatch se añade a `traceability_warnings`. La lectura, JSON, selección de evento y extracción numérica siguen validándose; datos ilegibles o respuestas que no se pueden reextraer fallan explícitamente. |
| `execution/campaign_runner.py::_revalidate_reuse` y `_analysis_execution_identity` | (a) digest de evidencia almacenada | Los mismatches se registran como advertencias; estado del nodo, paths dentro de la campaña/attempt, modos y artefactos existentes siguen validándose. |
| `domain/lr_analysis_v2.py`, `domain/matrix_lr.py`, `domain/scalar_lr.py`, `domain/observation_provenance.py` | (a) transporte/reporte/reuso | Los hashes aparecen como procedencia; la física usa ocupaciones y respuestas parseadas. No se usan como criterio de equivalencia física. |
| `reporting/lr_u_report.py`, `reporting/product_report.py` | (a) reporte | Presentan SHA de planificación/campaña como evidencia, no como aceptación. |
| `domain/response_grid_reproducibility.py`: hashes de DM, OUT/FDF, recibos, análisis, lock y dataset | (a) trazabilidad/reconstrucción | Mismatch se conserva en `traceability_warnings`; existencia/path y reextracción semántica se validan por separado. Contexto, receipt, dataset y comparación numérica siguen su propio contrato. |
| `domain/response_reuse.py`: identidad de padre, FDF, perfil, proyector, especie, magnetismo y MPI | (a) procedencia; contexto físico no representado | Hash igual/distinto/ausente/malformado produce la misma decisión `NOT_ESTABLISHED` cuando coinciden las claves semánticas disponibles; `PHYSICAL_CONTEXT_NOT_ESTABLISHED` exige recalcular directo. Las diferencias de claves semánticas se clasifican aparte como `PHYSICAL_IDENTITY_MISMATCH`. La identidad v1 solo contiene hashes para los valores físicos que faltan. |
| `execution/campaign_pilot_reuse.py`: output/receipt/identidad | (a) procedencia | Revalida lectura, esquema y estado del receipt; registra advertencias de todos los digests. No reusa un piloto sin valores físicos suficientes, independientemente de SHA. Selector independiente, todavía no conectado a init/runner. |
| `siesta_backend/observation_selector.py`, `bare_semantics_evidence.py`, `bare_trace_provider.py`: referencia/ejecutable/FDF/OUT/traza | (a) procedencia | Hash ausente/malformado/distinto se registra con `ARTIFACT_DIGEST_ABSENT`, `ARTIFACT_DIGEST_MALFORMED`, `ARTIFACT_DIGEST_MISMATCH` y continúa parseo. Los marcadores auditados, orden, unicidad, intervalo, versión y terminación siguen siendo condiciones semánticas. El contexto/receipt transporta las advertencias. |

## Otros hashes revisados

Los digests de FDF/configuración/perfil/pseudopotenciales son identidad de
entrada/procedencia. Los de reportes, locks, receipts y datasets son identidad de
archivos almacenados. Ninguno demuestra igualdad física; sus discrepancias no se
deben convertir en `PARENT_STATE_NOT_EQUIVALENT`. Los identificadores de campaña,
nodo, attempt, ruta y modo se mantienen como invariantes estructurales (no SHA).
Hashes canónicos de matrices/planes recuperan compromisos deterministas; donde
alimentan una decisión física deben reemplazarse por el valor/estado observado,
con el digest retenido como referencia.

## D16.1 y decisión dimensional de Fermi

`BITWISE` se eliminó del enum y de la configuración; la alternativa `RECORD_ONLY`
no concede equivalencia, pero conserva el rechazo por diferencia física real o identidad incompleta. `PRINT_EQUIVALENT` necesita un factor
`parent_reproduction_factor` explícito y `SCF.DM.Tolerance` única, positiva y
declarada en el FDF para formar el radio de ocupación
`max(semianchos de impresión sumados, factor × SCF.DM.Tolerance)`. Sin cualquiera
de esos elementos se emite `EQUIVALENCE_NOT_ASSESSED` y no se rechaza por SHA.

La tolerancia de density matrix no se aplica a eV. La política `tol_Fermi_eV`
es opcional, declarada y no tiene default. La CLI de producto `--tol-fermi-ev`
sobrescribe la configuración y registra fuente `cli`; la declaración por JSON
registra fuente `config`. Si está ausente se conserva diferencia, unidades y
semianchos bajo `fermi_equivalence=RECORDED_NOT_ASSESSED`; no cambia la decisión
de ocupación. Si está declarada se compara con el máximo de su valor y la suma
de ambos semianchos de impresión: los dos datos redondeados aportan radios
aditivos. Una declaración menor emite la advertencia tipada
`FERMI_TOLERANCE_BELOW_PRINT_HALF_WIDTH`, conserva el valor declarado y registra
el radio efectivo. Un exceso físico emite `PARENT_FERMI_NOT_EQUIVALENT`, distinto
del motivo de ocupación, y calcula directamente todas las clases que usan ese
padre. `occupation_equivalence` y `fermi_equivalence` se serializan y presentan
por separado. `RECORD_ONLY` nunca concede equivalencia y conserva los rechazos
físicos ya evaluados. Parseo no disponible produce
`EQUIVALENCE_NOT_ASSESSED`; identidad de átomo/proyector incompleta usa
`PARENT_IDENTITY_NOT_ESTABLISHED` y el fallback directo queda limitado a la clase
de ese átomo (o todas las clases si la diferencia es global).


## Correcciones y pruebas de esta pasada

Una diferencia de ocupación mayor que el radio declarado invalida la reducción
con `PARENT_STATE_NOT_EQUIVALENT` aunque la tolerancia energética de Fermi siga
sin evaluarse. El detalle identifica átomo, spin, elemento, diferencia y radio;
las comparaciones pendientes se registran aparte. No se aplica tolerancia de DM
a energía; una equivalencia de ocupación sí puede establecer el veredicto global
sin declaración energética, con el estado Fermi record-only visible.

### Ediciones de assertions autorizadas por el steering y el orquestador

| Prueba/caso | Antes | Ahora | Motivo |
|---|---|---|---|
| `test_reference_reproduction`: diferencia de dos cuantos | NOT_ASSESSED por Fermi ausente | Rechazo físico detallado aunque Fermi falte | Corregir masking de una diferencia de ocupación ya evaluable; se fortalece el invariante. |
| `test_response_reuse`: roundtrip y nueve dimensiones hash | EXACT_MATCH o IDENTITY_MISMATCH por SHA | NOT_ESTABLISHED, warning para SHA distinto; roundtrip y claves físicas siguen verificadas | Hash no contiene valores físicos suficientes. |
| `test_response_reuse`: output alterado y pilotos conflictivos | Excepción por SHA/bytes | Advertencias registradas, selección determinista, ningún piloto reusado | Recalcular directo sin bloquear campaña. |
| `test_response_reuse`: receipt alterado | Excepción por digest de receipt/identidad | Advertencias explícitas y NOT_ESTABLISHED; nuevos casos FAILED/None mantienen rechazo de estado de receipt | SHA es trazabilidad; esquema/estado siguen revalidados. |
| `test_bare_trace_provider`: executable sustituido | Excepción por SHA | Receipt VERIFIED con advertencia explícita; sidecar ausente y falta de collector siguen fallando | Trazabilidad separada de contrato semántico. |
| `test_bare_trace_adversarial_audit`: append inocuo a artefactos/traza | Excepción por SHA | Advertencia con campo, reason y digest observado | Cambiar bytes no demuestra diferencia física. |
| `test_bare_trace_adversarial_audit`: orden, marker duplicado/ausente, salida abortada, versión/revisión, vocabulario forjado, esquema incompleto | Error semántico | Mismas aserciones de error semántico | No se modificó el criterio físico/estructural. |

Se añadieron casos de hash ausente/malformado en los cinco campos BARE y piloto,
ruido de ocupación menor que el radio explícito, DM diferente con mismos números,
caso adversarial MnO archivado y serialización de warnings. No se cambió golden.

Verificación focalizada (PYTHONPATH del worktree):

```
python -m pytest -q tests/unit/test_hash_traceability.py tests/unit/test_reference_reproduction.py tests/unit/test_response_reuse.py tests/unit/test_bare_semantics_evidence.py tests/unit/test_bare_trace_adversarial_audit.py tests/unit/test_import_architecture.py
103 passed, 2 warnings in 3.04s
```

## Estado de cierre de esta pasada

La decisión del usuario cierra la política energética: las ocupaciones deciden
y Fermi participa solo con tolerancia eV declarada. Se cerraron los TODO de
trazabilidad de inventario/source/effective FDF y evidencia de calibración.

### Tabla adicional por callsite decisorio

`(a)` identifica procedencia de DM/archivo/evidencia y solo advierte. `(b)`
identifica la especie canónica necesaria para F2: representa pseudopotencial y
radiales, no etiqueta ni elemento. `(c)` es contrato operativo/protocolo fuera
del juicio de equivalencia de un padre; se mantiene por alcance confirmado por
el orquestador. Estos últimos pueden invalidar resume si cambia el contrato
congelado; no se presentan como diferencias físicas D16.

| Callsite | Clase | Tratamiento / justificación |
|---|---|---|
| `perturbation_plan_evidence.freeze_inventory`: inventory/effective-FDF SHA | a | No exige formato/presencia; conserva atom/site únicos y ProjectorEvidence completo. |
| `freeze_inventory`: species identity | b | Identidad canónica del pseudopotencial/subespacio usada para F2; se conserva require_sha256 cuando se aporta. |
| `coverage.qualify_coverage`: inventory/source/OUT SHA | a | Se retiraron validadores que impedían clasificar evidencia física ya parseada. |
| `CoverageQualification.__post_init__/from_mapping`: inventory/effective-FDF SHA | a | Opcionales; warnings computados y serializados cuando existen. Clases, índices de operación y partición se validan. |
| `symmetry_operations.classify`: input/effective-FDF SHA | a | Diferencia advierte en qualification; ya no produce EVIDENCE_BINDING_MISMATCH ni expansión por digest. |
| `symmetry_operations.classify`, `SymmetryAtom`, `SymmetryModel`: species identity y contrato canónico del modelo | b/c | Mantienen F2 exacta de especie/pseudopotencial y esquema del modelo. No se infiere equivalencia por etiqueta. |
| `ResolvedPerturbationPlan._validate`: source/effective/inventory binding | a | Warning; compara referencia física de coverage por valores y verifica protocolos, run_specs, omisiones y reconstrucciones. |
| `ResolvedPerturbationPlan.from_mapping`: metadatos SHA y campos derivados | a/c | SHA opcionales; igualdad de campos semánticos/bands/pesos sigue requerida. |
| `CalibrationQualification` del plan: evidence SHA y digest protocol observado | a | Warning en plan; tau, columnas, estimador y matriz conservan su contrato físico. |
| `perturbation_planner.resolve_perturbation_plan`: protocol_sha256 de qualification | a | Mismatch solo advertencia en plan; sigue comprobando tau y columnas/amplitudes declaradas. |
| `fdebq_models.CalibrationQualification`: evidence_sha256 | a | Optional/malformed permitido como metadata, warning serializado; estado/calificación, columnas y matriz sin cambios. Protocol SHA es contrato c separado. |
| `ProductSnapshot.__post_init__/from_mapping`: inventory/source/input/FDF SHA | a | Compara inventario/coverage por valores semánticos; ausencia/formato no decide. frozen-config hash discrepancy se registra en detail. |
| `product_admission.execution_admission/_translation_shadowed_admission`: inventory.digest | a | Warnings en admission; estado, inventario físico, sites, grid, reduction/shadow y reference flags siguen evaluándose. |
| `campaign_v2.load_campaign_v2/verify_campaign_inventory`: input-files SHA/input_identity | a | Hash opcional, mismatch/formato/ausencia warning; archivos reales, rutas seguras y estructura de manifiesto se conservan. Runner persiste warnings y reporte los muestra. |
| `campaign_runner._analysis_execution_identity`: evidence_digest obligatorio | a | Node ID y VALIDATED son obligatorios; evidence_digest ausente/malformado solo advierte. |
| `generic_executor.NodeReceipt/JsonDagCheckpoint`: evidence_digest | a | Metadata opcional y warnings serializados; node_id/state/duplicados y DAG operativo siguen exigidos. |
| `response_grid_reproducibility._fields/_digest/_validate_reference_execution`: SHA de DM/OUT/FDF/recibos | a | Campos SHA opcionales, formato/mismatch warnings; mapas de hashes ausentes no impiden reextraer archivos reales. Intentos independientes, modos, átomos, parseo y datos físicos se verifican. |
| `source_evidence.validate_source_manifest/extract_verified_response_tokens` y schema | a | SHA opcionales; formato/ausencia/mismatch warning; JSON finito, schema semántico, archivo/ruta, nodos VALIDATED, parser y numerics siguen requeridos. |
| `observation_provenance.validate_observation/validate_response_lot`: parent-DM/FDF/output/SCF-evidence SHA | a | No deciden aceptación; warnings en lote. Cartesian grid, roles, retorno cero, SCF y DM-read positivo siguen requeridos. |
| `observation_provenance`: pseudo/subspace/projector/physical-model/runtime/selector/magnetic canonical identities | b/c | Representan identidad física o contrato de selección declarado; fuera del gate D16 de estado recalculado. |
| `occupation_noise_calibration.validate_calibration_result`: result esperado/DM/receipts/replica-result SHA | a | SHA de evidencia opcionales y warnings; se rederiva el estadístico, conserva política, independencia jobs, rutas y count. |
| `occupation_noise_calibration`: frozen lock/result-lock SHA | c | Compromiso de receta preregistrada; cambio de receta no admite el resultado con otra política. |
| `adapter.prepare_canonical_dm` | a | Devuelve digest observado; mismatch solo RuntimeWarning con reason code; copy2/file existence conserva errores reales. Ruta retirada, no autoriza ejecución. |
| `campaign_plan.verify_frozen_campaign_plan` | c | Locks canónicos de plan/config/planner version para resume, separados del gate físico D16. Conservados. |
| `campaign_shadow` journal plan digest | c | Journal debe pertenecer al mismo plan operativo; conserva gate de asociación del registro. |
| `campaign_v2` resolved plan digest, `product_plan` lock, `ProductBoundary` receipt identity, `generic_executor` DAG digest | c | Contratos canónicos de plan/runtime; preservados, no equivalencia física. |
| `campaign_software_lock`, `backend_admission` | c | Garantizan ejecución con software realmente admitido/instalado; no se sustituyen por equivalencia D16. |
| `campaign_split`, `semantic_split_models`, `split_generated_identity`, `scf_ladder_inputs` | b/c | Identidad semántica/protocolo de materialización de entradas generadas; fuera del juicio D16 de DM/evidencia observada. |
| `fdf_symmetry_adapter`: symmetry certificate binding | b/c | Certificado de operación ligado al modelo físico declarado; no evidencia de reproducción del padre. |
| `scf_validation`: T0–T4 protocol/evidence commitment | c | Validación formal del protocolo científico independiente; no admite padres ni sombras D16. Conservado por alcance. |
| `u_certification_node`, `u_release_gate`, `downstream_u_admission`, `domain/u_certification.py` | c / protegido | Certificación/release científicos históricos; no se editaron. El nodo migrado forma parte del baseline V6 y está protegido. |
| `reporting/lr_u_report`, `reporting/product_report`, `domain/lr_analysis_v2`, `matrix_lr`, `scalar_lr` | a | Solo transportan/renderizan digests; no deciden por ellos. |

Los usos de los módulos parent/shadow/reuse/backend BARE de la tabla inicial
se mantienen advertencia-only. El escaneo se hizo con rg sobre `sha256`,
`digest`, comparaciones y `require_sha256` en domain/execution/backend/reporting.
No se editó V6 ni un gate de certificación/release.

### Ediciones adicionales de pruebas

| Caso | Antes | Ahora / razón |
|---|---|---|
| `test_coverage`: binding effective-FDF SHA | ALL_SUBSPACES/EVIDENCE_BINDING_MISMATCH | Misma estrategia/classes/computed_columns que evidencia idéntica; warning. Fallbacks de evidencia ausente, perturbación, especie/operación y syntax permanecen. |
| `test_perturbation_plan`: source/effective/inventory SHA | Error | Mismos status/runs/reconstrucciones y warnings; alteración bands/pesos aún error. |
| `test_product_admission`: snapshot digest | Bloqueo por digest | Caso físico preservado alterando atomic_number; nuevos casos SHA solo advierten. Fixture usa ProjectorEvidence/CorrelatedSubspace completos para comparar por valores. |
| `test_perturbation_planner`: parent-DM SHA ausente | NOT_ESTABLISHED | READY directo con warning; referencia realmente inadmisible sigue NOT_ESTABLISHED y runs completos. |
| `test_observation_provenance_integration`: parent SHA distinto | Error mixtures | compatible_for_analysis con warning; grid incompleto y estado SCF incorrecto siguen error. |
| Nuevos casos en `test_source_evidence`, `test_campaign_plan`, `test_generic_executor`, `test_fdebq_rounds`, `test_occupation_noise_calibration`, `test_hash_traceability` | Sin cobertura absence/malformed | Reextracción idéntica/estado físico idéntico para SHA ausente/malformado y errores reales por archivo ausente, recibo sin node ID, ocupación/identidad canónica cambiada o estadístico alterado. |

No se cambió timeout ni límite Hypothesis. Una ejecución intermedia excedió el
deadline de 200 ms por construir warnings del plan recorriendo dos veces todo
el modelo; se optimizó el código a inspeccionar solo metadata y se reran los
15 tests del plan: `15 passed, 2 warnings in 4.65s`.

Pasada ampliada final (incluye provider y los consumidores modificados antes):

```
python -m pytest -q tests/unit/test_hash_traceability.py tests/unit/test_reference_reproduction.py tests/unit/test_response_reuse.py tests/unit/test_bare_semantics_evidence.py tests/unit/test_bare_trace_adversarial_audit.py tests/unit/test_bare_trace_provider.py tests/unit/test_import_architecture.py tests/unit/test_observation_assembly.py tests/unit/test_product_admission.py tests/unit/test_campaign_shadow.py tests/unit/test_source_evidence.py
170 passed, 4 skipped, 2 warnings in 16.45s
```

Salida literal de gates finales:

```
git diff --check
# sin salida, exit 0
bash tools/check_v6_integrity.sh
V6 GATE OK
ruff check --isolated --target-version py312 --line-length 110 <hash_traceability, response_reuse, campaign_pilot_reuse y sus tests editados>
All checks passed!
ruff format --isolated --line-length 110 --check <mismos seis archivos>
6 files already formatted
mypy --strict --follow-imports=silent src/hubbardflow/domain/hash_traceability.py src/hubbardflow/domain/response_reuse.py src/hubbardflow/execution/campaign_pilot_reuse.py
Success: no issues found in 3 source files
```

Los cuatro skipped pertenecen a las pruebas POSIX/integración condicionadas en
Windows de la suite de source_evidence; no se ejecutó SIESTA. Los warnings son
las dos deprecaciones existentes de alpha_selection/adaptive_alpha. No se hizo
commit, push, PR ni cambio de rama en esta pasada.


## Evidencia final de la ampliación

```
# source_evidence + perturbation_plan_evidence + response_grid_reproducibility_independence
20 passed, 4 skipped, 2 warnings in 2.08s
# observation_provenance + occupation_noise_calibration (incluye fixture receipt DM/evidence opcionales)
16 passed in 0.71s
# fdebq_rounds + hash_traceability + generic_executor
43 passed, 2 warnings in 7.07s
# campaign_plan + campaign_runner_execution_identity + generic_executor + product_admission + source_evidence + observation_provenance + occupation_noise_calibration + hash_traceability + import_architecture
123 passed, 4 skipped, 2 warnings in 67.54s
```

La suite amplia inicial de doce módulos tenía assertions hash antiguas y fue
interrumpida tras difundir los resultados focalizados, a petición del
orquestador. Otra corrida coverage/plan/planner llegó a `70 passed` antes de la
aserción histórica parent-DM ausente (ya adaptada y documentada). La última
repetición de esos tres módulos se interrumpió para liberar escritor, sin
nuevos fallos impresos. No se declara suite amplia completa verde.


## Correcciones de la auditoría final de D16.1

- La comparación de ocupaciones calcula para cada elemento el radio como la
  suma de los semianchos de sus dos tokens decimales. Aplica a ese elemento
  `max(radio_impresion_elemento, factor * SCF.DM.Tolerance)`. Un token de menor
  precisión en otro elemento o átomo nunca amplía la tolerancia de éste.
  `occupation_tolerance_e` conserva el máximo sólo como resumen informativo;
  `occupation_tolerances_e` registra todos los radios efectivos usados.
- `affected_atom_indices` conserva todos los átomos con diferencias físicas;
  la expansión usa ese campo tipado. No interpreta el primer átomo de una
  cadena de diagnóstico. Identidad global incompleta, datos heredados sin
  alcance tipado o índices que no se pueden localizar hacen calcular
  directamente todas las clases reducidas de ese padre.
- El reporte muestra ambos digests, diferencias máximas, radios efectivos de
  ocupación, tolerancia SCF declarada y factor. Fermi registra su propio estado,
  diferencia, semianchos de impresión, tolerancia declarada/efectiva, fuente y
  advertencias. Sin declaración usa `RECORDED_NOT_ASSESSED` y no cambia el padre.
- Revalidar un resume guarda `node-evidence.json` aun cuando todos los nodos
  siguen validados: las advertencias de hash no dependen de una invalidación
  para persistirse.

Pruebas nuevas: precisiones heterogéneas en un mismo átomo (un token `0.5`
no oculta la diferencia `0.00002` en otro elemento); registro de dos átomos
físicamente distintos; expansión de dos clases y expansión global por
identidad incompleta; tolerancias y Fermi no evaluado en Markdown; advertencias
persistidas sin invalidaciones. La prueba adversarial de MnO archivado y las
pruebas de ruido y DM distinto permanecen activas. No se actualizó ningún golden.

Salida literal de verificación enfocada:

```text
70 passed, 2 warnings in 18.90s
All checks passed!
All checks passed!
3 files already formatted
Success: no issues found in 5 source files
V6 GATE OK
```

Comandos: pytest con rutas explícitas para `test_reference_reproduction.py`,
`test_campaign_shadow.py`, `test_campaign_runner_execution_identity.py` y
`test_import_architecture.py`; ruff check y format de referencia y adaptador;
ruff check de las pruebas de shadow; mypy strict con follow-imports=silent
para los cinco módulos/pruebas de referencia y shadow. Ruff F del runner
legado informa once hallazgos preexistentes (imports históricos y un f-string);
no se alteran sus APIs ni se eliminan esos imports en esta corrección.


La revisión final corrige `RECORD_ONLY`: nunca concede equivalencia, pero una
ocupación que excede la tolerancia efectiva y una identidad incompleta siguen
invalidando la reducción del padre con su reason code físico. Las pruebas
cubren ambas vías (comparador de dominio y parser), y mantienen la ausencia
de rechazo por ruido dentro de tolerancia o DM de bytes distintos. Se actualiza
`CODEX_TASK23_TS.md` para retirar la opción bitwise y el reason code de DM,
documentar cálculo directo por alcance físico y la decisión dimensional Fermi
recibida del usuario.


Salida literal después de corregir RECORD_ONLY (pytest con los cinco módulos
explícitos de referencia, shadow, identidad del runner, hash traceability y
arquitectura):

```text
89 passed, 2 warnings in 16.73s
All checks passed!
3 files already formatted
Success: no issues found in 5 source files
V6 GATE OK
```

`git diff --check` termina sin salida. El diff de `test_campaign_plan.py` se
minimiza preservando los bytes de las líneas históricas y agregando sólo los
casos de configuración/trazabilidad ya presentes; no se debilitan aserciones.

La suite explícita `tests/unit/test_campaign_plan.py` pasó:

```text
39 passed, 2 warnings in 45.33s
```
