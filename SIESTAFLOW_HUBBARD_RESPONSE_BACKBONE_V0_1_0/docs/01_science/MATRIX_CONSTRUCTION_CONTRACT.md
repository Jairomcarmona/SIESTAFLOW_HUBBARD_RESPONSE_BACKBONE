# Contrato de construcción matricial

## Flujo obligatorio

```text
datos crudos
 -> ajustes O x P
 -> transformación A
 -> chi0_raw y chi_raw de dimensión N x P
 -> verificación N = P
 -> gate de antisimetría
 -> matriz simetrizada opcional
 -> matriz seleccionada según lock
```

## Transformación de observables

La matriz `A` DEBE archivarse. En una suma de espines, cada fila identifica explícitamente los
canales que suma.

## Prohibiciones

- pseudoinversa silenciosa de matrices rectangulares;
- truncar observables para forzar cuadratura;
- transponer matrices sin contrato;
- simetrizar antes de medir antisimetría;
- construir sólo diagonales ignorando acoplamientos.


## Convenciones normativas

Las palabras **DEBE**, **NO DEBE**, **DEBERÍA**, **NO DEBERÍA** y **PUEDE** son normativas.  
Una regla marcada como DEBE es obligatoria para conformidad. Una regla marcada como DEBERÍA
puede omitirse sólo con una justificación registrada y auditable.
