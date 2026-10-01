#!/usr/bin/env python3
"""Close V6 observable reporting after CoO and MnO validation."""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/'FINAL_SIESTA_VALIDATION_REPORT_V6.md'
text=REPORT.read_text(encoding='utf-8')
text=re.sub(r'Alcance:.*?\n\n## Resumen terminal',
    'Alcance: cierre de las validaciones de observables pendientes NiO, FeO, CoO y MnO a partir del baseline científico V6 y de las corridas/artefactos autorizados para esta campaña. Se calcularon bandas sólo como diagonalizaciones no autoconsistentes sobre HSX de densidades convergidas y se ejecutaron únicamente los SCF MnO PBE+LR-U central/LOW/HIGH requeridos. No se recalculó U, no se cambiaron umbrales científicos y no se inició la consolidación.\n\n## Resumen terminal',text,count=1,flags=re.S)
lines=text.splitlines()
for i,line in enumerate(lines):
    if line.startswith('| NiO |'):
        lines[i]='| NiO | ACCEPTED | COMPLETE | Malla SCF: PBE 0.973616 eV, LR-U 3.176566 eV; búsqueda BZ: PBE 0.9519 eV en 16×32×32 (resolución limitada), LR-U 3.1772 eV en 8×16×16; ruta LR-U 3.1771 eV | PBE: ±1.426543 μB; LR-U: +1.748446/−1.748453 μB | Malla PBE BZ limitada por resolución; los gaps de Seekpath son extremos muestreados de ruta | COMPLETE |'
    elif line.startswith('| FeO |'):
        lines[i]='| FeO | ACCEPTED | COMPLETE | Malla SCF: PBE metálico (0 eV), LR-U 2.305916 eV; ruta Seekpath: PBE metálico, LR-U 2.332999 eV; directo LR-U 2.480536 eV | PBE: ±3.645050 μB; LR-U: +3.908901/−3.908899 μB | Gaps de malla/ruta muestreados; no prueban el gap global continuo de la BZ | COMPLETE |'
    elif line.startswith('| CoO |'):
        lines[i]='| CoO | REVIEW | COMPLETE | Malla SCF: PBE metálico (0 eV), LR-U 2.714823 eV; ruta: PBE metálico, LR-U 2.713803 eV; directo LR-U 3.597498 eV | PBE: +2.534298/−2.534297 μB; LR-U: +2.819499/−2.819440 μB | Sensibilidad del estimador CoLR1=0.020261154 eV supera el límite vigente 0.020000000 eV por 0.000261154 eV | REVIEW |'
    elif line.startswith('| MnO |'):
        lines[i]='| MnO | PROTOCOL_REVIEW_REQUIRED | COMPLETE | Malla SCF: PBE 0.896971 eV; LR-U central 2.448575 eV; ruta Seekpath LR-U 2.448575 eV; directo 2.957409 eV; sensibilidad de malla LR-U 2.445493–2.451650 eV | PBE: +4.709330/−4.709330 μB; LR-U central: +5.063565/−5.063542 μB | U conserva su calificación de protocolo; LOW/CENTRAL/HIGH permanecen aislantes y se cuantificó la respuesta de gap/momento | PROTOCOL_REVIEW_REQUIRED |'
text='\n'.join(lines)+'\n'

