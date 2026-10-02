# Revisión adversarial independiente de FDRC-v1 (HubbardFlow)

**Objeto revisado:** `HUBBARDFLOW_FDRC_V1_METHOD_PROPOSAL.md` + `HUBBARDFLOW_FDRC_CONTEXT_FOR_INDEPENDENT_REVIEW.md`
**Código inspeccionado:** rama `codex/hubbardflow-rename` @ `3c1398b0a591ea622ef9726cf2f92e536b6206e2` (autoritativa); tag `scientific-v6-final` → commit `45cb53c5a98d9d55a163c05ca3b815a8ff9cfb7f` (sólo lectura, como referencia histórica).
**Datos usados para ilustración:** `results/stage-ub-v6-observables/coo-u-b-campaigns/stageubv6-coo-a0/lr_u_analysis.v3.json` (lectura; ningún artefacto V6 fue modificado). Todos los cálculos numéricos de este informe son reproducibles con `fdrc_review_numerics.py` (adjunto).
**Fecha:** 2026-10-01

> **Advertencia de alcance.** Los cálculos sobre CoO son *ilustraciones post-hoc sobre un sistema de desarrollo*, no validación. Se usan para falsar o apoyar supuestos, nunca para fijar umbrales ni para reinterpretar la calificación V6 de CoO.

---

## Resumen ejecutivo

**Veredicto: REEMPLAZAR la metodología de decisión de FDRC-v1.** Se conserva su *diseño de medición* (pares simétricos \(\pm a\), diferencias centrales, varias escalas, compuerta de estado, procedencia), pero se sustituye su *lógica de calificación* (cocientes \(C\), \(D\), ventanas anidadas, intersecciones obligatorias, noise floor desde controles \(\alpha=0\)) por una **calificación por presupuesto de error específico del estimador** (en adelante **FD-EBQ**, *Finite-Difference Error-Budget Qualification*).

Hallazgos principales, ordenados por gravedad:

1. **La calificación tiene que ser específica del estimador, y FDRC-v1 no lo es.** FDRC-v1 analiza la pendiente central \(s(a)\), pero el estimador de producción V6 es el coeficiente \(c_1\) de un ajuste cúbico. Son funcionales lineales distintos de los mismos datos, con ganancias de ruido distintas (en el grid V6: \(\sum|w|=21.4\ \mathrm{eV^{-1}}\) lineal, \(58.3\ \mathrm{eV^{-1}}\) cúbico, \(50\ \mathrm{eV^{-1}}\) central a 0.02 eV) y errores de truncamiento de orden distinto (\(O(a^2)\) vs \(O(a^4)\)). Calificar una ventana "para la derivada" sin decir *con qué estimador* no tiene contenido matemático.

2. **El modelo \(E(a)\sim C_{\rm num}/a + C_{\rm nl}a^2\) es incompleto en el punto que más importa.** Faltan componentes de error *independientes de \(a\)* (error SCF relativo, sesgo del Hamiltoniano/DM parental). Ningún diagnóstico multiescala puede verlos: en la prueba sintética, un sesgo SCF relativo de \(10^{-3}\) produce **cobertura 0 %** con todos los diagnósticos multiescala en verde. Sólo una **escalera de tolerancias SCF sobre la diferencia \(n(+a)-n(-a)\)** lo detecta.

3. **El noise floor por réplicas a \(\alpha=0\) (ya implementado en `domain/occupation_noise_calibration.py`) mide reproducibilidad, no exactitud**, y a \(\alpha=0\) un reinicio desde la DM convergida converge casi sin iterar, así que subestima sistemáticamente el error a \(\alpha\neq0\). El propio código lo admite (`transfer_to_nonzero_alpha_established: False`). No debe ser la base del noise floor.

4. **BARE y SCREENED viven en regímenes de error opuestos** (CoO V6): BARE está dominado por truncamiento suave (cociente de derivas 1.645 frente a 1.667 teórico para \(c_3a^2\); \(c_3\approx9.4\ \mathrm{e/eV^3}\)); SCREENED está dominado por ruido (derivas \(\le10^{-4}\) con cocientes \(\pm4\), signo errático). Exigir **una ventana común y un estimador común** fuerza un compromiso subóptimo. Ilustración: con el estimador V6 los dos sitios AFM equivalentes por simetría difieren en 2.1 meV; usando Richardson para BARE y diferencia central a 0.02 eV para SCREENED difieren en 1.1×10⁻⁵ eV.

5. **La componente par está contaminada y es irrelevante para la pendiente.** En una malla simétrica, el estimador de mínimos cuadrados de los coeficientes impares depende *sólo* de la parte impar de los datos. La parte par mide curvatura \(c_2\), \(c_4\) **y** un desplazamiento de referencia \(\delta_0\) (CoO BARE: \(\delta_0\approx\pm2\times10^{-5}\) e, unos 40 cuantos de impresión). Por tanto, \(C^m_J(a)\) de FDRC-v1, los tests de residuo del ajuste completo y el criterio `nonlinear_residual` de `alpha_selection.py` penalizan términos que **no afectan** a \(\chi\).

6. **La métrica V6 "model sensitivity" \(|U_{\rm cúbico}-U_{\rm lineal}|\) mide el sesgo \(O(a^2)\) conocido del estimador inferior, no la incertidumbre del estimador usado.** En CoO, BARE está en régimen asintótico verificado; la diferencia lineal–cúbico es esencialmente \(c_3\sum_k w_k\alpha_k^3\) del estimador lineal. La calificación `REVIEW` de CoO es plausiblemente un artefacto de esta métrica. *Esto no modifica el estado V6 congelado*; sólo indica que FD-EBQ no debe heredar esa métrica como incertidumbre.

7. **Existe una prueba de falsación interna gratuita que FDRC-v1 no usa: reciprocidad \(\chi_{IJ}=\chi_{JI}\)** (tanto \(\chi^0\) como \(\chi\) son simétricas en la teoría exacta). Dos columnas obtenidas con perturbaciones distintas dan dos estimaciones independientes del mismo número. Hoy la simetrización la oculta.

8. **Una ventana común multi-sitio no es un requisito matemático.** Columnas obtenidas con mallas distintas son perfectamente válidas si cada elemento lleva su presupuesto de error. Declarar `NOT_ESTABLISHED` cuando la intersección es vacía rechaza sistemas heterogéneos sanos.

9. **FDRC-v1 ignora que la rama ya contiene tres mecanismos de selección de \(\alpha\) solapados** (`alpha_selection.py`/`adaptive_alpha.py`, `adaptive_alpha_control.py`, y la calibración de ruido/réplicas), dos clases distintas llamadas `AdaptiveAlphaPolicy`, umbrales numéricos por defecto ya codificados (0.02, 0.05, 10, 0.05), y un controlador en producción (`campaign_runner._execute_adaptive_gate` → `decide_round`) que **para por estabilidad de \(U\) entre rondas** con un contador histórico. Esto viola dos restricciones del propio encargo (no usar \(U\) como criterio de selección; decisión independiente del historial).

10. **La frontera `ResolvedPerturbationPlan` es insuficiente.** Como la calificación depende del estimador, del nivel SCF y del modo, el objeto que cruza la frontera debe ser un **`ResolvedResponseProtocol`**: malla por (sitio, modo), estimador por (sitio, modo), nivel SCF, y referencia a la evidencia de presupuesto.

**Bloqueo científico principal:** la componente SCF del noise floor (absoluta y, sobre todo, relativa/independiente de \(a\)). La cuantización de impresión ya está resuelta de forma rigurosa en el código.

---

## A. Reconstruction of the problem

Sea \(\mathbf n^m(\boldsymbol\alpha)\in\mathbb R^N\) el vector de ocupaciones de los \(N\) subespacios correlacionados en el estado \(m\in\{\mathrm{BARE},\mathrm{SCREENED}\}\), con \(\boldsymbol\alpha\) el vector de desplazamientos de potencial sobre los proyectores. El objeto científico es el Jacobiano en el origen,
\[
\chi^m_{IJ}=\left.\frac{\partial n^m_I}{\partial\alpha_J}\right|_{\boldsymbol\alpha=0},
\qquad
U=(\chi^0)^{-1}-\chi^{-1},
\]
donde \(\chi^0\) es la respuesta sin autoconsistencia (primera diagonalización de \(H_{\rm ref}+\alpha P_J\) desde la DM parental; perfil `siesta542_bare_profile.py`) y \(\chi\) la respuesta autoconsistente.

HubbardFlow no tiene acceso al Jacobiano: sólo puede evaluar \(\mathbf n^m\) en puntos \(\alpha_J=\pm a_k\) (una columna \(J\) por perturbación, todas las filas \(I\) a la vez), y cada evaluación es:

- **truncada** por la salida impresa (SIESTA estándar: `f12.6`, semipaso \(5\times10^{-7}\) e por token);
- **inexacta** por SCF incompleto (tolerancias finitas, historia de mezcla, reinicio desde la DM parental);
- **sesgada** de forma común por la calidad de la referencia (\(H_{\rm ref}\), DM parental);
- **potencialmente discontinua** si el punto cae en otra rama (orden orbital, magnético, metaestable).

