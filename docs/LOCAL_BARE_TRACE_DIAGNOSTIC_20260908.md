# Local BARE diagnostic trace status

This note records what is and is not demonstrated by the local SIESTA 5.4.2
example currently present in the repository. It is diagnostic evidence only;
it does not authorize a Hubbard-U result by itself.

## Observed native output

Input/output pair: `examples/MnO_BARE_+0.05.fdf` and
`examples/MnO_BARE_+0.05.out`.

The output contains the following ordered events:

| Event | Output line |
|---|---:|
| `DFTU.PotentialShift true` | 68 |
| DM read succeeded | 605 |
| local occupations, cycle 1 | 623 |
| Hubbard Hamiltonian rebuild | 654 |
| local occupations, cycle 1 (second internal call) | 657 |
| Hubbard Hamiltonian rebuild | 688 |
| local occupations, cycle 2 | 718 |
| Hubbard Hamiltonian rebuild | 749 |

This proves that the supplied run read a DM and that SIESTA entered the DFT+U
occupation/Hamiltonian code path. It does **not** identify, in the native text,
which population is the response population after a perturbation or expose the
exact Hxc-rebuild boundary.

## Instrumented runtime trace

An isolated source copy of the official SIESTA 5.4.2 release was instrumented
outside this repository at
`C:/Users/Jairo/Downloads/SIESTAFLOW_CONTEXT/siesta-5.4.2-audit`.
The diagnostic-only markers are placed at:

- `Src/m_new_dm.F90`: accepted continuation DM;
- `Src/dftu.F`: population evaluation and perturbation Hamiltonian build,
  including `iscf` and the population-cycle counter;
- `Src/setup_hamiltonian.F`: immediately before the `dhscf` Hxc rebuild,
  including `iscf`.

An isolated, patched copy of the official SIESTA 5.4.2 source was built
serially in WSL and run against the repository input
`examples/MnO_BARE_+0.05.fdf` with its continuation DM and PSML files. The
instrumented executable SHA-256 was
`0c1f097f0d1b97ffd813cda947670c349da1d510146714255a6d892b8fef6b18`.
The source release audited was official SIESTA tag `5.4.2`
(`e486d12067b96ff688179f0496d0ec21b6fae0ab`).

The relevant emitted events were:

| Output line | Observed event |
|---:|---|
| 603 | continuation DM accepted |
| 623 | population evaluated: `iscf=0`, population cycle 1 |
| 655 | perturbation Hamiltonian built: `iscf=0`, population cycle 1 |
| 656 | immediately before Hxc rebuild: `iscf=0` |
| 660 | population evaluated: `iscf=1`, population cycle 1 |
| 692 | perturbation Hamiltonian built: `iscf=1`, population cycle 1 |
| 693 | immediately before Hxc rebuild: `iscf=1` |
| 724 | population evaluated: `iscf=2`, population cycle 2 |
| 756 | perturbation Hamiltonian built: `iscf=2`, population cycle 2 |
| 757 | immediately before Hxc rebuild: `iscf=2` |

The diagnostic output and error-stream SHA-256 values were respectively
`7a9417b8a873c45487a78aa7c3f10aa9d53076f6011ecef9dc839bdf6be2b2bf`
and `388aaee5630fb7b11dceb23abd6033f336367ff9683616553e83129e3a057d88`.
The source marker called “perturbation Hamiltonian built” was deliberately
moved from its initial, incorrect placement immediately after zeroing the
Hamiltonian to after the construction loop. Thus the wording in the table is
now supported by the source control flow rather than merely by a nearby log
message.

The original example intentionally specifies only two SCF iterations and,
without an explicit BARE policy, emits `SCF_NOT_CONV` and
`ABNORMAL_TERMINATION`. Its trace proves execution order only; it cannot
authorize a BARE response or a value of \(U\).

A second MPI-4 local run added the explicit BARE declaration
`SCF.MustConverge F`. It emitted the expected `SCF_NOT_CONV` warning but ended
normally, with no abort. Its trace was accepted by the certificate writer. The
certificate binds the input FDF, continuation DM, executable, transcript and
selected `iscf=2` event by SHA-256. This distinction is essential: a BARE run
may intentionally not converge the density, whereas a reference or screened
run must remain converged and is rejected otherwise.

## MPI-4 diagnostic equivalence

The same patched source was also compiled in a separate OpenMPI/ScaLAPACK
build and executed with four MPI ranks. Its executable SHA-256 was
`22aceb36c2d083a2748328007ed14e2997f609ad97a8df010288e704bbca9c63`.
The MPI trace emitted the same ordered events and the same two SCF numerical
records as the serial diagnostic run; only transcript line numbers changed due
to the parallel header. In particular, its selected cycle was observed as
population evaluation at line 738, perturbation-Hamiltonian completion at 770,
and the immediately following Hxc boundary at 771.

It also terminated with the expected two-iteration `SCF_NOT_CONV` condition.
This establishes that MPI-4 does not alter the audited ordering for this
diagnostic input. It is not a numerical equivalence study and remains
non-authorizing for \(U\).

## Converged-certificate integration attempt

A separate disposable local run was attempted with the reference input's
larger SCF limit, followed by a BARE input seeded from the generated reference
DM. The audit build did not converge the reference after 50 iterations and
terminated with `SCF_NOT_CONV`. No reference evidence was accepted. This is
the intended fail-closed outcome: convergence behavior of a locally compiled
diagnostic executable is not silently substituted for the validated HPC
executable.

The package now exposes `write_bare_semantics_sidecar`. It can create a
certificate only from a normal, non-aborted BARE transcript whose hashed FDF
explicitly declares `SCF.MustConverge F`, containing exactly one selected set
of source-level markers. It binds the executable, parent DM, FDF, output,
trace, source revision, and selected parser interval by SHA-256. Its focused
tests reject aborts, missing BARE policy declarations, and reordered traces.

## Gate status

`DIAGNOSTIC_ORDER_TRACE_ESTABLISHED_NONAUTHORIZING`. The existing `.out` and
the instrumented runtime trace establish the intended local order, while the
fail-closed BARE semantic gate remains correct: it must reject this particular
non-converged run and accept only a complete, converged trace whose markers and
provenance satisfy the parser.
