# Política de presupuesto de recursos

## Objetivo

Maximizar paralelismo sin sobreasignar la asignación Slurm ni comprometer reproducibilidad.

## Debe declarar

- recursos totales;
- reserva del controlador;
- recursos por clase de tarea;
- concurrencia máxima;
- memoria de seguridad;
- timeout;
- política de cancelación;
- prioridad entre ramas.

La poda adaptativa reduce trabajo científico innecesario; no reduce gates.


## Convenciones normativas

Las palabras **DEBE**, **NO DEBE**, **DEBERÍA**, **NO DEBERÍA** y **PUEDE** son normativas.  
Una regla marcada como DEBE es obligatoria para conformidad. Una regla marcada como DEBERÍA
puede omitirse sólo con una justificación registrada y auditable.
