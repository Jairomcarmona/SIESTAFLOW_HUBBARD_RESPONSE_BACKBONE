# Plan de cierre del flujo independiente: DAG y U de respuesta

**Revisión del plan:** 2026-09-28 · **Estado:** fases A–C ejecutadas; integración y prueba operacional completadas.  
**Alcance autorizado:** fases A–C de §5, incluido el controlador adaptativo, la integración Slurm/históricos, pruebas sintéticas y una comprobación operacional SIESTA pequeña en WSL al cierre. Se limita a un proceso SIESTA simultáneo y hasta cuatro rangos MPI en la laptop. No incluye barridos exploratorios ni integración al orquestador general.

**Resultado de esta ejecución:** controlador adaptativo y rutas Slurm/históricas conectados al analizador común; pruebas sintéticas focales y auditoría puntual completadas; campaña operativa NiO PBE ejecutada en WSL con un solo SIESTA activo y 4 ranks. El DAG terminó con 11 nodos validados y produjo JSON v2 e informe Markdown. La expansión de α queda condicionada a una sonda SCF con medida de ruido válida y umbrales explícitos por campaña; no se activa automáticamente por defecto ni se deducen tolerancias de NiO.

**Decisión de arquitectura vigente:** `siestaflow_hubbard` seguirá siendo un paquete científico independiente, con su propio CLI. Esta tarea no lo integra al repositorio general `siestaflow` ni a otro orquestador. La modularidad se conserva mediante contratos internos estables entre CLI, ejecución, análisis y reporte, para dejar abierta una integración futura sin acoplarla ahora.

## 1. Resultado que debe obtener el usuario

Con una campaña configurada para un material y un conjunto explícito de subespacios correlacionados, el CLI independiente permite actualmente:

```text
siestaflow init material.fdf --name MATERIAL --lr-config respuesta.json --profile local-wsl.json
siestaflow run campaign.siestaflow.json
siestaflow status campaign.siestaflow.json
siestaflow resume campaign.siestaflow.json
siestaflow report campaign.siestaflow.json
siestaflow stop campaign.siestaflow.json
```

Esta es la interfaz pública ya registrada en `pyproject.toml`; `init` crea campañas v2 de malla fija o con política adaptativa, `run` y `resume` controlan el trabajador persistente en WSL, `status` consulta su estado, `stop` solicita una detención segura y `report` regenera/imprime el informe desde el análisis guardado. El reporte v2 muestra el candidato numérico o la causa precisa por la que no pudo calcularse.

**Uso final esperado:** el usuario opera el paquete desde PowerShell sin abrir Codex ni editar FDF durante la campaña. El perfil local invoca SIESTA en WSL mediante un lanzador persistente; la prueba operacional del 2026-09-28 confirmó que el trabajo siguió ejecutándose tras volver el control a PowerShell y que `status` consultó el estado durable. El CLI devuelve identificador de campaña/trabajo, fallos concretos y resultados.

El alcance es **todo material y cualquier número de sitios correlacionados** que cumpla el contrato de entrada. NiO y MnO son casos de regresión, no fuentes de constantes, umbrales o valores de U para el algoritmo. Los rangos MPI se configuran en el perfil y se validan contra los recursos expuestos por el runtime; para esta laptop el perfil puede fijarse en hasta cuatro rangos. Se conserva una sola ejecución SIESTA simultánea por espacio de trabajo. Slurm debe usar los recursos declarados por su perfil, sin límites de laptop codificados en la matemática.

El perfil local declara distribución WSL, ejecutable/versión en Linux, mapa de rutas Windows↔WSL, directorio de trabajo y límites MPI/concurrencia. Las rutas Slurm e históricas y la operación Windows→WSL quedaron conectadas y verificadas en esta ejecución.

### 1.1 Prioridad operativa: ejecutar simulaciones

En una campaña autorizada, la **prioridad 1 es iniciar y completar los cálculos SIESTA pendientes**. La trazabilidad se registra de forma automática y proporcional al riesgo; no se convierte en una serie de revisiones manuales antes de cada trabajo. La ruta crítica antes del lanzamiento contiene sólo: FDF/funcional/pseudopotenciales compatibles, entradas presentes, política de α y recursos válidos, y un identificador inmutable de la configuración de entrada calculado **una sola vez por versión de campaña**. Superados esos controles, despachar el primer cálculo sin esperar al reporte, a comparaciones con literatura, a una auditoría de todos los archivos históricos ni a la revisión humana de hashes.

Al terminar cada trabajo, el DAG registra automáticamente estado y procedencia de sus salidas; el análisis, el reporte y sus hashes se producen después del cálculo que los alimenta. En `resume` sólo se comprueba la evidencia de los nodos que se pretende reutilizar, una vez por reanudación; se recalcula la huella únicamente si falta, cambió el archivo o lo exige la validación de ese nodo. No volver a recorrer ni recalcular hashes del árbol completo por cada α, transición o intento. Un fallo de integridad de un artefacto requerido sí impide reutilizar **ese nodo** y obliga a rehacerlo junto con sus descendientes, sin detener los trabajos independientes listos para ejecutarse.

## 2. Estado del paquete al cierre de este plan

La ruta v2 de malla fija ya existe. El plan de implementación empieza desde ese código y no vuelve a proponer construir el CLI o el informe desde cero.

