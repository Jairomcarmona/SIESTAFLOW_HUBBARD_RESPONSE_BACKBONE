# Contrato de perturbación

## Requisitos

- rejilla simétrica alrededor de cero;
- unidades explícitas;
- target inequívoco;
- referencia común;
- política de ampliación/reducción;
- límites máximos;
- número mínimo de puntos;
- tratamiento de `alpha = 0`.

## Reglas

- La señal debe superar el ruido numérico.
- La perturbación debe permanecer en régimen lineal.
- La rama positiva y negativa deben ser consistentes.
- Cambios electrónicos discontinuos invalidan el ajuste.
- La selección de ventana debe ser determinista dado el lock y los resultados.


## Convenciones normativas

Las palabras **DEBE**, **NO DEBE**, **DEBERÍA**, **NO DEBERÍA** y **PUEDE** son normativas.  
Una regla marcada como DEBE es obligatoria para conformidad. Una regla marcada como DEBERÍA
puede omitirse sólo con una justificación registrada y auditable.
