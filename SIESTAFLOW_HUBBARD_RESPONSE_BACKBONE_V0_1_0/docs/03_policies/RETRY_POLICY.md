# Política de reintentos

Un reintento sólo se permite para clases declaradas como recuperables.

## Ejemplos recuperables

- fallo transitorio del scheduler;
- filesystem temporal;
- timeout con checkpoint válido.

## Ejemplos no recuperables sin cambio de campaña

- parser ambiguo;
- geometría inconsistente;
- PSML alterado;
- respuesta no lineal;
- cambio de estado magnético.

Todo reintento crea un nuevo `attempt_id` y conserva intentos previos.


## Convenciones normativas

Las palabras **DEBE**, **NO DEBE**, **DEBERÍA**, **NO DEBERÍA** y **PUEDE** son normativas.  
Una regla marcada como DEBE es obligatoria para conformidad. Una regla marcada como DEBERÍA
puede omitirse sólo con una justificación registrada y auditable.
