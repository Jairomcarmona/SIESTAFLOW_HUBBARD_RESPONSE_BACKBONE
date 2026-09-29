# Registro de ejecución P0 — 2026-09-28

> **Cierre final P0–P6 — 2026-09-28.** Este addendum sustituye el estado histórico de bloqueo registrado más abajo, que precedió a la localización de los datos NiO. Las puertas operativas se ejecutaron, pero el objetivo científico que el usuario considera necesario para declarar listo el producto no se alcanzó. Estado terminal actual: **PRODUCT_BLOCKED**. El resultado P5 permanece `NUMERICAL_CANDIDATE_UNASSESSED` / `NOT_ESTABLISHED` y no establece un U útil/aceptado.

| Puerta | Estado | Evidencia verificable |
|---|---|---|
| P0 — congelar contrato | `PASS` | Campaña NiO histórica `99d5ee67-d9cf-41f1-9f8f-39315c6e81fd`: 41 pares `.out`/DM verificados; 948 cotejos matrix→`Occupations:` sin anomalías. Contrato R1 y ruta P5 NiO PBE de dos sitios, 25 nodos, fijados antes del cálculo. El FDF P5 coincide con SHA-256 `b4fb34e642d862be6949a5b2033a60c5b9fcae56119879583bb3eaf237620ee7`; PSML NiLR0/NiLR1 `192eb05ffb64671715e570e2ca9a99a551cf15544984592082d43004f8554e06`; O `224ded5c59176d9bcb76d19b7a4a68a48d5dffabf8b262f64d5760250e87c35e`. |
| P1 — fuente de ocupación | `PASS` | Esquema `siestaflow.lr_u_analysis.v3`; total del token `Occupations:` como observable primario para reference/BARE/SCREENED y su precisión del mismo evento. `trace_total` sólo como cotejo. Los artefactos v2 y reportes históricos quedaron intactos. |
| P2 — decisiones matemáticas | `PASS` | Replay v3 guardado por ronda: `REFINE`, `REFINE`, `STOP_STABLE`; final `NUMERICAL_CANDIDATE_UNASSESSED`, aceptación `NOT_ESTABLISHED`, por ausencia de tolerancia declarada de sensibilidad. Umbrales adaptativos persistidos sin cambios; tests de control adaptativo pasaron. |
| P3 — DAG, CLI e informe | `PASS` | Ruta pública `init/run/status/resume/report` para PowerShell→WSL y manifiesto Linux/Slurm; reporte no inicia worker. Pruebas focalizadas y auditoría independiente de P3 pasaron. |
| P4 — regresión sin SIESTA | `PASS` | Suite pública final: `677 passed, 29 skipped, 20 subtests passed` (14.43 s). Los skips tienen razón registrada: APIs BARE antiguas retiradas, generador NiO legacy incompatible con FDF fixtures históricos congelados, auxiliares POSIX ejecutados en Windows y calibración ligada a un release histórico cuyo hash no coincide con el workspace actual. Regresión archivada Cu1 v3 valida outputs/DM y conserva `FAIL_CLOSED_NO_AUTHORIZED_U`. |
| Auditoría Sol — antes de P5 | `APTO` | Auditor científico independiente, GPT-6 Sol / medium / read-only; revisión única de fuente, funcional de ajuste OLS vía QR, cotas, matrices, inversión y reporte. Reprodujo χ⁰, χ y U. Cota primaria cúbica de redondeo: `0.034362731047454464 eV`; la cota lineal diagnóstica es `0.013537118260117095 eV`. |
| P5 — campaña real final | `PASS` | Única campaña nueva UUID `73a0a508-93df-41e2-b1bd-993c3dc7d94a`, `/home/jmc/.local/state/siestaflow/campaigns/nio-pbe-p5-20260928`. Ejecutó `25/25` nodos SIESTA, 4 rangos MPI, serialmente; cero nodos duplicados. DAG total `27/27` con análisis. Sin cambios al FDF/PSML base ni ejecución simultánea adicional. |
| P6 — entrega | `PASS` | Wheel `dist/siestaflow_hubbard-0.1.2-py3-none-any.whl`, SHA-256 `e66ad3621e9f4c3f2ba42d2eb632878fc014bde9e38980f98eaf7c9ea30a610e`. Instalación limpia y `pip check` pasaron en Windows y WSL; `--help`, `audit-fdf`, `status`, `resume`, `report` ejercitados. `resume` conservó 27 nodos y no relanzó SIESTA. README, manual, quickstart y changelog alineados; reportes regenerados idénticamente. |

