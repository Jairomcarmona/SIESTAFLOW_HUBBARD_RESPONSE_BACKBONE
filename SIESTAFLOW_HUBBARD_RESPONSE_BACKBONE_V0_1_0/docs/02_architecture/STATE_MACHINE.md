# Máquina de estados

## Estados permitidos

- `PLANNED`
- `READY`
- `RUNNING`
- `SUCCEEDED_UNVALIDATED`
- `VALIDATED`
- `REJECTED`
- `FAILED`
- `BLOCKED`
- `INVALIDATED`

## Transiciones principales

```text
PLANNED -> READY
READY -> RUNNING
RUNNING -> SUCCEEDED_UNVALIDATED | FAILED
SUCCEEDED_UNVALIDATED -> VALIDATED | REJECTED | INVALIDATED
PLANNED/READY -> BLOCKED
VALIDATED -> INVALIDATED  (si cambia una dependencia)
FAILED -> READY            (sólo mediante política de reintento)
```

## Regla crítica

Exit code cero nunca produce directamente `VALIDATED`.

## Terminalidad

`VALIDATED`, `REJECTED`, `FAILED`, `BLOCKED` e `INVALIDATED` son terminales para una revisión de
tarea concreta. Un reintento crea un nuevo `attempt_id`.


## Convenciones normativas

Las palabras **DEBE**, **NO DEBE**, **DEBERÍA**, **NO DEBERÍA** y **PUEDE** son normativas.  
Una regla marcada como DEBE es obligatoria para conformidad. Una regla marcada como DEBERÍA
puede omitirse sólo con una justificación registrada y auditable.
