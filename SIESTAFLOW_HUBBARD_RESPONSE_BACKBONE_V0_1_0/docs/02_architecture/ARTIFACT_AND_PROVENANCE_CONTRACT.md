# Contrato de artefactos y procedencia

Cada tarea DEBE producir o declarar:

- `task.json`;
- `task.lock.json`;
- `status.json`;
- `runtime.json`;
- `validation.json`;
- `stdout.log`;
- `stderr.log`;
- `trace.jsonl`;
- `failure.json` cuando aplique;
- entradas materializadas;
- salidas;
- hashes.

## Procedencia

Toda matriz y métrica debe poder rastrearse hasta observaciones, salidas SIESTA, tarea, candidato,
geometría, pseudopotenciales y binario.

## Inmutabilidad

Los datos crudos no se modifican. Las derivaciones crean nuevos artefactos.


## Convenciones normativas

Las palabras **DEBE**, **NO DEBE**, **DEBERÍA**, **NO DEBERÍA** y **PUEDE** son normativas.  
Una regla marcada como DEBE es obligatoria para conformidad. Una regla marcada como DEBERÍA
puede omitirse sólo con una justificación registrada y auditable.
