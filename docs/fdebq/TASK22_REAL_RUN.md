# TASK 22 — corrida real de NiO P5

## Identidad y ejecución

- Punta congelada: `fdebq/r6-task22-i5`, `0a8a12f2244cf217d25047ea426c9578073ca00e`.
- Directorio nuevo de validación: `/home/jmc/hubbardflow_validation/task22_20261003_0a8a12f/`.
- Código congelado desde ese commit en `code/`; inputs copiados de `/home/jmc/hubbardflow_validation/nio_p5_20261003/inputs/`.
- Campaña: `nio_p5_task22_0a8a12f`; id `99494d9a-5875-40d5-9b7e-8e60d2d2f5e1`.
- SIESTA `5.4.2`, cuatro rangos MPI (`/usr/bin/orterun --host localhost:4 --map-by ppr:4:node -np 4 /home/jmc/.local/siesta-5.4.2-openmpi/bin/siesta`).
- Worker: PID `811`, estado final `COMPLETED`, 27 nodos validados. Inicio `2026-10-03T22:52:53.061654Z`; última marca de vida `2026-10-03T22:57:41.580628Z`.
- El lanzamiento usó `setsid nohup … < /dev/null > log 2>&1 &`. Se verificó desde una invocación nueva de WSL con `ps`: el worker, `orterun` y cuatro procesos SIESTA seguían vivos. El log está en `product/run.log` dentro del directorio anterior.
- El perfil de ejecución copiado cambió únicamente `wsl.workspace_root`, del almacén compartido a `.../task22_20261003_0a8a12f/campaigns`. Así los manifiestos, nodos y artefactos de esta corrida quedaron bajo el directorio nuevo autorizado. FDF, LR config y demás insumos se conservaron byte por byte; las rutas de origen declaradas por el LR config siguen apuntando a los insumos verificados.
- La solicitud de ejecución fue `ADMISSIBLE_LEGACY_EQUIVALENT`; el plan conserva `NOT_ESTABLISHED` y no se usó override. La corrida terminó sin `failure.json`.

## Premisas de inputs

El FDF preparado tiene SHA-256 `b4fb34e642d862be6949a5b2033a60c5b9fcae56119879583bb3eaf237620ee7`. Las copias de NiLR0 y NiLR1 comparten SHA-256 `192eb05ffb64671715e570e2ca9a99a551cf15544984592082d43004f8554e06`; O tiene `224ded5c59176d9bcb76d19b7a4a68a48d5dffabf8b262f64d5760250e87c35e`. El registro de compatibilidad tiene `5189620dfa1e8b6090cbdbb9c36c412835d16feb5c50bbc82b16c139d3bcff2e`; `siesta_version.txt`, `bb5a9b03dfaec9953401a7ef8db045149461047c44f15f9c5bf7758900b5f3ee`. La versión ejecutable informó `5.4.2`.

La campaña usó 24 perturbaciones: dos sitios, BARE/SCREENED y seis amplitudes con signo. La cuadrícula y los valores salen del LR config versionado, no se seleccionaron a partir de U.

## I.5

JSON: `/home/jmc/hubbardflow_validation/task22_20261003_0a8a12f/campaigns/nio_p5_task22_0a8a12f/results/i5_state_gate.json`  
SHA-256: `d3eb4ce6e84ee319edc1e96c9fb9d81e3c7dfb88899b0c2eecfdfb04fff83f0c`
Esquema `hubbardflow.i5_state_gate.v1`, política `i5-state-policy-v1`.

| Sitio | Modo | Veredicto del par | Amplitudes admitidas (eV) | G4 |
|---|---|---|---|---|
| NiLR0 | BARE | PASS | 0.02, 0.04, 0.06 | APPLICABLE / PASS en los seis puntos |
| NiLR0 | SCREENED | PASS | 0.02, 0.04, 0.06 | APPLICABLE / PASS en los seis puntos |
| NiLR1 | BARE | PASS | 0.02, 0.04, 0.06 | APPLICABLE / PASS en los seis puntos |
| NiLR1 | SCREENED | PASS | 0.02, 0.04, 0.06 | APPLICABLE / PASS en los seis puntos |

En todos los puntos `G1`, `G2`, `G3a` y `G4` dieron PASS; no se excluyó ninguna amplitud. G3 de suavidad figura `NOT_ESTABLISHED:SMOOTHNESS_REQUIRES_SCF_LADDER`, según D13a; no cambia los veredictos de estos pares. No hubo falla de I.5.

## Comparación de U con Parte A

Se comparó `primary` completo de `lr_u_analysis.v3.json` con el resultado Parte A en `nio_p5_product_2`; los objetos son idénticos. U escalar:

| Sitio | Parte A (eV) | Corrida real (eV) | Diferencia (eV) |
|---|---:|---:|---:|
| NiLR0 | 6.864267700049239 | 6.864267700049239 | 0 |
| NiLR1 | 6.864387475210124 | 6.864387475210124 | 0 |

La matriz U también coincide exactamente, entrada por entrada.
