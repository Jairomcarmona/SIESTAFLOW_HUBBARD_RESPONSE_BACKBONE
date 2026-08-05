# Especificación del backend SIESTA 5.4.x

## Responsabilidades

- generar FDF determinista;
- definir especies y proyectores de acuerdo con la campaña;
- aplicar `DFTU.PotentialShift`;
- preservar geometría fija;
- ejecutar y capturar salida MPI;
- identificar banner real;
- extraer poblaciones BARE y SCREENED;
- validar terminación y convergencia;
- registrar DM padre e hijo;
- producir evidencia localizable.

## Validación obligatoria antes de producción

1. Corrida instrumentada con salida completa.
2. Identificación de dónde se aplica la perturbación.
3. Demostración de la población BARE.
4. Demostración de la población SCREENED.
5. Fixtures positivos y negativos.
6. Comparación manual independiente.
7. Prueba contra al menos una campaña conocida.

## Prohibiciones

- confiar sólo en el nombre del módulo;
- asumir que la primera línea de población es BARE;
- aceptar versiones fuera del rango declarado;
- reutilizar DM sin hash y relación padre-hijo;
- mezclar stdout de múltiples ranks sin estrategia de captura.


## Convenciones normativas

Las palabras **DEBE**, **NO DEBE**, **DEBERÍA**, **NO DEBERÍA** y **PUEDE** son normativas.  
Una regla marcada como DEBE es obligatoria para conformidad. Una regla marcada como DEBERÍA
puede omitirse sólo con una justificación registrada y auditable.
