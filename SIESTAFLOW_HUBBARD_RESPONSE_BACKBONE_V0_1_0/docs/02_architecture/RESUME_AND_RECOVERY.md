# Reanudación y recuperación

## Reanudación segura

- Reutilizar sólo tareas `VALIDATED`.
- Revalidar hashes antes de reuso.
- Crear un `attempt_id` nuevo para reintentos.
- No sobrescribir artefactos previos.
- Registrar razón de reanudación.

## Fallos parciales

Un candidato tiene `failure.json` y `trace.jsonl` propios. Un fallo de radio/proyector no debe
contaminar candidatos independientes.

## Invalidación

Un cambio de dependencia propaga `INVALIDATED` a descendientes materializados.


## Convenciones normativas

Las palabras **DEBE**, **NO DEBE**, **DEBERÍA**, **NO DEBERÍA** y **PUEDE** son normativas.  
Una regla marcada como DEBE es obligatoria para conformidad. Una regla marcada como DEBERÍA
puede omitirse sólo con una justificación registrada y auditable.
