# Stage U-B V5: comparador autocontenido A0 y repetibilidad

**Estado:** protocolo metodológico congelable antes de ejecución. La autorización de esta instrucción permite ejecutar una vez fijado el baseline V5. El protocolo no lee certificados U-A ni campañas anteriores.

## Contrato A0/B1/B2/B3

Cada material se ejecuta en cuatro campañas nuevas e independientes. `A0` es el comparador oficial, también calculado y certificado con el protocolo actual. `B1`, `B2` y `B3` son las tres réplicas preregistradas. Ningún output, DM, análisis, certificado o attempt se comparte entre runs.

El comparador U-A histórico, NiO V3 B1, canarios, locks antiguos y cualquier resultado previo quedan `HISTORICAL / FORENSIC`; no se leen, copian ni usan para inputs, análisis o `R`.

<!-- BEGIN GENERATED POLICY -->
Runs por material: **A0, B1, B2, B3**; comparador: **A0**; tres réplicas: **B1/B2/B3**.
Materiales: NiO, FeO, CoO. Orden preregistrado:

1. NiO A0
2. NiO B1
3. NiO B2
4. NiO B3
5. FeO A0
6. FeO B1
7. FeO B2
8. FeO B3
9. CoO A0
10. CoO B1
11. CoO B2
12. CoO B3

Campañas por run: UUID/raíz/referencia/DM/respuestas/análisis/certificación independientes (new_campaign_uuid, new_campaign_root, new_reference, new_parent_dm, new_response_attempts, new_matrix_analysis, new_u_certification).
Cada run contiene 25 nodos SIESTA. Total: 300 nodos para 12 campañas.

```text
delta_repeat[s,j] = abs(U_Bj[s] - U_A0[s])
R[s] = max(delta_repeat[s,B1], delta_repeat[s,B2], delta_repeat[s,B3])
envelope[s] = [U_A0[s] - R[s], U_A0[s] + R[s]]
```

Gates por sitio, sin cambios: semiancho certificado ≤ 0.020 eV; sensibilidad de estimador ≤ 0.020 eV; sensibilidad de ventana ≤ 0.020 eV; R ≤ 0.020 eV.
DAG exigido en cada run: `REFERENCE → RESPONSE_GRID → alpha-diagnostic-gate → MATRIX_ANALYSIS → U_CERTIFICATION`.
Ejecución: LOCAL_WSL, 4 rangos MPI, máximo 1 SIESTA simultánea.

No hay ninguna dependencia operativa de U-A, campaigns, locks, canarios ni outputs históricos.
<!-- END GENERATED POLICY -->

## Entradas y controles científicos

Cada run toma sus entradas de la configuración científica vigente y autoritativa del proyecto bajo el baseline V5: estructura, especies, pseudopotenciales, base, funcional, magnetismo, malla k, mesh cutoff, smearing, proyectores y sitios correlacionados, perturbaciones alpha, estimador/ventana y política SCF. Los cuatro runs de un mismo material comparten exactamente esa configuración. Cada uno crea su propia referencia, DM padre, respuestas, análisis de matriz y certificado.

No completar campos científicos por inferencia a partir del nombre del material. Si falta una entrada esencial vigente (por ejemplo, el FDF de referencia, el pseudopotencial requerido, los proyectores o la política de perturbaciones), ese material queda detenido por falta real de input. No se buscan ni solicitan artefactos históricos.

La ejecución usa SIESTA 5.4.2, `LOCAL_WSL`, cuatro rangos MPI y una sola invocación SIESTA simultánea. No se usa HPC. La configuración de campaña y la versión del runtime se fijan una vez antes del primer nodo. No se cambia código, protocolo, thresholds ni inputs después de iniciar NiO A0.

## DAG y validez

Cada run debe completar el DAG:

```text
REFERENCE
→ RESPONSE GRID
→ alpha-diagnostic-gate
→ MATRIX_ANALYSIS
→ U_CERTIFICATION
```

Una respuesta sólo es válida con reinicio controlado desde el DM padre del nodo, `DM.UseSaveDM`, label corto, comprobación del intento y evidencia de terminación normal; fallback no demuestra reinicio válido. No se declara `SCREENED` sólo por terminar SCF. Cada `U_CERTIFICATION` debe ser `CERTIFIED` y registrar U por sitio, intervalos, semianchos, sensibilidad del estimador y de ventana y estado.

Si falta `U_CERTIFICATION` en cualquier run, se detiene todo Stage U-B y se diagnostica como fallo sistémico. Una evidencia científica, de runtime o reinicio inválida detiene el run/material afectado. Un resultado válido que exceda un umbral numérico no detiene la secuencia.

## Gating y decisión

Se aplican sin cambios los tres gates independientes de certificado y sensibilidad definidos en `precision_policy.json`, más `R <= 0.020 eV/site`. El semiancho es `(upper-lower)/2`; estimator y window sensitivity se evalúan por separado. El envelope de repetibilidad se calcula sólo al completar y certificar `A0+B1+B2+B3`.

- `PASS`: los cuatro certificados son válidos y todos los gates, incluido `R`, pasan en cada sitio.
- `REVIEW`: evidencia completa y válida, pero uno o más gates numéricos no pasan.
- `FAIL`: evidencia científica, runtime o reinicio inválida.
- `NOT_ESTABLISHED`: set incompleto o falta certificado/medición.

No se ejecuta B4 para reemplazar un resultado válido incómodo. Las réplicas B1/B2/B3 quedan fijadas antes de ejecutar.

## Orden de ejecución

```text
NiO A0 → B1 → B2 → B3
FeO A0 → B1 → B2 → B3
CoO A0 → B1 → B2 → B3
```

Cada run tiene UUID y raíz nuevos. Un problema sistémico detiene Stage U-B; una clasificación `REVIEW` por cifras válidas no interrumpe runs pendientes. No se ejecuta repetibilidad parcial.

## Registro y reporte

Por run se registra solamente material, etiqueta A0/B1/B2/B3, UUID, fecha/hora, carpeta de campaña, baseline SHA, versión SIESTA, FDF/configuración de campaña, U por sitio, certificado, status, invocaciones SIESTA, tiempo de pared, CPU y reintentos. Hashes que el runtime ya requiera pueden permanecer internos; no se añaden capas de commitments ni provenance.

Por material, el informe contiene filas A0/B1/B2/B3 con `U0`, `U1`, `cert h0`, `cert h1`, `estimator max`, `window max` y status; luego delta de B1/B2/B3 frente a A0, `R` por sitio, envelope y veredicto. Se conservan resultados válidos fuera de gate sin ampliar el número de réplicas.

Stage U-B termina tras reportar NiO, FeO y CoO. No se ejecutan observables, bandas, DOS/PDOS, producción DFT+U, validación experimental ni HPC.