| Área | Estado actual | Trabajo restante |
|---|---|---|
| Ajuste y análisis v2 | Analizador común lineal/polinómico con matrices, diagnósticos y candidatos por sitio en JSON. | Calibrar valores predeterminados de tolerancias con casos diversos; no se infieren de NiO. |
| DAG de campaña | Trabajador persistente WSL, ejecución serial, refinamiento por rondas, presupuesto, recibos y reanudación selectiva. | Ninguna función estructural bloqueante; completar calibración científica de políticas de campaña antes de recomendar presets. |
| CLI independiente | `init`, `run`, `status`, `resume`, `report`, `stop` y `audit-fdf` disponibles; probado desde PowerShell→WSL. | Mantener como interfaz propia del paquete; sin integración con el orquestador general en este alcance. |
| Persistencia y recursos | Perfil configurable, validación contra CPU de WSL y una ejecución SIESTA simultánea; campaña regresó a `status=COMPLETED`. | Ninguna pendiente para el caso local verificado; WSL shutdown/reinicio requiere `resume`, como documenta el quickstart. |
| JSON y reporte humano | JSON v2 y `LR_U_REPORT.md` generados; el comando público `report` se verificó y sus archivos se conservaron en la carpeta de campaña. | La política `linear` del smoke test de dos amplitudes es sensible; no constituye validación de un ajuste cúbico. |
| Refinamiento adaptativo de α | Política versionada, decisiones, rondas, probes, presupuesto y DAG dinámico integrados; pruebas sintéticas completadas. | Expansión exterior sólo cuando la sonda SCF cuantifica ruido de forma comparable y la campaña declara umbrales; esos umbrales no se suministran como constantes universales. |
| Slurm y rutas históricas | Adaptadas al analizador y reporte comunes, con recibos y validación de observaciones. | Ninguna integración pendiente dentro de las fases autorizadas. |
| Integración externa | No forma parte de esta entrega. | Ninguna conexión al repositorio general `siestaflow`; dejar una interfaz modular para una integración futura. |

La fuente canónica del paquete es `src/siestaflow_hubbard`. Antes de editar, el ejecutor revisa sólo los archivos y cambios que vaya a tocar, conserva modificaciones existentes y evita copiar código de campañas históricas como implementación paralela. No se requiere inventario o recálculo general de hashes para comenzar esta tarea de software.

### 2.1 Estado de las dos tareas registradas previamente

| Documento previo | Estado | Aplicación a este plan |
|---|---|---|
| `ADAPTIVE_ALPHA_GRID_IMPLEMENTATION_TASK.md` | Integrado en el DAG y verificado con pruebas sintéticas. | Mantener la calibración de ruido/tolerancias como configuración explícita antes de habilitar expansión en campañas reales. |
| `PENDING_HUMAN_READABLE_RESULTS_EXPORT.md` | JSON v2 y Markdown canónico generados y verificados por el CLI público en campaña operativa. | Mantener Markdown como formato canónico; `.txt`/`.out` sigue siendo opcional. |

Los documentos originales se conservan como registro de requisitos. Si algún criterio allí menciona las antiguas «puertas de aceptación», aplicar la distinción de §3.2: los controles de datos, rama electrónica y álgebra siguen vigentes; la intersección de tres ventanas lineales pasa a ser diagnóstico, no veto para mostrar un candidato numérico.

## 3. Contrato científico y regla de reporte

Para cada sitio perturbado (J), sitio observado (I) y modo BARE/SCREENED, ajustar sobre amplitudes declaradas antes de ver el resultado:

\[
n_I(\alpha_J)=c_0+c_1\alpha_J+c_2\alpha_J^2+c_3\alpha_J^3,
\qquad
\chi^0_{IJ}=c_{1,\mathrm{BARE}},\quad
\chi_{IJ}=c_{1,\mathrm{SCREENED}}.
\]

Con filas = sitios observados y columnas = sitios perturbados, invertir matrices completas bajo la representación declarada:

\[
K=(\chi^0)^{-1}-\chi^{-1},\qquad U_I=K_{II}.
\]

Mantener los términos fuera de la diagonal en el JSON como elementos del núcleo de respuesta; **no etiquetarlos automáticamente como (V)** de otro funcional. La magnitud obtenida con ocupaciones de carga sumadas en espín se identificará como `U_scalar_charge`. Su transferencia a `Ueff_Dudarev` requiere un contrato físico separado; un informe de U numérico no autoriza por sí mismo escribir `DFTU.proj` para producción.

### 3.1 Selección del estimador, aplicable a cualquier material

1. Declarar en una política versionada `auto`, `polynomial` o `linear`. La opción `auto` será el valor por defecto **en campañas nuevas**, sin cambiar silenciosamente la interpretación de campañas congeladas.
2. Para una malla centrada con al menos cinco amplitudes distintas, signos positivo y negativo, diseño de rango completo y al menos un grado de libertad residual, `auto` usa la **cúbica de grado 3** ya implementada. En siete puntos conserva tres grados residuales. Ajustar BARE y SCREENED con la misma política y todos los canales requeridos.
3. Cuando esos requisitos no se cumplen, `auto` declara `linear_fallback` y explica la causa; nunca finge haber hecho un ajuste cúbico ni rebaja el grado sin registrarlo. Un modo `polynomial` solicitado explícitamente falla de forma clara si la malla no lo soporta.
4. Calcular, sobre **los mismos puntos**, el estimador lineal de comparación. Si la malla permite ventanas simétricas más estrechas con suficientes grados residuales, calcular también sus derivados en cero. Registrar grado, coeficientes, residuos, DoF, condición del diseño y amplitudes usadas por canal.
5. Elegir modelo y malla mediante reglas declaradas antes de la campaña; la cercanía a literatura, gap, red o momento magnético no entra en la selección. No promediar valores de U entre modelos, ventanas o sitios.

