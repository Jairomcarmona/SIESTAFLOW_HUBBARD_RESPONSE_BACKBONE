# Eje rector para cerrar la utilidad independiente de U con SIESTA

**Fecha:** 2026-09-28. **Estado:** plan de ejecución; ninguna campaña nueva queda autorizada por este documento.

> **Actualización de estado (2026-09-29):** este eje conserva el alcance y las
> puertas del plan; su tabla de línea de base no sustituye el estado posterior
> del trabajo. La fuente de ocupación del análisis v3 quedó fijada como
> `siesta_occupations_total` para los eventos seleccionados; `matrix_trace` se
> conserva como comprobación/semántica histórica v2. La campaña adaptativa
> NiO actual termina como `NUMERICAL_CANDIDATE_UNASSESSED` y
> `physical_acceptance=NOT_ESTABLISHED`; su tolerancia de sensibilidad no se
> había configurado. La cota cúbica de impresión reportada es 0.03436273105 eV
> y 0.01353711826 eV es un ajuste lineal diagnóstico, no la cota primaria.
> El objetivo posterior de ±0.02 eV es operativo, no una tolerancia física
> universal. Para el expediente y las rutas de investigación vigentes, véase
> [`INFORME_CONTEXTO_CUELLO_BOTELLA_U_20260929.md`](INFORME_CONTEXTO_CUELLO_BOTELLA_U_20260929.md).
> El [registro final P0–P6](P0_EXECUTION_20260928.md) declara
> `PRODUCT_BLOCKED`: el flujo operativo y la campaña P5 concluyeron, pero el
> objetivo científico de U que exige el usuario sigue sin establecerse.

Este documento gobierna el trabajo **pendiente** para entregar `siestaflow_hubbard` como utilidad independiente con CLI propio. El [plan de integración anterior](PLAN_INTEGRACION_GLOBAL_DAG_U_POLINOMICO.md) registra lo que ya se implementó; sus fases terminadas no se repiten. `AGENTS.md` conserva la prioridad de lanzar los nodos SIESTA una vez autorizada una campaña.

## 1. Meta comprobable y límite científico

Una persona debe poder instalar el paquete, declarar FDF, pseudopotenciales, sitios correlacionados y perfil de ejecución, y ejecutar `init → run/status/resume → report` desde PowerShell→WSL o directamente en Linux, incluido un entorno Slurm con una asignación ya concedida, sin que un agente edite la campaña en vivo. La ruta Slurm no necesita un segundo planificador ni enviar `sbatch` desde cada nodo; usa el ejecutor de asignación existente. La política automática documentada debe completar el recorrido o devolver un estado terminal dentro de su presupuesto; una política experta puede fijar tolerancias y límites distintos antes de iniciar. El DAG debe entregar JSON versionado e informe Markdown regenerable con la respuesta completa y un resultado **por sitio**:

\[
\chi^0_{IJ}=\left.\partial n_I^{\mathrm{BARE}}/\partial\alpha_J\right|_0,
\quad \chi_{IJ}=\left.\partial n_I^{\mathrm{SCREENED}}/\partial\alpha_J\right|_0,
\quad U_I=[(\chi^0)^{-1}-\chi^{-1}]_{II}.
\]

La cantidad de esta versión es `U_scalar_charge`, con la definición de ocupación y proyector declarada. El reporte **no** la convierte automáticamente en `Ueff_Dudarev`: SIESTA usa `U-J` en su implementación colineal de Dudarev y esa equivalencia requiere otro contrato físico. Tampoco se etiqueta automáticamente un elemento fuera de la diagonal como el `V` de otro funcional. La utilidad se considera terminada aunque un material particular termine como candidato sensible, sin U calculable o sin aceptación física, siempre que esa conclusión y su causa sean correctas y reproducibles. El acuerdo con gap, red o literatura puede servir de comparación independiente, nunca de selector de α, estimador o valor de U.

