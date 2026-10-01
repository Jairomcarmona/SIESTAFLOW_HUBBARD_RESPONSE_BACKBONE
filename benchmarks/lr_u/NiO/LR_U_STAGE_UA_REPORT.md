# NiO — informe de Stage U-A local

- Campaña: `d6d58dfd-8525-4d7f-b72c-5bbe679ec95f`; evidencia durable en `/home/jmc/.local/state/siestaflow/campaigns/lr-u-nio-restart-canary-r3-20260930`.
- Modelo: NiO rocksalt B1, celda magnética AFM-II de 4 átomos, PBE, DZP, malla 2×4×4, cutoff 200 Ry, smearing Fermi–Dirac 300 K. Perfil local WSL, SIESTA 5.4.2/OpenMPI, 4 rangos y concurrencia 1.
- Identidad de entradas: `2ddbe25854cbbcd114303fb0910fcc29247c385836fcc3e853237e20e3612fab`; presupuesto 41 nodos, 33 reservados, 8 restantes al detenerse.
- Evidencia: 37 nodos en el worker, todos válidos; 33 archivos `.times`; 513.759 s elapsed agregado y 4596.724 s CPU agregado. Tiempo calendario del worker 8 min 51 s (07:37:22–07:46:13 UTC).
- Malla α eV: `[-0.06,-0.04,-0.02,-0.01,0.01,0.02,0.04,0.06]`; ventana activa final 0.04 eV; polinomio grado 3; inversión de matrices raw.
- Resultado: `U_scalar_charge = 6.861874364188249 eV` en ambos sitios; `χ⁰=[[-0.1983500,0.0538358],[0.0538174,-0.1983500]] eV⁻¹`; `χ=[[-0.0812826,0.000896779],[0.000896779,-0.0812826]] eV⁻¹`. Ambas matrices tienen rango 2; condiciones 1.744884 y 1.022312.
- Decisión: `STOP_LIMIT_SENSITIVE`; candidato `NUMERICAL_CANDIDATE_UNASSESSED`; sensibilidad de modelo 0.001110279 eV/sitio; estabilidad de ventanas 0.000685526 eV. No se satisface el predicado de aceptación adaptativa.
- Certificado exacto posterior: `CERTIFIED` (`exact_rational_2x2`, consistencia y regularidad de `χ⁰`/`χ` verificadas). SHA científico `5064647ac55a6c894c9bdda57281eb45f3e6ab6c66de0f37eaf4b82c44130cb7`. Los intervalos racionales están en `u_certificate.v1.json` de la raíz indicada arriba.

**Alcance:** resultado de respuesta de carga `U_scalar_charge`, no `Ueff_Dudarev`. Sin aceptación física, observables, réplicas, ni `ValidatedURelease`.
