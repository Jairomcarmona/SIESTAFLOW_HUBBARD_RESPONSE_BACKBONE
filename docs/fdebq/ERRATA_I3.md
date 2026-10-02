R0 — ORDEN DEL TÉRMINO DOMINANTE (sobre la secuencia de pendientes centrales s_k)
- Diferencias d_k = s_{k+1} − s_k, con ruido δ_k = ν_k + ν_{k+1}.
- Para cada terna consecutiva de escalas: razón teórica ρ_p = (a_{k+2}^p − a_{k+1}^p) / (a_{k+1}^p − a_k^p) para p = 1 y p = 2. En V6: ρ_1 = 1 y ρ_2 = 5/3, exactos con fracciones.
- Si |d_k| ≤ δ_k o |d_{k+1}| ≤ δ_{k+1} (deriva no resuelta sobre el ruido): UNRESOLVED.
- Si ambas están resueltas pero con signos opuestos: INCONSISTENT.
- Si no: intervalo observado [lo, hi] con lo = (|d_{k+1}| − δ_{k+1}) / (|d_k| + δ_k) y hi = (|d_{k+1}| + δ_{k+1}) / (|d_k| − δ_k).
  - VERIFIED_2 si ρ_2 ∈ [lo, hi] y ρ_1 ∉ [lo, hi].
  - VERIFIED_1 si ρ_1 ∈ [lo, hi] y ρ_2 ∉ [lo, hi].
  - UNRESOLVED si ambas están dentro.
  - INCONSISTENT solo si hi < ρ₁.
  - UNRESOLVED en cualquier otro caso (incluye quedar entre ρ₁ y ρ₂ o por encima de ρ₂).
    Con datos precisos, los términos de orden superior pueden desplazar la razón observada;
    eso indica comportamiento preasintótico, no inconsistencia. Se usa p_used = 1, conservador.
- Si hay varias ternas, el estado de la familia es el más conservador, con este orden: INCONSISTENT > UNRESOLVED > VERIFIED_1 > VERIFIED_2. Determinista y sin depender de U.

ORDEN USADO Y VARIABLE DE MOMENTOS
- p_used = 2 solo si el estado es VERIFIED_2. Con VERIFIED_1 o UNRESOLVED, p_used = 1 (conservador). Con INCONSISTENT, todos los candidatos del elemento quedan excluidos con código de razón ORDER_INCONSISTENT; si no queda ninguno, el elemento queda NOT_ESTABLISHED.
- R1 y R2 se aplican con la variable u = a^{p_used} en lugar de t = a²:
  - Momento principal: N = Σ w_k a_k^{p_used} (exacto con fracciones).
  - q = N^(k+1) / N^(k).
  - Las diferencias divididas de R2 se toman sobre u.
  Con p_used = 2 esto coincide exactamente con R1/R2 tal como están.
  Con p_used = 1 en V6: central (0.02 vs 0.04) da q = 2; central (0.04 vs 0.06) da q = 3/2.
- Comprobación obligatoria: con n = n0 + χa + k·a|a| y ruido cero, la pendiente central a=0.02 da τ = 0.02|k| y la de a=0.04 da τ = 0.04|k|, iguales al sesgo verdadero (cobertura exacta en el límite sin ruido).

ESTIMADORES QUE ANULAN EL TÉRMINO EN t (M_1 = 0: Richardson, cúbico de mínimos cuadrados y cualquier j0 ≥ 2)
- Solo son candidatos si el estado es VERIFIED_2. En cualquier otro estado se excluyen con el código ORDER_NOT_VERIFIED_FOR_ESTIMATOR. Motivo: no cancelan un término k·a; por ejemplo, Richardson deja un sesgo k·a1·a2/(a1+a2).
- La regla TAIL_UNRESOLVED de R2 sigue aplicándose solo a estos estimadores (j0 ≥ 2), no a los centrales ni a los lineales.

CLASIFICACIÓN
- VERIFIED_1 y UNRESOLVED NO limitan por sí solos el estado final: el candidato sigue elegible con p_used = 1. Registra los códigos de razón ORDER_1_VERIFIED u ORDER_UNRESOLVED_CONSERVATIVE_P1 como diagnóstico.
- El resto de la clasificación (QUALIFIED, REVIEW, etc.) sigue las secciones J y K de la revisión.

TESTS ADICIONALES
1. k·a|a| sin ruido → VERIFIED_1, nunca VERIFIED_2; τ igual al sesgo verdadero; Richardson y cúbico excluidos.
2. b1·a³ sin ruido → VERIFIED_2, p_used = 2.
3. Mezcla b1·a³ + k·a|a| que dé una razón fuera de ambos ρ → INCONSISTENT y exclusión (fail-closed).
4. Deriva por debajo del ruido → UNRESOLVED, p_used = 1, candidato elegible.
5. Cobertura ≥ 99% en 400 ensayos con semilla para el caso no analítico con ruido, sobre los casos aceptados.

LIMITACIÓN CONOCIDA

