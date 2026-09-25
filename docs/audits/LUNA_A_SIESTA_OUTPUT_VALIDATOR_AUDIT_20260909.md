# Luna A — auditoría del adaptador de salida SIESTA

## Alcance

Esta entrega añade únicamente un validador de artefactos para nodos SIESTA.
No ejecuta SIESTA, MPI, Hydra ni Slurm y no modifica lanzadores, campañas,
materializadores ni perfiles de sitio.

## Candados implementados

- El nodo debe tener un contrato explícito de FDF, salida y DM, con rutas
  relativas al directorio del nodo.
- Las rutas absolutas, escapes mediante `..`, archivos ausentes y archivos
  vacíos se rechazan.
- Una salida normal sin evidencia científica no autoriza el nodo.
- Las salidas SCREENED con `SCF_NOT_CONV`, terminación anormal, `MPI_Abort`,
  errores de pseudopotencial o `FATAL` se rechazan. Un marcador
  `SCF_NOT_CONV` sólo puede aparecer en BARE si el sidecar semántico demuestra
  que corresponde a la terminación intencional de Hxc fijo; no se acepta por sí
  solo.
- Una referencia exige evidencia magnética ya validada por el parser existente
  de SIESTA 5.4 o una declaración explícita y comprobada de estado no
  polarizado.
- Un nodo SCREENED exige terminación normal, ausencia de marcadores de SCF no
  convergida y DM no vacía.
- Un nodo BARE exige el sidecar semántico versionado existente, ligado por
  SHA-256 al ejecutable, DM de referencia, FDF, salida y traza nativa. No se
  infiere BARE a partir de `MaxSCFIterations`.
- Modos desconocidos, incluidos SOC, no colinealidad y variantes no
  certificadas, se rechazan.
- El recibo contiene un digest de nodo, comando lógico y hashes de artefactos;
  el validador expone además la procedencia estructurada para el runtime.

## Pruebas focalizadas

Ejecutadas sin SIESTA/MPI/Slurm:

```text
python -m pytest tests/unit/test_siesta_output_validator.py \
  tests/unit/test_runtime_adapters.py \
  tests/unit/test_reference_magnetic_evidence.py \
  tests/unit/test_bare_semantics_evidence.py -q -p no:cacheprovider
18 passed
```

Las pruebas cubren salida SCREENED válida, DM ausente, referencia no polarizada
explícita, modo desconocido y sidecar BARE inválido, además de las regresiones
de los parsers y adaptadores existentes.

## Límites deliberados

Esto no constituye todavía un ejecutor de producción completo: el
`CommandFactory` debe ser implementado por el runtime y debe producir los
artefactos declarados. Tampoco activa SOC, no colinealidad, múltiples
subespacios ni (U+V). La prueba en Yoltla sólo podrá autorizarse después de
que Terra integre este validador en un perfil aislado y revise el diff.
