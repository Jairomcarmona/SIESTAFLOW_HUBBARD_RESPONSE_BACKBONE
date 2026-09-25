# Reconstrucción de la traza de salida SIESTA — MnO, 21-sep-2026

Resultado inspeccionado: `campaigns\mno_afmii_strict_lr_v3r2\results\response-matrix-foreground-recovery-v4`. Se reconstruyeron 29 ejecuciones: 1 referencia, 14 BARE y 14 SCREENED. Solo se leyeron archivos ya existentes; no se lanzó SIESTA/Slurm ni se modificó su código.

## Conclusión de traza

- Las 14/14 salidas BARE tienen un bloque completo de 16 poblaciones entre `stepf` y `scf: 1`; este es el evento candidato de primera diagonalización. En todas las respuestas BARE el evento está en líneas `5370–5835`; `stepf` está en 5369 y `scf: 1` en 5863.
- Las 14/14 salidas SCREENED convergen entre 3 y 12 iteraciones y conservan un último bloque de 16 poblaciones después del marcador de convergencia y del uso de `DM_out`; ese es el evento SCREENED que corresponde seguir.
- Las 29 salidas terminan con `Job completed` y tienen marcador externo `0_NORMAL_EXIT`. Los 28 hashes de `.out` registrados en `response-receipt.json` coinciden con los archivos existentes; los 28 hashes padre del recibo coinciden con la DM de referencia `65d418d1a21b4b4052d41d68554639fc4bc4682566bb780c0d072fd4cfe5eb47`.
- El FDF de referencia y los 28 FDF de respuesta usan SIESTA 5.4.2, mezcla Hamiltoniana, DFTU PotentialShift, método de proyector 2 y el mismo manifold Mn-3d (16 sitios; n=3, l=2, CutoffNorm=0.90, omega=0.05 Bohr). Cada perturbación no nula activa un solo sitio y signo; alpha=0 se identifica por el manifiesto/recibo porque el bloque FDF queda con U=0 en todos los sitios.
- La secuencia ya permite justificar en estas salidas qué población se toma como BARE candidata y cuál como SCREENED convergida. El `.out` no imprime literalmente una bandera “Hxc congelado”; la lectura semántica BARE se apoya en el orden de llamadas auditado para 5.4.2 y la identidad del ejecutable.
- La identidad de la DM padre está declarada y enlazada por el recibo, y cada salida confirma lectura exitosa. Sin embargo, el archivo DM pre-ejecución no se conservó por separado: el `.DM` actual de cada directorio es el artefacto post-run. Por tanto, no se puede volver a calcular retrospectivamente el hash exacto de cada copia leída desde los directorios finales.
- Esto no produce un U aceptado. `analysis-result.json` da `status=FAIL`, `U_Mn_eV=null`; el gate de señal rechaza las tres ventanas (`0.025`, `0.05`, `0.1 eV`) con `signal_unresolved`. La traza confirma selección y control de eventos, no la validez física/numerical de U.

## Secuencia reconstruida

La traza siguiente da intervalos inclusivos de los bloques `hubbard_term: recalculating local occupations`; cada bloque contiene 16 encabezados de átomo y 16 resúmenes `Occupations:`. Los archivos originales son los `.out` y `.fdf` del directorio indicado en `result_set` del JSON adjunto.

