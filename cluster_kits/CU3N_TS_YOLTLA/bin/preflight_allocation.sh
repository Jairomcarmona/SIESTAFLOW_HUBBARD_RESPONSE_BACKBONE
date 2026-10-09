#!/usr/bin/env bash
set -euo pipefail

ROOT="${SLURM_SUBMIT_DIR:?SLURM_SUBMIT_DIR is not set}"
source "$ROOT/config/site.sh"
source "$ROOT/bin/lib.sh"
load_kit_env
[[ -n "${SLURM_JOB_ID:-}" ]] || die "not inside a Slurm allocation"
total=$((HF_NODES * HF_PPN))
[[ "${SLURM_NNODES:-}" == "$HF_NODES" ]] || die "unexpected SLURM_NNODES"
[[ "${SLURM_NTASKS:-}" == "$total" ]] || die "unexpected SLURM_NTASKS"
[[ "${SLURM_CPUS_PER_TASK:-1}" == "1" ]] || die "SLURM_CPUS_PER_TASK must be 1"
[[ "$(sha256_of "$ROOT/bin/mpiexec.hydra")" == "$EXPECTED_ADAPTER_SHA256" ]] \
    || die "Hydra adapter hash differs from the pinned value"
python3 "$ROOT/bin/prepare_backend.py"
python3 "$ROOT/bin/make_slurm_profile.py" >/dev/null
hosts="$(scontrol show hostnames "$SLURM_JOB_NODELIST" | paste -sd, -)"
mkdir -p "$ROOT/results"
output="$ROOT/results/allocation_hosts_${SLURM_JOB_ID}.txt"
"$ROOT/bin/mpiexec.hydra" -bootstrap ssh -hosts "$hosts" -np "$total" \
    -ppn "$HF_PPN" -genv HF_PREFLIGHT_ID "$SLURM_JOB_ID" /bin/hostname > "$output"
[[ "$(wc -l < "$output")" -eq "$total" ]] || die "MPI hostname preflight count differs"
echo "ALLOCATION_PREFLIGHT_PASS"
