# Phase 4 Reference Compatibility Audit

**Objective**: Investigate the exact methodology of REFERENCE generation vs BARE alpha=0 run to explain why $\alpha=0$ produces a changed occupation after the first diagonalization (restart drift).

## Field-by-Field Comparison

| Parameter | `MnO_ref.fdf` (Reference) | `MnO_val_+0.00_BARE.fdf` (BARE $\alpha=0$) | Status |
| --- | --- | --- | --- |
| Geometry / Cell | Identical (Rock-salt a=4.445) | Identical | MATCH |
| Basis & Cutoff | SZ, 150 Ry | SZ, 150 Ry | MATCH |
| k-grid | 1x1x1 (Gamma) | 1x1x1 | MATCH |
| Spin / Charge | polarized, no net charge | polarized, no net charge | MATCH |
| Electronic Temp | default | default | MATCH |
| XC | default | default | MATCH |
| **Projector Generation** | **`DFTU.ProjectorGenerationMethod 1`** | **`DFTU.ProjectorGenerationMethod 2`** | **MISMATCH** |
| **Explicit Projectors**| None (Uses PAO basis) | `%block DFTU.proj` with rc=3.0, omega=0.05 | **MISMATCH** |
| MaxSCFIterations | 50 | 2 | Expected for BARE |
| SCF Mixing | `DM.MixingWeight 0.1` | `SCF.Mixer.Method Linear`, `Weight 1.0` | Expected for BARE |
| DM Source | Initial guess / SCF | `DM.UseSaveDM true` (loads `MnO_ref.DM`) | Expected for BARE |

## Conclusion

**`DRIFT_EXPLAINED_BY_METHOD_CHANGE`**

The reference calculation converged its density using `DFTU.ProjectorGenerationMethod 1` (default PAO-based projectors). However, the Phase 4 validation suite overrides the FDF builder to use `DFTU.ProjectorGenerationMethod 2` and injects an explicit `%block DFTU.proj` (rc=3.0, omega=0.05) for the response calculation.

Because the underlying projection subspace changed between the reference run and the perturbation runs, the density matrix `MnO_ref.DM` (which is stationary with respect to the PAO-projector Hamiltonian) is no longer exactly stationary with respect to the new Hamiltonian that uses the `DFTU.proj` projectors. 

Thus, even at $\alpha = 0.0$, evaluating the Hamiltonian at the first SCF step produces a different density response, causing the observed drift. This is a methodological error in how the validation was setup (the reference should have been generated with the exact same projector definitions as the perturbation).

This method change fully explains the restart drift.
