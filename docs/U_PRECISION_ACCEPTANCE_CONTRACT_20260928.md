# Contrato de precisión numérica de U

**Tolerancia predeclarada para una campaña futura:** ±0.02 eV por sitio en
`U_scalar_charge`. La campaña deberá congelar explícitamente
`analysis_policy.u_precision_tolerance_eV: 0.02` antes de generar sus
respuestas. Este umbral define un objetivo de precisión numérica; no es una
tolerancia física, una aceptación de DFT+U ni una razón para alterar α,
proyectores, ventanas, criterios SCF o el estimador después de observar U.

> **Estado de portabilidad (2026-09-29):** los cálculos condicionales de este
> contrato describen qué ocurriría bajo su fórmula de aceptación vigente; no
> autorizan ni establecen como ruta de producto una modificación de SIESTA.
> La opción experimental `f20.12` requiere cambiar/recompilar el ejecutable y
> por ello no satisface el requisito de usar instalaciones estándar
> soportadas. El experimento local de staging no produjo un build receipt
> admitido y su binario no se ejecutó en una campaña. La precisión extendida
> queda fuera de la ruta portable; este límite no demuestra que el error real
> de U supere ±0.02 eV. Para el estado y las rutas actuales, véase
> [`INFORME_CONTEXTO_CUELLO_BOTELLA_U_20260929.md`](INFORME_CONTEXTO_CUELLO_BOTELLA_U_20260929.md).

## Evidencias que deben permanecer separadas

- **Redondeo determinista de impresión:** calcularlo desde los tokens de
  ocupación realmente emitidos y propagar sus intervalos por el ajuste y la
  inversión. La revisión de la fórmula vigente de `lr_analysis_v2.py` separa
  `B_round` de la cuantización de las réplicas, y suma además los envolventes
  de estimador/ventana y el término condicional de repetibilidad. Para P5,
  `B_round = 0.01183306193 eV`; el término cuantitativo de impresión de las
  réplicas con `f12.6` es `B_replica,quant = 0.0118330619317529 eV`. Aun
  suponiendo dispersión empírica réplica-primaria igual a cero, la suma de
  esos términos y los envolventes por sitio da, incluso dejando fuera
  cualquier floor positivo y fijando la dispersión observada en cero, como
  mínimo
  `B_total,NiLR0 = 0.027510528418052065 eV` y
  `B_total,NiLR1 = 0.02792425893343447 eV`. Ambos exceden `0.02 eV`; la
  cuantización del formato stock hace imposible satisfacer este umbral con la
  fórmula actual incluso en ese caso de dispersión cero. La implementación
  aplica `max(deterministic_floor_e, observed_spread)` antes de sumar la
  cuantización de réplicas; por ello, un floor o dispersión positivos sólo
  pueden aumentar esos mínimos. Por tanto, el P5 stock no es elegible
  para la puerta de ±0.02 eV bajo este contrato; esto no invalida su valor
  numérico como diagnóstico y no es un juicio de aceptación física.
- **Precisión extendida `f20.12` (experimento no portable):** el parche aislado
  `reserved_external_patches/siesta542-occupations-f20.12.patch` cambia el
  formato de `f12.6` a `f20.12` y reduce por un factor de 10⁶ el semipaso
  decimal bajo la misma propagación. Bajo la fórmula `B_total` fijada aquí,
  ese cambio reduce el término de cuantización de réplicas; no garantiza por sí
  solo que el total pase. La afirmación de que `f20.12` es “necesario” sólo es
  condicional a mantener esa fórmula y esa puerta; no demuestra una necesidad
  física ni que la cota conservadora sea el error real. Además, exige modificar
  y recompilar SIESTA, así que **no es una ruta aceptable para el producto
  portable**. El staging local no produjo un build receipt admitido y el
  binario no se ejecutó en una campaña. El runner puede validar un receipt que
  enlace SHA-256 del parche y ejecutable, junto con al menos 12 decimales en
  cada salida, pero esa capacidad del runner no convierte el parche en una
  ruta aprobada. No reinterpretar salidas históricas `f12.6` como si tuvieran
  precisión extendida.
- **Modelo y ventana:** informar la sensibilidad entre estimadores y ventanas
  por separado. Es un diagnóstico de dependencia del análisis, no una cota
  matemática de error.
- **SCF y repetibilidad:** validar convergencia y estado electrónico. Una
  envolvente empírica de réplicas de la malla completa sólo describe
  reproducibilidad condicionada al protocolo observado; no es una cota de
  verdad ni una confianza probabilística. No transferir calibraciones de α=0
  a α≠0. La calibración de malla usa dataset schema v4 y result schema v2.
  Cada recibo identifica explícitamente el root de su campaña fuente; el
  dataset, análisis, `node-evidence.json`, FDF, OUT y DM quedan ligados por
  hashes. La referencia también enlaza su node ID/digest y attempt ID; cada
  celda enlaza node ID/digest, attempt ID y coordenada. El validador compara
  perturbación/sitio, relee el desplazamiento `DFTU.Proj` desde el FDF y
  reextrae las ocupaciones desde los OUT de respuesta y referencia. Los paths
  se confinan al root de la campaña fuente y al attempt de ejecución. Las
  campañas necesitan UUID, root y attempts distintos; hashes DM/OUT iguales
  son admisibles si los receipts prueban attempts independientes. Reutilizar
  un attempt o un recibo de ejecución no pasa. Datasets sin ese recibo no
  producen una calibración completa.

