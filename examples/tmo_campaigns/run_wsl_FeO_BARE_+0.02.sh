
rm -rf /tmp/siesta_run_FeO_BARE_+0.02
mkdir -p /tmp/siesta_run_FeO_BARE_+0.02
cp /mnt/c/Users/Jairo/Downloads/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0/examples/tmo_campaigns/*.fdf /mnt/c/Users/Jairo/Downloads/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0/examples/tmo_campaigns/*.psml /mnt/c/Users/Jairo/Downloads/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0/examples/tmo_campaigns/*.DM /tmp/siesta_run_FeO_BARE_+0.02/ 2>/dev/null || true

cat << 'EOF' > /tmp/siesta_run_FeO_BARE_+0.02/submit.sh
#!/bin/bash
#SBATCH --job-name=FeO_BARE_+0.02
#SBATCH --ntasks=4
#SBATCH --output=slurm_FeO_BARE_+0.02.out
#SBATCH --partition=local

cd /tmp/siesta_run_FeO_BARE_+0.02
mpirun -np 4 /home/jmc/.local/siesta-5.4.2-openmpi/bin/siesta < FeO_BARE_+0.02.fdf > FeO_BARE_+0.02.out
EOF

chmod +x /tmp/siesta_run_FeO_BARE_+0.02/submit.sh
cd /tmp/siesta_run_FeO_BARE_+0.02 && sbatch --wait /tmp/siesta_run_FeO_BARE_+0.02/submit.sh
cp /tmp/siesta_run_FeO_BARE_+0.02/FeO_BARE_+0.02.out /mnt/c/Users/Jairo/Downloads/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0/examples/tmo_campaigns/ 2>/dev/null || true
cp /tmp/siesta_run_FeO_BARE_+0.02/*.DM /mnt/c/Users/Jairo/Downloads/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0/examples/tmo_campaigns/ 2>/dev/null || true
