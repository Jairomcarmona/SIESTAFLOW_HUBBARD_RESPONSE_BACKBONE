# Contrato de proyectores

## Identidad

La identidad del proyector DEBE incluir:

- método de generación;
- canal orbital;
- `rc`;
- `omega`;
- parámetros adicionales;
- versión de SIESTA;
- especie y pseudopotencial;
- hash de entrada canónica.

## Reglas

- `rc` y `omega` son parte de la metodología y caché.
- Un plateau no convierte automáticamente un proyector en físicamente correcto.
- El proyector usado para calcular `U` DEBE coincidir con el usado al aplicar DFT+U.
- Los parámetros automáticos no reproducibles NO DEBEN usarse en campañas comparativas.


## Convenciones normativas

Las palabras **DEBE**, **NO DEBE**, **DEBERÍA**, **NO DEBERÍA** y **PUEDE** son normativas.  
Una regla marcada como DEBE es obligatoria para conformidad. Una regla marcada como DEBERÍA
puede omitirse sólo con una justificación registrada y auditable.