Cualquier estimador práctico es un funcional lineal de los datos de una columna,
\[
\hat\chi^m_{IJ}=\sum_k w_k\,n^m_I(\alpha_k),\qquad \sum_k w_k=0,\quad\sum_k w_k\alpha_k=1,
\]
y su error tiene tres naturalezas distintas: (i) error de datos amplificado por \(\sum_k|w_k|\); (ii) error de modelo (truncamiento) controlado por los momentos \(\sum_k w_k\alpha_k^p\) de orden superior al eliminado; (iii) errores que no dependen de la malla. El problema de "elegir \(\alpha\)" es, en realidad, **elegir un par (malla, estimador) por columna y modo, y demostrar una cota del error resultante que sea suficientemente pequeña para la precisión de \(U\) que se declara**, sin usar el valor de \(U\) como señal de calidad.

Este es el planteamiento que uso en todo el informe. Difiere del de FDRC-v1 en que (a) el estimador es parte de la decisión, (b) la tolerancia sale de un requisito declarado sobre \(U\) propagado por las matrices reales, y (c) los errores independientes de \(a\) se miden aparte.

---

## B. Audit of FDRC-v1 assumptions

| # | Supuesto (explícito o implícito) | Tipo | Evaluación |
|---|---|---|---|
| B1 | Existe una ventana intermedia en \(a\) donde el error total es pequeño | Num. | Correcto **sólo** para las componentes que dependen de \(a\). Falla si domina un error independiente de \(a\) (§C.4). |
| B2 | El error numérico de ocupaciones se resume en un escalar \(\epsilon_n\) | Num./Estad. | **Falso.** Hay al menos cuatro componentes con escalados distintos: impresión (cota exacta), SCF absoluto (\(\propto1/a\) en la pendiente), SCF relativo (\(\propto|\chi|\), independiente de \(a\)), sesgo de referencia (independiente de \(a\)). |
| B3 | Ese \(\epsilon_n\) se puede estimar con réplicas deterministas, \(\alpha=0\), etc. | Estad. | Las réplicas deterministas miden *reproducibilidad del camino*, no exactitud; \(\alpha=0\) reiniciado desde DM convergida no ejercita el SCF. Ver §E. |
| B4 | La pendiente central \(s(a)\) es el objeto a calificar | Mat. | **Falso para producción**: el estimador V6 es \(c_1\) cúbico. La calificación debe referirse al funcional realmente usado. |
| B5 | La componente par detecta no linealidad / asimetría | Mat. | Detecta curvatura par y **desplazamiento de referencia \(\delta_0\)**, ninguno de los cuales afecta a \(\hat\chi\) en malla simétrica. Útil sólo como detector de anomalías de estado. |
| B6 | Estabilidad de pendientes entre escalas (\(D\)) evidencia linealidad | Num. | Acuerdo no implica exactitud: (i) dos valores ruidosos pueden coincidir por azar; (ii) un sesgo común pasa; (iii) no distingue \(O(a)\) de \(O(a^2)\). Se necesita verificación de orden y cotas explícitas. |
| B7 | Richardson es secundario | Num. | Invertido. La estimación de error tipo Richardson (con verificación de orden) es el núcleo defendible; el estimador extrapolado es un candidato legítimo cuando el orden está verificado. |
| B8 | Hace falta ventana común BARE∩SCREENED | Mat. | No es requisito matemático; las corridas ya son nodos separados (`PerturbationSpec.mode`). Ver §F. |
| B9 | Hace falta ventana común entre todos los sitios | Mat. | No es requisito matemático. Ver §F. |
| B10 | Umbrales fijos \(S_{\min},D_{\max},C_{\max},R_{\max}\) | Estad. | La mayoría deben ser cantidades **derivadas** (ganancias, cotas) y un requisito **declarado** (precisión de \(U\)), no umbrales calibrados. Quedan pocos parámetros genuinos (§K). |
| B11 | Calibración y certificabilidad matricial son independientes | Arq./Mat. | Parcial. No hay que *ajustar \(\alpha\)* para mejorar \(\kappa\), pero el condicionamiento **sí fija la exactitud requerida** de \(\chi\). Separar "qué ventanas son válidas" (independiente de la matriz) de "qué exactitud se necesita" (depende de la matriz). |
| B12 | El estado electrónico se puede verificar con convergencia y momentos | E.E. | Insuficiente: cambios de orden orbital pueden conservar los momentos; momentos cambian legítimamente con \(\alpha\) (respuesta lineal del momento). Hay que inspeccionar matrices de ocupación locales y **suavidad**, no constancia. |
| B13 | Las corridas piloto son distintas de las de producción | Arq. | En FD-EBQ la evidencia de calibración **es** la evidencia de producción; la "promoción" se reduce a la clave de identidad de nodo que ya existe (§I.9). |
| B14 | Un grid V6 como semilla es neutral | Val. | Introduce sesgo de selección hacia los cuatro óxidos. La semilla debe derivarse de una red versionada + un piloto BARE barato. |
| B15 | La decisión es función del conjunto de evidencia | Arq. | Correcto como requisito, pero **el controlador existente lo viola** (`stable_comparisons`, dirección de refinamiento persistida). |
| B16 | La referencia \(\alpha=0\) es intercambiable con el parent | E.E. | El diferencial central no usa \(n(0)\); el par sí. Diferencias de referencia aparecen como \(\delta_0\) y no deben confundirse con curvatura. |
| B17 | Las respuestas son analíticas en \(\alpha=0\) | E.E. | Falso para metales a baja temperatura electrónica y en fronteras de fase: términos \(\alpha|\alpha|\) (impares) dan error \(O(a)\). Requiere verificación de orden. |
| B18 | Se puede representar cualquier \(a\) | Num. | El FDF se escribe con resolución \(10^{-4}\) eV (`_fdf_representable`). La red de amplitudes debe ser representable exactamente. |

---

## C. Mathematical analysis

### C.1 Desacople par/impar (resultado que FDRC-v1 no explota)

Para una malla simétrica \(\{\pm a_k\}\) (con o sin \(\alpha=0\)) y una base polinómica \(\{\alpha^p\}\), las columnas pares e impares de la matriz de diseño son ortogonales: \(\sum_{\pm,k}(\pm a_k)^{p}(\pm a_k)^{q}=0\) si \(p+q\) es impar. Por tanto, para **cualquier** ajuste de mínimos cuadrados (lineal, cúbico, de cualquier grado) sobre malla simétrica:
\[
\hat c_1=\text{función sólo de }\;o_k=\tfrac12[n(+a_k)-n(-a_k)].
\]
Consecuencias:

- \(n(0)\), \(c_2\), \(c_4\) y cualquier desplazamiento de referencia **no afectan** a \(\hat\chi\).
- Un test de residuo o \(R^2\) sobre el ajuste completo mezcla residuos pares (irrelevantes) con impares (relevantes). En CoO BARE, el residuo máximo del cúbico V6 (\(1.36\times10^{-5}\) e, 27 cuantos de impresión) se explica por el término par \(c_4\alpha^4\) con \(c_4\approx-7.8\), que el cúbico no modela y que **no contamina** \(\hat c_1\).
- El criterio `nonlinear_residual` de `alpha_selection.py` (residuos de OLS lineal incluyendo curvatura par) rechaza ventanas por un motivo irrelevante para \(\chi\).

### C.2 Todo estimador es un funcional; su calificación es suya

Sobre los datos impares, el problema se reduce a la secuencia de pendientes centrales \(s_k=o_k/a_k\) con modelo suave
\[
s(a)=\chi+b_1a^2+b_2a^4+\cdots\qquad(b_1=c_3,\ b_2=c_5).
\]
Un estimador \(\hat\chi=\sum_k v_k s_k\) con \(\sum v_k=1\) tiene:
\[
\text{truncamiento}=\sum_{p\ge1} b_p\,\mu_p,\qquad \mu_p=\sum_k v_k a_k^{2p};
\qquad
\text{ganancia de ruido sobre }o:\ G=\sum_k|v_k|/a_k .
\]
- Diferencia central en \(a_k\): \(\mu_1=a_k^2\), \(G=1/a_k\) (sobre ocupaciones: \(\sum|w|=1/a_k\cdot\) [dos puntos de peso \(1/2a_k\)]).
- Richardson de dos escalas \((a_k,a_{k+1})\): \(\mu_1=0\), \(\mu_2=-a_k^2a_{k+1}^2\).
- Cúbico V6 en \(\{\pm0.02,\pm0.04,\pm0.06\}\): \(\mu_1=0\) exactamente; \(\sum_k w_k\alpha_k^5=-3.99\times10^{-6}\); \(\sum|w|=58.3\ \mathrm{eV^{-1}}\).
- Lineal OLS en el mismo grid: \(\sum w_k\alpha_k^3=2.8\times10^{-3}\); \(\sum|w|=21.4\ \mathrm{eV^{-1}}\).

**El cúbico V6 es un Richardson ponderado disfrazado.** Elimina \(b_1\) a cambio de ~2.7× la ganancia de ruido del lineal. Eso es óptimo cuando domina el truncamiento (BARE en CoO) y subóptimo cuando domina el ruido (SCREENED en CoO). Ningún diagnóstico sobre \(s(a)\) que no conozca \(v\) puede calificarlo.

### C.3 Auditoría de los diagnósticos propuestos

