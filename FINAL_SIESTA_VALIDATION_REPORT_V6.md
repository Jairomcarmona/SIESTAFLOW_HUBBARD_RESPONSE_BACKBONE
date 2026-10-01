# Informe final de validación de observables Stage U-B V6

Fecha: 2026-10-01  
Baseline científico: commit `03ccd5913abdc6dd0e9e2cb59c0bc7637562c267`, tag `stage-ub-v6-20260930`.  
Alcance: cierre de las validaciones de observables pendientes NiO, FeO, CoO y MnO a partir del baseline científico V6 y de las corridas/artefactos autorizados para esta campaña. Se calcularon bandas sólo como diagonalizaciones no autoconsistentes sobre HSX de densidades convergidas y se ejecutaron únicamente los SCF MnO PBE+LR-U central/LOW/HIGH requeridos. No se recalculó U, no se cambiaron umbrales científicos y no se inició la consolidación.

## Resumen terminal

| Material | Calificación LR-U | Validación de observables | Gap informado | Momento local | Limitación pendiente | Estado final |
|---|---|---|---|---|---|---|
| NiO | ACCEPTED | COMPLETE | Malla SCF: PBE 0.973616 eV, LR-U 3.176566 eV; búsqueda BZ: PBE 0.9519 eV en 16×32×32 (resolución limitada), LR-U 3.1772 eV en 8×16×16; ruta LR-U 3.1771 eV | PBE: ±1.426543 μB; LR-U: +1.748446/−1.748453 μB | Malla PBE BZ limitada por resolución; los gaps de Seekpath son extremos muestreados de ruta | COMPLETE |
| FeO | ACCEPTED | COMPLETE | Malla SCF: PBE metálico (0 eV), LR-U 2.305916 eV; ruta Seekpath: PBE metálico, LR-U 2.332999 eV; directo LR-U 2.480536 eV | PBE: ±3.645050 μB; LR-U: +3.908901/−3.908899 μB | Gaps de malla/ruta muestreados; no prueban el gap global continuo de la BZ | COMPLETE |
| CoO | REVIEW | COMPLETE | Malla SCF: PBE metálico (0 eV), LR-U 2.714823 eV; ruta: PBE metálico, LR-U 2.713803 eV; directo LR-U 3.597498 eV | PBE: +2.534298/−2.534297 μB; LR-U: +2.819499/−2.819440 μB | Sensibilidad del estimador CoLR1=0.020261154 eV supera el límite vigente 0.020000000 eV por 0.000261154 eV | REVIEW |
| MnO | PROTOCOL_REVIEW_REQUIRED | COMPLETE | Malla SCF: PBE 0.896971 eV; LR-U central 2.448575 eV; ruta Seekpath LR-U 2.448575 eV; directo 2.957409 eV; sensibilidad de malla LR-U 2.445493–2.451650 eV | PBE: +4.709330/−4.709330 μB; LR-U central: +5.063565/−5.063542 μB | U conserva su calificación de protocolo; LOW/CENTRAL/HIGH permanecen aislantes y se cuantificó la respuesta de gap/momento | PROTOCOL_REVIEW_REQUIRED |

**PENDING_SIESTA_VALIDATIONS=0**  
**SIESTA_VALIDATION_PHASE=CLOSED**  
**READY_FOR_CONSOLIDATION_REVIEW=YES**

Estos estados indican que cada material tiene una conclusión terminal documentada. `READY_FOR_CONSOLIDATION_REVIEW=YES` habilita la revisión posterior; este informe no consolida, fusiona ni certifica el producto.

## NiO: gaps, bandas y momentos

La búsqueda estricta del gap global sobre mallas uniformes da para PBE un mejor valor muestreado de **0.9519 eV en 16×32×32**. La secuencia no alcanza convergencia de 1 meV, por lo que queda `BZ_GAP_CONVERGENCE=RESOLUTION_LIMITED`; no se duplicó más la malla. Para PBE+LR-U, **3.1772 eV en 8×16×16** es estable frente a 4×8×8 según los refinamientos disponibles. La densidad SCF de ambas ramas sigue siendo la V6 original 2×4×4.

