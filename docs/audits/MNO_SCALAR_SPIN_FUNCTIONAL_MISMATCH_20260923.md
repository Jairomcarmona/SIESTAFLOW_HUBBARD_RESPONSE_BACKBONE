# MnO: auditoría de la correspondencia entre respuesta lineal y funcional DFT+U

Fecha: 2026-09-23. Auditoría estática del código, la fuente SIESTA 5.4.2 y los resultados ya guardados. No se ejecutó SIESTA ni se inició una campaña.

## Hallazgo principal: la U calculada no es, en general, el U−J aplicado

`tools/run_mno_afmii_response_quantized_v1.py` selecciona exclusivamente `precision[atom.atom_index].total` en `_occupations` (líneas 142–160). A partir de ese total $n_I=n_{I\uparrow}+n_{I\downarrow}$, ajusta las matrices de respuesta BARE y SCREENED, y `src/siestaflow_hubbard/domain/quantized_response.py` (líneas 93–111) calcula

\[
U_I^{\rm carga}=\left[\chi_0^{-1}-\chi^{-1}\right]_{II}.
\]

La fórmula y su evaluación matricial son correctas **para la respuesta escalar de carga definida así**. La evidencia actual da 11.5320557 eV; la discrepancia BARE/SCREENED se encuentra en las ocupaciones nativas, no aparece por un cambio accidental de signo o por la inversión.

Sin embargo, los FDF de validación (por ejemplo `campaigns/mno_afmii_strict_lr_v3r2/results/u1153_minimal_afmii_relaxation/siesta.fdf`, líneas 49–57) pasan `11.53 0.00` a `DFTU.Proj` con `DFTU.PotentialShift false`. En `third_party/siesta-5.4.2-source-audit/Src/dftu.F` (líneas 682–713), la rama normal usa explícitamente `Ueff = U - J` y construye un potencial de tipo Dudarev que depende de la matriz de ocupación de *cada espín*. Ese funcional tiene términos cuadráticos intraespín, sin un término correctivo mixto $n_\uparrow n_\downarrow$. El parámetro obtenido al perturbar y observar ambos espines juntos sí incorpora, en general, la respuesta cruzada entre espines. Por ello no está justificada la identificación automática $U^{\rm carga}=U_{\rm eff}^{\rm Dudarev}$ para MnO magnético.

Linscott et al., *Phys. Rev. B* **98**, 235157 (2018), [texto completo](https://harvest.aps.org/v2/journals/articles/10.1103/PhysRevB.98.235157/fulltext), sección II B y ecuaciones 27–28, demuestran la equivalencia entre la respuesta escalar y una combinación espín-resuelta que incluye interacciones entre espines. En la página 5 explican expresamente que ese resultado **no corresponde** a la interacción de un solo espín $U_{\rm eff}=U-J$ de la corrección convencional. Es un resultado metodológico publicado, no una conjetura basada en que el número parezca alto. El propio artículo muestra, para MnO con otro código, proyectores y definición de $\chi_0$, que distintos tratamientos del espín dan valores diferentes; sus números no son una referencia numérica directamente intercambiable con esta campaña.

## Consecuencia verificable para el software

La salida `REPORTABLE_NUMERICAL_U_INTERVAL` del análisis certifica como máximo un intervalo de redondeo de la **U escalar de carga**. No certifica su equivalencia al coeficiente del funcional usado después, ni predicciones físicas de MnO. Los `.out` guardan ocupaciones up/down, pero la campaña aplicó el mismo desplazamiento a ambos espines; con esas perturbaciones no se determina por separado la matriz completa \(\partial n_{I\sigma}/\partial\alpha_{J\sigma'}\). Ajustar de nuevo los mismos datos o reducir el error de redondeo no resuelve esa identificación.

Esta falla de correspondencia puede explicar que un U numéricamente estable no reproduzca observables. **No demuestra por sí sola que 11.53 eV sea una U escalar incorrecta ni cuantifica cuánto de la anomalía física proviene de este punto**. La sensibilidad documentada al proyector y las demás aproximaciones del material permanecen como causas separadas. No se debe sustituir 11.53 por otro valor sin definir primero qué parámetro pretende recibir el funcional aplicado.

## Comprobación adicional sobre las salidas existentes

Se extrajeron los totales impresos por espín de los mismos eventos ya seleccionados y se ajustó cada componente contra los siete alphas guardados. Para el sitio A, las pendientes BARE up/down son −0.063203/−0.083502 electrones por eV; las SCREENED son −0.018350/−0.035788. El sitio B intercambia esas dos componentes por la orientación AFM. Las pendientes de ambos espines tienen el mismo signo, así que **no hay cancelación entre espines que explique artificialmente el valor alto de 11.53 eV**. La respuesta SCREENED total es aproximadamente −0.05414 frente a −0.14670 BARE; esa reducción es la fuente numérica inmediata de U alta para este modelo. Esta comprobación sólo relee las salidas existentes.

La regla correctiva de producto es nombrar el resultado `U_scalar_charge`, conservar su trazabilidad y bloquear su promoción automática a `Ueff_Dudarev` en cálculos espín-polarizados salvo que exista una derivación y validación explícitas de esa correspondencia. Cambiar simplemente el número de U o el campo J del FDF no repara el problema: la implementación examinada usa la diferencia `U-J` para el mismo término de Dudarev.
