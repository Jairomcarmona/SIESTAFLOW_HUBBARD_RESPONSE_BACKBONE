#!/bin/bash
#SBATCH --partition=tt2d-64p
#SBATCH --account=vini
#SBATCH --qos=normal
#SBATCH --nodes=2
#SBATCH --ntasks=64
#SBATCH --ntasks-per-node=32
#SBATCH --cpus-per-task=1
#SBATCH --job-name=SIESTAFLOW_Cu3N
#SBATCH --output=siestaflow_%j.out
#SBATCH --error=siestaflow_%j.err

cd "$SLURM_SUBMIT_DIR"

# Cargar entorno de Yoltla
module purge 2>/dev/null || true
module load siesta 2>/dev/null || module load siesta/5.4.2 2>/dev/null || true
module load python 2>/dev/null || true

# Activar entorno virtual
source venv/bin/activate

# Ejecución de la campaña de producción de Cu3N con 64 procesadores
python -u examples/tmo_campaigns/run_yoltla_campaign.py siesta 64
