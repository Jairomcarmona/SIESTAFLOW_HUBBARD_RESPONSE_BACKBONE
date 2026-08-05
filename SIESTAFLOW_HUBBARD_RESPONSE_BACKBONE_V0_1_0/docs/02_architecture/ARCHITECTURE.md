# Arquitectura

## Capas

```text
CLI / API
  |
Application services
  |
Domain core
  |---- planner and policies
  |---- analysis and gates
  |---- evidence and provenance
  |
Backend interfaces
  |---- SIESTA 5.4.x
  |---- synthetic backend
  |
Execution interfaces
  |---- local
  |---- Slurm allocation controller
```

## Núcleo

El núcleo contiene entidades y algoritmos generales. No contiene nombres de materiales,
elementos, geometrías ni recursos HPC concretos.

## Backends

Un backend traduce contratos generales a entradas y salidas de un motor. No decide qué sitio es
correlacionado ni qué umbral científico usar.

## Perfiles

Campañas y perfiles proporcionan datos específicos. Son serializables, validados por esquema,
versionados y dirigidos por contenido.


## Convenciones normativas

Las palabras **DEBE**, **NO DEBE**, **DEBERÍA**, **NO DEBERÍA** y **PUEDE** son normativas.  
Una regla marcada como DEBE es obligatoria para conformidad. Una regla marcada como DEBERÍA
puede omitirse sólo con una justificación registrada y auditable.
