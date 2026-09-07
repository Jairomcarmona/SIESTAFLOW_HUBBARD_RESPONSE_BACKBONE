#!/bin/bash
# Resumable scientific LR-U protocol.
# Example placement profile: 5 nodes x 20 ranks/node, one 100-rank FDF at a time.
# It is portable: select a partition at submission time and put backend details
# in slurm/site_profile.local (ignored by Git).
# This file is installed into an individual campaign by install_scientific_dag.py.
#SBATCH --job-name=siestaflow_lru
#SBATCH --nodes=5
#SBATCH --ntasks=100
#SBATCH --ntasks-per-node=20
#SBATCH --cpus-per-task=1
#SBATCH --time=2-00:00:00
#SBATCH --output=slurm/scientific_dag_%j.out
#SBATCH --error=slurm/scientific_dag_%j.err

set -euo pipefail

ROOT="$(cd "${SLURM_SUBMIT_DIR:-$(dirname "${BASH_SOURCE[0]}")/..}" && pwd)"
SITE_PROFILE="${SIESTAFLOW_SITE_PROFILE:-$ROOT/slurm/site_profile.local}"
TOOLS="$ROOT/scripts/siestaflow_dag"
STATE="$ROOT/results/scientific_dag_state.json"
CONFIG="$ROOT/scripts/scientific_dag.json"
GATE="$TOOLS/scientific_dag_gate.py"
MATERIALIZE="$TOOLS/materialize_method2_projector.py"
AUDIT="$TOOLS/audit_method2_projector.py"
STAGE="$TOOLS/stage_fdf_pseudos.py"
SELECT_PSML="$TOOLS/select_psml_for_label.py"

readonly NODES=5
readonly RANKS=100
readonly PPN=20
readonly PREFLIGHT_RANKS="${SIESTAFLOW_PREFLIGHT_RANKS:-1}"

# The public template carries no site or account information. A local profile
# can export SIESTAFLOW_SIESTA_MODULE, SIESTAFLOW_PYTHON_MODULE,
# SIESTAFLOW_SIESTA_BIN and SIESTAFLOW_MPI_BIN.
[[ ! -f "$SITE_PROFILE" ]] || source "$SITE_PROFILE"
readonly SIESTA_MODULE="${SIESTAFLOW_SIESTA_MODULE:-}"
readonly PYTHON_MODULE="${SIESTAFLOW_PYTHON_MODULE:-}"

fail() { echo "DAG_ERROR: $*" >&2; exit 1; }
gate_complete() { python "$GATE" --state "$STATE" complete "$1" "${@:2}"; echo "DAG_GATE_OK: $1"; }
gate_is_complete() { python "$GATE" --state "$STATE" is-complete "$1" "${@:2}"; }

[[ -f "$CONFIG" ]] || fail "missing scientific DAG configuration: $CONFIG"
for tool in "$GATE" "$MATERIALIZE" "$AUDIT" "$STAGE" "$SELECT_PSML"; do [[ -f "$tool" ]] || fail "missing installed tool: $tool"; done

[[ "${SLURM_JOB_NUM_NODES:-}" == "$NODES" ]] || fail "expected $NODES nodes, got ${SLURM_JOB_NUM_NODES:-unset}"
[[ "${SLURM_NTASKS:-}" == "$RANKS" ]] || fail "expected $RANKS tasks, got ${SLURM_NTASKS:-unset}"
mapfile -t HOST_ARRAY < <(scontrol show hostnames "$SLURM_JOB_NODELIST")
[[ "${#HOST_ARRAY[@]}" == "$NODES" ]] || fail "host resolution did not yield $NODES nodes"
HOSTS="$(IFS=,; echo "${HOST_ARRAY[*]}")"

if type module >/dev/null 2>&1; then
  module purge
  [[ -z "$SIESTA_MODULE" ]] || module load "$SIESTA_MODULE"
  [[ -z "$PYTHON_MODULE" ]] || module load "$PYTHON_MODULE"
elif [[ -n "$SIESTA_MODULE$PYTHON_MODULE" ]]; then
  fail "site profile requests modules, but this batch environment has no module command"
fi
SIESTA_BIN="${SIESTAFLOW_SIESTA_BIN:-$(command -v siesta || true)}"
MPI_BIN="${SIESTAFLOW_MPI_BIN:-$(command -v mpiexec.hydra || true)}"
[[ -x "$SIESTA_BIN" && -x "$MPI_BIN" ]] || fail "SIESTA or mpiexec.hydra unavailable after module load"

mpi() { "$MPI_BIN" -bootstrap ssh -hosts "$HOSTS" -ppn "$PPN" -n "$RANKS" "$@"; }
PLACEMENT="$(mktemp "$ROOT/slurm/placement_${SLURM_JOB_ID}.XXXXXX")"
trap 'rm -f "$PLACEMENT"' EXIT
mpi /bin/hostname -s > "$PLACEMENT"
for host in "${HOST_ARRAY[@]}"; do
  [[ "$(grep -Fxc "$host" "$PLACEMENT" || true)" == "$PPN" ]] || fail "Hydra placement is not $PPN ranks on $host"
