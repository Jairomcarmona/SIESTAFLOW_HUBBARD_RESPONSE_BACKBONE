# Stage U-B: protocolo prospectivo de repetibilidad y precisión

**Estado:** contrato de diseño previo a campaña. **No autoriza cálculos.**
No modifica la ciencia ni los artefactos U-A. Las salidas U-A, incluidos los
certificados superseding de MnO y CoO, permanecen congeladas.

## Puerta de software

La suite automatizada `tests/` pasó en WSL nativo Ubuntu, filesystem ext4:
**784 passed, 20 skipped, 0 failed**. Se excluyó
`examples/tmo_campaigns/test_order.py` porque su
importación inicia SIESTA, expresamente prohibido para esta tarea. La suite
`tests/` no inició SIESTA.

## Política y alcance

`docs/U_PRECISION_ACCEPTANCE_CONTRACT_20260928.md` ya declara, para campañas
futuras, `u_precision_tolerance_eV = 0.020 eV/site`. Para fijar U-B ahora,
este protocolo congela también `sensitivity_tolerance_eV = 0.020 eV/site`.
Ambos son gates independientes. No se aplican retrospectivamente: los cuatro
análisis U-A tienen ambos campos en `null`, así que U-A sirve de comparador
histórico y no de evidencia de que ya pasó un gate de precisión preregistrado.

U-B sólo evalúa cuánto cambia el U certificado al repetir el protocolo
condicionado. No evalúa exactitud física, acuerdo experimental, confianza
estadística ni incertidumbre verdadera. El intervalo determinista de cada
certificado, la repetibilidad empírica y las sensibilidades de estimador y
ventana se publican separadamente; no se suman.

## Métrica y puertas numéricas

Para cada sitio `s` y cada una de tres réplicas completas independientes `j`:

```text
delta_repeat[s,j] = abs(U_B[s,j] - U_A[s])
R[s] = max_j(delta_repeat[s,j])
repeatability_envelope[s] = [U_A[s] - R[s], U_A[s] + R[s]]
```

`R` es el máximo observado frente a U-A en las tres réplicas admitidas. Es un
envolvente empírico condicionado a este protocolo, no un intervalo de
confianza ni un bound de error verdadero. Se conservan sin colapsar el
intervalo determinista `I_A[s]` y los tres `I_B[s,j]`.

Los gates de U-B son independientes por sitio: (1) `R[s] <= 0.020 eV`,
(2) semiancho determinista de cada certificado admitido `<= 0.020 eV`, y
(3) sensibilidad de estimador y de ventana, evaluadas por separado, cada una
`<= 0.020 eV`. El certificado de cada B debe ser `CERTIFIED` y pasar sus
controles de regularidad. El umbral para sensibilidad se congela aquí porque
el contrato existente requiere que `sensitivity_tolerance_eV` coincida con
el objetivo de precisión para hacer elegible el gate; no se convierte una
diferencia de método en cota de error ni se agrega a `R` o al intervalo.

Los siguientes estados son terminales para una evaluación:

- **PASS:** tres réplicas completas admitidas; todos los certificados pasan;
  todos los sitios cumplen por separado los gates anteriores y conservan el
  estado magnético/SCF preregistrado.
- **REVIEW:** datos válidos y completos, pero algún gate numérico o diagnóstico
  preregistrado excede el umbral correspondiente. Se informa el resultado tal como salió; no se
  reajusta estimador, malla o política para obtener PASS.
- **FAIL:** una réplica declarada válida viola la identidad científica,
  convergencia o procedencia exigidas. Se invalida esa réplica y se detiene su
  uso; no se calcula un resumen con evidencia incompatible.
- **NOT_ESTABLISHED:** faltan réplicas admitidas, certificados, recibos o
  mediciones para decidir. No equivale a PASS ni a una conclusión física.

La sensibilidad de condicionamiento de FeO se informa como diagnóstico de
regularidad; no se vuelve a penalizar mediante otro término si esa misma
condición ya está certificada. La antigua suma automática
`B_round + E_estimator + E_window + E_SCF/repro` está supersedida por la
revisión exacta del contrato de precisión.

## Línea base y elegibilidad

El presupuesto empírico de repetibilidad proviene de la política de Stage U-B
y permanece separado del margen certificado.

La causa fue un error de derivación, no sólo de presentación: el resumen
forense, el generador de certificados y el gate de release llamaban semiancho a
`max(nominal-lower, upper-nominal)`. Ese valor mide la mayor distancia desde
el nominal, no el radio del intervalo. Ahora el semiancho se obtiene de los
dos extremos; las distancias desde el nominal se informan por separado.

<!-- BEGIN GENERATED BASELINE: render_stage_u_b_protocol.py -->
The following tables are generated from the frozen certificate artifacts, source analyses, and `precision_policy.json`.
The historical field reproduces the former nominal-to-endpoint deviation calculation; derived half-width is exactly `(upper-lower)/2`.

