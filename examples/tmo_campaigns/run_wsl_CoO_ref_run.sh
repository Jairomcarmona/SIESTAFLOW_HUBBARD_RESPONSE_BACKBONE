
rm -rf /tmp/siesta_run_CoO_ref_run
mkdir -p /tmp/siesta_run_CoO_ref_run
cp /mnt/c/Users/Jairo/Downloads/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0/examples/tmo_campaigns/*.fdf /mnt/c/Users/Jairo/Downloads/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0/examples/tmo_campaigns/*.psml /mnt/c/Users/Jairo/Downloads/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0/examples/tmo_campaigns/*.DM /tmp/siesta_run_CoO_ref_run/ 2>/dev/null || true

cat << 'EOF' > /tmp/siesta_run_CoO_ref_run/submit.sh
#!/bin/bash
#SBATCH --job-name=CoO_ref_run
#SBATCH --ntasks=4
#SBATCH --output=slurm_CoO_ref_run.out
#SBATCH --partition=local

cd /tmp/siesta_run_CoO_ref_run
mpirun -np 4 /home/jmc/.local/siesta-5.4.2-openmpi/bin/siesta < CoO_ref_run.fdf > CoO_ref.out
EOF

chmod +x /tmp/siesta_run_CoO_ref_run/submit.sh
cd /tmp/siesta_run_CoO_ref_run && sbatch --wait /tmp/siesta_run_CoO_ref_run/submit.sh
cp /tmp/siesta_run_CoO_ref_run/CoO_ref.out /mnt/c/Users/Jairo/Downloads/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0/examples/tmo_campaigns/ 2>/dev/null || true
cp /tmp/siesta_run_CoO_ref_run/*.DM /mnt/c/Users/Jairo/Downloads/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0/examples/tmo_campaigns/ 2>/dev/null || true
