Reanudas la FASE 2 en C:\Users\Jairo\work\hubbardflow. Tu reporte fue correcto: los bloqueos eran huecos de la especificación. Yo (autor) los resuelvo así; guarda este texto íntegro como `docs/fdebq/AMENDMENTS_2.md` en el primer commit y rige sobre CODEX_TASKS_PHASE2.md.

PRINCIPIO GENERAL: ante cualquier hueco que no cubra este texto, elige la opción más conservadora (más perturbaciones, o un estado más bajo: REVIEW / NOT_ESTABLISHED), nunca la que suba un estado, y anótalo en la nota de la tarea como "decisión del implementador (conservadora)". Solo te detienes si la única salida posible sube un estado o toca la certificación existente.

BASE: continúa desde la punta de `fdebq/task19-product-cli`. No reescribas historia: crea ramas nuevas apiladas `fdebq/r2-taskNN-<slug>` (NN = 10, 12, 13, 14, 16, 17, 18, 19, y 15 al final) y al terminar cada una actualiza `docs/fdebq/BLOCKERS.md` marcando el bloqueo como RESUELTO con el commit. Orden: 10, 12, 13, 14, 16, 17, 18, 19, 15. Mismas reglas de siempre: V6 GATE OK antes de cada commit, ruff, format, mypy, pytest, nota por tarea en C:\Users\Jairo\work\fdebq_pr_notes, push sin PR, verificador independiente, banderas apagadas por defecto, no ejecutar SIESTA, sin debilitar tests ni inventar umbrales.

D1. TASK 10, evidencia de referencia. Una referencia es admisible SOLO si UNA salida de SIESTA, junto con su FDF de entrada (ambas ligadas por sha256), contiene: terminación normal; momentos Mulliken finales por átomo si el cálculo es polarizado (si es `Spin non-polarized` verificado, no se exigen momentos); y matrices de ocupación locales. Nunca se combinan datos de salidas distintas. Si falta algo: `REFERENCE_NOT_ADMISSIBLE`, estrategia `ALL_SUBSPACES`, motivo `EVIDENCE_INCOMPLETE`. Una salida con un sitio perturbado (α≠0) no es una referencia.
 Goldens de TASK 10: (a) CoO, NiO y FeO de `examples/tmo_campaigns` y las salidas de `validation_observables_v6`: golden NEGATIVO = REFERENCE_NOT_ADMISSIBLE → ALL_SUBSPACES con el motivo exacto (esto es un resultado válido y es el que se espera). (b) Cu3N (`examples/tmo_campaigns/Cu3N_ref.out`, no polarizado): golden POSITIVO por traslaciones. (c) MnO v3r2: busca en `campaigns/mno_afmii_strict_lr_v3r2` una salida de referencia sin perturbar (α=0, DM padre) que tenga a la vez ocupaciones locales y Mulliken; si existe, golden positivo (16→2 con banderas apagadas, 16→1 con ε=−1 solo como candidato); si no existe, NO uses salidas por-α como referencia: documenta la limitación y cubre MnO con el toy sintético de TASK 9. Se eliminan los goldens "CoO 2→1" y "MnO 16→1" como resultados automáticos.

D2. TASK 10, regla de ahorro. `would_reduce_to` (conteo de representantes candidatos) se informa siempre. La estrategia efectiva de una clase es reducida solo si, con sombra obligatoria, (representantes + sombras) < miembros de la clase; si no ahorra corridas, la clase se perturba explícita con motivo `NO_SAVING`. Las órbitas de tamaño 1 no se reducen. Ejemplo: CoO con ε=−1 habilitado es candidato 2→1 pero se perturba completo por NO_SAVING. La cláusula "sistema pequeño" de §H significa exactamente esto, no otra cosa.

D3. TASK 16, agregación por columna. Todas las filas I de una columna (J, modo) comparten las mismas corridas y por tanto el mismo conjunto de amplitudes. El estimador de `ColumnPlan` se elige así: entre los candidatos de la familia cerrada (TASK 2) que sean admisibles en TODAS las filas observadas, el que minimiza el máximo sobre I del presupuesto total absoluto (e/eV); desempate determinista: menor amplitud máxima, luego orden fijo de familia. Si ninguno es admisible en todas las filas: la columna queda no resuelta en esa ronda y se pasa a pedir más amplitudes de la red; sin candidatos nuevos → NOT_ESTABLISHED. La producción usa el estimador del ColumnPlan para todas las filas (no se elige por elemento); el mejor por fila queda solo como diagnóstico en el reporte.
 Regla de ronda: refinar primero la columna con mayor contribución de primer orden a la cota de U (pesos |A_KI A_JK| y |𝒜_KI 𝒜_JK| calculados con las matrices estimadas, que no son U); añadir la siguiente amplitud de la red permitida por la regla monótona de exclusión; parar con QUALIFIED si pasa la compuerta D4, con REVIEW si se agota el máximo de rondas del protocolo, con NOT_ESTABLISHED si no hay más candidatos.

