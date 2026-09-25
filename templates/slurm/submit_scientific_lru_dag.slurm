#!/bin/bash
# Resumable scientific LR-U protocol.
# Resource counts are supplied at submission time. Select one explicit
# SIESTAFLOW_EXECUTION_PROFILE: local_openmpi or slurm_hydra_5x20.
# This file is installed into an individual campaign by install_scientific_dag.py.
#SBATCH --job-name=siestaflow_lru
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
VERIFY_PROJECTOR="$TOOLS/verify_method2_projector_identity.py"
ANALYSIS_ACCEPT="$TOOLS/scientific_dag_analysis.py"

# The public template carries no site or account information. A local profile
# can export SIESTAFLOW_SIESTA_MODULE, SIESTAFLOW_PYTHON_MODULE,
# SIESTAFLOW_SIESTA_BIN and SIESTAFLOW_MPI_BIN.
[[ ! -f "$SITE_PROFILE" ]] || source "$SITE_PROFILE"
readonly SIESTA_MODULE="${SIESTAFLOW_SIESTA_MODULE:-}"
readonly PYTHON_MODULE="${SIESTAFLOW_PYTHON_MODULE:-}"

fail() { echo "DAG_ERROR: $*" >&2; exit 1; }
gate_complete() {
  local gate="$1" status=VALIDATED index
  shift
  local -a args=("$@")
  python "$GATE" --state "$STATE" complete "$gate" "${args[@]}"
  for ((index=0; index<${#args[@]}; index++)); do
    if [[ "${args[$index]}" == "--status" && $((index + 1)) -lt ${#args[@]} ]]; then status="${args[$((index + 1))]}"; fi
  done
  echo "DAG_GATE_${status}: $gate"
}
gate_is_complete() { python "$GATE" --state "$STATE" is-complete "$1" "${@:2}"; }

case "${SIESTAFLOW_EXECUTION_PROFILE:-}" in
  local_openmpi)
    readonly NODES=1 RANKS=4 PPN=4 MPI_BACKEND=openmpi
    ;;
  slurm_hydra_5x20)
    readonly NODES=5 RANKS=100 PPN=20 MPI_BACKEND=hydra
    ;;
  *)
    fail "set SIESTAFLOW_EXECUTION_PROFILE to local_openmpi or slurm_hydra_5x20"
    ;;
esac
readonly PREFLIGHT_RANKS="${SIESTAFLOW_PREFLIGHT_RANKS:-1}"

[[ -f "$CONFIG" ]] || fail "missing scientific DAG configuration: $CONFIG"
for tool in "$GATE" "$MATERIALIZE" "$AUDIT" "$STAGE" "$SELECT_PSML" "$VERIFY_PROJECTOR" "$ANALYSIS_ACCEPT"; do [[ -f "$tool" ]] || fail "missing installed tool: $tool"; done

[[ "${SLURM_JOB_NUM_NODES:-}" == "$NODES" ]] || fail "expected $NODES nodes, got ${SLURM_JOB_NUM_NODES:-unset}"
[[ "${SLURM_NTASKS:-}" == "$RANKS" ]] || fail "expected $RANKS tasks, got ${SLURM_NTASKS:-unset}"
[[ "${SLURM_CPUS_PER_TASK:-}" == "1" ]] || fail "expected one CPU per MPI task, got ${SLURM_CPUS_PER_TASK:-unset}"
export OMP_NUM_THREADS=1
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
if [[ -n "${SIESTAFLOW_MPI_BIN:-}" ]]; then
  MPI_BIN="$SIESTAFLOW_MPI_BIN"
elif [[ "$MPI_BACKEND" == openmpi ]]; then
  MPI_BIN="$(command -v orterun || command -v mpiexec.openmpi || command -v mpiexec || true)"
else
  MPI_BIN="$(command -v mpiexec.hydra || true)"
fi
[[ -x "$SIESTA_BIN" && -x "$MPI_BIN" ]] || fail "SIESTA or selected $MPI_BACKEND launcher unavailable after module load"

mpi() {
  if [[ "$MPI_BACKEND" == openmpi ]]; then
    "$MPI_BIN" --host "${HOST_ARRAY[0]}:$PPN" --map-by "ppr:$PPN:node" -np "$RANKS" "$@"
  else
    "$MPI_BIN" -bootstrap ssh -hosts "$HOSTS" -ppn "$PPN" -n "$RANKS" "$@"
  fi
}
PLACEMENT="$(mktemp "$ROOT/slurm/placement_${SLURM_JOB_ID}.XXXXXX")"
trap 'rm -f "$PLACEMENT"' EXIT
mpi /bin/hostname -s > "$PLACEMENT"
for host in "${HOST_ARRAY[@]}"; do
  [[ "$(grep -Fxc "$host" "$PLACEMENT" || true)" == "$PPN" ]] || fail "$MPI_BACKEND placement is not $PPN ranks on $host"
done
echo "DAG_MPI_PLACEMENT_OK: profile=$SIESTAFLOW_EXECUTION_PROFILE hosts=$HOSTS backend=$MPI_BACKEND ranks=$RANKS ppn=$PPN"

# A previous analysis/evidence record is never trusted across a new submission.
# Gate 4 rebuilds the verdict from the current result, contract, code and inputs.
python "$GATE" --state "$STATE" invalidate --from ANALYSIS

central_label() { python -c 'import json,sys; print(json.load(open(sys.argv[1]))["central_label"])' "$CONFIG"; }
result_path() { python -c 'import json,sys; print(json.load(open(sys.argv[1]))["result_file"])' "$CONFIG"; }
analysis_script() { python -c 'import json,sys; print(json.load(open(sys.argv[1]))["analysis_script"])' "$CONFIG"; }
run_mode() { python -c 'import json,sys; r=next(x for x in json.load(open(sys.argv[1])) if x["id"]==sys.argv[2]); print(r["mode"])' "$ROOT/runs/manifest.json" "$1"; }
run_parent_dm() { python -c 'import json,sys; r=next(x for x in json.load(open(sys.argv[1])) if x["id"]==sys.argv[2]); print(r.get("parent_dm") or "")' "$ROOT/runs/manifest.json" "$1"; }
all_runs() { python -c 'import json,sys; print("\n".join(x["id"] for x in json.load(open(sys.argv[1]))))' "$ROOT/runs/manifest.json"; }
child_runs() { python -c 'import json,sys; print("\n".join(x["id"] for x in json.load(open(sys.argv[1])) if x["mode"]!="REFERENCE"))' "$ROOT/runs/manifest.json"; }

normal_exit() { [[ -f "$1/0_NORMAL_EXIT" ]] || grep -qiE 'siesta: normal completion|job completed' "$1/siesta.out"; }
validate_outputs() {
  local run="$1" directory="$ROOT/runs/$1" mode label
  mode="$(run_mode "$run")"
  [[ -s "$directory/siesta.out" ]] && normal_exit "$directory" || return 1
  if [[ "$mode" != "BARE" ]]; then
    ! grep -Eqi 'SCF_NOT_CONV|SCF: not converged|ABNORMAL_TERMINATION|MPI_Abort|pseudo_read: ERROR' "$directory/siesta.out" "$directory/siesta.err" 2>/dev/null || return 1
  fi
  python "$ROOT/scripts/validate_run.py" "$directory/siesta.out" "$mode" >/dev/null
  if [[ "$mode" == "REFERENCE" ]]; then
    [[ -s "$directory/${run}.DM" ]] || return 1
    [[ ! -f "$ROOT/scripts/validate_reference_state.py" ]] || python "$ROOT/scripts/validate_reference_state.py" "$directory/siesta.out" >/dev/null
    label="$(central_label)"
    python "$VERIFY_PROJECTOR" --reference-fdf "$directory/siesta.fdf" --reference-dir "$directory" --candidate-fdf "$directory/siesta.fdf" --candidate-dir "$directory" >/dev/null || return 1
    python "$VERIFY_PROJECTOR" --reference-fdf "$directory/siesta.fdf" --reference-dir "$directory" --preflight-dir "$ROOT/preflight/materialized" --label "$label" --pseudo-directory "$ROOT/pseudopotentials" >/dev/null || return 1
  else
    python "$VERIFY_PROJECTOR" --reference-fdf "$ROOT/runs/00_REFERENCE/siesta.fdf" --reference-dir "$ROOT/runs/00_REFERENCE" --candidate-fdf "$directory/siesta.fdf" --candidate-dir "$directory" >/dev/null || return 1
  fi
}

run_input_fingerprint() {
  local run="$1" directory="$ROOT/runs/$1" mode
  mode="$(run_mode "$run")"
  PYTHONPATH="$TOOLS${PYTHONPATH:+:$PYTHONPATH}" python - "$ROOT" "$directory" "$run" "$mode" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

from verify_method2_projector_identity import (
    fdf_sha256,
    projector_configuration_fingerprint,
    selected_psml_hashes,
)

root, run_dir = Path(sys.argv[1]), Path(sys.argv[2])
run_id, mode = sys.argv[3], sys.argv[4]
fdf = run_dir / "siesta.fdf"
if not fdf.is_file():
    raise SystemExit(f"missing FDF for input fingerprint: {fdf}")
manifest = json.loads((root / "runs" / "manifest.json").read_text(encoding="utf-8"))
record = next((item for item in manifest if item.get("id") == run_id), None)
if record is None:
    raise SystemExit(f"run is absent from manifest: {run_id}")
pseudo_files = sorted(run_dir.glob("*.psml"), key=lambda path: path.name)
if not pseudo_files:
    raise SystemExit(f"no staged PSML files for input fingerprint: {run_dir}")
pseudo_hashes = {
    path.stem: hashlib.sha256(path.read_bytes()).hexdigest()
    for path in pseudo_files
}
if len(pseudo_hashes) != len(pseudo_files):
    raise SystemExit(f"duplicate staged PSML labels in {run_dir}")
selected_hashes = selected_psml_hashes(fdf, root / "pseudopotentials")
if set(pseudo_hashes) != set(selected_hashes):
    raise SystemExit(f"staged PSML labels do not match FDF species for {run_id}")
if pseudo_hashes != selected_hashes:
    raise SystemExit(f"staged PSML files differ from current selections for {run_id}")
parent_dm_hash = None
parent_dm_relative = record.get("parent_dm")
if parent_dm_relative:
    parent_dm = root / "runs" / parent_dm_relative
    if not parent_dm.is_file():
        raise SystemExit(f"parent DM is missing for {run_id}: {parent_dm}")
    parent_dm_hash = hashlib.sha256(parent_dm.read_bytes()).hexdigest()
payload = {
    "schema_version": 1,
    "run_id": run_id,
    "mode": mode,
    "manifest_record": record,
    "fdf_sha256": fdf_sha256(fdf),
    "projector_configuration_sha256": projector_configuration_fingerprint(fdf),
    "pseudopotential_sha256": pseudo_hashes,
    "selected_psml_sha256": selected_hashes,
    "parent_dm_sha256": parent_dm_hash,
}
canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
payload["input_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
PY
}

write_run_fingerprint() {
  local directory="$1" fingerprint="$2" temporary
  temporary="$(mktemp "$directory/.siestaflow_run_inputs.XXXXXX")"
  printf '%s\n' "$fingerprint" > "$temporary"
  mv -f "$temporary" "$directory/siestaflow_run_inputs.json"
}

valid_run() {
  local run="$1" directory="$ROOT/runs/$1" expected recorded marker
  marker="$directory/siestaflow_run_inputs.json"
  [[ -s "$marker" ]] || return 1
  expected="$(run_input_fingerprint "$run")" || return 1
  recorded="$(cat "$marker")" || return 1
  [[ "$recorded" == "$expected" ]] || return 1
  validate_outputs "$run"
}

archive_incomplete() {
  local run="$1" directory="$ROOT/runs/$1" stamp archive file
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"; archive="$ROOT/slurm/interrupted_attempts/${run}_${SLURM_JOB_ID}_${stamp}"
  for file in 0_NORMAL_EXIT siesta.out siesta.err "$run.DM" siestaflow_run_inputs.json; do
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
  local run="$1" directory="$ROOT/runs/$1" fingerprint
  [[ -d "$directory" && -s "$directory/siesta.fdf" ]] || fail "missing materialized FDF for $run"
  if valid_run "$run"; then echo "DAG_SKIP_VALID: $run"; return; fi
  echo "DAG_RUN: $run hosts=$HOSTS ranks=$RANKS ppn=$PPN"
  archive_incomplete "$run"; stage_run "$run"
  fingerprint="$(run_input_fingerprint "$run")" || fail "cannot fingerprint inputs for $run"
  (cd "$directory"; mpi "$SIESTA_BIN" < siesta.fdf > siesta.out 2> siesta.err)
  validate_outputs "$run" || fail "scientific validation failed: $run"
  write_run_fingerprint "$directory" "$fingerprint"
  valid_run "$run" || fail "accepted run fingerprint did not validate: $run"
  echo "DAG_DONE: $run"
}

# Gate 0: materialize only the Method-2 projector and audit its locality.
PREFLIGHT="$ROOT/preflight"; AUDIT_JSON="$PREFLIGHT/projector_audit.json"; AUDIT_MD="$PREFLIGHT/projector_audit.md"
label="$(central_label)"
if gate_is_complete PROJECTOR_AUDIT --require "$AUDIT_JSON" --require "$AUDIT_MD" && \
   python "$VERIFY_PROJECTOR" --reference-fdf "$ROOT/runs/00_REFERENCE/siesta.fdf" --preflight-dir "$PREFLIGHT/materialized" --label "$label" --pseudo-directory "$ROOT/pseudopotentials" >/dev/null; then
  echo "DAG_SKIP_VALID: PROJECTOR_AUDIT"
else
  mkdir -p "$PREFLIGHT"
  pseudo_args=()
  while IFS= read -r pseudo; do pseudo_args+=(--pseudo-source "$pseudo"); done < <(find "$ROOT/pseudopotentials" -maxdepth 1 -type f -name '*.psml' | sort)
  [[ "${#pseudo_args[@]}" -gt 0 ]] || fail "no PSML files in pseudopotentials"
  echo "DAG_RUN: PROJECTOR_AUDIT ranks=$PREFLIGHT_RANKS"
  python "$MATERIALIZE" --fdf "$ROOT/runs/00_REFERENCE/siesta.fdf" --central-label "$label" "${pseudo_args[@]}" --siesta "$SIESTA_BIN" --mpi-launcher "$MPI_BIN" --ranks "$PREFLIGHT_RANKS" --output-dir "$PREFLIGHT/materialized"
  central_psml="$(python "$SELECT_PSML" --fdf "$ROOT/runs/00_REFERENCE/siesta.fdf" --label "$label" --pseudo-directory "$ROOT/pseudopotentials")"
  python "$AUDIT" --fdf "$ROOT/runs/00_REFERENCE/siesta.fdf" --central-label "$label" --psml "$central_psml" --projector "$PREFLIGHT/materialized/${label}.dftu_proj" --json-out "$AUDIT_JSON" --markdown-out "$AUDIT_MD"
  python -c 'import json,sys; d=json.load(open(sys.argv[1])); assert d["status"]=="PASS_PRELIGHT_REVIEW_REQUIRED"; assert d["recommendation"]["status"]=="LOCALITY_WINDOW_AVAILABLE"' "$AUDIT_JSON" || fail "projector locality audit did not pass"
  python "$VERIFY_PROJECTOR" --reference-fdf "$ROOT/runs/00_REFERENCE/siesta.fdf" --preflight-dir "$PREFLIGHT/materialized" --label "$label" --pseudo-directory "$ROOT/pseudopotentials" >/dev/null || fail "preflight input fingerprint or projector identity did not validate"
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

# Gate 4: preserve the native campaign status and validate only its declared
# analysis contract. Recording the analysis is distinct from physical acceptance.
ANALYSIS_SCRIPT="$ROOT/$(analysis_script)"; [[ -f "$ANALYSIS_SCRIPT" ]] || fail "missing campaign algebra entry point: $ANALYSIS_SCRIPT"
python "$ANALYSIS_SCRIPT"
RESULT="$ROOT/$(result_path)"; [[ -s "$RESULT" ]] || fail "algebra did not produce declared result: $RESULT"
ANALYSIS_VERDICT="$ROOT/results/analysis-verdict.json"
python "$ANALYSIS_ACCEPT" --campaign-root "$ROOT" --config "$CONFIG" --result "$RESULT" --analysis-script "$ANALYSIS_SCRIPT" --output "$ANALYSIS_VERDICT" || fail "analysis result did not satisfy its declared acceptance contract"
ANALYSIS_STATUS="$(python -c 'import json,sys; v=json.load(open(sys.argv[1])); print("VALIDATED" if v.get("gate_decision")=="ACCEPTED" else "RECORDED")' "$ANALYSIS_VERDICT")"
ANALYSIS_DETAIL="$(python -c 'import json,sys; v=json.load(open(sys.argv[1])); print("source_status="+str(v.get("source_status"))+" analysis_state="+str(v.get("analysis_state"))+" gate_decision="+str(v.get("gate_decision"))+" physical_acceptance="+str(v.get("physical_acceptance")))' "$ANALYSIS_VERDICT")"
gate_complete ANALYSIS --status "$ANALYSIS_STATUS" --analysis-verdict "$ANALYSIS_VERDICT" --require "$RESULT" --require "$ANALYSIS_VERDICT" --detail "$ANALYSIS_DETAIL"
echo "DAG_ANALYSIS_RECORDED: $RESULT $ANALYSIS_DETAIL"

# Gate 5: record protocol state and typed analysis verdict. This evidence report
# explicitly does not claim that a numerical interval is physical validation.
EVIDENCE="$ROOT/results/evidence/scientific_dag_protocol.json"; mkdir -p "$(dirname "$EVIDENCE")"
python "$GATE" --state "$STATE" report > "$EVIDENCE"
gate_complete EVIDENCE --status RECORDED --require "$EVIDENCE" --require "$RESULT" --require "$ANALYSIS_VERDICT" --detail "protocol and analysis record captured; physical acceptance remains separately classified"
python "$GATE" --state "$STATE" report > "$EVIDENCE"
echo "DAG_PROTOCOL_RECORDED: $RESULT"