El estimador cúbico entrega una derivada en α = 0, no una prueba automática de que todos los puntos pertenezcan a la misma rama electrónica. La validación de convergencia SCF, continuidad magnética y procedencia de la respuesta es independiente del ajuste.

### 3.2 Sustituir el veto de intersección por diagnóstico transparente

La intersección de intervalos de tres ventanas lineales deja de ser condición necesaria para **mostrar** un candidato. Conservar los tres valores como `window_sensitivity_eV` y el contraste cúbico/lineal como `model_sensitivity_eV`. Las cotas por redondeo de ocupaciones impresas se registran como `printing_rounding_bound_eV`; no se llaman intervalos de confianza ni se suman a una incertidumbre total no justificada.

Estados propuestos para el resultado común:

| Estado | Condición | Salida |
|---|---|---|
| `NUMERICAL_CANDIDATE` | Datos validados, misma rama electrónica, diseño e inversas válidas; diagnósticos dentro de la política. | (U_I), matrices, sensibilidad y limitaciones. |
| `NUMERICAL_CANDIDATE_SENSITIVE` | Se puede invertir y calcular (U_I), pero ventana/modelo/ruido excede un umbral declarado o no hay ventana lineal admitida. | (U_I) visible, diferencias y motivos; ninguna aceptación física automática. |
| `NO_SINGLE_STATE_U` | Cambio de estado magnético/electrónico entre perturbaciones utilizadas. | Curvas y diagnóstico; no un único U obtenido mezclando estados. |
| `NO_NUMERICAL_U` | Observaciones incompletas o inválidas, matrices de rango insuficiente o inversión fallida. | Razón exacta y evidencia disponible; campo U nulo. |

Los umbrales de sensibilidad pertenecen a una política versionada, con unidades y justificación; no se ajustan usando el resultado de NiO. Si no existe un límite de ruido SCF cuantificado, reportar `noise_not_quantified` y evitar una precisión física ficticia. La compatibilidad entre sitios se reporta separadamente. Un `U_common_scalar` sólo se emite si una política física de equivalencia de sitios y una regla de agregación explícita lo respaldan; siempre se preservan los (U_I).

La evaluación del nodo de amplitud puede terminar correctamente aunque su conclusión sea `no_linear_window`. El DAG debe avanzar a `MATRIX_ANALYSIS` para producir el candidato sensible o el diagnóstico final. Fallos de ejecución, salidas incompletas, procedencia inválida y cambios de rama siguen teniendo estados propios y no se convierten en un `PASS` científico.

### 3.3 Refinamiento adaptativo de α como parte del DAG

**Elección recomendada para v1:** mantener una malla simétrica inicial de siete amplitudes `{-3h, -2h, -h, 0, h, 2h, 3h}` y el ajuste cúbico como estimador principal cuando el diseño sea válido. Cada ronda y cada dirección posible (`shrink`/`expand`) deben tener en la política una ventana activa, grado y grados de libertad mínimos propios; los puntos fuera de la ventana se conservan como diagnóstico y no entran silenciosamente en el estimador activo. Para esta malla predeterminada, la ruta `shrink` añade `±h/2` y usa `|α|≤2h` en la primera ronda; después añade `±h/4` y usa `|α|≤h`. Así cada estimación activa conserva siete puntos, mientras que los puntos exteriores siguen disponibles para medir sensibilidad. En una malla distinta, la política debe declarar explícitamente la secuencia de puntos nuevos y las ventanas activas para cada rama.

La ruta `expand` añade pares exteriores predeclarados y sólo los incluye en la ventana activa de la ronda que los calcula. **No se expande α por una señal débil, un residuo bajo o una sonda SCF aislados.** Se requiere una medida empírica de sensibilidad numérica SCF, comparación de canales/vectores equivalentes, una predicción de señal frente al ruido de ocupación/SCF dentro de los límites de la política y evidencia de continuidad de rama. Si no existen los predicados y umbrales versionados necesarios, la acción es cerrar como candidato sensible; no expandir ni declarar estabilidad. Aplicar cada par aceptado a todos los sitios/modos. Dos rondas añaden como máximo cuatro valores α: 11 en total desde una malla inicial de siete, más los trabajos puntuales de comprobación SCF si se activan. Este límite de rondas es un **tope de costo v1**, no una constante física; puede elevarse explícitamente en el perfil de campaña.

La escala `h` debe declararse o seleccionarse por un preset visible. Como semilla para probar, `alpha_seed_span_eV = 3h = 0.1 eV` es razonable: ABINIT usa 0.1 eV por defecto y reporta un rango lineal amplio en sus pruebas. Ese dato depende de ABINIT/PAW y no demuestra que 0.1 eV sea óptimo para SIESTA; por eso se registra como semilla configurable, se examinan simetría y no linealidad, y no se codifica como verdad universal. Si existe una malla explícita y validada en el manifiesto, se conserva. `alpha_ceiling_eV` es una **cota distinta** que debe superar la semilla cuando la expansión esté habilitada; en otro caso, el controlador no propone pares exteriores.

