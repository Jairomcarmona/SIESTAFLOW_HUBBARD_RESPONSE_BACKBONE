#!/bin/bash
#SBATCH --job-name=siestaflow_hubbard_benchmark
#SBATCH --partition=tt2d-100p
#SBATCH --nodes=5
#SBATCH --ntasks=100
#SBATCH --cpus-per-task=1
#SBATCH --time=48:00:00
#SBATCH --output=campaign_logs/slurm_%j.out
#SBATCH --error=campaign_logs/slurm_%j.err

# Load modules (edit for Yoltla environment)
module load intel/2023
module load intelmpi/2023

# Campaign parameters (override via sbatch --export)
CAMPAIGN_DIR=${CAMPAIGN_DIR:-$(pwd)}
MATERIAL=${MATERIAL:-FeO}
DAG_NODE=${DAG_NODE:-REFERENCE_RUN}
MPI_RANKS_PER_RUN=${MPI_RANKS_PER_RUN:-20}
MAX_CONCURRENT=${MAX_CONCURRENT:-5}
SIESTA=${SIESTA:-/path/to/siesta}

export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1

cd $CAMPAIGN_DIR

python -m production_benchmarks.slurm_runner   --campaign-dir "$CAMPAIGN_DIR"   --material "$MATERIAL"   --dag-node "$DAG_NODE"   --mpi-ranks $MPI_RANKS_PER_RUN   --max-concurrent $MAX_CONCURRENT   --siesta-binary "$SIESTA"

echo "DAG node $DAG_NODE for $MATERIAL completed with status $?"
