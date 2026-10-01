# Stage U-B V6: validación de observables NiO / FeO

Baseline: commit 03ccd5913abdc6dd0e9e2cb59c0bc7637562c267, tag stage-ub-v6-20260930. Geometría fija, PBE, pseudopotenciales, DZP, meshcutoff 200 Ry, malla SCF 2×4×4 (23 k-points irreducibles), FD 300 K, orden AFM-II y tolerancias V6. Los dos métodos usan el mismo bloque de proyectores con DFTU.PotentialShift=false; DFT+U aplica Ueff=U-J con J=0 eV y U certificado asignado directamente por sitio LR0/LR1.

## Resultados de las ramas SCF V6

| Material / método | SCF | Energía total (eV/celda) | Momentos locales Mulliken (μB) | Estado/gap de malla SCF |
|---|---:|---:|---|---|
| NiO PBE | convergió, 16 iter. | −10107.202374 | NiLR0 +1.426543; NiLR1 −1.426543 | aislante; 0.97361552 eV |
| NiO PBE+LR-U | convergió, 103 iter. | −10104.152219 | NiLR0 +1.748446; NiLR1 −1.748453 | aislante; 3.17656591 eV |
| FeO PBE | convergió, 3 iter. desde DM común | −7719.060044 | FeLR0 +3.645050; FeLR1 −3.645050 | metálico; banda 22 cruza EF, gap 0 |
| FeO PBE+LR-U | no convergió, 300 iter. | — | — | no establecido; salidas descartadas |

En NiO, los gaps de malla proceden de los máximos ocupados y mínimos desocupados de EIG, referidos al EF del archivo y sobre los 23 puntos KP. PBE: VBM −5.01348651 eV en (−0.199336, 0.199336, −0.199336), spin 2 banda 24; CBM −4.03987099 eV en (0.398671, 0, 0), spin 1 banda 25. PBE+LR-U: VBM −5.81671381 eV en (−0.199336, 0.199336, 0.199336), spin 1 banda 24; CBM −2.64014790 eV en Gamma, spin 1 banda 25. Delta E total (LR-U menos PBE) = +3.050155 eV/celda; no es un observable experimental.

## Bandas NiO en ruta Seekpath

La ruta se calculó con Seekpath 2.2.2, usando get_path_orig_cell, symprec=1e-5, angle_tolerance=-1 y simetría de inversión temporal. Para la detección de simetría se distinguieron las dos subredes Ni AFM-II mediante IDs enteros 28 y 29; son etiquetas de simetría, y ambas siguen siendo Ni en los FDF/PSML. Seekpath encontró R-3m (No. 166), sin reducción a una celda primitiva química más pequeña. La ruta en coordenadas recíprocas fraccionarias de la celda original es Gamma-T-H_2 | H_0-L-Gamma-S_0 | S_2-F-Gamma, con 40 puntos por segmento.

| Método | SCF durante la salida de bandas | VBM en la ruta | CBM en la ruta | Gap indirecto de la ruta |
|---|---:|---|---|---:|
| NiO PBE | convergió, 2 iter.; E = −10107.202374 eV | −5.0136 eV, spins 1 y 2 degenerados, banda 24, F-Gamma, k=(0.500000, 0.250000, 0.250000) | −3.7883 eV, spins 1 y 2 degenerados, banda 25, Gamma-S_0, k=(0.464063, 0.232031, 0.464063) | 1.2253 eV |
| NiO PBE+LR-U | convergió, 10 iter.; E = −10104.152299 eV | −5.8172 eV, spins 1 y 2 degenerados, banda 24, Gamma-T, k=(0.500000, 0, 0) | −2.6401 eV, spins 1 y 2 degenerados, banda 25, Gamma, k=(0, 0, 0) | 3.1771 eV |

En ambas ramas se generaron 283 k-points, 64 bandas y dos canales de spin; en los bordes de banda reportados sus energías son degeneradas, por lo que la banda figura en ambos canales. No se observó cruce con EF en la ruta. Los extremos aquí son sólo los de la ruta de alta simetría; la ruta no demuestra por sí sola los extremos globales de toda la BZ. Los resultados de ruta y de malla SCF son cercanos para LR-U, mientras PBE difiere (0.974 eV en malla frente a 1.225 eV en ruta); se conserva esa diferencia y no se toma un único valor como gap global convergido.

## Comparación experimental y errores nominales

Error absoluto = |cálculo − referencia|. Error relativo = error absoluto / |referencia| × 100%.

- NiO brecha: referencia XPS+BIS de 4.3 eV en monocristal altamente estequiométrico. Sobre la malla SCF: PBE 3.32638448 eV (77.36%); LR-U 1.12343409 eV (26.13%). Sobre Seekpath: PBE 3.0747 eV (71.50%); LR-U 1.1229 eV (26.11%). Referencia espectroscópica y gaps KS no son exactamente el mismo observable; comparaciones indicativas.
- NiO momento: referencia de difracción de neutrones 1.943(9) μB/Ni. Usando magnitudes Mulliken: PBE 1.426543, error 0.516457 μB (26.59%); LR-U media de magnitudes 1.7484495, error 0.1945505 μB (10.01%). Mulliken no representa de forma idéntica la contribución orbital medida; errores nominales.
- FeO PBE momento: difracción en FeO casi estequiométrico reporta componentes 3.8(4) y 1.3(3) μB, módulo aproximadamente 4.016 μB. El Mulliken colineal 3.645050 difiere 0.371 μB (9.24%) nominal; composición, orientación y contribución orbital no son equivalentes. LR-U sin comparación: no convergió.
- FeO carácter/gap: PBE es metálico en 23 k-points (gap 0 frente al borde óptico AFM de aproximadamente 1.15 eV reportado en Fe0.93O). Diferencia aritmética 1.15 eV (100%), pero no es un error comparable: composición no estequiométrica, medición óptica y cálculo KS de FeO ideal difieren. No se asigna error LR-U.

## Estado terminal y límites

NiO_OBSERVABLE_VALIDATION = COMPLETE (ramas DFT y LR-U convergidas; bandas Seekpath ejecutadas; los valores de gap siguen limitados a la malla y a la ruta calculadas).
FeO_OBSERVABLE_VALIDATION = NOT_ESTABLISHED (rama LR-U no convergida después de tres intentos; no se usaron sus observables).


## Búsqueda global del gap de NiO en la BZ completa

La búsqueda estricta con mallas uniformes de la zona de Brillouin está documentada en [NIO_FULL_BZ_GAP_SEARCH.md](nio-full-bz-gap-search/NIO_FULL_BZ_GAP_SEARCH.md); incluye entradas y salidas de bandas. El resultado PBE más fino es 0.9519 eV en 16×32×32 y **no está convergido al umbral de 1 meV**. PBE+LR-U da 3.1772 eV en 8×16×16 y pasa el umbral frente a 4×8×8 para un par de refinamientos. En ambos casos la densidad autoconsistente sigue siendo la de V6 en 2×4×4.
