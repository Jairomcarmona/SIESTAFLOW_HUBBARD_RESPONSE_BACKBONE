# Límites de componentes

## Regla de no hardcodeo

El núcleo NO DEBE contener:

- símbolos de elementos;
- nombres de materiales;
- coordenadas;
- número fijo de sitios;
- dimensiones matriciales fijas;
- nombres de pseudopotenciales;
- rutas de clúster;
- particiones;
- módulos de entorno;
- umbrales específicos de una campaña.

## Dependencias permitidas

- El dominio no depende de SIESTA ni Slurm.
- El backend SIESTA depende del dominio mediante interfaces.
- El ejecutor depende de interfaces de tareas, no de física.
- Las políticas consumen métricas y producen decisiones.
- La evidencia observa todos los componentes, pero no altera resultados.


## Convenciones normativas

Las palabras **DEBE**, **NO DEBE**, **DEBERÍA**, **NO DEBERÍA** y **PUEDE** son normativas.  
Una regla marcada como DEBE es obligatoria para conformidad. Una regla marcada como DEBERÍA
puede omitirse sólo con una justificación registrada y auditable.