## Reanálisis retrospectivo de P5

La CLI `tools/package_response_grid_replica.py --mode reanalyze-primary`
permite evaluar el P5 fixed-grid existente con una tolerancia indicada
explícitamente con `--target-tolerance-eV`, junto con un lock y resultado de
calibración validados. La primaria se vuelve a comprobar desde sus artefactos
hash-verificados y se escribe un análisis/informe en un sidecar nuevo, fuera
de la carpeta de campaña. P5 no se cuenta como réplica ni se modifican sus
artefactos históricos. La CLI considera la tolerancia preregistrada sólo si
los dos campos (`sensitivity_tolerance_eV` y `u_precision_tolerance_eV`) de
la política guardada en la campaña ya coinciden con el valor explícito.

Si esos campos no coinciden, se conservan los diagnósticos, pero el estado de
la puerta se fuerza a `RETROSPECTIVE_THRESHOLD_NOT_PREREGISTERED` y
`precision_gate_eligible` es `false`, aunque el cálculo retrospectivo quede
dentro del umbral. Si coinciden, la evaluación puede ser elegible para la
puerta de reproducibilidad numérica bajo el protocolo, nunca para aceptación
física. La coincidencia de campos no altera el análisis ni los artefactos
históricos; sólo determina si el sidecar puede ser elegible para la puerta.

Ese umbral es **declarado por el usuario para evaluación retrospectiva**. No
fue preregistrado para P5 y el reanálisis no puede cambiar ese hecho. El
resultado condicional, si existiera, sólo describiría reproducibilidad
numérica bajo el protocolo empírico validado; no sería aceptación física ni
una garantía de error total. Esta descripción no anuncia un pase de precisión.

La evidencia SCF NiO disponible incluye 12 salidas SCREENED con `TDM=1e-5` y
`TH=1e-4 eV`. La diferencia post hoc entre los registros terminales
convergido y final se observó como un drift diagnóstico de 8.224 meV/sitio.
Es sensibilidad terminal observada, no una cota ni una calibración de
repetibilidad independiente. Sigue faltando evidencia de réplicas
independientes de la malla completa para evaluar el componente SCF/repro bajo
el contrato.

### Comparación retrospectiva P5–adaptive-v2

La campaña P5 fixed-grid y la campaña adaptativa NiO v2 tienen UUID, roots y
attempts de ejecución distintos, pero comparten el mismo SHA del DM de
referencia. Ambas usaron la malla `[-0.06, -0.04, -0.02, 0.02, 0.04,
0.06] eV`, el funcional PBE y la política `polynomial`, grado 3, matriz raw y
`minimum_residual_dof=1`. La igualdad del DM es compatible con ejecuciones
deterministas; la independencia operativa se apoya en los receipts de campaña
y de nodo con UUID/root/attempts distintos, no en exigir bytes distintos del
estado físico.

Los receipts registran estos hashes idénticos en ambas campañas:

| Entrada común | SHA-256 |
|---|---|
| Reference FDF | `b4fb34e642d862be6949a5b2033a60b5c9fcae56119879583bb3eaf237620ee7` |
| Execution profile | `fbc9ff5ae47a6791d0e1ff962b6070f8690f1ffef475bafd8784a7388d755ae1` |
| `software/siesta_version.txt` | `bb5a9b03dfaec9953401a7ef8db045149461047c44f15f9c5bf7758900b5f3ee` |
| `backend_compatibility.json` | `5189620dfa1e8b6090cbdbb9c36c412835d16feb5c50bbc82b16c139d3bcff2e` |
| Ni pseudopotential | `192eb05ffb64671715e570e2ca9a99a551cf15544984592082d43004f8554e06` |
| O pseudopotential | `224ded5c59176d9bcb76d19b7a4a68a48d5dffabf8b262f64d5760250e87c35e` |

Ambas declaran SIESTA 5.4.2, el mismo path de ejecutable y el mismo texto de
versión. No se archivó un hash del binario ejecutable; por eso esta igualdad
de entradas y metadatos no constituye calibración formal del ejecutable ni
cambia la clasificación diagnóstica de la ronda adaptativa.

La ronda adaptativa 00 sigue siendo **diagnóstico**, no una réplica admitida
por el calibrador: su campaña es adaptativa y su análisis histórico usa schema
v2, mientras el packager de réplica exige campaña fixed-grid y análisis v3.
No se contó ni se usó para construir una envolvente de repetibilidad.

Los valores reconstruidos por sitio fueron:

