# Published validation regressions

This regression set records repository evidence and its provisional comparison
tolerances. The tolerances are centralized in
`tests/unit/validation_tolerances.py`, marked `PROVISIONAL`, and await owner
review. They are for reproducing recorded values only; they do not qualify a
physical result, set a Hubbard-U acceptance criterion, or authorize a campaign.

| Case | Regression and repository evidence | Provisional tolerance | Status and limit |
|---|---|---:|---|
| MnO Yoltla vs laptop | Compare paired outputs for the same declared MnO calculation. Existing MnO audit data are not a paired laptop run. | Pending; no value assigned | `xfail`: `PENDIENTE_MNO_LAPTOP_ARTIFACT`. No substitute campaign is used. |
| Cu3N by translation symmetry | Recheck the eight translation permutations against the archived 24-site matrices in `docs/evidence/cu3n_mathematical_20260812/CU3N_PBE_LRU_SC222_RC3p0_V1.json`; retain the three-orbit site-U summary. | Matrix residual `0`; U-spread recomputation `1e-12 eV` | Archive self-consistency passes. It is not an independent shadow validation. The direct-shadow package regression remains xfailed because its source FDF is absent. |
| One-column probe vs full campaign | Compare the M1 one-column U `10.6622 eV` with the archived 36x36 range `[10.6578, 10.6586] eV` in `tests/fixtures/projector_curve_m1.json`. The recorded maximum delta is `0.0044 eV`. | `1e-4 eV`, the sum of the two four-decimal half-quanta | Passes as a record-only consistency check; it does not impose an acceptance threshold. |
| Projector scan | Reproduce the nine measured M1 CutoffNorm points from the same JSON fixture and the table in `docs/03_policies/PROJECTOR_SCAN_EXECUTABLE_SPEC.md`. | `5e-5 eV`, one half-quantum at four decimal places | Passes for these sampled values only. It makes no claim about unsampled norms or a general plateau. |
| chi0 response selection | `tests/unit/test_lr06_trace_excerpt.py` uses the verified Yoltla SIESTA 5.4.2 trace extract and checks the selected BARE population, its line boundary, and the first indented SCF marker. | `5e-7 electron`, one half-quantum at six decimal places | Passes for the excerpt and the audited profile. The trace is a small extract; it is not a complete campaign artifact. |
| Resume after signal termination | A full campaign-attempt record terminated by a signal and then resumed is not checked into the repository. Component coverage exists in `test_runtime_adapters.py` and the NIO replay's separate run/resume test. | Not numeric; exact state assertions | End-to-end regression is `xfail`: `PENDIENTE_SIGNAL_RESTART_ARTIFACT`. Component tests do not prove that missing scenario. |

The existing Cu3N direct-shadow test is also left xfailed by
`tests/known_failures.txt`: `tests/unit/test_cu3n_symmetry_shadow_package.py::test_fdf_mutation_changes_only_the_declared_target_shift`
requires `CU3N_PBE_LRU_SC222_RC3p0_V1/runs/10_X_BARE_MINUS/siesta.fdf`. The
archived mathematical JSON records reconstructed matrices, not a direct
perturbation of a translated Cu site.

Run the focused suite with:

```bash
python -m pytest -q \
  tests/unit/test_published_validation_regressions.py \
  tests/unit/test_projector_plateau.py \
  tests/unit/test_lr06_trace_excerpt.py
```

## Validation without a cluster

The mathematical validation path uses `hubbardflow.synthetic_backend` and the
repository's algebraic/unit tests. Its population generator, noise injection,
matrix assembly, fitting, and recovery modules provide reproducible synthetic
inputs without a scheduler or SIESTA. This checks numerical/software behavior;
it cannot establish agreement with a real SIESTA execution, validate a site's
MPI setup, or replace missing campaign evidence.

## HPC profile interface

The profile is an explicit runtime input, separate from scientific campaign
policy. The public schema is
`docs/schemas/execution-profile.schema.json`; the site-neutral controller and
site-plugin boundary are specified in
`docs/HPC_SLURM_EXECUTION_CONTRACT.md`. `docs/03_policies/HPC_PROFILE.md`
describes how a site profile maps to that interface and uses Yoltla as the
historical Slurm example. Concrete partitions, accounts, module names,
executable paths, resource limits, and launcher details must come from the
current site's administrator and a live profile. They are not inferred from
the older archived deployment guide.
