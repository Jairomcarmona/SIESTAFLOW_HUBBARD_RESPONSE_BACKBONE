# CoO — informe de Stage U-A local

- Campaña: `ae62285c-268f-48f9-9c0a-8b2064a3f192`; evidencia durable en `/home/jmc/.local/state/siestaflow/campaigns/lr-u-coo-ideal-afmii-stage-u-a-20260930`.
- Modelo congelado: CoO ideal rocksalt B1, celda magnética AFM-II [111] de 4 átomos, `a=4.254 Å`, PBE, DZP, malla 2×4×4, cutoff 200 Ry, smearing Fermi–Dirac 300 K y Hubbard Method 2 (`rc=3.0`, `omega=0.05`), momentos iniciales ±3. La estructura cúbica es el modelo teórico de transferencia de esta etapa; CoO real es monoclinico C2/m a baja temperatura ([Jauch et al. 2001](https://doi.org/10.1103/PhysRevB.64.052102)). No se presenta el modelo como estructura de equilibrio de baja temperatura.
- Perfil local WSL, SIESTA 5.4.2/OpenMPI, 4 rangos; concurrencia 1. Identidad de entradas: `b7d94badc338fb4cacb1f964231917fc16be7a144fa3346b133ef24bffed22ff`.
- Ejecución: 41 nodos SIESTA/41 de presupuesto y 47 nodos completados por el worker; 47/47 recibos `VALIDATED`. Archivos `.times`: 549.005 s elapsed agregado, 4619.364 s CPU agregado. Worker 08:09:51–08:19:22 UTC (9 min 31 s).
- Malla α eV: `[-0.06,-0.04,-0.02,-0.01,-0.005,0.005,0.01,0.02,0.04,0.06]`; ventana final 0.02 eV; ajuste polinómico grado 3, matrices raw.
- Resultado: `U_scalar_charge`: CoLR0 `5.818030435715443 eV`, CoLR1 `5.817951497770718 eV`. `χ⁰=[[-1.355339776,1.205665546],[1.205695798,-1.355309524]] eV⁻¹`; `χ=[[-0.1170631653,0.0344915966],[0.0344915966,-0.1170631653]] eV⁻¹`. Rango 2; condiciones 17.11399 y 1.835435.
- Decisión adaptativa `STOP_STABLE`, dos comparaciones consecutivas equivalentes; candidato `NUMERICAL_CANDIDATE_UNASSESSED` por falta de tolerancia absoluta predeclarada. Sensibilidad de modelo: 0.000430237 y 0.000496730 eV/sitio; variación de la última ronda: 0.001235130 eV.
- Certificación exacta posterior: `CERTIFICATE_NOT_ESTABLISHED`; consistencia `NOT_ESTABLISHED`, método primario e intervalos ausentes. Causa registrada: `INCONSISTENT_NOMINAL_AND_CERTIFICATE_INPUTS`. SHA científico del certificado: `5d6cf40d341f34df71efc3ea7e2e9264e49e68badeff1b53f061a7557982db73`. Se detuvo esta rama sin reintentos ni ajustes.

**Alcance:** `U_scalar_charge`; sin aceptación física, observables, réplicas, ni `ValidatedURelease`.