**Alcance certificado v1:** ruta SIESTA 5.4.2 y modos de espín para los que el parser y el protocolo BARE/SCREENED tengan pruebas reales. El número de sitios y el perfil MPI son parámetros de campaña. No se promete cobertura de espín no colineal, spin–orbit, un `J` calculado, ni un U físico universal. Ampliar esas capacidades sería otra versión y no bloqueará el cierre de esta utilidad.

## 2. Línea de base que no se vuelve a construir

| Pieza | Evidencia actual | Pendiente real |
|---|---|---|
| CLI y DAG | El cierre P3/P6 ejercitó `init/run/status/resume/report/stop` en PowerShell→WSL y la ruta pública de manifiesto directo para Linux/Slurm dentro de una asignación concedida. El DAG adaptativo, presupuesto y reanudación selectiva están implementados; P5 completó 25 nodos seriales y `resume` no relanzó SIESTA. | Mantener la evidencia de la ruta soportada y distinguir su cierre operativo del bloqueo científico de U. |
| NiO PBE adaptativo | La campaña contiene 41 nodos: 1 referencia, 20 BARE y 20 SCREENED. El análisis v3 reporta `NUMERICAL_CANDIDATE_UNASSESSED` y `physical_acceptance=NOT_ESTABLISHED`, porque no había tolerancia de sensibilidad configurada. El análisis histórico v2 y la reconstrucción v3 de los mismos OUT son resultados versionados distintos; no se sobrescriben. | Usar el reanálisis v3 para el estado actual y conservar intactos los artefactos y conclusiones históricas. No interpretar `STOP_STABLE` como pase de tolerancia física. |
| Ocupación y precisión | El análisis v3 ajusta `siesta_occupations_total`, el total seleccionado de `Occupations:`; `matrix_trace` queda como comprobación y semántica histórica v2. La precisión se propaga desde los tokens realmente seleccionados. | Mantener una única fuente por análisis/versionado y documentar por separado el intervalo de impresión, la sensibilidad del ajuste y cualquier término de repetibilidad. No exigir un ejecutable SIESTA modificado como ruta portable. |
| Reporte | El esquema v3 y Markdown publican fuente de ocupación, respuesta por sitio, cota de impresión, diagnósticos de ajuste, SCF y estado de aceptación. Los reportes v2 históricos conservan su significado original. | Comunicar en primer plano el estado `PRODUCT_BLOCKED` del cierre P0–P6 y los límites de la afirmación numérica. |
| Políticas | Las puertas operativas, el presupuesto, el refinamiento simétrico y los estados terminaron P0–P6; el análisis NiO original carecía de tolerancia de sensibilidad preregistrada. | Resolver prospectivamente qué garantía numérica y qué evidencia permiten declarar un U útil bajo el objetivo del usuario, sin cambiar retrospectivamente el contrato. |

El árbol de trabajo ya contiene cambios sin consolidar en `src/siestaflow_hubbard`. El ejecutor los inspeccionará por archivo antes de editar y conservará los `.out`, los manifiestos y los reportes históricos como evidencia inmutable. No hará un inventario de hashes del repositorio.

## 3. Rutas de investigación, en orden y con salida obligatoria

### R1. Definir el observable ajustado: una sola ruta primaria

