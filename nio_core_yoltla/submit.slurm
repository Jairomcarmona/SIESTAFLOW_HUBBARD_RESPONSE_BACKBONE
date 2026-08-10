#!/bin/bash
#SBATCH --job-name=nio_u_core
#SBATCH --partition=tt2d-64p
#SBATCH --nodes=2
#SBATCH --ntasks=64
#SBATCH --ntasks-per-node=32
#SBATCH --cpus-per-task=1
#SBATCH --time=12:00:00
#SBATCH --output=nio_core_%j.out
#SBATCH --error=nio_core_%j.err
set -euo pipefail
module load python/3.12
module load siesta/5.4.2
export SIESTA_BIN="${SIESTA_BIN:-$(command -v siesta)}"
export MPI_LAUNCHER="${MPI_LAUNCHER:-$(command -v mpiexec.hydra)}"
export NIO_CORE_MPI_RANKS="${NIO_CORE_MPI_RANKS:-64}"
exec bash run_nio_core.sh
