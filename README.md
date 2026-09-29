# SIESTAFLOW Hubbard Response Backbone

**Release:** 0.1.2

**Estado del cierre P0–P6:** `PRODUCT_BLOCKED`. Las puertas operativas y la
campaña P5 terminaron, pero el U de NiO permanece
`NUMERICAL_CANDIDATE_UNASSESSED` / `NOT_ESTABLISHED` frente al objetivo
científico del usuario. Véase el [registro final](docs/P0_EXECUTION_20260928.md).
El [inventario de sincronización](docs/ESTADO_REPOSITORIO_Y_PUBLICACION_20260929.md)
explica el commit local preparado y su estado de publicación en GitHub.

SIESTAFLOW runs finite-difference charge-response campaigns with SIESTA, records their inputs and outputs, analyzes the response matrices, and writes a versioned JSON result plus a Markdown report. Its result is `U_scalar_charge`; the software does not convert that value automatically to `Ueff_Dudarev` or declare physical acceptance without the required scientific contract.

## Install

Install the built wheel in the Python environment used for the CLI. Install it separately in Windows Python and the selected WSL distribution when using PowerShell → WSL. The wheel does not install SIESTA or MPI.

```powershell
py -m pip install .\dist\siestaflow_hubbard-0.1.2-py3-none-any.whl
```

```bash
python3 -m pip install ./dist/siestaflow_hubbard-0.1.2-py3-none-any.whl
```

## PowerShell → WSL quickstart

Prepare an FDF, an `lr-config.json`, and a validated `local_wsl` execution profile. Then use the public CLI:

```powershell
siestaflow audit-fdf .\reference.fdf
siestaflow init .\reference.fdf --lr-config .\lr-config.json --profile .\local-wsl-profile.json --name material-lr
siestaflow run .\material-lr.siestaflow.json
siestaflow status .\material-lr.siestaflow.json
siestaflow resume .\material-lr.siestaflow.json
siestaflow report .\material-lr.siestaflow.json
siestaflow stop .\material-lr.siestaflow.json
```

The detailed profile and configuration contract is in [CLI_LOCAL_WSL_QUICKSTART.md](docs/CLI_LOCAL_WSL_QUICKSTART.md). `init` freezes the input inventory; the worker runs one local SIESTA node at a time. `resume` validates saved node evidence and schedules only missing or invalid work. `report` does not launch SIESTA.

## Linux and Slurm

The public Linux CLI accepts a direct `campaign.v2.json` manifest. The Slurm execution profile must describe a compatible runtime and an allocation that has already been granted; SIESTAFLOW does not submit `sbatch` jobs. See [HPC_SLURM_EXECUTION_CONTRACT.md](docs/HPC_SLURM_EXECUTION_CONTRACT.md) and the CLI section of the [technical user manual](docs/USER_MANUAL.md).

## Scientific meaning and limits

The v3 analysis names its adjusted observable with `occupation_source=siesta_occupations_total` and reports per-site response matrices, `U_scalar_charge`, rounding bounds, SCF and magnetic diagnostics, and numerical status. A report may correctly end as `NUMERICAL_CANDIDATE_UNASSESSED` or `NUMERICAL_CANDIDATE_SENSITIVE`; neither state establishes physical acceptance. Literature agreement is not an acceptance criterion.

For the current NiO precision bottleneck, evidence, limitations, and investigation routes, see the [context report](docs/INFORME_CONTEXTO_CUELLO_BOTELLA_U_20260929.md) and the [precision acceptance contract](docs/U_PRECISION_ACCEPTANCE_CONTRACT_20260928.md).

For the frozen six-amplitude routes, a fixed-grid campaign costs `1 + 2 × S × 6` SIESTA nodes: at most 13 for one correlated site or 25 for the two-site NiO alternative. An adaptive campaign must use its separately declared policy and total node budget. These limits are not permission to alter α, fit windows, tolerances, projectors, or acceptance criteria after inspecting a result.

The certified backend scope is SIESTA 5.4.2 and the tested spin modes. Automatic `Ueff_Dudarev`, computed `J`, interpreting off-diagonal terms as a functional's `V`, non-collinear/SOC support, and universal material presets are outside this release. See [CHANGELOG.md](CHANGELOG.md) and [docs/USER_MANUAL.md](docs/USER_MANUAL.md).
