# Visión y alcance

## Visión

Construir un procesador general, reproducible y auditable de respuesta lineal Hubbard para SIESTA
5.4.x, basado inicialmente en diferencias finitas y campañas adaptativas.

## Alcance de la versión metodológica inicial

La primera implementación operativa DEBE limitarse a:

- geometría fija durante la respuesta;
- magnetismo colineal;
- perturbaciones de carga;
- parámetro efectivo tipo Dudarev;
- un conjunto explícito de subespacios correlacionados;
- proyectores SIESTA declarados;
- campañas de diferencias finitas;
- matrices cuadradas físicamente definidas;
- Slurm como backend de ejecución HPC inicial.

## Resultado esperado

El sistema produce evidencia reproducible y candidatos numéricos. No produce por sí solo una
declaración de validez universal ni una recomendación científica automática.

## Audiencias

- desarrolladores del núcleo;
- autores de backends;
- investigadores que definen campañas;
- operadores HPC;
- auditores científicos;
- revisores humanos.


## Convenciones normativas

Las palabras **DEBE**, **NO DEBE**, **DEBERÍA**, **NO DEBERÍA** y **PUEDE** son normativas.  
Una regla marcada como DEBE es obligatoria para conformidad. Una regla marcada como DEBERÍA
puede omitirse sólo con una justificación registrada y auditable.
