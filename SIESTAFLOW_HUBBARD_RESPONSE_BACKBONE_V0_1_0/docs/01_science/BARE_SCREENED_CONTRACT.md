# Contrato BARE/SCREENED

## BARE

BARE representa la derivada de la población antes del apantallamiento autoconsistente. Su
extracción es específica del backend y DEBE demostrarse con evidencia de la secuencia SCF.

## SCREENED

SCREENED representa la derivada de la población en el estado SCF convergido bajo la perturbación.

## Prohibiciones

El backend NO DEBE:

- asumir que la primera población impresa es BARE sin validación;
- usar una población previa a aplicar la perturbación;
- mezclar iteraciones de distintas ejecuciones;
- aceptar SCREENED sin convergencia demostrada;
- inferir BARE desde SCREENED por transformación algebraica no documentada.

## Evidencia mínima del backend

- líneas o registros de aplicación de perturbación;
- índice de iteración;
- población seleccionada;
- criterio de selección;
- banner y versión;
- fixture de salida validado;
- prueba end-to-end con comportamiento conocido.


## Convenciones normativas

Las palabras **DEBE**, **NO DEBE**, **DEBERÍA**, **NO DEBERÍA** y **PUEDE** son normativas.  
Una regla marcada como DEBE es obligatoria para conformidad. Una regla marcada como DEBERÍA
puede omitirse sólo con una justificación registrada y auditable.
