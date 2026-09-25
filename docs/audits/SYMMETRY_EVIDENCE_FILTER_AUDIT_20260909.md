# Symmetry evidence filter — Luna B proposal

## Alcance

Esta propuesta añade una ruta estricta para autorizar reducción de
perturbaciones. El certificado geométrico/magnético existente continúa siendo
compatible con el comportamiento anterior; la ruta estricta exige además un
`SymmetryEvidenceBundle` ligado por SHA-256 al certificado, al FDF de
referencia, a su salida y a la evidencia magnética.

El paquete también contiene una huella explícita del subespacio local por
átomo. Una operación magnética candidata sólo pasa el filtro si los átomos que
intercambia tienen la misma huella de subespacio. El filtro no infiere
equivalencia a partir de nombres de sitio ni de `DM.InitSpin`.

## Candados conservados

- La ausencia o incompletitud de evidencia produce `SymmetryPlanError` en la
  ruta estricta.
- La política existente `translation_only=True` sigue siendo la única que
  puede autorizar reducción; las rotaciones permanecen candidatas.
- La autorización exige todavía respuestas sombra directas y sus tolerancias
  preexistentes. Este cambio no altera ninguna tolerancia.
- No se añadió `spglib`, no se modificaron FDF, campañas, lanzadores, Slurm ni
  perfiles de sitio.

## Qué demuestran las pruebas

Las pruebas sintéticas verifican que:

1. un bundle correctamente ligado conserva sólo operaciones compatibles con el
   subespacio declarado;
2. una huella diferente elimina operaciones no triviales, conservando como
   máximo la identidad;
3. un hash de certificado incorrecto bloquea la planificación;
4. evidencia magnética incompleta bloquea la ruta estricta;
5. formatos desconocidos o hashes inválidos no se aceptan.

Pruebas ejecutadas:

```text
python -m pytest tests/unit/test_symmetry_evidence_contract.py \
  tests/unit/test_symmetry_reduction_plan.py \
  tests/unit/test_fdf_symmetry_adapter.py -q -p no:cacheprovider
15 passed
```

## Límites deliberados

Este cambio no implementa operaciones orbitales generales, inversión temporal,
SOC, no colinealidad ni simetría magnética automática. Tampoco genera el
bundle desde `siesta.out`: el adaptador de producción debe producirlo a partir
de una referencia aceptada y calcular sus hashes. Hasta entonces, la ruta
estricta es un contrato verificable y no una afirmación de capacidad de
producción.
