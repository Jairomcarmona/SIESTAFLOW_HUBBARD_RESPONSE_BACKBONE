# Source Audit of the BARE Branch: SIESTA 5.4.2

## Scope and provenance

The official SIESTA repository tag `5.4.2`, cloned at
`third_party/siesta-5.4.2-source-audit`, was inspected statically at `HEAD`
`e486d12067b96ff688179f0496d0ec21b6fae0ab`. SIESTA, MPI, Hydra, and Slurm
were not built or run during this audit.

This document describes the semantics of the published source. The
institutional binary must still be compared with this version by checking its
version, hash/build recipe, and a small control; perfect identity with a
binary modified by an administrator is not assumed.

## Verifiable facts in the source

1. `SCF.MustConverge` is read in `Src/read_options.F90` and only decides
   whether lack of convergence at the end of the loop causes
   `ABNORMAL_TERMINATION`. It does not freeze Hartree--XC or by itself turn a
   calculation into BARE.
2. `DFTU.PotentialShift=true` forces `DFTU.FirstIteration=true` in
   `Src/dftu_specs.f`. The 5.4.2 manual states that the local shift allows
   recording the population change and obtaining `U` following
   Cococcioni--de Gironcoli.
3. Hamiltonian mixing is the default (`Src/read_options.F90`). With it,
   `Src/siesta_forces.F90` performs a `setup_hamiltonian(0)` preparation
   before the SCF loop. On the first actual step it runs `compute_DM(1)` and
   then `setup_hamiltonian(1)`.
4. `setup_hamiltonian` calls `hubbard_term` with `Dscf`. On the
   `PotentialShift` path, that routine constructs the local shift and emits
   projected populations (`Src/dftu.F`). Therefore, with Hamiltonian mixing,
   the population emitted during `setup_hamiltonian(1)` is calculated from
   the DM produced by diagonalizing the Hamiltonian prepared with the parent
   DM and the shift. The Hamiltonian is rebuilt after that diagonalization.

## Consequence for BARE selection

The candidate occupation for \(n^{(0)}\) on this path is the **second**
initial `hubbard_term` print with counter `1`: the one that appears after
`stepf: Fermi-Dirac step function` and before the first `scf: 1` line. The
first print with counter `1` belongs to the `iscf=0` pre-step and reflects the
parent DM. The DFT+U counter alone does not identify the SCF step because it
resets for `iscf <= 1`.

By contrast, under `SCF.Mix density`, the source runs
`setup_hamiltonian(iscf)` before `compute_DM(iscf)`. The first printable
perturbed population appears at the next Hamiltonian setup, when the path has
already incorporated the response DM. That configuration must not be
automatically promoted to \(\chi^0\) using the rule above.

## Finding about the current code

The historical builder materializes BARE with `SCF.Mix density`, two steps,
and the historical selector looks for a pseudo-`scf_iteration == 2`. This
rule is not derived from 5.4.2 source and cannot be certified as Cococcioni
BARE under the Hamiltonian-mixing profile described here.

This does not show that previous numbers are physically useless; it does mean
they must be classified as results under **historical semantics** until a
controlled comparison is done. Do not reuse the label `VERIFIED_BARE` for
them.

## Corrective profile integrated in isolation

The profile `siesta-5.4.2-potential-shift-hamiltonian-v1` was added in
`src/siestaflow_hubbard/siesta_backend/siesta542_bare_profile.py`. It requires:

- `DFTU.PotentialShift true`, `DFTU.FirstIteration true`;
- `DM.UseSaveDM true` and a parent DM with a matching hash;
- explicit `SCF.Mix Hamiltonian` (not relying on the default);
- one useful SCF step for BARE; `SCF.MustConverge false` only allows the
  non-self-consistent control to terminate; it is not evidence of freezing;
- a context parser that selects the block after `stepf` and before `scf: 1`,
  not a generic DFT+U counter;
- a regression test on retained real output and a minimal local/HPC control
  with the institutional module.

The profile selects only the population block strictly between those two
markers and rejects results without the Hamiltonian-mixing signature. Its
focused tests cover retained real MnO output, explicit FDF materialization,
density mixing, and missing markers.

Integration with the production executor remains intentionally separate: the
historical BARE validator still fails closed. Before authorizing a new
campaign, this profile must be linked to a verifiable recipe/version of the
institutional binary and a small control must demonstrate that signature.
This avoids both altering SCREENED and reinterpreting archived campaigns.
