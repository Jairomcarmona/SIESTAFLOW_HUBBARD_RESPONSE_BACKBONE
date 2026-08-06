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
set -euo pipefail

cd "${SLURM_SUBMIT_DIR:?SLURM_SUBMIT_DIR no definido}"

# Cargar entorno de Yoltla
module purge
module load siesta/5.4.2
module load python/3.12

# Activar entorno virtual
source venv/bin/activate

# Verificar el runtime antes de comenzar la campaña
command -v siesta
command -v mpiexec.hydra
command -v python

# Ejecución de la campaña de producción de Cu3N con la asignación completa
python -u examples/tmo_campaigns/run_yoltla_campaign.py siesta 64
