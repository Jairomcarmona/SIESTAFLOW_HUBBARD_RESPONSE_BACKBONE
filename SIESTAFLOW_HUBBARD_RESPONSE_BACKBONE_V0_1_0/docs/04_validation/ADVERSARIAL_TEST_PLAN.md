# Plan de pruebas adversariales

La suite DEBE detectar:

- resta cambiada por suma;
- `chi0` y `chi` intercambiadas;
- transposición no autorizada;
- PSML modificado;
- geometría modificada;
- banner SIESTA modificado;
- DM padre incorrecta;
- perturbación ausente;
- salida MPI truncada;
- BARE ambiguo;
- no linealidad localizada;
- elemento fuera de diagonal degradado;
- antisimetría excesiva;
- matriz mal condicionada;
- inversa incompatible;
- matriz seleccionada distinta del lock;
- archivo no manifestado;
- recomendación sin decisión humana.

Cada prueba debe fallar por una razón específica y diagnosticable.


## Convenciones normativas

Las palabras **DEBE**, **NO DEBE**, **DEBERÍA**, **NO DEBERÍA** y **PUEDE** son normativas.  
Una regla marcada como DEBE es obligatoria para conformidad. Una regla marcada como DEBERÍA
puede omitirse sólo con una justificación registrada y auditable.
