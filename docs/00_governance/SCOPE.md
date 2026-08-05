# Scope & Governance Definition: SIESTAFLOW Hubbard Response Backbone

## 1. Primary Purpose & Mission Statement
The primary mission of **SIESTAFLOW** is to provide a robust, automated, and auditable Linear Response Hubbard $U$ calculation engine specifically for **SIESTA (v5.4.x)**.

### Why SIESTAFLOW exists:
* **Quantum ESPRESSO** has `hp.x` (Density Functional Perturbation Theory for Hubbard $U$).
* **SIESTA** has **NO native automated tool equivalent to `hp.x`** for computing $U$ from first principles. Users are forced to manually construct FDF perturbations, track occupation matrices, and execute linear regressions.
* **SIESTAFLOW fills this exact technological gap**, acting as the de-facto automated $U$ calculation backbone for the SIESTA community.

---

## 2. Architectural Boundary & Backend Policy

1. **SIESTA as First-Class Native Backend**:
   - `siestaflow_hubbard.siesta_backend` is the primary, fully supported production backend.
   - It natively manages FDF generation, `DFTU.proj` blocks, BARE response frozen-density overrides (`MaxSCFIterations 2`, `DM.MixingWeight 1.0`), and output parsing.

2. **Abstract Interface (`BaseBackendAdapter`)**:
   - The separation between the mathematical core ($U = \chi_0^{-1} - \chi^{-1}$) and the backend ensures that SIESTA's file parsing logic does not contaminate the physical inversion algorithms.
   - **Target Extension Codes**: Other DFT codes that ALSO lack native automated $U$ solvers (e.g., **VASP**, **CP2K**, **OpenMX**).
   - **Excluded Target**: Codes like Quantum ESPRESSO that already possess a native `hp.x` solver are explicitly out of scope.

---

## 3. Normative Scope Rules

- **MUST** prioritize SIESTA 5.4.x feature completeness and parser stability.
- **MUST NOT** include hardcoded material parameters or fixed physical assumptions.
- **SHALL** enforce automated physical quality gates ($R^2$, positivity, condition numbers).
