# Adversarial scientific assurance for finite-difference LR Hubbard interactions

## Purpose and scientific boundary

This repository must not assert that a calculated interaction is immune to
scientific criticism.  That is neither possible nor a scientific standard.
Its stronger and testable objective is **fail-closed reproducibility**: every
mathematical or physical prerequisite for a stated result has a named evidence
gate, a machine-readable record, and a test that rejects an unsupported claim.

The implemented equation is the finite-difference linear-response definition

\[
  \chi^0_{IJ}=\frac{\partial n_I^{(0)}}{\partial\alpha_J},\qquad
  \chi_{IJ}=\frac{\partial n_I}{\partial\alpha_J},\qquad
  K=(\chi^0)^{-1}-\chi^{-1},\qquad U_I=K_{II}.
\]

Rows are observed manifolds \(I\); columns are perturbed manifolds \(J\).
No diagonal-only substitution, pseudoinverse, artificial charge-neutrality
projection, or automatic averaging over projector definitions is permitted.

This follows the finite-difference framework of
[Cococcioni and de Gironcoli (2005)](https://doi.org/10.1103/PhysRevB.71.035105).
Its most important implication is also explicit there: the result is tied to
the definition of the localized subspace.  It is not an element-wide constant.

## What SIESTA must mean

For SIESTA's DFT+U implementation, the declared Hubbard manifold is part of
the observable being calculated.  The input lock records the shell, projector
generation method, \(r_c\), \(\omega\), potential-shift convention, and the
exact pseudopotential.  In particular, SIESTA Method 2 uses pseudoatomic
solutions cut with a Fermi-like radial cutoff; `DFTU.PotentialShift` is the
documented switch intended for a local potential-shift response calculation.
See the [SIESTA DFT+U reference](https://docs.siesta-project.org/projects/siesta/en/latest/reference/siesta.html).

`DFTU.FirstIteration` makes the Hubbard term available on the first iteration,
but it does **not**, by itself, prove the time ordering required for
\(\chi^0\): first diagonalize \(H_{KS}[\rho_\mathrm{ref}]+\alpha P_J\), then
read the occupations before an Hxc rebuild from the perturbed density.  A
two-iteration job is therefore only a candidate BARE construction until a
native, executable-specific trace establishes that ordering.

## Required adversarial gates

| Gate | Attack it prevents | Required evidence | Fail-closed action |
|---|---|---|---|
| G1: subspace lock | changing the observable by changing projectors/pseudos | FDF + pseudo fingerprints; method, shell, \(r_c\), \(\omega\) | refuse LR/production comparison with unequal locks |
| G2: parent-state identity | each perturbation starting from a different electronic state | byte-level parent-DM hash copied to every child; reference completion | reject child without the declared parent hash |
| G3: BARE semantics | calling a later self-consistent density response \(\chi^0\) | version-specific native SIESTA trace that excludes Hxc rebuild before selected event | label candidate only; do not certify \(\chi^0\) |
| G4: screened convergence | using an unconverged response as \(\chi\) | normal completion, no SCF nonconvergence marker, selected final event | reject run |
| G5: finite-difference integrity | one-sided, swapped-sign, missing-column or label-order errors | signed \(\pm\alpha\), all-site occupation vectors, explicit row/column labels | reject incomplete/ambiguous matrix |
| G6: linear window | treating a nonlinear finite difference as a derivative | at least three signed amplitudes for a representative/full policy | declare the selected \(\alpha\) unsupported |
| G7: matrix policy | reporting raw data but inverting an undocumented symmetrization | persisted `matrix_for_inversion=raw|symmetrized`; raw and sym matrices retained | prohibit inversion without one policy |
| G8: inverse validity | hiding a singular response with numerical regularization | rank, singular values, condition number, both inverse residuals | no interaction matrix is emitted |
| G9: finite-size/state dependence | mistaking an image-coupled or metastable result for bulk \(U\) | \(U(L)\) series; reference magnetic/state audit | label as one-cell/state result only |
| G10: independent reconstruction | trusting only the campaign's own analysis code | parser reconstructs occupations, matrices, inverses and kernel from native outputs | reject mismatch with stored result |

## Implemented software safeguards

- The reusable matrix engine has one explicit `matrix_for_inversion` selector.
  The chosen representation, and not a separately reported representation,
  drives rank, conditioning, inversion residuals and \(U\).
- Raw and symmetrized \(\chi^0\) and \(\chi\) are retained together.  A
  symmetrization is a declared numerical reconstruction, never a silent data
  replacement.
- Direct `numpy.linalg.inv` is the only inverse accepted in LR code.  A
  rank-deficient or policy-ill-conditioned response raises an error; an
  historical pseudoinverse option now raises before calculation.
- The BARE selector distinguishes `CANDIDATE_BARE` from a verified BARE
  selection.  Promotion requires both an evidence reference and a positive
  assertion from a native SIESTA semantic trace that Hxc rebuild was excluded.

## Tests that must remain green

1. Exact synthetic recovery of full coupled \(\chi^0\), \(\chi\), and \(K\).
2. Off-diagonal retention, sign convention and row/column permutation tests.
3. Missing perturbation, duplicate semantic event and unconverged-screened
   rejection.
4. Singular and ill-conditioned response rejection; source-tree scan for
   pseudoinverse calls.
5. Raw-versus-symmetrized inversion-policy test.
6. Native-output archive audit that independently reconstructs the published
   matrices and direct inverse residuals.

## Claims permitted by the gates

When G1--G8 pass, the permitted statement is:

> A reproducible one-shot finite-difference interaction
> \(U_{LR}^{DFT}[P,\alpha,L,\mathrm{state}]\) was obtained for the declared
> SIESTA version, projector manifold \(P\), perturbation window, cell and
> reference electronic state.

Calling it a Cococcioni \(\chi^0\) result requires G3.  Calling it
supercell-converged requires G9.  Calling it self-consistent \(U_{scf}\) or a
structure--\(U\) self-consistent result requires an additional validated
frozen-prior-Hubbard-potential/relaxation loop; this repository must not infer
those claims from a one-shot PBE response calculation.

The same distinction between the Hubbard projector and the resulting
interaction is emphasized in modern DFPT work:
[Timrov, Marzari and Cococcioni (2022)](https://arxiv.org/abs/2203.15684).