La literatura LR-U recomienda varias perturbaciones pequeñas de ambos signos y advierte que amplitudes grandes pueden introducir no linealidad/asimetría. No fija siete puntos, dos rondas ni un porcentaje universal de estabilidad. Esos tres elementos son decisiones transparentes de ingeniería para una primera política acotada; el trabajo de diferencias finitas adaptativas aporta el principio de equilibrar truncamiento y ruido, no una receta específica para U.

En cada ronda, comparar estimaciones obtenidas con la **misma familia de ajuste y regla de selección de ventana** fijadas en la política. La firma comparable incluye método/grado, DoF mínimo, regla de selección, política de matriz y nivel SCF; la ventana activa concreta puede cambiar según la rama/ronda predeclarada y se reporta como variable de refinamiento, no como cambio de método. Si se cambia la regla o el nivel SCF de las observaciones usadas, reiniciar el contador de comparaciones estables; no contar un cambio de método como evidencia de convergencia. Conservar ajustes de ventana central/completa, el lineal sobre los mismos datos y sus residuos como diagnósticos. La decisión no se toma por el menor RMS de un único ajuste. Un predicado de truncamiento compara los `U_I` de las ventanas activa e interior con la misma política; sus tolerancias absoluta/relativa pertenecen a la campaña y sus unidades se informan. Sin umbral configurado, la evidencia se reporta como sensibilidad y no autoriza `shrink` automático. Para cada sitio, calcular el mayor cambio absoluto de `U_I` entre rondas comparables y contrastarlo con una tolerancia mixta:

```text
delta_U(r) = max_I |U_I(r) - U_I(r-1)|
tol_U(r)   = max(tol_abs_eV, tol_rel * max_I |U_I(r)|)
```

`STOP_STABLE` exige que `delta_U <= tol_U` en **dos comparaciones interronda consecutivas**, rama electrónica/magnética consistente, matrices utilizables y sensibilidad ventana/modelo que no empeore más que su tolerancia configurada. Por lo tanto, hacen falta la malla inicial y dos refinamientos comparables; una política con menos de dos rondas posibles no puede emitir `STOP_STABLE`. La forma absoluta-relativa sigue el patrón usado por software numérico para controlar errores a distintas escalas; no existe en la literatura un porcentaje universal que certifique el U físico. Por ello `tol_abs_eV`, `tol_rel` y tolerancias de ventana pertenecen a una política versionada: el preset por defecto debe calibrarse con una batería de sistemas y convergencias independiente de NiO, y el informe debe imprimir sus valores exactos. Si una tolerancia o un predicado necesario no está configurado, no se afirma estabilidad ni se activa una refinación que dependa de ese criterio; se conserva el candidato como sensible.

El controlador no interpreta el RMS del ajuste como incertidumbre física. Presenta por separado sensibilidad al modelo/ventana, límite por redondeo de ocupaciones y sensibilidad a la convergencia SCF. Si esta última no se ha medido, lo marca como `noise_not_quantified`; puede informar convergencia respecto a la malla de α, pero no afirmar una incertidumbre numérica total.

**Comprobación puntual durante la misma campaña:** después de la malla inicial, si los trabajos SCF convergieron pero la norma del cambio de ocupaciones de una columna entre `+h` y `-h` queda cerca de la resolución impresa según `probe_trigger_ratio` de la política, repetir sólo el punto de referencia y ese par simétrico con el siguiente nivel SCF más estricto, predeclarado en la política. Comparar, por separado para BARE y SCREENED, los vectores de respuesta con el mismo orden de sitios y la misma amplitud; registrar la norma, la resolución de impresión del vector y la diferencia entre niveles. La diferencia es una **medida empírica de sensibilidad al criterio SCF**, no una cota rigurosa de error de U. No comparar cambios escalares incompatibles ni interpretar el máximo cambio de ocupación como error de U. Limitar la comprobación a una vez por columna afectada y contabilizar todos sus nodos en el presupuesto; los resultados del nivel estricto no se mezclan con los anteriores para ajustar una misma matriz. Si se adopta el nivel estricto para el U final, rehacer de forma consistente los puntos utilizados por las matrices de respuesta, conservando los recibos previos como evidencia. Una salida SCF no convergida sigue la ruta normal de fallo/reintento y no se usa como sonda de ruido.

Para fijar la comparación de la sonda, por columna J y modo m ∈ {BARE, SCREENED}, definir `v_m^L(J,h)=n_m^L(J,+h)-n_m^L(J,-h)` y `eta_m(J)=||v_m^strict-v_m^base||₂`. `eta_m` es sensibilidad empírica de la respuesta al nivel SCF. La resolución del vector diferencia se deriva de los intervalos de redondeo validados de ambos vectores; si éstos no están disponibles, la sonda queda `noise_not_quantified`. La activación/materialidad de la sonda se evalúa por separado por modo con ratios configurados, nunca con el máximo de una componente aislada. Para proponer expansión hasta `a`, estimar `rho_m(J,a)=(a/h)||v_m^strict||₂/(eta_m(J)+q_m(J))`, donde `q_m` es la cota determinista de redondeo del vector diferencia. `REFINE(expand)` requiere un `rho_min` explícito y que los modos/columnas requeridos lo cumplan, además de la cota α y la continuidad de rama. Como la malla y las matrices de respuesta comparten α para todos los sitios, una expansión global requiere métricas completas para todas las columnas y ambos modos; una sonda parcial puede activar mejora SCF para las columnas afectadas, pero no autoriza expandir las demás. Esta proyección lineal sólo decide si merece medirse el nuevo par; no prueba que la respuesta siga lineal fuera de la malla existente, lo que debe verificarse con los datos de la ronda siguiente.


