# Luna E — auditoría adversarial de trazas BARE

## Alcance

Esta entrega contiene únicamente fixtures sintéticos y pruebas unitarias. No
es evidencia física, no ejecuta SIESTA/MPI/Hydra/Slurm y no modifica campañas,
FDF, perfiles ni código de producción.

La batería ataca el contrato
`siestaflow-bare-semantics-v2` en dos niveles:

1. integridad de la secuencia nativa (`DM → población seleccionada →
   perturbación → reconstrucción Hxc`);
2. procedencia de los artefactos ligados por SHA-256 (ejecutable, DM, FDF,
   salida y traza).

## Casos cubiertos

- marcador duplicado;
- marcador ausente o combinación parcial;
- eventos fuera de orden;
- modificación del ejecutable;
- modificación del DM padre;
- modificación del FDF;
- modificación de `siesta.out`;
- modificación de la traza sin actualizar su hash;
- `MPI_Abort`/terminación anormal aunque se actualice el hash de la salida;
- versión SIESTA distinta de la versión certificada;
- vocabulario de marcadores sustituido por cuatro cadenas arbitrarias;
- esquema parcial sin todos los campos de procedencia.

En todos estos casos, salvo las dos limitaciones explícitas indicadas abajo,
el verificador debe lanzar `BareSemanticEvidenceError`; por lo tanto no se
puede obtener `VerifiedBareEvidence`.

## Resultado de la revisión

Las pruebas demuestran que una traza no puede conservar un certificado válido
si se cambia cualquier artefacto ligado o si se rompe la secuencia de eventos.
Actualizar `trace_sha256` no oculta un orden inválido, un evento repetido, un
marcador faltante ni una terminación anormal.

## Corrección de Terra posterior a la auditoría

La auditoría identificó tres huecos y Terra los corrigió en la misma frontera
del verificador. La batería adversarial ya no contiene `xfail` para ellos:

1. `BareTraceExpectation` se aporta desde el contrato de campaña, no desde el
   sidecar. Fija tanto `source_revision` como los cuatro marcadores exactos.
   Una revisión o un vocabulario alterados se rechazan.
2. El verificador vuelve a leer `siesta.out` aun cuando coincida su hash y
   rechaza `MPI_Abort`, `ABNORMAL_TERMINATION` o ausencia de terminación
   normal.
3. `SiestaOutputValidator` no autoriza un nodo BARE si la política no declara
   una expectativa auditada.

Esto fortalece el contrato de verificación, pero no inventa una traza para un
binario estándar. Si no existe una revisión identificable y una gramática
nativa auditada, la decisión sigue siendo `CONTRACT GAP`, no `PASS`.

## Evidencia real indispensable para una prueba posterior

Para certificar BARE real serán necesarios, como mínimo:

- `siesta.out` y `siesta.err` de la misma corrida;
- FDF exacta y hash;
- DM padre exacta y hash;
- ejecutable y versión/build identificables;
- traza nativa versionada con los cuatro eventos únicos y ordenados;
- sidecar generado sin sobrescritura y ligado a todos los hashes;
- manifest del DAG que relacione nodo, perturbación y artefactos.

Una salida normal o un código de retorno cero no sustituyen la traza nativa.
