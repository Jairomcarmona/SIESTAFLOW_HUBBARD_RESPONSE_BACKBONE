# Luna D — proveedor de evidencia BARE

## Alcance

Se añadió una interfaz de sólo validación para una traza BARE nativa ya
existente y su sidecar versionado. La validación reutiliza el verificador
`siestaflow-bare-semantics-v2`, que liga el sidecar a los hashes del
ejecutable, DM padre, FDF, salida y traza, y exige los cuatro eventos nativos
en el orden certificado.

## Candados

- No se ejecuta ni modifica SIESTA.
- No se crea un sidecar `PASS` a partir de `SCF.MustConverge`, códigos de
  salida, número de iteración ni texto ordinario de `siesta.out`.
- `collect()` falla cerrado: una traza sólo puede proceder de un backend
  nativo auditado o de evidencia externa versionada.
- Sustituir el ejecutable, DM, FDF, salida, sidecar o traza invalida la
  solicitud.
- No se modifican factory, validador de outputs, FDF, DAG, Slurm ni campañas.

## Pruebas focalizadas

`tests/unit/test_bare_trace_provider.py` cubre aceptación hash-ligada,
sustitución del ejecutable, sidecar ausente y rechazo de recolección implícita.
Las pruebas usan sólo fixtures sintéticas; no constituyen evidencia física.

## Límite explícito

La instalación estándar de SIESTA no se presume capaz de producir los
marcadores `TRACE: LR_BARE ...`. Hasta disponer de una traza nativa real y
versionada, BARE permanece bloqueado para producción.
