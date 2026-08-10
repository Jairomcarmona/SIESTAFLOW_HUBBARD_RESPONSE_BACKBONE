#!/bin/bash
# Yoltla pre-campaign verification
set -e
echo '=== YOLTLA ENVIRONMENT VERIFICATION ==='
# Check SIESTA binary
SIESTA=${SIESTA_BIN:-$(which siesta 2>/dev/null || echo 'NOT_FOUND')}
if [ -x "$SIESTA" ]; then
  VER=$($SIESTA --version 2>&1 | head -1 || echo 'unknown')
  echo "SIESTA_BINARY: $SIESTA"
  echo "SIESTA_VERSION_STRING: $VER"
else
  echo "SIESTA_BINARY: NOT_FOUND"
fi
# Check MPI
MPIRUN=$(which mpirun 2>/dev/null || which srun 2>/dev/null || echo NOT_FOUND)
echo "MPI_LAUNCHER: $MPIRUN"
# Check scratch
SCRATCH=${SCRATCH_BASE:-/scratch/$USER}
mkdir -p $SCRATCH && echo "SCRATCH_WRITABLE: True" || echo "SCRATCH_WRITABLE: False"
# Check pseudopotentials
for PSML in Fe.psml Ni.psml Cu.psml O.psml N.psml; do
  if [ -f "pseudos/$PSML" ]; then
    echo "PSEUDO_$PSML: PRESENT"
  else
    echo "PSEUDO_$PSML: MISSING"
  fi
done
echo '=== VERIFICATION COMPLETE ==='
