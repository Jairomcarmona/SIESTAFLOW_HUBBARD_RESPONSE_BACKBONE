# Contrato de datos de respuesta

## Dimensiones generales

- `P`: perturbaciones independientes.
- `O`: observables crudos.
- `N`: subespacios físicos finales.
- `K_j`: puntos de perturbación para target `j`.

Las respuestas primarias tienen dimensión `O x P`. La transformación `A` tiene dimensión `N x O`.
Para inversión Hubbard se requiere `N = P`.

## Cada observación debe registrar

- target;
- alpha;
- modo BARE o SCREENED;
- observable;
- valor;
- unidad;
- iteración;
- procedencia;
- estado SCF;
- firma magnética;
- incertidumbre o resolución cuando exista.

## Reglas

No se permite rellenar datos ausentes con cero ni interpolar silenciosamente.


## Convenciones normativas

Las palabras **DEBE**, **NO DEBE**, **DEBERÍA**, **NO DEBERÍA** y **PUEDE** son normativas.  
Una regla marcada como DEBE es obligatoria para conformidad. Una regla marcada como DEBERÍA
puede omitirse sólo con una justificación registrada y auditable.