| Diagnóstico FDRC-v1 | Defecto |
|---|---|
| 7.1 Resolución de señal \(\|\mathbf n(+a)-\mathbf n(-a)\|\) vs floor | Correcto en espíritu, pero debe aplicarse a la **ganancia del estimador** y por elemento, no a la norma de columna (los elementos cruzados pequeños quedan sin resolver aunque la norma lo esté). |
| 7.2 Consistencia \(\pm\alpha\) | Equivale a la componente par; ver abajo. |
| 7.3 \(C^m_J(a)=\|e\|/(\|o\|+E_{\rm floor})\) | Contaminado por \(\delta_0\) (desplazamiento de referencia) y por \(c_2a^2\), ninguno relevante para \(\hat\chi\). A amplitud pequeña, \(\delta_0\) domina: \(C\) se dispara precisamente donde la pendiente es mejor. CoO BARE: \(\delta_0\approx2\times10^{-5}\) e vs \(o(0.02)\approx2.7\times10^{-2}\) e. |
| 7.4 Deriva \(D^m_J(a_p,a_q)\) normalizada por \(S^m_J\) | No distingue ruido de truncamiento; el umbral \(D_{\max}\) no tiene derivación; la normalización por columna oculta elementos cruzados; no identifica el orden. |
| 7.5 Ventanas anidadas \(W_1,W_2,W_3\) | Redundantes y fuertemente correlacionadas (comparten puntos); "coherencia" sin cota no tiene interpretación. |
| 7.6 Estado | Necesario pero subespecificado (§I.5). |
| 8 Richardson secundario | Debe ser primario como **estimación de error** con verificación de orden. |

### C.4 El modelo de error correcto

Para la ocupación impresa \(\tilde n_I(\alpha)\) en el punto \(\alpha\):
\[
\tilde n_I(\alpha)=n_I(\alpha)+\underbrace{\rho_I(\alpha)}_{\text{impresión}}+\underbrace{r^{\rm abs}_I(\alpha)}_{\text{SCF abs.}}+\underbrace{r^{\rm rel}_I(\alpha)}_{\text{SCF rel.}}+\underbrace{\beta_I(\alpha)}_{\text{referencia}},
\]
con \(|\rho_I|\le q_I\) (exacto, de los tokens), \(|r^{\rm abs}|\le\varepsilon_{\rm abs}\), \(|r^{\rm rel}|\le\varepsilon_{\rm rel}|n_I(\alpha)-n_I(0)|\), y \(\beta\) una función **suave** de \(\alpha\) (p. ej. el efecto de un \(H_{\rm ref}\) no convergido sobre toda la familia de corridas BARE). El error del estimador es entonces
\[
|\hat\chi-\chi|\ \le\ \underbrace{G\,q}_{\text{1/a}}+\underbrace{G\,\varepsilon_{\rm abs}}_{\text{1/a}}+\underbrace{\varepsilon_{\rm rel}\,\textstyle\sum_k|v_k|\,|s_k|}_{\text{independiente de }a}+\underbrace{|\textstyle\sum_p b_p\mu_p|}_{\text{truncamiento}}+\underbrace{|\partial_\alpha\beta|}_{\text{independiente de }a}.
\]
Sólo los términos 1, 2 y 4 tienen la estructura \(C/a+Ca^2\). **Los términos 3 y 5 son invisibles para cualquier análisis multiescala**: desplazan todas las pendientes por igual. Por eso FDRC-v1, aun perfectamente implementado, puede emitir PASS con un error arbitrario. Esto no es teórico: la prueba sintética (Apéndice) da cobertura 0.000 con sesgo relativo \(10^{-3}\).

Observación empírica en CoO SCREENED: las derivas irregulares crecen con \(a\) (\(\sim10^{-5}\) entre 0.02–0.04, \(\sim10^{-4}\) entre 0.04–0.06) con signo errático, y el residuo de reciprocidad \(|\hat\chi_{01}-\hat\chi_{10}|\) pasa de \(0\) a 0.02 eV a \(4.2\times10^{-5}\) a 0.06 eV, por encima de la cota de impresión del par (\(2q/a=1.7\times10^{-5}\)). Eso no es truncamiento suave (no tiene signo coherente) ni ruido de impresión: es consistente con un error SCF que crece con el tamaño de la perturbación, lo que refuerza la necesidad del término relativo.

---

## D. Numerical-analysis assessment

**Truncamiento.** Para la diferencia central, \(T(a)=b_1a^2+O(a^4)\). Para Richardson/cúbico, \(T=O(a^4)\). El orden sólo es fiable si se **verifica** en los datos: con red geométrica de razón \(r\), las derivas \(d_k=s_{k+1}-s_k\) cumplen \(d_{k+1}/d_k\to r^{p}\) en régimen asintótico (\(p=2\) analítico, \(p=1\) si hay un término impar \(\alpha|\alpha|\)). CoO BARE: cociente 1.645 frente a 1.667 esperado (malla aritmética 2:4:6) → régimen asintótico verificado, \(b_1\approx9.4\ \mathrm{e/eV^3}\), igual al \(c_3=9.34\) del cúbico V6.

**Error de datos.** La cota de impresión se propaga exactamente: \(\sum_k|w_k|q_k\) (ya implementado en `quantized_response.fit_centered_linear_response` y en `u_certification.propagate_linear_occupation_tokens`). Los componentes SCF no tienen cota rigurosa; requieren medición (§E).

**Escala óptima (ilustrativa, sólo CoO).** Minimizando \(q/a+|b_1|a^2\): \(a^\*=(q/2|b_1|)^{1/3}\).
- BARE: \(a^\*\approx3\times10^{-3}\) eV con diferencia central; o bien amplitudes mayores con Richardson (residuo \(\sim2\times10^{-4}\) entre las dos extrapolaciones disponibles).
- SCREENED: \(|b_1|\lesssim0.05\) (no resuelto) → \(a^\*\gtrsim0.017\) eV.

Es decir, **en el mismo material las escalas óptimas de BARE y SCREENED difieren en un factor \(\sim6\)** y además prefieren estimadores distintos. Esto es la razón numérica de fondo para no imponer ventana/estimador común (§F).

**Condicionamiento.** La exactitud requerida de \(\chi\) depende de la matriz. Linealizando \(U_{KK}\):
\[
\delta U_{KK}=-\big[(\chi^0)^{-1}\delta\chi^0(\chi^0)^{-1}\big]_{KK}+\big[\chi^{-1}\delta\chi\,\chi^{-1}\big]_{KK},
\qquad
\frac{\partial U_{KK}}{\partial\chi_{IJ}}=(\chi^{-1})_{KI}(\chi^{-1})_{JK}.
\]
CoO: \(\partial U_{00}/\partial\chi_{00}=87.5\), \(\partial U_{00}/\partial\chi_{01}\approx25.9\), \(\partial U_{00}/\partial\chi^0_{00}=-12.5\) (unidades eV²/e). Un error de \(10^{-4}\) e/eV en \(\chi_{00}\) son ~9 meV en \(U\). Los valores propios de \(\chi^0\) son \(-2.56\) y \(-0.150\): el modo \((1,1)\) amplifica errores ~17×.

Dos observaciones finas:
- Los errores de **truncamiento** son estructurados y con signo (la matriz \(b_1\) tiene el mismo patrón que \(\chi^0\)); en CoO el sesgo del estimador lineal en \(\chi^0\) (~0.026) produce sólo ~0.017 eV en \(U\) por cancelaciones. Sumar cotas elementales en valor absoluto es ~10× pesimista para truncamiento. El **ruido**, en cambio, debe propagarse en valor absoluto.
- La validez de la linealización exige \(\beta=\|\chi^{-1}\|_2\|\Delta\chi\|_2<1\) con \(\Delta\chi\) el **presupuesto completo**, no sólo impresión (hoy `inverse_rounding_bound` usa sólo impresión).

**Selección de escala.** Red geométrica versionada, representable con \(10^{-4}\) eV (p. ej. de forma ilustrativa \(\{0.005,0.01,0.02,0.04,0.08\}\); ningún valor de este informe es un umbral recomendado). Las fórmulas de §I admiten razón variable, así que la representabilidad no exige \(r=2\) exacto.

---

## E. Noise-floor solution

### E.1 Principios

1. **Medir el error de la cantidad que entra al estimador**: la diferencia \(\Delta(a)=n(+a)-n(-a)\), no \(n\) aislado. Los errores de \(+a\) y \(-a\) están correlacionados (mismo parent, misma historia de mezcla) y pueden cancelarse o sumarse; sólo medir \(\Delta\) lo captura.
2. **Separar componentes con escalado distinto** (§C.4) en vez de un escalar \(\epsilon_n\).
3. **Distinguir cota de estimación.** La impresión tiene cota; lo SCF sólo tiene estimación a posteriori, que necesita un factor de seguridad validado.
4. **No tratar errores deterministas como varianzas**: combinar por suma de cotas, no por RSS.

### E.2 Procedimiento recomendado