**Artefactos P5:** JSON `/home/jmc/.local/state/siestaflow/campaigns/nio-pbe-p5-20260928/results/lr_u_analysis.v3.json`; Markdown `/home/jmc/.local/state/siestaflow/campaigns/nio-pbe-p5-20260928/results/LR_U_REPORT.v3.md`. SHA-256 JSON `d9b76e3841c1da43e70a82a56fad9f69fb68ddd9726779a5643f0cf39b1860ba`; Markdown `f52f370f1ee6b7198ac27e9c7dc5748261ae5df33c80bc943c975c7e34138f1d`. `U_scalar_charge`: NiLR0 `6.864267700049239 eV`, NiLR1 `6.864387475210124 eV`; cota de redondeo de ocupación `±0.01183306193 eV` por sitio. La interpretación continúa `NUMERICAL_CANDIDATE_UNASSESSED` y `NOT_ESTABLISHED`.

**Estado terminal vigente: `PRODUCT_BLOCKED`.** La ejecución y entrega del paquete funcionan, pero la salida científica principal no llegó a un U establecido: P5 carece de un criterio predeclarado y justificado de estabilidad/ruido que permita interpretar el valor como resultado útil. Este bloqueo no se resuelve marcando el U como aceptado ni cambiando retrospectivamente α, tolerancias, proyectores, ventanas o criterios. Trabajo mínimo para reabrir: fijar antes de cualquier cálculo adicional un protocolo independiente de aceptación/ruido y su presupuesto; después volver a evaluar el contrato desde P0. Esta ejecución no autoriza una campaña adicional. No se usó concordancia con literatura como criterio.

> **Addendum de reanudación — 2026-09-28.** La revisión local de los 41 resultados NiO levantó el bloqueo previo. El resto de las secciones inferiores conserva el expediente inicial como antecedente; sus estados y decisiones de campaña quedan sustituidos por este cierre final.

## Decisiones y evidencia añadidas en la ejecución P0–P2

**Ruta única P5 fijada en P0 antes de cualquier campaña nueva:** no hay una entrada NiO de un sitio con configuración pública `lr-config.json` en los conjuntos locales inspeccionados; los dos candidatos NiO PBE tienen los sitios `NiLR0` y `NiLR1`. Se elige la alternativa NiO PBE de dos sitios con seis amplitudes simétricas no nulas `[-0.06,-0.04,-0.02,0.02,0.04,0.06] eV`, máximo `1+2×2×6=25` nodos SIESTA. FDF de referencia: `campaigns/nio_pbe_adaptive_20260928/reference_pbe.fdf`; PSML Ni/O y funcional PBE: las entradas ya empleadas por esa campaña, cuyos hashes de procedencia están en el resultado v3. La campaña nueva usará malla fija y el CLI público; no se editarán FDF ni PSML. Perfil: hasta 4 rangos MPI, una ejecución SIESTA concurrente. La campaña adaptativa histórica de 41 nodos no será la prueba P5.