Con 3 amplitudes, una mezcla de un término no analítico k·a|a| con un término analítico
de signo opuesto puede cancelar en la razón observada y no queda cubierta por este
diagnóstico (cobertura sintética de alrededor de 0.84; con 5 amplitudes, alrededor de
0.92). El protocolo calibrado de fase 2 deberá usar al menos 4 amplitudes.

NOTACIÓN. Escalas t_k = a_k² (eV²), k=1..K crecientes. Pendientes centrales s_k = [n(+a_k) − n(−a_k)] / (2 a_k), con radio de ruido ν_k (cota). Modelo: s_k = χ + Σ_{j≥1} b_j t_k^j. Todo estimador de la familia es E = Σ w_k s_k con Σ w_k = 1. Momentos M_j = Σ w_k t_k^j, calculados con fracciones exactas (fractions.Fraction), sin tolerancias. Sesgo de truncamiento = Σ_j b_j M_j. j0 = primer j con M_j ≠ 0 (comparación exacta). Ruido propagado: ν_E = Σ |w_k| ν_k.

REGLA R1 (hay un estimador vecino de la misma familia). Sean E_k y E_{k+1} consecutivos, con el mismo j0 y M^(k)_{j0}, M^(k+1)_{j0} del mismo signo. Sea q = M^(k+1)_{j0} / M^(k)_{j0}. Si q ≤ 1, el candidato no es utilizable (código de razón explícito). Si q > 1:
  Δ = E_k − E_{k+1}
  τ_k = ( |Δ| + ν_{E_k} + ν_{E_{k+1}} ) / (q − 1)   [ESTIMATE de truncamiento, no BOUND]
Ejemplos exactos en la malla V6 (a = 0.02, 0.04, 0.06; t = 4e-4, 16e-4, 36e-4):
  - central a=0.02 vs 0.04: q = 4 (denominador 3).
  - central a=0.04 vs 0.06: q = 9/4 (denominador 5/4).
  - Richardson(0.02,0.04) vs Richardson(0.04,0.06): M_2 = −t1·t2 y −t2·t3, q = 9 (denominador 8, NO 15 ni r⁴−1 con r=2).
En una malla geométrica de razón r, Richardson da q = r⁴ y reproduce el r⁴−1 antiguo: añade ese caso como test de regresión.

REGLA R2 (sin vecino, o el estimador usa todas las escalas, por ejemplo el lineal por OLS o el cúbico por mínimos cuadrados del protocolo). Sea D_j(ventana) la diferencia dividida de orden j de las s_k sobre j+1 escalas consecutivas, con radio de ruido δ_j propagado con los valores absolutos de sus coeficientes. Entonces:
  τ = |M_{j0}| · max_{ventanas} ( |D_{j0}| + δ_{j0} )   [ESTIMATE]
Tomar el máximo sobre todas las ventanas disponibles es una regla determinista y conservadora; no depende del valor de U ni de ninguna selección.
Si no existen K ≥ j0+2 escalas para contrastar el orden, marca el candidato con el código de razón TAIL_UNRESOLVED (diagnóstico). Un candidato con TAIL_UNRESOLVED NO puede llegar a QUALIFIED; como máximo REVIEW. Decisión explícita mía, reversible por el usuario.
Ejemplos en V6:
  - Lineal OLS de 6 puntos: j0 = 1, M_1 = (0.02⁴+0.04⁴+0.06⁴)/(0.02²+0.04²+0.06²) = 0.0028 eV² exactamente (verifícalo con fracciones). Para n(a) = n0 + χ a + b1 a³ el sesgo es M_1·b1, y la cota NUNCA puede ser cero cuando M_1 ≠ 0.
  - Cúbico del protocolo (mínimos cuadrados con base {a, a³}): M_1 = 0 exacto (reproduce a³), j0 = 2. Calcula y reporta M_2 con fracciones.

TESTS OBLIGATORIOS ADICIONALES para TASK 2:
  1. Datos sintéticos n = n0 + χ a + b1 a³: el lineal OLS debe dar una cota ≥ |M_1·b1| y cubrir la verdad; el cúbico y Richardson deben dar M_1 = 0 exacto.
  2. Richardson V6 con datos sintéticos con b2 conocido: q = 9 y la estimación debe quedar dentro de la tolerancia de la propia fórmula frente al sesgo verdadero.
  3. Regresión con malla geométrica (q = r⁴).
  4. Detección exacta de j0 con fracciones, sin tolerancias numéricas.
  5. Invarianza al orden de entrada y rechazo de datos no finitos, como el resto de tests.

ACLARACIÓN SUPLEMENTARIA — TAIL_UNRESOLVED

Los candidatos con TAIL_UNRESOLVED se conservan visibles en el reporte con su τ y su código de razón, pero NO son admisibles para `best` mientras exista al menos un candidato admisible sin TAIL_UNRESOLVED. Si NO queda ningún candidato admisible sin TAIL_UNRESOLVED, se elige `best` entre los TAIL_UNRESOLVED con la misma regla determinista de siempre, y el resultado del elemento queda como máximo en REVIEW, con el código TAIL_UNRESOLVED. Añadir candidatos TAIL_UNRESOLVED nunca puede empeorar el estado de un elemento que sin ellos sería QUALIFIED: añade un test de esta monotonicidad.