| Componente | Medición | Estatus |
|---|---|---|
| Impresión \(q\) | Tokens impresos por punto, exacto (`siesta_backend/occupation_precision.py`; `read_printed_matrix_trace_precision` o `read_printed_occupation_precision`, **sin mezclar observables** entre puntos) | Cota rigurosa. Ya implementado. |
| SCF absoluto y relativo (SCREENED) | **Escalera de tolerancias SCF sobre \(\Delta(a)\).** Para cada columna \(J\), en la amplitud más pequeña y en la más grande que vaya a usarse, repetir \(\pm a\) en niveles \(L_0\) (producción), \(L_1\), \(L_2\) (DM.Tolerance y tolerancia en H endurecidas por un factor declarado), cada nivel con referencia parental propia del mismo nivel. \(\eta_1=\|\Delta_{L_0}-\Delta_{L_1}\|\), \(\eta_2=\|\Delta_{L_1}-\Delta_{L_2}\|\). Si \(\eta_2\le\hat\rho\,\eta_1\) con \(\hat\rho<1\) (contracción) o ambos están al nivel de impresión, estimar el error en \(L_0\) como \(\theta\,\eta_1/(1-\hat\rho)\). La comparación entre amplitud pequeña y grande separa absoluto (\(\eta\) constante) de relativo (\(\eta\propto a\)). | Estimación a posteriori; \(\theta\) requiere validación (§K). Sin contracción → `NOISE_FLOOR_NOT_ESTABLISHED`. |
| Sesgo de referencia (BARE) | BARE \(\pm a\) desde una DM parental del nivel \(L_1\) frente a la de \(L_0\); además, el ajuste \(e_k=\delta_0+c_2a_k^2+c_4a_k^4\) de la parte par estima \(\delta_0\) (no autoconsistencia del parent) sin coste adicional | Estimación; \(\delta_0\) es un indicador, no una cota. |
| Camino computacional | Reiniciar desde DM alternativa dentro de la cuenca (p. ej. la de la amplitud vecina), y cambio de descomposición MPI | **Sólo en validación** o disparado por ambigüedad de estado; mide sensibilidad al camino/multiestabilidad. |
| Réplicas \(\alpha=0\) | Mantener como prueba de humo de determinismo | **No** usar como noise floor. |

Infraestructura existente reutilizable: el controlador ya tiene el concepto de *strict SCF probe* (`v_base_electron` vs `v_strict_electron` en `adaptive_alpha_control.py`) y `lr_dag.build_adaptive_campaign_dag` ya enclava nodos por (sitio, \(\alpha\), modo, nivel SCF, nodo de referencia) con una referencia estricta compartida. FD-EBQ cambia el **uso**: el probe deja de ser un disparador heurístico y se convierte en una medición obligatoria con verificación de contracción.

Coste adicional orientativo por columna: 4–8 corridas SCREENED (dos niveles × dos amplitudes × \(\pm\)), 2 BARE baratas, más una referencia por nivel compartida por todas las columnas.

### E.3 Combinación

\[
\varepsilon_I(\alpha)=q_I(\alpha)+\theta\big[\hat\eta^{\rm abs}_I+\hat\eta^{\rm rel}_I\,|\tilde n_I(\alpha)-\tilde n_I(0)|\big]\ (+\,s^{\rm path}_I\ \text{si se midió}).
\]

### E.4 Falsación interna del noise floor

- **Reciprocidad:** \(|\hat\chi_{IJ}-\hat\chi_{JI}|\le\kappa(B_{IJ}+B_{JI})\) para todo \(I\ne J\) perturbados.
- **Equivalencia declarada:** si (y sólo si) el módulo de simetría (`domain/symmetry_reduction.py`, con su compuerta de sombra) declara sitios equivalentes con evidencia, \(|\hat\chi_{II}-\hat\chi_{KK}|\) debe quedar dentro de los presupuestos. No se infiere equivalencia: sólo se *usa* la declarada.

Advertencia derivada de la prueba sintética: la consistencia interna entre escalas **no rescata fiablemente** un noise floor subestimado (cobertura 0.98 con verificación de orden conservadora, 0.58 sin ella). La reciprocidad añade poder, pero **la escalera SCF no es opcional**.

**Requisito previo a usar la reciprocidad como compuerta:** verificar una vez (validación T2) que en SIESTA 5.4.2 el operador de ocupación y el operador de perturbación de `DFTU.PotentialShift` son el mismo proyector (par adjunto). Los datos CoO lo apoyan (BARE: \(1.201775\) vs \(1.201775\)), pero un caso no es una demostración.

---

## F. Multi-site and BARE/SCREENED analysis

### F.1 ¿Ventana común para \(\chi^0\) y \(\chi\)? **No.**

- **Matemática:** \(\chi^0\) y \(\chi\) son derivadas en el origen de dos funciones distintas. La definición de \(U\) no exige que se evalúen con la misma amplitud; el límite \(a\to0\) es independiente para cada una.
- **Supuesta cancelación de errores:** no existe un argumento general de que errores \(O(a^2)\) de \(\chi^0\) y \(\chi\) se cancelen en \((\chi^0)^{-1}-\chi^{-1}\); los coeficientes \(b_1\) son de funciones distintas y en CoO difieren en dos órdenes de magnitud. No debe asumirse; puede *medirse* en validación.
- **Numérica:** regímenes opuestos (§D). El común es subóptimo para ambos.
- **Coste:** BARE y SCREENED ya son nodos separados (`PerturbationSpec.mode`); amplitudes distintas no añaden corridas.

**Regla:** calificar por separado cada par \((J,m)\). Usar malla común si ambos modos califican sobre el mismo subconjunto (default: simplicidad y comparabilidad con V6); si no, mallas específicas por modo, marcadas en procedencia. Nunca `NOT_ESTABLISHED` sólo por intersección vacía.

### F.2 ¿Malla común para todos los sitios? **No es requisito; es una preferencia de simplicidad.**

Columnas obtenidas con mallas distintas son matemáticamente válidas si:

1. todas comparten **la misma referencia** (misma DM parental, mismo nivel SCF de la referencia) — la matriz debe ser el Jacobiano en un único punto;
2. **no se mezclan niveles SCF dentro del estimador de una columna**; entre columnas se recomienda un único nivel por campaña (simplifica el presupuesto, y el código actual ya prohíbe mezclar);
3. cada elemento lleva su **presupuesto de error** propio (\(B_{IJ}\));
4. se aplica la **compuerta de reciprocidad** entre columnas — con mallas distintas pasa a ser un control cruzado aún más fuerte, porque los truncamientos son distintos;
5. la política de inversión (raw vs simetrizada) se mantiene declarada; con mallas distintas, la antisimetría del raw refleja truncamientos distintos y debe quedar dentro de los presupuestos.

**Procedencia mínima por \((J,m)\):** amplitudes usadas, estimador (identificador + pesos), nivel SCF, componentes del presupuesto (\(q\), \(\eta\), truncamiento con orden verificado), estado de compuertas.

**Recomendación v1:** malla común por defecto; si la intersección es vacía y cada columna califica por separado, emitir `QUALIFIED_HETEROGENEOUS` (no `NOT_ESTABLISHED`). La única razón legítima para no implementarlo en la primera iteración es el cambio de modelo de datos (§M), no la corrección matemática.

### F.3 Respuestas cruzadas cerca de cero

Los criterios relativos por elemento son la métrica equivocada. El peso correcto de un error en \(\chi_{IJ}\) es su influencia en \(U\), \(|(\chi^{-1})_{KI}(\chi^{-1})_{JK}|\), que **no depende del tamaño de \(\chi_{IJ}\)**. En FD-EBQ:

- El error de cada elemento se expresa en absoluto (e/eV): \(B_{IJ}=N_{IJ}+T_{IJ}+\ldots\).
- La aceptación se decide en espacio de \(U\): \(\delta U_{KK}\le\sum_{IJ}|A_{KI}A_{JK}|B^0_{IJ}+|\mathcal B_{KI}\mathcal B_{JK}|B_{IJ}\le\tau_U\) (con \(A=(\chi^0)^{-1}\), \(\mathcal B=\chi^{-1}\)), más \(\beta<1\).
- Un elemento cruzado cuyo \(|\hat\chi_{IJ}|<B_{IJ}\) se reporta como "no resuelto respecto de cero" sin que eso sea un fallo, si su influencia en \(U\) cabe en el presupuesto.

---

## G. Failure modes (contraejemplos adversariales)

