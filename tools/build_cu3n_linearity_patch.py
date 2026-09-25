#!/usr/bin/env python3
"""Create a post-reference Cu3N ±0.025 eV linearity-check deployment patch.

The patch deliberately contains no reference FDF and no pseudopotential.  It
is deployed into the two already completed Cu3N campaigns, reuses their saved
reference DM and their analysed ±0.05 eV occupations, and only runs the four
new X-site finite-difference calculations per projector radius.
"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

from build_cu3n_projector_campaigns import CORE, fdf, write


ROOT = Path(__file__).resolve().parents[1]
ALPHA_FINE = 0.025
RUNS = (
    ("40_X_BARE_MINUS", "BARE", -ALPHA_FINE),
    ("40_X_BARE_PLUS", "BARE", ALPHA_FINE),
    ("40_X_SCREENED_MINUS", "SCREENED", -ALPHA_FINE),
    ("40_X_SCREENED_PLUS", "SCREENED", ALPHA_FINE),
)


ANALYSE = r'''#!/usr/bin/env python3
"""Compare the existing ±0.05 eV and new ±0.025 eV Cu3N X-site slopes."""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from analyze import selected

COARSE_ALPHA = 0.05
FINE_ALPHA = 0.025
TARGET = 0


def derivative(plus, minus, alpha):
    return (np.asarray(plus, float) - np.asarray(minus, float)) / (2.0 * alpha)


def summary(coarse, fine):
    absolute = fine - coarse
    denominator = max(float(np.linalg.norm(coarse)), np.finfo(float).eps)
    return {
        "coarse_target_dn_dalpha_e_per_ev": float(coarse[TARGET]),
        "fine_target_dn_dalpha_e_per_ev": float(fine[TARGET]),
        "target_relative_difference": float(abs(absolute[TARGET]) / max(abs(coarse[TARGET]), np.finfo(float).eps)),
        "vector_relative_l2_difference": float(np.linalg.norm(absolute) / denominator),
        "coarse_vector_e_per_ev": coarse.tolist(),
        "fine_vector_e_per_ev": fine.tolist(),
    }


def main():
    baseline_path = ROOT / "results/raw_occupations/occupations.json"
    if not baseline_path.is_file():
        raise RuntimeError("missing analysed ±0.05 eV occupations")
    baseline = {key: np.asarray(value, float) for key, value in json.loads(baseline_path.read_text()).items()}
    result = {"status": "ANALYZED", "target": "CuLR00", "coarse_alpha_ev": COARSE_ALPHA, "fine_alpha_ev": FINE_ALPHA}
    for mode in ("BARE", "SCREENED"):
        coarse = derivative(baseline[f"10_X_{mode}_PLUS"], baseline[f"10_X_{mode}_MINUS"], COARSE_ALPHA)
        fine = derivative(
            selected(ROOT / "runs" / f"40_X_{mode}_PLUS" / "siesta.out", mode),
            selected(ROOT / "runs" / f"40_X_{mode}_MINUS" / "siesta.out", mode),
            FINE_ALPHA,
        )
        result[mode.lower()] = summary(coarse, fine)
    target_error = max(result["bare"]["target_relative_difference"], result["screened"]["target_relative_difference"])
    result["linearity_assessment"] = "CONSISTENT_WITHIN_5_PERCENT" if target_error <= 0.05 else "REVIEW_REQUIRED"
    result["max_target_relative_difference"] = target_error
    target = ROOT / "results/final/linearity_alpha_0p025.json"
    target.write_text(json.dumps(result, indent=2) + "\n")
    print(target)


if __name__ == "__main__":
    main()
'''


def dag(name: str) -> str:
    run_ids = " ".join(record[0] for record in RUNS)
    return f'''#!/bin/bash
# Post-reference Cu3N linearity DAG: one 100-rank FDF at a time.
# It never runs or overwrites the completed reference or ±0.05 eV runs.
#SBATCH --job-name={name.lower()}_lin
#SBATCH --partition=tt2d-100p
#SBATCH --nodes=5
#SBATCH --ntasks=100
#SBATCH --ntasks-per-node=20
#SBATCH --cpus-per-task=1
#SBATCH --time=2-00:00:00
#SBATCH --output=slurm/linearity_%j.out
#SBATCH --error=slurm/linearity_%j.err
set -euo pipefail
ROOT="$(cd "${{SLURM_SUBMIT_DIR:-$PWD}}" && pwd)"
NODES=5; RANKS=100; PPN=20
RUNS=({run_ids})
fail() {{ echo "LINEARITY_DAG_ERROR: $*" >&2; exit 1; }}
[[ "${{SLURM_JOB_NUM_NODES:-}}" == "$NODES" && "${{SLURM_NTASKS:-}}" == "$RANKS" ]] || fail "incorrect Slurm allocation"
test -s "$ROOT/runs/00_REFERENCE/00_REFERENCE.DM" || fail "reference DM missing"
test -s "$ROOT/results/raw_occupations/occupations.json" || fail "missing analysed ±0.05 eV occupations"
mapfile -t HOSTS_A < <(scontrol show hostnames "$SLURM_JOB_NODELIST")
[[ "${{#HOSTS_A[@]}}" == "$NODES" ]] || fail "host resolution"
HOSTS="$(IFS=,; echo "${{HOSTS_A[*]}}")"
module purge; module load siesta/5.4.2; module load python/3.12
SIESTA="$(command -v siesta)"; MPI="$(command -v mpiexec.hydra)"
[[ -x "$SIESTA" && -x "$MPI" ]] || fail "runtime unavailable"
mpi() {{ "$MPI" -bootstrap ssh -hosts "$HOSTS" -ppn "$PPN" -n "$RANKS" "$@"; }}
PROBE="$(mktemp "$ROOT/slurm/linearity_placement_${{SLURM_JOB_ID}}.XXXX")"
trap 'rm -f "$PROBE"' EXIT
mpi /bin/hostname -s > "$PROBE"
for h in "${{HOSTS_A[@]}}"; do [[ "$(grep -Fxc "$h" "$PROBE" || true)" == "$PPN" ]] || fail "MPI placement for $h"; done
echo "LINEARITY_MPI_PLACEMENT_OK: hosts=$HOSTS ranks=$RANKS ppn=$PPN"
normal() {{ [[ -f "$1/0_NORMAL_EXIT" ]] || grep -qiE 'siesta: normal completion|job completed' "$1/siesta.out"; }}
mode_for() {{ [[ "$1" == *BARE* ]] && echo BARE || echo SCREENED; }}
valid() {{
  local r="$1" d="$ROOT/runs/$1" mode
  mode="$(mode_for "$r")"
  [[ -s "$d/siesta.out" ]] && normal "$d" || return 1
  if [[ "$mode" == SCREENED ]]; then ! grep -Eqi 'SCF_NOT_CONV|SCF: not converged|ABNORMAL_TERMINATION' "$d/siesta.out" "$d/siesta.err" 2>/dev/null || return 1; fi
  python "$ROOT/scripts/validate_run.py" "$d/siesta.out" "$mode" >/dev/null
}}
stage() {{
  local r="$1" d="$ROOT/runs/$1"
  for n in $(seq -w 0 23); do cp -fp "$ROOT/pseudopotentials/Cu.psml" "$d/CuLR$n.psml"; done
  cp -fp "$ROOT/pseudopotentials/N.psml" "$d/N.psml"
  cp -fp "$ROOT/runs/00_REFERENCE/00_REFERENCE.DM" "$d/$r.DM"
}}
for r in "${{RUNS[@]}}"; do
  d="$ROOT/runs/$r"
  if [[ -e "$d/siesta.out" || -e "$d/siesta.err" ]]; then valid "$r" || fail "existing run failed scientific validation: $r"; echo "LINEARITY_SKIP_VALID: $r"; continue; fi
  echo "LINEARITY_RUN: $r hosts=$HOSTS ranks=$RANKS ppn=$PPN"
  stage "$r"
  (cd "$d"; mpi "$SIESTA" < siesta.fdf > siesta.out 2> siesta.err)
  valid "$r" || fail "scientific validation failed: $r"
  echo "LINEARITY_DONE: $r"
done
python "$ROOT/scripts/analyze_linearity.py"
echo "LINEARITY_COMPLETE: $ROOT/results/final/linearity_alpha_0p025.json"
'''


def build_patch() -> Path:
    patch_root = ROOT / "CU3N_PBE_LRU_SC222_LINEARITY_PATCH_STAGING"
    if patch_root.exists():
        import shutil
        shutil.rmtree(patch_root)
    for radius in (2.5, 3.0):
        key = str(radius).replace(".", "p")
        name = f"CU3N_PBE_LRU_SC222_RC{key}_V1"
        package = patch_root / name
        for run_id, mode, alpha in RUNS:
            record = {"id": run_id, "mode": mode, "target": "CuLR00", "alpha_ev": alpha}
            write(package / "runs" / run_id / "run.json", json.dumps(record, indent=2))
            write(package / "runs" / run_id / "siesta.fdf", fdf(record, radius))
        write(package / "scripts" / "analyze.py", CORE)
        write(package / "scripts" / "analyze_linearity.py", ANALYSE)
        write(package / "slurm" / "submit_linearity_dag.slurm", dag(name))
    write(patch_root / "CU3N_LINEARITY_DEPLOYMENT.md", '''# Cu3N ±0.025 eV linearity deployment

Deploy this patch into the two completed Cu3N campaign directories. It adds
four new X-site runs per radius and contains no reference or existing ±0.05 eV
run files. `submit_linearity_dag.slurm` reserves five nodes with 20 ranks per
node, runs one 100-rank FDF at a time, and reuses `runs/00_REFERENCE/00_REFERENCE.DM`.

It refuses to overwrite an existing failed output. After the four new runs,
it writes `results/final/linearity_alpha_0p025.json` and compares the slopes
from ±0.025 eV against the already analysed ±0.05 eV data.
''')
    archive = ROOT / "CU3N_PBE_LRU_SC222_LINEARITY_PATCH_V1.zip"
    if archive.exists():
        archive.unlink()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
        for path in patch_root.rglob("*"):
            if path.is_file():
                output.write(path, path.relative_to(patch_root).as_posix())
    return archive


if __name__ == "__main__":
    print(build_patch())