1. Leer el código fuente local **SIESTA 5.4.2** que acumula y escribe la matriz y `Occupations:`. Comparar el orden real de impresión con los eventos seleccionados BARE y SCREENED de los 41 `.out` NiO; incluir al menos un caso sin polarización del archivo de regresión. La documentación de otra versión no decide este contrato.
2. **Si** el tercer número de `Occupations:` representa la misma suma interna de diagonales y cada intervalo de impresión concuerda con la traza de matriz del mismo evento, usar ese total como dato primario de referencia, BARE y SCREENED. Leer su semiancho directamente del token; conservar `trace_total` sólo como comprobación independiente. Recalcular de cero pendientes, matrices, U y cota de redondeo. Nunca aplicar el semiancho de seis decimales al U calculado con diagonales de cinco.
3. **Si** falla esa equivalencia, mantener `trace_total` como primario con el semiancho de sus diagonales; publicar la discrepancia concreta. Si ninguna representación se puede vincular inequívocamente al evento físico, terminar la ruta como `OBSERVABLE_UNRESOLVED`, con valor previo sólo histórico. No probar observables adicionales hasta obtener una hipótesis nueva y verificable.
4. El cambio de significado del dato ajustado exige un campo obligatorio `occupation_source` y una versión de esquema nueva si la interpretación de v2 cambia. Un lector antiguo debe seguir entendiendo un resultado v2 como histórico; `report` nunca reetiquetará sus números.

**Salida de R1:** una decisión documentada, tablas de comparación por evento, U recalculado por sitio y cota de impresión de la variable realmente usada, o un bloqueo con línea de código/`.out` que lo demuestra. Máximo una ruta primaria y una alternativa; no se elige la que acerque U a literatura.

### R2. Distinguir fuentes de sensibilidad sin inventar una incertidumbre total

- **Impresión:** propagar los intervalos decimales del dato ajustado por el ajuste y la inversión. Si los intervalos permiten una matriz singular o la cota no puede certificarse, publicar `bound_unavailable` y su causa; mantener separado el candidato puntual.
- **Modelo/ventana:** comparar cúbico, lineal en la misma malla y ventanas predeclaradas sólo cuando tengan rango y grados de libertad suficientes. Informar cada diferencia y el motivo de exclusión de una ventana. No promediar estimadores ni ampliar grado para mejorar R².
- **SCF:** conservar el estado de cada referencia y SCREENED, iteraciones, último `dDmax`/`dHmax` y tolerancias. BARE de un solo paso se informa como `BARE_SINGLE_STEP`, aunque SIESTA imprima `SCF_NOT_CONV`. Un residual SCF no es una barra de error de U. La campaña NiO actual no justifica un rerun SCF más estricto por defecto.
- **Rama electrónica, proyector y álgebra:** validar continuidad de estado, identidad del proyector entre referencia/perturbaciones, completitud de filas/columnas de χ, rango e inversión. Si falla cualquiera, el DAG emite una causa terminal, no una cifra aparente.
- **Automatización sin umbral físico ficticio:** una política predeterminada puede elegir estimador, malla inicial y presupuesto operativo; sólo se rotula `WITHIN_TOLERANCE` cuando la tolerancia científica de U está declarada y su alcance está explicado. Sin ella, el CLI termina normalmente con `UNASSESSED`, muestra U y sensibilidades y no pide vigilancia de un agente.

**Salida de R2:** estados y causas independientes para `printing_rounding`, `fit_window`, `scf`, `magnetic_branch`, `projector` e `inversion`; ninguna suma de incertidumbres de fuentes no calibradas.

### R3. Decidir si un cálculo nuevo puede cambiar una conclusión

Sólo se agregan nodos si existe una pregunta cuantitativa predeclarada cuya respuesta pueda cambiar el estado y el costo cabe en el presupuesto. Para `shrink`, la política fija par simétrico, ventana y límite antes del despacho. Para `expand`, se requieren la sonda de ruido y los predicados de señal/continuidad ya definidos por el controlador; una sonda parcial no certifica U ni autoriza ampliar las otras columnas. Un cambio de nivel SCF del **U final** requiere rehacer todos los puntos de las matrices que éste usa bajo el mismo nivel, no mezclar valores. Si falta umbral o presupuesto, el resultado termina `UNASSESSED` o `SENSITIVE` con motivo. Un valor de U “prometedor” o cercano a literatura nunca activa una ronda.

## 4. Contrato de decisión que impide iteraciones cíclicas