**P2 reproducido con el observable v3 y sin SIESTA:** el replay volvió a verificar los mismos recibos/output/DM seleccionados y recalculó por ronda con `occupation_source=siesta_occupations_total`. Las rondas 0 y 1 entregan `REFINE/shrink` con adiciones `[-0.01,+0.01]` y `[-0.005,+0.005] eV`, respectivamente; sus mallas coinciden con las rondas persistidas. En ronda 2, dos comparaciones dan `ΔU=0.00375228894 eV`, menor que la tolerancia aplicada `0.06867064122 eV` (`tol_abs=0.05 eV`, `tol_rel=0.01`), y `STOP_STABLE` tiene precedencia sobre la métrica de truncación. Cierre: candidato `NUMERICAL_CANDIDATE_UNASSESSED`; aceptación física `NOT_ESTABLISHED`; presupuesto `41/41`. Esto sustituye sólo la decisión histórica para el análisis v3; los resultados y estado adaptativo v2 de WSL siguen intactos.

Artefactos v3 reproducibles: `campaigns/nio_pbe_adaptive_20260928/results/lr_u_analysis.v3.json`, `LR_U_REPORT.v3.md` y `alpha_rounds_v3/round-00..02/analysis.v3.json`. Las pruebas de la política ejecutadas por `implementador_luna`: `.venv\Scripts\python.exe -m pytest tests/unit/test_adaptive_alpha_control.py -q` → 11 passed. No se ejecutó SIESTA.

## Reapertura de P0 y contrato congelado

La campaña requerida está en `/home/jmc/.local/state/siestaflow/campaigns/nio-pbe-adaptive-20260928-v2`. El manifiesto `node-evidence.json` selecciona los 41 outputs SIESTA (1 referencia, 20 BARE y 20 SCREENED); la revisión de lectura verificó los hashes de los 41 outputs y sus DM padres. Esto resuelve la ausencia de datos que causó el bloqueo anterior. Los reportes históricos de la campaña permanecen sin cambios.

La fuente SIESTA 5.4.2 local, [`dftu.F`](../third_party/siesta-5.4.2-source-audit/Src/dftu.F), imprime la matriz en `f12.5`, acumula sus diagonales y después imprime `Occupations:` y `sum(oc)` en `f12.6`. En los 41 outputs se cotejaron 948 bloques de población matriz→`Occupations:` completos: error máximo por canal `2.2e-5`, bajo el límite de redondeo `2.55e-5`; error máximo en total `3.1e-5`, bajo `5.05e-5`; cero anomalías. Ejemplo reproducible: output de referencia, átomo 1, líneas 1010–1038: las trazas impresas suman `5.01139`, `3.01979` y `8.03118`; el resumen informa `5.011377`, `3.019776` y `8.031153` (diferencias `1.3e-5`, `1.4e-5` y `2.7e-5`).

**Decisión R1 congelada:** el total de `Occupations:` del evento seleccionado es el observable primario de referencia, BARE y SCREENED. Su semiancho se lee de sus tokens (`f12.6`; para el formato de dos canales sin total explícito, se suman los semianchos de los dos tokens). `trace_total` y la traza de matriz quedan únicamente como cotejo independiente: no alimentan los ajustes, `χ0`, `χ`, `U` ni la cota. El cambio de significado se publica como esquema `siestaflow.lr_u_analysis.v3` con `occupation_source=siesta_occupations_total`; los resultados v2 históricos no se reetiquetan.

P0 queda superada. P1/R1 reprocesó los mismos 41 outputs sin volver a ejecutar SIESTA y creó artefactos v3 con `occupation_source=siesta_occupations_total`; P2 volvió a analizar por separado las tres rondas y congeló su resultado `STOP_STABLE` dentro de la política declarada. Los artefactos históricos v2 y estado WSL permanecen sin cambios. P3 está en ejecución; P4–P6 aún no se han ejecutado. No se han cambiado α, tolerancias, proyectores, ventanas ni criterios; literatura no participa en la aceptación; P5 está seleccionada pero no despachada.

