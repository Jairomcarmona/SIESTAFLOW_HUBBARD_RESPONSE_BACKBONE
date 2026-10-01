# HubbardFlow 0.1.2 — Technical User Manual

HubbardFlow runs SIESTA linear-response charge campaigns and records their inputs, node receipts, analysis, and report. This manual describes the installed CLI in release 0.1.2. It does not promise a physically accepted or universal Hubbard parameter for every material.

The completed P0–P6 product closure is recorded as `PRODUCT_BLOCKED`: the CLI
and P5 campaign completed, while the NiO result remains
`NUMERICAL_CANDIDATE_UNASSESSED` / `NOT_ESTABLISHED` for the scientific objective
required by the user. See the [final execution record](P0_EXECUTION_20260928.md)
and the [repository synchronization inventory](ESTADO_REPOSITORIO_Y_PUBLICACION_20260929.md).

## Scientific quantity

For correlated sites `I` and perturbation sites `J`, the analysis forms

\[
\chi^0_{IJ}=\left.\partial n_I^{\mathrm{BARE}}/\partial\alpha_J\right|_0,
\qquad
\chi_{IJ}=\left.\partial n_I^{\mathrm{SCREENED}}/\partial\alpha_J\right|_0,
\qquad
U_I=[(\chi^0)^{-1}-\chi^{-1}]_{II}.
\]

The versioned result is `U_scalar_charge`, with the occupation source and projector convention stated in the JSON and Markdown report. It is not relabeled automatically as `Ueff_Dudarev`; SIESTA's collinear Dudarev input uses `U-J`, which needs its own physical contract. An off-diagonal matrix value is not automatically a functional's `V`.

Schema v3 uses `occupation_source=siesta_occupations_total` when the selected SIESTA `Occupations:` total is the adjusted observable. The rounding interval, matrix inversion, fit-window and model diagnostics, SCF state, branch/projection checks, and per-site result remain distinct fields. A missing scientific U tolerance yields `NUMERICAL_CANDIDATE_UNASSESSED`; that status can be a valid terminal campaign result and does not establish physical acceptance. Numerical output, convergence, and physical acceptance are separate claims.

## Install and inspect an input

Install the release wheel in the Python environment that will run the CLI. For PowerShell → WSL, install it both in Windows Python and in the selected WSL distribution; the wheel does not include SIESTA or MPI.

```powershell
py -m pip install .\dist\hubbardflow-0.1.2-py3-none-any.whl
hubbardflow audit-fdf .\reference.fdf
```

The FDF audit parses the declared functional, spin mode, lattice, and DFTU projector information. It is not a substitute for validating the pseudopotentials, runtime, compatibility registry, projectors, or campaign policy. Use the [PowerShell → WSL quickstart](CLI_LOCAL_WSL_QUICKSTART.md) to prepare those inputs and a validated execution profile.

## PowerShell → WSL campaign commands

The profile declares a single-node local runtime, MPI ranks, SIESTA executable, and WSL workspace. `init` copies the scientific inputs into a separate WSL campaign directory, writes their SHA-256 inventory and returns a Windows pointer. Use the public commands with that pointer:

```powershell
hubbardflow init .\reference.fdf --lr-config .\lr-config.json --profile .\local-wsl-profile.json --name material-lr
hubbardflow run .\material-lr.siestaflow.json
hubbardflow status .\material-lr.siestaflow.json
hubbardflow resume .\material-lr.siestaflow.json
hubbardflow report .\material-lr.siestaflow.json
hubbardflow stop .\material-lr.siestaflow.json
```

`run` starts the campaign worker. `status` reads durable state. `resume` revalidates prior receipts and reuses valid nodes, rerunning only missing/invalid nodes and descendants. `report` renders the saved analysis; it does not run SIESTA. `stop` requests a safe stop. The shared workspace lock serializes SIESTA nodes across local campaigns. Do not run separate workers outside this control plane.

## Linux and Slurm direct-manifest commands

On Linux, the public CLI can initialize a direct `campaign.v2.json` manifest from a profile with `target="slurm"` inside an already granted Slurm allocation. The allocation/site profile must be validated for that installation. HubbardFlow uses the allocation's hosts and does not submit `sbatch`.

```bash
hubbardflow audit-fdf ./reference.fdf
hubbardflow init ./reference.fdf --lr-config ./lr-config.json --profile ./slurm-profile.json --name material-lr --campaign-root /scratch/hubbardflow-campaigns
hubbardflow run /scratch/hubbardflow-campaigns/material-lr/campaign.v2.json
hubbardflow status /scratch/hubbardflow-campaigns/material-lr/campaign.v2.json
hubbardflow resume /scratch/hubbardflow-campaigns/material-lr/campaign.v2.json
hubbardflow report /scratch/hubbardflow-campaigns/material-lr/campaign.v2.json
hubbardflow stop /scratch/hubbardflow-campaigns/material-lr/campaign.v2.json
```

This route expects an existing allocation and profile; it is not a generic remote-login or queue-submission client. See [HPC_SLURM_EXECUTION_CONTRACT.md](HPC_SLURM_EXECUTION_CONTRACT.md) for the site-neutral execution boundary.

## Grid, budget, and interpretation

For a fixed grid with `S` correlated sites and `A` nonzero α amplitudes, the run costs one shared reference plus one BARE and one SCREENED calculation per site and amplitude:

\[
N_{\mathrm{SIESTA}}=1+2SA.
\]

The frozen six-amplitude route therefore costs 13 nodes for one site and 25 for the two-site NiO alternative. A policy-driven adaptive run uses the explicit `total_siesta_node_budget` in its policy and counts new references and probes too. Freeze α values, fit windows, tolerances, projector, and criteria before execution; do not alter them to seek a preferred U.

Reports distinguish workflow validation from a scientific conclusion. `NUMERICAL_CANDIDATE_UNASSESSED`, `NUMERICAL_CANDIDATE_SENSITIVE`, and a `NOT_ESTABLISHED` physical-acceptance state must be reported as-is. Literature agreement is not an algorithm acceptance criterion.

## Supported scope and limitations

The release scope is SIESTA 5.4.2 for the tested spin modes and BARE/SCREENED protocol. A campaign must pass the exact executable/compatibility gate; setting a version string alone does not admit a runtime. The software does not provide automatic `Ueff_Dudarev`, a computed `J`, generic off-diagonal `V` interpretation, non-collinear/SOC support, or universal material presets. See [CHANGELOG.md](../CHANGELOG.md) for release notes and the [project scope](00_governance/SCOPE.md) for broader boundaries.
