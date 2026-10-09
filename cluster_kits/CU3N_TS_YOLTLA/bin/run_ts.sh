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
bash "$ROOT/bin/provenance.sh" "ts_${SLURM_JOB_ID:-nojob}"

MAN="$ROOT/runs/cu3n_ts/campaign.v2.json"
COMMON=("$ROOT/inputs/reference.fdf" --lr-config "$ROOT/config/lr-config.json"
    --coverage TRANSLATION_SHADOWED --reference-output "$OUT" --reference-dm "$DM"
    --profile "$ROOT/config/slurm-profile.json" --output-dir "$ROOT/ts")
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
    [[ "${HF_START_TS:-}" == "YES" ]] || die "set HF_START_TS=YES to resume TS"
    python3 "$ROOT/bin/check_plan.py" ts "$ROOT/ts"
    echo "RESUMING_EXISTING_TS_CAMPAIGN"
    python3 -m hubbardflow.cli resume "$MAN" &
else
    python3 -m hubbardflow.cli run "${COMMON[@]}" --dry-run \
        > "$ROOT/results/ts_dry_run.txt" 2>&1 || {
        die "TS planner dry-run failed; see results/ts_dry_run.txt"
    }
    grep -q "ADMISSIBLE_TRANSLATION_SHADOWED" "$ROOT/results/ts_dry_run.txt" \
        || die "TS admission is not ADMISSIBLE_TRANSLATION_SHADOWED"
    echo "TS_DRY_RUN_ADMISSION=ADMISSIBLE_TRANSLATION_SHADOWED"
    python3 "$ROOT/bin/check_plan.py" ts "$ROOT/ts" \
        | tee "$ROOT/results/ts_plan_check.json"
    if [[ "${HF_START_TS:-}" != "YES" ]]; then
        echo "TS_DRY_RUN_READY; no campaign started"
        echo "Review evidence, then submit with HF_START_TS=YES to launch TS"
        exit 0
    fi
    (( stop_requested == 0 )) || die "USR1 received before TS start"
    python3 -m hubbardflow.cli run "${COMMON[@]}" --name cu3n_ts \
        --campaign-root "$ROOT/runs" &
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
    echo "TS_STOP_REQUESTED; resubmit with HF_START_TS=YES to resume"
fi
echo "TS_RC=$rc"
exit "$rc"
