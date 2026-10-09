#!/usr/bin/env bash
set -euo pipefail

ROOT="${SLURM_SUBMIT_DIR:?SLURM_SUBMIT_DIR is not set}"
cd "$ROOT"
source "$ROOT/config/site.sh"
source "$ROOT/bin/lib.sh"
load_kit_env
mkdir -p results
REF="$ROOT/ref/planning_reference"
OUT="$REF/reference.out"
DM="$REF/00_REFERENCE.DM"
[[ -s "$OUT" && -s "$DM" ]] || die "run submit_reference.slurm first"
python3 "$ROOT/bin/check_nonpolarized_reference.py" \
    "$ROOT/inputs/reference.fdf" "$OUT" \
    --json-out "$ROOT/results/nonpolarized_reference_check.json"
bash "$ROOT/bin/preflight_allocation.sh"
bash "$ROOT/bin/provenance.sh" "probe_${SLURM_JOB_ID:-nojob}"

python3 -m hubbardflow.cli run "$ROOT/inputs/reference.fdf" \
    --lr-config "$ROOT/config/lr-config.json" --coverage TRANSLATION_SHADOWED \
    --reference-output "$OUT" --reference-dm "$DM" \
    --profile "$ROOT/config/slurm-profile.json" --output-dir "$ROOT/ts" --dry-run \
    > "$ROOT/results/ts_dry_run.txt" 2>&1 || {
    die "TS planner dry-run failed; see results/ts_dry_run.txt"
}
grep -q "ADMISSIBLE_TRANSLATION_SHADOWED" "$ROOT/results/ts_dry_run.txt" \
    || die "TS admission is not ADMISSIBLE_TRANSLATION_SHADOWED"
echo "TS_DRY_RUN_ADMISSION=ADMISSIBLE_TRANSLATION_SHADOWED"
python3 "$ROOT/bin/check_plan.py" ts "$ROOT/ts" \
    | tee "$ROOT/results/ts_plan_check.json"
python3 "$ROOT/bin/make_probe.py" "$ROOT/ts"
python3 -m hubbardflow.cli run "$ROOT/probe/probe.fdf" \
    --lr-config "$ROOT/probe/probe-lr-config.json" --coverage DISABLED \
    --profile "$ROOT/config/slurm-profile.json" \
    --output-dir "$ROOT/probe_product" --dry-run \
    > "$ROOT/results/probe_dry_run.txt" 2>&1 || {
    die "probe planner dry-run failed; see results/probe_dry_run.txt"
}
echo "PROBE_DRY_RUN_LOG=results/probe_dry_run.txt"
python3 "$ROOT/bin/check_plan.py" probe "$ROOT/probe_product" \
    | tee "$ROOT/results/probe_plan_check.json"

MAN="$ROOT/runs/cu3n_probe/campaign.v2.json"
if [[ "${HF_START_PROBE:-}" != "YES" ]]; then
    echo "PROBE_DRY_RUN_READY; no SIESTA campaign started"
    echo "Review probe/probe.diff, then submit with HF_START_PROBE=YES"
    exit 0
fi

stop_requested=0
worker_pid=""
request_stop() {
    for ((attempt = 0; attempt < 60; attempt++)); do
        if [[ -f "$MAN" ]]; then
            timeout 60s python3 -m hubbardflow.cli stop "$MAN" || true
            return
        fi
        [[ -n "$worker_pid" ]] || return
        sleep 1
    done
    echo "STOP_MANIFEST_NOT_FOUND_WITHIN_60S" >&2
}
on_usr1() {
    stop_requested=1
    echo "WALLTIME_SIGNAL_RECEIVED $(date -u +%FT%TZ)"
    request_stop
}
trap on_usr1 USR1
if [[ -f "$MAN" ]]; then
    echo "RESUMING_EXISTING_PROBE"
    python3 -m hubbardflow.cli resume "$MAN" &
else
    (( stop_requested == 0 )) || die "USR1 received before probe start"
    python3 -m hubbardflow.cli run "$ROOT/probe/probe.fdf" \
        --lr-config "$ROOT/probe/probe-lr-config.json" --coverage DISABLED \
        --profile "$ROOT/config/slurm-profile.json" --output-dir "$ROOT/probe_product" \
        --name cu3n_probe --campaign-root "$ROOT/runs" &
fi
worker_pid=$!
if (( stop_requested )); then
    request_stop
fi
set +e
wait "$worker_pid"
rc=$?
while kill -0 "$worker_pid" 2>/dev/null; do
    wait "$worker_pid"
    rc=$?
done
set -e
if (( stop_requested )); then
    echo "PROBE_STOP_REQUESTED; resubmit with HF_START_PROBE=YES to resume"
fi
echo "PROBE_RC=$rc"
exit "$rc"