| Puerta | Para continuar o declarar candidato dentro de política | Si no se cumple |
|---|---|---|
| Entrada | FDF/funcional/pseudopotenciales/proyector/estado de referencia compatibles; α, estimador, recurso y presupuesto congelados. | `INPUT_INVALID`; corregir antes del primer SIESTA. |
| Datos | Un evento inequívoco por sitio, α y modo, unido a salida normal y DM padre; referencia/SCREENED convergidos; BARE validado como un paso. | `DATA_INVALID` o `NO_NUMERICAL_U`; no ajustar datos incompletos. |
| Cálculo | Diseño de ajuste con rango y DoF declarados; χ⁰ y χ utilizables; inversión reproducible; ocupaciones de una sola rama. | `NO_NUMERICAL_U` o `NO_SINGLE_STATE_U`; conservar diagnósticos. |
| Evaluación | Umbral de sensibilidad **predeclarado**, métricas requeridas presentes y dentro de él; dos comparaciones entre rondas comparables para `STOP_STABLE` cuando se usa adaptación. | Candidato `UNASSESSED` o `SENSITIVE`; `STOP_LIMIT_SENSITIVE` al agotar rondas/presupuesto. |
| Impresión | Cota vinculada al observable ajustado y matrices invertibles para todos los valores admitidos por esa cota. | Candidato visible con `bound_unavailable`; no certificar decimales mediante otra métrica. |
| Publicación del resultado | JSON e informe coinciden en dato, ecuación, U por sitio, unidades, estado, costo y razones. | Fallo de reporte bloquea la entrega, no reejecuta SIESTA. |

Se conservan los límites ya implementados: a lo sumo `max_refinement_rounds`, `max_alpha_points`, `total_siesta_node_budget` y el número de intentos del perfil. La configuración no cambia a mitad de una campaña. Un nodo terminal sólo se reabre si se identifica un error reproducible en su entrada, salida o código; se versiona la nueva campaña/análisis. **Ningún agente ajustará umbrales, α o proyector para forzar `STOP_STABLE` o un U deseado.**

Por puerta de software se permiten dos correcciones localizadas con repetición de la prueba que falló, y como máximo doce correcciones localizadas en toda la ejecución P1–P6; los contadores no se reinician al cambiar de agente o fase. Si aparece la misma falla una tercera vez, o se agota el límite global, la ejecución one shot termina `BLOCKED` con archivo, comando, salida y causa probable; no empieza otra exploración abierta. Un bloqueo crítico impide declarar terminado el producto. Un material `SENSITIVE` con método válido **no** bloquea el producto.

## 5. Secuencia de implementación y pruebas de la ejecución one shot

