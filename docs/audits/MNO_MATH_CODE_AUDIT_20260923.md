# Auditoría focalizada de matemática y valores fijos: MnO

Fecha: 2026-09-23. Se releen las 28 salidas BARE/SCREENED y siete valores de α ya archivados en `campaigns/mno_afmii_strict_lr_v3r2/results/response-matrix-foreground-recovery-v4/`. No se ejecutó SIESTA ni se modificaron entradas congeladas.

## ¿El 11.532 eV se fabrica en la inversión?

No se halló evidencia de ello. La reconstrucción independiente a partir de los totales de ocupación impresos y los SHA-256 del recibo da los siguientes controles (eV):

| Operación sobre las mismas respuestas | U medio |
|---|---:|
| Matrices 16×16 crudas, inversión directa | 11.532055662576 |
| Matrices 16×16 simetrizadas, inversión directa (resultado publicado) | 11.532055666425 |
| Sólo diagonales de ambas matrices, inversión directa | 11.654375296484 |
| Trazas antiguas redondeadas en lugar del total impreso nativo | 11.531189060530 |

La simetrización cambia U en ~3.85×10⁻⁹ eV; la contribución total de términos fuera de diagonal es −0.12232 eV; y la corrección de precisión de ocupación cambia U en +0.00087 eV. Las condiciones espectrales de las matrices crudas son aproximadamente 2.005 (BARE) y 1.254 (SCREENED). Los ajustes de ±0.025, ±0.05 y ±0.10 eV dan 11.5370, 11.5327 y 11.5321 eV. Por tanto, ni inversión mal condicionada, ni simetrización, ni el redondeo antiguo explican un exceso de varios eV. El factor dos interno de `dftu.F` en la rama `DFTU.PotentialShift=true` multiplica `Ueff` por dos para cancelar el prefactor `0.5` del potencial de desplazamiento; con J=0 la entrada α produce un desplazamiento α, no 2α.

La reconstrucción 16×16 desde representantes A/B es una hipótesis de traslación codificada en `campaigns/mno_afmii_strict_lr_v3r2/scripts/lru_core.py:176`; aquí se verifica el impacto de sus términos fuera de diagonal, no la simetría física de todas las columnas no medidas. Su eliminación no reduce U: lo eleva a 11.654 eV.

## Defecto matemático en la entrega de U al funcional

`tools/run_mno_afmii_response_quantized_v1.py` lee `printed_totals_e`, suma los espines y construye una susceptibilidad de carga. `src/siestaflow_hubbard/domain/quantized_response.py:93` evalúa `diag(inv(χ₀) − inv(χ))`; 11.532 eV es, por construcción, **U escalar de carga**. `campaigns/mno_afmii_strict_lr_v3r2/audits/uncertainty_assurance_20260923/prepare_physical_convergence.py:15` fija `U_CENTRAL = 11.5321` y la línea 40 lo introduce sin conversión en el primer registro `DFTU.Proj` de los FDF físicos. Con `DFTU.PotentialShift=false`, `third_party/siesta-5.4.2-source-audit/Src/dftu.F:682-713` interpreta esa entrada como `Ueff = U-J` dentro de un potencial Dudarev por espín.

Linscott et al., *Physical Review B* **98**, 235157 (2018), sec. II B, [texto completo](https://harvest.aps.org/v2/journals/articles/10.1103/PhysRevB.98.235157/fulltext), muestran que la U de respuesta escalar combina interacciones entre espines y **no corresponde en general** al parámetro intraespín `Ueff=U−J`. Esto hace injustificada la asignación directa usada en los FDF físicos, pero no demuestra que el 11.532 eV escalar esté calculado incorrectamente ni determina un Ueff sustituto. Los datos actuales aplican el mismo α a ambos espines y sólo identifican sumas de columnas de la respuesta espín-resuelta; no permiten reconstruir la matriz completa de perturbaciones independientes por espín. La tabla I de ese artículo informa 5.44 eV para Mn de MnO bajo su propio método; no es una referencia numérica intercambiable porque emplea otra definición de χ₀, código y proyectores. La cifra ~10.88 eV del artículo pertenece al **oxígeno** de MnO (tabla II), no al Mn.

Existe además una etiqueta engañosa en `src/siestaflow_hubbard/reporting/evidence_exporter.py:30,64`, que llama `U_eff` a la inversión de susceptibilidades sin demostrar esa correspondencia. En `src/siestaflow_hubbard/siesta_backend/fdf_builder.py:105-109,169-173` hay valores por defecto `species="Mn", n=3, l=2, rc=3.0, omega=0.05` para materializar respuestas genéricas. Son supuestos Mn 3d codificados que no deben aplicarse silenciosamente a otros materiales; no originaron la U de esta campaña, que proporcionó su propio proyector.

Otra regla fija del núcleo genérico, `src/siestaflow_hubbard/domain/matrix_lr.py:208-219`, define la ventana interna como `|α|≤0.011 eV` y, si no hay dos puntos, sustituye el ajuste interno por el ajuste completo. En una malla como la de MnO (menor |α| distinto de cero: 0.025 eV) esto hace que el diagnóstico interno coincida consigo mismo y no pueda detectar dependencia de ventana. La campaña auditada usó su analizador propio con ventanas de 0.025/0.05/0.10 eV, así que esta falla **no generó** su 11.532 eV; sí es un defecto de generalidad a corregir en el núcleo.

Control mínimo ejecutado en memoria: con las siete α de MnO y una ocupación artificial `n(α)=1−0.05α−α³`, el núcleo informa pendiente completa e «interna» idénticas, −0.058125 e/eV, mientras que los tres puntos centrales reales dan −0.050625 e/eV. Se ejecutó sólo este control algebraico, sin SIESTA.

## Corrección delimitada

Separar explícitamente el tipo `U_scalar_charge` del parámetro `Ueff_Dudarev` en resultado, reporte y entrega a FDF. Bloquear la transferencia automática del primero al segundo en cálculos espín-polarizados hasta disponer de una derivación compatible o de una respuesta espín-resuelta con perturbaciones independientes y el funcional apropiado. No sustituir 11.532 por 5.44 eV ni por un valor ajustado: los datos archivados no identifican ese parámetro.
