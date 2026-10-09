#!/usr/bin/env bash
set -euo pipefail

ROOT="${SLURM_SUBMIT_DIR:?SLURM_SUBMIT_DIR is not set}"
cd "$ROOT"
source "$ROOT/config/site.sh"
source "$ROOT/bin/lib.sh"
load_kit_env
mkdir -p results
if [[ "${HF_START_REFERENCE:-}" != "YES" ]]; then
    echo "REFERENCE_NOT_STARTED; submit with HF_START_REFERENCE=YES"
    exit 0
fi
[[ -f vendor/hubbardflow-src/pyproject.toml ]] || die "run setup_login.sh first"
[[ ! -e "$ROOT/ref" ]] || die "ref/ exists; use a fresh kit copy"
[[ ! -e "$ROOT/runs/cu3n_ts_reference" ]] || die "reference manifest already exists"
bash "$ROOT/bin/preflight_allocation.sh"
bash "$ROOT/bin/provenance.sh" reference

start=$SECONDS
set +e
python3 -m hubbardflow.cli reference "$ROOT/inputs/reference.fdf" \
    --lr-config "$ROOT/config/lr-config.json" \
    --profile "$ROOT/config/slurm-profile.json" \
    --name cu3n_ts_reference --output-dir "$ROOT/ref" \
    --campaign-root "$ROOT/runs" > "$ROOT/results/reference_cli.txt" 2>&1
rc=$?
set -e
echo "REFERENCE_COMMAND_LOG=results/reference_cli.txt"
echo "REFERENCE_RC=$rc wall_seconds=$((SECONDS - start))"
[[ "$rc" -eq 0 ]] || exit "$rc"

python3 "$ROOT/bin/check_nonpolarized_reference.py" \
    "$ROOT/inputs/reference.fdf" "$ROOT/ref/planning_reference/reference.out" \
    --json-out "$ROOT/results/nonpolarized_reference_check.json"
[[ -s "$ROOT/ref/planning_reference/00_REFERENCE.DM" ]] \
    || die "reference DM is missing"
echo "REFERENCE_READY"