La política versionada fija antes de ejecutar la tolerancia, la escala inicial permitida, máximo de rondas/puntos, presupuesto y manejo del ruido. No se eligen puntos por cercanía a literatura. El presupuesto se cuenta como **nodos SIESTA adicionales reales** tras expandir las amplitudes por sitios y modos; el DAG no inicia una ronda incompleta si su costo excede el remanente. No se promedian U entre sitios.

En cada ronda, el controlador además revisa residuos, DoF, condición del diseño, convergencia SCF, estado magnético y rango/condición de χ₀ y χ. Debe registrar una de estas decisiones con motivo, entradas y presupuesto consumido:

| Decisión del controlador | Acción del DAG |
|---|---|
| `PROBE_SCF` | Reservar y ejecutar sólo los nodos de sonda autorizados por política; persistir antes el recibo/ID idempotente de la sonda y su costo. Tras validar resultados, reevaluar la política. |
| `STOP_STABLE` | Concluir sólo al pasar dos comparaciones interronda consecutivas bajo tolerancias explícitas, con controles de rama, matrices y sensibilidad satisfechos; requiere dos refinamientos posibles. |
| `REFINE` | Registrar dirección `shrink` o `expand`, ventana activa/grado/DoF, predicados y valores que la justifican; `expand` requiere sensibilidad SCF empírica medida y criterio de señal/ruido predeclarado. Añadir un par simétrico dentro de los límites, materializar sólo sus FDF y ejecutar sólo las respuestas faltantes. |
| `IMPROVE_SCF_FIRST` | Si la comprobación revela sensibilidad SCF material, adoptar sólo un nivel más estricto preconfigurado y rehacer los puntos necesarios para analizar una matriz bajo condiciones consistentes; si no cabe en el presupuesto, detener y reportar la limitación. |
| `STOP_LIMIT_SENSITIVE` | Agotar presupuesto o rondas sin estabilidad: cerrar como **no resuelto en estabilidad**, conservar y mostrar cualquier candidato numérico con su sensibilidad. |
| `STOP_INVALID` | Detener por datos inválidos, cambio de rama o matriz no utilizable; indicar la causa exacta y no mezclar estados. |

Un buen residuo no equivale a estabilidad ni aceptación física. `STOP_LIMIT_SENSITIVE` y `NUMERICAL_CANDIDATE_SENSITIVE` pueden coexistir: el primer estado expresa la decisión de campaña; el segundo, que sí se pudo calcular una estimación de U. La política, ventanas activas, nivel SCF, presupuesto y decisiones se congelan/versionan. Cada transición de ronda se persiste atómicamente antes de despachar nodos; la identidad durable de cada nodo incluye campaña/política, α, sitio, modo BARE/SCREENED, nivel SCF y DM padre pertinente. Las referencias compartidas se deduplican y se contabilizan una sola vez. `resume` debe reconstruir la misma decisión y no repetir puntos, sondas ni costo ya comprometidos. La convergencia en α no certifica convergencia con tamaño de supercelda, funcional, pseudopotencial ni definición del proyector; son controles físicos independientes.

## 4. Contrato de entrada y salida del DAG

### Entrada de campaña nueva

El manifiesto v2 existente declara FDF efectivo e `include` resueltos, estructura, sitios/subespacios correlacionados y sus proyectores, pseudopotenciales, funcional, estado magnético de referencia, malla α fija, política de estimador, validación, identidad de SIESTA y perfil de ejecución. Para la extensión adaptativa, añadir una versión de esquema que declare además la **política de refinamiento y presupuesto**; el resultado adaptativo debe ser versionado de manera compatible con JSON v2. No cambiar silenciosamente el significado de campañas fijas. No inferir el subespacio por el nombre del material. Si el FDF y la procedencia del pseudopotencial declaran funcionales incompatibles, bloquear antes de lanzar SIESTA; esto evita repetir la mezcla LDA/PBE.

El adaptador SIESTA debe entregar observaciones normalizadas `ResponseObservation` con etiquetas de sitio estables, modo BARE/SCREENED, amplitud, ocupaciones, DM padre, salida y recibo de validación. El análisis consume **únicamente** observaciones verificadas; esa verificación ocurre cuando la salida se consume, no como auditoría reiterada antes de lanzar otras simulaciones independientes. El perfil local declara `mpi_ranks` según los recursos expuestos por el runtime y `max_concurrent_siesta = 1`; Slurm usa el perfil de la instalación, sin codificar valores de la laptop en la matemática.

El supervisor tendrá un registro durable de campaña, lock para impedir dos controladores sobre el mismo DAG, identificador de proceso/trabajo y heartbeat. Si el proceso termina durante un nodo, `status` lo reporta como interrumpido; `resume` archiva el intento parcial y reintenta sólo ese nodo desde entradas validadas. No asumir que un PID antiguo sigue vivo únicamente porque aparece guardado en disco. Los gates deterministas del DAG requieren handlers locales propios; no se envían como si fueran comandos SIESTA.