La ruta de bandas fue generada con Seekpath 2.2.2 (`get_path_orig_cell`, simetría R-3m No. 166, `symprec=1e-5`) y se ejecutó con 283 puntos, 64 bandas y dos canales de spin. Sobre la ruta:

| Método | VBM | CBM | Gap indirecto de ruta | Mínimo gap directo en ruta |
|---|---|---|---:|---:|
| PBE | −5.0136 eV, banda 24, F–Γ, k=(0.5,0.25,0.25) | −3.7883 eV, banda 25, Γ–S₀, k=(0.464063,0.232031,0.464063) | 1.2253 eV | 1.3168 eV |
| PBE+LR-U | −5.8172 eV, banda 24, T | −2.6401 eV, banda 25, Γ | 3.1771 eV | 3.9337 eV |

Los canales SIESTA 1 y 2 están degenerados en los bordes VBM/CBM indicados. El mínimo gap directo es el menor gap vertical muestreado sobre la ruta y no implica que el mínimo directo global de la BZ tenga ese valor. El gap global de malla y el gap de ruta se reportan por separado: en PBE difieren de forma apreciable.

Los momentos de Ni son Mulliken y antiferromagnéticos: PBE ±1.426543 μB y LR-U ±1.748446/1.748453 μB. Frente a la referencia de neutrones 1.943(9) μB/Ni, las diferencias nominales en magnitud son 0.516457 μB (26.59 %) y 0.194551 μB (10.01 %), respectivamente; población de Mulliken y momento experimental no son particiones idénticas del momento.

Figuras vectoriales accesibles: [NiO PBE](results/stage-ub-v6-observables/figures/NiO_PBE_SEEKPATH_BANDS.svg) y [NiO PBE+LR-U](results/stage-ub-v6-observables/figures/NiO_PBE_LRU_SEEKPATH_BANDS.svg). Se corrigieron las leyendas a “spin channel 1/2” y se marcaron ambos canales degenerados en los extremos. El detalle de la ruta, coordenadas y archivos fuente está en [validación de observables NiO/FeO](results/stage-ub-v6-observables/OBSERVABLE_VALIDATION_STAGE_UB_V6.md), [búsqueda completa BZ NiO](results/stage-ub-v6-observables/nio-full-bz-gap-search/NIO_FULL_BZ_GAP_SEARCH.md) y [datos de Seekpath](results/stage-ub-v6-observables/seekpath_nio_high_symmetry_route.json).

## FeO: validación de bandas y cierre

La corrida PBE+LR-U a U completo terminó convergida en **33 iteraciones**: dDmax=0.000006, dHmax=0.000027 eV y cambio máximo de población local DFT+U=0.000005. Los observables finales son Etot=−7716.070778 eV, FreeEng=−7716.070778 eV, Ef=−3.768908 eV, momentos Mulliken FeLR0=+3.908901 μB y FeLR1=−3.908899 μB, y momento total ≈0. El gap muestreado en la malla SCF es 2.305916 eV.

La convergencia se obtuvo al reiniciar el cálculo full-U sin cambiar su FDF desde la DM near-converged que había producido el mismo cálculo. Ese proceso nuevo reinició la historia de Pulay; no cambió el Hamiltoniano científico. El intento full-U anterior acabó a 300 iteraciones con dDmax=0.000202 y dHmax=0.000094 eV; se preservó esa DM y el reinicio convergió con las mismas U, J, estructura, proyectores, malla, temperatura, tolerancias y controles SCF. No se alteró ningún parámetro SCF en el reinicio convergido.

La ruta estándar se calculó una vez con Seekpath 2.2.2 (`get_path_orig_cell`) a partir de la celda FeO AFM-II V6, `symprec=1e-5 Å`, `angle_tolerance=−1°`, con simetría espacial R-3m (No. 166) y time reversal. Se diferenciaron las dos subredes Fe en la detección de simetría (`FeLR0=26`, `FeLR1=27` como etiquetas; ambos sitios son Fe físico, Z=26). Ruta ordenada: **Γ–T–H₂ | H₀–L–Γ–S₀ | S₂–F–Γ**. Las coordenadas fraccionarias de los puntos de esta ruta en los vectores recíprocos de la celda original son:

