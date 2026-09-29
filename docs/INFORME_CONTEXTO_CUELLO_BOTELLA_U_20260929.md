# Informe de contexto: cuello de botella para obtener y reportar U con SIESTAFLOW

**Fecha:** 2026-09-29  
**Propósito:** entregar a otro asistente un estado técnico suficientemente completo para razonar sobre rutas de investigación, cuestionar las hipótesis actuales y proponer el siguiente paso que más información aporte.  
**Alcance de este informe:** síntesis y análisis de evidencia ya existente. No autoriza una campaña nueva, ejecución de SIESTA, cambios a código de SIESTA, cambios a datos históricos ni modificaciones de tolerancias.

**Estado terminal del cierre P0–P6 registrado el 2026-09-28:** `PRODUCT_BLOCKED`.
Las puertas operativas P0–P6 pasaron y se construyó el wheel 0.1.2, pero el
resultado P5 quedó como `NUMERICAL_CANDIDATE_UNASSESSED` / `NOT_ESTABLISHED`.
Según el [registro final de ejecución](P0_EXECUTION_20260928.md), eso no
satisface el objetivo científico que el usuario exige para considerar listo el
producto. Este informe busca una vía para resolver ese bloqueo; no reclasifica
el estado terminal.

**Disponibilidad del repositorio:** la implementación 0.1.2, varios módulos
v3, pruebas y documentos de cierre están reunidos en la rama local
`codex/sync-product-20260929`, pendiente de envío. Una lectura de GitHub por
sí sola refleja aún una versión anterior. Véase
el [inventario de sincronización](ESTADO_REPOSITORIO_Y_PUBLICACION_20260929.md)
antes de atribuir a la rama remota el estado de este expediente.

---

## 1. Resumen ejecutivo

El problema que se quiere resolver no es simplemente “hacer que el reporte diga que U sirve” ni “conseguir más decimales”. La necesidad central es que SIESTAFLOW pueda producir una respuesta de Hubbard U que sea **numéricamente útil, reproducible bajo un protocolo explícito y presentada con una interpretación honesta**, usando instalaciones de SIESTA soportadas sin modificarlas.

El cierre ejecutado de P0–P6 entregó el flujo operativo y una campaña P5 de
25 nodos, pero terminó en **`PRODUCT_BLOCKED`** por el objetivo científico de
U pendiente. `0.1.2` identifica el paquete construido y probado; no debe
interpretarse como declaración de `PRODUCT_READY`.

Hoy hay una diferencia fundamental entre dos preguntas:

1. **¿El software funciona como herramienta?** Puede recibir una estructura/configuración, preparar y ejecutar el protocolo soportado, registrar procedencia, analizar la respuesta y generar resultados reproducibles o un estado terminal informativo.
2. **¿Está establecida la aceptación numérica o física de un U concreto para NiO?** Eso requiere criterios y evidencia adicionales. Un candidato numérico puede ser útil sin que la aceptación física esté establecida.

El reporte actual de la campaña adaptativa NiO comunica `NUMERICAL_CANDIDATE_UNASSESSED` y `NOT_ESTABLISHED` para aceptación física porque no había una tolerancia de sensibilidad declarada antes de esa campaña. El algoritmo `STOP_STABLE` indica que se cumplió su regla de parada de refinamiento adaptativo; **no** convierte por sí solo esa regla en una garantía de exactitud física.

El objetivo operativo que el usuario escogió después es ±0.02 eV por sitio para `U_scalar_charge`. Es un objetivo de ingeniería/aceptación numérica para investigar, no una constante física universal ni un umbral reconocido automáticamente por todos los métodos. El hecho de que una cota determinista conservadora exceda 0.02 eV significa que **el procedimiento actual no certifica ese objetivo bajo esa cota**. No prueba que el error real de U exceda 0.02 eV, que U sea inútil, ni que el método de respuesta lineal haya fallado.

La cota cúbica primaria que aparece en el resultado adaptativo es **0.03436273105 eV**. La cifra **0.01353711826 eV** corresponde a un ajuste lineal diagnóstico. No deben intercambiarse: provienen de estimadores distintos. Para otra malla/campaña fija P5, la cota determinista de impresión v3 reportada es aproximadamente **0.01183306193 eV** por sitio. Las magnitudes difieren porque la propagación depende de la malla, de las observaciones usadas y del estimador.

La evidencia ya descarta una atribución simple de una diferencia entre campañas al ruido SCF: al releer con el mismo analizador v3, la distancia P5–adaptive ronda 10.22 meV por sitio y queda dentro de las cotas deterministas de impresión de ambas. En cambio, aplicar v2 y v3 a los mismos archivos adaptativos cambia U en aproximadamente 30.5–31.6 meV, lo que demuestra que cambiar la fuente/semántica de ocupación y el analizador puede mover el resultado más que la diferencia entre campañas. Esa incompatibilidad histórica ya está identificada y no debe mezclarse con repetibilidad SCF.

La comparación pública con otros códigos da contexto, no un criterio de aceptación: Quantum ESPRESSO muestra U diagonal con cuatro decimales en su salida normal y matrices con seis decimales en salida más detallada; su documentación configura por separado umbrales de convergencia. Un correo de desarrolladores explica un formato de 15 decimales para una matriz y una corrección de ancho de campo para evitar que números negativos queden pegados. VASP presenta ocupaciones con tres decimales en un tutorial. Ninguno de esos decimales demuestra por sí mismo exactitud de U, y sus algoritmos/observables pueden no ser comparables con SIESTAFLOW.

