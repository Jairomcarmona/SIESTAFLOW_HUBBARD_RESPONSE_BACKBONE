#!/usr/bin/env bash
# Make a light evidence archive without pseudopotentials or matrix data.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p results evidence
if [[ -s results/slurm_jobs.txt ]] && command -v sacct >/dev/null; then
    ids="$(awk '{print $1}' results/slurm_jobs.txt | grep -E '^[0-9]+$' | paste -sd, - || true)"
    if [[ -n "$ids" ]]; then
        sacct -j "$ids" --format=JobID,JobName,Partition,AllocNodes,AllocCPUS,State,ExitCode,Start,End,Elapsed -P \
            > results/sacct.txt 2>&1 || true
    fi
fi
find runs ref -name '*.DM' -type f -print0 2>/dev/null \
    | sort -z | xargs -0 -r sha256sum > results/dm_sha256.txt || true
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
archive="evidence/CU3N_TS_YOLTLA_EVIDENCE_${stamp}.tar.gz"
include=(README_RUN.md docs config inputs/reference.fdf results plan_direct ref ts probe \
    probe_product runs .hubbardflow vendor/HUBBARDFLOW_COMMIT.txt CHECKSUMS.sha256)
for index in "${!include[@]}"; do
    [[ -e "${include[$index]}" ]] || unset 'include[index]'
done
tar -czf "$archive" \
    --exclude='*.psml' --exclude='*.PSML' --exclude='*.DM' --exclude='*.dm' \
    --exclude='*.WFSX' --exclude='*.HSX' --exclude='*.TSHS' --exclude='*.DMHS' \
    --exclude='*.RHO' --exclude='*.VT' --exclude='*.VH' --exclude='*.IOCH' \
    --exclude='*.TOCH' --exclude='*.DIFFCH' --exclude='*.csv' --exclude='*.npy' \
    --exclude='*.npz' --exclude='*.mtx' --exclude='lr_u_analysis.v3.json' \
    --exclude='hubbardflow_report_source.v1.json' --exclude='HUBBARDFLOW.out' \
    --exclude='*/chi0_matrix*.csv' --exclude='*/chi_matrix*.csv' \
    "${include[@]}"
sha256sum "$archive" | tee "$archive.sha256"
echo "EVIDENCE_ARCHIVE_WRITTEN $archive"
