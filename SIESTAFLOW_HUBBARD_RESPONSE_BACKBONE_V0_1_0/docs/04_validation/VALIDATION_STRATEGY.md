# Estrategia de validación

## Capas

1. **Esquemas:** entradas y artefactos válidos.
2. **Unitaria:** transformaciones, regresión, matrices e inversión.
3. **Sintética:** recuperación de `U` conocido.
4. **Parser:** fixtures SIESTA positivos y negativos.
5. **Reproducción:** campaña histórica.
6. **End-to-end:** sistema pequeño real.
7. **Adversarial:** mutaciones.
8. **Replicación:** ejecución independiente.

## Separación

- Validación de software no demuestra validez física.
- Comparación con literatura no sustituye consistencia interna.
- Coincidencia numérica con QE no es requisito universal por diferencias de subespacio.


## Convenciones normativas

Las palabras **DEBE**, **NO DEBE**, **DEBERÍA**, **NO DEBERÍA** y **PUEDE** son normativas.  
Una regla marcada como DEBE es obligatoria para conformidad. Una regla marcada como DEBERÍA
puede omitirse sólo con una justificación registrada y auditable.
