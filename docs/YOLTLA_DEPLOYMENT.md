# Guía de Despliegue y Ejecución en el Cluster Yoltla (UAM)

Esta guía explica paso a paso cómo subir y ejecutar **SIESTAFLOW (v0.1.0)** en la supercomputadora **Yoltla**, utilizando el gestor de colas **SLURM**.

---

## 1. Arquitectura de Ejecución en Yoltla

SIESTAFLOW cuenta con el adaptador `SiestaLRAdapter` preparado para generar scripts de trabajo nativos para **SLURM**. 

### Parámetros Configurados para Yoltla:
* **Planificador:** SLURM (`sbatch`)
* **Módulo/Executable:** `siesta` (cargado vía `module load siesta` o ruta al ejecutable compilado con OpenMPI / ScaLAPACK)
* **Paralelización:** 16 a 32 tareas MPI por nodo (`#SBATCH --ntasks=16`)
* **Partición:** `batch` (o la partición asignada a tu usuario en Yoltla)

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
module load python/3.10  # O la versión de Python 3 disponible
module load siesta       # O cargar OpenMPI / HDF5 / NetCDF

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

# 3. Lanzar la campaña en Slurm
siestaflow run campaign.json --hpc-scheduler slurm --ntasks 16
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
#SBATCH --ntasks=16
#SBATCH --nodes=1
#SBATCH --time=02:00:00
#SBATCH --partition=batch

# Cargar entorno
source venv/bin/activate

# Ejecutar campaña de producción de Cu3N
python examples/tmo_campaigns/run_yoltla_campaign.py
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