D4. TASK 16, compuerta en el espacio de U. NO se acota O(β²) analíticamente. La aceptación es: (i) β⁰ < 1 y β < 1 (§I.7); (ii) U evaluada con las rutinas existentes de `domain/u_certification.py` (importar, NO modificar) sobre un `MatrixBox` ampliado al presupuesto completo por elemento (§I.8); el semiancho del intervalo de U_KK debe ser ≤ τ_U (τ_U la da el usuario, sin valor por defecto). Etiqueta del resultado: "calificación condicional al modelo de error", nunca "certificado". Si el API de MatrixBox no admite radios por elemento, detente y repórtalo (no lo modifiques).
 Sin componente SCF ESTIMATE, el modo calibrado no puede pasar de REVIEW.

D5. TASK 17, escalera SCF. Para cada columna y amplitud a de la escalera: Δ_L(a) = n_L(+a) − n_L(−a); η1 = |Δ_L0 − Δ_L1|, η2 = |Δ_L1 − Δ_L2|. R_i = suma de los semianchos de impresión de los cuatro valores impresos que entran en η_i. Cotas: η_i⁺ = η_i + R_i, η_i⁻ = max(η_i − R_i, 0).
 (a) η1⁻ > 0 (resuelta): ρ̂ = η2⁺/η1⁻. Si ρ̂ ≤ ρ_max: SCF_ESTIMATE(a) = θ·η1⁺/(1 − ρ̂). Si ρ̂ > ρ_max: NOISE_FLOOR_NOT_ESTABLISHED (columna limitada a REVIEW).
 (b) η1⁻ = 0 (diferencia no resuelta, incluye η1 = η2 = 0): ρ̂ = ρ_max (el valor declarado del protocolo) y SCF_ESTIMATE(a) = θ·η1⁺/(1 − ρ_max), estado SCF_UNDER_RESOLVED; el estado de la decisión se limita a REVIEW.
 θ y ρ_max vienen del protocolo (sin valores por defecto en código; en tests, valores explícitos de prueba).
 Separación absoluto/relativo con dos amplitudes medidas a_s < a_l (cada una con η⁺ y g = ½|Δ| como magnitud de respuesta): η_rel = max(0, (η_l − η_s)/(g_l − g_s)) si g_l − g_s > 0, y η_abs = max(0, η_s − η_rel·g_s); si g_l − g_s ≤ 0, todo es absoluto: η_abs = max(η_s, η_l), η_rel = 0. La envolvente η(a) = η_abs + η_rel·g(a) solo vale en [a_s, a_l]: un candidato con amplitudes fuera de ese intervalo es inadmisible con motivo SCF_ENVELOPE_NOT_COVERED (no se extrapola). Mapeo a TASK 2 sin cambiar su API: eps_abs_e (por punto) = η_abs⁺-escalado/(2·(1−ρ̂))·θ y eps_rel análogo, de modo que la incertidumbre de la pendiente sea ε_Δ/(2a), donde ε_Δ es el error de Δ (cota por suma, no RSS). Estas cantidades son ESTIMATE, nunca BOUND. Sin réplicas en α=0 como suelo de ruido.

D6. TASK 15. Se queda preparada: `STAGED_PENDING_GENERATED_IDENTITY` es el estado correcto. Añade `tools/hubbardflow_verify_split_identity.py` que, dado el directorio de una corrida real de SIESTA con las etiquetas alias, compara por sha256 los `.ion` generados de cada alias con el de la etiqueta original y emite el veredicto (la corrida real la hace el usuario; documéntalo en el runbook). No hace falta una prueba positiva con una FDF real del repo: basta la sintética más las pruebas negativas con archivos reales. Integra `auto_split_species` en la admisión de campaña cuando TASK 13 exista, siempre apagada por defecto.

