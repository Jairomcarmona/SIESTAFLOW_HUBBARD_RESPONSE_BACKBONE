#!/usr/bin/env bash
set -euo pipefail

die() {
    echo "ERROR: $*" >&2
    exit 2
}

log() {
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"
}

load_kit_env() {
    : "${ROOT:?ROOT is not set}"
    source "$ROOT/config/geometry.env"
    source "$ROOT/config/expected.env"
    export HF_NODES HF_PPN HF_PARTITION HF_MEMORY HF_WALLTIME
    export HF_SHUTDOWN_MARGIN_SECONDS
}

sha256_of() {
    sha256sum "$1" | cut -d' ' -f1
}
