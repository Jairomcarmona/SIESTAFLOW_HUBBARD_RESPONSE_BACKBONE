# Identidad de tareas y caché

## Componentes mínimos del hash

- versión metodológica;
- versión de esquema;
- geometría;
- FDF canónico;
- pseudopotenciales;
- binario SIESTA;
- banner SIESTA;
- banner MPI;
- proyectores;
- target;
- alpha;
- modo;
- DM padre;
- parámetros numéricos;
- backend;
- política de parsing.

## Regla

La caché es por contenido y evidencia, no por nombre de carpeta.

Una tarea cacheada sólo puede reutilizarse si:

- su identidad coincide;
- su estado es `VALIDATED`;
- su manifiesto pasa;
- sus dependencias siguen válidas;
- la metodología permite compatibilidad.


## Convenciones normativas

Las palabras **DEBE**, **NO DEBE**, **DEBERÍA**, **NO DEBERÍA** y **PUEDE** son normativas.  
Una regla marcada como DEBE es obligatoria para conformidad. Una regla marcada como DEBERÍA
puede omitirse sólo con una justificación registrada y auditable.
