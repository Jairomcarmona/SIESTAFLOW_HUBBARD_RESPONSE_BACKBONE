
rm -rf /tmp/siesta_run_REP_SCREENED_+0.02
mkdir -p /tmp/siesta_run_REP_SCREENED_+0.02
cp /mnt/c/Users/Jairo/Downloads/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0/scratch/phase4_val/*.fdf /mnt/c/Users/Jairo/Downloads/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0/scratch/phase4_val/*.psml /mnt/c/Users/Jairo/Downloads/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0/scratch/phase4_val/*.DM /tmp/siesta_run_REP_SCREENED_+0.02/ 2>/dev/null || true

cat << 'EOF' > /tmp/siesta_run_REP_SCREENED_+0.02/submit.sh
#!/bin/bash
#SBATCH --job-name=REP_SCREENED_+0.02
#SBATCH --ntasks=1
#SBATCH --output=slurm_REP_SCREENED_+0.02.out
#SBATCH --partition=local

cd /tmp/siesta_run_REP_SCREENED_+0.02
sed -i 's/\r$//' REP_SCREENED_+0.02.fdf
mpirun -np 1 /home/jmc/.local/siesta-5.4.2-serial/bin/siesta < REP_SCREENED_+0.02.fdf > REP_SCREENED_+0.02.out
EOF

chmod +x /tmp/siesta_run_REP_SCREENED_+0.02/submit.sh
cd /tmp/siesta_run_REP_SCREENED_+0.02 && sbatch --wait /tmp/siesta_run_REP_SCREENED_+0.02/submit.sh
cp /tmp/siesta_run_REP_SCREENED_+0.02/REP_SCREENED_+0.02.out /mnt/c/Users/Jairo/Downloads/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0/scratch/phase4_val/ 2>/dev/null || true
cp /tmp/siesta_run_REP_SCREENED_+0.02/*.DM /mnt/c/Users/Jairo/Downloads/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0/scratch/phase4_val/ 2>/dev/null || true
