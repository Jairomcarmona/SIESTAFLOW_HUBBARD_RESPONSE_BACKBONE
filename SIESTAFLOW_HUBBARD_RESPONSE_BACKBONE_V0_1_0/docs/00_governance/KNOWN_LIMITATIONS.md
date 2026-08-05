# Limitaciones conocidas

- El backbone no contiene parser SIESTA validado.
- No se fijan umbrales científicos universales.
- No se garantiza determinismo bit a bit del SCF.
- No se resuelven estados metaestables de forma automática.
- No se infieren subespacios ni equivalencias desde química.
- No se implementa DFPT.
- No se validan todavía sistemas reales de referencia.
- La política Slurm inicial asume que job steps internos son compatibles con el clúster.
- La interpretación de poblaciones depende de la versión y compilación de SIESTA.


## Convenciones normativas

Las palabras **DEBE**, **NO DEBE**, **DEBERÍA**, **NO DEBERÍA** y **PUEDE** son normativas.  
Una regla marcada como DEBE es obligatoria para conformidad. Una regla marcada como DEBERÍA
puede omitirse sólo con una justificación registrada y auditable.
