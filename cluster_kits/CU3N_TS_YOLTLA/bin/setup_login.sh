#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export ROOT
cd "$ROOT"
source "$ROOT/config/site.sh"
source "$ROOT/bin/lib.sh"
load_kit_env
mkdir -p results runs

log "verify kit and input checksums"
sha256sum -c CHECKSUMS.sha256 --quiet || die "kit checksum mismatch"
(cd inputs && sha256sum -c INPUTS.sha256 --quiet) || die "input checksum mismatch"
[[ "$(sha256_of bin/mpiexec.hydra)" == "$EXPECTED_ADAPTER_SHA256" ]] \
    || die "Hydra adapter checksum mismatch"

log "install the pinned HubbardFlow source"
bash "$ROOT/bin/bootstrap_vendor.sh"
source "$ROOT/config/site.sh"

log "verify SIESTA and write local runtime configuration"
python3 "$ROOT/bin/prepare_backend.py"
python3 "$ROOT/bin/make_slurm_profile.py"
python3 "$ROOT/bin/make_lr_config.py"

log "verify the direct plan without SIESTA"
python3 -m hubbardflow.cli plan "$ROOT/inputs/reference.fdf" \
    --lr-config "$ROOT/config/lr-config.json" --coverage DISABLED \
    --output-dir "$ROOT/plan_direct" > "$ROOT/results/plan_direct_stdout.txt"
python3 "$ROOT/bin/check_plan.py" direct "$ROOT/plan_direct" \
    | tee "$ROOT/results/plan_direct_check.json"
echo "SETUP_LOGIN_PASS"
echo "Next: submit submit_reference.slurm"
