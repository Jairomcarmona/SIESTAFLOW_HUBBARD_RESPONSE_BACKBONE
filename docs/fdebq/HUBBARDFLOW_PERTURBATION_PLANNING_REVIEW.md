# HubbardFlow: revisión independiente y diseño de la planificación de perturbaciones de extremo a extremo

**Alcance.** Este informe responde a `CLAUDE_OPUS_HUBBARDFLOW_FULL_PERTURBATION_AUTOMATION_REVIEW.md` (secciones A–Y). Cubre las tres decisiones científicas que separan una FDF autorizada de una campaña de producción:

1. qué subespacios correlacionados existen (descubrimiento);
2. cuáles y cuántos deben perturbarse de forma independiente (cobertura);
3. con qué amplitudes α (calibración).

**Relación con la revisión anterior.** `docs/fdebq/HUBBARDFLOW_FDRC_INDEPENDENT_REVIEW.md` y `docs/fdebq/ERRATA_I3.md` especificaron la calibración de α (FD-EBQ). Este informe **no la repite**. La resume en las secciones I–M, la acopla a la cobertura (sección N) y deja ambas dentro de un único contrato, `ResolvedPerturbationPlan` (sección O).

**Rama auditada:** `codex/hubbardflow-rename` @ `241d009` (contiene `3c1398b` más el PR #5, que solo añade configuración y documentos). El baseline congelado `scientific-v6-final` (`45cb53c`) se usó solo como lectura.

**Material reproducible** (fuera del repositorio, sin escribir en él):
- `coverage_review_checks.py`: comprueba la ley de reconstrucción en campañas archivadas.
- `toy_symmetry_ring.py`: modelo de campo medio con contraejemplos.

Todos los números de este informe salen de esos scripts o de los archivos citados. Son datos de desarrollo, no validación.

---

## A. Reconstrucción del problema completo

Para subespacios correlacionados \(I,J\) y modo \(m\in\{\mathrm{BARE},\mathrm{SCREENED}\}\):

\[
\chi^{(m)}_{IJ}=\left.\frac{\partial n^{(m)}_I}{\partial \alpha_J}\right|_{\alpha=0},\qquad U=(\chi^{0})^{-1}-\chi^{-1}.
\]

Una perturbación del subespacio \(J\) produce la columna completa \(\chi^{(m)}_{:J}\). El costo dominante es aproximadamente \(N_{\rm runs}\approx 2\,P\,A\) por modo (dos signos, \(P\) blancos, \(A\) amplitudes), más referencias y controles. El problema tiene dos decisiones acopladas y una restricción:

1. **Cobertura.** Encontrar el conjunto mínimo de blancos \(\mathcal{R}\subseteq\mathcal{S}\) (con \(\mathcal{S}\) el inventario de subespacios correlacionados) tal que **todas** las columnas de \(\chi^0\) y \(\chi\) se obtengan sin aproximación: o calculadas, o reconstruidas exactamente desde las calculadas.
2. **Amplitudes.** Para cada columna calculada y cada modo, elegir una ventana de α y un estimador cuya incertidumbre de pendiente esté acotada o estimada, y cuyo efecto sobre \(U\) quede por debajo de una tolerancia declarada por el usuario.
3. **Restricción.** Ninguna de las dos decisiones puede usar el valor de \(U\), su estabilidad, el número de condición ni el acuerdo con la literatura. Cuando la evidencia no alcanza, el resultado es explícito (`NOT_ESTABLISHED`, `REVIEW`, `AMBIGUOUS`) y el respaldo es perturbar todo.

La respuesta corta: \(P\) es el número de **órbitas** de los subespacios correlacionados bajo un grupo \(G_{\rm resp}\) de operaciones que **demostrablemente** dejan invariante el problema de respuesta. Las secciones D–G definen ese grupo. Si \(G_{\rm resp}\) no puede establecerse, \(G_{\rm resp}=\{e\}\) y \(P=|\mathcal{S}|\).

---

## B. Auditoría de la implementación actual (`codex/hubbardflow-rename`)

| Pieza | Archivo | Qué hace hoy | Qué no hace o qué falla |
|---|---|---|---|
| Inventario de sitios en producción | `execution/campaign_v2.py` (`validate_reference_fdf`, `validate_lr_config`, `resolve_fdf_includes`) | Resuelve `%include`. Lee `ChemicalSpeciesLabel` y `DFTU.Proj` y exige que las **etiquetas DFTU sean únicas**. El `lr-config` del usuario debe **enumerar todos los sitios DFTU** con su `atom_index` y la malla `alpha_grid_ev`, que debe ser simétrica. | No descubre nada. `orbit_id` es solo metadato. No hay reducción en producción. **No analiza `AtomicCoordinatesAndAtomicSpecies`**, así que no verifica que cada etiqueta DFTU la use exactamente un átomo ni que el `atom_index` declarado tenga esa especie. |
| Detección de simetría | `src/symmetry_reduction_proposal.py` (`detect_symmetry`) | Prueba solo rotaciones que son **permutaciones con signo de los ejes de la red** y deduce traslaciones mapeando el átomo 0. Exige especie+etiqueta iguales. Compara momentos como vectores axiales (\(\det R\,R\,m\)). Marca ambigüedad si hay más de un candidato. | No incluye inversión temporal ni volteo de espín explícito. Por la vía actual (adaptador, solo traslaciones) **rechaza siempre el intercambio de subredes AFM**. Con capas escalares declaradas, una rotación C2⊥z invertiría el \(S_z\) almacenado como (0,0,Sz) y actuaría como volteo **según la elección arbitraria del eje z**: es un artefacto de tratar el espín colineal como vector axial (ver E.4). Omite operaciones que no son permutaciones con signo (celdas romboédricas o hexagonales); eso es conservador, no incorrecto. La tolerancia magnética fija de \(10^{-6}\,\mu_B\) es menor que la dispersión SCF de los momentos de Mulliken. |
| Puente FDF | `siesta_backend/fdf_symmetry_adapter.py` | Solo admite `AtomicCoordinatesFormat Fractional`, `LatticeConstant` y `LatticeVectors`. La clase de equivalencia es `Z + (n,l,U,J,rc,ω)` del `DFTU.Proj`, sin depender de la etiqueta. Fija `complete_l_shell=False` y `rotationally_invariant=False`, de modo que **solo puede autorizar traslaciones**. | Solo calcula el hash de la FDF: no compara el contenido de pseudopotencial, `PAO.Basis` ni `.ion` entre etiquetas. No resuelve `%include` (a diferencia de `campaign_v2`). |
| Evidencia magnética | `siesta_backend/reference_magnetic_evidence.py` | Momentos colineales finales de Mulliken, ligados por hash a la FDF y la salida. No usa `DM.InitSpin`. | No toma las matrices de ocupación locales, así que no detecta un orden orbital que rompa la simetría. |
| Plan de reducción | `domain/symmetry_reduction.py` | Agrupa órbitas, elige representante y sombra, genera specs ±α BARE/SCREENED y hace fallback explícito a todos los sitios. Autoriza por órbita y expande las órbitas rechazadas. Es un buen esqueleto de máquina de estados. | Política con **literales fijos** (`occupation_max_abs_e=2e-5`, `response_max_abs_e_per_ev=5e-5`, `response_max_relative_l2=1e-3`) que viola la regla 6 de `AGENTS.md` y no escala con α. Usa un solo α. No está conectado a `campaign_v2` ni al runner. |
| Materialización | `siesta_backend/symmetry_materializer.py` | Reescribe la línea de desplazamiento de **todos** los registros de `DFTU.Proj`: α en el sitio blanco (con 4 decimales) y cero en los demás, sin tocar las otras líneas. Exige método 2 y `PotentialShift`. | Correcto como base: equivale a "solo el blanco" porque la referencia exige desplazamiento cero. |
| División de especies | `siesta_backend/fdf_builder.py::materialize_split_species_fdf` | Divide una etiqueta compartida en `X0..XN-1` reescribiendo `ChemicalSpeciesLabel`, `NumberOfSpecies` y coordenadas (conserva `DM.InitSpin`). Hoy solo la usan scripts fuera del runner de producción. | **No duplica `PAO.Basis`, la entrada `DFTU.Proj` ni el pseudopotencial por etiqueta**; la entrada DFTU de la etiqueta original queda huérfana. Si la FDF base define una base explícita por etiqueta, las nuevas especies cambiarían de física en silencio (ver la sección S). |
| Observable | `siesta_backend/event_parser.py`, `occupation_precision.py` | \(n_I=\mathrm{tr}\) de la matriz de ocupación sobre \(m\) y espín. El lector de la diagonal suma el semiancho de redondeo de cada token y verifica que esa suma coincida con `trace_total`. | Correcto: es un observable escalar e invariante ante el volteo de espín. **Dos salvedades:** el rechazo de no colineal/SOC es solo implícito (`UnsupportedSpinFormat` salta por el número de campos del resumen `Occupations:`; no hay una puerta explícita en `campaign_v2`), y para resúmenes polarizados de 3 tokens se usa solo el semipaso del token total. |
| Perturbación | `symmetry_materializer.py`, `response_grid_semantics.py` | Un único desplazamiento de potencial no nulo, aplicado a un sitio, en el canal U, con `DFTU.PotentialShift true`. Es independiente del espín. | Correcto. |
| Selección de α y parada | `domain/adaptive_alpha_control.py::decide_round`, `alpha_selection.py`, `adaptive_alpha.py` | Rondas adaptativas que paran cuando U se estabiliza (`STOP_STABLE`). | Es circular respecto a U; queda reemplazado por FD-EBQ (revisión anterior, sección I). |
| Reconstrucción histórica | `campaigns/mno_afmii_strict_lr_v3r2/scripts/lru_core.py` (`translated_column`, `reconstruct`) | MnO de 16 Mn: perturbó a dos representantes (A y B) y reconstruyó la matriz por traslaciones. | Es lógica *ad hoc* de una campaña, no está en el paquete. Sí es una evidencia retrospectiva valiosa (sección D.4). |

**Conclusión de la auditoría.** Hay piezas sólidas: órbitas con sombra y fallback, una materialización segura, un observable escalar y una perturbación independiente del espín. Pero el sistema **no** puede hoy decidir la cobertura de forma automática y defendible:

- la detección no conoce el volteo de espín;
- no verifica que el estado de referencia sea simétrico;
- no verifica que dos etiquetas tengan física idéntica;
- usa tolerancias literales;
- y no está conectada a producción.

---

## C. Descubrimiento de subespacios correlacionados

### C.1 Qué aporta la FDF y qué no

| Información | Fuente | ¿Basta la FDF? |
|---|---|---|
| Red y posiciones | `LatticeVectors`/`LatticeConstant`, `AtomicCoordinates*` | Sí, dentro de un subconjunto sintáctico soportado. |
| Átomo → etiqueta → Z | `ChemicalSpeciesLabel`, columna de especie | Sí. |
| Etiqueta → subespacio correlacionado | `DFTU.Proj` (método 2: `n l`, `U J`, `rc ω`, λ opcional) | Sí. |
| **Identidad física** de dos etiquetas | pseudopotencial (digest del PSML), `PAO.Basis` y opciones de base, `.ion` generado | **Solo junto con los archivos de entrada**; la FDF sola no basta. |
| Estado magnético | salida SCF de referencia (Mulliken final) | **No.** `DM.InitSpin` es una semilla, no evidencia. |
| Estado orbital (orden orbital, Jahn–Teller) | matrices de ocupación locales de la referencia | **No.** |
| Mallas numéricas efectivas | salida (`InitMesh`, malla k efectiva) | Parcialmente; la malla real la reporta la salida. |

Conclusión: el inventario **estático** sale de la FDF y sus archivos; el inventario **de estado** sale de la referencia SCF. La referencia hace falta de todos modos, porque es la matriz densidad padre de todas las respuestas. La cobertura se decide después de ella.

### C.2 Mapa canónico

```text
atom_index (1..N, orden de AtomicCoordinates)
  ↕ species_label (texto, solo como identificador)
  ↕ species_identity_digest (PSML + PAO.Basis + opciones de base + .ion, sin la etiqueta)
  ↕ subspace_id = (atom_index, n, l)   ← identidad científica
  ↕ dftu_record_digest = (n,l,rc,ω,λ,U_ref,J_ref)
  ↕ response_index (posición en χ, orden determinista por atom_index)
  ↕ output_atom_index (índice en las tablas de ocupación de SIESTA; biyección verificada)
```

### C.3 Reglas de ambigüedad (todas fallan cerrado)

1. **Etiqueta DFTU compartida por varios átomos.** Perturbar la etiqueta desplazaría todos esos átomos a la vez, y eso no es una columna de un solo sitio. Se admite la división automática en una etiqueta por sitio **solo** si las nuevas especies son semánticamente idénticas a la original: mismo PSML (digest), bloques `PAO.Basis` duplicados exactamente, entrada `DFTU.Proj` duplicada y `.ion` idénticos salvo la etiqueta tras la generación. Si no se puede demostrar: `SUBSPACE_MAPPING_NOT_ESTABLISHED`.
2. **Más de un registro DFTU por etiqueta** (varias capas por átomo): `NOT_SUPPORTED` en la versión actual. El código ya lo rechaza.
3. **Sintaxis FDF fuera del subconjunto auditado** (`%include` sin resolver, ZMatrix, `LatticeParameters`, coordenadas no fraccionarias sin normalización explícita): `NOT_SUPPORTED`. La resolución de `%include` debe producir una FDF efectiva con su propio digest.
4. **Spin no colineal o SOC:** `NOT_SUPPORTED`. Hoy el rechazo es solo implícito en el parser; hay que añadir una puerta explícita a partir de la FDF y del `redata` de la salida.
5. **Biyección átomo ↔ tabla de ocupación** no verificada: `FAIL`.
6. **Dos etiquetas distintas con la misma identidad física:** no es error. La etiqueta es un nombre, no una física (`fdf_symmetry_adapter.py` ya lo reconoce).
7. **Misma etiqueta pero distinto contenido** (PSML o base distintos): el planificador debe tratarlas como especies distintas y nunca como equivalentes.

---

## D. Matemática de la cobertura de perturbaciones

### D.1 Ley de reconstrucción

Sea \(\theta\) una operación del espacio de Hilbert de Kohn–Sham: una isometría espacial \(g=\{R\,|\,t\}\), opcionalmente compuesta con un volteo global de espín \(\varepsilon=-1\). Supongamos:

- **(H1) Covarianza del funcional.** \(\theta\,H[\rho]\,\theta^{-1}=H[\theta\rho\theta^{-1}]\) para el Hamiltoniano KS+U completo, incluida la discretización numérica (sección D.3).
- **(H2) Invariancia del estado de referencia.** \(\theta\rho_0\theta^{-1}=\rho_0\).
- **(H3) Covarianza de proyectores.** \(\theta P_J\theta^{-1}=P_{g(J)}\) para cada subespacio correlacionado, donde \(P_J\) es independiente del espín y \(g\) induce una permutación de \(\mathcal{S}\).
- **(H4) Unicidad de rama.** Para \(|\alpha|\) en la ventana usada, la solución SCF perturbada es la continuación única de \(\rho_0\) (no hay saltos de rama).

Entonces, para la perturbación \(V_J=\alpha P_J\), la densidad perturbada cumple \(\rho[\alpha\,\text{en }g(J)]=\theta\,\rho[\alpha\,\text{en }J]\,\theta^{-1}\). Para el observable escalar \(n_I=\mathrm{Tr}(P_I\rho)\):

\[
n_{g(I)}\big(\alpha\ \text{en}\ g(J)\big)=\mathrm{Tr}\!\left(\theta P_I\theta^{-1}\,\theta\rho\theta^{-1}\right)=\mathrm{Tr}(P_I\rho)=n_I(\alpha\ \text{en}\ J).
\]

Para \(\theta\) antiunitaria la traza se conjuga, pero es real porque \(P_I\) y \(\rho\) son hermíticos. El resultado es exacto **para cada α finito**, no solo para la derivada. Por lo tanto:

\[
\boxed{\chi^{(m)}_{g(I),g(J)}=\chi^{(m)}_{I,J},\qquad \chi^{(m)}=\Pi_g\,\chi^{(m)}\,\Pi_g^{\mathsf T},\qquad \chi^{(m)}_{:,g(J)}=\Pi_g\,\chi^{(m)}_{:,J}}
\]

con \((\Pi_g)_{g(I),I}=1\). La ley es la misma para BARE y para SCREENED. En BARE el Hamiltoniano está congelado en \(H[\rho_0]\): se necesita \(\theta H[\rho_0]\theta^{-1}=H[\rho_0]\), es decir H1 **y** H2, más H3 para la perturbación y el observable; solo H4 deja de ser necesaria. Como vale punto a punto en α, **se reconstruyen los datos crudos** \(n_I(\pm a_k)\), no solo las pendientes. Así el FD-EBQ se aplica idéntico a los elementos reconstruidos.

### D.2 Cuándo basta con menos perturbaciones

Sea \(G_{\rm resp}\) el conjunto de operaciones que cumplen H1–H4 (forma un grupo si se cierra bajo composición). Las órbitas de \(G_{\rm resp}\) sobre \(\mathcal{S}\) particionan los subespacios. **Basta y es necesario** calcular una columna por órbita:

- **Basta:** para cada \(J\) existe \(g\) con \(g(r)=J\), y \(\chi_{:,J}=\Pi_g\chi_{:,r}\).
- **Es necesario:** sin una operación que relacione dos sitios, ninguna relación exacta permite **sustituir** una columna por otra. La reciprocidad \(\chi_{IJ}=\chi_{JI}\) relaciona elementos sueltos entre columnas (solo en la derivada, no punto a punto en α), pero no reemplaza una columna completa; sirve como prueba, no como reconstrucción.

Si varias operaciones llevan \(r\) a \(J\), las reconstrucciones coinciden **si y solo si** \(\chi_{:,r}\) es invariante bajo el estabilizador \(\mathrm{Stab}(r)\). Esa es una **prueba de consistencia gratuita** sobre datos ya calculados.

Una aclaración: los subespacios no correlacionados (ligandos) no se perturban ni se observan, pero **sí** cuentan para H1 y H2 (geometría y momentos de todos los átomos).

### D.3 La discretización también debe ser covariante

SIESTA no resuelve el continuo. H1 exige que la operación respete:

- **La malla de espacio real** (`MeshCutoff`). Una traslación \(t\) debe llevar la malla a sí misma (\(t\cdot N_{\rm mesh}\in\mathbb{Z}^3\) en coordenadas fraccionarias de la celda). Una rotación \(R\) debe dejar la malla invariante. Si no, aparece el efecto *egg-box*: una ruptura pequeña pero no nula.
- **La malla k.** \(R\) debe dejarla invariante. Las traslaciones solo introducen fases y no la afectan.
- **La base y el pseudopotencial.** Deben ser idénticos entre \(J\) y \(g(J)\) (sección C.1).

Esto define dos clases de operación:

| Clase | Definición | Consecuencia |
|---|---|---|
| `EXACT_IN_DISCRETIZATION` | Traslación de la red padre conmensurable con la malla real; las especies tienen identidad semántica; malla k irrelevante. | Exacta salvo errores de implementación (que es lo que detecta la sombra). |
| `EXACT_IN_CONTINUUM_ONLY` | Rotaciones, traslaciones no conmensurables o mallas k no invariantes. | Ruptura numérica pequeña; requiere sombra y, además, el programa de validación (sección R) antes de habilitarse. |

### D.4 Evidencia retrospectiva en datos del propio proyecto

Hay campañas archivadas en las que **ambas** columnas relacionadas por simetría se calcularon de forma directa, de modo que la ley puede probarse sin correr nada nuevo (script `coverage_review_checks.py`):

**CoO V6** (2 Co de subredes opuestas; \(g\) = intercambio de subred con volteo de espín, \(\varepsilon=-1\)), en e/eV:

| modo | a (eV) | \(\chi_{00}-\chi_{11}\) | \(\chi_{01}-\chi_{10}\) | \(|\chi_{00}|\) |
|---|---|---|---|---|
| BARE | 0.02 / 0.04 / 0.06 | 0 / −1.25e-5 / −8.3e-6 | 0 / 0 / 0 | 1.35 |
| SCREENED | 0.02 / 0.04 / 0.06 | 0 / +1.25e-5 / −2.5e-5 | 0 / +1.25e-5 / −4.2e-5 | 0.117 |

Las diferencias son de uno a pocos pasos de impresión dividido entre \(2a\). Las ocupaciones de referencia difieren en \(10^{-6}\) e.

**MnO v3r2** (16 Mn; columnas A y B calculadas; \(g\) = traslación A→B con volteo de espín):

| modo | a (eV) | \(\max_I|\chi_{I,B}-(\Pi_g\chi_{:,A})_I|\) | × a (e) | cota de impresión sola |
|---|---|---|---|---|
| BARE | 0.025 / 0.05 / 0.10 | 6.0e-4 / 3.0e-4 / 1.5e-4 | 1.5e-5 (constante) | 4.0e-4 / 2.0e-4 / 1.0e-4 |
| SCREENED | 0.025 / 0.05 / 0.10 | 8.0e-4 / 4.0e-4 / 1.5e-4 | 1.5–2.0e-5 | 4.0e-4 / 2.0e-4 / 1.0e-4 |

Interpretación:

1. La discrepancia es **constante a nivel de ocupación** (alrededor de 1.5×10⁻⁵ e) y decrece como \(1/a\) en la pendiente. Es ruido de nivel absoluto, no una violación sistemática de la simetría, que sería constante en la pendiente. En \(a=0.10\) eV equivale a 0.1% de \(|\chi^0_{\rm diag}|=0.147\).
2. Supera la cota de impresión sola por un factor de 1.5 a 2. Su origen (tolerancia SCF de la DM padre o selección del evento BARE) no queda determinado. Es justamente el término independiente de α que la revisión FD-EBQ identificó como invisible al diagnóstico multiescala y que aquí **se vuelve visible al comparar dos columnas**.
3. La política actual (`response_max_abs_e_per_ev=5e-5`) habría **rechazado** esta equivalencia en todas las α. Una tolerancia absoluta en la pendiente, fija e independiente de α, está mal planteada.

Esto es evidencia de desarrollo y **post hoc**, no validación: dos sistemas, ambos óxidos de rocksal AFM. Además, en MnO el script construye la permutación solo con las posiciones de Mn (\(t=\mathbf r_{B0}-\mathbf r_{A0}\)) y no verifica que los oxígenos también se mapeen: que \(g\) sea una simetría de toda la estructura se **asume** (rocksal ideal), no se demuestra. Sin embargo, apoya directamente admitir \(\varepsilon=-1\) bajo las condiciones de la sección G.

### D.5 Contraejemplos sintéticos (`toy_symmetry_ring.py`)

Anillo de Hubbard en campo medio con salto a segundos vecinos (para romper la simetría partícula-hueco), BARE congelado y SCREENED autoconsistente. Se muestra \(\max|\Pi\chi\Pi^{\mathsf T}-\chi|\):

| Caso | Momentos | χ⁰ | χ | Lectura |
|---|---|---|---|---|
| Anillo de 4, AFM, \(i\to i+1\) con volteo | ±0.82 | 4e-12 | 2e-12 | La ley con \(\varepsilon=-1\) es exacta. |
| Anillo de 4, AFM con energías de sitio 0/0.8, \(i\to i+1\) | **±0.81 (iguales en magnitud)** | **6e-3** | **6e-3** | **Momentos idénticos no bastan:** el entorno químico oculto rompe la equivalencia. La geometría (H1) es indispensable. (Mismo resultado en el anillo de 6: 3e-3 con ±0.74.) |
| Igual, \(i\to i+2\) | ±0.81 | 7e-12 | 1e-12 | La traslación de la red verdadera sí vale. |
| Anillo de 6, geometría simétrica, estado ↑↑↓↑↑↓, \(i\to i+1\) | 0.86, 0.86, −0.73 (×2) | **5.5e-2** | **4.0e-2** | **Ruptura espontánea:** con estructura simétrica el estado no lo es, así que H2 es indispensable. |

---

## E. Ley de reconstrucción por simetría, en el detalle de HubbardFlow

1. **Filas y columnas.** \(\chi_{g(I),g(J)}=\chi_{I,J}\). Se permutan filas **y** columnas con la misma \(\Pi_g\) restringida a \(\mathcal{S}\).
2. **Proyectores y marcos locales.** Para \(R\neq I\), H3 requiere que el conjunto \(\{\phi_{nlm}\}_m\) del proyector sea cerrado bajo \(R\). Una capa \(l\) completa con la misma función radial lo es (\(D^{l}(R)\) mezcla solo dentro de \(l\)), y en el método 2 de SIESTA la capa siempre es completa. Como el observable es la **traza**, el marco local no importa: \(\mathrm{tr}\,D n D^{\mathsf T}=\mathrm{tr}\,n\). Si en el futuro se observa la matriz de ocupación completa (por ejemplo para J de Hund o respuesta orbital), la ley pasa a ser \(n_{g(I)}=D^{l}(R)\,n_I\,D^{l}(R)^{\mathsf T}\) (más el intercambio ↑↔↓ si \(\varepsilon=-1\)) y la reconstrucción debe transformar matrices, no permutar escalares.
3. **Espín.** La perturbación es \(\alpha\sum_\sigma P_{J\sigma}\) (independiente del espín) y el observable es \(\sum_\sigma\mathrm{tr}\,n_{I\sigma}\). Ambos son invariantes ante \(\sigma\to-\sigma\). Un observable resuelto en espín se transformaría como \(n_{I\uparrow}\to n_{g(I)\downarrow}\).
4. **Simetría magnética.** En magnetismo colineal sin SOC, los grados espaciales y de espín están desacoplados (grupo de espín). Las operaciones relevantes son \(g\) (con \(\varepsilon=+1\)) y \(g\circ\)volteo (con \(\varepsilon=-1\)); no actúan sobre el espín como vectores axiales. Por eso la regla actual de `detect_symmetry` (\(\det R\,R\,m\)) es incorrecta como criterio general sin SOC, aunque sea conservadora para traslaciones. Con SOC o no colinealidad harían falta operaciones antiunitarias del grupo magnético. Eso está **fuera de alcance** porque el backend lo rechaza.
5. **Antiunitarias.** No se necesitan en el caso colineal sin SOC (el volteo global es unitario en el espacio de espín). Si se añaden, la traza sigue siendo real.
6. **BARE y SCREENED.** Siguen la misma ley si la DM padre es la misma (lo es, por construcción de campaña) y es simétrica (H2).
7. **Definición de ocupación.** Es invariante si el parser suma los mismos tokens (capa completa) para todos los sitios. `occupation_precision.py` ya verifica que la suma de la diagonal coincida con `trace_total`.

---

## F. Criterios de equivalencia de respuesta

Una operación \(\theta=(g,\varepsilon)\) pertenece a \(G_{\rm resp}\) si y solo si cumple **todo** lo siguiente:

| # | Condición | Evidencia | Tolerancia |
|---|---|---|---|
| F1 | \(g\) es simetría de la estructura completa (todos los átomos) | Geometría de la FDF efectiva | Banda geométrica |
| F2 | \(g\) preserva la **identidad semántica** de especie de cada átomo | digest de PSML, `PAO.Basis` y `.ion` (sin etiqueta) | Igualdad exacta |
| F3 | \(g\) preserva el registro DFTU de cada sitio correlacionado | \((n,l,r_c,\omega,\lambda,U_{\rm ref},J_{\rm ref})\) | Igualdad exacta |
| F4 | Si \(R\neq I\): la capa es completa, la malla k es invariante y la operación queda marcada `EXACT_IN_CONTINUUM_ONLY` | Registro DFTU, malla k efectiva | Exacta |
| F5 | Magnetismo: \(m_{g(s)}=\varepsilon\,m_s\) para **todo** átomo \(s\), con una sola \(\varepsilon\) global | Momentos finales de la referencia | Banda magnética |
| F6 | Si \(\varepsilon=-1\): espín colineal, sin SOC, perturbación y observable independientes del espín | Contrato del backend y salida (`redata`) | Exacta |
| F7 | Estado: el espectro de la matriz de ocupación local de \(s\) y de \(g(s)\) coincide (con ↑↔↓ si \(\varepsilon=-1\)) | Matrices de ocupación de la referencia | Banda de estado |
| F8 | Discretización: se clasifica la conmensurabilidad de \(t\) con la malla real | `InitMesh` de la salida | Exacta |

**Tolerancias en banda (sin umbral único).** Para cada magnitud comparada \(x\) (distancia geométrica, \(|m_{g(s)}-\varepsilon m_s|\), diferencia espectral) el protocolo declara dos tolerancias versionadas, \(\tau_{\rm eq}<\tau_{\rm neq}\), y el resultado es:

- \(x\le\tau_{\rm eq}\): `EQUAL`;
- \(x\ge\tau_{\rm neq}\): `DIFFERENT`;
- en medio: `AMBIGUOUS`. Cualquier `AMBIGUOUS` en una operación la excluye, y si eso deja una órbita sin cubrir se registra el motivo.

\(\tau_{\rm eq}\) se ancla en la resolución de la magnitud: el paso de impresión y la tolerancia SCF declarada. **No** se elige mirando el resultado. Esto resuelve la clasificación dependiente de tolerancia: una estructura casi simétrica cae en `AMBIGUOUS` y se perturba completa.

**Equivalencias declaradas por el usuario.** Se admiten, pero solo como **hipótesis**: una clase declarada se acepta si existe una operación de \(G_{\rm resp}\) que la genere. La declaración puede **restringir** la reducción (por ejemplo, el usuario la desactiva), pero nunca puede **añadir** equivalencias que F1–F8 no demuestren.

**Lo que no es criterio:** el mismo elemento, la misma etiqueta, el mismo Wyckoff sin estado, la misma coordinación ni que el U obtenido salga parecido (eso es circular).

---

## G. Tratamiento magnético

| Caso | Operaciones admitidas | Reducción típica |
|---|---|---|
| No magnético (`Spin non-polarized` verificado en la salida) | \(\varepsilon=+1\) (el volteo es trivial) | Por órbita de \(g\). |
| Ferromagnético | Solo \(\varepsilon=+1\); \(\varepsilon=-1\) falla F5 salvo momento nulo | Por órbita de \(g\). |
| AFM colineal compensado | \(\varepsilon=+1\) dentro de cada subred; \(\varepsilon=-1\) entre subredes si F1–F7 se cumplen | Subredes A y B en **una** clase (CoO: 2→1; MnO: 16→1). |
| Ferrimagnético (magnitudes distintas) | \(\varepsilon=-1\) imposible (F5 falla porque \(|m|\) difiere) | Por subred. |
| AFM con entornos inequivalentes y \(|m|\) igual | F1 y F2 deciden (contraejemplo D.5) | Ninguna entre subredes si la geometría no las relaciona. |
| Simetría magnética rota por el estado (orden orbital, canting) | F7 falla | Se perturba todo lo afectado. |
| No colineal o SOC | Fuera de alcance (`NOT_SUPPORTED`) | Se perturba todo, o se rechaza la campaña. |

\(\varepsilon=-1\) es teóricamente exacta (secciones D.1 y E.4) y está respaldada retrospectivamente en CoO y MnO. Aun así, se habilita **por bandera** solo después del programa de validación (sección R), porque los dos casos disponibles son del mismo tipo estructural.

---

## H. Comportamiento de respaldo seguro

Se perturban **todos** los subespacios correlacionados (`coverage_strategy = ALL_SUBSPACES`) cuando ocurre cualquiera de estos casos:

- falta la evidencia de referencia (salida no normal, SCF sin converger, momentos o matrices incompletos);
- hay algún `AMBIGUOUS` que impide cubrir una órbita;
- la identidad semántica de especies no se demuestra;
- la sintaxis no está soportada;
- la reducción se desactiva por política o usuario (`DISABLED`);
- el sistema es pequeño y la órbita mínima ya es \(|\mathcal S|\).

Si una órbita reducida **falla su sombra**, esa órbita (no toda la campaña) se expande a perturbación explícita de sus miembros, reutilizando lo ya calculado. Así lo hace hoy `explicit_expansion_specs`.

Estados por clase: `PROVEN`, `CANDIDATE_PENDING_SHADOW`, `REJECTED_EXPANDED`, `NOT_ESTABLISHED`, `DISABLED`.
Estado global: `ALL_SUBSPACES`, `SYMMETRY_REDUCED` (todas las clases reducidas en `PROVEN`) o `PARTIALLY_REDUCED`.

---

## I. Auditoría de FDRC-v1 en el contexto ampliado

Se mantienen sin cambios las conclusiones de la revisión anterior (`docs/fdebq/HUBBARDFLOW_FDRC_INDEPENDENT_REVIEW.md`):

- FDRC-v1 se **reemplaza** por FD-EBQ;
- el piso de ruido con réplicas en α=0 no es válido para SCF deterministas;
- la estabilidad de U no puede ser criterio de parada;
- BARE y SCREENED tienen regímenes de error distintos;
- la malla común global es una comodidad, no un requisito.

En el contexto ampliado hay tres consecuencias nuevas:

1. FDRC-v1 suponía blancos ya elegidos. Ahora la calibración opera **solo sobre representantes** y la sombra hereda el protocolo del representante (sección N).
2. FDRC-v1 no tenía un mecanismo para comparar columnas. La comparación sombra–reconstrucción es una prueba de falsación cruzada que **sí detecta errores independientes de α** (sección D.4, punto 2), algo que el análisis multiescala de una sola columna no puede ver.
3. Los literales fijos de `SymmetryReductionPolicy` y los de FDRC-v1 se sustituyen por los presupuestos FD-EBQ.

---

## J. Metodología recomendada de calibración de α (FD-EBQ, resumen)

La especificación completa está en la revisión anterior (secciones I–K) más `ERRATA_I3.md` (R0–R2, `TAIL_UNRESOLVED`).

Para cada (columna \(J\), modo \(m\), fila \(I\)):

1. **Descomposición par/impar.** Las pendientes centrales son \(s_k=\frac{n(+a_k)-n(-a_k)}{2a_k}\); la parte par no afecta la pendiente.
2. **Orden del término dominante (R0).** Las razones de deriva \(\rho_p=\frac{a_{k+2}^p-a_{k+1}^p}{a_{k+1}^p-a_k^p}\) se comparan con el intervalo observado y dan `VERIFIED_2`, `VERIFIED_1`, `UNRESOLVED` o `INCONSISTENT`. Se usa \(p=2\) solo si el orden 2 está verificado; si no, \(p=1\) (conservador).
3. **Truncamiento (R1/R2).** \(\tau=\frac{|\Delta|+\nu_k+\nu_{k+1}}{q-1}\) con \(q=N^{(k+1)}/N^{(k)}\), y momentos \(N=\sum w\,a^{p}\) calculados con fracciones exactas. Los estimadores que anulan \(a^2\) (Richardson, cúbico) solo se admiten con `VERIFIED_2`.
4. **Ruido.** Cuantización de impresión (`BOUND`, suma de semipasos por token) más una componente SCF (`ESTIMATE`) a partir de una escalera de tolerancia SCF (fase 2). Las cotas se **suman**, no se combinan en cuadratura.
5. **Falsación.** Consistencia entre estimadores vecinos, reciprocidad \(\chi_{IJ}\approx\chi_{JI}\), consistencia sombra–reconstrucción (nuevo) y la puerta de consistencia de estado.
6. **Aceptación en el espacio de U.** \(\partial U_{KK}/\partial\chi_{IJ}=(\chi^{-1})_{KI}(\chi^{-1})_{JK}\) (con signo opuesto para \(\chi^0\)), contra una tolerancia \(\tau_U\) declarada por el usuario, más \(\beta<1\) (invertibilidad en todo el intervalo).
7. **Rondas deterministas** sobre una red de amplitudes declarada, con barreras y sin contadores históricos ni dependencia del orden de llegada.
8. **Estados:** `QUALIFIED`, `QUALIFIED_HETEROGENEOUS`, `REVIEW`, `NOT_ESTABLISHED`, `NOT_DIFFERENTIABLE_AT_SCALE`, `FAIL`.

El modelo conceptual \(E(a)\sim C_{\rm num}/a+C_{\rm nl}a^2\) de la consigna es correcto como intuición, pero insuficiente:

- \(C_{\rm num}\) tiene componentes absoluta, relativa y de sesgo común, y esta última es invisible al análisis multiescala;
- el término no lineal puede ser \(O(a)\) (impar no analítico) y no \(O(a^2\));
- y la aceptación debe hacerse en el espacio de U, no en el de la pendiente.

---

## K. Estrategia para el piso de ruido numérico

Esta sección mantiene la revisión anterior (sección K) con una adición empírica.

- **Cota rigurosa:** el redondeo de impresión, sumando los semipasos de **todos** los tokens que forman la traza (`occupation_precision.py`). Atención: en la revisión anterior se usó \(5\times10^{-7}\) por ocupación solo como ilustración; para una capa d con dos espines, la cota correcta es la suma de 10 semipasos.
- **Estimación SCF:** escalera de tolerancias (`SCF.DM.Tolerance` reducida en factores declarados) sobre la diferencia impar \(\Delta(a)\), con prueba de contracción. Es la única fuente que mide el error de convergencia sin suponer que es aleatorio.
- **No válidos como piso de ruido:** réplicas en α=0 (los cálculos deterministas no dan estadística), variaciones de la última iteración SCF por sí solas y la "repetibilidad" de reinicios con la misma DM.
- **Nuevo, la discrepancia entre columnas simétricas.** Cuando hay dos columnas relacionadas por simetría calculadas directamente, su diferencia mide el error independiente de α, del orden de \(2\times10^{-5}\) e en MnO. Es una **cota inferior empírica** del ruido efectivo, no un piso aceptable por sí misma.

**Bloqueador abierto:** la escalera SCF todavía no está validada (los parámetros θ y \(\rho_{\max}\) de la revisión anterior). Mientras no lo esté, los presupuestos solo cubren la impresión. Para la **cobertura** eso es seguro: una sombra comparada con una cota demasiado estrecha produce rechazos falsos que expanden la órbita, lo que cuesta cómputo pero no compromete la corrección. Para la **calibración**, en cambio, hay riesgo de subestimar el error de SCREENED; por eso FD-EBQ marca esos resultados como `print-quantization bounds only`.

---

## L. Malla de α común o por sitio

**Decisión: se permite una malla por columna y por modo, sobre una red de candidatos común.**

- **Justificación matemática.** \(\chi_{:J}\) depende solo de las perturbaciones de \(J\). Columnas distintas son experimentos distintos, y cada una puede usar su propio estimador siempre que su presupuesto sea correcto. Nada en la definición de \(\chi\) ni de \(U\) exige la misma α para todas.
- **Red común de candidatos.** Las amplitudes se toman de una red declarada (por ejemplo \(\{a_1<\dots<a_K\}\) en el protocolo). Eso permite reutilizar pilotos, hacer comparaciones sombra–representante sobre los mismos puntos y mantener una procedencia simple.
- **Clases de simetría.** La sombra y las columnas reconstruidas **deben** usar la malla y el estimador del representante. Las reconstruidas los heredan por construcción, y la sombra se corre con el `ColumnPlan` resuelto del representante. Una calibración independiente de la sombra destruiría la comparabilidad.
- **Análisis matricial.** La incertidumbre es heterogénea por elemento. La propagación usa la influencia por elemento y \(\beta\); no hay suposición de homogeneidad. El estado `QUALIFIED_HETEROGENEOUS` lo hace visible.
- **Reproducción de V6.** `FIXED_PROTOCOL_GRID` aplica la misma malla a todas las columnas y modos, sin cambios.

---

## M. Política de amplitudes BARE frente a SCREENED

**Decisión: la selección es independiente por modo y la red de candidatos es común.**

BARE está dominado por el truncamiento (en CoO, \(c_3\approx9.4\) e/eV³ y razón de deriva 1.645 frente a 1.667 teórica), mientras que SCREENED está dominado por el ruido. Forzar una ventana común obliga a uno de los dos a operar fuera de su óptimo.

Para \(U\) basta con que cada matriz tenga su presupuesto: la propagación por influencia trata \(\chi^0\) y \(\chi\) por separado. Una ventana común sigue disponible como política explícita (por reproducibilidad histórica), no como requisito científico.

---

## N. Acoplamiento entre cobertura y calibración

1. **Orden.** Primero la cobertura (necesita solo la referencia), luego la calibración, que solo se aplica a representantes. La cobertura **no** depende de ninguna respuesta, salvo la sombra, que solo confirma o revoca.
2. **La calibración del representante basta para su clase.** Por la ley D.1, los datos crudos de \(g(J)\) son una permutación exacta de los de \(J\) en cada α, así que la ventana y el estimador son igualmente válidos para toda la órbita.
3. **La sombra es el puente empírico.** Por cada clase con más de un miembro se elige **un** miembro no representante de forma determinista: el de menor `atom_index` entre los alcanzables por una operación de \(G_{\rm resp}\). Se ejecuta con el `ColumnPlan` **ya resuelto** del representante (sus mismas α y estimador), en ambos modos, y se comprueba que, para todo \(I\) y modo \(m\),

\[
\big|\hat\chi^{\rm dir}_{I,J'}-\hat\chi^{\rm rec}_{I,J'}\big|\le B^{\rm dir}_{I,J'}+B^{\rm rep}_{g^{-1}(I),r}
\]

con presupuestos FD-EBQ: comparación absoluta por elemento, sin métricas relativas. Las columnas de sombra son datos directos y **se usan directamente** en la matriz (lo calculado prevalece sobre lo reconstruido).
4. **Si la sombra falla,** la clase se revoca y se expande. Eso no reabre la calibración del representante, que sigue siendo válida para su propia columna.
5. **Coste.** Una columna extra por clase reducida. En MnO con \(\varepsilon=-1\): 1 representante + 1 sombra = 2 columnas frente a 16. Con \(\varepsilon=+1\) solamente: 2 + 2 = 4 frente a 16.
6. **Comprobaciones gratuitas, sin cálculos nuevos:** reciprocidad \(\chi_{r_1r_2}\) frente a \(\chi_{r_2r_1}\) entre representantes; invariancia de \(\chi_{:,r}\) bajo \(\mathrm{Stab}(r)\); y la equivalencia de filas dentro de cada columna calculada (\(\chi_{g(I),r}=\chi_{I,r}\) para \(g\in\mathrm{Stab}(r)\)).
7. **¿Validar varias sombras por clase?** No por defecto. La ley es exacta bajo F1–F8, y la sombra detecta errores de mapeo, de especie o de estado, que serían sistemáticos para toda la clase. Más sombras solo sirven en el programa de validación (sección R), no en producción.

---

## O. Metodología completa: de la FDF base al `ResolvedPerturbationPlan`

```text
1. FDF base ──resolve %include──► FDF efectiva (digest)
2. Inventario estático: átomos, especies semánticas, registros DFTU, mapa (sección C.2)
   └─ ambigüedad → NOT_SUPPORTED / SUBSPACE_MAPPING_NOT_ESTABLISHED (STOP)
3. División de especies si una etiqueta DFTU cubre varios átomos (con identidad semántica verificada)
4. Referencia SCF (DM padre) ──► evidencia de estado: momentos finales, matrices de ocupación locales,
   malla real efectiva, malla k, terminación normal
5. Cobertura:
   a. operaciones geométricas candidatas (conservadoras)
   b. filtrar F1–F8 con tolerancias en banda → G_resp
   c. órbitas, representantes y sombras deterministas
   d. sin G_resp útil → ALL_SUBSPACES
6. Calibración FD-EBQ por representante y modo (rondas deterministas sobre la red común)
   └─ estados por elemento y columna
7. Sombras con el ColumnPlan del representante → consistencia → PROVEN / REJECTED_EXPANDED
8. Expansión de clases rechazadas (reutilizando los datos válidos)
9. ResolvedPerturbationPlan congelado (digest) ──► CampaignPlan ──► campaign.lock ──► DAG de producción
```

El plan se congela antes de la producción. En `FIXED_PROTOCOL_GRID` los pasos 6–7 se reducen a la malla fija, y con blancos explícitos el paso 5 se omite: así se reproduce V6 sin reinterpretarlo.

---

## P. Algoritmo determinista (pseudocódigo)

```python
def resolve_perturbation_plan(fdf, inputs, protocol, user_policy) -> ResolvedPerturbationPlan:
    eff = resolve_includes(fdf)                                   # digest
    inv = build_static_inventory(eff, inputs)                     # fail closed
    if inv.status is not OK:
        return stop(inv.status)
    eff, inv = split_shared_dftu_species(eff, inv)                # semantic identity proven or STOP
    ref = run_or_load_reference(eff)                              # parent DM
    state = extract_state_evidence(ref)                           # moments, occ. spectra, mesh, k-mesh
    if not state.normal_and_converged:
        return stop("REFERENCE_NOT_ADMISSIBLE")

    # ---- coverage (no response data used)
    if user_policy.coverage == "DISABLED" or protocol.fixed_targets:
        cov = all_subspaces(inv, reason="DISABLED_OR_FIXED")
    else:
        cands = candidate_operations(inv.geometry, protocol.geometry_band)          # conservative
        G = [op for op in cands
             for eps in allowed_eps(state.spin_model)                               # (+1) or (+1, -1)
             if classify(op, eps, inv, state, protocol.bands).all_equal()]          # F1..F8; AMBIGUOUS -> excluded
        G = close_under_composition(G)                                              # verify group closure
        orbits = orbits_of(G, inv.correlated)                                       # sorted by min atom_index
        cov = coverage_from_orbits(orbits, op_class=exactness_class(G, state))      # reps = min index
        if user_policy.declared_classes:
            cov = restrict_to_declared(cov, user_policy.declared_classes)           # may only restrict

    # ---- calibration on representatives only
    plans = {}
    for r in cov.representatives:
        for m in (BARE, SCREENED):
            plans[(r, m)] = fdebq_rounds(r, m, protocol.candidate_lattice, protocol.policy)   # barriers per round
    # ---- shadows (coverage confirmation), same ColumnPlan as representative
    for cls in cov.reduced_classes:
        s, g = cls.shadow, cls.op_to_shadow
        data = run_column(s, plans_for(cls.rep), modes=(BARE, SCREENED))
        ok = all(abs(direct - reconstructed) <= B_dir + B_rep
                 for each (I, m) in rows x modes)
        cls.status = PROVEN if ok and state_gate(data) else REJECTED_EXPANDED
    for cls in cov.rejected():
        for J in cls.members - computed:
            plans_for_member = calibrate_or_reuse(J)               # explicit fallback
    plan = assemble(inv, cov, plans, state, protocol)              # reconstruction maps for omitted columns
    return freeze(plan)                                            # digest over everything above
```

**Reglas de determinismo:**
- todo se itera en orden de `atom_index`;
- los representantes son el índice mínimo de cada órbita, y las sombras el siguiente índice alcanzable;
- las decisiones de una ronda se toman en su barrera con todos los resultados de la ronda;
- el orden de llegada de tareas no influye;
- ninguna decisión lee \(U\), su estabilidad ni el número de condición.

**Flujo de información sin circularidad:**

```text
COVERAGE VALIDITY      ← geometría, especies, estado de referencia, sombras
CALIBRATION VALIDITY   ← datos de su propia columna (y sombra solo como falsación)
MATRIX CERTIFIABILITY  ← existente (rango, β, inversión directa)
U QUALIFICATION        ← todo lo anterior + τ_U del usuario
```

Ninguna flecha vuelve hacia arriba.

---

## Q. Contrato de evidencia y procedencia

`CoverageQualification`. Se evita la palabra "certificado"; sí se usa "calificación".

```text
inventory_digest, effective_fdf_sha256, species_identity_digests{label→digest}
reference: fdf_sha256, output_sha256, parent_dm_sha256, scf_tolerances, normal_completion
state_evidence: moments_by_atom, occupation_spectra_by_subspace(σ), mesh_divisions, k_mesh
protocol_bands: {geometry, magnetic, spectral}: (tau_eq, tau_neq), protocol_version
operations: [ {rotation, translation, eps, permutation_atoms, permutation_subspaces,
               exactness_class, per_condition_result F1..F8 with values} ]
classes: [ {members, representative, shadow, op_rep_to_member{J→op_id}, status,
            shadow_comparison: per (I,m) |Δ|, B_dir, B_rep, pass} ]
reconstruction_maps: {omitted J → (representative r, op_id)}
strategy: ALL_SUBSPACES | SYMMETRY_REDUCED | PARTIALLY_REDUCED | USER_RESTRICTED
reasons: [codes]
```

`CalibrationQualification`: los `ElementBudgetReport` de FD-EBQ por (J, m, I), los `ColumnPlan` resueltos, las rondas con sus barreras, y los digests de cada salida usada.

Todo se incluye en el digest de `ResolvedPerturbationPlan`. Los pilotos se reutilizan como producción **solo** si coinciden en: FDF efectiva, DM padre, subespacio blanco, α exacto (representable en FDF), modo, registro DFTU, identidad de backend y versión, perfil SCF, versión del parser, estado magnético y perfil científico de la campaña. Nunca se reutilizan por nombre de archivo o directorio.

---

## R. Programa de validación

| Fase | Sistemas | Qué demuestra | Criterio |
|---|---|---|---|
| V0, sintético | Anillos de campo medio (este informe); FD-EBQ sintético (revisión anterior) | La ley y los contraejemplos | La ley se cumple a precisión de máquina en los positivos y se detecta en todos los negativos. |
| V1, retrospectivo (sin SIESTA) | CoO V6, NiO V6, MnO v3r2 A/B, Cu3N (X/Y/Z, archivo de evidencia) | Consistencia en columnas ya calculadas | Consistencia sombra–reconstrucción dentro de presupuestos; registrar la discrepancia independiente de α. |
| V2, sombras prospectivas | MnO (traslación ε=+1 y ε=−1), Cu3N (una traslación por órbita; una rotación X→Y como `EXACT_IN_CONTINUUM_ONLY`) | Exactitud en la discretización real | Todas las sombras pasan con presupuestos que incluyan el ESTIMATE SCF. |
| V3, controles negativos (deben rechazarse) | FeO u otro estado con orden orbital; un ferrimagnético; un slab o supercelda con defecto; una estructura casi simétrica dentro de la banda; especies con la misma etiqueta y base distinta | Ningún falso positivo | **Cero** aceptaciones falsas. |
| V4, holdout | Sistemas elegidos y congelados **antes** de correr (por ejemplo, NiO en otra supercelda o un AFM no rocksal) | Generalización | Protocolo congelado; sin ajuste posterior. |
| T0–T4 | Programa FD-EBQ de la revisión anterior (escalera SCF, referencias f20.12) | Validez de la calibración | Según la revisión anterior. |

**Qué se habilita y cuándo:**
- Reducción por traslación con \(\varepsilon=+1\) y sombra obligatoria: tras V1 y V2.
- \(\varepsilon=-1\): tras V1, V2 y V3 con éxito.
- Rotaciones: tras V2 y V3 y una cuantificación del egg-box.
- Sombra opcional: nunca por defecto; solo como política explícita tras V4.
- α calibrada: tras T0–T4.

---

## S. Modos de falla adversariales

| Falla | Cómo se manifiesta | Detección o manejo |
|---|---|---|
| Sitios cristalográficamente equivalentes, magnéticamente no | m difiere en signo o magnitud de forma no global | F5; banda magnética. |
| AFM con \(|m|\) igual pero entorno distinto | Equivalencia aparente por momentos | F1 y F2 (contraejemplo D.5). |
| Mismo elemento, proyectores distintos | Registros DFTU distintos | F3 (igualdad exacta). |
| Misma etiqueta, base distinta (o división sin duplicar `PAO.Basis`) | Física cambiada en silencio | F2 por digest; división solo con identidad semántica. |
| Simetría rota por la DM (orden orbital) | Espectros locales distintos | F7; si se escapa, la sombra falla. |
| Defectos, superficies, distorsiones | Faltan operaciones | Órbitas más pequeñas; fallback natural. |
| Casi simetría | Distancias dentro de la banda | `AMBIGUOUS` → sin reducción. |
| Clasificación dependiente de tolerancia | El resultado cambia con τ | Bandas declaradas y versionadas; `AMBIGUOUS` en la zona gris. |
| Ejes locales no triviales | Rotación de la capa | Solo afecta a observables no escalares; con traza es invariante (E.2). |
| Inversión de espín | Subredes opuestas | ε=−1 solo con F6 y bajo bandera hasta V3. |
| BARE y SCREENED con simetría efectiva distinta | Una sombra pasa en un modo y falla en el otro | La sombra se evalúa por modo; si falla cualquiera, la clase se revoca. |
| Ruptura numérica de simetría (egg-box) | Discrepancia pequeña en sombras con rotación | Clase `EXACT_IN_CONTINUUM_ONLY`; sombra; V2. |
| Salto de rama bajo perturbación | Pendientes no suaves, momentos cambian | Puerta de estado; `NOT_DIFFERENTIABLE_AT_SCALE`. |
| Respuestas cruzadas casi nulas | Métricas relativas inestables | Comparaciones absolutas con presupuesto; aceptación en el espacio de U. |
| Matriz mal condicionada | β cercano a 1 | Certificación existente; **nunca** como criterio de α ni de cobertura. |
| Señal α insuficiente | Deriva no resuelta | FD-EBQ: `UNRESOLVED` → p=1 conservador, o `NOT_ESTABLISHED`. |
| Ventanas contradictorias entre sitios | Estimadores distintos por columna | Permitido; `QUALIFIED_HETEROGENEOUS`. |
| Clase que falla en la sombra | La sombra no coincide | Expansión explícita de la clase. |
| Mapa que preserva la geometría pero no los observables | Etiqueta de salida permutada | Biyección átomo ↔ tabla verificada (sección C.3, regla 5); la sombra lo detecta. |
| Tolerancia fija en la pendiente | Rechazos de equivalencias válidas a α pequeña (MnO) | Comparación por presupuesto, que escala con 1/a. |

---

## T. Integración en HubbardFlow (mínima)

| Cambio | Archivo | Tipo |
|---|---|---|
| Inventario canónico de subespacios (puro) | **nuevo** `domain/subspace_inventory.py` | Dataclasses congeladas; sin I/O. |
| Modelo FDF único (subconjunto soportado, mapa átomo ↔ etiqueta ↔ registro DFTU, identidad de especies) | **nuevo** `siesta_backend/fdf_model.py`, que consolida el parseo duplicado en `campaign_v2.py` y `fdf_symmetry_adapter.py` y reutiliza `campaign_v2.resolve_fdf_includes` (ya existe) | Backend. |
| Evidencia de estado (espectros locales, malla real, malla k) | ampliar `siesta_backend/reference_magnetic_evidence.py` (o un nuevo `reference_state_evidence.py`) | Backend. |
| Operaciones con ε, bandas y clases de exactitud | ampliar `src/symmetry_reduction_proposal.py` → mover a `domain/symmetry_operations.py` | Dominio puro. |
| Política de reducción sin literales; comparación sombra por presupuesto; varias α | `domain/symmetry_reduction.py` | Dominio. |
| División de especies con identidad semántica | `siesta_backend/fdf_builder.py::materialize_split_species_fdf` (duplicar `PAO.Basis`, `DFTU.Proj` y PSML, y verificar `.ion`) | Backend. |
| Reconstrucción de datos crudos por permutación | **nuevo** `domain/response_reconstruction.py` (generaliza `lru_core.reconstruct`) | Dominio. |
| Protocolo por columna | `domain/response_protocol.py` (TASK 1, rama `fdebq/task1-protocol`; aún no en la rama base) | En curso. |
| Contrato del plan | **nuevo** `domain/perturbation_plan.py` (`ResolvedPerturbationPlan`) | Dominio. |
| Producción | `execution/campaign_v2.py`: `sites` opcional en `lr-config` → el planificador lo llena; los blancos explícitos más `FIXED_PROTOCOL_GRID` se mantienen | Ejecución. |
| Decisiones de ronda | `execution/campaign_runner.py`: `decide_round` → FD-EBQ (fase 2) | Ejecución. |
| Regla de `AGENTS.md` | Sustituir "never infer site equivalences" por "solo mediante `CoverageQualification` con F1–F8, bandas declaradas y sombra" | Gobernanza. |

---

## U. Lo que puede implementarse ya (seguro)

1. El inventario canónico y el modelo FDF único, en modo solo lectura.
2. La evidencia de estado desde la salida de referencia.
3. Las clases y bandas de operaciones, más `CoverageQualification` en modo **diagnóstico** (propone y registra, pero no reduce).
4. `response_reconstruction.py` y las comprobaciones gratuitas (reciprocidad y estabilizador).
5. Las herramientas retrospectivas de V1 sobre campañas archivadas.
6. El esquema `ResolvedPerturbationPlan` con `ALL_SUBSPACES` y `FIXED_PROTOCOL_GRID` (reproduce V6).
7. La reducción por traslación con ε=+1 y sombra obligatoria **comparada solo con cotas de impresión**. Es segura: los rechazos falsos solo expanden la clase.
8. La fase 1 de FD-EBQ (en curso).

## V. Lo que requiere validación primero

1. ε=−1 (V1 → V2 → V3).
2. Rotaciones (`EXACT_IN_CONTINUUM_ONLY`).
3. Cualquier modo de sombra opcional.
4. La activación de la α calibrada (FD-EBQ fase 2, T0–T4) y la escalera SCF (θ y \(\rho_{\max}\)).
5. Los valores de las bandas \(\tau_{\rm eq}\) y \(\tau_{\rm neq}\) por magnitud (deben anclarse en la resolución y probarse en V3).
6. La división automática de especies en producción.

## W. Lo que no debe implementarse

- Equivalencia por elemento, etiqueta, coordinación o "parecido químico".
- `DM.InitSpin` como evidencia magnética.
- Promediar o simetrizar columnas para "forzar" acuerdo, o simetrizar χ para ocultar asimetría (solo como reporte, con su norma).
- Usar la similitud de U entre sitios como prueba de equivalencia (es circular).
- Tolerancias absolutas fijas en la pendiente, o métricas relativas en elementos casi nulos.
- Muestreo heurístico de sitios representativos, truncamiento por localidad, modelos de bajo rango, pseudoinversa o regularización.
- Elegir bandas o tolerancias mirando el resultado.
- Pisos de ruido con réplicas en α=0.
- Eliminar la sombra "porque la teoría lo garantiza" antes de V4.

## X. Secuencia de implementación recomendada

1. Terminar FD-EBQ fase 1 (TASK 0–4, en curso).
2. Modelo FDF único e inventario canónico (U.1).
3. Evidencia de estado (U.2).
4. Operaciones, bandas y `CoverageQualification` en modo diagnóstico (U.3).
5. Reconstrucción y comprobaciones gratuitas, y V1 retrospectivo con informe (U.4–U.5).
6. Esquema `ResolvedPerturbationPlan` con `ALL_SUBSPACES` y `FIXED_PROTOCOL_GRID`; `campaign_v2` con `sites` opcional (U.6).
7. Reducción por traslación con ε=+1 y sombra por cotas de impresión (U.7), y V2 prospectivo.
8. Escalera SCF y FD-EBQ fase 2 (T0–T4), con `decide_round` reemplazado.
9. ε=−1 bajo bandera → V3 → habilitar.
10. Rotaciones → V2/V3 específicos.
11. Consolidación de producto (`hubbardflow run` y `hubbardflow submit`).

**El contrato del plan (esquema y máquina de estados) debe congelarse antes del paso 11.** La lógica científica que aún no está validada se entrega desactivada por bandera, nunca ausente del contrato.

---

## Y. Veredicto

1. **¿Puede HubbardFlow determinar automáticamente todos los subespacios correlacionados desde la FDF?** Sí, dentro de un subconjunto sintáctico auditado y con los archivos de entrada (PSML, `PAO.Basis`, `.ion`) para la identidad semántica. Fuera de ese subconjunto falla cerrado. El estado (magnético u orbital) **no** sale de la FDF: requiere la referencia SCF, que hace falta de todos modos.
2. **¿Puede determinar automáticamente cuántos sitios perturbar?** Sí: el número de órbitas de \(G_{\rm resp}\). Con el respaldo de perturbar todo cuando \(G_{\rm resp}\) no se establece.
3. **¿En qué condiciones exactas puede la simetría reducir ese número?** F1–F8: simetría de toda la estructura, identidad semántica de especies y de registros DFTU, invariancia magnética con ε global (ε=−1 solo en el caso colineal sin SOC con perturbación y observable independientes del espín), invariancia del estado de referencia, capa completa y malla k invariante para rotaciones, y clasificación de la discretización. Además, una sombra por clase consistente dentro de presupuestos.
4. **¿Es correcto el respaldo de perturbar todo?** Sí, y debe ser el valor por defecto ante cualquier ambigüedad, con expansión por clase cuando falla una sombra.
5. **¿Puede automatizarse la selección de α de forma defendible?** Sí, con FD-EBQ (presupuesto de error por elemento, orden verificado y aceptación en el espacio de U). Hoy solo con cotas de impresión; plenamente tras validar la escalera SCF.
6. **¿α global o por sitio?** Por columna y modo, sobre una red de candidatos común. Las clases de simetría comparten el protocolo de su representante.
7. **¿Deben BARE y SCREENED compartir malla?** No como requisito: la selección es independiente por modo y la red de candidatos es común.
8. **¿Es suficiente FDRC-v1?** No. Se reemplaza por FD-EBQ (revisión anterior más la errata) y, a nivel de sistema, por este planificador.
9. **¿Cuál es el mayor bloqueador científico pendiente?** La componente de error SCF independiente de α. Es invisible al análisis multiescala, ya visible en MnO (alrededor de \(2\times10^{-5}\) e entre columnas simétricas) y necesaria para que las sombras y la calibración de SCREENED no dependan solo de la impresión.
10. **¿Qué hay que validar antes de que los usuarios confíen en el planificador automático?** V1–V4 con cero falsos positivos en los controles negativos, más T0–T4 de FD-EBQ.
11. **¿Debe diseñarse y congelarse esta metodología antes de la consolidación más amplia?** Sí: el **contrato** (`ResolvedPerturbationPlan`, sus estados y su procedencia) debe congelarse antes. La activación científica puede ir después, detrás de banderas.
12. **¿Qué contrato `ResolvedPerturbationPlan` debe implementarse?**

```text
ResolvedPerturbationPlan(frozen, schema_version, digest)
  source_fdf_sha256, effective_fdf_sha256, inventory: CorrelatedSubspaceInventory
  reference: ReferenceEvidence (fdf, output, parent_dm, state evidence digests)
  coverage: CoverageQualification
      strategy ∈ {ALL_SUBSPACES, SYMMETRY_REDUCED, PARTIALLY_REDUCED, USER_RESTRICTED}
      classes[{members, representative, shadow?, status, ops, comparison}]
      reconstruction_maps{omitted J → (r, op_id)}
  calibration: per (J computed, mode)
      alpha_strategy ∈ {FIXED_PROTOCOL_GRID, USER_EXPLICIT_GRID, CALIBRATED_GRID}
      ColumnPlan (amplitudes, estimator spec + weights) ; CalibrationQualification
  computed_columns: [J]  (= representatives ∪ shadows ∪ expanded)
  run_specs: [(J, mode, ±a_k)]  → materialización determinista
  protocol_version, planner_version, backend identity, bands, τ_U (user)
  status ∈ {READY, REVIEW, NOT_ESTABLISHED, FAIL} + reason codes
```

---

### Apéndice: reproducción

```bash
# desde un checkout de codex/hubbardflow-rename
python coverage_review_checks.py .     # CoO V6 y MnO v3r2: ley de reconstrucción en datos archivados
python toy_symmetry_ring.py            # anillos de campo medio: ley exacta y contraejemplos
```