### Salida canónica por campaña

`results/lr_u_analysis.v2.json` ya es la fuente para el DAG fijo y los reportes. Para campañas adaptativas se conserva el contrato v2 cuando la extensión resulte compatible; si requiere campos o semántica incompatibles, se publica una versión nueva en lugar de cambiar el significado de v2. Campos mínimos del resultado completo:

```text
schema_version, campaign_id, material, functional, quantity,
site_labels, alpha_grid_eV, estimator_policy, selected_estimator,
chi0_raw, chi_raw, matrix_for_inversion, U_matrix_eV,
U_by_site_eV, U_common_scalar_eV_or_null,
fit_diagnostics_by_channel, window_sensitivity_eV,
model_sensitivity_eV, printing_rounding_bound_eV,
scf_and_magnetic_diagnostics, matrix_diagnostics,
alpha_rounds, refinement_policy, refinement_decision,
scf_probe_trigger_and_pairs, scf_levels_and_occupation_deltas,
cost_budget_and_consumption,
numerical_status, physical_acceptance, reasons, provenance
```

Todos los campos numéricos no disponibles serán `null` con causa explícita; no usar `NaN` en JSON. `results/LR_U_REPORT.md` será el **formato legible canónico v2** y se genera desde ese JSON. La tabla debe identificar material, campaña, funcional, observable, valor y unidad, método/estimador, referencia de comparación cuando exista, sensibilidad por origen, estado de reportabilidad y acción permitida por el DAG. Una sección por sitio muestra U, amplitudes, ajustes y estado; otras observables sólo aparecen si están en el JSON, sin inventar referencias. El encabezado registra pseudopotenciales, archivos fuente, hashes, versión del analizador y si cada dato es canónico o candidato. Se puede añadir `.txt`/`.out` como vista derivada posterior, sin crear otra fuente de verdad. El JSON conserva curvas, matrices y fuentes. La exportación es idempotente, registra hashes de entrada/salida y no invoca SIESTA ni envía trabajos a Slurm.

El contrato `tools/scientific_dag_analysis.py` registrará el resultado numérico como `RECORDED_ONLY` y `physical_acceptance=NOT_ESTABLISHED`, salvo que una política física distinta demuestre explícitamente más. `tools/scientific_dag_gate.py` conservará el vínculo hash del JSON, el veredicto y el Markdown. Las campañas antiguas mantienen sus esquemas y veredictos originales; la versión nueva no reescribe NiO v1/v2, MnO ni sus recibos.

## 5. Secuencia de trabajo restante

El refinamiento se aplica como extensión versionada del flujo existente; conserva compatibilidad con campañas fijas y manifiestos anteriores.

### Fase A — Controlador adaptativo de α y DAG por rondas (completada)

- Añadir un esquema versionado para la política adaptativa. Implementar como propuestas por defecto la malla simétrica de siete puntos y un máximo de dos rondas que añaden un par interior o exterior (hasta once amplitudes); `h`, ventanas activas por ronda/dirección, grado/DoF, `alpha_seed_span_eV`, `alpha_ceiling_eV`, `probe_trigger_ratio`, predicados/umbrales de señal-ruido y tolerancias, escalera SCF y presupuesto total deben quedar configurables y visibles. La semilla de 0.1 eV requiere validación para SIESTA antes de anunciarse como valor predeterminado del producto.
- Calibrar el preset de `tol_abs_eV`/`tol_rel` y tolerancias de ventana en casos diversos con datos de respuesta conocidos y convergencia numérica; no deducirlo sólo de NiO ni copiar la tolerancia por defecto de otra biblioteca. Si esa calibración aún no existe, exigir una política explícita para activar `STOP_STABLE`/refinamientos basados en tolerancia y permitir cerrar por presupuesto como candidato sensible.
- Implementar decisiones `STOP_STABLE`, `REFINE`, `IMPROVE_SCF_FIRST`, `STOP_LIMIT_SENSITIVE` y `STOP_INVALID` de §3.3. Cada decisión guarda los diagnósticos que la motivan y el costo restante.
- Al decidir `REFINE(shrink)`, requerir que la diferencia de U entre ventanas interior/activa supere el umbral de truncamiento versionado; elegir el grado y puntos usados según la ventana activa congelada. Al decidir `REFINE(expand)`, exigir una sonda SCF validada, métrica señal/ruido de canales equivalentes, tolerancias configuradas y continuidad de rama. Si falta un predicado, cerrar como sensible. Añadir el par simétrico correspondiente dentro de los límites declarados, materializar sólo los FDF aún ausentes, expandir antes el par a todos los sitios/modos y comprobar el costo completo de la ronda. La nueva ronda conserva nodos y recibos todavía válidos; `resume` vuelve a ejecutar únicamente el trabajo incompleto o invalidado y sus descendientes.
- Implementar `PROBE_SCF` de §3.3 como nodos diagnósticos de una sola activación por columna afectada, sin rehacer la campaña completa para medir sensibilidad. Su recibo identifica referencia, par ±α, vectores BARE/SCREENED comparables, nivel SCF, resolución impresa, diferencia empírica y decisión. Si se contempla una expansión global de α, completar las sondas para todas las columnas/modos requeridos o cerrar sin expandir. Contar el costo antes de despacharlos, deduplicar referencias compartidas y no reutilizar una respuesta de otro nivel SCF dentro del ajuste final.
- Si se admite una escalera SCF, versionarla y reaplicar el mismo nivel a todo el conjunto usado para comparar derivadas; nunca mezclar respuestas convergidas con criterios SCF diferentes sin anotarlo y rehacer el conjunto pertinente.
- Mantener independiente el estado del cálculo, el candidato numérico de U y la aceptación física. Una falta de estabilidad no borra un candidato calculable ni lo presenta como convergido.
- Preservar lectura de manifiestos/análisis de malla fija v2. La integración adaptativa debe usar una versión nueva o una extensión aditiva validada del esquema; no reinterpretar silenciosamente campañas anteriores. Persistir cada política/decisión de manera atómica antes de despachar trabajo; la identidad de nodo incluye política, ronda, α, sitio, modo, nivel SCF y DM padre pertinente.

