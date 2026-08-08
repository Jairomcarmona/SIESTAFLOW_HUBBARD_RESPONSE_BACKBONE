
rm -rf /tmp/siesta_run_MnO_Method2_Ref
mkdir -p /tmp/siesta_run_MnO_Method2_Ref
cp /mnt/c/Users/Jairo/Downloads/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0/scratch/phase4_val/*.fdf /mnt/c/Users/Jairo/Downloads/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0/scratch/phase4_val/*.psml /mnt/c/Users/Jairo/Downloads/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0/scratch/phase4_val/*.DM /tmp/siesta_run_MnO_Method2_Ref/ 2>/dev/null || true

cat << 'EOF' > /tmp/siesta_run_MnO_Method2_Ref/submit.sh
#!/bin/bash
#SBATCH --job-name=MnO_Method2_Ref
#SBATCH --ntasks=1
#SBATCH --output=slurm_MnO_Method2_Ref.out
#SBATCH --partition=local

cd /tmp/siesta_run_MnO_Method2_Ref
sed -i 's/\r$//' MnO_Method2_Ref.fdf
mpirun -np 1 /home/jmc/.local/siesta-5.4.2-serial/bin/siesta < MnO_Method2_Ref.fdf > MnO_Method2_Ref.out
EOF

chmod +x /tmp/siesta_run_MnO_Method2_Ref/submit.sh
cd /tmp/siesta_run_MnO_Method2_Ref && sbatch --wait /tmp/siesta_run_MnO_Method2_Ref/submit.sh
cp /tmp/siesta_run_MnO_Method2_Ref/MnO_Method2_Ref.out /mnt/c/Users/Jairo/Downloads/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0/scratch/phase4_val/ 2>/dev/null || true
cp /tmp/siesta_run_MnO_Method2_Ref/*.DM /mnt/c/Users/Jairo/Downloads/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0/scratch/phase4_val/ 2>/dev/null || true