| Fase | Trabajo concreto | Evidencia de salida y condición de avance |
|---|---|---|
| P0. Congelar contrato | Revisar sólo los archivos afectados, fijar fuente SIESTA 5.4.2, versiones de esquema, dos conjuntos reales archivados (NiO multisite y la campaña Cu1 en `docs/evidence/siesta542_openmpi_slurm_full_campaign_20260920_run2_wheel`, si sus salidas pasan el control de integridad; si falla, dejar la selección de otro conjunto documentada antes de P1), política de prueba y límite de recursos. | Lista corta de archivos/decisiones y costos. No se recalculan hashes históricos en masa. |
| P1. Fuente de ocupación | Ejecutar R1 sobre los `.out` existentes; implementar un adaptador único de ocupación con fuente explícita y verificación cruzada; migrar análisis sin mutar v2. | Cada vector ajustado corresponde a su token y evento; recomputación independiente de χ, inversas, U y cota. |
| P2. Decisiones matemáticas | Revisar estados, ventana, impresión, rama, SCF y matriz; adaptar sólo los predicados que no representen el contrato de §4. | Pruebas con datos sintéticos de U conocido y casos adversos; cada caso termina en estado único dentro del presupuesto. |
| P3. DAG, CLI e informe | Conectar P1–P2 al cierre común de `run/resume/report`, tanto fijo como adaptativo; añadir resumen SCF y tabla por nodo en JSON/Markdown; conservar trazabilidad automática acotada. Enrutar el CLI público según el perfil: puntero y supervisor para PowerShell→WSL; manifiesto directo para Linux y asignación Slurm, sin duplicar el analizador ni implantar un nuevo envío `sbatch`. Quitar la restricción `local_wsl` sólo donde el adaptador existente y una prueba la respalden. | El mismo análisis produce el mismo JSON/reporte al reanudar; `report` no invoca SIESTA; el usuario ve causa y valor cuando existe; CLI Linux/Slurm controla el DAG por la ruta pública documentada. |
| P4. Regresión sin cómputo SIESTA | Reprocesar los 41 `.out` NiO y otro conjunto real archivado; cubrir modo de espín admitido, varios sitios, BARE/SCREENED, matrices singulares, resolución limitada, cambio de rama, presupuesto, `resume` y la ruta **pública** Linux/Slurm con fixtures y evidencia Slurm real archivada. Correr una vez la suite pública y clasificar fallos vigentes/obsoletos. | Las pruebas pertinentes al producto pasan; todo fallo de la suite queda reparado o explícitamente retirado con razón. La evidencia antigua conserva su semántica y el nuevo resultado lleva versión propia. |
| P5. Prueba real final | Una campaña **nueva y pequeña**, con FDF y PSML auditados antes de empezar, controlada enteramente por el CLI desde PowerShell→WSL. Ruta primaria: un sitio correlacionado y seis α no nulas simétricas, `1 + 2×1×6 = 13` nodos. Si ningún FDF de un sitio pasa P0, elegir **antes de calcular** el NiO PBE de dos sitios ya conocido con las mismas seis α: `1 + 2×2×6 = 25` nodos. Es una sola campaña elegida en P0, nunca dos intentos por preferencia de U. Hasta cuatro rangos MPI de la laptop y un SIESTA simultáneo. `status/resume/report` se ejercitan sin editar FDF a mano. La campaña NiO archivada cubre la regresión adaptativa multisite. | Termina como resultado numérico o diagnóstico científico honesto; conteo ≤13 en la ruta primaria o ≤25 en la alternativa, sin nodos duplicados ni intervención agentica durante transiciones normales. Un fallo posterior al lanzamiento se corrige/reanuda en la misma campaña, sin cambiar material. |
| P6. Entrega | Instalar el paquete construido en entorno limpio, ejecutar el quickstart real para PowerShell y el comando público en Linux dentro de WSL, alinear README/manual/políticas con CLI y límites certificados; fijar versión de entrega y notas de cambios. | Artefacto instalable, comandos reproducibles en ambas superficies, JSON e informe profesional, matriz de capacidades soportadas y pendientes sin prometer Ueff. |

Las pruebas de P4 pueden ser numerosas porque son locales y repetibles; P5 está acotada y es una prueba de producto, no una campaña de búsqueda de U. El CLI Slurm nuevo se prueba contra el ejecutor ya existente y salidas reales archivadas. Una prueba Slurm **nueva** con SIESTA sólo se incluye si P4 descubre un defecto que la evidencia archivada no puede resolver; se declara antes su propio presupuesto y no se carga a P5. Ninguna fase usa parámetros de red, gap o U de literatura como valor esperado del algoritmo.

### Mapa de integración y prueba

| Contrato | Módulos que se revisan y modifican sólo si hace falta | Comprobación decisiva |
|---|---|---|
| Fuente de ocupación y precisión | `siesta_backend/occupation_precision.py`, parser de ocupaciones y `domain/quantized_response.py` | La observación ajustada, su token fuente y su intervalo corresponden al mismo evento; prueba unitaria y reproceso NiO/Cu1. |
| Ajuste y decisiones | `domain/matrix_response_acceptance.py`, `domain/adaptive_alpha.py`, `domain/adaptive_alpha_control.py` | Datos sintéticos conocidos y casos singulares/sensibles terminan con causa única; ningún bucle supera los límites. |
| DAG y perfiles | `execution/campaign_runner.py`, `execution/campaign_v2.py`, `execution/slurm_foreground.py`, `cli.py` | `run/resume` reusan nodos válidos y ejercen el mismo cierre en WSL, Linux y Slurm; sólo un SIESTA activo en la laptop. |
| Entrega científica | `reporting/lr_u_report.py`, exportador JSON y esquema versionado | `report` regenera tablas y diagnósticos sin ejecutar SIESTA; JSON y Markdown coinciden y v2 histórico sigue interpretable. |