| # | Escenario | FDRC-v1 | FD-EBQ |
|---|---|---|---|
| G1 | Sesgo SCF relativo común a todas las amplitudes (tolerancia floja) | **PASS falso**: todas las escalas coinciden | Detectado por escalera SCF; sin ella, igual de ciego (sintético: cobertura 0) |
| G2 | Noise floor estimado con réplicas \(\alpha=0\) que convergen en 1 iteración | **PASS falso** con \(\epsilon\) subestimado | Réplicas \(\alpha=0\) no usadas; escalera en \(\alpha\neq0\) |
| G3 | Dos pendientes ruidosas coinciden por azar a escala grande | PASS (D pequeño) | Cota \(B\) explícita grande → no satisface \(\tau_U\) |
| G4 | Metal / borde de fase: término impar \(\kappa\alpha|\alpha|\) (error \(O(a)\)) | Deriva pequeña → PASS; Richardson con orden 2 erróneo | Verificación de orden → cota conservadora \(p=1\) (sintético: cobertura 1.0) |
| G5 | BARE con \(\delta_0\) apreciable (parent no del todo autoconsistente) | \(C(a)\) grande a amplitud pequeña → rechaza la mejor escala | \(\delta_0\) se ajusta y reporta; no afecta \(\hat\chi\) |
| G6 | Sitios heterogéneos (p. ej. Fe octaédrico/tetraédrico; TM + 4f) | Intersección vacía → `NOT_ESTABLISHED` | Mallas por columna → `QUALIFIED_HETEROGENEOUS` |
| G7 | \(\chi^0\) fuertemente acoplada (valor propio pequeño, como CoO 0.150 vs 2.56) | Normalización por columna dominada por la diagonal → PASS aunque \(U\) sea inexacto | Requisito propagado por influencia y \(\beta<1\) |
| G8 | Cambio de orden orbital a \(+a\) con momentos iguales | Momentos dentro de 0.05 μB → pasa la compuerta | Autovalores/autovectores de la matriz de ocupación local, salto en parte par |
| G9 | Momento que responde linealmente con \(\alpha\) y supera una tolerancia absoluta (imanes blandos) | `magnetic_tolerance` absoluto rechaza un caso sano | La compuerta evalúa **suavidad**, no constancia |
| G10 | \(\pm a\) caen en mínimos de orden orbital distintos (degeneración) | Parte impar enorme → interpretada como respuesta grande | Solapamiento de subespacios con la referencia; salto de la parte par |
| G11 | Cúbico con 1–2 grados de libertad residuales y ruido SCF | Residuo bajo (sobreajuste) → buena "linealidad" | Ganancia de ruido explícita del cúbico (58/eV) entra en \(B\) |
| G12 | Tareas terminando en distinto orden; refinamiento con contador histórico | Riesgo explícito; el controlador actual lo viola | Barrera por ronda + decisión \(f(\mathcal E,\text{protocolo})\) |
| G13 | Amplitud no representable en el FDF (redondeo a \(10^{-4}\) eV) | No contemplado | Red versionada representable por construcción |
| G14 | Observable mezclado (resumen `Occupations:` vs traza de matriz) entre puntos | No contemplado | Identidad del observable en la clave de evidencia |
| G15 | Ventana elegida por mínima cota entre muchas (maldición del ganador) | — | Conjunto candidato pequeño y predeclarado; exigencia de consistencia con vecinos |

---

## H. Verdict on FDRC-v1

**Replace.**

Justificación: los componentes que deciden el resultado — noise floor, métricas \(C\)/\(D\), ventanas anidadas, intersecciones obligatorias, umbrales a calibrar, Richardson secundario, tratamiento del estimador como externo — son precisamente los defectuosos (§B, §C, §G). Lo que sobrevive (pares simétricos, diferencias centrales en varias escalas, compuerta de estado, determinismo como requisito, procedencia, reutilización por identidad) es el diseño de medición y la infraestructura, y se reutiliza en FD-EBQ. No es "retener con modificaciones mayores" porque la teoría de decisión cambia de naturaleza: de "acuerdo entre diagnósticos con umbrales" a "cota de error del estimador concreto frente a un requisito declarado".

---

## I. Recommended final methodology (FD-EBQ)

### I.1 Datos y notación

Para cada columna \(J\), modo \(m\), fila \(I\), amplitud \(a_k\) de una red versionada \(\mathcal L=\{a_1<\dots<a_K\}\):
\[
o_k=\tfrac12[\tilde n_I(+a_k)-\tilde n_I(-a_k)],\quad s_k=o_k/a_k,\quad e_k=\tfrac12[\tilde n_I(+a_k)+\tilde n_I(-a_k)]-\tilde n_I(0).
\]
Error de datos de \(s_k\) (de §E): \(\nu_k=\big(\varepsilon(+a_k)+\varepsilon(-a_k)\big)/(2a_k)\).

### I.2 Verificación de orden

Derivas \(d_k=s_{k+1}-s_k\) con incertidumbre \(\delta_k=\nu_k+\nu_{k+1}\). Una deriva está **resuelta** si \(|d_k|>\delta_k\). Para dos derivas consecutivas resueltas del mismo signo, el cociente admisible es el intervalo
\[
\Big[\tfrac{|d_{k+1}|-\delta_{k+1}}{|d_k|+\delta_k},\ \tfrac{|d_{k+1}|+\delta_{k+1}}{|d_k|-\delta_k}\Big]\ \ni\ \rho_p\equiv\frac{a_{k+2}^{p}-a_{k+1}^{p}}{a_{k+1}^{p}-a_{k}^{p}}
\]
(para red geométrica de razón \(r\), \(\rho_p=r^p\); para la malla aritmética V6, \(\rho_2=20/12\)). Orden 2 verificado si el intervalo contiene \(\rho_2\) y excluye \(\rho_1\); orden 1 si contiene \(\rho_1\); **inconsistente** (ninguno) → esas escalas quedan excluidas. Si las derivas no están resueltas, el orden no es identificable y se usa la cota conservadora \(p=1\).

### I.3 Estimadores candidatos (familia cerrada y predeclarada)

1. **Central** en \(a_k\): \(\hat\chi=s_k\),
\[
B^{\rm C}_k=\nu_k+\frac{|d_k|+\delta_k}{r^{p_k}-1},\qquad p_k=\begin{cases}2&\text{orden 2 verificado}\\1&\text{en otro caso}\end{cases}
\]
2. **Richardson** \((a_k,a_{k+1})\), sólo si orden 2 verificado: \(\hat\chi=\frac{a_{k+1}^2s_k-a_k^2s_{k+1}}{a_{k+1}^2-a_k^2}\), con cota
\[
B^{\rm R}_k=N_k+\frac{|\hat\chi^{\rm R}_{k+1}-\hat\chi^{\rm R}_k|+N_k+N_{k+1}}{r^4-1},\quad N_k=\frac{a_{k+1}^2\nu_k+a_k^2\nu_{k+1}}{a_{k+1}^2-a_k^2}.
\]
3. **Estimador protocolario** (p. ej. cúbico V6) con sus pesos \(w\): \(B=\sum|w_k|\varepsilon_k+|\sum_k w_k\alpha_k^5|\cdot\overline{|b_2|}\), con \(\overline{|b_2|}\) acotado desde la segunda diferencia dividida de \(s\) en \(t=a^2\). Esto permite **calificar** el protocolo FIXED sin cambiarlo.

### I.4 Compuertas de falsación (sin umbrales libres salvo \(\kappa\))

- **Consistencia entre vecinos:** un candidato es admisible sólo si \(|\hat\chi_E-\hat\chi_{E'}|\le\kappa(B_E+B_{E'})\) para los vecinos de su familia.
- **Reciprocidad** (§E.4) y **equivalencia declarada**.
- **Parte par:** \(e_k=\delta_0+c_2a_k^2+c_4a_k^4\) debe ajustarse dentro de \(\varepsilon\); un residuo anómalo en un punto señala ese punto para la compuerta de estado (no afecta a \(\hat\chi\) directamente).

### I.5 STATE_CONSISTENCY_GATE

Inspecciona por punto \((J,m,\pm a_k)\) frente a la referencia:

