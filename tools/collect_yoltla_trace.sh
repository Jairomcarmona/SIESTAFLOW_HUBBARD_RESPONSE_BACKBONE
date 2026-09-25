#!/usr/bin/env bash
set -euo pipefail

# Collect the minimum auditable record of a Yoltla NiO response run.
# Usage from prueba_Uresp_lineal:
#   bash collect_yoltla_trace.sh nio_core_yoltla yoltla_trace_783533 783533 783662_2
# The last arguments are optional Slurm job IDs.

ROOT_DIR="${1:-$PWD/nio_core_yoltla}"
DEST_DIR="${2:-$PWD/yoltla_trace_$(date +%Y%m%dT%H%M%S)}"
BASELINE_ROOT="${YOLTLA_BASELINE_ROOT:-}"
shift 2 || true
JOB_IDS=("$@")

if [[ ! -d "$ROOT_DIR" ]]; then
    printf 'ERROR: package directory not found: %s\n' "$ROOT_DIR" >&2
    exit 2
fi

mkdir -p "$DEST_DIR/package" "$DEST_DIR/runs" "$DEST_DIR/screening" \
         "$DEST_DIR/slurm" "$DEST_DIR/metadata" "$DEST_DIR/large_files"

copy_if_present() {
    local source="$1" target="$2"
    if [[ -f "$source" ]]; then
        mkdir -p "$(dirname "$target")"
        cp -p "$source" "$target"
    fi
}

copy_run_record() {
    local run_dir="$1" rel="$2"
    for name in siesta.fdf siesta.out siesta.err 0_NORMAL_EXIT runs.json \
                MESSAGES OUTVARS.yml CLOCK TIMES FORCE_STRESS STRUCT_OUT; do
        copy_if_present "$run_dir/$name" "$DEST_DIR/$rel/$name"
    done
    for path in "$run_dir"/*.KP "$run_dir"/*.XV "$run_dir"/*.EIG \
                "$run_dir"/*.BONDS "$run_dir"/*.ORB_INDX; do
        [[ -f "$path" ]] || continue
        copy_if_present "$path" "$DEST_DIR/$rel/${path##*/}"
    done
}

# Source code and fixed inputs needed to interpret the observations.
for path in \
    analyze_nio.py screening_campaign.py validate_reference.py \
    run_nio_core.sh submit.slurm submit_screening.slurm \
    submit_supercell_kmatched.slurm runs.json real_baseline_783533.json \
    REAL_EXECUTION_REGRESSION_BASELINE.md; do
    copy_if_present "$ROOT_DIR/$path" "$DEST_DIR/package/$path"
done
if [[ -d "$ROOT_DIR/pseudos" ]]; then
    while IFS= read -r -d '' path; do
        rel="${path#"$ROOT_DIR/"}"
        copy_if_present "$path" "$DEST_DIR/package/$rel"
    done < <(find "$ROOT_DIR/pseudos" -type f -name '*.psml' -print0)
fi
if [[ -d "$ROOT_DIR/production_benchmarks" ]]; then
    while IFS= read -r -d '' path; do
        rel="${path#"$ROOT_DIR/"}"
        copy_if_present "$path" "$DEST_DIR/package/$rel"
    done < <(find "$ROOT_DIR/production_benchmarks" -type f -name '*.py' -print0)
fi
if [[ -d "$ROOT_DIR/src" ]]; then
    while IFS= read -r -d '' path; do
        rel="${path#"$ROOT_DIR/"}"
        copy_if_present "$path" "$DEST_DIR/package/$rel"
    done < <(find "$ROOT_DIR/src" -type f \( -name '*.py' -o -name '*.toml' \) -print0)
fi

# The 11-run small-cell baseline and any completed response runs. If the
# working package was redeployed after the run, point YOLTLA_BASELINE_ROOT at
# the preserved baseline directory so its raw outputs are retained too.
RUN_ROOTS=("$ROOT_DIR")
if [[ -n "$BASELINE_ROOT" && -d "$BASELINE_ROOT" ]]; then
    RUN_ROOTS+=("$BASELINE_ROOT")
fi
for run_root in "${RUN_ROOTS[@]}"; do
    for run_dir in "$run_root/reference" "$run_root"/bare_* "$run_root"/screened_*; do
        [[ -d "$run_dir" ]] || continue
        copy_run_record "$run_dir" "runs/${run_dir##*/}"
    done
done

# Screening candidates: preserve only auditable text/input markers, not SIESTA
# scratch products (.HSX, .ion, .xml, .KP, .XV, etc.).
if [[ -d "$ROOT_DIR/screening" ]]; then
    while IFS= read -r -d '' path; do
        rel="${path#"$ROOT_DIR/"}"
        copy_if_present "$path" "$DEST_DIR/$rel"
    done < <(find "$ROOT_DIR/screening" -type f \( \
        -name siesta.fdf -o -name siesta.out -o -name siesta.err \
        -o -name 0_NORMAL_EXIT -o -name runs.json \) -print0)
