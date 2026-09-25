# MnO linear-response handoff for independent review

Date: 2026-09-25. This document identifies what the repository currently
demonstrates, where the primary evidence lives, and the questions an independent
review must settle. It does not certify a production Hubbard parameter.

## Start here

1. Read [`MNO_MATH_CODE_AUDIT_20260923.md`](audits/MNO_MATH_CODE_AUDIT_20260923.md)
   for an independent reconstruction of the numerical matrix inversion.
2. Read [`MNO_SCALAR_SPIN_FUNCTIONAL_MISMATCH_20260923.md`](audits/MNO_SCALAR_SPIN_FUNCTIONAL_MISMATCH_20260923.md)
   and [`NUCLEO_MATEMATICO_FISICO_SIESTA_ADVERSARIAL_20260924.md`](audits/NUCLEO_MATEMATICO_FISICO_SIESTA_ADVERSARIAL_20260924.md)
   for the mathematical and functional-definition issues.
3. Read [`SIESTA_OUTPUT_TRACE_RECONSTRUCTION_MNO_20260921.md`](audits/SIESTA_OUTPUT_TRACE_RECONSTRUCTION_MNO_20260921.md)
   and [`SIESTA_542_BARE_SOURCE_AUDIT_20260909.md`](audits/SIESTA_542_BARE_SOURCE_AUDIT_20260909.md)
   before interpreting the BARE population selected from SIESTA 5.4.2.

## What the saved MnO campaign contains

The frozen input is a 32-atom AFM-II MnO supercell with 16 Mn response sites.
The response archive contains one reference SIESTA output plus 28 BARE/SCREENED
outputs: representatives A and B at seven alpha values each, in both modes.
The alpha grid is -0.10, -0.05, -0.025, 0, +0.025, +0.05, +0.10 eV. The
response analyzer measures the printed total Mn-3d occupation, summing both
spin channels, and reconstructs 14 unperturbed columns of each 16x16 matrix by
translation from the two directly measured representative columns.

The exact response inputs and selected outputs are under
`campaigns/mno_afmii_strict_lr_v3r2/results/response-matrix-foreground-recovery-v4/`.
`response-receipt.json` binds the run records and output hashes. The 29
`siesta.fdf` and 29 `siesta.out` files in that directory are included for
independent re-reading; density matrices, Hamiltonian files, runtime
environments, and Slurm logs are not part of this Git handoff. Campaign locks,
source material, geometry, pseudopotentials, the response script, and the
historical 0.1.2 wheel are included. A fresh SIESTA execution requires a
compatible SIESTA 5.4.2 installation; it is not implied by this archive.

The five admitted zero-shift calibration replicas are also included as 25
native `siesta.out` files, their FDF inputs, five `replica-result.json`
receipts, and `calibration-result.json`. The excluded interrupted attempt and
all runtime directories are omitted. This permits an independent audit of the
recorded 5e-5-electron noise policy without treating the policy as proof of a
complete uncertainty budget.

## Numerical result and its limits

Reconstructing the saved occupation totals gives
`U_scalar_charge = 11.532055666425 eV` with symmetrized matrices, and
`11.532055662576 eV` without symmetrization. The BARE and SCREENED matrix
condition numbers are approximately 2.005 and 1.254. Fits using maximum
absolute alpha of 0.025, 0.05, and 0.10 eV give 11.5370, 11.5327, and
11.5321 eV. These overlapping windows support local linearity of this scalar
estimator; they are not independent validation experiments.

The original `analysis-result.json` and
`analysis-result-signal-gate-v1.json` report a failed scientific gate and no
accepted U. The later `analysis-result-corrected-v1.json` gives a numerical
point estimate and a 11.472-11.592 eV interval for the widest window. That
interval propagates printed decimal rounding only. It does not cover SCF
error, basis, k mesh, cell, projector, symmetry reconstruction, or the
functional-definition issue. The different analysis statuses must remain
visible; a numerical interval must not be relabeled as a scientific PASS.

The following command re-reads the saved outputs and writes a new analysis
outside the frozen archive; it does not run SIESTA:

```bash
PYTHONPATH=src SIESTAFLOW_MNO_RESPONSE_RESULTS=response-matrix-foreground-recovery-v4 \
  python3 tools/run_mno_afmii_response_quantized_v1.py analyze \
  --output /tmp/opus-mno-reanalysis.json
```

In the 2026-09-25 WSL check, it verified 28 response outputs and reported
`PRINT_ROUNDING_INTERVAL_ACCEPTED`, 11.532055666425 eV, and the
11.472088914582-11.592022418269 eV print-rounding interval. That label has
the limited meaning stated above, irrespective of the older archived result
labels.

The applied perturbation is identical in both spin channels. Consequently,
the saved calculations determine a total-charge response, not every element of
the spin-resolved susceptibility. SIESTA's normal DFT+U branch uses the
spin-channel `U-J` coefficient of a Dudarev-type potential. No validated
mapping from the archived scalar response to that coefficient has been shown.
The exploratory FDF that inserted 11.53 eV as a DFT+U input does not validate
this identification or MnO observables.

## Questions for independent review

1. Verify the response observable and BARE/SCREENED event selection against
   the 29 native outputs and the audited SIESTA source order. Report a concrete
   counterexample if the selected population is not the intended response.
2. Reconstruct the two measured susceptibility columns directly from the
   printed occupations and check alpha fits, units, signs, reference offsets,
   and inversion without using the saved analysis JSON as input.
3. Determine whether the A/B translations truly generate the other 14
   response columns for this magnetic structure and numerical run. Separate
   proven crystallographic symmetry from an untested computational assumption.
4. Specify the response tensor or derivation required to obtain the parameter
   actually used by SIESTA's DFT+U functional. Do not infer its magnitude or
   direction from the scalar 11.532 eV estimate alone.
5. Review whether the signal gate's rule for weak matrix channels and the
   available occupation precision justify accepting or rejecting the scalar
   matrix estimate. Distinguish print rounding from reproducibility noise.
6. Review the current reusable software changes and their tests against the
   defects catalogued in the adversarial core audit. Treat the archived
   campaign result as immutable while evaluating current source code.

The primary objective is a physically defined, reproducible parameter with
honest uncertainty, not a numerically smaller U. Any proposed code change
should state whether it changes the archived scalar estimate, the acceptance
decision, or the definition of the parameter being calculated.

## Current source validation and version caveat

The source tree includes later reusable-software changes. The campaign's
historical software lock and wheel identify the code used to generate its
archived outputs; a present-day source checkout is not byte-identical to that
lock. Do not rewrite the frozen lock to make it match later source changes.

On 2026-09-25, a WSL run of
`PYTHONPATH=src python3 -m pytest -q tests/unit tests/backend tests/execution tests/adversarial tests/algebraic`
was interrupted after 172 passes and nine failures. The failures include a
test that still expects a disabled context-only BARE promotion, three legacy
material FDF tests affected by the new unique-target requirement, a legacy
BARE completion expectation, a Cu3N shadow function-signature mismatch, and
three Cu campaign tests whose frozen software hash no longer matches the
current `pyproject.toml`. These failures are unresolved in this handoff; they
must be triaged rather than silently rebaselined. No SIESTA calculation was
launched as part of this GitHub update.

Two focused WSL checks passed: 81 backend-admission and runtime tests (the
GitHub workflow selection) and 54 response-math, parameter-semantics,
precision, alpha-selection, and projector tests. All 54 staged native
`siesta.out` files and the five staged calibration receipts match the SHA-256
values in their parent receipts byte for byte. The historical source lock
still differs from the present source checkout as described above.
