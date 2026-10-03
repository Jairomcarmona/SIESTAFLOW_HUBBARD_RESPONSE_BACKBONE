# TASK 22 — resumen de cierre

## Commits por ítem

| Ítem | Commit |
|---|---|
| Preparación y decisiones D13a–c | `3c0b8ca` |
| 22.1 — código de salida y evidencia de corridas fallidas | `c397fb1` |
| 22.2 — error explícito de versión del planificador | `d044deb` |
| 22.3 — parser y records de estado I.5 | `b54a74c` |
| Registro de preguntas científicas | `386dd52` |
| R11/R12 del autor | `72539b8` |
| 22.4 — gates de estado y pruebas | `80e2f3b` |
| 22.5 — integración, reporte y replay | `0a8a12f` |
| 22.6 — corrida real y guía WSL | este commit: `docs: record TASK 22 real NiO validation` |

## Cambios de pruebas y golden

- 22.1 amplió `tests/unit/test_runtime_adapters.py` para salida no cero, señales/launcher, OSError, límites de stdout/stderr y el recibo de falla. Los casos POSIX se verificaron en WSL.
- 22.2 añadió `test_resume_reports_explicit_planner_version_change` en `tests/unit/test_campaign_plan.py`.
- 22.4 añadió `tests/unit/test_state_gate.py`, pruebas para R11/R12 y fixtures comprimidos de stdout/`.EIG` de referencia y puntos NiO reales.
- 22.5 actualizó el replay y añadió `tests/fixtures/replay_nio_p5/replay_i5_state_gate.json`, SHA-256 `326f5f63ecc590d27350493ed28636dfe9a6f8bceb369902124581b61f430404`. No se regeneró el manifest. No hubo ediciones de pruebas ni golden en 22.6.

## Decisiones conservadoras

- R11 define `k` solo desde la referencia y devuelve `SUBSPACE_AMBIGUOUS` si el margen del punto no alcanza; R12 usa E_F y quantum impresos en `.EIG`, con comparación inclusiva y chequeo separado contra stdout.
- G3 suavidad permanece `NOT_ESTABLISHED:SMOOTHNESS_REQUIRES_SCF_LADDER` según D13a. I.5 sigue siendo diagnóstico.
- En la corrida real, solo la copia del perfil movió `wsl.workspace_root` a la carpeta de campaña nueva para mantener allí los artefactos.

## Ejecución y gates

La campaña real del ítem 22.6 terminó COMPLETED, sin `failure.json`; cuatro pares I.5 PASS, G4 APPLICABLE/PASS y U idéntico a Parte A (ΔU=0 para ambos sitios). Los detalles y hashes están en [TASK22_REAL_RUN.md](TASK22_REAL_RUN.md).

Los gates locales post-commit 22.6 están registrados en `TASK22_LOG.md`: replay 7, golden 4, producto 110, regresiones 70, arquitectura 8, ruff/formato/mypy, V6 `OK` y suite `1395 passed, 27 skipped, 20 xfailed, 4 subtests`. La punta final se publica sin PR y se verifica con dos corridas CI verdes consecutivas usando `gh run rerun`; sus enlaces se entregan en el reporte de cierre.