**Entrega:** campaña adaptativa que decide continuar o terminar dentro del presupuesto, registra por qué y reutiliza las amplitudes válidas sin repetir sus SIESTA.

### Fase B — Adaptadores Slurm e históricos (completada)

- Conectar la plantilla Slurm al contrato común de observaciones, análisis y reporte; el adaptador envía los nodos científicos conforme al perfil del clúster y conserva el mismo JSON/Markdown que la ruta local.
- Adaptar `production_benchmarks/lr_arithmetic.py` y `campaign_controller.py` al analizador común. Las rutas históricas pueden convertir sus observaciones al contrato común, pero no mantener una fórmula o política de U paralela.
- Dejar esta fase desacoplada del CLI PowerShell/WSL: Slurm es otro backend del paquete autónomo, no una integración con el orquestador general SIESTAFLOW.

**Entrega:** mismo análisis reproducible en perfil local y Slurm a partir de observaciones equivalentes.

### Fase C — Verificación sintética y cierre operativo (completada)

- Cubrir ajuste lineal/cúbico, N=1/2/3, mallas de cinco/siete puntos, DoF insuficientes, cambio de rama, matrices singulares/mal condicionadas, diferencias por sitio, redondeo frente a sensibilidad, fallos de salida, refinamiento y límites de costo.
- Verificar `REFINE` con sólo FDF nuevos, estabilidad en rondas consecutivas, activación condicional de la comprobación SCF, expansión sólo después de una señal débil confirmada, consistencia del nivel SCF en las matrices, presupuesto que incluye los nodos diagnósticos, `STOP`/`UNRESOLVED` sin trabajos extra, interrupción/reanudación sin duplicar nodos, reporte idempotente y que cambios únicamente de reporte no recalculen SIESTA.
- Reproducir, sin SIESTA nuevo y con datos PBE existentes ya validados, aproximadamente 6.8684 eV (NiLR0) y 6.8638 eV (NiLR1) para `U_scalar_charge`. Investigar cualquier diferencia como cambio de datos, contrato o álgebra; no ajustar umbrales para forzar concordancia.
- Completar una comprobación operacional Windows→WSL desde PowerShell normal con un caso PBE pequeño basado en entradas existentes y auditadas: lanzar, cerrar la terminal, consultar `status`, recuperar con `resume` si aplica y generar JSON/reporte. En la laptop usar como máximo cuatro rangos MPI y un SIESTA simultáneo. Esta prueba acredita persistencia; las pruebas sintéticas por sí solas no lo hacen.
- Auditar una sola vez el contrato y el diff final. Según la instrucción vigente del usuario para esta integración, Luna GPT-6 máximo ejecuta y Sol GPT-6 alto revisa puntualmente los contratos o hallazgos concretos; no hay auditorías repetidas durante cada amplitud ni revisiones generales del repositorio.

**Entrega:** criterios científicos, de reanudación y de operación verificados; ninguna campaña nueva se lanza sólo por ejecutar pruebas del software.

## 6. Criterios de aceptación y límites

### Ya implementado en la ruta fija v2

- CLI independiente con `init`, `run`, `status`, `resume`, `report`, `stop` y `audit-fdf`, registrado como comando instalable.
- Campaña de malla fija con perfil MPI configurable, trabajador WSL persistente, ejecución serial, análisis JSON v2 y reporte Markdown generado desde los datos guardados.
- El reporte muestra dataset de ocupaciones, ajustes, matrices, diagnósticos, sensibilidad y procedencia; no necesita PDF ni dependencias pesadas.
- Verificación focal: las pruebas sintéticas del controlador/DAG/análisis común pasaron; pruebas dirigidas confirmaron `audit-fdf`, salida UTF-8 del puente y emisión segura en consola cp1252. La campaña operativa PBE se ejecutó con SIESTA/MPI y generó reporte JSON/Markdown.

### Criterios cubiertos al cierre de la integración

