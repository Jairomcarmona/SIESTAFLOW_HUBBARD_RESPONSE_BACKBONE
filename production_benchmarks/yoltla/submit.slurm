#!/bin/bash
# Thin Yoltla allocation wrapper: campaign logic remains in the Python controller.
#SBATCH --job-name=siestaflow_hubbard_benchmark
#SBATCH --partition=tt2d-100p
#SBATCH --nodes=5
#SBATCH --ntasks=100
#SBATCH --cpus-per-task=1
#SBATCH --time=48:00:00
#SBATCH --output=campaign_logs/slurm_%j.out
#SBATCH --error=campaign_logs/slurm_%j.err
set -euo pipefail

module load siesta/5.4.2-intel-oneapi
CAMPAIGN_DIR=${CAMPAIGN_DIR:-$PWD}
MATERIAL=${MATERIAL:-NiO}
DAG_NODE=${DAG_NODE:-REFERENCE_RUN}
MPI_RANKS_PER_RUN=${MPI_RANKS_PER_RUN:-20}
MAX_CONCURRENT=${MAX_CONCURRENT:-5}
SIESTA=${SIESTA_BIN:-$(command -v siesta || true)}
MPI_LAUNCHER=${MPI_LAUNCHER:-$(command -v mpiexec.hydra || true)}
[ -x "$SIESTA" ] || { echo 'SIESTA binary unavailable'; exit 1; }
[ -x "$MPI_LAUNCHER" ] || { echo 'mpiexec.hydra unavailable'; exit 1; }

cd "$CAMPAIGN_DIR"
exec python -m production_benchmarks.slurm_runner \
  --campaign-dir "$CAMPAIGN_DIR" --material "$MATERIAL" --dag-node "$DAG_NODE" \
  --mpi-ranks "$MPI_RANKS_PER_RUN" --max-concurrent "$MAX_CONCURRENT" \
  --siesta-binary "$SIESTA" --mpi-launcher "$MPI_LAUNCHER"
