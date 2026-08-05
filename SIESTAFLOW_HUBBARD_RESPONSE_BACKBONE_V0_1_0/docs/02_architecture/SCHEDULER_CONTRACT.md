# Contrato del scheduler

## Modelo

El DAG puede ejecutarse dentro de una asignación Slurm mediante job steps controlados.

## Debe gestionar

- CPUs, nodos y memoria disponibles;
- máximo de pasos concurrentes;
- aislamiento de directorios;
- códigos de salida;
- cancelación;
- timeouts;
- reserva para el controlador;
- afinidad MPI;
- recuperación;
- evidencia por step.

## Reglas

- Ningún step puede exceder recursos de la asignación.
- La concurrencia debe derivarse de un presupuesto materializado.
- Un fallo de una rama no corrompe otras ramas.
- No se lanzan shells remotos ad hoc fuera del contrato.


## Convenciones normativas

Las palabras **DEBE**, **NO DEBE**, **DEBERÍA**, **NO DEBERÍA** y **PUEDE** son normativas.  
Una regla marcada como DEBE es obligatoria para conformidad. Una regla marcada como DEBERÍA
puede omitirse sólo con una justificación registrada y auditable.
