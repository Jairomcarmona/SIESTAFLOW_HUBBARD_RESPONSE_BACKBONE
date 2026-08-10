#!/bin/bash
set -euo pipefail
SIESTA=${SIESTA_BIN:-$(command -v siesta || true)}
MPI=${MPI_LAUNCHER:-$(command -v mpiexec.hydra || true)}
RANKS=${NIO_CORE_MPI_RANKS:-20}
[ -x "$SIESTA" ] || { echo "SIESTA unavailable" >&2; exit 1; }
[ -x "$MPI" ] || { echo "mpiexec.hydra unavailable" >&2; exit 1; }
run_dir () {
  local d="$1" label
  label=$(awk 'tolower($1)=="systemlabel" {print $2; exit}' "$d/siesta.fdf")
  cp pseudos/Ni.psml "$d/NiLR0.psml"
  cp pseudos/Ni.psml "$d/NiLR1.psml"
  cp pseudos/O.psml "$d/O.psml"
  (cd "$d" && "$MPI" -n "$RANKS" "$SIESTA" < siesta.fdf > siesta.out 2> siesta.err)
  printf '%s\n' "$label"
}
ref_label=$(run_dir reference)
PYTHONPATH="$(pwd)/src:$(pwd)${PYTHONPATH:+:$PYTHONPATH}" python validate_reference.py reference/siesta.out
[ -s "reference/${ref_label}.DM" ] || { echo "reference DM missing" >&2; exit 1; }
cp "reference/${ref_label}.DM" reference.DM
for d in bare_J*_a* screened_J*_a*; do
  label=$(awk 'tolower($1)=="systemlabel" {print $2; exit}' "$d/siesta.fdf")
  cp reference.DM "$d/${label}.DM"
  run_dir "$d" >/dev/null
done
PYTHONPATH="$(pwd)/src:$(pwd)${PYTHONPATH:+:$PYTHONPATH}" python analyze_nio.py
