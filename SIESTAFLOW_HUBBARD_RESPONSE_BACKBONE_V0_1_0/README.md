# SIESTAFLOW Hubbard Response Backbone

**Versión:** 0.1.0  
**Estado:** columna vertebral documental y de esquemas; no es todavía un motor científico operativo.

Este paquete define los contratos, límites arquitectónicos, DAG, máquina de estados, políticas,
artefactos y esquemas JSON necesarios para implementar un procesador general de respuesta lineal
Hubbard sobre SIESTA 5.4.x.

El objetivo es que Codex, Antigravity u otro agente de ingeniería puedan implementar el sistema
sin hardcodear una geometría, material, elemento, número de sitios, clúster o campaña particular.

## Principio central

SIESTA resuelve la respuesta electrónica para una entrada concreta:

```text
geometría + subespacios Hubbard + perturbación + parámetros numéricos
    -> poblaciones y estado electrónico
```

SIESTAFLOW Hubbard Response organiza, valida y documenta el experimento completo:

```text
contrato de campaña
    -> DAG adaptativo
    -> respuestas BARE/SCREENED
    -> ajustes
    -> matrices chi0/chi
    -> inversión validada
    -> matriz U
    -> sensibilidad
    -> paquete de evidencia
    -> decisión humana explícita
```

## Separación obligatoria

- El **núcleo** no conoce birnessita, Mn, seis sitios ni Yoltla.
- El **backend SIESTA** conoce FDF, ejecución y parsing, pero no decide la química.
- El **contrato de campaña** declara geometría, subespacios, perturbaciones y políticas.
- El **perfil HPC** declara Slurm, MPI, memoria y tiempo.
- La **decisión científica** permanece separada del éxito computacional.

## Contenido

- `docs/00_governance/`: alcance, gobernanza y control de cambios.
- `docs/01_science/`: contratos físicos y matemáticos.
- `docs/02_architecture/`: arquitectura, DAG, estados, caché y artefactos.
- `docs/03_policies/`: políticas adaptativas y gates configurables.
- `docs/04_validation/`: estrategia de validación y pruebas adversariales.
- `schemas/`: JSON Schema Draft 2020-12.
- `examples/`: campaña sintética mínima, sin dependencia de SIESTA real.
- `tools/verify_backbone.py`: verificador estructural y de ejemplos.

## Uso previsto

1. Congelar esta versión como referencia.
2. Resolver decisiones abiertas registradas en `docs/00_governance/OPEN_DECISIONS.md`.
3. Implementar primero un backend sintético.
4. Implementar después el backend SIESTA 5.4.x y validar la extracción BARE/SCREENED.
5. Reproducir una campaña histórica.
6. Ejecutar una campaña viva pequeña.
7. Sólo entonces habilitar campañas adaptativas de producción.

## Verificación

```bash
python tools/verify_backbone.py
```

La verificación comprueba estructura, JSON, esquemas, ejemplos, referencias de archivos y manifiesto SHA-256.


## Convenciones normativas

Las palabras **DEBE**, **NO DEBE**, **DEBERÍA**, **NO DEBERÍA** y **PUEDE** son normativas.  
Una regla marcada como DEBE es obligatoria para conformidad. Una regla marcada como DEBERÍA
puede omitirse sólo con una justificación registrada y auditable.