| Modo | Ejecución | Sitio | α (eV) | Eventos de población (líneas inclusivas) | SCF/convergencia |
|---|---|---|---:|---|---|
| REF | `00_REFERENCE` | — | 0 | E1 4898–5363; E2 5367–5832; E3 5863–6328; E4 6332–6797; E5 6801–7266; E6 7270–7735; E7 7739–8204; E8 8208–8673; E9 8677–9142; E10 9145–9610; E11 9614–10079; E12 10082–10547; E13 10550–11015; E14 11018–11483; E15 11486–11951; E16 11954–12419; E17 12432–12897 | convergió en 15 iteraciones, línea 12428; E17 es post-convergencia |
| BARE | `A_BARE_m0d025` | MnLR00 | -0.025 | E1 4901–5366; E2 5370–5835; E3 5871–6336 | 1 paso; SCF_NOT_CONV línea 5866 |
| BARE | `A_BARE_m0d050` | MnLR00 | -0.050 | E1 4901–5366; E2 5370–5835; E3 5871–6336 | 1 paso; SCF_NOT_CONV línea 5866 |
| BARE | `A_BARE_m0d100` | MnLR00 | -0.100 | E1 4901–5366; E2 5370–5835; E3 5871–6336 | 1 paso; SCF_NOT_CONV línea 5866 |
| BARE | `A_BARE_p0d000` | MnLR00 | +0.000 | E1 4901–5366; E2 5370–5835; E3 5876–6341 | 1 paso; converge (α=0) |
| BARE | `A_BARE_p0d025` | MnLR00 | +0.025 | E1 4901–5366; E2 5370–5835; E3 5871–6336 | 1 paso; SCF_NOT_CONV línea 5866 |
| BARE | `A_BARE_p0d050` | MnLR00 | +0.050 | E1 4901–5366; E2 5370–5835; E3 5871–6336 | 1 paso; SCF_NOT_CONV línea 5866 |
| BARE | `A_BARE_p0d100` | MnLR00 | +0.100 | E1 4901–5366; E2 5370–5835; E3 5871–6336 | 1 paso; SCF_NOT_CONV línea 5866 |
| SCREENED | `A_SCREENED_m0d025` | MnLR00 | -0.025 | E1 4906–5371; E2 5375–5840; E3 5871–6336; E4 6339–6804; E5 6807–7272; E6 7275–7740; E7 7743–8208; E8 8211–8676; E9 8679–9144; E10 9147–9612; E11 9625–10090 | convergió en 9 pasos, línea 9621; evento final E11 |
| SCREENED | `A_SCREENED_m0d050` | MnLR00 | -0.050 | E1 4906–5371; E2 5375–5840; E3 5871–6336; E4 6339–6804; E5 6807–7272; E6 7275–7740; E7 7743–8208; E8 8211–8676; E9 8679–9144; E10 9147–9612; E11 9615–10080; E12 10083–10548; E13 10551–11016; E14 11029–11494 | convergió en 12 pasos, línea 11025; evento final E14 |
| SCREENED | `A_SCREENED_m0d100` | MnLR00 | -0.100 | E1 4906–5371; E2 5375–5840; E3 5871–6336; E4 6339–6804; E5 6808–7273; E6 7276–7741; E7 7744–8209; E8 8212–8677; E9 8680–9145; E10 9148–9613; E11 9616–10081; E12 10084–10549; E13 10552–11017; E14 11030–11495 | convergió en 12 pasos, línea 11026; evento final E14 |
| SCREENED | `A_SCREENED_p0d000` | MnLR00 | +0.000 | E1 4906–5371; E2 5375–5840; E3 5871–6336; E4 6339–6804; E5 6817–7282 | convergió en 3 pasos, línea 6813; evento final E5 |
| SCREENED | `A_SCREENED_p0d025` | MnLR00 | +0.025 | E1 4906–5371; E2 5375–5840; E3 5871–6336; E4 6339–6804; E5 6807–7272; E6 7275–7740; E7 7743–8208; E8 8211–8676; E9 8679–9144; E10 9157–9622 | convergió en 8 pasos, línea 9153; evento final E10 |
| SCREENED | `A_SCREENED_p0d050` | MnLR00 | +0.050 | E1 4906–5371; E2 5375–5840; E3 5871–6336; E4 6339–6804; E5 6807–7272; E6 7275–7740; E7 7743–8208; E8 8211–8676; E9 8679–9144; E10 9147–9612; E11 9615–10080; E12 10093–10558 | convergió en 10 pasos, línea 10089; evento final E12 |
| SCREENED | `A_SCREENED_p0d100` | MnLR00 | +0.100 | E1 4906–5371; E2 5375–5840; E3 5871–6336; E4 6339–6804; E5 6808–7273; E6 7276–7741; E7 7744–8209; E8 8212–8677; E9 8680–9145; E10 9148–9613; E11 9616–10081; E12 10084–10549; E13 10562–11027 | convergió en 11 pasos, línea 10558; evento final E13 |
| BARE | `B_BARE_m0d025` | MnLR01 | -0.025 | E1 4901–5366; E2 5370–5835; E3 5871–6336 | 1 paso; SCF_NOT_CONV línea 5866 |
| BARE | `B_BARE_m0d050` | MnLR01 | -0.050 | E1 4901–5366; E2 5370–5835; E3 5871–6336 | 1 paso; SCF_NOT_CONV línea 5866 |
| BARE | `B_BARE_m0d100` | MnLR01 | -0.100 | E1 4901–5366; E2 5370–5835; E3 5871–6336 | 1 paso; SCF_NOT_CONV línea 5866 |
| BARE | `B_BARE_p0d000` | MnLR01 | +0.000 | E1 4901–5366; E2 5370–5835; E3 5876–6341 | 1 paso; converge (α=0) |
| BARE | `B_BARE_p0d025` | MnLR01 | +0.025 | E1 4901–5366; E2 5370–5835; E3 5871–6336 | 1 paso; SCF_NOT_CONV línea 5866 |
| BARE | `B_BARE_p0d050` | MnLR01 | +0.050 | E1 4901–5366; E2 5370–5835; E3 5871–6336 | 1 paso; SCF_NOT_CONV línea 5866 |
| BARE | `B_BARE_p0d100` | MnLR01 | +0.100 | E1 4901–5366; E2 5370–5835; E3 5871–6336 | 1 paso; SCF_NOT_CONV línea 5866 |
| SCREENED | `B_SCREENED_m0d025` | MnLR01 | -0.025 | E1 4906–5371; E2 5375–5840; E3 5871–6336; E4 6339–6804; E5 6807–7272; E6 7275–7740; E7 7743–8208; E8 8211–8676; E9 8679–9144; E10 9147–9612; E11 9625–10090 | convergió en 9 pasos, línea 9621; evento final E11 |
| SCREENED | `B_SCREENED_m0d050` | MnLR01 | -0.050 | E1 4906–5371; E2 5375–5840; E3 5871–6336; E4 6339–6804; E5 6807–7272; E6 7275–7740; E7 7743–8208; E8 8211–8676; E9 8679–9144; E10 9147–9612; E11 9615–10080; E12 10083–10548; E13 10551–11016; E14 11029–11494 | convergió en 12 pasos, línea 11025; evento final E14 |
| SCREENED | `B_SCREENED_m0d100` | MnLR01 | -0.100 | E1 4906–5371; E2 5375–5840; E3 5871–6336; E4 6339–6804; E5 6808–7273; E6 7276–7741; E7 7744–8209; E8 8212–8677; E9 8680–9145; E10 9148–9613; E11 9616–10081; E12 10084–10549; E13 10552–11017; E14 11030–11495 | convergió en 12 pasos, línea 11026; evento final E14 |
| SCREENED | `B_SCREENED_p0d000` | MnLR01 | +0.000 | E1 4906–5371; E2 5375–5840; E3 5871–6336; E4 6339–6804; E5 6817–7282 | convergió en 3 pasos, línea 6813; evento final E5 |
| SCREENED | `B_SCREENED_p0d025` | MnLR01 | +0.025 | E1 4906–5371; E2 5375–5840; E3 5871–6336; E4 6339–6804; E5 6807–7272; E6 7275–7740; E7 7743–8208; E8 8211–8676; E9 8679–9144; E10 9157–9622 | convergió en 8 pasos, línea 9153; evento final E10 |
| SCREENED | `B_SCREENED_p0d050` | MnLR01 | +0.050 | E1 4906–5371; E2 5375–5840; E3 5871–6336; E4 6339–6804; E5 6807–7272; E6 7275–7740; E7 7743–8208; E8 8211–8676; E9 8679–9144; E10 9147–9612; E11 9615–10080; E12 10093–10558 | convergió en 10 pasos, línea 10089; evento final E12 |
| SCREENED | `B_SCREENED_p0d100` | MnLR01 | +0.100 | E1 4906–5371; E2 5375–5840; E3 5871–6336; E4 6339–6804; E5 6808–7273; E6 7276–7741; E7 7744–8209; E8 8212–8677; E9 8680–9145; E10 9148–9613; E11 9616–10081; E12 10084–10549; E13 10562–11027 | convergió en 11 pasos, línea 10558; evento final E13 |

