#!/bin/bash
#SBATCH --job-name=sf542-e2e
#SBATCH --partition=local
#SBATCH --nodes=1
#SBATCH --ntasks=4
#SBATCH --cpus-per-task=1
#SBATCH --time=00:10:00
#SBATCH --output=/tmp/siestaflow-542-e2e-%j.out
#SBATCH --error=/tmp/siestaflow-542-e2e-%j.err
set -euo pipefail
exec /usr/bin/env \
  OMP_NUM_THREADS=1 \
  /mnt/c/Users/Jairo/Downloads/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0/.codex_wheel_validation/bin/python \
  /mnt/c/Users/Jairo/Downloads/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0/tools/run_siesta542_openmpi_slurm_e2e.py
