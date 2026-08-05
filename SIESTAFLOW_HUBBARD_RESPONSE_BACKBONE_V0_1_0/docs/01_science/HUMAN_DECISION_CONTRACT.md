# Contrato de decisión humana

La herramienta sólo puede elevar automáticamente un candidato a
`CANDIDATE_READY_FOR_REVIEW`.

## La aprobación debe registrar

- identificador del candidato;
- revisor;
- fecha;
- decisión;
- justificación;
- alcance de validez;
- hashes de artefactos revisados;
- valor o matriz aceptada;
- limitaciones;
- firma criptográfica o hash del registro.

## Inmutabilidad

La aprobación crea un artefacto nuevo. No modifica matrices, gates ni evidencia previa.


## Convenciones normativas

Las palabras **DEBE**, **NO DEBE**, **DEBERÍA**, **NO DEBERÍA** y **PUEDE** son normativas.  
Una regla marcada como DEBE es obligatoria para conformidad. Una regla marcada como DEBERÍA
puede omitirse sólo con una justificación registrada y auditable.
