# Contrato de subespacios correlacionados

Cada subespacio DEBE tener un identificador estable independiente del índice interno de SIESTA.

## Campos conceptuales

- `subspace_id`;
- átomo o conjunto de átomos asociado;
- especie SIESTA;
- canal orbital;
- convención de espín;
- definición de proyector;
- observable(s) asociado(s);
- target perturbable o sólo observable;
- grupo de equivalencia declarado.

## Reglas

- No se asigna `U` por elemento químico de forma automática.
- Dos sitios del mismo elemento NO se consideran equivalentes sin declaración.
- La cardinalidad `N` se deriva del contrato, nunca del código.
- La transformación de observables DEBE mapear inequívocamente a estos subespacios.


## Convenciones normativas

Las palabras **DEBE**, **NO DEBE**, **DEBERÍA**, **NO DEBERÍA** y **PUEDE** son normativas.  
Una regla marcada como DEBE es obligatoria para conformidad. Una regla marcada como DEBERÍA
puede omitirse sólo con una justificación registrada y auditable.