D7. TASK 18. Impleméntalo extremo a extremo con las banderas apagadas por defecto. Egg-box: no se añade tolerancia ni parámetro nuevo; las rotaciones (EXACT_IN_CONTINUUM_ONLY) tienen sombra obligatoria comparada con los presupuestos de TASK 14, así que un efecto egg-box se manifiesta como fallo de sombra y expande la clase. El plan registra `egg_box_quantification = NOT_QUANTIFIED` hasta que el usuario aporte la validación V2 específica. VALIDATION_GATES.md documenta qué resultados (V2, V3, V4, con digests) habilitan cada bandera; no fabriques resultados.

D8. TASK 12, 13, 14, 19. Sin cambios de especificación, salvo que ahora sí son implementables una vez D1 y D2 den una `CoverageQualification` completa. TASK 19: si alguna dependencia sigue sin cumplirse, entrega los comandos `plan` y `run`/`submit` hasta donde el contrato permita, con estado NOT_ESTABLISHED explícito, en lugar de omitirlos.

CIERRE: actualiza PHASE2_SUMMARY.md (tabla tarea, rama, commit, pruebas, estado, bloqueos RESUELTOS/ABIERTOS) y responde con esa tabla. No hagas merge a la rama base.
## Phase 2 close

### §4. Decisiones del autor (D9–D12)

- **D9 (SCF ladder).** Review §E.2 is authoritative over TASK 17.
  - Levels harden both the DM and the H tolerance, and each level has its own α=0 reference and
    parent DM.
  - For BARE, the level difference comes only from the parent DM (`MaxSCFIterations 1`). The D5
    formulas apply with three parent levels.
  - This extends §E.2, which describes BARE with two levels as an indicator. The third level gives
    the contraction check at the cost of two cheap BARE runs per amplitude.
- **D10 (species identity).** The verdict is width-preserving label normalization plus a diff
  confined to the label lines, not raw sha256 equality. The real pair FeLR0/FeLR1 is the positive
  control.
- **D11 (frozen Phase-2 plans).**
  - No Phase-2 campaign has run with SIESTA (checked in 0.2.5).
  - Plans frozen under `campaign-planner-v1` are not migrated: resume fails with
    `PLANNER_VERSION_CHANGED`, and the user re-initializes.
  - Plan content must not depend on optional packages.
- **D12 (product execution).**
  - A plan with no reduction, a fixed explicit grid and no adaptive policy is executable through
    the legacy runner. Its scientific content is the legacy V6-validated path.
  - I.5 and pilot reuse are requirements only for reduced or calibrated plans.

### Phase 2 close — resoluciones R1–R4

- **R1 (20.2).** “Is read” means “recognized.” `Chemical_Species_Label` is recognized and rejected with `NONCANONICAL_MANAGED_LABEL`, with a message that gives the canonical spelling `ChemicalSpeciesLabel`. For the positive read test, use a label outside the managed-label set recorded in the phase-close log, and record the selected label there. The rest of 20.2 is unchanged.
- **R2 (20.4).** Editing `tests/unit/test_split_generated_identity.py::test_real_archive_label_only_difference_is_never_a_positive` is authorized because it encodes the D6 rule replaced by D10. Rename it to `test_real_archive_label_only_difference_matches` and expect `MATCH` for the real `FeLR0`/`FeLR1` pair.
- **R3 (20.5).** (a) Editing `tests/unit/test_symmetry_operations.py::test_f8_records_incommensurate_translation_without_excluding_candidate` is authorized. With translation t=1/4 and `InitMesh=(3,3,3)`, retain the operation as a candidate and classify it `EXACT_IN_CONTINUUM_ONLY`, not `EXACT_TRANSLATION`. Keep the test name. (b) Remove `spglib` from planning as specified. The internal enumeration's missed rotation candidates for non-orthogonal cells can only reduce savings: rotations default off and are never reduced in production without V2 validation. Record the known Phase 3 limitation as “enumeración de rotaciones independiente de spglib para redes no ortogonales” in `BLOCKERS.md`; do not classify it as `RISK_UNCOVERED`. Verify and log that translations do not lose candidates; stop if one does.
- **R4 (20.9).** The only compatible archive chain is `campaigns/nio_pbe_p5_20260928/` (`campaign.v2.json`, `lr-config.json`, and node evidence). Redefine 20.9 to initialize, with current code and `coverage=DISABLED`, from the reference FDF and lr-config located via that campaign manifest. Compare the `(site, atom, mode, alpha)` set with the manifest and node evidence; also compare materialized-input hashes if node evidence records them. Record CoO, MnO, and Cu3N as `NOT_COVERED`; their equivalence is covered by the TASK 13 golden and TASK 21 test. If NiO P5 does not reproduce exactly, do not modify anything; stop and report the difference.
