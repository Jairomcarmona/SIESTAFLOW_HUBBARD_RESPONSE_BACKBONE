#!/bin/bash
# Run on Yoltla before sbatch; this script never launches SIESTA calculations.
set -euo pipefail
echo '=== YOLTLA ENVIRONMENT VERIFICATION ==='
module avail siesta 2>&1 || true
module load siesta/5.4.2-intel-oneapi
SIESTA=${SIESTA_BIN:-$(command -v siesta || true)}
MPI=${MPI_LAUNCHER:-$(command -v mpiexec.hydra || true)}
[ -n "$SIESTA" ] && [ -x "$SIESTA" ] || { echo 'SIESTA_BINARY: NOT_FOUND'; exit 1; }
[ -n "$MPI" ] && [ -x "$MPI" ] || { echo 'MPI_LAUNCHER: NOT_FOUND'; exit 1; }
echo "SIESTA_BINARY: $SIESTA"
"$SIESTA" --version || "$SIESTA" -v || true
echo "MPI_LAUNCHER: $MPI"
ldd "$SIESTA" | grep -E 'mpi|ifcore|mkl' || true
SCRATCH=${SCRATCH_BASE:-/scratch/$USER}
mkdir -p "$SCRATCH" && echo 'SCRATCH_WRITABLE: True' || { echo 'SCRATCH_WRITABLE: False'; exit 1; }
for PSML in Fe.psml Ni.psml Cu.psml O.psml N.psml; do
  [ -s "pseudos/$PSML" ] && echo "PSEUDO_$PSML: PRESENT" || { echo "PSEUDO_$PSML: MISSING"; exit 1; }
done
echo '=== VERIFICATION COMPLETE ==='