Por ello, las rutas prometedoras no deben presuponer que el cuello de botella es `f12.6`, ni que el umbral ±0.02 es físicamente obligatorio, ni que el análisis actual sea necesariamente demasiado estricto. Primero hay que localizar qué componente consume el margen y qué afirmación se desea garantizar: resolución de impresión, robustez del estimador, repetibilidad SCF, estabilidad del protocolo o concordancia con un valor físico independiente. Estas son afirmaciones diferentes y requieren pruebas distintas.

---

## 2. Qué es el proyecto y qué se quiere entregar

`siestaflow_hubbard` es una utilidad independiente para calcular y reportar la respuesta de carga asociada a perturbaciones locales de tipo Hubbard en SIESTA. Automatiza el protocolo de campaña y conserva la relación entre entradas, nodos, salidas y análisis, en vez de exigir que una persona coordine manualmente cada cálculo y reconstruya después la procedencia.

El flujo de usuario previsto es, en términos generales:

```text
configurar entradas y sitios
        ↓
init → run / status / resume → report
        ↓
campaña trazable → respuesta por sitio → JSON versionado + informe Markdown
```

El CLI contempla los comandos `init`, `run`, `status`, `resume`, `report` y `stop`. La operación objetivo incluye PowerShell→WSL y ejecución Linux; existe además una ruta para usar una asignación Slurm ya concedida. La herramienta no debe depender de una recompilación privada de SIESTA: la portabilidad a instalaciones soportadas de SIESTA es parte del valor del producto.

El eje rector vigente es [`docs/EJE_RECTOR_CIERRE_PRODUCTO.md`](EJE_RECTOR_CIERRE_PRODUCTO.md). Define la utilidad independiente como producto y distingue el cierre del producto de la aceptación física de cada material. El plan documenta límites del alcance, puertas, rutas de investigación y estados terminales. No autoriza por sí mismo una campaña adicional.

### 2.1 Observable reportado

El método estima las matrices de respuesta sin pantalla y apantallada:

\[
\chi^0_{IJ}=\left.\frac{\partial n_I^{\mathrm{BARE}}}{\partial\alpha_J}\right|_{0},\qquad
\chi_{IJ}=\left.\frac{\partial n_I^{\mathrm{SCREENED}}}{\partial\alpha_J}\right|_{0}.
\]

La cantidad implementada como `U_scalar_charge` es:

\[
U_I=\left[(\chi^0)^{-1}-\chi^{-1}\right]_{II}.
\]

Aquí `I` identifica el sitio y `J` el sitio perturbado. La ocupación proyectada depende de la definición de orbitales/proyector y de la forma en que se extrae de la salida. `U_scalar_charge` no es automáticamente `Ueff_Dudarev`; SIESTA aplica en su implementación colineal de Dudarev una combinación `U-J`, y una equivalencia requeriría un contrato físico separado. Tampoco se debe etiquetar automáticamente un elemento fuera de la diagonal como el parámetro V de otro funcional.

### 2.2 Alcance científico/técnico

El alcance certificado de la versión se centra en SIESTA 5.4.2 y en los modos de espín con protocolo y parser probados. No promete un U material universal, ni cobertura automática de SOC, espín no colineal o cálculo separado de J. La aceptación de la herramienta no se decide comparando U con literatura, gaps, parámetros de red ni el valor esperado para NiO. Esas comparaciones pueden describirse como contexto externo, pero no usarse para elegir α, ventana, estimador o valor de U.

---

## 3. El caso que origina el cuello de botella: NiO

El caso central es NiO antiferromagnético tipo II con PBE y dos sitios correlacionados inequivalentes en el modelo de respuesta, reportados como `NiLR0` y `NiLR1`. El método aplica perturbaciones locales α, realiza cálculos BARE y SCREENED según el protocolo y reconstruye las respuestas para calcular U por sitio.

Hay más de una generación de campaña y análisis. Es esencial no tratarlas como si fueran una serie homogénea:

| Elemento | Contexto | Lo que significa |
|---|---|---|
| Campaña adaptativa histórica/v2 | 41 nodos en total: 1 referencia, 20 BARE y 20 SCREENED a través de rondas adaptativas | Registró el protocolo adaptativo y análisis inicial; parte del resultado quedó ligada a la fuente de ocupación/semántica v2. |
| Reanálisis de los mismos OUT adaptativos con v3 | Usa el mismo material producido, pero selector/parser/análisis actuales | Permite comparar método de extracción de forma controlada; no es una nueva campaña SIESTA. |
| Cierre fijo P5/v3 | Malla fija de 25 nodos documentada para el cierre anterior | Resultado de otro protocolo/malla; no es una réplica certificada de la campaña adaptativa. |
| Posible calibración futura | Contrato separado propone tres réplicas completas y una primaria preregistrada | Un diseño prospectivo de hasta 100 nodos (25 + 3×25); es propuesta, no autorización ni ejecución pendiente automática. |

La ruta P5 previa tuvo un límite de campaña de hasta 25 nodos para la alternativa NiO seleccionada. Ese límite no debe confundirse con el diseño prospectivo de 100 nodos de calibración: son objetivos y contratos distintos. No hay autorización vigente para iniciar otra campaña.

### 3.1 Valores y reportes adaptativos actuales

El reporte adaptativo v3 asociado a la campaña UUID `99d5ee67-d9cf-41f1-9f8f-39315c6e81fd` identifica el material `NiO-AFMII-PBE`, SIESTA 5.4.2, analizador v0.1.2 y esquema v3. Informa, aproximadamente:

| Magnitud | NiLR0 | NiLR1 |
|---|---:|---:|
| `U_scalar_charge` en el análisis adaptativo v3 | 6.86706412 eV | 6.86623404 eV |
| Diagnóstico de sensibilidad al estimador | 0.00604 eV | 0.00534 eV |
| Diagnóstico de sensibilidad a ventana | 0.004777 eV | 0.004359 eV |
| Condición de χ⁰ | rango 2/2; condición ≈1.745 | rango 2/2; condición ≈1.745 |
| Condición de χ | rango 2/2; condición ≈1.024 | rango 2/2; condición ≈1.024 |

