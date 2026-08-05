# Política de selección de alpha

## Entradas

- rejilla inicial;
- límites;
- señal mínima;
- métricas de linealidad;
- curvatura;
- asimetría positivo/negativo;
- continuidad electrónica;
- presupuesto máximo.

## Acciones deterministas

- `ACCEPT_WINDOW`;
- `SHRINK_WINDOW`;
- `EXPAND_WINDOW`;
- `ADD_POINTS`;
- `REJECT_CANDIDATE`.

Las prioridades y desempates deben estar declarados en el lock. No se permite inspección visual
como criterio de ejecución.


## Convenciones normativas

Las palabras **DEBE**, **NO DEBE**, **DEBERÍA**, **NO DEBERÍA** y **PUEDE** son normativas.  
Una regla marcada como DEBE es obligatoria para conformidad. Una regla marcada como DEBERÍA
puede omitirse sólo con una justificación registrada y auditable.