1. **Convergencia SCF** (bandera, dDmax/dHmax finales vs tolerancia del nivel, número de iteraciones; outliers de iteraciones respecto a la amplitud).
2. **Matrices de ocupación locales** \(n^{\sigma}_{mm'}\) de cada subespacio: autovalores ordenados y **solapamiento de subespacios ocupados** con la referencia (detecta cambios de orden orbital con momento constante).
3. **Momentos** por sitio (vector si no colineal) y total; en aislantes, el momento total cuantizado.
4. **Gap/HOMO-LUMO o nivel de Fermi** (cierre de gap ⇒ cambio de carácter).
5. **Suavidad**, no constancia: cada observable de estado debe admitir un modelo polinómico de bajo orden en \(\alpha\) dentro de su propio error (impresión + escalera); un salto aislado es un cambio de rama.
6. **Opcional (validación/disparado):** histéresis — reiniciar \(\pm a_k\) desde la DM de la amplitud vecina en lugar del parent; diferencia > presupuesto ⇒ multiestabilidad.
7. **Condicional:** consistencia energía–ocupación (Hellmann–Feynman, \(E(+a)-E(-a)\approx\int n_J\,d\alpha\)) **sólo** tras verificar qué incluye la energía impresa por SIESTA con `DFTU.PotentialShift`.

Clasificación de causas:

| Señal | Diagnóstico |
|---|---|
| Suave, orden verificado, compuertas en verde | No linealidad ordinaria de diferencias finitas |
| No convergencia, escalera no contractiva, iteraciones anómalas | Inestabilidad SCF |
| Salto en autovalores/subespacios o momentos, histéresis | Cambio de rama metaestable / estado magnético |
| Orden \(p\approx1\) estable o falta de régimen asintótico a todas las escalas resolubles | Discontinuidad física / no analiticidad: **no hay derivada a esa escala** → STOP |

**Regla monótona:** si un punto falla la compuerta en \(a_k\), esa amplitud y todas las mayores se excluyen para esa columna y modo.

### I.6 Selección por columna

Entre los candidatos admisibles, elegir \(E^\*=\arg\min_E B_E\), desempate determinista (menor amplitud máxima, luego familia en orden fijo). La selección ve sólo cotas; nunca \(U\).

### I.7 Requisito propagado y compuerta matricial

Con las matrices estimadas: \(\beta^0=\|(\hat\chi^0)^{-1}\|_2\|\mathbf B^0\|_2<1\), \(\beta=\|\hat\chi^{-1}\|_2\|\mathbf B\|_2<1\); y por sitio,
\[
\delta U_{KK}\le\sum_{I,J}\Big(|A_{KI}A_{JK}|B^0_{IJ}+|\mathcal B_{KI}\mathcal B_{JK}|B_{IJ}\Big)+O(\beta^2)\ \le\ \tau_U .
\]
\(\tau_U\) es un **requisito científico declarado por el usuario** (como el ±0.02 eV del contrato existente), no un parámetro calibrado. Si falla: los únicos remedios permitidos son los que **reducen cotas** (endurecer SCF, mayor precisión de salida en validación, más escalas dentro de la región válida); nunca buscar otra ventana para mejorar \(\kappa\).

### I.8 Separación respecto a la certificación existente

La certificación intervalar actual (`domain/u_certification.py`: racional 2×2, Krawczyk, Neumann) **no se toca** y sigue certificando la propagación de la impresión. FD-EBQ puede emitir, como **artefacto separado**, una segunda evaluación con las mismas rutinas sobre un `MatrixBox` ampliado al presupuesto completo, etiquetada como *calificación condicional al modelo de error*, nunca como certificación.

### I.9 Reutilización piloto → producción

En FD-EBQ las corridas de la escalera **son** la evidencia de producción; no hay fase piloto separada salvo cuando el usuario declare explícitamente un subconjunto (prohibido inferirlo). La reutilización es por clave de identidad exacta:

- digest del FDF **efectivo** (incluye \(\alpha\), sitio, modo, tolerancias SCF, perfil BARE);
- digest en bytes de la DM parental y del nodo de referencia;
- identidad del binario SIESTA (hash + versión) y del perfil de backend;
- digests de pseudopotenciales y huella de proyectores;
- identidad del observable/parser (`siesta_occupations_total` vs traza de matriz) y su versión;
- nivel SCF;
- descomposición MPI: registrar; tratar como no-identidad hasta que la validación de camino demuestre equivalencia por debajo de \(q\).

Una corrida del nivel estricto **no** es reutilizable en un estimador de nivel base. El enclavado actual de `build_adaptive_campaign_dag` (sitio, \(\alpha\), modo, nivel SCF, referencia) ya cubre la mayor parte.

### I.10 Estados de salida

`QUALIFIED`, `QUALIFIED_HETEROGENEOUS`, `REVIEW` (evidencia válida, presupuesto > \(\tau_U\) o noise floor sólo parcialmente establecido), `NOT_ESTABLISHED` (no hay estimador admisible en la red), `NOT_DIFFERENTIABLE_AT_SCALE`, `FAIL` (evidencia inválida/incompleta). Nombre del artefacto: **Response Error-Budget Qualification** — no "certificate".

---

## J. Complete algorithm

```text
INPUT  protocol P (versioned): lattice L, ratio data, estimator family F, SCF levels {L0,L1,L2},
                               tightening factors, theta, kappa, rho_max, budget limits
       requirement tau_U (user-declared), correlated-subspace inventory S, reference R(L0)
STATE  evidence set E = set of validated records keyed by
       (site, mode, alpha, scf_level, reference_node, observable_id, run_identity_digest)

S0  PREFLIGHT
    - every a in L representable at FDF precision        else FAIL(lattice_not_representable)
    - S from FDF, no inferred equivalences              else FAIL(inventory)
    - observable_id fixed for the campaign              else FAIL(observable_mixing)

S1  SEED ROUND (pure function of P)
    - BARE: all columns J, amplitudes L_seed_bare (cheap, wide)
    - SCREENED: all columns J, amplitudes L_seed_scr
    - SCF ladder nodes: for each J, SCREENED +-a at levels L1,L2 for a in {min, max of L_seed_scr};
      BARE +-a_min from reference R(L1); references R(L1), R(L2)
    -> request set Q0 = g0(P)

LOOP over rounds t = 0,1,...  (barrier: analysis starts only when all Q_t are terminal)
S2  EXECUTE Q_t, add validated records to E (failed runs recorded as failed, never retried silently)

S3  STATE GATE  (per J, m, point)  -> exclusion set X(E)
    - monotone rule: failure at a_k excludes a >= a_k for that (J, m)
    - if reference itself fails consistency                         -> FAIL(reference_state)
    - if every amplitude of some (J, m) excluded and smallest a in L reached
                                                                    -> NOT_DIFFERENTIABLE_AT_SCALE(J,m)

S4  NOISE FLOOR (per J, m)
    - q from tokens (exact)
    - ladder: eta1, eta2 on Delta(a); contraction eta2 <= rho_max * eta1 or both <= print level
        ok   -> eps_abs, eps_rel = theta * eta1/(1 - rho_hat) split by small/large amplitude
        else -> mark NOISE_FLOOR_NOT_ESTABLISHED(J, m)  (decision capped at REVIEW)
    - BARE: reference bias from R(L1) vs R(L0); delta0 from even-part fit (reported)

S5  BUDGETS (per J, m, I) on E \ X
    - s_k, nu_k, drifts, order verification (I.2)
    - candidates in F with B_E (I.3); include protocol estimator if declared

S6  FALSIFICATION
    - neighbour consistency (kappa)           -> drop inconsistent candidates
    - reciprocity for I != J                  -> violation: mark BUDGET_FALSIFIED(I,J) => REVIEW
    - declared-equivalence residuals          -> same

S7  COLUMN QUALIFICATION
    - choose E* = argmin B_E (deterministic tie-break)
    - column qualified if every I has an admissible E*

S8  MATRIX / REQUIREMENT
    - beta0, beta < 1 with full budgets       else MATRIX_NOT_RESOLVED
    - deltaU_KK <= tau_U for all K            else REQUIREMENT_NOT_MET

S9  NEXT ROUND  Q_{t+1} = g(E, P)  (pure function; no history counters)
    for each (J, m) not qualified, in fixed sorted order:
      a) noise-limited (smallest usable B dominated by nu, larger amplitudes not excluded)
           -> add next larger lattice level for (J,m) if not excluded and exists
      b) truncation-limited (B dominated by truncation, order verified)
           -> add next smaller lattice level if exists
      c) order unresolved but drifts resolved -> add one level adjacent to the resolved pair
      d) REQUIREMENT_NOT_MET with B dominated by SCF term
           -> request next stricter SCF level for the whole campaign (all columns, one level)
              only if declared in P; otherwise stop
      e) none applicable -> no addition for (J,m)
    if Q_{t+1} empty or budget exhausted -> exit loop

S10 DECISION (pure function of E and P)
    FAIL                         if any invalid/incomplete evidence or protocol violation
    NOT_DIFFERENTIABLE_AT_SCALE  if any (J,m) so marked
    NOT_ESTABLISHED              if some (J,m) has no admissible estimator
    REVIEW                       if NOISE_FLOOR_NOT_ESTABLISHED, BUDGET_FALSIFIED,
                                 MATRIX_NOT_RESOLVED or REQUIREMENT_NOT_MET
    QUALIFIED_HETEROGENEOUS      if all qualified but grids/estimators differ by (J,m)
    QUALIFIED                    otherwise
    emit ResolvedResponseProtocol + ResponseErrorBudgetQualification (+ evidence digest of E)
```

**Determinismo.** (i) \(\mathcal E\) es un conjunto (sin orden) y todas las funciones \(f\), \(g\) lo leen ordenado por clave; (ii) barrera por ronda: el orden de terminación dentro de una ronda no afecta a nada; (iii) sin contadores históricos — dos campañas que reúnen el mismo \(\mathcal E\) por caminos distintos producen la misma decisión; (iv) red finita y añadidos monótonos ⇒ terminación garantizada; (v) desempates deterministas.

---

## K. Threshold strategy

| Cantidad | Naturaleza | Cómo se establece |
|---|---|---|
| \(q\) | Derivada | Exacta desde tokens. Sin umbral. |
| \(G\), \(\mu_p\), pesos | Derivada | Algebraica desde la malla y el estimador. Sin umbral. |
| \(\eta\), \(\hat\rho\) | Medida | Escalera SCF por campaña. |
| \(\tau_U\) | **Requisito declarado** | Lo fija el usuario por razones científicas antes de ver resultados; no se calibra. |
| \(\theta\) (seguridad de la escalera) | **Parámetro a validar** | Elegir el menor valor que logra la cobertura objetivo predeclarada frente a referencia de alta precisión (T2) en desarrollo; congelar; evaluar en holdout. |
| \(\rho_{\max}\) (contracción aceptable) | **Parámetro a validar** | Igual que \(\theta\); además verificar en T0 con contracción conocida. |
| \(\kappa\) (consistencia/reciprocidad) | Parámetro | Por defecto 1 (intervalos estrictos); sólo aumentar con evidencia de que las cotas son conservadoras, nunca para hacer pasar casos. |
| Política de orden | Sin parámetro libre | Intervalos estrictos (§I.2). |
| Suavidad de la compuerta de estado | Derivada + validar | Error de los observables de estado (impresión + escalera); el orden polinómico admitido se fija en el protocolo y se valida con casos de cambio de rama inducidos. |
| Red \(\mathcal L\), presupuesto de corridas | Constantes de protocolo | Representabilidad + coste; validar insensibilidad desplazando la red (T2). |

Proceso: preregistro de (\(\theta,\rho_{\max},\kappa\), red, familia de estimadores, objetivo de cobertura); calibración sólo en T0 + sistemas de desarrollo; congelación con versión; evaluación en holdout sin reajuste. Cualquier cambio posterior ⇒ nueva versión y nuevo holdout. Los umbrales históricos V6 permanecen intactos y no se reutilizan como parámetros de FD-EBQ.

---

## L. Validation program

**T0 — Sintético con verdad conocida** (usar `synthetic_backend/`: `population_generator.py`, `noise_injection.py`). Funciones \(n(\alpha)\) analíticas con \(\chi\), \(b_1\), \(b_2\) conocidos; ruido de impresión exacto; ruido SCF absoluto, relativo, correlacionado entre \(\pm a\); sesgo común; términos \(\alpha|\alpha|\); saltos de rama a un lado; matrices casi singulares. Métricas: cobertura (verdad dentro de \(B\)), tasa de PASS falso, tasa de rechazo de casos sanos, determinismo bajo permutación de llegada.

**T1 — Modelo de campo medio interno** (Hubbard de pocos sitios autoconsistente, rápido): derivada analítica por solución lineal, multisitio, condicionamiento controlable, multiestabilidad controlable.

**T2 — Referencia SIESTA de alta precisión (núcleo de la validación).** Para cada sistema: escalera densa de amplitudes, SCF muy estricto y **el build con salida `f20.12`** (`reserved_external_patches/`) usado **sólo como referencia de validación**, nunca como producto. Comparar la decisión y la cota de FD-EBQ con salida estándar frente a la "verdad" de alta precisión. Incluye verificación de reciprocidad y de la contabilidad energética de `DFTU.PotentialShift`.

**T3 — Controles negativos inducidos.** Amplitudes deliberadamente demasiado pequeñas y grandes, SCF flojo, DM parental no convergida, rama forzada: todos deben ser señalados (PASS falso = 0).

**T4 — Cruce entre códigos (opcional, débil).** Comparación cualitativa con DFPT (`hp.x`) sólo de tendencias de \(\chi^0,\chi\); los proyectores difieren, así que no es una referencia cuantitativa.

**Clases de benchmark mínimas** (desarrollo = NiO, FeO, CoO, MnO; el resto holdout):

| Clase | Ejemplos posibles | Qué estresa |
|---|---|---|
| Óxido AFM de gap amplio | NiO (dev) | Caso fácil de control |
| Degeneración orbital / ramas | CoO, FeO (dev); un Jahn–Teller (LaMnO₃ o KCuF₃) holdout | Compuerta de estado |
| Respuesta apantallada pequeña | MnO (dev); d¹⁰ o d⁰ (ZnO, TiO₂) holdout | Límite de ruido |
| Metal | bcc Fe o Ni metálico; SrVO₃ | No analiticidad, smearing |
| Sitios inequivalentes | Fe₃O₄ (oct/tet) o una espinela | Mallas por columna |
| Muchos sitios | Supercelda de NiO con 8–16 sitios; un defecto | Escalado, condicionamiento |
| Proyector distinto (4f) | CeO₂ | Generalidad del proyector |
| Matriz casi singular | Par de sitios fuertemente acoplados, construido a propósito | Compuerta matricial |

**Criterios de éxito preregistrados:** cobertura ≥ objetivo declarado en T0 y T2; PASS falso = 0 en T3; ninguna violación de reciprocidad en casos `QUALIFIED`; decisiones invariantes bajo permutación de orden de llegada y desplazamiento de la red; acuerdo con revisión experta ciega en los casos holdout. Nunca: acuerdo de \(U\) con experimento o literatura.

---

## M. HubbardFlow integration

### M.1 Lo que ya existe (y FDRC-v1 no menciona)

| Archivo | Qué hace | Destino |
|---|---|---|
| `domain/alpha_selection.py` | Gate de 7 puntos, 3 ventanas OLS anidadas, defaults `residual_relative=0.02`, `slope_relative=0.05`, `min_signal_to_noise=10`, `magnetic_tolerance=0.05` | **Deprecar.** Umbrales inventados; residuo con parte par; magnetismo por constancia. Usado sólo por `tools/` históricos y tests. |
| `domain/adaptive_alpha.py` | Envoltorio del anterior; define **otra** `AdaptiveAlphaPolicy` | **Deprecar** (colisión de nombre con la de `adaptive_alpha_control.py`). |
| `domain/adaptive_alpha_control.py` | Controlador de rondas; `STOP_STABLE` por estabilidad de \(U\) en dos comparaciones; `stable_comparisons` histórico; "truncation metric" en eV de \(U\) | **Reemplazar la lógica de decisión** por \(f(\mathcal E,P)\); conservar presupuesto de nodos, representabilidad, concepto de probe SCF. |
| `execution/campaign_runner.py::_execute_adaptive_gate` | Llama a `decide_round` con métricas de \(U\) | Cambiar la llamada a la nueva función de calificación. |
| `execution/lr_dag.py::build_adaptive_campaign_dag` | DAG acumulativo, nodos por (sitio, \(\alpha\), modo, nivel SCF, referencia) | **Reutilizar** tal cual para rondas y escalera SCF. |
| `domain/occupation_noise_calibration.py` | Réplicas \(\alpha=0\) | Mantener como prueba de determinismo; no como noise floor. |
| `domain/response_grid_reproducibility.py`, `lr_analysis_v2._response_grid_empirical_widths` | Envolvente de réplicas de malla completa | Mantener como evidencia de camino (validación). |
| `siesta_backend/occupation_precision.py` | Cuantización exacta | **Reutilizar** (q). |
| `domain/quantized_response.py` | Propagación de impresión, \(\beta\) | Añadir función hermana con presupuesto completo; no modificar las existentes. |
| `domain/u_certification.py` | Certificación intervalar | **No tocar.** |
| `domain/matrix_lr.py::ResponseObservation` | Acopla BARE y SCREENED en el mismo \(\alpha\) | Ver M.3. |
| `domain/lr_analysis_v2.py::_validate_observations` | Exige "every perturbed site must use the same alpha grid" | Generalizar para el nuevo camino; conservar para FIXED. |
| `execution/campaign_v2.py::validate_lr_config` | `alpha_grid_ev` global único | Añadir bloque `perturbation_strategy`. |

### M.2 Frontera mínima

```text
FDF → preflight → subspace inventory
    → [response_strategy: FIXED_PROTOCOL_GRID | USER_EXPLICIT_GRID | CALIBRATED]
    → ResolvedResponseProtocol  (per (J,m): amplitudes, estimator id + weights, SCF level;
                                 reference identity; observable id; protocol version)
    + ResponseErrorBudgetQualification (may be NOT_ASSESSED for FIXED/USER)
    → production DAG (lr_dag) → χ0/χ via declared estimators → U → existing certification
```

**Auditoría de la abstracción "el resto no debe saber de dónde viene el plan":** es sólida **sólo** si el objeto lleva estimador, nivel SCF y mallas por \((J,m)\). Un `ResolvedPerturbationPlan` que sólo lleve amplitudes obliga a que el análisis elija el estimador por su cuenta (`LRAnalysisPolicy` en la campaña), y la calificación pierde su significado. Recomendación adicional: calcular el presupuesto también para FIXED y USER (en modo diagnóstico), para que el downstream sea uniforme y el V6 pueda *describirse* con el mismo lenguaje sin cambiarse.

### M.3 Módulos nuevos (dominio puro, sin E/S)

- `domain/response_error_budget.py`: odd/even, \(s_k\), \(\nu_k\), verificación de orden, candidatos y cotas, pesos de estimadores (incluido el cúbico V6), reciprocidad, propagación por influencia.
- `domain/scf_tolerance_ladder.py`: \(\eta\), contracción, separación abs/rel, estados.
- `domain/response_state_gate.py`: compuerta de estado sobre evidencia ya parseada (autovalores/subespacios de matrices locales, momentos, convergencia, gap).
- `domain/response_qualification.py`: \(f(\mathcal E,P)\) y \(g(\mathcal E,P)\) (decisión y siguiente ronda), salida `ResponseErrorBudgetQualification`.
- `domain/response_protocol.py`: `ResolvedResponseProtocol` (dataclass congelada, serializable, con digest).
- Modelo de datos: `ResponseColumnRecord` por \((J,m,\alpha,\text{nivel})\) — desacopla modos. Adaptador hacia `ResponseObservation` sólo para el camino FIXED existente.
- Backend: extender el parser (`siesta_backend/event_parser.py`, `parser_models.py`) para exponer matrices de ocupación locales completas y datos de convergencia por corrida, si no están ya accesibles.

---

## N. Preservation requirements

1. Tag `scientific-v6-final` / commit `45cb53c…`, todos sus artefactos y hashes (`MANIFEST.sha256`, `production_benchmarks_v6.zip*`, `validation_observables_v6/`, `results/stage-ub-v6-observables/`).
2. Las calificaciones V6 (NiO/FeO ACCEPTED, CoO REVIEW, MnO PROTOCOL_REVIEW_REQUIRED) y sus umbrales; este informe no las reinterpreta.
3. Definición de \(\chi^0\) (perfil `siesta-5.4.2-potential-shift-hamiltonian-v1`), de \(\chi\), y de \(U=(\chi^0)^{-1}-\chi^{-1}\); inversión directa; sin pseudoinversa ni regularización.
4. `domain/u_certification.py` y su semántica (impresión → intervalos → certificación).
5. Ruta de reinicio `DM.UseSaveDM true` y la identidad de la DM parental; no introducir `File.DM.Init`.
6. Camino FIXED_PROTOCOL_GRID reproducible bit a bit (mismo estimador cúbico, misma malla, mismo análisis), incluidas las restricciones de `_validate_observations` en ese camino.
7. Prohibición de inferir equivalencias de sitios.

---

## O. Implementation sequence

**Safe to implement immediately**
- `ResolvedResponseProtocol` y bloque `perturbation_strategy` (FIXED/USER/CALIBRATED como enum; CALIBRATED deshabilitado) con mallas y estimador por \((J,m)\).
- Desacoplar modos en el modelo de datos (registro por columna-modo), con adaptador al camino FIXED.
- `response_error_budget.py` en **modo diagnóstico**: pesos, ganancias, momentos, derivas, verificación de orden, reciprocidad, \(\delta_0\). Ejecutarlo sobre campañas existentes como *sidecar* (escrito fuera de las carpetas V6).
- Clave de identidad de reutilización completa (§I.9) sobre el enclavado actual de `lr_dag`.
- Deprecación explícita de `alpha_selection.py`/`adaptive_alpha.py` y resolución de la colisión `AdaptiveAlphaPolicy`.
- Retirar `STOP_STABLE` por estabilidad de \(U\) y el contador `stable_comparisons` de la ruta de decisión (puede quedar como diagnóstico reportado).
- Escalera SCF como **tipo de nodo** del DAG (ejecutable a demanda), sin que influya aún en decisiones automáticas.

**Requires scientific validation first**
- Uso de la escalera SCF como noise floor (\(\theta\), \(\rho_{\max}\)).
- Reciprocidad como compuerta (verificar operador adjunto en SIESTA 5.4.2).
- Compuerta de estado con autovalores/subespacios y criterio de suavidad.
- Selección automática por mínima cota y la estrategia CALIBRATED completa.
- Mallas heterogéneas por columna en producción.
- Consistencia energía–ocupación.
- Evaluación del presupuesto completo con Krawczyk como artefacto separado.

**Should not be implemented**
- Noise floor basado en réplicas \(\alpha=0\).
- Umbrales \(D_{\max}\), \(C_{\max}\), \(R_{\max}\), \(R^2\), o residuos del ajuste completo como criterio de linealidad.
- Intersección obligatoria BARE∩SCREENED o entre sitios como condición de fallo.
- Cualquier criterio de parada o selección basado en \(U\) (valor, estabilidad entre rondas, o sensibilidad lineal–cúbico como incertidumbre).
- Selección de ventana para mejorar \(\kappa\) o la invertibilidad.
- Calibración en un subconjunto de sitios "representativos" inferido automáticamente.
- El build `f20.12` como ruta de producto.

---

## P. Final recommendation

1. **¿Es defendible la calibración automática por diferencias finitas?** Sí, **condicionada** a: (a) calificación específica del estimador; (b) noise floor con escalera SCF sobre la diferencia \(\pm a\) y verificación de contracción; (c) verificación de orden; (d) requisito declarado sobre \(U\) propagado por las matrices; (e) validación T0/T2/T3 con holdout. Sin (b), no lo es: los errores independientes de \(a\) quedan fuera de alcance de cualquier lógica multiescala. No hace falta DFPT.

2. **¿Es FDRC-v1 el diseño correcto?** No. Su diseño de medición es bueno; su teoría de decisión no.

3. **¿Qué lo reemplaza?** FD-EBQ (§I–§J): presupuesto de error por \((J,m,I)\) para una familia cerrada de estimadores (central, Richardson con orden verificado, estimador protocolario), con falsación interna (vecinos, reciprocidad, equivalencias declaradas), compuerta de estado por suavidad, selección por mínima cota, aceptación en espacio de \(U\) frente a \(\tau_U\), mallas y estimadores por modo y columna, decisión \(f(\mathcal E,P)\) con barreras.

4. **¿Cuál es el mayor bloqueo científico?** Acotar la componente SCF del error —en particular la parte relativa/independiente de \(a\)— a partir de una escalera de tolerancias, y demostrar con referencia de alta precisión (T2) que la estimación \(\theta\eta_1/(1-\hat\rho)\) cubre el error real.

5. **¿Diseñar la metodología antes de la consolidación?** **Diseñar el contrato sí, ahora**: el modelo de datos actual (modos acoplados en `ResponseObservation`, malla común obligatoria en `lr_analysis_v2`, `alpha_grid_ev` global en `campaign_v2`) incrusta exactamente las restricciones que esta revisión rechaza, y consolidar sobre él las congelaría. **Habilitar el selector automático no**: eso espera a la validación. La consolidación debe además reducir los tres mecanismos de \(\alpha\) existentes a uno.

6. **Evidencia mínima antes de habilitar el selector para usuarios:**
   - T0: cobertura ≥ objetivo preregistrado en toda la batería adversarial, determinismo bajo permutación.
   - T2: en todos los sistemas de desarrollo **y** en al menos un representante holdout de cada clase de §L (incluido un metal, un sistema heterogéneo y uno de muchos sitios), la verdad de alta precisión cae dentro de la cota en todos los casos calificados.
   - T3: cero PASS falsos.
   - Ninguna violación de reciprocidad en casos `QUALIFIED`; reciprocidad del operador verificada en SIESTA 5.4.2.
   - Parámetros \(\theta,\rho_{\max},\kappa\) congelados y versionados antes de evaluar el holdout.
   - Hasta entonces, CALIBRATED sólo en modo **asesor**: produce el informe de presupuesto y una propuesta, y el usuario firma la elección como USER_EXPLICIT_GRID.

---

## Apéndice 1 — Reanálisis ilustrativo de CoO V6 (desarrollo, post-hoc)

**Derivas de la pendiente central** (malla 0.02/0.04/0.06 eV; para \(b_1a^2\) puro el cociente es \(20/12=1.667\)):

| Elemento | \(s(0.02)\) | \(s(0.04)\) | \(s(0.06)\) | Cociente | Régimen |
|---|---|---|---|---|---|
| BARE \(\chi^0_{00}\) | −1.351575 | −1.340237 | −1.321592 | 1.645 | Truncamiento suave, orden 2 verificado |
| BARE \(\chi^0_{10}\) | 1.201775 | 1.190037 | 1.170808 | 1.638 | Ídem |
| SCREENED \(\chi_{00}\) | −0.117175 | −0.117163 | −0.117108 | 4.3 | Ruido, signo/cociente erráticos |
| SCREENED \(\chi_{10}\) vs \(\chi_{01}\) | 0.034650 / 0.034650 | 0.034662 / 0.034675 | 0.034617 / 0.034575 | — | Reciprocidad exacta a 0.02; residuo \(4.2\times10^{-5}\) a 0.06 > \(2q/a\) |

**Parte par BARE:** \(e(a)=\delta_0+c_2a^2+c_4a^4\) con \(\delta_0=+1.9\times10^{-5}\) (sitio 0) y \(-2.1\times10^{-5}\) (sitio 1), \(c_2\approx0.35\), \(c_4\approx-7.8\).

**\(U\) por sitio (eV) con distintos estimadores** (sitios equivalentes por simetría AFM):

| Estimador | \(U_0\) | \(U_1\) | \(|U_0-U_1|\) |
|---|---|---|---|
| Central 0.02 (ambos modos) | 5.81843 | 5.81843 | <10⁻¹⁴ |
| Central 0.06 | 5.83906 | 5.84104 | 2.0×10⁻³ |
| Lineal OLS 6 pt | 5.83431 | 5.83528 | 9.7×10⁻⁴ |
| **Cúbico 6 pt (V6)** | 5.81715 | 5.81502 | 2.1×10⁻³ |
| BARE Richardson / SCREENED central 0.02 | 5.81609 | 5.81610 | 1.1×10⁻⁵ |
| BARE cúbico / SCREENED central 0.02 | 5.81691 | 5.81688 | 2.3×10⁻⁵ |

Lectura: la asimetría entre sitios equivalentes del estimador V6 procede de amplificar el ruido SCREENED con un estimador diseñado para eliminar truncamiento; tratar cada modo según su régimen la elimina. **No se propone recalcular ni reclasificar CoO.**

## Apéndice 2 — Prueba sintética de cobertura (400 ensayos por caso)

| Caso | Aceptados | Cobertura | Cota relativa mediana | Estimador elegido |
|---|---|---|---|---|
| BARE-like, sólo impresión | 400 | 1.000 | 1.2×10⁻⁴ | Richardson |
| SCREENED-like, SCF abs. conocido | 400 | 1.000 | 2.6×10⁻³ | Central |
| SCREENED-like, SCF rel. conocido | 400 | 1.000 | 3.9×10⁻³ | Central |
| SCREENED-like, SCF abs. **asumido 0** | 400 | 0.983 | 8.5×10⁻⁴ | Central |
| **Sesgo SCF relativo común** | 400 | **0.000** | 7.5×10⁻⁴ | Central |
| Término impar no analítico \(\kappa\alpha|\alpha|\) | 400 | 1.000 | 8.5×10⁻³ | Central (orden 1) |

Sin verificación de orden, el caso no analítico tenía cobertura 0 y el de noise floor subestimado 0.58. El caso de sesgo común permanece en 0 con cualquier lógica multiescala: es la demostración operativa del bloqueo principal.

## Apéndice 3 — Reproducción

```bash
git checkout codex/hubbardflow-rename
python fdrc_review_numerics.py \
  results/stage-ub-v6-observables/coo-u-b-campaigns/stageubv6-coo-a0/lr_u_analysis.v3.json
```