| Fuente y método | NiLR0 (eV) | NiLR1 (eV) |
|---|---:|---:|
| Adaptive round-00, análisis histórico v2 | 6.884591569153939 | 6.885789004356711 |
| Adaptive round-00, reextracción de los mismos OUT con v3 | 6.854048120360063 | 6.854167895520947 |
| P5, análisis v3 | 6.864267700049239 | 6.864387475210124 |

Al releer los mismos OUT adaptativos con el selector de eventos y parser de
`Occupations:` vigentes y el análisis v3, la diferencia P5–adaptive queda en
10.219579689 meV/sitio para ambos sitios, frente al salto histórico de
20.324/21.402 meV. Las cotas deterministas de impresión propagadas por v3 son
11.833061932 meV para P5 y 11.834222998 meV para adaptive. El residual
10.220 meV queda dentro de esas cotas: esta comparación no identifica por sí
sola un componente SCF/repetibilidad independiente.

El cambio entre adaptive v2 y v3 sobre los mismos archivos OUT mueve U en
30.543448794 meV (NiLR0) y 31.621108836 meV (NiLR1). Es una diferencia de
fuente/interpretación del observable (`matrix_trace` v2 frente a
`siesta_occupations_total` v3), no ruido SCF. Por tanto, el salto original no
debe atribuirse a variación entre campañas sin separar primero este cambio de
extracción. Ninguna fila de esta comparación constituye calibración,
aceptación de tolerancia ni aceptación física.

La comparación se puede reproducir sin escribir en las campañas: leer los
manifiestos, análisis y receipts `node-evidence.json` existentes; verificar
los hashes de manifest, análisis, node evidence, FDF, OUT y DM, además de
UUID, root, node ID, evidence digest y attempt de cada fuente; comprobar la
malla y el contexto de análisis; reextraer ocupaciones desde los OUT con
`Siesta542PotentialShiftHamiltonianProfile.select_response(...).response_event`
para BARE y `select_converged_screened_event(...)` para SCREENED; obtener
valores e intervalos con `read_printed_occupation_precision(...)`; y pasar las
observaciones reconstruidas a `analyze_verified_lr` con la política v3
declarada. Mantener los archivos originales intactos y guardar cualquier
análisis futuro sólo en un sidecar. Los nombres de ruta se toman de los
receipts relativos a cada root; no dependen de rutas absolutas de una máquina.

El protocolo fijado requiere tres réplicas completas adicionales. Con 25
nodos por malla, su presupuesto es **75 nodos**. Una campaña primaria nueva,
con tolerancias congeladas antes de ejecutarse, requiere otros 25: **100 nodos
en total** para una ruta prospectiva con primary preregistrada y tres
réplicas. P5 puede reanalizarse como primaria exploratoria y evita repetir
esos 25 nodos para esa evaluación retrospectiva, pero no sustituye la primaria
preregistrada de una futura ruta de aceptación numérica. No se cuenta P5 como
réplica, ni se reduce la cobertura o relaja la independencia.

Para campañas y réplicas futuras, la tolerancia, la política de análisis y el
protocolo de SCF/repetibilidad deben quedar congelados antes de ejecutar los
cálculos. La evaluación retrospectiva de P5 no sustituye esa preregistración.

Para evaluar el objetivo total, la campaña futura deberá declarar antes de
calcular una envolvente de modelo/ventana por sitio y un protocolo de
repetibilidad SCF. La composición conservadora propuesta es

```text
B_total,s = B_round,s + E_estimator,s + E_window,s + E_SCF/repro,s
```

El pase numérico requiere que los cuatro términos estén disponibles,
`analysis_policy.sensitivity_tolerance_eV` esté predeclarado, y
`B_total,s <= 0.02 eV` para **cada** sitio. No basta con que cada componente
individual sea menor que 0.02 eV. Si una envolvente de modelo/ventana o de
SCF/repetibilidad es empírica, el resultado debe etiquetarse como
**condicional al protocolo observado**, nunca como garantía matemática o
probabilística. Si alguno de esos términos sólo es un diagnóstico sin una
envolvente predeclarada defendible, el total queda sin establecer; no se debe
sumar ese diagnóstico como si fuera una cota.

El analizador compone esos términos por sitio y sólo puede emitir
`CONDITIONALLY_REPRODUCIBLE_WITHIN_TOTAL_TOLERANCE` cuando todos están
disponibles, el umbral de sensibilidad está predeclarado, existe evidencia de
estado/SCF y el total está bajo el criterio. La parte SCF/repetibilidad se
propaga excluyendo el redondeo primario, para no contarlo dos veces; incluye
la cuantización de las réplicas y la dispersión primaria-réplica. Aun cuando
el estado condicional pase, `total_numerical_U_interval` permanece
`NOT_ESTABLISHED`: las envolventes empíricas no son cotas de error verdadero.
El estado tampoco implica aceptación física.

El reanálisis sidecar puede reevaluar retrospectivamente el P5 histórico, pero
no modifica sus datos, manifiestos, JSON ni informes originales. Tampoco
establece aceptación física de ningún valor de U. La suma parcial revisada de
P5 se informa aquí para fijar el margen pendiente; no modifica sus artefactos.
