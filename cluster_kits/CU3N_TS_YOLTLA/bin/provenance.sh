#!/usr/bin/env bash
set -euo pipefail
ROOT="${ROOT:?ROOT is not set}"
mkdir -p "$ROOT/results"
HF_MODULE_LIST="$(module list 2>&1 || true)" python3 "$ROOT/bin/provenance.py" "$1"