| Puerta | Estado vigente | Evidencia/razón |
|---|---|---|
| P0 — congelar contrato | `PASS` | Ubicación WSL recuperada; 41 pares output/DM verificados; cotejo 948/948 y fuente primaria R1 fijada arriba. |
| P1 — fuente de ocupación | `PASS` | Reprocesamiento de los 41 outputs publicado en JSON/Markdown v3 con `occupation_source=siesta_occupations_total`; v2 histórico intacto. |
| P2 — decisiones matemáticas | `PASS` | Tres decisiones reproducidas con la política original; `STOP_STABLE` por dos comparaciones dentro de tolerancia y las rondas 0/1 reducidas por la truncación declarada. |
| P3 — DAG, CLI e informe | `PASS` | CLI público Linux/Slurm acepta manifiesto directo dentro de la asignación; WSL conserva pointer/supervisor; `report` no inicia worker. Pruebas focalizadas 7 passed y verificación independiente 4 passed. |
| P4 — regresión sin SIESTA | `IN_PROGRESS` | Reproceso NiO v3 realizado; cerrando segundo conjunto real Cu1 y suite pública sin cómputo SIESTA. |
| P5 — prueba real final | `SELECTED / NO DESPACHADA` | Ruta alternativa NiO PBE de dos sitios; tope de 25 nodos. |
| P6 — entrega | `NOT STARTED` | El proyecto continúa en P1. |

---

**Plan rector:** [`EJE_RECTOR_CIERRE_PRODUCTO.md`](EJE_RECTOR_CIERRE_PRODUCTO.md), §§ 2–6.  
**Resultado:** `PRODUCT_BLOCKED` en P0.  
**Alcance ejecutado:** sólo inspección de P0. No se editaron código, configuración, entradas de campaña ni datos históricos; no se ejecutaron pruebas ni SIESTA.

## Decisión de P0

P0 no puede congelar el contrato de ocupación ni autorizar P1: falta el conjunto NiO PBE adaptativo de 41 salidas requerido para cotejar el orden de impresión y los eventos BARE/SCREENED. El conjunto alternativo Cu1 es evidencia de ejecución real e íntegra en sus nodos, pero su propio veredicto cierra el análisis sin autorizar χ, inversiones ni U, porque no tiene un límite externo de ruido de ocupación aplicable. No sustituye la evidencia científica NiO que P0 exige para la ruta primaria.

Por esta puerta fallida, **P1–P6 no se ejecutan**. En particular, no se inicia una campaña ni se invoca al auditor Sol: la auditoría prevista antes de P5 depende de completar P0–P4 y no se alcanza ese punto.

## Evidencia reproducible

1. **Fuente SIESTA 5.4.2.** En [`third_party/siesta-5.4.2-source-audit/Src/dftu.F`](../third_party/siesta-5.4.2-source-audit/Src/dftu.F), líneas 525–526, la matriz se imprime con formato `(2i4,2f12.5)`; líneas 534–538 acumulan las diagonales; líneas 541–544 escriben `Occupations:` y `sum(oc)` mediante `(a,/,a,3f12.6)`. Esto establece el código fuente local que se debe contrastar, pero no demuestra que los tokens sean del mismo evento físico que los archivos NiO ausentes.
2. **NiO requerido ausente.** El directorio [`campaigns/nio_pbe_adaptive_20260928`](../campaigns/nio_pbe_adaptive_20260928) contiene **0** archivos `*.out` y `*.DM` (conteo recursivo dirigido a esas extensiones). La misma serie de 41 salidas no se encuentra en `docs/evidence`. Hay otras carpetas de campañas NiO, pero son campañas distintas y no se usan como sustitución de datos.
3. **Cu1 archivado, alcance y estado.** [`final-verdict.json`](../docs/evidence/siesta542_openmpi_slurm_full_campaign_20260920_run2_wheel/final-verdict.json) registra `13_VALIDATED_NODES`, `FAIL_CLOSED_NO_AUTHORIZED_U` y `U_ev: null`; sus razones indican que no se declaró `occupation_noise` con justificación externa y que no se permite derivarlo de la malla observada, pruebas sintéticas o repetibilidad histórica de MnO. [`result.json`](../docs/evidence/siesta542_openmpi_slurm_full_campaign_20260920_run2_wheel/result.json) confirma `METHODOLOGY_LOCK_MISSING_EXTERNAL_OCCUPATION_NOISE_BOUND`, inversión `NOT_AUTHORIZED` y reconstrucción de matrices `NOT_AUTHORIZED`. La inspección del `artifact-manifest.json` encontró 450 entradas: 449 artefactos coinciden en tamaño y SHA256; la única discrepancia de tamaño corresponde a `FULL_CAMPAIGN_REPORT.md`. Los 13 nodos y sus salidas de ejecución están validados en el veredicto y resultado archivados. Esta discrepancia no convierte el resultado Cu1 en un U autorizado.
4. **Recursos registrados, no despachados.** El perfil Slurm archivado declara 4 CPU/rangos y SIESTA 5.4.2. La laptop expone un comando WSL y no un comando SIESTA nativo; la lectura de `Win32_Processor` fue denegada, así que no se atribuye un conteo de CPU local no verificado. No se lanzó trabajo alguno.