## Configuración y comprobaciones

- SHA-256 DM de referencia: `65d418d1a21b4b4052d41d68554639fc4bc4682566bb780c0d072fd4cfe5eb47`.
- Recibo de respuestas: `da0363ebeaa4705063917dfb32c53db8501b02c743ce11167849bac63431b7c6`; job Slurm `333`.
- SHA-256 del ejecutable SIESTA declarado en el recibo: `aaa9a2e45a41b12f3aad52ca4fca7c25b1cc6afd3aff2a0c7fe145b1bd9f18ce`; MPI: `e3a009cd4ab8b41ef23019df3a1388944294b330b7c51ad17be18a0120b36daa`.
- Clave FDF de referencia: `DFTU.PotentialShift true`, `DFTU.FirstIteration false`, `SCF.Mix Hamiltonian`, `SCF.MustConverge T`, `MaxSCFIterations 300`, `DM.UseSaveDM false`.
- Claves FDF BARE: `DFTU.PotentialShift true`, `DFTU.FirstIteration true`, `SCF.Mix Hamiltonian`, `SCF.MustConverge F`, `MaxSCFIterations 1`, `DM.UseSaveDM true`.
- Claves FDF SCREENED: `DFTU.PotentialShift true`, `DFTU.FirstIteration true`, `SCF.Mix Hamiltonian`, `SCF.MustConverge T`, `MaxSCFIterations 300`, `DM.UseSaveDM true`, `SCF.DM.Converge T`, `SCF.H.Converge T`.
- Fuente semántica contrastada: `docs/audits/SIESTA_542_BARE_SOURCE_AUDIT_20260909.md` (commit SIESTA `e486d12067b96ff688179f0496d0ec21b6fae0ab`).
- Detalle máquina-legible por ejecución, hashes de FDF/OUT/DM, marcadores y los 16 sitios de cada evento: el JSON adjunto.