| Material | Certificate half-width | Estimator sensitivity | Candidate precision policy | Repeatability budget | Stage U-B status |
|---|---:|---:|---|---|---|
| NiO | 0.006414465 eV | 0.001110279 eV/site | U-B: ±0.020 eV/site; sensitivity ±0.020 eV/site; U-A fields null | R≤0.020; cert margins 0.013585535/0.013585582 eV | `READY_FOR_STAGE_UB` |
| MnO | 0.048962558 eV | 0.030738482 eV/site | U-B: ±0.020 eV/site; sensitivity ±0.020 eV/site; U-A fields null | R≤0.020; cert margins -0.028962558/-0.028953811 eV | `PROTOCOL_REVIEW_REQUIRED` |
| FeO | 0.005789373 eV | 0.000682422 eV/site | U-B: ±0.020 eV/site; sensitivity ±0.020 eV/site; U-A fields null | R≤0.020; cert margins 0.014210627/0.014210642 eV | `READY_FOR_STAGE_UB` |
| CoO | 0.016158253 eV | 0.000496730 eV/site | U-B: ±0.020 eV/site; sensitivity ±0.020 eV/site; U-A fields null | R≤0.020; cert margins 0.003841836/0.003841747 eV | `READY_FOR_STAGE_UB` |

Nominal values, exact interval endpoints, endpoint-derived half-widths, interval centers, and separate nominal-to-endpoint distances (sites 0/1; eV):

| Material | Nominal U-A (site 0 / 1) | Interval site 0 | Center 0 | Half-width 0 | Nominal lower / upper distance 0 | Interval site 1 | Center 1 | Half-width 1 | Nominal lower / upper distance 1 |
|---|---|---:|---:|---:|---|---|---:|---:|---|
| NiO | 6.861874364 / 6.861874364 | [6.857300307, 6.870129237] | 6.863714772 | 0.006414465 | 0.004574057 / 0.008254873 | [6.857407641, 6.870236477] | 6.863822059 | 0.006414418 | 0.004466723 / 0.008362113 |
| MnO | 11.117477005 / 11.115065146 | [11.068637186, 11.166562302] | 11.117599744 | 0.048962558 | 0.048839819 / 0.049085296 | [11.066234042, 11.164141664] | 11.115187853 | 0.048953811 | 0.048831104 / 0.049076518 |
| FeO | 5.638281766 / 5.638315884 | [5.632494835, 5.644073581] | 5.638284208 | 0.005789373 | 0.005786931 / 0.005791814 | [5.632528967, 5.644107684] | 5.638318326 | 0.005789358 | 0.005786917 / 0.005791800 |
| CoO | 5.818030436 / 5.817951498 | [5.801893354, 5.834209681] | 5.818051517 | 0.016158164 | 0.016137082 / 0.016179245 | [5.801814326, 5.834130832] | 5.817972579 | 0.016158253 | 0.016137171 / 0.016179334 |

Per-site estimator and window sensitivities (eV/site):

| Material | Estimator site 0 / site 1 | Window site 0 / site 1 |
|---|---|---|
| NiO | 0.001110279 / 0.001110279 | 0.000685526 / 0.000685526 |
| MnO | 0.021176715 / 0.030738482 | 0.013125851 / 0.020275758 |
| FeO | 0.000640554 / 0.000682422 | 0.000435924 / 0.000454471 |
| CoO | 0.000430237 / 0.000496730 | 0.000100555 / 0.000060792 |

Before/after half-width derivation (eV):

| Material | Old reported half-width | Derived half-width | Old margin | Derived margin | Changed? |
|---|---:|---:|---:|---:|---|
| NiO | 0.008362113182 | 0.006414464918 | 0.011637886818 | 0.013585535082 | yes |
| MnO | 0.049085296250 | 0.048962557654 | -0.029085296250 | -0.028962557654 | yes |
| FeO | 0.005791814297 | 0.005789372573 | 0.014208185703 | 0.014210627427 | yes |
| CoO | 0.016179334156 | 0.016158252729 | 0.003820665844 | 0.003841747271 | yes |
<!-- END GENERATED BASELINE -->

### Material notes

- **NiO:** the exact endpoint half-widths and both adaptive diagnostics are
  generated above from the committed certificate and source analysis. The
  historical U-A policy fields remain null, so U-A is only the fixed comparator.
- **FeO:** the exact endpoint half-widths and sensitivities are generated above. The certified
  regularity condition remains established. Conditioning is reported once as
  a diagnostic, without double counting it against precision.
- **CoO:** use only the corrected superseding certificate. The forensic summary
  records model, window, and last-round diagnostics separately; the generated
  table above derives interval and margin values from the superseding artifact.
- **MnO:** its interval-derived half-widths and estimator/window sensitivities
  are generated from its superseding certificate and committed analysis.
  The status and values above are authoritative for this protocol; retain
  `PROTOCOL_REVIEW_REQUIRED` while a gate exceeds policy. Do not change its
  estimator here.

## Qué cuenta como réplica válida