- El DAG decide `REFINE`/`STOP` con una política explícita y presupuesto, añade únicamente FDF nuevos y conserva recibos válidos entre rondas.
- Si una respuesta inicial queda cerca de la resolución, una comprobación SCF puntual y presupuestada permite decidir entre mejorar SCF, ampliar α dentro de su cota o cerrar con diagnóstico. La expansión requiere una medida de ruido y predicados configurados para todos los sitios/modos implicados; el reporte no presenta la diferencia de ocupaciones como cota rigurosa de error.
- Los candidatos invertibles por sitio se muestran aunque la estabilidad no esté demostrada; cambio de rama, datos inválidos o inversión imposible producen estado y causa propios. El reporte separa candidato numérico y aceptación física.
- La misma política y observaciones dan el mismo resultado en ejecución continua y tras `resume`. Modificar sólo el reporte no vuelve a ejecutar SIESTA.
- El controlador adaptativo y los resultados se versionan sin alterar manifiestos, datos o recibos de campañas fijas anteriores.
- El contrato general funciona para materiales y números de sitios distintos; NiO/MnO sirven como regresiones y no determinan constantes ni umbrales.
- La integración Slurm y las rutas históricas usan el analizador y el reporte comunes; el paquete sigue independiente y no depende del orquestador general SIESTAFLOW.
- La ruta Windows→WSL se verificó operacionalmente con una campaña SIESTA autorizada el 2026-09-28; el trabajo persistió después de volver el control a PowerShell.
- La ruta crítica de una campaña autorizada lanza el primer SIESTA tras los controles físicos mínimos de §1.1. Los hashes se registran automáticamente una vez por entrada/salida pertinente; no se inspecciona ni recalcula el árbol completo por cada nodo.

Una simulación real no es requisito para comprobar la matemática mediante entradas guardadas o adaptadores sintéticos, pero sí es necesaria para declarar demostrada la operación persistente Windows→WSL. La implementación no debe iniciar nuevas campañas durante las fases de software sin autorización expresa.

## 7. Ejecución y evidencia de cierre

La ejecución siguió `AGENTS.md`: Luna GPT-6 máximo implementó y ejecutó; Sol GPT-6 alto hizo una auditoría puntual del contrato adaptativo y del control científico previo a campaña. No se lanzaron barridos exploratorios ni se repitieron revisiones manuales de hashes.

- Las fases A–C quedaron implementadas y verificadas; el smoke test local PBE usó SIESTA 5.4.2, 4 ranks MPI y concurrencia máxima 1.
- El proceso de PowerShell terminó tras despachar el trabajador; comprobaciones posteriores confirmaron persistencia y `status=COMPLETED` con 11 nodos validados.
- El reporte del smoke test entrega `U_scalar_charge = 6.86087028 eV` por sitio y estado `NUMERICAL_CANDIDATE_SENSITIVE`. Como sólo usó α = ±0.025 eV y estimador lineal, el resultado verifica el cierre operacional/analítico del DAG, no estabilidad cúbica ni aceptación física.
- El smoke test evidenció la decodificación cp1252 del reporte en Windows; se corrigió el puente para leer UTF-8 y emitir texto seguro en consolas heredadas.
- Evidencia accesible: `campaigns/nio_pbe_cli_smoke_20260928/results/LR_U_REPORT.md` y `campaigns/nio_pbe_cli_smoke_20260928/results/lr_u_analysis.v2.json`.

No queda una decisión del usuario pendiente para cerrar el alcance autorizado. La expansión de α en materiales futuros deberá activarse sólo si una medida de ruido SCF comparable y umbrales explícitos de campaña permiten distinguir señal de ruido; de lo contrario, el DAG reporta candidato sensible y se detiene dentro del presupuesto.

## Referencias internas y metodológicas

- [Polynomial response fitting](RESPONSE_POLYNOMIAL_FIT.md): implementación actual y límites del ajuste.
- [Refinamiento adaptativo de α](ADAPTIVE_ALPHA_GRID_IMPLEMENTATION_TASK.md): requisitos incluidos en el controlador del DAG; su implementación y pruebas sintéticas no autorizan por sí mismas una campaña SIESTA nueva.
- [Informe legible de resultados](PENDING_HUMAN_READABLE_RESULTS_EXPORT.md): requisitos incorporados al reporte Markdown canónico v2.
- [Cococcioni y de Gironcoli, respuesta lineal](https://arxiv.org/abs/cond-mat/0405160).
- [Tutorial oficial ABINIT LR-U(J)](https://docs.abinit.org/tutorial/lruj/): precedente de regresión polinómica sobre múltiples perturbaciones.
- [MacEnulty et al., prácticas de LR-U/J](https://doi.org/10.1088/2516-1075/ad610f): amplitud, ruido, no linealidad y sensibilidad de la respuesta.
- [Shi et al., intervalo adaptativo para diferencias finitas con ruido](https://arxiv.org/abs/2110.06380): base numérica para equilibrar error de truncamiento y ruido; no es una regla física específica para calcular U.
- [Documentación oficial de SciPy `quad`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.quad.html): ejemplo de criterio de parada con tolerancias absoluta/relativa y límite de evaluaciones; su valor predeterminado numérico no se transfiere al estimador de U.

## Historial de implementación — actualizado 2026-09-28

Las fases A–C quedan cerradas. Además de las pruebas sintéticas focales, las pruebas dirigidas del `audit-fdf` PBE y del manejo UTF-8 del CLI pasaron; el smoke test generó informe Markdown/JSON y verificó la operación persistente Windows→WSL con una campaña SIESTA real de bajo costo. El alcance sigue independiente del repositorio general SIESTAFLOW. La calibración de tolerancias de política con familias de materiales y la selección de presets recomendados quedan como trabajo científico futuro, no como bloqueo de integración.