Los nombres son puntos de inspección, no una orden de reescribir todos esos archivos. Los tests existentes `tests/unit/test_occupation_precision.py`, `tests/unit/test_quantized_response.py`, `tests/unit/test_matrix_response_acceptance.py`, `tests/unit/test_adaptive_alpha_dag_resume.py`, `tests/unit/test_campaign_runner_synthetic.py`, `tests/unit/test_slurm_foreground.py` y `tests/test_cli_and_manifest.py` sirven de base; se añaden sólo los casos que cubren contratos nuevos. La política automática predeterminada, sus unidades, límites y el significado de `UNASSESSED` deben quedar probados como parte de P2 y documentados en P6.

## 6. Criterio final de producto y reporte de cierre

Se declara `PRODUCT_READY` sólo cuando P1–P6 cumplen sus puertas, el CLI completa la prueba real dentro del presupuesto, el resultado versionado se regenera desde datos guardados y no queda un defecto crítico abierto en el camino soportado. El cierre entregará:

1. Comando de instalación y ejemplo mínimo de `init/run/status/resume/report` probado.
2. JSON + Markdown de una campaña real con la definición exacta de ocupación, χ⁰, χ, U por sitio, diagnósticos, estado y costo.
3. Tabla de regresiones: NiO archivado, material independiente archivado, campaña nueva, fixture Slurm y fallos adversos.
4. Lista breve de capacidades fuera de v1 (`Ueff_Dudarev` automático, J, V funcional, spin–orbit/no colineal, presets universales) sin disfrazarlas como defectos del cálculo de carga.

Si una puerta obligatoria no pasa después de las correcciones acotadas, el estado final será `PRODUCT_BLOCKED`, con un único bloqueo reproducible y el mínimo trabajo necesario para reabrirlo. Nunca se anunciará `PRODUCT_READY` porque se agotó el tiempo o porque un U coincidió con literatura.

### Encargo único para los agentes después de autorizar ejecución

> Ejecuten P0→P6 de este documento. Luna controla los cambios y la única campaña SIESTA; Sol hace una auditoría puntual del contrato científico y del diff correspondiente, con esfuerzo conforme a la instrucción vigente del usuario. Cada auditoría devuelve `APTO`, `CORRECCIÓN LOCAL` o `BLOQUEO` con evidencia y no se repite si el contrato no cambió. Respeten las puertas, dos correcciones por falla, el presupuesto de 13 nodos en la ruta primaria o 25 en la alternativa de P5 y los estados terminales. No amplíen el alcance para perseguir un U concreto. Entreguen `PRODUCT_READY` o `PRODUCT_BLOCKED` con evidencia verificable.

## Fuentes metodológicas del contrato

- [Cococcioni y de Gironcoli, método de respuesta lineal](https://arxiv.org/abs/cond-mat/0405160): exige coherencia entre respuesta y definición de la ocupación localizada.
- [Manual SIESTA 5.4, DFT+U](https://docs.siesta-project.org/projects/siesta/en/5.4/reference/siesta.html): define proyectores y el uso de `Ueff=U-J` en la ruta colineal.
- [Tutorial oficial ABINIT LRUJ](https://docs.abinit.org/tutorial/lruj/): muestra comparación de regresiones lineales/polinómicas y sus residuos; no fija umbrales universales para SIESTA.
