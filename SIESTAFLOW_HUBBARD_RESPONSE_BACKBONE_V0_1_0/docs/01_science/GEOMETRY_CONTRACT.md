# Contrato de geometría

La geometría es específica de la campaña, pero externa al núcleo.

## Debe registrar

- celda;
- coordenadas;
- unidades;
- periodicidad;
- orden de átomos;
- mapeo átomo-especie;
- hashes canónicos;
- política `FIXED_DURING_LINEAR_RESPONSE`.

## Reglas

- Cualquier cambio de celda, coordenada, especie u orden atómico invalida la caché dependiente.
- La geometría NO DEBE relajarse durante las perturbaciones de una matriz.
- Una geometría relajada con otro `U` constituye otra campaña o iteración metodológica.
- El núcleo NO DEBE contener coordenadas ni asumir número de átomos.


## Convenciones normativas

Las palabras **DEBE**, **NO DEBE**, **DEBERÍA**, **NO DEBERÍA** y **PUEDE** son normativas.  
Una regla marcada como DEBE es obligatoria para conformidad. Una regla marcada como DEBERÍA
puede omitirse sólo con una justificación registrada y auditable.
