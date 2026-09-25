# MnO minimal-cell PBE+U validation

This is a four-atom AFM-II magnetic primitive-cell relaxation using the provisional linear-response value `U=11.53 eV`. It reuses the production campaign's Mn/O pseudopotentials, PBE, DZP basis, 200 Ry mesh, and Method-2 projector definition (`CutoffNorm=0.90`). The 6x6x6 k-grid preserves the reciprocal-space sampling density of the 32-atom campaign's 3x3x3 grid.

The run tests whether this U gives a stable AFM-II relaxed structure and reasonable Mn moment and Kohn-Sham gap at modest cost. Compare the final cell metric, Mn moment, gap, forces, and stress with bulk MnO reference data. This single magnetic-state calculation cannot establish that AFM-II is the ground state; that requires at least a competing magnetic configuration at the same settings and a consistent structural comparison. It also cannot certify the supercell/radius convergence of the U itself.

`U=11.53 eV` is the direct-inversion estimate from the existing response matrices; the repository's automatic analysis currently withholds a reportable U because of its separate matrix-acceptance gate. Treat this run as diagnostic evidence, not a production certification.
