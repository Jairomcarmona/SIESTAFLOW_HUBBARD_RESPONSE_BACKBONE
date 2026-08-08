
rm -rf /tmp/siesta_run_MnO_val_-0.01_SCR
mkdir -p /tmp/siesta_run_MnO_val_-0.01_SCR
cp /mnt/c/Users/Jairo/Downloads/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0/scratch/phase4_val/*.fdf /mnt/c/Users/Jairo/Downloads/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0/scratch/phase4_val/*.psml /mnt/c/Users/Jairo/Downloads/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0/scratch/phase4_val/*.DM /tmp/siesta_run_MnO_val_-0.01_SCR/ 2>/dev/null || true

cat << 'EOF' > /tmp/siesta_run_MnO_val_-0.01_SCR/submit.sh
#!/bin/bash
#SBATCH --job-name=MnO_val_-0.01_SCR
#SBATCH --ntasks=1
#SBATCH --output=slurm_MnO_val_-0.01_SCR.out
#SBATCH --partition=local

cd /tmp/siesta_run_MnO_val_-0.01_SCR
sed -i 's/\r$//' MnO_val_-0.01_SCR.fdf
mpirun -np 1 /home/jmc/.local/siesta-5.4.2-serial/bin/siesta < MnO_val_-0.01_SCR.fdf > MnO_val_-0.01_SCR.out
EOF

chmod +x /tmp/siesta_run_MnO_val_-0.01_SCR/submit.sh
cd /tmp/siesta_run_MnO_val_-0.01_SCR && sbatch --wait /tmp/siesta_run_MnO_val_-0.01_SCR/submit.sh
cp /tmp/siesta_run_MnO_val_-0.01_SCR/MnO_val_-0.01_SCR.out /mnt/c/Users/Jairo/Downloads/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0/scratch/phase4_val/ 2>/dev/null || true
cp /tmp/siesta_run_MnO_val_-0.01_SCR/*.DM /mnt/c/Users/Jairo/Downloads/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0/scratch/phase4_val/ 2>/dev/null || true