fi
for source_root in "${RUN_ROOTS[@]}"; do
    for path in nio_scientific_screening_available.json nio_scientific_screening.json nio_u_result.json; do
        copy_if_present "$source_root/$path" "$DEST_DIR/results/${path}"
    done
done

# SIESTA also writes some native auxiliary files in the calculation root
# (especially for the reference run), rather than inside reference/.
for source_root in "${RUN_ROOTS[@]}"; do
    for path in "$source_root"/OUTVARS.yml "$source_root"/CLOCK \
                "$source_root"/TIMES "$source_root"/FORCE_STRESS \
                "$source_root"/MESSAGES "$source_root"/BASIS_ENTHALPY \
                "$source_root"/BASIS_HARRIS_ENTHALPY \
                "$source_root"/*.KP "$source_root"/*.XV \
                "$source_root"/*.EIG "$source_root"/*.BONDS \
                "$source_root"/*.ORB_INDX "$source_root"/*.STRUCT_OUT; do
        [[ -f "$path" ]] || continue
        copy_if_present "$path" "$DEST_DIR/metadata/native_auxiliary/${path##*/}"
    done
done

# The common parent DM is required to reproduce child handoff, but should be
# kept as an archive artifact rather than committed to the source repository.
for source_root in "${RUN_ROOTS[@]}"; do
    for path in "$source_root/reference.DM" "$source_root"/reference/*.DM "$source_root"/*.DM; do
        [[ -f "$path" ]] || continue
        copy_if_present "$path" "$DEST_DIR/large_files/${path##*/}"
    done
done

# Scheduler and environment evidence.
{
    date -Is 2>/dev/null || date
    printf 'pwd=%s\n' "$PWD"
    printf 'root_dir=%s\n' "$ROOT_DIR"
    hostname 2>/dev/null || true
    printf '\n--- modules ---\n'
    module list 2>&1 || true
    printf '\n--- executables ---\n'
    command -v siesta 2>&1 || true
    command -v mpiexec.hydra 2>&1 || true
    command -v python 2>&1 || true
    printf '\n--- git revision (if present) ---\n'
    git -C "$ROOT_DIR" rev-parse HEAD 2>&1 || true
    printf '\n--- siesta version output ---\n'
    siesta -version 2>&1 || true
} > "$DEST_DIR/metadata/environment.txt"

for path in "$ROOT_DIR"/nio_core_*.out "$ROOT_DIR"/nio_core_*.err \
            "$ROOT_DIR"/nio_screen_*.out "$ROOT_DIR"/nio_screen_*.err; do
    [[ -f "$path" ]] || continue
    copy_if_present "$path" "$DEST_DIR/slurm/${path##*/}"
done

{
    printf '%s\n' '--- package zip listing ---'
    if command -v unzip >/dev/null 2>&1 && [[ -f "$(dirname "$ROOT_DIR")/nio_core_yoltla.zip" ]]; then
        unzip -l "$(dirname "$ROOT_DIR")/nio_core_yoltla.zip" || true
    fi
    printf '%s\n' '--- requested Slurm jobs ---'
    for job in "${JOB_IDS[@]}"; do
        printf '\n### %s: scontrol show job\n' "$job"
        scontrol show job "$job" 2>&1 || true
        printf '\n### %s: sacct\n' "$job"
        sacct -j "$job" --format=JobIDRaw,JobName,State,ExitCode,Elapsed,NodeList 2>&1 || true
    done
} > "$DEST_DIR/slurm/job_reports.txt"

# Compact human-readable summary generated from actual result JSON files.
PYTHON_BIN="$(command -v python3 || command -v python || true)"
if [[ -n "$PYTHON_BIN" ]]; then
    "$PYTHON_BIN" - "$DEST_DIR" > "$DEST_DIR/metadata/scientific_summary.txt" <<'PY'
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
files = sorted(root.rglob("*.json"))
for path in files:
    try:
        data = json.loads(path.read_text())
    except Exception:
        continue
    print(f"FILE: {path.relative_to(root)}")
    for key in ("status", "rank_chi0", "rank_chi", "condition_chi0", "condition_chi", "U"):
        if key in data:
            print(f"{key}: {json.dumps(data[key], separators=(',', ':'))}")
    if "unavailable" in data:
        print(f"unavailable_count: {len(data['unavailable'])}")
    print()
PY
else
    printf '%s\n' 'Python not found; JSON summary was not generated.' > "$DEST_DIR/metadata/scientific_summary.txt"
fi

{
    printf '%s\n' 'YOLTLA TRACE COLLECTION'
    printf 'created=%s\n' "$(date -Is 2>/dev/null || date)"
    printf 'source=%s\n' "$ROOT_DIR"
    printf '\nIncluded files (path, bytes):\n'
    find "$DEST_DIR" -type f -printf '%P %s\n' 2>/dev/null | sort
} > "$DEST_DIR/MANIFEST.txt"

ARCHIVE="${DEST_DIR%/}.tar.gz"
tar -czf "$ARCHIVE" -C "$(dirname "$DEST_DIR")" "$(basename "$DEST_DIR")"
printf 'TRACE_DIR=%s\nTRACE_ARCHIVE=%s\n' "$DEST_DIR" "$ARCHIVE"