Las cifras de sensibilidad son diagnósticos empíricos entre decisiones de análisis consideradas; no son automáticamente errores estándar, intervalos de confianza ni cotas del error verdadero. Los valores de condición sugieren que las matrices de este reporte no son severamente mal condicionadas en el sentido numérico habitual. Eso reduce la plausibilidad de que una singularidad obvia sea el único cuello de botella, pero no reemplaza una inspección completa de propagación de perturbaciones ni prueba la calidad física del proyector.

El algoritmo adaptativo registró decisiones de refinamiento en las rondas anteriores y `STOP_STABLE` al final, tras dos comparaciones consecutivas equivalentes que pasaron su regla interna. La ventana activa reportada y el conjunto final de α forman parte del protocolo analizado. `STOP_STABLE` expresa estabilidad respecto de esa regla; no equivale a “la sensibilidad física está bajo ±0.02 eV”, porque en esa campaña `sensitivity_tolerance_eV` quedó sin configurar.

### 3.2 Campañas no equivalentes: comparación cuantitativa

El contrato de precisión registra una reconstrucción v3 comparable de dos fuentes existentes:

| Fuente/método de análisis | NiLR0 (eV) | NiLR1 (eV) |
|---|---:|---:|
| Adaptive round-00, análisis histórico v2 | 6.8845915692 | 6.8857890044 |
| Los mismos archivos adaptativos, reextraídos y analizados con v3 | 6.8540481204 | 6.8541678955 |
| P5, análisis v3 | 6.8642677000 | 6.8643874752 |

Al comparar P5 y adaptive con el mismo tratamiento v3, la diferencia es de unos **10.2196 meV por sitio**, esencialmente igual en ambos sitios. Las cotas deterministas de impresión v3 citadas para esas dos reconstrucciones son aproximadamente **11.8331 meV** y **11.8342 meV**. Por tanto, esa diferencia cae dentro de las cotas de impresión consideradas y no permite aislar por sí sola una contribución SCF/reproducibilidad.

En cambio, v2 frente a v3 aplicado a los mismos OUT adaptativos cambia U aproximadamente **30.5434 meV** para NiLR0 y **31.6211 meV** para NiLR1. La diferencia se asocia al cambio de fuente/interpretación de ocupación (`matrix_trace` en el tratamiento histórico v2 frente a `siesta_occupations_total` en v3), junto con la versión/selector de análisis. **No es ruido de ejecución de SIESTA**, porque los archivos de salida son los mismos. La comparación histórica de 20–21 meV entre campañas no debe atribuirse a SCF sin corregir primero esa diferencia semántica.

Se validaron receipts de 25/25 nodos en cada campaña comparada para FDF/OUT/DM, con identificadores de campaña, nodos y ejecuciones distintos. Se comparte la referencia DM SHA y ciertos metadatos; ambas declaran SIESTA 5.4.2, el mismo path y texto de versión. Sin embargo, no se archivó hash de contenido del ejecutable. Esto sirve para el reanálisis diagnóstico, pero no constituye calibración formal de reproducibilidad entre binarios.

---

## 4. Qué significan los estados actuales

El resultado más reciente relevante se clasifica como:

```text
NUMERICAL_CANDIDATE_UNASSESSED
physical_acceptance: NOT_ESTABLISHED
```

La lectura correcta es que se produjo un candidato numérico con análisis reproducible, pero el protocolo no permite afirmar aceptación bajo un criterio de sensibilidad/precisión declarado antes de la campaña y la aceptación física permanece fuera de lo establecido. No significa “U no sirve”, “el cálculo fracasó” o “la herramienta no funciona”.

Tampoco hay que invertir el error y afirmar que el U está garantizado dentro de ±0.02 eV. Con la evidencia actual, esa afirmación tampoco está demostrada.

El plan de cierre contempla conceptualmente que una utilidad pueda funcionar
aunque un material particular termine como candidato sensible o sin aceptación
física. La decisión final del flujo ejecutado fue más exigente: el usuario
consideró que el objetivo científico principal seguía sin resolverse y el
registro terminal fijó `PRODUCT_BLOCKED`. Por eso la entrega operativa del
paquete y el estado del producto deben comunicarse por separado. Resolver el
bloqueo requiere una afirmación útil y respaldada sobre U, no sólo cambiar la
etiqueta del resultado.

---

## 5. Objetivo ±0.02 eV: estatus y límites

El documento [`docs/U_PRECISION_ACCEPTANCE_CONTRACT_20260928.md`](U_PRECISION_ACCEPTANCE_CONTRACT_20260928.md) consolida ±0.02 eV por sitio para `U_scalar_charge` como el objetivo operativo futuro elegido por el usuario. El contrato advierte que:

- no es una tolerancia física universal;
- no se debe modificar α, proyectores, ventanas, umbrales SCF, estimador o criterios al ver el U para forzar que pase;
- el objetivo debe estar preregistrado para una evaluación prospectiva;
- una envolvente empírica solo permite una afirmación condicional al protocolo observado;
- aun un pase numérico condicional no implica aceptación física;
- `total_numerical_U_interval` puede seguir como `NOT_ESTABLISHED` aunque el protocolo muestre reproducibilidad condicional.

Para P5, el contrato calcula una suma parcial conservadora bajo el modelo compuesto de redondeo, sensibilidad de estimador y ventana. Incluso tomando como cero el spread observado de réplicas, esa suma es aproximadamente:

