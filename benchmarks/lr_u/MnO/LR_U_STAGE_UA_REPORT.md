# MnO — informe de Stage U-A local

- Campaña: `2eefb3e5-db29-4656-ad6a-99d2f0566038`; evidencia durable en `/home/jmc/.local/state/siestaflow/campaigns/lr-u-mno-afmii-stage-u-a-20260930`.
- Modelo congelado: MnO rocksalt B1, celda magnética AFM-II [111] de 4 átomos, `a=4.4455 Å`, PBE, DZP, malla 2×4×4, cutoff 200 Ry, smearing Fermi–Dirac 300 K, Hubbard Method 2 con CutoffNorm 0.90 y momentos iniciales ±5. Geometría basada en Kantor et al. (2005), [DOI 10.1016/j.jallcom.2005.04.155](https://doi.org/10.1016/j.jallcom.2005.04.155).
- Perfil local WSL, SIESTA 5.4.2/OpenMPI, 4 rangos; una ejecución simultánea. Identidad de entradas: `983137cd695e767247cf808cf0f0ef92978163df52879410d8e07b45499e65f5`.
- Ejecución: 41 nodos SIESTA/41 de presupuesto y 47 nodos completados por el worker; todos los recibos `VALIDATED`. Archivos `.times`: 304.750 s elapsed agregado, 2509.593 s CPU agregado. Ventana de worker: 07:55:43–08:01:09 UTC (5 min 26 s).
- Malla α eV: `[-0.06,-0.04,-0.02,-0.01,-0.005,0.005,0.01,0.02,0.04,0.06]`; ventana final 0.02 eV; ajuste polinómico grado 3 y matrices raw.
- Resultado: `U_scalar_charge`: MnLR0 `11.117477005325092 eV`, MnLR1 `11.115065146109803 eV`. `χ⁰=[[-0.1324302521,0.0406586835],[0.0406586835,-0.1324302521]] eV⁻¹`; `χ=[[-0.0519605042,0.00538711485],[0.00538711485,-0.0519669468]] eV⁻¹`. Rango 2; condiciones 1.886085 y 1.231323.
- Decisión adaptativa `STOP_STABLE`, dos comparaciones consecutivas equivalentes; candidato permanece `NUMERICAL_CANDIDATE_UNASSESSED` porque no hay tolerancia absoluta de precisión U predeclarada. Sensibilidad de modelo: 0.021177 y 0.030738 eV/sitio.
- Certificación exacta posterior: `CERTIFICATE_NOT_ESTABLISHED`, consistencia `NOT_ESTABLISHED`, sin método primario ni intervalos; causa declarada `INCONSISTENT_NOMINAL_AND_CERTIFICATE_INPUTS`. SHA científico: `852ce7298eb5980df3a627794db2b01f5eaa890ee1b1a1555cdfbdd531b956ef`. Se detuvo esta rama sin reintentos ni ajustes.

**Alcance:** `U_scalar_charge`; sin aceptación física, observables, réplicas, ni `ValidatedURelease`.
