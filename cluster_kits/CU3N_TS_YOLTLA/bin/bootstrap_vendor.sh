#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SHA="$(tr -d '[:space:]' < "$ROOT/vendor/HUBBARDFLOW_COMMIT.txt")"
SRC="$ROOT/vendor/hubbardflow-src"
DEPS="$ROOT/external/hubbardflow_py"
REPO="https://github.com/Jairomcarmona/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE.git"

module purge
module load python/3.12
mkdir -p "$ROOT/vendor" "$ROOT/external"

if [[ ! -d "$SRC/.git" ]]; then
    if [[ -e "$SRC" ]]; then
        echo "ERROR: $SRC exists but is not a git checkout" >&2
        exit 2
    fi
    git clone --no-checkout "$REPO" "$SRC"
fi

ACTUAL="$(git -C "$SRC" rev-parse HEAD 2>/dev/null || true)"
if [[ "$ACTUAL" != "$SHA" ]]; then
    git -C "$SRC" fetch --depth 1 origin "$SHA"
    git -C "$SRC" checkout --detach FETCH_HEAD
fi

ACTUAL="$(git -C "$SRC" rev-parse HEAD)"
[[ "$ACTUAL" == "$SHA" ]] || {
    echo "ERROR: vendor commit $ACTUAL does not match $SHA" >&2
    exit 3
}
[[ -z "$(git -C "$SRC" status --porcelain)" ]] || {
    echo "ERROR: vendor checkout has local changes" >&2
    exit 3
}

python3 -m pip install --disable-pip-version-check --target "$DEPS" \
    --upgrade 'numpy>=1.20,<2.0' 'jsonschema>=4,<5'
PYTHONNOUSERSITE=1 PYTHONPATH="$SRC/src:$DEPS" python3 - <<'PY'
import hubbardflow
print("HUBBARDFLOW_IMPORT_PASS")
PY

echo "HUBBARDFLOW_VENDOR_READY commit=$SHA"