## Contrato y límites retenidos

- Se conserva como referencia la semántica histórica del esquema v2. Si el análisis posterior cambia la representación ajustada, el plan requiere `occupation_source` explícito y una nueva versión de esquema; `report` no debe reetiquetar números v2.
- La decisión de usar `Occupations:` como variable primaria queda **pendiente** del cotejo con los mismos eventos de los 41 `.out` NiO; no se infiere equivalencia sólo porque la fuente acumule diagonales y luego imprima `sum(oc)`.
- No se eligió material ni ruta P5. El plan limita P5 a una campaña única de hasta 13 nodos para un sitio, o hasta 25 para la alternativa NiO de dos sitios elegida antes del cálculo; contempla hasta cuatro rangos MPI y una ejecución SIESTA simultánea. Esos límites quedan registrados sin autorización de despacho.
- No se modifican α, tolerancias, proyectores, ventanas, límites ni criterios para obtener un U. Literatura no se usa como criterio de aceptación. Los artefactos y reportes históricos permanecen inmutables.

## Mínimo necesario para reabrir

Recuperar en la ruta NiO declarada las **41 salidas `.out`**, sus archivos `.DM` padres y el manifiesto de procedencia/integridad que permita vincular cada salida con su entrada y evento. Después se podrá reanudar P0 y comprobar la selección científica fijada por el plan. El conjunto Cu1 requiere además, si se pretende usar para una decisión que dependa de ruido de ocupación, un protocolo de repetibilidad/calibración aplicable a Cu predeclarado y su recibo inmutable de bloqueo metodológico, tal como especifica `final-verdict.json`.

| Puerta | Estado | Evidencia/razón |
|---|---|---|
| P0 — congelar contrato | `BLOCKED` | Fuente inspeccionada; faltan los 41 `.out`, `.DM` padres y manifiesto NiO. Cu1 está cerrado sin U autorizado. |
| P1 — fuente de ocupación | `NOT RUN` | P0 no superada; no hay datos NiO requeridos para el cotejo. |
| P2 — decisiones matemáticas | `NOT RUN` | P0 no superada. |
| P3 — DAG, CLI e informe | `NOT RUN` | P0 no superada. |
| P4 — regresión sin SIESTA | `NOT RUN` | P0 no superada. |
| P5 — prueba real final | `NOT RUN / NO AUTORIZADA` | No se seleccionó campaña; no se ejecutó SIESTA. |
| P6 — entrega | `NOT RUN` | El producto no satisface las puertas previas. |

**Estado terminal de esta ejecución:** `PRODUCT_BLOCKED`, por la ausencia reproducible de los datos NiO y su procedencia necesarios en P0. No se amplía el alcance para fabricar un sustituto ni se continúa hacia P1–P6.