| Punto | (kx, ky, kz) |
|---|---|
| Γ | (0, 0, 0) |
| T | (0.5, 0, 0) |
| H₂ | (1.125, 0.3125, 0.625) |
| H₀ | (0.875, 0.375, 0.6875) |
| L | (0.5, 0, 0.5) |
| S₀ | (0.6875, 0.34375, 0.6875) |
| S₂ | (1, 0.34375, 0.65625) |
| F | (1, 0.5, 0.5) |

La ruta se muestreó con 40 intervalos por tramo y **283 k-points** totales. Los dos HSX se generaron junto con sus propias DM convergidas: PBE DM SHA-256 `ae47355040d7…f3d2744`; LR-U DM SHA-256 `490c6895b8f1…be94f1`. Las bandas se obtuvieron diagonalizando cada HSX en esos mismos k-points; no se lanzó SIESTA ni se ejecutó un ciclo SCF en esta etapa.

| Método | VBM relativo a Ef | CBM relativo a Ef | Gap indirecto de ruta | Mínimo gap directo en ruta | Clasificación en ruta |
|---|---|---|---:|---:|---|
| PBE | 0.192294 eV, banda 22, canal 1, Γ→S₀ (t=0.950), k=(0.653125, 0.326563, 0.653125) | −0.279518 eV, banda 23, canal 1, T, k=(0.5, 0, 0) | −0.471812 eV | 0.005541 eV, bandas 22–23, canal 1, k=(0.0125, 0, 0.0125) sobre L→Γ | Metálico/solapado |
| PBE+LR-U | −1.782047 eV, banda 22, canal 1, T, k=(0.5, 0, 0) | 0.550952 eV, banda 23, canal 1, Γ, k=(0, 0, 0) | 2.332999 eV | 2.480536 eV, bandas 22–23, canal 1, Γ | Aislante |

PBE es metálico: el CBM de ruta cae por debajo del VBM. Para PBE+LR-U no hay cruces con Ef en ninguno de los dos canales de spin; el gap muestreado en la malla SCF es 2.305916 eV y el gap indirecto muestreado sobre Seekpath es 2.332999 eV. El mínimo directo de la ruta es 2.480536 eV. Se conserva explícitamente la distinción: **gap muestreado en malla SCF ≠ gap muestreado sobre Seekpath ≠ gap global de la BZ demostrado matemáticamente**. Ninguno de los gaps muestreados demuestra el gap global continuo de la BZ y no se ejecutó refinamiento uniforme de BZ.

La revisión de consistencia encontró que las energías que recibía el postprocesador ya estaban referidas a Ef. El SVG anterior restaba Ef por segunda vez; ese error de referencia creó los cruces aparentes de Ef. El postprocesador corregido escribe `energy_ev = (E−Ef)+Ef`, conserva `energy_minus_ef_ev = E−Ef` y grafica directamente `E−Ef`. Los CSV, SVG y JSON de PBE y PBE+LR-U se regeneraron diagonalizando solamente los HSX existentes. **No se necesitó recalcular SIESTA.**

Figuras vectoriales con ventana idéntica E−Ef=[−8,+8] eV y canales de spin coloreados de igual manera: [FeO PBE](FEO_SCF_DIAGNOSTIC_EXPORT_20261001/feo_seekpath_bands/FeO_PBE_SEEKPATH_BANDS.svg) y [FeO PBE+LR-U](FEO_SCF_DIAGNOSTIC_EXPORT_20261001/feo_seekpath_bands/FeO_PBE+LR-U_SEEKPATH_BANDS.svg). La ruta con todas las coordenadas especiales, resultados JSON, CSV de bandas y script reproducible están en [artefactos Seekpath FeO](FEO_SCF_DIAGNOSTIC_EXPORT_20261001/feo_seekpath_bands) y [analizador HSX/Seekpath](FEO_SCF_DIAGNOSTIC_EXPORT_20261001/analyze_feo_seekpath_bands.py). Los resultados de ruta no demuestran los extremos globales de toda la zona de Brillouin.

