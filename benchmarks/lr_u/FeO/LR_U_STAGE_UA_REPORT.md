# FeO — informe de Stage U-A local

- Campaña: `d1697a97-dd54-40d3-98c7-a17ed8de82dc`; evidencia durable en `/home/jmc/.local/state/siestaflow/campaigns/lr-u-feo-ideal-afmii-stage-u-a-20260930`.
- Modelo congelado: FeO estequiométrico ideal rocksalt B1, AFM-II [111], celda de 4 átomos, `a=4.334 Å`, PBE, DZP, malla 2×4×4, cutoff 200 Ry, smearing Fermi–Dirac 300 K y Hubbard Method 2 (`rc=3.0`, `omega=0.05`), momentos iniciales ±4. La estructura cúbica es un modelo ideal; wüstita real puede ser no estequiométrica y presentar complejidad magnética de baja temperatura ([Stølen et al. 1996](https://doi.org/10.1006/jssc.1996.0206)). No se modelaron vacantes ni distorsiones.
- Perfil local WSL, SIESTA 5.4.2/OpenMPI, 4 rangos; concurrencia 1. Identidad de entradas: `c41a5da26cfc8f01abb03692fc3f28bae72b16e2c052c99ec3f3abe837139558`.
- Ejecución: 25 nodos SIESTA; todos los nodos/recibos producidos fueron `VALIDATED`. Archivos `.times`: 378.621 s elapsed agregado, 3245.806 s CPU agregado. Worker 08:02:21–08:08:52 UTC (6 min 31 s). De presupuesto 41, 25 reservados y 16 restantes al detenerse.
- Malla α eV: `[-0.06,-0.04,-0.02,0.02,0.04,0.06]`; ventana activa 0.06 eV; ajuste polinómico grado 3, matrices raw.
- Resultado: `U_scalar_charge`: FeLR0 `5.638281766243177 eV`, FeLR1 `5.638315883828983 eV`. `χ⁰=[[-1.726883929,1.586477579],[1.586477579,-1.726899802]] eV⁻¹`; `χ=[[-0.1175371032,0.0352744048],[0.0352744048,-0.1175371032]] eV⁻¹`. Rango 2; condiciones 23.59710 y 1.857604.
- Decisión adaptativa `STOP_LIMIT_SENSITIVE`; candidato `NUMERICAL_CANDIDATE_UNASSESSED`; sensibilidad de modelo 0.000640554 y 0.000682422 eV/sitio. No existe tolerancia absoluta de precisión U en el análisis.
- Certificación exacta posterior: `CERTIFIED`, método `exact_rational_2x2`, consistencia y regularidad de ambas matrices verificadas. SHA científico `c04997b0c4753048c68a42ee999ef3bf0b9fb0273c0fc51b1e9d901080e1a8a5`. Intervalos racionales en `u_certificate.v1.json` de la raíz arriba.

**Alcance:** `U_scalar_charge`; sin aceptación física, observables, réplicas, ni `ValidatedURelease`.
