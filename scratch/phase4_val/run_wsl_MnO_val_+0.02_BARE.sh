
rm -rf /tmp/siesta_run_MnO_val_+0.02_BARE
mkdir -p /tmp/siesta_run_MnO_val_+0.02_BARE
cp /mnt/c/Users/Jairo/Downloads/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0/scratch/phase4_val/*.fdf /mnt/c/Users/Jairo/Downloads/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0/scratch/phase4_val/*.psml /mnt/c/Users/Jairo/Downloads/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0/scratch/phase4_val/*.DM /tmp/siesta_run_MnO_val_+0.02_BARE/ 2>/dev/null || true

cat << 'EOF' > /tmp/siesta_run_MnO_val_+0.02_BARE/submit.sh
#!/bin/bash
#SBATCH --job-name=MnO_val_+0.02_BARE
#SBATCH --ntasks=1
#SBATCH --output=slurm_MnO_val_+0.02_BARE.out
#SBATCH --partition=local

cd /tmp/siesta_run_MnO_val_+0.02_BARE
sed -i 's/\r$//' MnO_val_+0.02_BARE.fdf
mpirun -np 1 /home/jmc/.local/siesta-5.4.2-serial/bin/siesta < MnO_val_+0.02_BARE.fdf > neg_control.out
EOF

chmod +x /tmp/siesta_run_MnO_val_+0.02_BARE/submit.sh
cd /tmp/siesta_run_MnO_val_+0.02_BARE && sbatch --wait /tmp/siesta_run_MnO_val_+0.02_BARE/submit.sh
cp /tmp/siesta_run_MnO_val_+0.02_BARE/neg_control.out /mnt/c/Users/Jairo/Downloads/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0/scratch/phase4_val/ 2>/dev/null || true
cp /tmp/siesta_run_MnO_val_+0.02_BARE/*.DM /mnt/c/Users/Jairo/Downloads/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0/scratch/phase4_val/ 2>/dev/null || true