done
echo "DAG_MPI_PLACEMENT_OK: hosts=$HOSTS ranks=$RANKS ppn=$PPN"

central_label() { python -c 'import json,sys; print(json.load(open(sys.argv[1]))["central_label"])' "$CONFIG"; }
result_path() { python -c 'import json,sys; print(json.load(open(sys.argv[1]))["result_file"])' "$CONFIG"; }
analysis_script() { python -c 'import json,sys; print(json.load(open(sys.argv[1]))["analysis_script"])' "$CONFIG"; }
run_mode() { python -c 'import json,sys; r=next(x for x in json.load(open(sys.argv[1])) if x["id"]==sys.argv[2]); print(r["mode"])' "$ROOT/runs/manifest.json" "$1"; }
run_parent_dm() { python -c 'import json,sys; r=next(x for x in json.load(open(sys.argv[1])) if x["id"]==sys.argv[2]); print(r.get("parent_dm") or "")' "$ROOT/runs/manifest.json" "$1"; }
all_runs() { python -c 'import json,sys; print("\n".join(x["id"] for x in json.load(open(sys.argv[1]))))' "$ROOT/runs/manifest.json"; }
child_runs() { python -c 'import json,sys; print("\n".join(x["id"] for x in json.load(open(sys.argv[1])) if x["mode"]!="REFERENCE"))' "$ROOT/runs/manifest.json"; }

normal_exit() { [[ -f "$1/0_NORMAL_EXIT" ]] || grep -qiE 'siesta: normal completion|job completed' "$1/siesta.out"; }
valid_run() {
  local run="$1" directory="$ROOT/runs/$1" mode
  mode="$(run_mode "$run")"
  [[ -s "$directory/siesta.out" ]] && normal_exit "$directory" || return 1
  if [[ "$mode" != "BARE" ]]; then
    ! grep -Eqi 'SCF_NOT_CONV|SCF: not converged|ABNORMAL_TERMINATION|MPI_Abort|pseudo_read: ERROR' "$directory/siesta.out" "$directory/siesta.err" 2>/dev/null || return 1
  fi
  python "$ROOT/scripts/validate_run.py" "$directory/siesta.out" "$mode" >/dev/null
  if [[ "$mode" == "REFERENCE" ]]; then
    [[ -s "$directory/${run}.DM" ]] || return 1
    [[ ! -f "$ROOT/scripts/validate_reference_state.py" ]] || python "$ROOT/scripts/validate_reference_state.py" "$directory/siesta.out" >/dev/null
  fi
}

archive_incomplete() {
  local run="$1" directory="$ROOT/runs/$1" stamp archive file
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"; archive="$ROOT/slurm/interrupted_attempts/${run}_${SLURM_JOB_ID}_${stamp}"
  for file in 0_NORMAL_EXIT siesta.out siesta.err "$run.DM"; do
    [[ -e "$directory/$file" ]] || continue
    mkdir -p "$archive"; mv "$directory/$file" "$archive/$file"
  done
  [[ -d "$archive" ]] && echo "DAG_ARCHIVED_INCOMPLETE: $run -> $archive"
}

stage_run() {
  local run="$1" directory="$ROOT/runs/$1" parent
  python "$STAGE" --fdf "$directory/siesta.fdf" --pseudo-directory "$ROOT/pseudopotentials" --destination "$directory" >/dev/null
  parent="$(run_parent_dm "$run")"
  if [[ -n "$parent" ]]; then
    [[ -s "$ROOT/runs/$parent" ]] || fail "parent DM missing before $run: $parent"
    cp -fp "$ROOT/runs/$parent" "$directory/$run.DM"
  fi
}

run_one() {
  local run="$1" directory="$ROOT/runs/$1"
  [[ -d "$directory" && -s "$directory/siesta.fdf" ]] || fail "missing materialized FDF for $run"
  if valid_run "$run"; then echo "DAG_SKIP_VALID: $run"; return; fi
  echo "DAG_RUN: $run hosts=$HOSTS ranks=$RANKS ppn=$PPN"
  archive_incomplete "$run"; stage_run "$run"
  (cd "$directory"; mpi "$SIESTA_BIN" < siesta.fdf > siesta.out 2> siesta.err)
  valid_run "$run" || fail "scientific validation failed: $run"
  echo "DAG_DONE: $run"
}

# Gate 0: materialize only the Method-2 projector and audit its locality.
PREFLIGHT="$ROOT/preflight"; AUDIT_JSON="$PREFLIGHT/projector_audit.json"; AUDIT_MD="$PREFLIGHT/projector_audit.md"
if gate_is_complete PROJECTOR_AUDIT --require "$AUDIT_JSON" --require "$AUDIT_MD"; then
  echo "DAG_SKIP_VALID: PROJECTOR_AUDIT"