## CoO: observables completos; calificación U permanece REVIEW

Se usaron los U de sitio certificados CoLR0=5.817148502021659 eV y CoLR1=5.815019855497104 eV. La calificación del estimador sigue siendo **REVIEW** porque la sensibilidad CoLR1 de 0.020261154 eV excede en 0.000261154 eV el límite vigente de 0.020000000 eV. Los observables no modifican esa calificación.

PBE convergió en 22 iteraciones (dDmax=5.7784×10⁻⁶, dHmax=4.50683×10⁻⁵ eV), con Etot=−9225.172943 eV, FreeEng=−9225.186411 eV, Ef=−4.211470 eV y momentos Mulliken CoLR0=+2.534298 μB/CoLR1=−2.534297 μB. La malla SCF de 23 puntos es **METAL**, con cruces de las bandas 23 y 24 en ambos spins.

PBE+LR-U convergió en 93 iteraciones (dDmax=4.8134×10⁻⁶, dHmax=4.78931×10⁻⁵ eV y cambio de población DFT+U=4.0288×10⁻⁶), con Etot=FreeEng=−9222.337920 eV, Ef=−3.502153 eV y momentos CoLR0=+2.819499 μB/CoLR1=−2.819440 μB. Su gap muestreado en la malla SCF es 2.714823 eV.

La compatibilidad HSX/EIG se estableció para ambos métodos. Ef coincide dentro de 1.33×10⁻⁹ eV (PBE) y 2.06×10⁻¹⁰ eV (LR-U). Las clasificaciones/canales de cruce son iguales; LR-U conserva VBM, CBM y gap con diferencias EIG−HSX de +1.25×10⁻⁹, −3.84×10⁻⁹ y −5.09×10⁻⁹ eV. La diferencia espectral máxima (0.179703 meV PBE; 0.180071 meV LR-U) se encuentra en k22≈(0,0.5,0.5), spin 1, banda 62, a 82.7/82.0 eV sobre Ef, aislada de las bandas vecinas. Dentro de ±5 eV de Ef, el máximo desacuerdo es 7.41 μeV (PBE) y 7.24 μeV (LR-U). La reducción Hermítica independiente y los residuos generalizados confirman una diagonalización numéricamente estable: residuo relativo máximo 8.81×10⁻¹⁶ y diferencia de autovalores frente al diagonalizador existente menor que 3×10⁻¹³ eV. Decisión: `HSX_EIG_SPECTRALLY_COMPATIBLE`.

Se empleó una única ruta Seekpath 2.2.2, `symprec=1e-5 Å`, grupo detectado R-3m (No. 166), 283 puntos: **Γ–T–H₂ | H₀–L–Γ–S₀ | S₂–F–Γ**. Cada método usa su propia DM/HSX convergida. Sobre la ruta, PBE es **METAL** (bandas 23 y 24 cruzan Ef en ambos spins), así que no se informa un gap aislante. PBE+LR-U es **INSULATOR**, sin cruces; VBM=−2.070320 eV relativo a Ef, banda 23 spin 1 en k=(0.825,0.4125,0.4125); CBM=+0.643483 eV, banda 24 spin 2 en Γ. El gap indirecto de ruta es 2.713803 eV. El mínimo gap directo muestreado es 3.597498 eV, bandas 23–24, spin 2, k=(0.025,0,0.025).

