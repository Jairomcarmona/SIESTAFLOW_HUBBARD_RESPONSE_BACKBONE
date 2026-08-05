# Casos de referencia

## R0: sintético diagonal

Matrices diagonales conocidas, sin ruido. Debe recuperar `U` exactamente dentro de tolerancia.

## R1: sintético acoplado

Matrices densas simétricas y bien condicionadas. Debe recuperar términos diagonales y no diagonales.

## R2: ruido controlado

Debe recuperar dentro del intervalo esperado y reportar sensibilidad.

## R3: no linealidad localizada

Un solo observable-target contiene curvatura. Debe fallar aunque las diagonales sean válidas.

## R4: antisimetría excesiva

Debe fallar antes de simetrizar.

## R5: SIESTA fixture

Se añadirá cuando el contrato BARE/SCREENED se valide contra una salida real.


## Convenciones normativas

Las palabras **DEBE**, **NO DEBE**, **DEBERÍA**, **NO DEBERÍA** y **PUEDE** son normativas.  
Una regla marcada como DEBE es obligatoria para conformidad. Una regla marcada como DEBERÍA
puede omitirse sólo con una justificación registrada y auditable.