| Sitio | Suma parcial bajo la fórmula conservadora actual |
|---|---:|
| NiLR0 | 0.0275105 eV |
| NiLR1 | 0.0279243 eV |

Ambas superan ±0.02 eV. La consecuencia exacta es: **el contrato actual, con esa composición conservadora, no puede certificar ±0.02 eV en P5**. No se sigue lógicamente que el error real esté por encima de 0.02 eV. La cota es determinista respecto de intervalos de cuantización y puede resultar conservadora; las sensibilidades son diagnósticos, no necesariamente incertidumbres independientes que deban sumarse linealmente como componentes de error.

Por separado, la cota cúbica primaria adaptativa del informe de cierre es **0.03436273105 eV**. El ajuste lineal diagnóstico entrega **0.01353711826 eV**. Que el lineal quede por debajo de 0.02 eV no habilita escogerlo después de ver el resultado. Para preferir un estimador se requiere una razón metodológica predeclarada, validación adecuada o un contrato que explique qué estimando se quiere obtener. El número mayor tampoco prueba que el valor real esté mal: señala que la propagación conservadora asociada al cúbico no satisface el criterio operativo en ese análisis.

### Distinción esencial: cinco conceptos distintos

1. **Decimales impresos:** formato de texto del programa. Determina la resolución de la entrada observada por el parser, no la exactitud física.
2. **Cota determinista de redondeo:** propagación de intervalos de redondeo a través del ajuste y la inversión de matrices bajo supuestos explícitos. Es una envolvente de posibilidad, no una distribución de probabilidad.
3. **Sensibilidad al estimador/ventana:** cambio observado al variar modelos o subconjuntos definidos. No es automáticamente error ni incertidumbre estadística.
4. **Variabilidad SCF/reproducibilidad:** diferencia observada entre ejecuciones bajo protocolo comparable. Requiere separar redondeo, entradas, binario, ramas magnéticas y criterio de convergencia.
5. **Error/aceptación física verdadera:** cuánto se aparta el resultado del objeto físico que se quiere describir. No se deduce sólo de los cuatro anteriores, ni de acuerdo con literatura.

El contrato no debe fusionar esos conceptos sin demostrar independencia, supuestos de distribución o cobertura. En particular, una suma lineal de cotas puede ser deliberadamente segura, pero no es una estimación típica del error si sus contribuciones están correlacionadas o describen distintas variaciones diagnósticas.

---

## 6. ¿Qué dicen los decimales de otros códigos?

Se consultaron fuentes técnicas oficiales o de primera mano. La comparación ayuda a cuestionar qué precisión de presentación es razonable, pero no determina cuántos decimales debe aceptar SIESTAFLOW.

### Quantum ESPRESSO / `hp.x`