Cada réplica conserva sin cambios la estructura, pseudopotenciales y sus
hashes, base/basis, proyectores y su definición, funcional, alpha grid,
estimador y selección de ventana, observable de ocupación, versión y hash del
ejecutable/backend SIESTA, política SCF, contrato de estado magnético y
recursos MPI. Se registran las versiones y hashes de software y la política
antes del primer nodo.

Una réplica requiere UUID de campaña, root, referencia y attempts nuevos; una
referencia nueva y sus DM/output nuevos; y los 24 nodos BARE/SCREENED nuevos
para dos sitios y seis valores alpha de la malla U-A activa. No se reutiliza
una celda ni un attempt U-A. La evidencia de campaña y nodo liga node ID,
digest/attempt, FDF, OUT, DM, análisis y dataset por hash; se relee el
desplazamiento del FDF y se reextraen las ocupaciones desde OUT. El validador
`ValidatedResponseGridCalibration` exige al menos tres réplicas, UUID/root y
attempts distintos, cobertura completa de la misma malla/sitios/modos y una
referencia validada. La igualdad byte a byte de DM/OUT no invalida una
ejecución independiente si los recibos prueban attempts distintos.

Para su esquema, el lock de calibración fijará `safety_factor = 1.0` (máximo
empírico observado; sin interpretación de confianza) y
`deterministic_floor_e = 5e-7` electrones, la mitad de la última cifra
impresa en `f12.6`. Esa calibración valida la malla y su procedencia; no se
suma como una magnitud de incertidumbre U. La métrica de U sigue siendo el
`R` definido arriba.

## Coste local estimado

U-A guardó 33/41/25/41 archivos `.times` para NiO/MnO/FeO/CoO. Sus medianas
por nodo fueron 17.0/8.1/18.2/17.2 s; percentiles 90 empíricos
26.5/11.9/23.9/23.9 s. El perfil local declara cuatro procesos MPI y una
ejecución simultánea máxima. Estimo una réplica como 25 nodos secuenciales:
una referencia y 24 respuestas. Tiempo de pared = 25 por la mediana o p90;
CPU-hours = tiempo de pared por cuatro rangos. Esto excluye preparación,
reintentos e instalación, y no es una garantía de runtime.

| Material | Nodos por réplica válida | Wall por réplica (mediana–p90) | CPU-hours por réplica (mediana–p90) | Tres réplicas: wall (mediana–p90) | Tres réplicas: CPU-hours (mediana–p90) |
|---|---:|---:|---:|---:|---:|
| NiO | 25 | 7.1–11.0 min | 0.47–0.74 | 21.3–33.1 min | 1.42–2.21 |
| MnO | 25 | 3.4–5.0 min | 0.23–0.33 | no recomendar | no recomendar |
| FeO | 25 | 7.6–10.0 min | 0.51–0.66 | 22.8–29.9 min | 1.52–1.99 |
| CoO | 25 | 7.2–10.0 min | 0.48–0.66 | 21.5–29.9 min | 1.43–1.99 |

No hay reducción de malla que satisfaga el contrato: omitir la referencia o
alguna combinación de sitio/alpha/modo viola la cobertura completa requerida.
El presupuesto para los tres materiales elegibles sería **225 nodos**. El
contrato existente separa una primaria futura preregistrada: si se buscara una
declaración formal que la requiera en lugar de usar U-A como comparador, se
añadirían 25 nodos por material (100 por material contando las tres réplicas).
Esta tarea no pide recalcular U-A ni ejecutar esa primaria.

## Cálculos futuros exactos (no ejecutados)

Sólo después de autorizar la campaña y congelar/validar los locks:

1. Para NiO, ejecutar tres campañas independientes; cada una: 1 referencia
   nueva + 2 sitios × 6 alpha activos × 2 modos = 25 nodos.
2. Para FeO, el mismo conjunto completo de 25 nodos por cada una de tres
   campañas UUID/root/attempt nuevos.
3. Para CoO, el mismo conjunto completo de 25 nodos por cada una de tres
   campañas UUID/root/attempt nuevos.
4. Validar cada certificado B, construir `delta_repeat` y `R` por sitio,
   informar `I_A` e `I_B` separadamente y aplicar una sola vez los gates
   congelados. No recalcular ni reescribir U-A.
5. Mantener MnO fuera de esta lista mientras siga vigente el gate de precisión.

U-B no valida experimentalmente U. Sólo tras completar U-B se decidirá por
separado si algún material pasa a un benchmark de observables
`DFT(U=0) vs DFT+U_LR`; ese experimento queda fuera del diseño de este
protocolo.

## Decisiones científicas pendientes

No falta elegir una tolerancia: los umbrales están congelados en
`precision_policy.json` y se imprimen aquí desde ese artifact.
NiO, FeO y CoO son candidatos; MnO queda excluido bajo estos gates. No se
requiere decisión científica para cerrar el diseño. La condición operativa
futura es autorización expresa de campaña; este documento no la implica.
