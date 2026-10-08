# HubbardFlow: Independent Review and End-to-End Perturbation Planning Design

**Scope.** This report responds to `CLAUDE_OPUS_HUBBARDFLOW_FULL_PERTURBATION_AUTOMATION_REVIEW.md` (sections A–Y). It covers the three scientific decisions that separate an authorized FDF from a production campaign:

1. which correlated subspaces exist (discovery);
2. which and how many must be perturbed independently (coverage);
3. which amplitudes α to use (calibration).

**Relation to the previous review.** `docs/fdebq/HUBBARDFLOW_FDRC_INDEPENDENT_REVIEW.md` and `docs/fdebq/ERRATA_I3.md` specified α calibration (FD-EBQ). This report **does not repeat it**. It summarizes it in sections I–M, couples it to coverage (section N), and places both within a single contract, `ResolvedPerturbationPlan` (section O).

**Branch audited:** `codex/hubbardflow-rename` @ `241d009` (contains `3c1398b` plus PR #5, which only adds configuration and documents). The frozen `scientific-v6-final` baseline (`45cb53c`) was used read-only.

**Reproducible materials** (outside the repository; nothing was written to it):
- `coverage_review_checks.py`: checks the reconstruction law on archived campaigns.
- `toy_symmetry_ring.py`: mean-field model with counterexamples.

All numbers in this report come from those scripts or the cited files. They are development data, not validation.

---

## A. Reconstructing the complete problem

For correlated subspaces \(I,J\) and mode \(m\in\{\mathrm{BARE},\mathrm{SCREENED}\}\):

\[
\chi^{(m)}_{IJ}=\left.\frac{\partial n^{(m)}_I}{\partial \alpha_J}\right|_{\alpha=0},\qquad U=(\chi^{0})^{-1}-\chi^{-1}.
\]

Perturbing subspace \(J\) produces the full column \(\chi^{(m)}_{:J}\). The dominant cost is approximately \(N_{\rm runs}\approx 2\,P\,A\) per mode (two signs, \(P\) targets, \(A\) amplitudes), plus references and controls. The problem has two coupled decisions and one constraint:

1. **Coverage.** Find the smallest target set \(\mathcal{R}\subseteq\mathcal{S}\) (where \(\mathcal{S}\) is the correlated-subspace inventory) such that **all** columns of \(\chi^0\) and \(\chi\) are obtained without approximation: either calculated directly or reconstructed exactly from calculated columns.
2. **Amplitudes.** For each calculated column and mode, choose an α window and estimator whose slope uncertainty is bounded or estimated and whose effect on \(U\) is below a user-declared tolerance.
3. **Constraint.** Neither decision may use the value of \(U\), its stability, the condition number, or agreement with literature. When evidence is insufficient, the result is explicit (`NOT_ESTABLISHED`, `REVIEW`, `AMBIGUOUS`) and the fallback is to perturb every site.

In brief: \(P\) is the number of **orbits** of correlated subspaces under a group \(G_{\rm resp}\) of operations that **provably** leave the response problem invariant. Sections D–G define this group. If \(G_{\rm resp}\) cannot be established, then \(G_{\rm resp}=\{e\}\) and \(P=|\mathcal{S}|\).

---

## B. Audit of the current implementation (`codex/hubbardflow-rename`)

| Component | File | Current behavior | Missing behavior or failure |
|---|---|---|---|
| Production site inventory | `execution/campaign_v2.py` (`validate_reference_fdf`, `validate_lr_config`, `resolve_fdf_includes`) | Resolves `%include`. Reads `ChemicalSpeciesLabel` and `DFTU.Proj` and requires **unique DFTU labels**. The user's `lr-config` must **list every DFTU site** with its `atom_index` and symmetric `alpha_grid_ev`. | Discovers nothing. `orbit_id` is metadata only. There is no production reduction. **It does not parse `AtomicCoordinatesAndAtomicSpecies`**, so it does not verify that each DFTU label is used by exactly one atom or that the declared `atom_index` has that species. |
| Symmetry detection | `src/symmetry_reduction_proposal.py` (`detect_symmetry`) | Tests only rotations that are **signed permutations of lattice axes** and infers translations by mapping atom 0. Requires identical species and labels. Compares moments as axial vectors (\(\det R\,R\,m\)). Marks ambiguity when there is more than one candidate. | Does not include time reversal or explicit spin flip. Through the current path (adapter, translations only), it **always rejects AFM sublattice exchange**. With declared scalar layers, a C2⊥z rotation would invert \(S_z\), stored as (0,0,Sz), and act as a flip **depending on the arbitrary choice of z axis**: this is an artifact of treating collinear spin as an axial vector (see E.4). Omits operations that are not signed permutations (rhombohedral or hexagonal cells); this is conservative, not incorrect. The fixed magnetic tolerance of \(10^{-6}\,\mu_B\) is smaller than the SCF spread of Mulliken moments. |
| FDF adapter | `siesta_backend/fdf_symmetry_adapter.py` | Supports only `AtomicCoordinatesFormat Fractional`, `LatticeConstant`, and `LatticeVectors`. The equivalence class is `Z + (n,l,U,J,rc,ω)` from `DFTU.Proj`, independent of label. Sets `complete_l_shell=False` and `rotationally_invariant=False`, so it **can authorize translations only**. | Computes only the FDF hash: it does not compare pseudopotential, `PAO.Basis`, or `.ion` content between labels. Does not resolve `%include` (unlike `campaign_v2`). |
| Magnetic evidence | `siesta_backend/reference_magnetic_evidence.py` | Final collinear Mulliken moments, hash-bound to the FDF and output. Does not use `DM.InitSpin`. | Does not read local occupation matrices, so it cannot detect symmetry-breaking orbital order. |
| Reduction plan | `domain/symmetry_reduction.py` | Groups orbits, selects a representative and shadow, generates ±α BARE/SCREENED specs, and explicitly falls back to all sites. Authorizes by orbit and expands rejected orbits. It is a good state-machine skeleton. | Policy contains **fixed literals** (`occupation_max_abs_e=2e-5`, `response_max_abs_e_per_ev=5e-5`, `response_max_relative_l2=1e-3`) that violate `AGENTS.md` rule 6 and do not scale with α. Uses one α. Not connected to `campaign_v2` or the runner. |
| Materialization | `siesta_backend/symmetry_materializer.py` | Rewrites the shift line in **every** `DFTU.Proj` record: α at the target site (with 4 decimals) and zero elsewhere, without changing other lines. Requires method 2 and `PotentialShift`. | Sound as a baseline: this is equivalent to "target only" because the reference requires zero shift. |
| Species splitting | `siesta_backend/fdf_builder.py::materialize_split_species_fdf` | Splits a shared label into `X0..XN-1` by rewriting `ChemicalSpeciesLabel`, `NumberOfSpecies`, and coordinates (preserves `DM.InitSpin`). Currently used only by scripts outside the production runner. | **Does not duplicate `PAO.Basis`, the `DFTU.Proj` entry, or pseudopotential per label**; the original label's DFTU entry becomes orphaned. If the base FDF defines an explicit basis per label, the new species silently change the physics (see section S). |
| Observable | `siesta_backend/event_parser.py`, `occupation_precision.py` | \(n_I=\mathrm{tr}\) of the occupation matrix over \(m\) and spin. The diagonal reader sums each token's rounding half-width and verifies that the sum matches `trace_total`. | Sound: this is a scalar observable invariant under spin flip. **Two caveats:** rejection of noncollinear/SOC is only implicit (`UnsupportedSpinFormat` is raised based on the field count in the `Occupations:` summary; `campaign_v2` has no explicit gate), and polarized three-token summaries use only the total token's half-step. |
| Perturbation | `symmetry_materializer.py`, `response_grid_semantics.py` | A single nonzero potential shift applied to one site in the U channel, with `DFTU.PotentialShift true`. It is spin-independent. | Sound. |
| α selection and stopping | `domain/adaptive_alpha_control.py::decide_round`, `alpha_selection.py`, `adaptive_alpha.py` | Adaptive rounds that stop when U stabilizes (`STOP_STABLE`). | Circular with respect to U; replaced by FD-EBQ (previous review, section I). |
| Historical reconstruction | `campaigns/mno_afmii_strict_lr_v3r2/scripts/lru_core.py` (`translated_column`, `reconstruct`) | MnO with 16 Mn: perturbed two representatives (A and B) and reconstructed the matrix by translations. | Campaign-specific *ad hoc* logic, not part of the package. It is valuable retrospective evidence (section D.4). |

**Audit conclusion.** Several components are sound: orbits with a shadow and fallback, safe materialization, a scalar observable, and a spin-independent perturbation. However, the system **cannot currently determine coverage automatically and defensibly**:

- detection does not account for spin flip;
- it does not verify that the reference state is symmetric;
- it does not verify that two labels have identical physics;
- it uses literal tolerances;
- and it is not connected to production.

---

## C. Discovering correlated subspaces

### C.1 What the FDF provides and what it does not

| Information | Source | Is the FDF sufficient? |
|---|---|---|
| Lattice and positions | `LatticeVectors`/`LatticeConstant`, `AtomicCoordinates*` | Yes, within a supported syntactic subset. |
| Atom → label → Z | `ChemicalSpeciesLabel`, species column | Yes. |
| Label → correlated subspace | `DFTU.Proj` (method 2: `n l`, `U J`, `rc ω`, optional λ) | Yes. |
| **Physical identity** of two labels | pseudopotential (PSML digest), `PAO.Basis` and basis options, generated `.ion` | **Only together with the input files**; the FDF alone is insufficient. |
| Magnetic state | reference SCF output (final Mulliken moments) | **No.** `DM.InitSpin` is an initial guess, not evidence. |
| Orbital state (orbital order, Jahn–Teller) | local occupation matrices from the reference | **No.** |
| Effective numerical grids | output (`InitMesh`, effective k-grid) | Partly; the output reports the actual grid. |

Conclusion: the **static** inventory comes from the FDF and its files; the **state** inventory comes from the SCF reference. The reference is needed in any case because it is the parent density matrix for all responses. Coverage is decided after obtaining it.

### C.2 Canonical map

```text
atom_index (1..N, AtomicCoordinates order)
  ↕ species_label (text, identifier only)
  ↕ species_identity_digest (PSML + PAO.Basis + opciones de base + .ion, sin la etiqueta)
  ↕ subspace_id = (atom_index, n, l)   ← scientific identity
  ↕ dftu_record_digest = (n,l,rc,ω,λ,U_ref,J_ref)
  ↕ response_index (position in χ, deterministic order by atom_index)
  ↕ output_atom_index (index in SIESTA occupation tables; verified bijection)
```

### C.3 Ambiguity rules (all fail closed)

1. **One DFTU label shared by multiple atoms.** Perturbing that label would shift all those atoms at once, which is not a single-site column. Automatic splitting into one label per site is allowed **only** if the new species are semantically identical to the original: same PSML (digest), exactly duplicated `PAO.Basis` blocks, duplicated `DFTU.Proj` entry, and `.ion` files identical except for the generated label. If this cannot be proven: `SUBSPACE_MAPPING_NOT_ESTABLISHED`.
2. **More than one DFTU record per label** (multiple shells per atom): `NOT_SUPPORTED` in the current version. The code already rejects this.
3. **FDF syntax outside the audited subset** (unresolved `%include`, ZMatrix, `LatticeParameters`, non-fractional coordinates without explicit normalization): `NOT_SUPPORTED`. Resolving `%include` must produce an effective FDF with its own digest.
4. **Noncollinear spin or SOC:** `NOT_SUPPORTED`. Rejection is currently only implicit in the parser; an explicit gate based on the FDF and output `redata` must be added.
5. **Unverified atom ↔ occupation-table bijection:** `FAIL`.
6. **Two distinct labels with the same physical identity:** not an error. A label is a name, not physical identity (`fdf_symmetry_adapter.py` already recognizes this).
7. **Same label but different contents** (different PSML or basis): the planner must treat them as distinct species and never as equivalent.

---

## D. Mathematics of perturbation coverage

### D.1 Reconstruction law

Let \(\theta\) be an operation on the Kohn–Sham Hilbert space: a spatial isometry \(g=\{R\,|\,t\}\), optionally combined with a global spin flip \(\varepsilon=-1\). Assume:

- **(H1) Functional covariance.** \(\theta\,H[\rho]\,\theta^{-1}=H[\theta\rho\theta^{-1}]\) for the full KS+U Hamiltonian, including numerical discretization (section D.3).
- **(H2) Reference-state invariance.** \(\theta\rho_0\theta^{-1}=\rho_0\).
- **(H3) Projector covariance.** \(\theta P_J\theta^{-1}=P_{g(J)}\) for each correlated subspace, where \(P_J\) is spin-independent and \(g\) induces a permutation of \(\mathcal{S}\).
- **(H4) Branch uniqueness.** For \(|\alpha|\) in the window used, the perturbed SCF solution is the unique continuation of \(\rho_0\) (there are no branch jumps).

Then, for perturbation \(V_J=\alpha P_J\), the perturbed density satisfies \(\rho[\alpha\,\text{at }g(J)]=\theta\,\rho[\alpha\,\text{at }J]\,\theta^{-1}\). For the scalar observable \(n_I=\mathrm{Tr}(P_I\rho)\):

\[
n_{g(I)}\big(\alpha\ \text{en}\ g(J)\big)=\mathrm{Tr}\!\left(\theta P_I\theta^{-1}\,\theta\rho\theta^{-1}\right)=\mathrm{Tr}(P_I\rho)=n_I(\alpha\ \text{en}\ J).
\]

For antiunitary \(\theta\), the trace is conjugated, but remains real because \(P_I\) and \(\rho\) are Hermitian. The result is exact **for every finite α**, not only for the derivative. Therefore:

\[
\boxed{\chi^{(m)}_{g(I),g(J)}=\chi^{(m)}_{I,J},\qquad \chi^{(m)}=\Pi_g\,\chi^{(m)}\,\Pi_g^{\mathsf T},\qquad \chi^{(m)}_{:,g(J)}=\Pi_g\,\chi^{(m)}_{:,J}}
\]

with \((\Pi_g)_{g(I),I}=1\). The law is the same for BARE and SCREENED. In BARE, the Hamiltonian is frozen at \(H[\rho_0]\): we need \(\theta H[\rho_0]\theta^{-1}=H[\rho_0]\), i.e. H1 **and** H2, plus H3 for the perturbation and observable; only H4 is unnecessary. Because the law holds pointwise in α, **reconstruct the raw data** \(n_I(\pm a_k)\), not only the slopes. FD-EBQ then applies identically to reconstructed elements.

### D.2 When fewer perturbations are sufficient

Let \(G_{\rm resp}\) be the set of operations satisfying H1–H4 (it forms a group if closed under composition). The orbits of \(G_{\rm resp}\) on \(\mathcal{S}\) partition the subspaces. Computing one column per orbit is **necessary and sufficient**:

- **Sufficient:** for every \(J\), there is a \(g\) such that \(g(r)=J\), and \(\chi_{:,J}=\Pi_g\chi_{:,r}\).
- **Necessary:** without an operation relating two sites, no exact relation allows one column to **replace** another. Reciprocity \(\chi_{IJ}=\chi_{JI}\) relates individual elements across columns (only for the derivative, not pointwise in α), but does not replace a full column; it is a test, not a reconstruction rule.

If multiple operations map \(r\) to \(J\), the reconstructions agree **if and only if** \(\chi_{:,r}\) is invariant under the stabilizer \(\mathrm{Stab}(r)\). This is a **free consistency check** on data already calculated.

One clarification: uncorrelated subspaces (ligands) are neither perturbed nor observed, but they **do** matter for H1 and H2 (geometry and moments of all atoms).

### D.3 Discretization must also be covariant

SIESTA does not solve the continuum. H1 requires the operation to preserve:

- **Real-space grid** (`MeshCutoff`). A translation \(t\) must map the grid onto itself (\(t\cdot N_{\rm mesh}\in\mathbb{Z}^3\) in fractional cell coordinates). A rotation \(R\) must leave the grid invariant. Otherwise the *egg-box* effect appears: a small but nonzero symmetry breaking.
- **k-grid.** \(R\) must leave it invariant. Translations introduce only phases and do not affect it.
- **Basis and pseudopotential.** They must be identical for \(J\) and \(g(J)\) (section C.1).

This defines two operation classes:

| Class | Definition | Consequence |
|---|---|---|
| `EXACT_IN_DISCRETIZATION` | Translation of the parent lattice commensurate with the real-space grid; species have semantic identity; k-grid is irrelevant. | Exact except for implementation errors (which the shadow detects). |
| `EXACT_IN_CONTINUUM_ONLY` | Rotations, incommensurate translations, or non-invariant k-grids. | Small numerical symmetry breaking; requires a shadow and, before activation, the validation program (section R). |

### D.4 Retrospective evidence from project data

There are archived campaigns in which **both** symmetry-related columns were calculated directly, so the law can be tested without running anything new (script `coverage_review_checks.py`):

**CoO V6** (2 Co on opposite sublattices; \(g\) = sublattice exchange with spin flip, \(\varepsilon=-1\)), in e/eV:

| mode | a (eV) | \(\chi_{00}-\chi_{11}\) | \(\chi_{01}-\chi_{10}\) | \(|\chi_{00}|\) |
|---|---|---|---|---|
| BARE | 0.02 / 0.04 / 0.06 | 0 / −1.25e-5 / −8.3e-6 | 0 / 0 / 0 | 1.35 |
| SCREENED | 0.02 / 0.04 / 0.06 | 0 / +1.25e-5 / −2.5e-5 | 0 / +1.25e-5 / −4.2e-5 | 0.117 |

The differences are one to a few print steps divided by \(2a\). The reference occupations differ by \(10^{-6}\) e.

**MnO v3r2** (16 Mn; columns A and B calculated; \(g\) = translation A→B with spin flip):

| mode | a (eV) | \(\max_I|\chi_{I,B}-(\Pi_g\chi_{:,A})_I|\) | × a (e) | print-only bound |
|---|---|---|---|---|
| BARE | 0.025 / 0.05 / 0.10 | 6.0e-4 / 3.0e-4 / 1.5e-4 | 1.5e-5 (constante) | 4.0e-4 / 2.0e-4 / 1.0e-4 |
| SCREENED | 0.025 / 0.05 / 0.10 | 8.0e-4 / 4.0e-4 / 1.5e-4 | 1.5–2.0e-5 | 4.0e-4 / 2.0e-4 / 1.0e-4 |

Interpretation:

1. The discrepancy is **constant at the occupation level** (about 1.5×10⁻⁵ e) and decreases as \(1/a\) in the slope. This is absolute-level noise, not a systematic symmetry violation, which would be constant in the slope. At \(a=0.10\) eV it is 0.1% of \(|\chi^0_{\rm diag}|=0.147\).
2. It exceeds the print-only bound by a factor of 1.5 to 2. Its origin (SCF tolerance of the parent DM or selection of the BARE event) is undetermined. This is precisely the α-independent term that the FD-EBQ review identified as invisible to multiscale diagnostics and that **becomes visible here by comparing two columns**.
3. The current policy (`response_max_abs_e_per_ev=5e-5`) would have **rejected** this equivalence at every α. A fixed absolute slope tolerance independent of α is ill-posed.

This is development and **post-hoc** evidence, not validation: only two systems, both AFM rock-salt oxides. In addition, for MnO the script constructs the permutation using Mn positions only (\(t=\mathbf r_{B0}-\mathbf r_{A0}\)) and does not verify that oxygen atoms also map: that \(g\) is a symmetry of the full structure is **assumed** (ideal rock salt), not demonstrated. Nonetheless, this directly supports allowing \(\varepsilon=-1\) under the conditions in section G.

### D.5 Synthetic counterexamples (`toy_symmetry_ring.py`)

Mean-field Hubbard ring with next-neighbor hopping (to break particle-hole symmetry), frozen BARE and self-consistent SCREENED. The table shows \(\max|\Pi\chi\Pi^{\mathsf T}-\chi|\):

| Case | Moments | χ⁰ | χ | Interpretation |
|---|---|---|---|---|
| Four-site ring, AFM, \(i\to i+1\) with spin flip | ±0.82 | 4e-12 | 2e-12 | The law with \(\varepsilon=-1\) is exact. |
| Four-site ring, AFM with site energies 0/0.8, \(i\to i+1\) | **±0.81 (equal magnitudes)** | **6e-3** | **6e-3** | **Identical moments are insufficient:** the hidden chemical environment breaks equivalence. Geometry (H1) is essential. (Same result on the six-site ring: 3e-3 with ±0.74.) |
| Same, \(i\to i+2\) | ±0.81 | 7e-12 | 1e-12 | The actual lattice translation is valid. |
| Six-site ring, symmetric geometry, state ↑↑↓↑↑↓, \(i\to i+1\) | 0.86, 0.86, −0.73 (×2) | **5.5e-2** | **4.0e-2** | **Spontaneous symmetry breaking:** the structure is symmetric but the state is not, so H2 is essential. |

---

## E. Symmetry reconstruction law in HubbardFlow detail

1. **Rows and columns.** \(\chi_{g(I),g(J)}=\chi_{I,J}\). Rows **and** columns are permuted using the same \(\Pi_g\), restricted to \(\mathcal{S}\).
2. **Projectors and local frames.** For \(R\neq I\), H3 requires the projector set \(\{\phi_{nlm}\}_m\) to be closed under \(R\). A complete \(l\) shell with the same radial function has this property (\(D^{l}(R)\) mixes only within \(l\)); in SIESTA method 2 the shell is always complete. Because the observable is the **trace**, the local frame does not matter: \(\mathrm{tr}\,D n D^{\mathsf T}=\mathrm{tr}\,n\). If the full occupation matrix is observed in the future (for example for Hund's J or orbital response), the law becomes \(n_{g(I)}=D^{l}(R)\,n_I\,D^{l}(R)^{\mathsf T}\) (plus ↑↔↓ exchange if \(\varepsilon=-1\)), and reconstruction must transform matrices rather than permuting scalars.
3. **Spin.** The perturbation is \(\alpha\sum_\sigma P_{J\sigma}\) (spin-independent) and the observable is \(\sum_\sigma\mathrm{tr}\,n_{I\sigma}\). Both are invariant under \(\sigma\to-\sigma\). A spin-resolved observable would transform as \(n_{I\uparrow}\to n_{g(I)\downarrow}\).
4. **Magnetic symmetry.** In collinear magnetism without SOC, spatial and spin degrees of freedom are decoupled (spin group). The relevant operations are \(g\) (with \(\varepsilon=+1\)) and \(g\circ\)spin-flip (with \(\varepsilon=-1\)); they do not act on spin as axial vectors. Therefore the current `detect_symmetry` rule (\(\det R\,R\,m\)) is incorrect as a general criterion without SOC, though conservative for translations. SOC or noncollinearity would require magnetic-group antiunitary operations. This is **out of scope** because the backend rejects those cases.
5. **Antiunitary operations.** They are unnecessary in the collinear, no-SOC case (global spin flip is unitary in spin space). If added, the trace remains real.
6. **BARE and SCREENED.** They obey the same law if the parent DM is the same (it is, by campaign construction) and is symmetric (H2).
7. **Occupation definition.** It is invariant if the parser sums the same tokens (complete shell) for every site. `occupation_precision.py` already verifies that the diagonal sum matches `trace_total`.

---

## F. Response-equivalence criteria

An operation \(\theta=(g,\varepsilon)\) belongs to \(G_{\rm resp}\) if and only if it satisfies **all** of the following:

| # | Condition | Evidence | Tolerance |
|---|---|---|---|
| F1 | \(g\) is a symmetry of the complete structure (all atoms) | Effective-FDF geometry | Geometric band |
| F2 | \(g\) preserves the **semantic species identity** of every atom | PSML, `PAO.Basis`, and `.ion` digests (label-independent) | Exact equality |
| F3 | \(g\) preserves the DFTU record of every correlated site | \((n,l,r_c,\omega,\lambda,U_{\rm ref},J_{\rm ref})\) | Exact equality |
| F4 | If \(R\neq I\): the shell is complete, the k-grid is invariant, and the operation is marked `EXACT_IN_CONTINUUM_ONLY` | DFTU record, effective k-grid | Exact |
| F5 | Magnetism: \(m_{g(s)}=\varepsilon\,m_s\) for **every** atom \(s\), with a single global \(\varepsilon\) | Final reference moments | Magnetic band |
| F6 | If \(\varepsilon=-1\): collinear spin, no SOC, spin-independent perturbation and observable | Backend contract and output (`redata`) | Exact |
| F7 | State: the local occupation-matrix spectra of \(s\) and \(g(s)\) match (with ↑↔↓ if \(\varepsilon=-1\)) | Reference occupation matrices | State band |
| F8 | Discretization: classify whether \(t\) is commensurate with the real-space grid | Output `InitMesh` | Exact |

**Band tolerances (no single threshold).** For each compared quantity \(x\) (geometric distance, \(|m_{g(s)}-\varepsilon m_s|\), spectral difference), the protocol declares two versioned tolerances, \(\tau_{\rm eq}<\tau_{\rm neq}\), and the result is:

- \(x\le\tau_{\rm eq}\): `EQUAL`;
- \(x\ge\tau_{\rm neq}\): `DIFFERENT`;
- in between: `AMBIGUOUS`. Any `AMBIGUOUS` result excludes that operation; if this leaves an orbit uncovered, record the reason.

\(\tau_{\rm eq}\) is anchored to the resolution of the quantity: the print step and declared SCF tolerance. It is **not** selected by looking at the result. This resolves tolerance-dependent classification: a nearly symmetric structure is `AMBIGUOUS` and all of it is perturbed.

**User-declared equivalences.** These are allowed only as **hypotheses**: a declared class is accepted only if an operation in \(G_{\rm resp}\) generates it. The declaration may **restrict** reduction (for example, the user disables it), but may never **add** equivalences that F1–F8 do not establish.

**Not criteria:** the same element, same label, same Wyckoff position without state, same coordination, or similar resulting U (that would be circular).

---

## G. Magnetic treatment

| Case | Allowed operations | Typical reduction |
|---|---|---|
| Nonmagnetic (`Spin non-polarized` verified in output) | \(\varepsilon=+1\) (spin flip is trivial) | By orbit of \(g\). |
| Ferromagnetic | Only \(\varepsilon=+1\); \(\varepsilon=-1\) fails F5 unless the moment is zero | By orbit of \(g\). |
| Compensated collinear AFM | \(\varepsilon=+1\) within each sublattice; \(\varepsilon=-1\) between sublattices if F1–F7 hold | Sublattices A and B in **one** class (CoO: 2→1; MnO: 16→1). |
| Ferrimagnetic (different magnitudes) | \(\varepsilon=-1\) impossible (F5 fails because \(|m|\) differs) | By sublattice. |
| AFM with inequivalent environments and equal \(|m|\) | F1 and F2 decide (counterexample D.5) | None between sublattices unless geometry relates them. |
| Magnetic symmetry broken by the state (orbital order, canting) | F7 fails | Perturb all affected sites. |
| Noncollinear or SOC | Out of scope (`NOT_SUPPORTED`) | Perturb all sites or reject the campaign. |

\(\varepsilon=-1\) is theoretically exact (sections D.1 and E.4) and supported retrospectively by CoO and MnO. Even so, it is enabled **by flag** only after the validation program (section R), because the two available cases share the same structural type.

---

## H. Safe fallback behavior

Perturb **all** correlated subspaces (`coverage_strategy = ALL_SUBSPACES`) when any of the following applies:

- reference evidence is missing (abnormal termination, unconverged SCF, incomplete moments or matrices);
- an `AMBIGUOUS` operation prevents covering an orbit;
- semantic species identity is not established;
- the syntax is unsupported;
- reduction is disabled by policy or the user (`DISABLED`);
- the system is small and the minimum orbit count is already \(|\mathcal S|\).

If a reduced orbit **fails its shadow**, expand that orbit (not the entire campaign) to explicit perturbations of its members, reusing already calculated data. `explicit_expansion_specs` does this today.

Per-class states: `PROVEN`, `CANDIDATE_PENDING_SHADOW`, `REJECTED_EXPANDED`, `NOT_ESTABLISHED`, `DISABLED`.
Global state: `ALL_SUBSPACES`, `SYMMETRY_REDUCED` (all reduced classes are `PROVEN`), or `PARTIALLY_REDUCED`.

---

## I. Audit of FDRC-v1 in the broader context

The conclusions from the previous review (`docs/fdebq/HUBBARDFLOW_FDRC_INDEPENDENT_REVIEW.md`) remain unchanged:

- FDRC-v1 is **replaced** by FD-EBQ;
- the noise floor from replicas at α=0 is invalid for deterministic SCF;
- U stability cannot be a stopping criterion;
- BARE and SCREENED have different error regimes;
- a common global grid is convenient, not required.

The broader context adds three consequences:

1. FDRC-v1 assumed targets had already been selected. Calibration now operates **only on representatives**, and the shadow inherits the representative's protocol (section N).
2. FDRC-v1 had no mechanism for comparing columns. Shadow–reconstruction comparison is a cross-falsification test that **does detect α-independent errors** (section D.4, item 2), which single-column multiscale analysis cannot see.
3. Fixed literals in `SymmetryReductionPolicy` and FDRC-v1 are replaced by FD-EBQ budgets.

---

## J. Recommended α-calibration methodology (FD-EBQ summary)

The complete specification is in the previous review (sections I–K) plus `ERRATA_I3.md` (R0–R2, `TAIL_UNRESOLVED`).

For each (column \(J\), mode \(m\), row \(I\)):

1. **Even/odd decomposition.** Central slopes are \(s_k=\frac{n(+a_k)-n(-a_k)}{2a_k}\); the even component does not affect the slope.
2. **Dominant-term order (R0).** Drift ratios \(\rho_p=\frac{a_{k+2}^p-a_{k+1}^p}{a_{k+1}^p-a_k^p}\) are compared with the observed interval and yield `VERIFIED_2`, `VERIFIED_1`, `UNRESOLVED`, or `INCONSISTENT`. Use \(p=2\) only when order 2 is verified; otherwise use \(p=1\) (conservative).
3. **Truncation (R1/R2).** \(\tau=\frac{|\Delta|+\nu_k+\nu_{k+1}}{q-1}\), with \(q=N^{(k+1)}/N^{(k)}\), and moments \(N=\sum w\,a^{p}\) computed exactly using fractions. Estimators that cancel \(a^2\) (Richardson, cubic) are allowed only with `VERIFIED_2`.
4. **Noise.** Print quantization (`BOUND`, sum of token half-steps) plus an SCF component (`ESTIMATE`) from an SCF-tolerance ladder (Phase 2). Bounds are **added**, not combined in quadrature.
5. **Falsification.** Consistency between neighboring estimators, reciprocity \(\chi_{IJ}\approx\chi_{JI}\), shadow–reconstruction consistency (new), and the state-consistency gate.
6. **Acceptance in U-space.** \(\partial U_{KK}/\partial\chi_{IJ}=(\chi^{-1})_{KI}(\chi^{-1})_{JK}\) (with the opposite sign for \(\chi^0\)), against a user-declared tolerance \(\tau_U\), plus \(\beta<1\) (invertibility over the full interval).
7. **Deterministic rounds** over a declared amplitude grid, with barriers and no historical counters or dependence on arrival order.
8. **States:** `QUALIFIED`, `QUALIFIED_HETEROGENEOUS`, `REVIEW`, `NOT_ESTABLISHED`, `NOT_DIFFERENTIABLE_AT_SCALE`, `FAIL`.

The conceptual model \(E(a)\sim C_{\rm num}/a+C_{\rm nl}a^2\) from the task is correct as intuition, but insufficient:

- \(C_{\rm num}\) has absolute, relative, and common-bias components; the last is invisible to multiscale analysis;
- the nonlinear term may be \(O(a)\) (non-analytic odd) rather than \(O(a^2)\);
- acceptance must be evaluated in U-space, not slope-space.

---

## K. Strategy for the numerical noise floor

This section retains the previous review (section K) with one empirical addition.

- **Rigorous bound:** print rounding, summing the half-steps of **all** tokens that form the trace (`occupation_precision.py`). Note: the previous review used \(5\times10^{-7}\) per occupation only as an illustration; for a d shell with two spins, the correct bound is the sum of 10 half-steps.
- **SCF estimate:** tolerance ladder (`SCF.DM.Tolerance` reduced by declared factors) on the odd difference \(\Delta(a)\), with a contraction test. This is the only source that measures convergence error without assuming it is random.
- **Not valid as a noise floor:** replicas at α=0 (deterministic calculations provide no statistics), last-SCF-iteration variations by themselves, and the "repeatability" of restarts from the same DM.
- **New: discrepancy between symmetry-related columns.** When two symmetry-related columns are calculated directly, their difference measures the α-independent error, on the order of \(2\times10^{-5}\) e in MnO. It is an **empirical lower bound** on effective noise, not an acceptable floor by itself.

**Open blocker:** the SCF ladder has not yet been validated (the θ and \(\rho_{\max}\) parameters from the previous review). Until then, budgets cover print precision only. This is safe for **coverage**: comparing a shadow against an overly narrow bound can cause false rejections that expand the orbit, which costs computation but does not compromise correctness. For **calibration**, however, there is a risk of underestimating SCREENED error; FD-EBQ therefore marks such results as `print-quantization bounds only`.

---

## L. Common α grid or per-site grid

**Decision: allow a grid per column and per mode, on a common candidate set.**

- **Mathematical justification.** \(\chi_{:J}\) depends only on perturbations of \(J\). Different columns are different experiments, and each can use its own estimator as long as its budget is correct. Nothing in the definition of \(\chi\) or \(U\) requires the same α for all columns.
- **Common candidate set.** Amplitudes come from a declared set (for example, \(\{a_1<\dots<a_K\}\) in the protocol). This allows pilot reuse, shadow–representative comparisons at the same points, and simple provenance.
- **Symmetry classes.** The shadow and reconstructed columns **must** use the representative's grid and estimator. Reconstructed columns inherit them by construction, and the shadow runs with the representative's resolved `ColumnPlan`. Calibrating the shadow independently would destroy comparability.
- **Matrix analysis.** Uncertainty varies by element. Propagation uses per-element influence and \(\beta\); no homogeneity assumption is made. `QUALIFIED_HETEROGENEOUS` makes this visible.
- **V6 reproduction.** `FIXED_PROTOCOL_GRID` applies the same grid to all columns and modes, unchanged.

---

## M. BARE versus SCREENED amplitude policy

**Decision: select independently by mode and use a common candidate set.**

BARE is truncation-dominated (in CoO, \(c_3\approx9.4\) e/eV³ and drift ratio 1.645 versus the theoretical 1.667), while SCREENED is noise-dominated. Forcing a common window makes one of them operate away from its optimum.

For \(U\), each matrix only needs its own budget: influence propagation treats \(\chi^0\) and \(\chi\) separately. A common window remains available as an explicit policy (for historical reproducibility), not as a scientific requirement.

---

## N. Coupling between coverage and calibration

1. **Order.** Determine coverage first (it requires only the reference), then calibrate, which applies only to representatives. Coverage does **not** depend on any response, except for the shadow, which only confirms or revokes it.
2. **Representative calibration suffices for its class.** By law D.1, the raw data for \(g(J)\) are an exact permutation of those for \(J\) at every α, so the window and estimator are valid for the whole orbit.
3. **The shadow is the empirical bridge.** For each class with more than one member, deterministically select **one** non-representative member: the one with the smallest `atom_index` among those reachable by an operation in \(G_{\rm resp}\). Run it with the representative's **already resolved** `ColumnPlan` (same α values and estimator), in both modes, and check for every \(I\) and mode \(m\) that

\[
\big|\hat\chi^{\rm dir}_{I,J'}-\hat\chi^{\rm rec}_{I,J'}\big|\le B^{\rm dir}_{I,J'}+B^{\rm rep}_{g^{-1}(I),r}
\]

using FD-EBQ budgets: absolute comparison per element, without relative metrics. Shadow columns are direct data and **are used directly** in the matrix (calculated data take precedence over reconstructed data).
4. **If the shadow fails,** revoke and expand the class. This does not reopen representative calibration, which remains valid for its own column.
5. **Cost.** One additional column per reduced class. In MnO with \(\varepsilon=-1\): 1 representative + 1 shadow = 2 columns instead of 16. With \(\varepsilon=+1\) only: 2 + 2 = 4 instead of 16.
6. **Free checks, requiring no new calculations:** reciprocity \(\chi_{r_1r_2}\) versus \(\chi_{r_2r_1}\) between representatives; invariance of \(\chi_{:,r}\) under \(\mathrm{Stab}(r)\); and row equivalence within each calculated column (\(\chi_{g(I),r}=\chi_{I,r}\) for \(g\in\mathrm{Stab}(r)\)).
7. **Validate multiple shadows per class?** Not by default. The law is exact under F1–F8, and the shadow detects mapping, species, or state errors, which would be systematic across the class. Additional shadows are useful only in the validation program (section R), not in production.

---

## O. Complete methodology: from the base FDF to `ResolvedPerturbationPlan`

```text
1. Base FDF ──resolve %include──► effective FDF (digest)
2. Static inventory: atoms, semantic species, DFTU records, map (section C.2)
   └─ ambiguity → NOT_SUPPORTED / SUBSPACE_MAPPING_NOT_ESTABLISHED (STOP)
3. Split species if one DFTU label covers multiple atoms (after verifying semantic identity)
4. SCF reference (parent DM) ──► state evidence: final moments, local occupation matrices,
   effective real-space grid, k-grid, normal termination
5. Cobertura:
   a. candidate geometric operations (conservative)
   b. filter F1–F8 with in-band tolerances → G_resp
   c. deterministic orbits, representatives, and shadows
   d. no useful G_resp → ALL_SUBSPACES
6. FD-EBQ calibration per representative and mode (deterministic rounds on the common grid)
   └─ states per element and column
7. Sombras con el ColumnPlan del representante → consistencia → PROVEN / REJECTED_EXPANDED
8. Expand rejected classes (reusing valid data)
9. Freeze ResolvedPerturbationPlan (digest) ──► CampaignPlan ──► campaign.lock ──► production DAG
```

Freeze the plan before production. Under `FIXED_PROTOCOL_GRID`, steps 6–7 reduce to the fixed grid, and explicit targets omit step 5: this reproduces V6 without reinterpretation.

---

## P. Deterministic algorithm (pseudocode)

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

**Determinism rules:**
- iterate everything in `atom_index` order;
- representatives are the minimum index in each orbit, and shadows are the next reachable index;
- make each round's decisions at its barrier, after all results for the round are available;
- task arrival order has no effect;
- no decision reads \(U\), its stability, or the condition number.

**Non-circular information flow:**

```text
COVERAGE VALIDITY      ← geometry, species, reference state, shadows
CALIBRATION VALIDITY   ← data from its own column (shadow only as falsification)
MATRIX CERTIFIABILITY  ← existing (rank, β, direct inversion)
U QUALIFICATION        ← all of the above + user-declared τ_U
```

No arrows point upward.

---

## Q. Evidence and provenance contract

`CoverageQualification`. Use the term "qualification," not "certificate."

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

`CalibrationQualification`: FD-EBQ `ElementBudgetReport` entries per (J, m, I), resolved `ColumnPlan` objects, rounds and their barriers, and digests of every output used.

Include everything in the `ResolvedPerturbationPlan` digest. Reuse pilots as production **only** when these match: effective FDF, parent DM, target subspace, exact α (representable in the FDF), mode, DFTU record, backend identity and version, SCF profile, parser version, magnetic state, and campaign scientific profile. Never reuse by filename or directory name.

---

## R. Validation program

| Phase | Systems | What it demonstrates | Criterion |
|---|---|---|---|
| V0, synthetic | Mean-field rings (this report); synthetic FD-EBQ (previous review) | The law and counterexamples | The law holds to machine precision for positive cases and all negative cases are detected. |
| V1, retrospective (no SIESTA) | CoO V6, NiO V6, MnO v3r2 A/B, Cu3N (X/Y/Z, evidence archive) | Consistency across already calculated columns | Shadow–reconstruction consistency within budgets; record the α-independent discrepancy. |
| V2, prospective shadows | MnO (translation ε=+1 and ε=−1), Cu3N (one translation per orbit; one X→Y rotation as `EXACT_IN_CONTINUUM_ONLY`) | Accuracy on the actual discretization | All shadows pass under budgets that include the SCF ESTIMATE. |
| V3, negative controls (must be rejected) | FeO or another state with orbital order; a ferrimagnet; a defective slab or supercell; a nearly symmetric structure within the band; species with the same label but different basis | No false positives | **Zero** false acceptances. |
| V4, holdout | Systems selected and frozen **before** runs (for example, NiO in another supercell or a non-rock-salt AFM) | Generalization | Protocol frozen; no post-hoc adjustment. |
| T0–T4 | FD-EBQ program from the previous review (SCF ladder, f20.12 references) | Calibration validity | As specified in the previous review. |

**What is enabled, and when:**
- Translation reduction with \(\varepsilon=+1\) and mandatory shadow: after V1 and V2.
- \(\varepsilon=-1\): after successful V1, V2, and V3.
- Rotations: after V2 and V3 and quantifying the egg-box effect.
- Optional shadow: never by default; only as an explicit policy after V4.
- Calibrated α: after T0–T4.

---

## S. Adversarial failure modes

| Failure | Manifestation | Detection or handling |
|---|---|---|
| Crystallographically equivalent but magnetically inequivalent sites | m differs in sign or magnitude non-globally | F5; magnetic band. |
| AFM with equal \(|m|\) but different environments | Apparent equivalence based on moments | F1 and F2 (counterexample D.5). |
| Same element, different projectors | Different DFTU records | F3 (exact equality). |
| Same label, different basis (or split without duplicating `PAO.Basis`) | Silent change in physics | F2 by digest; split only with semantic identity. |
| Symmetry broken by DM (orbital order) | Different local spectra | F7; if missed, the shadow fails. |
| Defects, surfaces, distortions | Operations are missing | Smaller orbits; natural fallback. |
| Near-symmetry | Distances fall within the band | `AMBIGUOUS` → no reduction. |
| Tolerance-dependent classification | Result changes with τ | Declared, versioned bands; `AMBIGUOUS` in the gray zone. |
| Nontrivial local axes | Shell rotation | Affects only non-scalar observables; the trace is invariant (E.2). |
| Spin inversion | Opposite sublattices | ε=−1 only with F6 and behind a flag until V3. |
| Different effective symmetry for BARE and SCREENED | A shadow passes in one mode and fails in the other | Evaluate shadows per mode; revoke the class if either fails. |
| Numerical symmetry breaking (egg-box) | Small discrepancy in rotational shadows | `EXACT_IN_CONTINUUM_ONLY` class; shadow; V2. |
| Branch jump under perturbation | Nonsmooth slopes, changing moments | State gate; `NOT_DIFFERENTIABLE_AT_SCALE`. |
| Nearly zero cross-responses | Unstable relative metrics | Absolute, budgeted comparisons; acceptance in U-space. |
| Ill-conditioned matrix | β near 1 | Existing certification; **never** an α-selection or coverage criterion. |
| Insufficient α signal | Unresolved drift | FD-EBQ: conservative p=1 for `UNRESOLVED`, or `NOT_ESTABLISHED`. |
| Contradictory windows across sites | Different estimators per column | Allowed; `QUALIFIED_HETEROGENEOUS`. |
| Class fails its shadow | Shadow does not match | Explicitly expand the class. |
| Map preserves geometry but not observables | Output label is permuted | Verified atom ↔ table bijection (section C.3, rule 5); shadow detects it. |
| Fixed slope tolerance | Rejects valid equivalences at small α (MnO) | Budget comparison, which scales as 1/a. |

---

## T. HubbardFlow integration (minimal)

| Change | File | Type |
|---|---|---|
| Change | File | Type |
| Canonical correlated-subspace inventory (pure) | **new** `domain/subspace_inventory.py` | Frozen dataclasses; no I/O. |
| Single FDF model (supported subset, atom ↔ label ↔ DFTU-record map, species identity) | **new** `siesta_backend/fdf_model.py`, consolidating duplicate parsing in `campaign_v2.py` and `fdf_symmetry_adapter.py` and reusing the existing `campaign_v2.resolve_fdf_includes` | Backend. |
| State evidence (local spectra, real-space grid, k-grid) | Extend `siesta_backend/reference_magnetic_evidence.py` (or add `reference_state_evidence.py`) | Backend. |
| Operations with ε, bands, and exactness classes | Extend `src/symmetry_reduction_proposal.py` → move to `domain/symmetry_operations.py` | Pure domain. |
| Reduction policy without literals; budgeted shadow comparison; multiple α | `domain/symmetry_reduction.py` | Domain. |
| Species splitting with semantic identity | `siesta_backend/fdf_builder.py::materialize_split_species_fdf` (duplicate `PAO.Basis`, `DFTU.Proj`, and PSML, and verify `.ion`) | Backend. |
| Raw-data reconstruction by permutation | **new** `domain/response_reconstruction.py` (generalizes `lru_core.reconstruct`) | Domain. |
| Per-column protocol | `domain/response_protocol.py` (TASK 1, branch `fdebq/task1-protocol`; not yet in the base branch) | In progress. |
| Plan contract | **new** `domain/perturbation_plan.py` (`ResolvedPerturbationPlan`) | Domain. |
| Production | `execution/campaign_v2.py`: optional `sites` in `lr-config` → planner fills it; explicit targets and `FIXED_PROTOCOL_GRID` remain supported | Execution. |
| Round decisions | `execution/campaign_runner.py`: `decide_round` → FD-EBQ (Phase 2) | Execution. |
| `AGENTS.md` rule | Replace "never infer site equivalences" with "only through `CoverageQualification` using F1–F8, declared bands, and a shadow" | Governance. |

---

## U. What can be implemented now (safely)

1. The canonical inventory and single FDF model, read-only.
2. State evidence from the reference output.
3. Operation classes and bands, plus `CoverageQualification` in **diagnostic** mode (proposes and records, but does not reduce).
4. `response_reconstruction.py` and free checks (reciprocity and stabilizer).
5. V1 retrospective tools for archived campaigns.
6. The `ResolvedPerturbationPlan` schema with `ALL_SUBSPACES` and `FIXED_PROTOCOL_GRID` (reproduces V6).
7. Translation reduction with ε=+1 and a mandatory shadow **compared only against print bounds**. This is safe: false rejections only expand the class.
8. FD-EBQ Phase 1 (in progress).

## V. What requires prior validation

1. ε=−1 (V1 → V2 → V3).
2. Rotations (`EXACT_IN_CONTINUUM_ONLY`).
3. Any optional-shadow mode.
4. Activation of calibrated α (FD-EBQ Phase 2, T0–T4) and the SCF ladder (θ and \(\rho_{\max}\)).
5. Band values \(\tau_{\rm eq}\) and \(\tau_{\rm neq}\) for each quantity (must be anchored to resolution and tested in V3).
6. Automatic species splitting in production.

## W. What must not be implemented

- Equivalence based on element, label, coordination, or "chemical similarity."
- `DM.InitSpin` as magnetic evidence.
- Averaging or symmetrizing columns to "force" agreement, or symmetrizing χ to hide asymmetry (reporting only, with its norm, is allowed).
- Using similarity of U across sites as evidence of equivalence (circular reasoning).
- Fixed absolute slope tolerances or relative metrics for near-zero elements.
- Heuristic sampling of representative sites, locality truncation, low-rank models, pseudoinverse, or regularization.
- Choosing bands or tolerances after looking at the result.
- Noise floors based on replicas at α=0.
- Removing the shadow "because theory guarantees it" before V4.

## X. Recommended implementation sequence

1. Complete FD-EBQ Phase 1 (TASK 0–4, in progress).
2. Single FDF model and canonical inventory (U.1).
3. State evidence (U.2).
4. Operations, bands, and diagnostic-mode `CoverageQualification` (U.3).
5. Reconstruction and free checks, plus V1 retrospective report (U.4–U.5).
6. `ResolvedPerturbationPlan` schema with `ALL_SUBSPACES` and `FIXED_PROTOCOL_GRID`; add optional `sites` in `campaign_v2` (U.6).
7. Translation reduction with ε=+1 and print-bound shadows (U.7), then prospective V2.
8. SCF ladder and FD-EBQ Phase 2 (T0–T4), replacing `decide_round`.
9. ε=−1 behind a flag → V3 → enable.
10. Rotations → targeted V2/V3.
11. Product consolidation (`hubbardflow run` and `hubbardflow submit`).

**Freeze the plan contract (schema and state machine) before step 11.** Scientific logic that has not yet been validated must ship disabled behind a flag, never omitted from the contract.

---

## Y. Verdict

1. **Can HubbardFlow automatically determine all correlated subspaces from the FDF?** Yes, within an audited syntactic subset and with input files (PSML, `PAO.Basis`, `.ion`) for semantic identity. Outside that subset it fails closed. The state (magnetic or orbital) does **not** come from the FDF: it requires the SCF reference, which is needed anyway.
2. **Can it automatically determine how many sites to perturb?** Yes: the number of orbits of \(G_{\rm resp}\), falling back to perturbing everything when \(G_{\rm resp}\) cannot be established.
3. **Under exactly what conditions can symmetry reduce that number?** F1–F8: symmetry of the full structure; semantic identity of species and DFTU records; magnetic invariance under a global ε (ε=−1 only for the collinear, no-SOC case with spin-independent perturbation and observable); invariance of the reference state; complete shell and k-grid invariance for rotations; and discretization classification. Also require one consistent shadow per class within the budgets.
4. **Is perturbing everything the correct fallback?** Yes, and it must be the default for any ambiguity, with class expansion when a shadow fails.
5. **Can α selection be automated defensibly?** Yes, with FD-EBQ (per-element error budget, verified order, and acceptance in U-space). Currently only with print bounds; full automation follows validation of the SCF ladder.
6. **Global α or per-site α?** Per column and mode, on a common candidate grid. Symmetry classes share their representative's protocol.
7. **Must BARE and SCREENED share a grid?** Not as a requirement: selection is independent by mode and the candidate grid is common.
8. **Is FDRC-v1 sufficient?** No. It is replaced by FD-EBQ (the previous review plus the erratum) and, at system level, by this planner.
9. **What is the largest outstanding scientific blocker?** The SCF error component independent of α. It is invisible to multiscale analysis, already visible in MnO (about \(2\times10^{-5}\) e between symmetric columns), and must be bounded so shadows and SCREENED calibration do not rely on print precision alone.
10. **What must be validated before users can trust the automatic planner?** V1–V4 with zero false positives in negative controls, plus FD-EBQ T0–T4.
11. **Should this methodology be designed and frozen before broader consolidation?** Yes: freeze the **contract** (`ResolvedPerturbationPlan`, its states, and provenance) first. Scientific activation can follow behind flags.
12. **Which `ResolvedPerturbationPlan` contract should be implemented?**

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
  run_specs: [(J, mode, ±a_k)]  → deterministic materialization
  protocol_version, planner_version, backend identity, bands, τ_U (user)
  status ∈ {READY, REVIEW, NOT_ESTABLISHED, FAIL} + reason codes
```

---

### Appendix: reproduction

```bash
# from a codex/hubbardflow-rename checkout
python coverage_review_checks.py .     # CoO V6 and MnO v3r2: reconstruction law on archived data
python toy_symmetry_ring.py            # mean-field rings: exact law and counterexamples
```