- El código fuente oficial de QE 7.5, `HP/src/hp_postproc.f90`, escribe los valores diagonales de Hubbard U en salida normal con formato `f10.4`, cuatro posiciones decimales. Con verbosidad mayor escribe matrices Hubbard y respuestas con `f11.6`, seis posiciones decimales. [Fuente: QE 7.5 `hp_postproc.f90`](https://gitlab.com/QEF/q-e/-/raw/qe-7.5/HP/src/hp_postproc.f90).
- La documentación de `hp.x` define por separado `conv_thr_chi` (umbral de convergencia de respuesta, con valor por defecto documentado de `1.D-5`) y `ethr_nscf` (`1.D-11`). Un umbral interno de iteración es distinto de los decimales con que se imprime U o χ. [Fuente: documentación `INPUT_HP`](https://www.quantum-espresso.org/Doc/INPUT_HP.html).
- En una respuesta de la lista oficial de desarrolladores sobre QE 6.7 se cita que `hp_write_chi_full.f90` escribía matrices con `f19.15`; la sugerencia de cambiar a `f20.15` se hizo para añadir un espacio y evitar que valores negativos consecutivos quedaran pegados, no como certificación de quince decimales de exactitud. [Fuente: lista QE developers](https://lists.quantum-espresso.org/pipermail/developers/2021-July/002428.html).

### VASP

El tutorial de respuesta lineal de VASP muestra ocupaciones con tres decimales y un ejemplo de análisis lineal de U a partir de una sola perturbación y de un ajuste con varias perturbaciones, que produce valores distintos (aprox. 6.33 eV y 5.58 eV en ese ejemplo). Eso ilustra que el diseño de perturbaciones/ajuste puede mover U más que el conteo de decimales mostrado en una tabla; no permite comparar directamente esos números con NiO/SIESTA. [Fuente: VASP Wiki, Calculate U](https://vasp.at/wiki/index.php/Calculate_U_for_LSDA%2BU).

### Conclusión prudente de la comparación

Hay códigos que presentan U con menos decimales y matrices con más; esto es habitual porque el formato responde a necesidades de lectura, depuración y postproceso. No se encontró en estas fuentes una regla física universal del tipo “el U queda validado a N decimales” o “una tolerancia de 0.02 eV es obligatoria”. Tampoco se puede concluir que 4 decimales publicados por QE signifiquen que sus U tienen incertidumbre de 0.0001 eV, ni que 15 decimales internos sean quince dígitos significativos físicamente confiables.

La pregunta útil no es solamente “cuántos decimales imprimen otros códigos”, sino “qué afirmación cuantitativa hace SIESTAFLOW, qué evidencia la respalda y qué precisión de presentación evita insinuar más conocimiento del que hay”. Si U se reporta a centésimas, eso puede ser una convención de presentación; no demuestra automáticamente una cota de ±0.01 eV.

---

## 7. Hipótesis abiertas sobre el cuello de botella

Las hipótesis siguientes son explicaciones alternativas que se deben discriminar; no son resultados aceptados de antemano.

### H1. La propagación de cuantización es conservadora, pero el peor caso es físicamente inverosímil

La ocupación `Occupations:` se imprime con seis decimales en la ruta v3. El lector deriva un intervalo de cuantización por observación y propaga sus extremos al resultado. Al invertir matrices, las combinaciones de extremos pueden ser muy conservadoras, especialmente si se tratan como independientes aunque provengan de cantidades vinculadas o de redondeo correlacionado.

**A favor:** las cotas de impresión superan el cambio observado entre P5 y la reextracción adaptive v3; el actual análisis de cotas no constituye un experimento de errores reales.  
**No demostrado:** que la cota sea excesivamente conservadora en este problema concreto; correlación favorable suficiente; o que el valor probable de redondeo sea <0.02 eV.

### H2. El rango de α, la ventana o el grado del ajuste domina la variación

La sensibilidad adaptativa reportada a estimador y ventana está en varios meV por sitio, y la cota cúbica primaria es mayor que la cota del ajuste lineal diagnóstico. El resultado depende de cómo se aproxima la derivada en α=0 y de qué puntos se incluyen.

**A favor:** las propias comparaciones de modelos/ventanas cambian U de forma medible.  
**No demostrado:** cuál estimador representa mejor el límite de respuesta lineal ni que una ventana más estrecha o más amplia deba elegirse para lograr una meta concreta. Elegirla por el valor de U sería sesgo post hoc.

### H3. SCF, rama magnética o reproducibilidad entre ejecuciones consumen margen

Los outputs SCREENED reportan umbrales TDM `1e-5` y `1e-4 eV`. Se calculó un diagnóstico post hoc de deriva U entre estado terminal y último estado de alrededor de 8.224 meV/sitio. Ese valor no es un límite de error. No hay réplicas completas admitidas por el calibrador ni una envolvente independiente de SCF/reproducibilidad establecida.

**A favor:** el SCF es una fuente plausible y el diagnóstico de deriva no es nulo.  
**No demostrado:** que sea el factor principal o que una repetición reduzca el total bajo 0.02 eV. La comparación entre campañas actual no permite aislarlo.

### H4. Condicionamiento de matrices

La respuesta matricial afecta a U mediante inversiones. El informe adaptativo muestra rango completo 2/2 y números de condición de aproximadamente 1.745 para χ⁰ y 1.024 para χ.

**A favor:** es una transformación sensible en principio.  
**En contra de que sea el único problema obvio en este caso:** las matrices reportadas no aparecen mal condicionadas por esos indicadores.  
**Pendiente:** sensibilidad local de U respecto a cada entrada y de los intervalos de observación, incluidas dependencias/covarianzas. Buen condicionamiento no elimina redondeo ni valida el proyector.

### H5. La definición/extracción de ocupación y las versiones de análisis causaron diferencias históricas

El cambio v2→v3 sobre los mismos OUT altera U unos 31 meV/sitio. La fuente actual v3 usa el total `Occupations:` (`siesta_occupations_total`); el análisis histórico v2 usaba suma de traza de matriz. El plan rector histórico describía `trace_total` como ruta primaria y `Occupations:` como verificación pendiente; la implementación y reportes posteriores fijaron otra semántica.

**Estado:** la discrepancia histórica está identificada y explica que la comparación bruta entre campañas fuese engañosa. El significado exacto debe documentarse como contrato vigente y mantenerse uniforme al comparar. No hay que volver a atribuir ese salto a SCF.

### H6. El problema quizá no sea una garantía de ±0.02, sino definir una afirmación de producto útil

Puede ser que el obstáculo práctico se haya amplificado al pedir una garantía más fuerte de la que el dato experimental/protocolo necesita, o que se estén mezclando exactitud física y reproducibilidad numérica. También puede ocurrir lo contrario: que la aplicación realmente necesite ≤0.02 eV para distinguir decisiones posteriores. El umbral no se debe bajar ni subir para conseguir un “pase”; se debe justificar por el uso posterior o reportar como objetivo de ingeniería condicionado.

El usuario reconoce que la herramienta necesita entregar un U numérico útil, y no quedarse en una negativa permanente. El trabajo pendiente es proponer una afirmación comprobable útil y respaldada, no defender el `NOT_ESTABLISHED` como respuesta final a todo.

---

## 8. Qué se exploró y qué quedó descartado

### Ya explorado con evidencia existente

1. **Reanalizar resultados históricos sin volver a ejecutar SIESTA.** Se reconstruyeron los OUT adaptativos con la extracción v3 y se compararon con P5 bajo análisis equivalente.
2. **Separar diferencia de análisis de diferencia entre ejecuciones.** El cambio v2→v3 se observó sobre los mismos OUT y mueve U ~30.5–31.6 meV; por ello no es variación SCF.
3. **Examinar si la brecha P5–adaptive demuestra ruido SCF.** Su diferencia v3 de ~10.22 meV queda dentro de las cotas de redondeo propagadas; por sí sola no permite tal conclusión.
4. **Mirar la regla de parada adaptativa y sensibilidad.** La campaña terminó `STOP_STABLE`, pero no tenía tolerancia de sensibilidad física/numerica declarada; el estado no es una garantía de aceptación.
5. **Cuantificar la cota de impresión con más de un estimador.** La cota primaria cúbica adaptativa es 0.03436273105 eV; el lineal diagnóstico da 0.01353711826 eV. No se usó el lineal como sustituto por quedar debajo del objetivo.
6. **Comparar formato de otros códigos y sus umbrales.** Hay ejemplos oficiales donde U se imprime con 4 decimales, matrices con 6 o 15; las fuentes separan convergencia y formato.
7. **Investigar si resolverlo requiere modificar SIESTA.** El objetivo de portabilidad descarta modificar la fuente o exigir una recompilación privada como solución de producto.

### Descartado como ruta de producto

Se preparó durante la investigación una copia temporal de SIESTA 5.4.2 con formato `f20.12`, bajo `build/siesta542-f20.12-offline/`, para explorar si más resolución textual movería la cota. La fuente auditada original `third_party/siesta-5.4.2-source-audit/Src/dftu.F` quedó intacta. El staging y los logs de compilación son un experimento de investigación, no el backend de producto. **No se ejecutó el binario ni se lanzó una campaña con él**, y no se confirmó un receipt de compilación completo para admisión. Tras la aclaración del usuario de que la herramienta debe ser portable a instalaciones SIESTA soportadas, esta ruta se considera descartada como solución desplegable.

Esto no demuestra que la resolución impresa sea irrelevante; significa que la solución no puede exigir una modificación de SIESTA. Una futura mejora debe funcionar leyendo artefactos estándar de una instalación soportada, o demostrar con datos que el formato actual ya basta para la afirmación deseada.

### No debe presentarse como hecho

- “U está inválido porque la cota conservadora es mayor que ±0.02 eV.” No se deduce de la cota.
- “U está garantizado porque los números impresos tienen seis decimales.” Tampoco se deduce.
- “QE imprime cuatro decimales, por lo tanto ±0.02 eV es demasiado estricto.” El formato no demuestra exactitud.
- “La discrepancia entre campañas es ruido SCF de 20 meV.” Mezcla versiones/fuentes de ocupación.
- “`STOP_STABLE` equivale a tolerancia física satisfecha.” La tolerancia no estaba configurada.
- “Una campaña de réplicas es la única vía posible.” Puede ser necesaria para una afirmación de repetibilidad definida, pero antes conviene explotar de forma rigurosa los datos existentes y precisar la pregunta que el experimento debe resolver.

---

## 9. Rutas neutrales para avanzar

El objetivo es elegir pasos por su capacidad de distinguir hipótesis, su coste y su compatibilidad con SIESTA estándar. El orden sugerido no presupone la causa principal.

### Ruta A — Cerrar semántica y cuantización usando los archivos que ya existen

**Pregunta:** ¿qué dato exacto se está ajustando, con qué resolución y cómo se propaga esa resolución a U?

1. Congelar en el informe técnico el significado del evento y de `siesta_occupations_total` para referencia, BARE y SCREENED en la versión de salida soportada.
2. Para observaciones existentes, reconstruir los límites de ocupación por token impreso y derivar cómo cada perturbación impacta χ⁰, χ y U por sitio.
3. Separar un “peor caso determinista” de exploraciones de combinaciones plausibles. Si se plantea una interpretación probabilística del redondeo, declarar la distribución y dependencias antes de presentar probabilidades; una simulación Monte Carlo con entradas uniformes no es una garantía sin justificar uniformidad/independencia.
4. Identificar qué parte de la cota viene de observaciones concretas (referencia, BARE, SCREENED; sitio; α) y si una o pocas filas dominan. Esto puede revelar qué medición merece mejor resolución o qué ecuación amplifica el intervalo.

**Resultado esperado:** saber si el 0.03436 eV está distribuido por todo el protocolo, si lo domina una observación específica, o si el método de extremos genera una envolvente muy pesimista. No se modifica el criterio de aceptación.

### Ruta B — Distinguir error de estimación de sensibilidad al modelo

**Pregunta:** ¿el ajuste cúbico está estimando una curvatura/no linealidad real, o el intervalo ±0.02 depende de un modelo particular?

Usar los análisis ya existentes para documentar, por sitio, cada curva ocupación–α, residuos, dominio de α, número de puntos, grados de libertad y coeficiente lineal/cúbico. Revisar si la regla de seleccionar cúbico/lineal fue fijada con razón científica antes de mirar U y si los puntos adaptativos son comparables. Si hacen falta otros modelos, predefinirlos y tratarlos como sensibilidad, no escoger el menor U ni la menor cota.

**Resultado esperado:** determinar qué objeto reporta el algoritmo: derivada local bajo una base de α dada, derivada de un polinomio en la ventana declarada, o ajuste diagnóstico. Elegir una salida principal en función del estimando y una regla declarada, no del pase de ±0.02.

### Ruta C — Verificar resolución accesible sin modificar SIESTA

**Pregunta:** ¿hay una representación estándar más precisa ya generada por SIESTA o recuperable desde una salida nativa de ejecución soportada?

Revisar documentación y artefactos disponibles de SIESTA 5.4.2 para determinar si `Occupations:` y la matriz impresa son las únicas fuentes, o si un archivo estándar (por ejemplo, DM/HSX u otro producto nativo compatible) permite calcular la misma ocupación proyectada con mayor resolución a través de interfaces ya soportadas. No asumir que DM/HSX contiene los mismos proyectores/ocupaciones ni que el postproceso los puede reproducir sin cambiar el observable. Validar equivalencia en resultados existentes antes de adoptarlo.

**Resultado esperado:** una respuesta verificable “sí/no” sobre una ruta de precisión portable. Si no existe, el diseño debe tratar el texto estándar como resolución de dato y reportar su limitación, no modificar el ejecutable.

### Ruta D — Aislar SCF/reproducibilidad solo si es la incertidumbre decisiva

**Pregunta:** ¿una ejecución repetida bajo el mismo protocolo cambia U más que el margen disponible?

Los datos actuales no constituyen réplicas formales: adaptive y P5 difieren en campaña/malla, historia de análisis y no tienen hash de contenido del ejecutable; tampoco existe un protocolo preregistrado para la tolerancia de sensibilidad de la campaña original. Si, después de las rutas A–C, SCF sigue siendo el término dominante que impide una decisión, definir un protocolo mínimo prospectivo: qué se repite (un subconjunto informativo o una malla completa), qué se mantiene idéntico, cómo se identifica el ejecutable instalado sin modificarlo, cómo se comprueba la misma rama magnética, cómo se elimina doble conteo de redondeo y qué decisión cambiaría el resultado.

El contrato futuro actual propone una primaria más tres réplicas de malla completa (25 nodos cada una: 100 en total con una nueva primaria). Eso es una opción conservadora para una evaluación de reproducibilidad condicional, no una necesidad ya demostrada como primer siguiente paso. Requiere autorización de campaña y presupuesto; este informe no la autoriza.

**Resultado esperado:** elegir entre una prueba focalizada y el diseño completo, con criterios que permitan abandonar la ruta si el dato no cambiaría la conclusión.

### Ruta E — Justificar el nivel de tolerancia por el uso

**Pregunta:** ¿qué decisión posterior requiere que U sea estable a ±0.02 eV?

El umbral podría ser una exigencia legítima del producto o una meta conservadora creada como objetivo de ingeniería. Para distinguirlo, describir el uso downstream: ¿se usa U para un reporte cuantitativo, comparar sitios, seleccionar una configuración, alimentar un cálculo DFT+U, o tomar una decisión cuya respuesta cambia en escalas de 20 meV? Si el uso posterior no discrimina esa escala, la interfaz podría expresar un nivel de afirmación distinto (p. ej., cifras reportadas más una categoría de estabilidad) sin fingir una garantía. Si sí discrimina, el objetivo permanece relevante.

**Límite:** no cambiar ±0.02 retrospectivamente sólo porque el resultado actual falla. Cualquier política nueva debe justificarse desde el uso y aplicarse prospectivamente o etiquetarse con claridad como reanálisis exploratorio.

---

## 10. Propuesta de marco para una decisión útil

Se recomienda que la siguiente decisión no sea “¿pasa o falla la cota?” en abstracto, sino una de estas afirmaciones explícitas:

| Nivel de afirmación | Qué tendría que estar respaldado | Qué no implica |
|---|---|---|
| Resultado reproducible desde artefactos existentes | Mismo input/versiones de análisis generan mismos matrices, ajustes y U | No demuestra exactitud física ni estabilidad entre ejecuciones SIESTA distintas |
| Estable bajo modelo/ventana declarados | Rango de U al variar modelos/ventanas preregistrados está reportado y acotado condicionalmente | No demuestra error estadístico/verdadero menor al rango |
| Resolución de impresión suficiente | Cuantización de entradas estándar propagada y comparada con el objetivo | No garantiza SCF ni exactitud del proyector |
| Repetibilidad condicional de ejecución | Protocolo comparable, rama controlada y réplicas definidas producen envolvente observada | No garantiza resultados fuera de condiciones/máquina/protocolo muestreados |
| Aceptación física | Definición física del observable, validez del modelo/proyector y criterio físico independente debidamente justificado | No se obtiene solo con más decimales ni concordancia con literatura |

Una herramienta útil puede reportar varias capas en vez de colapsarlas en un único “sirve/no sirve”: U estimado; intervalo por cuantización de impresión; dispersión entre modelos/ventanas; diagnóstico SCF/reproducibilidad; advertencias de rango y condición; y nivel de afirmación que sí está respaldado. Esto permite entregar un resultado sin ocultar límites ni llamar “físicamente inválido” a un cálculo que simplemente no ha pasado una prueba de garantía que aún no se diseñó.

---

## 11. Restricciones que deben sobrevivir a cualquier ruta

1. **No editar ni recompilar SIESTA como solución de producto.** SIESTAFLOW debe permanecer portable a instalaciones soportadas.
2. **No alterar campañas, datos o informes históricos.** Reanálisis debe guardarse aparte y enlazarse a la fuente.
3. **No ajustar α, tolerancias SCF, proyectores, ventanas, grados del polinomio o criterios para alcanzar un U deseado o forzar un pase.** Los cambios metodológicos requieren justificación y congelamiento previo.
4. **No usar acuerdo con literatura como criterio de aceptación** ni escoger el resultado por acercarse a un valor esperado.
5. **No tratar decimales de salida como cifras significativas certificadas.** Formato y exactitud son distintos.
6. **No llamar error observado a una cota de peor caso**, ni llamar cota a un rango empírico entre dos ajustes.
7. **No llamar réplica formal a la comparación adaptive/P5 actual.** Es diagnóstico de archivos/historia existentes.
8. **No iniciar otra campaña sin autorización y puerta correspondiente.** La posibilidad de una calibración de hasta 100 nodos está documentada, no autorizada.
9. **Comunicar correctamente el estado del producto.** Las puertas operativas
   concluyeron, pero el cierre vigente es `PRODUCT_BLOCKED` por el objetivo
   científico del usuario. Distinguir ese bloqueo de un fallo de ejecución del
   CLI y de una demostración de que el valor numérico sea erróneo.

---

## 12. Paquete local que sirve como evidencia primaria

Revisar estas fuentes locales para recuperar definiciones exactas, detalles de salida y valores citados:

- [`docs/EJE_RECTOR_CIERRE_PRODUCTO.md`](EJE_RECTOR_CIERRE_PRODUCTO.md): plan vigente de cierre, estado del producto, rutas R1/R2 y límites de campaña.
- [`docs/P0_EXECUTION_20260928.md`](P0_EXECUTION_20260928.md): registro final de las puertas P0–P6, auditoría Sol, campaña P5, wheel y estado terminal `PRODUCT_BLOCKED` (el addendum inicial sustituye las secciones históricas inferiores).
- [`docs/ESTADO_REPOSITORIO_Y_PUBLICACION_20260929.md`](ESTADO_REPOSITORIO_Y_PUBLICACION_20260929.md): inventario previo, selección del commit local y estado de publicación en GitHub.
- [`docs/U_PRECISION_ACCEPTANCE_CONTRACT_20260928.md`](U_PRECISION_ACCEPTANCE_CONTRACT_20260928.md): objetivo ±0.02 eV, revisión de P5/adaptive, cotas y protocolo propuesto de réplicas.
- [`README.md`](../README.md): propósito, CLI, alcance SIESTA y estados.
- Reporte JSON/Markdown y manifest/receipts de la campaña NiO adaptativa mencionada arriba: valores v3, estado terminal, malla, rondas y procedencia.
- Reporte y receipts de P5: reconstrucción fija, ocupaciones y cotas de impresión.
- `src/siestaflow_hubbard/siesta_backend/occupation_precision.py`: interpretación de decimales impresos y semianchos.
- `src/siestaflow_hubbard/lr_analysis_v2.py`: política de análisis, tolerancias y contexto de respuesta.

Los paths absolutos de artefactos de campaña pueden depender de Windows/WSL y de las rutas del usuario; la evidencia debe resolverse desde los roots registrados en los receipts en vez de asumir una ruta portátil fija.

---

## 13. Preguntas concretas para el siguiente análisis

Un análisis externo útil debería contestar, con evidencias y no con preferencia previa:

1. ¿Cuál es el cuello de botella que más contribuye hoy a no poder respaldar una afirmación de ±0.02 eV: cuantización, modelo/ventana, SCF/reproducibilidad, definición del observable o mezcla de versiones?
2. ¿Qué parte está demostrada con los datos existentes y cuál es solo una hipótesis plausible?
3. ¿La suma conservadora `B_round + E_estimator + E_window + E_SCF/repro` es matemáticamente apropiada para la afirmación deseada? ¿Qué dependencias o dobles conteos hay? Si se propone otra regla, ¿qué cobertura/garantía tiene y bajo qué supuestos explícitos?
4. ¿Se puede calcular un diagnóstico más informativo de cuantización con los mismos resultados sin asignar una probabilidad injustificada al redondeo?
5. ¿Qué opción portable basada en salidas nativas de SIESTA podría aportar más resolución sin cambiar el observable ni recompilar el programa, y qué prueba de equivalencia la falsaría?
6. ¿Qué mínimo experimento prospectivo cambiaría la decisión, si uno es imprescindible? Comparar explícitamente el valor de una prueba focalizada con la campaña de réplicas completas de 100 nodos. No ejecutar nada.
7. ¿Qué afirmación de producto le permitiría al usuario obtener un U útil sin presentar como garantizada una exactitud física que no se ha probado?
8. ¿Qué evidencia refutaría cada explicación propuesta? Evitar una sola narrativa dominante si los datos no la distinguen.

---

## 14. Prompt neutral para entregar junto con este informe

> Lee el informe como expediente de evidencia, no como instrucción de defender el criterio existente. Analiza el cuello de botella de SIESTAFLOW para obtener un U numérico útil y respaldado, manteniendo la portabilidad a instalaciones estándar de SIESTA 5.4.2. Distingue explícitamente hechos observados, inferencias y preguntas sin resolver. Intenta falsificar las hipótesis H1–H6: no supongas que `f12.6` es la causa, que ±0.02 eV es una ley física, que la cota conservadora es el error real, ni que el análisis actual tiene razón por fallar la puerta. Tampoco reduzcas retrospectivamente el objetivo para obtener aprobación. Usa primero la evidencia existente y las fuentes enlazadas. Compara cuantización, estimador/ventana, SCF/reproducibilidad, condicionamiento y semántica del observable. Propón la siguiente acción más pequeña que discrimine hipótesis y explica qué resultado cambiaría la decisión. No modifiques archivos o parámetros, no ejecutes SIESTA, no inicies una campaña y no uses coincidencia con literatura como criterio de aceptación. Devuelve: (1) diagnóstico priorizado con confianza, (2) evidencia a favor y en contra, (3) acción siguiente mínima, (4) costo/nodos si aplica, claramente como propuesta no autorizada, y (5) la afirmación sobre U que sí sería legítimo comunicar después de esa acción.

Si sólo tienes acceso a GitHub, indica qué afirmaciones no puedes contrastar
porque el código, las pruebas y los documentos 0.1.2 descritos aquí están en
una rama local aún no enviada. No atribuyas al estado remoto la evidencia del
workspace sin haberla recibido o verificado directamente.

---

## 15. Fuentes externas consultadas

- Quantum ESPRESSO, código oficial QE 7.5: [`HP/src/hp_postproc.f90`](https://gitlab.com/QEF/q-e/-/raw/qe-7.5/HP/src/hp_postproc.f90).
- Quantum ESPRESSO, documentación oficial de [`INPUT_HP`](https://www.quantum-espresso.org/Doc/INPUT_HP.html).
- Quantum ESPRESSO Developers mailing list, nota sobre `hp_write_chi_full.f90`, formato `f19.15`/`f20.15` y escritura de matrices: [mensaje de julio de 2021](https://lists.quantum-espresso.org/pipermail/developers/2021-July/002428.html).
- VASP Wiki, tutorial de respuesta lineal para U: [`Calculate U for LSDA+U`](https://vasp.at/wiki/index.php/Calculate_U_for_LSDA%2BU).

Estas fuentes se citan para describir formato, umbrales y ejemplos metodológicos de otros códigos. **No** se usan para validar el valor de U de NiO ni para fijar el criterio de aceptación de SIESTAFLOW.