Los CSV se contrastaron con los arrays usados para trazar los SVG: 36,224 estados por método, discrepancia máxima de redondeo 5.1×10⁻¹¹ eV, referencia `E−Ef`, línea Ef en cero y cero estados dentro del intervalo de gap LR-U. Los gaps SCF y ruta son cantidades muestreadas y no prueban un gap global continuo de la BZ. Artefactos: [resultados](validation_observables_v6/coo/bands/results.json), [ruta Seekpath](validation_observables_v6/coo/bands/seekpath_route.json), [diagnóstico HSX/EIG](validation_observables_v6/coo/bands/hsx_eig_spectral_diagnostic.json), [bandas PBE](validation_observables_v6/coo/bands/CoO_PBE_SEEKPATH_BANDS.svg) y [bandas LR-U](validation_observables_v6/coo/bands/CoO_PBE+LR-U_SEEKPATH_BANDS.svg). No se inició ningún SCF adicional de CoO.

## MnO: observables completos; calificación U permanece PROTOCOL_REVIEW_REQUIRED

El U usado proviene del certificado supersedente [MnO_u_certificate.superseding.v2.json](benchmarks/lr_u/forensic_audit/MnO_u_certificate.superseding.v2.json), SHA-256 `14133690a65fd3ced84594c95b4bed8aadab48c398b0aeeedd5f5d40f2f17265`, campaña `2eefb3e5-db29-4656-ad6a-99d2f0566038`. Los valores centrales exactos son MnLR0=11.117477005325092 eV y MnLR1=11.115065146109803 eV. Los extremos racionales certificados son MnLR0=[11.068637186266534, 11.166562301574963] eV y MnLR1=[11.066234041923392, 11.164141664047319] eV; sus fracciones exactas y procedencia están en [authoritative_u_inputs.json](validation_observables_v6/mno/authoritative_u_inputs.json). El certificado figura `CERTIFIED/CONSISTENT`, pero `physical_acceptance=NOT_ESTABLISHED`; la calificación de U sigue **PROTOCOL_REVIEW_REQUIRED**. El medio ancho geométrico de cada intervalo es 0.048962558 y 0.048953811 eV. El campo de certificado `half_width_by_site`, definido respecto al U nominal, es 0.049085296 y 0.049076518 eV; ambos se conservan separados porque los intervalos no están centrados exactamente en el nominal. Sensibilidades publicadas del estimador: 0.021176715/0.030738482 eV; de ventana: 0.013125851/0.020275758 eV.

### PBE y PBE+LR-U central

Se reutilizó la referencia PBE AFM-II convergida Stage U-A porque su entrada corresponde al FDF físico MnO vigente y ya incluye la DM/EIG/HSX/KP. Convergió en 13 iteraciones: dDmax=5.1345×10⁻⁶, dHmax=2.28926×10⁻⁵ eV, Etot=FreeEng=−6865.561143 eV, Ef=−4.888531 eV, momentos MnLR0=+4.709330/MnLR1=−4.709330 μB. La malla SCF de 23 puntos es **INSULATOR**, gap muestreado 0.896971 eV.

PBE+LR-U central se ejecutó con U de sitio anterior, cuatro MPI ranks y la DM PBE como `MNCL.DM`; `siesta.out` confirma `Attempting to read DM from file... Succeeded...`. Convergió en 13 iteraciones: dDmax=7.5796×10⁻⁶, dHmax=9.18511×10⁻⁵ eV, cambio de población DFT+U=6.2186×10⁻⁶, Etot=FreeEng=−6860.365334 eV, Ef=−5.222883 eV y momento total ≈10⁻⁶ μB; momentos MnLR0=+5.063565/MnLR1=−5.063542 μB. La malla SCF es **INSULATOR**, gap muestreado 2.448575 eV.

El diagnóstico HSX/EIG conserva el mismo cero de energía (diferencias de Ef 4.54×10⁻⁹ eV PBE y 7.93×10⁻¹⁰ eV LR-U), la misma clasificación y bordes/gap LR-U invariantes dentro de 5×10⁻⁹ eV. La discrepancia máxima, 0.126145 meV (PBE) y 0.126065 meV (LR-U), está en k13, spin 1, banda 64, a más de 137 eV sobre Ef; alrededor de Ef los máximos en ±5 eV son 5.05 μeV y 4.18 μeV. El residuo generalizado máximo es menor que 9×10⁻¹⁶. Decisión: `HSX_EIG_SPECTRALLY_COMPATIBLE`.