else
  mkdir -p "$PREFLIGHT"
  label="$(central_label)"; pseudo_args=()
  while IFS= read -r pseudo; do pseudo_args+=(--pseudo-source "$pseudo"); done < <(find "$ROOT/pseudopotentials" -maxdepth 1 -type f -name '*.psml' | sort)
  [[ "${#pseudo_args[@]}" -gt 0 ]] || fail "no PSML files in pseudopotentials"
  echo "DAG_RUN: PROJECTOR_AUDIT ranks=$PREFLIGHT_RANKS"
  python "$MATERIALIZE" --fdf "$ROOT/runs/00_REFERENCE/siesta.fdf" --central-label "$label" "${pseudo_args[@]}" --siesta "$SIESTA_BIN" --mpi-launcher "$MPI_BIN" --ranks "$PREFLIGHT_RANKS" --output-dir "$PREFLIGHT/materialized"
  central_psml="$(python "$SELECT_PSML" --fdf "$ROOT/runs/00_REFERENCE/siesta.fdf" --label "$label" --pseudo-directory "$ROOT/pseudopotentials")"
  python "$AUDIT" --fdf "$ROOT/runs/00_REFERENCE/siesta.fdf" --central-label "$label" --psml "$central_psml" --projector "$PREFLIGHT/materialized/${label}.dftu_proj" --json-out "$AUDIT_JSON" --markdown-out "$AUDIT_MD"
  python -c 'import json,sys; d=json.load(open(sys.argv[1])); assert d["status"]=="PASS_PRELIGHT_REVIEW_REQUIRED"; assert d["recommendation"]["status"]=="LOCALITY_WINDOW_AVAILABLE"' "$AUDIT_JSON" || fail "projector locality audit did not pass"
  gate_complete PROJECTOR_AUDIT --require "$AUDIT_JSON" --require "$AUDIT_MD" --detail "Method-2 projector materialized and locality-audited"
fi

# Gate 1: reference SCF and its parent density matrix.
run_one 00_REFERENCE
gate_complete REFERENCE --require "$ROOT/runs/00_REFERENCE/siesta.out" --require "$ROOT/runs/00_REFERENCE/00_REFERENCE.DM" --detail "reference SCF, semantic occupations and parent DM accepted"

# Gate 2: children are either generated by a campaign hook or already materialized.
[[ ! -x "$ROOT/scripts/build_children_after_reference.py" ]] || python "$ROOT/scripts/build_children_after_reference.py"
while IFS= read -r run; do [[ -s "$ROOT/runs/$run/siesta.fdf" ]] || fail "child FDF absent after reference: $run"; done < <(child_runs)
CHILDREN_MARKER="$ROOT/results/children_materialized.json"; mkdir -p "$(dirname "$CHILDREN_MARKER")"
python -c 'import json,sys; json.dump({"status":"VALIDATED","source":"runs/manifest.json"},open(sys.argv[1],"w"),indent=2); print()' "$CHILDREN_MARKER"
gate_complete CHILDREN_MATERIALIZED --require "$CHILDREN_MARKER" --detail "child FDF inputs present only after accepted reference"

# Gate 3: BARE and SCREENED responses, one full MPI FDF at a time.
while IFS= read -r run; do run_one "$run"; done < <(child_runs)
RESPONSES_MARKER="$ROOT/results/responses_validated.json"
python -c 'import json,sys; json.dump({"status":"VALIDATED","all_children":"normal completion and semantic validation"},open(sys.argv[1],"w"),indent=2); print()' "$RESPONSES_MARKER"
gate_complete RESPONSES --require "$RESPONSES_MARKER" --detail "all BARE/SCREENED response runs accepted under mode-specific policy"

# Gate 4: campaign-specific algebra remains the only authority for chi and U.
ANALYSIS_SCRIPT="$ROOT/$(analysis_script)"; [[ -f "$ANALYSIS_SCRIPT" ]] || fail "missing campaign algebra entry point: $ANALYSIS_SCRIPT"
python "$ANALYSIS_SCRIPT"
RESULT="$ROOT/$(result_path)"; [[ -s "$RESULT" ]] || fail "algebra did not produce declared result: $RESULT"
python -c 'import json,sys; d=json.load(open(sys.argv[1])); assert d.get("status")=="PASS"; assert d.get("rank_chi0")==d.get("matrix_dimension"); assert d.get("rank_chi")==d.get("matrix_dimension")' "$RESULT" || fail "algebraic acceptance failed"
gate_complete ANALYSIS --require "$RESULT" --detail "direct LR algebra passed declared full-rank acceptance"

# Gate 5: compact protocol state is reproducible evidence alongside native SIESTA outputs.
EVIDENCE="$ROOT/results/evidence/scientific_dag_protocol.json"; mkdir -p "$(dirname "$EVIDENCE")"
python "$GATE" --state "$STATE" report > "$EVIDENCE"
gate_complete EVIDENCE --require "$EVIDENCE" --require "$RESULT" --detail "protocol gates and final result recorded"
python "$GATE" --state "$STATE" report > "$EVIDENCE"
echo "DAG_COMPLETE: $RESULT"
