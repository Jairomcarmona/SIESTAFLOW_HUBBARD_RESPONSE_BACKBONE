# Especificación del DAG

## Topología lógica

```mermaid
flowchart TD
  A[METHOD_LOCK] --> B[INPUT_AUDIT]
  B --> C[RUNTIME_PROBE]
  C --> D[REFERENCE_SCF]
  D --> E[REFERENCE_POPULATIONS]
  E --> F[ALPHA_PILOT]
  E --> G[PROJECTOR_COARSE_SCAN]
  F --> H[PROJECTOR_REFINEMENT]
  G --> H
  H --> I[CANDIDATE_FREEZE]
  I --> J[FULL_BARE_RESPONSE]
  I --> K[FULL_SCREENED_RESPONSE]
  J --> L[FIT_ALL_CHANNELS]
  K --> L
  L --> M[BUILD_SITE_MATRICES]
  M --> N[ANTISYMMETRY_GATE]
  N --> O[CONDITIONING_GATE]
  O --> P[MATRIX_SELECTION]
  P --> Q[MATRIX_INVERSION]
  Q --> R[INVERSION_RESIDUAL_GATE]
  R --> S[COMPUTE_U_MATRIX]
  S --> T[SENSITIVITY_ANALYSIS]
  T --> U[PACKAGE_EVIDENCE]
  U --> V[HUMAN_DECISION]
```

## Parametrización

El DAG se materializa desde cardinalidades declaradas, no desde constantes:

```text
for candidate in candidates:
  for target in perturbation_targets:
    for alpha in candidate.alpha_grid:
      create BARE and SCREENED tasks
```

## Poda

Una rama puede podarse por gate fallido. La poda debe registrar razón y dependencias bloqueadas.

## Reanudación

Los nodos validados pueden reutilizarse sólo si su identidad completa coincide.


## Convenciones normativas

Las palabras **DEBE**, **NO DEBE**, **DEBERÍA**, **NO DEBERÍA** y **PUEDE** son normativas.  
Una regla marcada como DEBE es obligatoria para conformidad. Una regla marcada como DEBERÍA
puede omitirse sólo con una justificación registrada y auditable.