La ruta Seekpath 2.2.2 se generó desde la celda AFM-II exacta con `symprec=1e-5 Å`, sin imponer grupo espacial; Seekpath detectó R-3m (No. 166) y produjo 283 puntos, **Γ–T–H₂ | H₀–L–Γ–S₀ | S₂–F–Γ**. PBE y LR-U usan esta misma lista y sus propias DM/HSX. Ambos son aislantes en la ruta. PBE: gap indirecto 0.896971 eV, VBM banda 21 spin 1 en T y CBM banda 22 spin 2 en Γ, mínimo directo 1.421966 eV (bandas 21–22, spin 1, L). PBE+LR-U: VBM −1.493702 eV relativo a Ef (banda 21, spin 2, T), CBM +0.954873 eV (banda 22, spin 2, Γ), gap indirecto 2.448575 eV y mínimo directo 2.957409 eV (bandas 21–22, spin 2, Γ). Las validaciones CSV/SVG reproducen los arrays con error máximo de redondeo 5.1×10⁻¹¹ eV; no hay estados dentro de los intervalos de gap y Ef está graficado en cero.

### Sensibilidad SCF a los extremos certificados de U

LOW y HIGH son single-points SCF, no nuevas campañas LR-U. Ambos reiniciaron de `MNCL.DM`, leyeron exitosamente su DM y conservaron geometría, funcional, pseudos, base, malla, temperatura, proyectores, mezcla y tolerancias; sólo cambiaron U a los extremos racionales de sitio. Cada corrida convergió en 7 iteraciones.

| Caso | U(MnLR0) / U(MnLR1) (eV) | Estado en malla | Gap malla (eV) | MnLR0 / MnLR1 (μB) | Etot=FreeEng (eV) | Δgap vs central (eV) | Δmomento medio absoluto vs central (μB) |
|---|---:|---|---:|---:|---:|---:|---:|
| LOW | 11.068637186266534 / 11.066234041923392 | INSULATOR | 2.44549328 | +5.062935 / −5.062912 | −6860.382745 | −0.00308140 | −0.0006300 |
| CENTRAL | 11.117477005325092 / 11.115065146109803 | INSULATOR | 2.44857468 | +5.063565 / −5.063542 | −6860.365334 | 0 | 0 |
| HIGH | 11.166562301574963 / 11.164141664047319 | INSULATOR | 2.45164993 | +5.064203 / −5.064180 | −6860.347866 | +0.00307525 | +0.0006380 |

Los tres U mantienen la misma fase aislante y el mismo orden AFM-II; no se activa una condición de sensibilidad cualitativa. No se calcularon bandas LOW/HIGH. El gap de malla y el de ruta son cantidades muestreadas, no prueba matemática del gap continuo global de la BZ. Artefactos: [resultados de bandas](validation_observables_v6/mno/bands/results.json), [ruta Seekpath](validation_observables_v6/mno/bands/seekpath_route.json), [diagnóstico HSX/EIG](validation_observables_v6/mno/hsx_eig_spectral_diagnostic.json), [observables SCF](validation_observables_v6/mno/scf_observables.json) y [tabla de validación](validation_observables_v6/observable_validation_v6.json).

## Cierre

Las validaciones de observables NiO, FeO, CoO y MnO quedaron completas. Las calificaciones de U se mantienen en su propio eje y no fueron promovidas por los resultados de observables. Los gaps de malla y ruta son cantidades muestreadas; ninguna conclusión equivale a probar matemáticamente los extremos globales de la BZ continua. No se inició consolidación.

```text
NiO = COMPLETE
FeO = COMPLETE
CoO = COMPLETE
MnO = COMPLETE

PENDING_SIESTA_OBSERVABLE_VALIDATIONS = 0
SIESTA_VALIDATION_PHASE = CLOSED
READY_FOR_CONSOLIDATION_REVIEW = YES
```
