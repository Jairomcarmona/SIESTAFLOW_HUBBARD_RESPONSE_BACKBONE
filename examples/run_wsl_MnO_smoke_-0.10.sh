
rm -rf /tmp/siesta_run_MnO_smoke_-0.10
mkdir -p /tmp/siesta_run_MnO_smoke_-0.10
cp /mnt/c/Users/Jairo/Downloads/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0/examples/*.fdf /mnt/c/Users/Jairo/Downloads/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0/examples/*.psml /tmp/siesta_run_MnO_smoke_-0.10/ 2>/dev/null || true

cat << 'EOF' > /tmp/siesta_run_MnO_smoke_-0.10/submit.sh
#!/bin/bash
#SBATCH --job-name=MnO_smoke_-0.10
#SBATCH --ntasks=4
#SBATCH --output=slurm_MnO_smoke_-0.10.out
#SBATCH --partition=local

cd /tmp/siesta_run_MnO_smoke_-0.10
mpirun -np 4 /home/jmc/.local/siesta-5.4.2-serial/bin/siesta < MnO_smoke_-0.10.fdf > MnO_smoke_-0.10.out
EOF

chmod +x /tmp/siesta_run_MnO_smoke_-0.10/submit.sh
cd /tmp/siesta_run_MnO_smoke_-0.10 && sbatch --wait /tmp/siesta_run_MnO_smoke_-0.10/submit.sh
cp /tmp/siesta_run_MnO_smoke_-0.10/MnO_smoke_-0.10.out /mnt/c/Users/Jairo/Downloads/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0/examples/
