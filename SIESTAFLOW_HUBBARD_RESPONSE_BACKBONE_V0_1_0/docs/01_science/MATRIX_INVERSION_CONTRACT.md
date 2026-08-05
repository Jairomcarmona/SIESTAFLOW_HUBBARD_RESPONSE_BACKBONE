# Contrato de inversión

## Precondiciones

- matriz cuadrada;
- todos los ajustes requeridos válidos;
- gate de antisimetría evaluado;
- rango numérico completo;
- condición dentro de política;
- matriz seleccionada fijada en el lock.

## Artefactos obligatorios

Para `chi0` y `chi`:

- matriz cruda;
- matriz simetrizada;
- matriz seleccionada;
- inversa;
- valores singulares;
- rango;
- número de condición;
- algoritmo;
- precisión;
- residuo izquierdo;
- residuo derecho.

## Residuos

\[
r_L = ||A^{-1}A-I||_F, \qquad
r_R = ||AA^{-1}-I||_F.
\]

## Fórmula

\[
U = \chi_0^{-1} - \chi^{-1}.
\]

La suite DEBE contener una mutación que cambie resta por suma y falle.


## Convenciones normativas

Las palabras **DEBE**, **NO DEBE**, **DEBERÍA**, **NO DEBERÍA** y **PUEDE** son normativas.  
Una regla marcada como DEBE es obligatoria para conformidad. Una regla marcada como DEBERÍA
puede omitirse sólo con una justificación registrada y auditable.
