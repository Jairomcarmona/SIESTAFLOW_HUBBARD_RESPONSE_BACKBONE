# Deployment and execution guide for the Yoltla cluster (UAM)

> **Historical file:** this guide describes the interface and direct scripts
> from version 0.1.0. Its `siestaflow` commands are not the current interface.
> For new installations and campaigns, follow [`USER_MANUAL.md`](USER_MANUAL.md)
> and [`CLI_LOCAL_WSL_QUICKSTART.md`](CLI_LOCAL_WSL_QUICKSTART.md), which use
> the current `hubbardflow` CLI. The paths and records in this document are
> preserved as historical reference.

This guide explains how to upload and run **SIESTAFLOW (v0.1.0)** on the
**Yoltla** supercomputer using the **SLURM** queue manager.

---

## 1. Execution architecture on Yoltla

SIESTAFLOW includes the `SiestaLRAdapter`, which is prepared to generate native
**SLURM** job scripts.

### Parameters configured for Yoltla

* **Scheduler:** SLURM (`sbatch`)
* **Module/executable:** `siesta` (loaded with `module load siesta` or by using
  the path to an executable compiled with OpenMPI / ScaLAPACK)
* **Parallelization:** 16 to 32 MPI tasks per node (`#SBATCH --ntasks=16`)
* **Partition:** `batch` (or the partition assigned to your Yoltla account)

---

## 2. Prepare and upload to the cluster

### Step A: Download or clone the private repository on Yoltla

In a Yoltla terminal (over SSH):

```bash
# 1. Connect to Yoltla
ssh user@yoltla.uam.mx

# 2. Clone the private repository
git clone https://github.com/Jairomcarmona/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE.git
cd SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE
```

*(Alternatively, upload the compressed ZIP package
`SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0.zip` using SCP/SFTP.)*

---

## 3. Install dependencies on Yoltla

```bash
# Load cluster modules
module load python/3.10  # Or the available Python 3 version
module load siesta       # Or load OpenMPI / HDF5 / NetCDF

# Create a lightweight virtual environment
python3 -m venv venv
source venv/bin/activate

# Install SIESTAFLOW in editable mode
pip install -e .
```

---

## 4. Run the production calculation ($\text{Cu}_3\text{N}$)

To run the production test with the converged $8\times 8\times 8$ mesh and an
asymmetric $\alpha$ grid:

### Option 1: Via the CLI (automated)

```bash
# 1. Inspect the FDF first
siestaflow audit-fdf examples/tmo_campaigns/Cu3N_ref.fdf

# 2. Initialize the campaign
siestaflow init examples/tmo_campaigns/Cu3N_ref.fdf --name Cu3N_Yoltla

# 3. Launch the campaign on Slurm
siestaflow run campaign.json --hpc-scheduler slurm --ntasks 16
```

### Option 2: Via the launch script (`examples/tmo_campaigns/run_yoltla_campaign.py`)

```bash
python examples/tmo_campaigns/run_yoltla_campaign.py
```

---

## 5. Slurm submission script (`yoltla_submit.sh`)

SIESTAFLOW automatically generates `submit.sh` scripts for each perturbation,
or you can submit the full campaign with this master script:

```bash
#!/bin/bash
#SBATCH --job-name=SIESTAFLOW_Cu3N
#SBATCH --output=siestaflow_%j.log
#SBATCH --error=siestaflow_%j.err
#SBATCH --ntasks=16
#SBATCH --nodes=1
#SBATCH --time=02:00:00
#SBATCH --partition=batch

# Load the environment
source venv/bin/activate

# Run the Cu3N production campaign
python examples/tmo_campaigns/run_yoltla_campaign.py
```

Submit it to the Yoltla queue with:

```bash
sbatch yoltla_submit.sh
```

Monitor its status with:

```bash
squeue -u $USER
```

---

## 6. Fault tolerance and resuming

If the Yoltla job is interrupted because it reached the Slurm time limit, **no
data will be lost**. Simply run:

```bash
siestaflow resume campaign.json
```

SIESTAFLOW checks the SHA-256 signatures of completed `.DM` density matrices
and resumes at the pending perturbation.
