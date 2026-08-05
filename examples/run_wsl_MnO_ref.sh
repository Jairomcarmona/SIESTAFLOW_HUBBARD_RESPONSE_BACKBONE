
rm -rf /tmp/siesta_run_MnO_ref
mkdir -p /tmp/siesta_run_MnO_ref
cp /mnt/c/Users/Jairo/Downloads/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0/examples/*.fdf /mnt/c/Users/Jairo/Downloads/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0/examples/*.psml /mnt/c/Users/Jairo/Downloads/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0/examples/*.DM /tmp/siesta_run_MnO_ref/ 2>/dev/null || true

cat << 'EOF' > /tmp/siesta_run_MnO_ref/submit.sh
#!/bin/bash
#SBATCH --job-name=MnO_ref
#SBATCH --ntasks=1
#SBATCH --output=slurm_MnO_ref.out
#SBATCH --partition=local

cd /tmp/siesta_run_MnO_ref
mpirun -np 1 /home/jmc/.local/siesta-5.4.2-serial/bin/siesta < MnO_ref.fdf > MnO_ref.out
EOF

chmod +x /tmp/siesta_run_MnO_ref/submit.sh
cd /tmp/siesta_run_MnO_ref && sbatch --wait /tmp/siesta_run_MnO_ref/submit.sh
cp /tmp/siesta_run_MnO_ref/MnO_ref.out /mnt/c/Users/Jairo/Downloads/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0/examples/ 2>/dev/null || true
cp /tmp/siesta_run_MnO_ref/*.DM /mnt/c/Users/Jairo/Downloads/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0/examples/ 2>/dev/null || true
