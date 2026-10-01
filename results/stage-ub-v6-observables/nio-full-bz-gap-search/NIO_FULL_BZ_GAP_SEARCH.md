# Búsqueda estricta del gap global de NiO en toda la zona de Brillouin

Fecha de cálculo: 2026-10-01. Baseline V6: commit 03ccd5913abdc6dd0e9e2cb59c0bc7637562c267, tag stage-ub-v6-20260930.

## Método

Se muestreó uniformemente toda la zona de Brillouin mediante bloques BandPoints, centrados en Gamma y expresados en coordenadas recíprocas fraccionarias de la celda V6. Se buscaron los extremos globales en todas las bandas y ambos canales de spin; no hay bandas que crucen el nivel de Fermi en estos resultados. En todos los trabajos se conservaron geometría, funcional, pseudopotenciales, parámetros DFT+U y condiciones SCF V6; la malla autoconsistente permaneció en 2×4×4 y se reutilizó la matriz DM guardada. El refinamiento densificó sólo los puntos usados para evaluar las bandas.

El umbral operativo de estabilidad es ≤1 meV para cada una de estas tres diferencias entre mallas consecutivas: VBM, CBM y gap indirecto. La tabla reporta energías en eV; los extremos están redondeados por la salida de bandas a 0.1 meV.

## Resultados

| Método | Malla BZ | Puntos | VBM (eV) | CBM (eV) | Gap indirecto (eV) |
|---|---:|---:|---:|---:|---:|
| PBE | 4×8×8 | 256 | -5.0135 | -4.0399 | 0.9736 |
| PBE | 8×16×16 | 2 048 | -5.0108 | -4.0399 | 0.9709 |
| PBE | 16×32×32 | 16 384 | -5.0092 | -4.0573 | 0.9519 |
| PBE+LR-U | 4×8×8 | 256 | -5.8173 | -2.6401 | 3.1772 |
| PBE+LR-U | 8×16×16 | 2 048 | -5.8173 | -2.6401 | 3.1772 |

## Comparación de refinamientos

| Método | Malla comparada | ΔVBM (meV) | ΔCBM (meV) | Δgap (meV) | Resultado del umbral |
|---|---|---:|---:|---:|---|
| PBE | 4×8×8 → 8×16×16 | 2.7 | 0.0 | -2.7 | No pasa |
| PBE | 8×16×16 → 16×32×32 | 1.6 | -17.4 | -19.0 | No pasa |
| PBE+LR-U | 4×8×8 → 8×16×16 | 0.0 | 0.0 | 0.0 | Pasa para este par |

PBE permanece **no convergido al umbral de 1 meV**. El valor de 0.9519 eV es el mínimo global hallado en la malla calculada de 16×32×32, no un gap global convergido: la malla más fina descubrió otro mínimo de conducción y el gap cambió 19.0 meV frente a 8×16×16. La búsqueda aún podría hallar un CBM más bajo al refinar.

PBE+LR-U da 3.1772 eV tanto en 4×8×8 como en 8×16×16 a la precisión publicada; VBM, CBM y gap cambian 0.0 meV en la salida redondeada. Esto pasa el criterio para el par comparado, pero es una única comparación de refinamiento y utiliza la densidad autoconsistente V6 de 2×4×4. No es una convergencia de la propia malla SCF.

## Ubicaciones de los extremos

PBE 16×32×32: VBM en spin 1, banda 24; CBM en spin 1, banda 25. PBE+LR-U 8×16×16: VBM en spin 1, banda 24; CBM en spin 1, banda 25, en Gamma para el CBM. Las coordenadas impresas en cada archivo de bandas están incluidas en sus registros run_record.json.

## Archivos y estado de los cálculos

Cada carpeta de malla contiene la entrada FDF, las bandas crudas, la salida siesta.out, el error estándar y el registro run_record.json. La ejecución PBE de 16×32×32 convergió SCF en 2 iteraciones y completó la diagonalización; PBE 8×16×16 y LR-U 8×16×16 también finalizaron correctamente. Las dos ejecuciones en 4×8×8 finalizaron correctamente.
