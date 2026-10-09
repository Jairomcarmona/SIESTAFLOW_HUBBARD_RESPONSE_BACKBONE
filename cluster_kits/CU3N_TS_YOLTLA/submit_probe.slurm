#!/bin/bash
#SBATCH --job-name=HF_CU3N_PROBE
#SBATCH --partition=q4d-40p
#SBATCH --nodes=2
#SBATCH --ntasks=32
#SBATCH --ntasks-per-node=16
#SBATCH --cpus-per-task=1
#SBATCH --time=12:00:00
#SBATCH --signal=B:USR1@900
#SBATCH --output=slurm-%j.out
#SBATCH --error=slurm-%j.err
set -euo pipefail
ROOT="${SLURM_SUBMIT_DIR:?SLURM_SUBMIT_DIR is not set}"
cd "$ROOT"
exec bash "$ROOT/bin/run_probe.sh"
