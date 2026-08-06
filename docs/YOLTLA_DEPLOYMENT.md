# Guía de Despliegue y Ejecución en el Cluster Yoltla (UAM)

Esta guía explica paso a paso cómo subir y ejecutar **SIESTAFLOW (v0.1.0)** en la supercomputadora **Yoltla**, utilizando el gestor de colas **SLURM**.

---

## 1. Arquitectura de Ejecución en Yoltla

SIESTAFLOW cuenta con el adaptador `SiestaLRAdapter` preparado para generar scripts de trabajo nativos para **SLURM**. 

### Parámetros Configurados para Yoltla:
* **Planificador:** SLURM (`sbatch`)
* **Módulo/Executable:** `siesta/5.4.2`, verificado con `command -v siesta`
* **Paralelización Yoltla:** 2 nodos, 64 tareas MPI, 32 tareas por nodo
* **Launcher Yoltla:** `mpiexec.hydra -bootstrap ssh -np 64`
* **Partición:** `tt2d-64p`, con cuenta `vini` y QoS `normal`

---

## 2. Preparación y Subida al Cluster

### Paso A: Descargar o Clonar el Repositorio Privado en Yoltla
En la terminal de Yoltla (vía SSH):

```bash
# 1. Conectarse a Yoltla
ssh usuario@yoltla.uam.mx

# 2. Clonar el repositorio privado
git clone https://github.com/Jairomcarmona/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE.git
cd SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE
```

*(Alternativamente, puedes subir el paquete ZIP comprimido `SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0.zip` vía SCP/SFTP).*

---

## 3. Instalación de Dependencias en Yoltla

```bash
# Cargar módulos del cluster
module load python/3.12
module load siesta/5.4.2

# Crear entorno virtual liviano
python3 -m venv venv
source venv/bin/activate

# Instalar SIESTAFLOW en modo editable
pip install -e .
```

---

## 4. Ejecución del Cálculo de Producción ($\text{Cu}_3\text{N}$)

Para correr la prueba de producción con la malla convergida $8\times 8\times 8$ y grilla asimétrica de $\alpha$:

### Opción 1: Vía CLI (Automatizado)
```bash
# 1. Inspección previa del FDF
siestaflow audit-fdf examples/tmo_campaigns/Cu3N_ref.fdf

# 2. Inicializar la campaña
siestaflow init examples/tmo_campaigns/Cu3N_ref.fdf --name Cu3N_Yoltla

# 3. Validar el runtime antes de enviar
command -v siesta
command -v mpiexec.hydra

# 4. Enviar la campaña completa usando el script maestro
sbatch submit.slurm
```

### Opción 2: Vía Script de Lanzamiento (`examples/tmo_campaigns/run_yoltla_campaign.py`)
```bash
python examples/tmo_campaigns/run_yoltla_campaign.py
```

---

## 5. Script de Entrega a Slurm (`yoltla_submit.sh`)

SIESTAFLOW genera automáticamente scripts `submit.sh` por cada perturbación, o puedes enviar la campaña completa con el siguiente script maestro:

```bash
#!/bin/bash
#SBATCH --job-name=SIESTAFLOW_Cu3N
#SBATCH --output=siestaflow_%j.log
#SBATCH --error=siestaflow_%j.err
#SBATCH --partition=tt2d-64p
#SBATCH --account=vini
#SBATCH --qos=normal
#SBATCH --nodes=2
#SBATCH --ntasks=64
#SBATCH --ntasks-per-node=32
#SBATCH --cpus-per-task=1
set -euo pipefail

# Cargar entorno
module purge
module load siesta/5.4.2
module load python/3.12
source venv/bin/activate
command -v siesta
command -v mpiexec.hydra

# Ejecutar campaña de producción de Cu3N
python -u examples/tmo_campaigns/run_yoltla_campaign.py siesta 64
```

Para enviarlo a la cola de Yoltla:
```bash
sbatch yoltla_submit.sh
```

Para monitorear el estado:
```bash
squeue -u $USER
```

---

## 6. Tolerancia a Fallos y Reanudación

Si el trabajo en Yoltla se interrumpe por límite de tiempo de Slurm, **no perderás nada**. Simplemente ejecuta:

```bash
siestaflow resume campaign.json
```
SIESTAFLOW verificará las firmas SHA-256 de las matrices de densidad `.DM` completadas y reanudará exactamente en la perturbación pendiente.
