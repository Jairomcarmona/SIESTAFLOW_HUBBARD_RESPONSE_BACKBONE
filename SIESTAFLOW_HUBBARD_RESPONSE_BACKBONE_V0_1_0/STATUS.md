# Estado del backbone

## Aceptado en esta versión

- La geometría es un input científico inmutable, no lógica del núcleo.
- La cardinalidad es dinámica: `P` perturbaciones, `O` observables, `N` subespacios físicos.
- No se invierten matrices rectangulares mediante pseudoinversa silenciosa.
- Se conservan matrices crudas, simetrizadas, seleccionadas, inversas y residuos.
- Todo gate y umbral debe estar en un lock metodológico versionado.
- Un código de salida cero sólo produce `SUCCEEDED_UNVALIDATED`.
- `recommended_single_U_ev` permanece `null` hasta decisión humana explícita.
- El backend SIESTA debe demostrar qué salida corresponde a BARE y SCREENED.

## No resuelto todavía

- Identificación exacta y validada de la población BARE en SIESTA 5.4.x.
- Umbrales científicos por defecto.
- Política general de equivalencia de sitios.
- Criterios de supercelda y convergencia por familia de sistemas.
- Soporte de magnetismo no colineal, SOC, J independiente, U+V o múltiples manifolds.
