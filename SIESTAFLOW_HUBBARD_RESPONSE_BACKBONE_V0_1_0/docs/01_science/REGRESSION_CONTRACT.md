# Contrato de regresión

Cada par observable-target se ajusta por separado para BARE y SCREENED.

## Salidas mínimas

- pendiente;
- intercepto;
- covarianza;
- error estándar;
- `R2`;
- `R2` ajustado;
- residuo máximo;
- curvatura;
- ajuste positivo;
- ajuste negativo;
- leave-one-out;
- puntos incluidos y excluidos;
- clasificación de gate.

## Reglas

- Los elementos fuera de la diagonal tienen los mismos gates que los diagonales.
- La exclusión de puntos requiere una regla predefinida.
- No se acepta un ajuste sólo por `R2` alto.
- El estimador y pesos deben estar versionados.
- El resultado debe poder recomputarse desde datos crudos.


## Convenciones normativas

Las palabras **DEBE**, **NO DEBE**, **DEBERÍA**, **NO DEBERÍA** y **PUEDE** son normativas.  
Una regla marcada como DEBE es obligatoria para conformidad. Una regla marcada como DEBERÍA
puede omitirse sólo con una justificación registrada y auditable.