coo=r'''## CoO: observables completos; calificación U permanece REVIEW

Se usaron los U de sitio certificados CoLR0=5.817148502021659 eV y CoLR1=5.815019855497104 eV. La calificación del estimador sigue siendo **REVIEW** porque la sensibilidad CoLR1 de 0.020261154 eV excede en 0.000261154 eV el límite vigente de 0.020000000 eV. Los observables no modifican esa calificación.

PBE convergió en 22 iteraciones (dDmax=5.7784×10⁻⁶, dHmax=4.50683×10⁻⁵ eV), con Etot=−9225.172943 eV, FreeEng=−9225.186411 eV, Ef=−4.211470 eV y momentos Mulliken CoLR0=+2.534298 μB/CoLR1=−2.534297 μB. La malla SCF de 23 puntos es **METAL**, con cruces de las bandas 23 y 24 en ambos spins.

PBE+LR-U convergió en 93 iteraciones (dDmax=4.8134×10⁻⁶, dHmax=4.78931×10⁻⁵ eV y cambio de población DFT+U=4.0288×10⁻⁶), con Etot=FreeEng=−9222.337920 eV, Ef=−3.502153 eV y momentos CoLR0=+2.819499 μB/CoLR1=−2.819440 μB. Su gap muestreado en la malla SCF es 2.714823 eV.

La compatibilidad HSX/EIG se estableció para ambos métodos. Ef coincide dentro de 1.33×10⁻⁹ eV (PBE) y 2.06×10⁻¹⁰ eV (LR-U). Las clasificaciones/canales de cruce son iguales; LR-U conserva VBM, CBM y gap con diferencias EIG−HSX de +1.25×10⁻⁹, −3.84×10⁻⁹ y −5.09×10⁻⁹ eV. La diferencia espectral máxima (0.179703 meV PBE; 0.180071 meV LR-U) se encuentra en k22≈(0,0.5,0.5), spin 1, banda 62, a 82.7/82.0 eV sobre Ef, aislada de las bandas vecinas. Dentro de ±5 eV de Ef, el máximo desacuerdo es 7.41 μeV (PBE) y 7.24 μeV (LR-U). La reducción Hermítica independiente y los residuos generalizados confirman una diagonalización numéricamente estable: residuo relativo máximo 8.81×10⁻¹⁶ y diferencia de autovalores frente al diagonalizador existente menor que 3×10⁻¹³ eV. Decisión: `HSX_EIG_SPECTRALLY_COMPATIBLE`.

Se empleó una única ruta Seekpath 2.2.2, `symprec=1e-5 Å`, grupo detectado R-3m (No. 166), 283 puntos: **Γ–T–H₂ | H₀–L–Γ–S₀ | S₂–F–Γ**. Cada método usa su propia DM/HSX convergida. Sobre la ruta, PBE es **METAL** (bandas 23 y 24 cruzan Ef en ambos spins), así que no se informa un gap aislante. PBE+LR-U es **INSULATOR**, sin cruces; VBM=−2.070320 eV relativo a Ef, banda 23 spin 1 en k=(0.825,0.4125,0.4125); CBM=+0.643483 eV, banda 24 spin 2 en Γ. El gap indirecto de ruta es 2.713803 eV. El mínimo gap directo muestreado es 3.597498 eV, bandas 23–24, spin 2, k=(0.025,0,0.025).

Los CSV se contrastaron con los arrays usados para trazar los SVG: 36,224 estados por método, discrepancia máxima de redondeo 5.1×10⁻¹¹ eV, referencia `E−Ef`, línea Ef en cero y cero estados dentro del intervalo de gap LR-U. Los gaps SCF y ruta son cantidades muestreadas y no prueban un gap global continuo de la BZ. Artefactos: [resultados](validation_observables_v6/coo/bands/results.json), [ruta Seekpath](validation_observables_v6/coo/bands/seekpath_route.json), [diagnóstico HSX/EIG](validation_observables_v6/coo/bands/hsx_eig_spectral_diagnostic.json), [bandas PBE](validation_observables_v6/coo/bands/CoO_PBE_SEEKPATH_BANDS.svg) y [bandas LR-U](validation_observables_v6/coo/bands/CoO_PBE+LR-U_SEEKPATH_BANDS.svg). No se inició ningún SCF adicional de CoO.
'''
mno=r'''## MnO: observables completos; calificación U permanece PROTOCOL_REVIEW_REQUIRED

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
'''
close=r'''## Cierre

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
'''
text='\n'.join(lines)+'\n'
co_marker='## CoO: repetibilidad pasa; precisión del estimador requiere revisión'
mn_marker='## MnO: certificado corregido; precisión del protocolo aún requiere revisión'
close_marker='## Cierre'
start=text.index(co_marker); mid=text.index(mn_marker,start); end=text.index(close_marker,mid)
text=text[:start]+coo+'\n'+mno+'\n'+close
REPORT.write_text(text,encoding='utf-8')
print(f'updated {REPORT}')
