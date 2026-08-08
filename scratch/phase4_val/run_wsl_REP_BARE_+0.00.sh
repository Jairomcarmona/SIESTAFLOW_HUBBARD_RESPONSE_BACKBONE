
rm -rf /tmp/siesta_run_REP_BARE_+0.00
mkdir -p /tmp/siesta_run_REP_BARE_+0.00
cp /mnt/c/Users/Jairo/Downloads/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0/scratch/phase4_val/*.fdf /mnt/c/Users/Jairo/Downloads/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0/scratch/phase4_val/*.psml /mnt/c/Users/Jairo/Downloads/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0/scratch/phase4_val/*.DM /tmp/siesta_run_REP_BARE_+0.00/ 2>/dev/null || true

cat << 'EOF' > /tmp/siesta_run_REP_BARE_+0.00/submit.sh
#!/bin/bash
#SBATCH --job-name=REP_BARE_+0.00
#SBATCH --ntasks=1
#SBATCH --output=slurm_REP_BARE_+0.00.out
#SBATCH --partition=local

cd /tmp/siesta_run_REP_BARE_+0.00
sed -i 's/\r$//' REP_BARE_+0.00.fdf
mpirun -np 1 /home/jmc/.local/siesta-5.4.2-serial/bin/siesta < REP_BARE_+0.00.fdf > REP_BARE_+0.00.out
EOF

chmod +x /tmp/siesta_run_REP_BARE_+0.00/submit.sh
cd /tmp/siesta_run_REP_BARE_+0.00 && sbatch --wait /tmp/siesta_run_REP_BARE_+0.00/submit.sh
cp /tmp/siesta_run_REP_BARE_+0.00/REP_BARE_+0.00.out /mnt/c/Users/Jairo/Downloads/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0/scratch/phase4_val/ 2>/dev/null || true
cp /tmp/siesta_run_REP_BARE_+0.00/*.DM /mnt/c/Users/Jairo/Downloads/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0/scratch/phase4_val/ 2>/dev/null || true
