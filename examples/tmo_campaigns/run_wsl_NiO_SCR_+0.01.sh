
rm -rf /tmp/siesta_run_NiO_SCR_+0.01
mkdir -p /tmp/siesta_run_NiO_SCR_+0.01
cp /mnt/c/Users/Jairo/Downloads/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0/examples/tmo_campaigns/*.fdf /mnt/c/Users/Jairo/Downloads/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0/examples/tmo_campaigns/*.psml /mnt/c/Users/Jairo/Downloads/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0/examples/tmo_campaigns/*.DM /tmp/siesta_run_NiO_SCR_+0.01/ 2>/dev/null || true

cat << 'EOF' > /tmp/siesta_run_NiO_SCR_+0.01/submit.sh
#!/bin/bash
#SBATCH --job-name=NiO_SCR_+0.01
#SBATCH --ntasks=4
#SBATCH --output=slurm_NiO_SCR_+0.01.out
#SBATCH --partition=local

cd /tmp/siesta_run_NiO_SCR_+0.01
mpirun -np 4 /home/jmc/.local/siesta-5.4.2-openmpi/bin/siesta < NiO_SCR_+0.01.fdf > NiO_SCR_+0.01.out
EOF

chmod +x /tmp/siesta_run_NiO_SCR_+0.01/submit.sh
cd /tmp/siesta_run_NiO_SCR_+0.01 && sbatch --wait /tmp/siesta_run_NiO_SCR_+0.01/submit.sh
cp /tmp/siesta_run_NiO_SCR_+0.01/NiO_SCR_+0.01.out /mnt/c/Users/Jairo/Downloads/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0/examples/tmo_campaigns/ 2>/dev/null || true
cp /tmp/siesta_run_NiO_SCR_+0.01/*.DM /mnt/c/Users/Jairo/Downloads/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0/examples/tmo_campaigns/ 2>/dev/null || true
