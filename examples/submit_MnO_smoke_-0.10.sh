#!/bin/bash
#SBATCH --job-name=MnO_smoke_-0.10
#SBATCH --ntasks=4
#SBATCH --output=slurm_MnO_smoke_-0.10.out
#SBATCH --partition=local

cd /mnt/c/Users/Jairo/Downloads/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0/examples
mpirun -np 4 /home/jmc/.local/siesta-5.4.2-serial/bin/siesta < MnO_smoke_-0.10.fdf > MnO_smoke_-0.10.out
