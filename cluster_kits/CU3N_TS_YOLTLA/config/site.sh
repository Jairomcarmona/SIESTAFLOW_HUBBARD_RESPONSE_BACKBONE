#!/usr/bin/env bash
set -euo pipefail
module purge
module load python/3.12
module load siesta/5.4.2
if [[ -n "${SLURM_SUBMIT_DIR:-}" ]]; then
    ROOT="$SLURM_SUBMIT_DIR"
fi
ROOT="${ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
export ROOT
export PYTHONNOUSERSITE=1
export PYTHONPATH="$ROOT/vendor/hubbardflow-src/src:$ROOT/external/hubbardflow_py"
export PATH="$ROOT/bin:$PATH"
