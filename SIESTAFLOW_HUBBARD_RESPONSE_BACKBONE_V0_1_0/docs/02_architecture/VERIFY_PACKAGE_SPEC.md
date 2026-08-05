# Especificación de verify_package

El verificador DEBE:

- recomputar SHA-256;
- detectar archivos faltantes y no manifestados;
- validar esquemas;
- comprobar cardinalidades;
- recomputar regresiones cuando sea posible;
- recomputar transformación de observables;
- recomputar matrices;
- comprobar matriz seleccionada;
- recomputar inversas y residuos;
- recomputar `U`;
- verificar estados y dependencias;
- verificar identidad de geometría, PSML y runtime;
- rechazar recomendación sin decisión humana;
- devolver código distinto de cero ante cualquier fallo.

No debe confiar en un campo `"passed": true` sin recomputación.


## Convenciones normativas

Las palabras **DEBE**, **NO DEBE**, **DEBERÍA**, **NO DEBERÍA** y **PUEDE** son normativas.  
Una regla marcada como DEBE es obligatoria para conformidad. Una regla marcada como DEBERÍA
puede omitirse sólo con una justificación registrada y auditable.
