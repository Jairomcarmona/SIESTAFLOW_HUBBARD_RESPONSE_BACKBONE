#!/usr/bin/env python3
"""Build an isolated Cu3N LR-U translation-shadow validation package.

This is intentionally *not* a new U campaign.  It uses the validated Cu3N
SC222/rc=3.0 input family, copies only its immutable input/evidence metadata,
and requires the user to provide the already-converged source reference DM at
submit time.  The package runs 12 direct perturbations: one translated site
from each of the X/Y/Z translation orbits, in BARE/SCREENED and +/- alpha.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "CU3N_PBE_LRU_SC222_RC3p0_V1"
# The shipped input directory intentionally excludes large result files.  The
# immutable columns used as the shadow prediction come from the selectively
# extracted, SHA-recorded evidence TAR; never synthesize them from inputs.
EVIDENCE = ROOT / "tmp" / "symmetry_cu3n_audit" / "CU3N_PBE_LRU_SC222_RC3p0_V1"
NAME = "CU3N_PBE_LRU_SC222_RC3p0_SYMMETRY_SHADOW_V1"
ALPHA = 0.05

# The translation (0, 0, 1/2) maps 00/01/02 to these unperturbed sites.
SHADOWS = (("X", "CuLR00", "CuLR03", 0, 3),
           ("Y", "CuLR01", "CuLR04", 1, 4),
           ("Z", "CuLR02", "CuLR05", 2, 5))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8", newline="\n")


def shadow_fdf(template: Path, run_id: str, target: str, alpha: float, mode: str) -> str:
    """Replace only SystemLabel and potential shifts in DFTU.Proj.

    It deliberately parses the projector in four-line records rather than
    globally replacing labels, which would alter ChemicalSpeciesLabel and
    invalidate the physical subspace.
    """
    lines = template.read_text(encoding="utf-8").splitlines()
    output: list[str] = []
    in_projectors = False
    index = 0
    changed_target = changed_old = False
    while index < len(lines):
        line = lines[index]
        if line.strip().lower() == "%block dftu.proj":
            in_projectors = True
            output.append(line)
            index += 1
            continue
        if line.strip().lower() == "%endblock dftu.proj":
            in_projectors = False
            output.append(line)
            index += 1
            continue
        if line.startswith("SystemLabel "):
            output.append(f"SystemLabel {run_id}")
            index += 1
            continue
        if in_projectors and index + 3 < len(lines):
            label = line.strip().split()
            shell = lines[index + 1].strip().split()
            if len(label) == 2 and label[0].startswith("CuLR") and label[1] == "1" and shell == ["3", "2"]:
                this_label = label[0]
                output.extend((line, lines[index + 1]))
                shift = alpha if this_label == target else 0.0
                output.append(f"  {shift:+.4f} 0.0000")
                output.append(lines[index + 3])
                changed_target |= this_label == target
                changed_old |= this_label == "CuLR00"
                index += 4
                continue
        output.append(line)
        index += 1
    if not changed_target or not changed_old:
        raise ValueError(f"could not set exactly the target projector in {template}")
    if mode == "BARE":
        controlled = {"maxscfiterations", "scf.mustconverge", "scf.mix", "scf.mixer.method",
                      "scf.mixer.weight", "scf.mixer.history", "dm.usesavedm"}
        output = [line for line in output if not line.strip() or line.strip().split(maxsplit=1)[0].lower() not in controlled]
        output.extend(("MaxSCFIterations 1", "SCF.MustConverge F", "SCF.Mix Hamiltonian",
                       "SCF.Mixer.Method Pulay", "SCF.Mixer.Weight 0.05", "SCF.Mixer.History 8",
                       "DM.UseSaveDM true"))
    return "\n".join(output) + "\n"


def shadow_runs() -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for ordinal, (orbit, representative, target, representative_index, target_index) in enumerate(SHADOWS, 1):
        for mode in ("BARE", "SCREENED"):
            for sign, alpha in (("MINUS", -ALPHA), ("PLUS", ALPHA)):
                records.append({
                    "id": f"{ordinal}0_SHADOW_{orbit}_{mode}_{sign}",
                    "mode": mode,
                    "orbit": orbit,
                    "representative": representative,
                    "target": target,
                    "representative_matrix_index": representative_index,
                    "target_matrix_index": target_index,
                    "alpha_ev": alpha,
                })
    return records


def dag(run_ids: list[str]) -> str:
    joined = " ".join(run_ids)
    return f'''#!/bin/bash
# Validated Yoltla single-allocation pattern: 5 nodes x 20 ranks = 100 ranks.
# Each shadow FDF is serial in the DAG but uses all 100 MPI ranks.
# SOURCE_CAMPAIGN_DIR must point to the completed original Cu3N campaign.
#SBATCH --job-name=cu3n_sym_shadow
#SBATCH --partition=tt2d-100p
#SBATCH --nodes=5
#SBATCH --ntasks=100
#SBATCH --ntasks-per-node=20
#SBATCH --cpus-per-task=1
#SBATCH --time=2-00:00:00
#SBATCH --output=slurm/dag_%j.out
#SBATCH --error=slurm/dag_%j.err
set -euo pipefail
ROOT="$(cd "${{SLURM_SUBMIT_DIR:-$PWD}}" && pwd)"
SOURCE_CAMPAIGN_DIR="${{SOURCE_CAMPAIGN_DIR:-}}"
NODES=5; RANKS=100; PPN=20
RUNS=({joined})
fail() {{ echo "DAG_ERROR: $*" >&2; exit 1; }}
[[ "${{SLURM_JOB_NUM_NODES:-}}" == "$NODES" && "${{SLURM_NTASKS:-}}" == "$RANKS" ]] || fail "incorrect Slurm allocation"
[[ -n "$SOURCE_CAMPAIGN_DIR" && -d "$SOURCE_CAMPAIGN_DIR" ]] || fail "set SOURCE_CAMPAIGN_DIR to completed Cu3N source campaign"
python "$ROOT/scripts/verify_source_campaign.py" "$SOURCE_CAMPAIGN_DIR" || fail "source campaign provenance/reference validation failed"
mapfile -t HOSTS_A < <(scontrol show hostnames "$SLURM_JOB_NODELIST")
[[ "${{#HOSTS_A[@]}}" == "$NODES" ]] || fail "host resolution"
HOSTS="$(IFS=,; echo "${{HOSTS_A[*]}}")"
module purge
module load siesta/5.4.2
module load python/3.12
SIESTA="$(command -v siesta)"; MPI="$(command -v mpiexec.hydra)"
[[ -x "$SIESTA" && -x "$MPI" ]] || fail "standard SIESTA/MPI runtime unavailable"
mpi() {{ "$MPI" -bootstrap ssh -hosts "$HOSTS" -ppn "$PPN" -n "$RANKS" "$@"; }}
PROBE="$(mktemp "$ROOT/slurm/placement_${{SLURM_JOB_ID}}.XXXX")"; trap 'rm -f "$PROBE"' EXIT
mpi /bin/hostname -s > "$PROBE"
for host in "${{HOSTS_A[@]}}"; do [[ "$(grep -Fxc "$host" "$PROBE" || true)" == "$PPN" ]] || fail "MPI placement for $host"; done
echo "DAG_MPI_PLACEMENT_OK: hosts=$HOSTS ranks=$RANKS ppn=$PPN"
normal() {{ [[ -f "$1/0_NORMAL_EXIT" ]] || grep -qiE 'siesta: normal completion|job completed' "$1/siesta.out"; }}
valid() {{
  local run="$1" directory="$ROOT/runs/$1" mode="$2"
  [[ -s "$directory/siesta.out" ]] && normal "$directory" || return 1
  if [[ "$mode" == SCREENED ]]; then ! grep -Eqi 'SCF_NOT_CONV|SCF: not converged|ABNORMAL_TERMINATION|MPI_Abort|pseudo_read: ERROR' "$directory/siesta.out" "$directory/siesta.err" 2>/dev/null || return 1; fi
  python "$ROOT/scripts/validate_run.py" "$directory/siesta.out" "$mode" >/dev/null
}}
stage() {{
  local run="$1" directory="$ROOT/runs/$1"
  for n in $(seq -w 0 23); do cp -fp "$ROOT/pseudopotentials/Cu.psml" "$directory/CuLR$n.psml"; done
  cp -fp "$ROOT/pseudopotentials/N.psml" "$directory/N.psml"
  cp -fp "$SOURCE_CAMPAIGN_DIR/runs/00_REFERENCE/00_REFERENCE.DM" "$directory/$run.DM"
}}
for run in "${{RUNS[@]}}"; do
  directory="$ROOT/runs/$run"; mode="$(python "$ROOT/scripts/run_field.py" "$run" mode)"
  if [[ -e "$directory/siesta.out" || -e "$directory/siesta.err" ]]; then valid "$run" "$mode" || fail "existing run failed scientific validation: $run"; echo "DAG_SKIP_VALID: $run"; continue; fi
  echo "DAG_RUN: $run hosts=$HOSTS ranks=$RANKS ppn=$PPN"
  stage "$run"
  (cd "$directory"; mpi "$SIESTA" < siesta.fdf > siesta.out 2> siesta.err)
  valid "$run" "$mode" || fail "scientific validation failed: $run"
  echo "DAG_DONE: $run"
done
python "$ROOT/scripts/analyze_shadow.py"
echo "DAG_COMPLETE: $ROOT/results/final/symmetry_shadow_result.json"
'''


RUN_FIELD = '''#!/usr/bin/env python3
import json, sys
from pathlib import Path
records = json.loads((Path(__file__).resolve().parents[1] / "runs" / "manifest.json").read_text())
record = next((item for item in records if item["id"] == sys.argv[1]), None)
if record is None: raise SystemExit(f"unknown run: {sys.argv[1]}")
print(record[sys.argv[2]])
'''


VALIDATE_RUN = '''#!/usr/bin/env python3
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from analyze_shadow import selected
selected(Path(sys.argv[1]), sys.argv[2])
print("SEMANTIC_OCCUPATION_VALID")
'''


VERIFY_SOURCE = '''#!/usr/bin/env python3
import hashlib, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
expected = json.loads((ROOT / "source_provenance.json").read_text())
source = Path(sys.argv[1]).resolve()
def sha(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1048576),b""): h.update(b)
    return h.hexdigest()
for rel, digest in expected["required_sha256"].items():
    actual = source / rel
    if not actual.is_file() or sha(actual) != digest:
        raise SystemExit(f"source checksum mismatch: {rel}")
out = (source / "runs/00_REFERENCE/siesta.out").read_text(errors="ignore").lower()
err = (source / "runs/00_REFERENCE/siesta.err").read_text(errors="ignore") if (source / "runs/00_REFERENCE/siesta.err").is_file() else ""
state = out + "\\n" + err.lower()
if not ("job completed" in state or "siesta: normal completion" in state or ">> end of run" in state):
    raise SystemExit("source reference lacks normal completion")
if re.search(r"scf_not_conv|scf: not converged|abnormal_termination|mpi_abort", state):
    raise SystemExit("source reference is not converged")
for token in ("spin configuration = none", "number of spin components = 1", "time-reversal symmetry = t"):
    if token not in state: raise SystemExit(f"source non-magnetic state not certified: {token}")
print("SOURCE_CAMPAIGN_CERTIFIED")
'''


ANALYZE = '''#!/usr/bin/env python3
"""Parse direct shadow responses and compare to immutable archived columns."""
import json, re
from pathlib import Path
import numpy as np
from siesta542_bare_contract import select_bare_occupations

ROOT=Path(__file__).resolve().parents[1]
N=24
ABS_OCC_E=2.0e-5
ABS_RESPONSE=5.0e-5
REL_RESPONSE=1.0e-3

def event_vectors(text):
    events=[]; current=None
    for line in text.splitlines():
        if "hubbard_term: recalculating local occupations" in line:
            if current is not None: events.append(current)
            current=[]
        elif current is not None and "Occupations:" in line:
            values=re.findall(r"[-+]?(?:\\d*\\.\\d+|\\d+)(?:[Ee][-+]?\\d+)?", line.split("Occupations:",1)[1])
            if len(values)==3: current.append(float(values[2]))
            elif len(values)==2: current.append(float(values[0])+float(values[1]))
            else: raise RuntimeError(f"unrecognized Occupations line: {line}")
    if current is not None: events.append(current)
    return [event for event in events if len(event)==N]

def selected(path, mode):
    path=Path(path); text=path.read_text(errors="ignore")
    err=(path.parent/"siesta.err").read_text(errors="ignore") if (path.parent/"siesta.err").is_file() else ""
    state=(text+"\\n"+err).lower()
    if not ((path.parent/"0_NORMAL_EXIT").is_file() or "siesta: normal completion" in state or "job completed" in state): raise RuntimeError(f"normal completion missing: {path}")
    if mode=="SCREENED" and re.search(r"scf_not_conv|scf: not converged|abnormal_termination|mpi_abort",state): raise RuntimeError(f"SCF convergence missing: {path}")
    if mode=="BARE": return np.asarray(select_bare_occupations(text,N))
    events=event_vectors(text)
    if not events: raise RuntimeError(f"no complete {N}-site Hubbard event: {path}")
    return np.asarray(events[-1])

def main():
    cfg=json.loads((ROOT/"campaign.json").read_text()); runs=json.loads((ROOT/"runs/manifest.json").read_text())
    chi0=np.loadtxt(ROOT/"reference_evidence/chi0.csv",delimiter=","); chi=np.loadtxt(ROOT/"reference_evidence/chi.csv",delimiter=",")
    archived_raw={key:np.asarray(value) for key,value in json.loads((ROOT/"reference_evidence/occupations.json").read_text()).items()}
    permutation=np.asarray([3,4,5,0,1,2,9,10,11,6,7,8,15,16,17,12,13,14,21,22,23,18,19,20])
    def translated(vector):
        output=np.empty(N); output[permutation]=vector; return output
    raw={record["id"]:selected(ROOT/"runs"/record["id"] / "siesta.out",record["mode"]) for record in runs}
    results=[]; failures=[]
    for orbit in ("X","Y","Z"):
        entries=[r for r in runs if r["orbit"]==orbit]
        target=entries[0]["target"]; j=int(entries[0]["target_matrix_index"])
        def derivative(mode):
            plus=next(r["id"] for r in entries if r["mode"]==mode and r["alpha_ev"]>0)
            minus=next(r["id"] for r in entries if r["mode"]==mode and r["alpha_ev"]<0)
            return (raw[plus]-raw[minus])/(2*cfg["alpha_ev"]), plus, minus
        direct0, plus0, minus0=derivative("BARE"); direct, plus, minus=derivative("SCREENED")
        expected0, expected=chi0[:,j],chi[:,j]
        residual0=direct0-expected0; residual=direct-expected
        occupation={}
        for record in entries:
            rep_id=f"{10 if orbit == 'X' else 20 if orbit == 'Y' else 30}_{orbit}_{record['mode']}_{'PLUS' if record['alpha_ev'] > 0 else 'MINUS'}"
            delta=raw[record['id']]-translated(archived_raw[rep_id])
            occupation[record['id']]={"reference_run":rep_id,"max_abs_e":float(np.max(abs(delta))),"relative_l2":float(np.linalg.norm(delta)/max(np.linalg.norm(archived_raw[rep_id]),1e-12))}
        item={"orbit":orbit,"target":target,"matrix_column":j,"runs":{"bare_plus":plus0,"bare_minus":minus0,"screened_plus":plus,"screened_minus":minus},"occupation_by_run":occupation,"chi0":{"max_abs_e_per_ev":float(np.max(abs(residual0))),"relative_l2":float(np.linalg.norm(residual0)/max(np.linalg.norm(expected0),1e-12))},"chi":{"max_abs_e_per_ev":float(np.max(abs(residual))),"relative_l2":float(np.linalg.norm(residual)/max(np.linalg.norm(expected),1e-12))}}
        item["pass"]=(max(x["max_abs_e"] for x in occupation.values())<=ABS_OCC_E and item["chi0"]["max_abs_e_per_ev"]<=ABS_RESPONSE and item["chi"]["max_abs_e_per_ev"]<=ABS_RESPONSE and item["chi0"]["relative_l2"]<=REL_RESPONSE and item["chi"]["relative_l2"]<=REL_RESPONSE)
        if not item["pass"]: failures.append(orbit)
        results.append(item)
    payload={"campaign_id":cfg["campaign_id"],"status":"PASS" if not failures else "FAIL","purpose":"independent direct validation of translation-only symmetry reduction","alpha_ev":cfg["alpha_ev"],"tolerances":{"occupation_reference_max_abs_e":ABS_OCC_E,"response_column_max_abs_e_per_ev":ABS_RESPONSE,"response_column_relative_l2":REL_RESPONSE},"results":results,"failed_orbits":failures,"notes":["No orbital rotation is certified or tested.","A PASS authorizes only the tested translation subgroup and only this immutable input family."]}
    (ROOT/"results/raw_occupations").mkdir(parents=True,exist_ok=True); (ROOT/"results/raw_occupations"/"occupations.json").write_text(json.dumps({key:value.tolist() for key,value in raw.items()},indent=2)+"\\n")
    target=ROOT/"results/final/symmetry_shadow_result.json"; target.parent.mkdir(parents=True,exist_ok=True); target.write_text(json.dumps(payload,indent=2)+"\\n"); print(target)
    if failures: raise SystemExit("SHADOW_VALIDATION_FAILED: " + ",".join(failures))
if __name__=="__main__": main()
'''


README = '''# Cu3N translation-shadow LR-U validation

This package directly tests the translation-only symmetry reduction previously
used by `CU3N_PBE_LRU_SC222_RC3p0_V1`. It is not a new U calculation and never
overwrites its source campaign.

It executes 12 SIESTA calculations in one validated 100-rank Slurm allocation:
for each translated shadow `CuLR03`, `CuLR04`, and `CuLR05`, BARE and SCREENED
responses at `-0.05` and `+0.05` eV are compared with the corresponding
immutable reconstructed column and sign-resolved occupations in the archived
original evidence.

Deployment requires the absolute path of the completed original campaign:

```bash
SOURCE_CAMPAIGN_DIR=/absolute/path/CU3N_PBE_LRU_SC222_RC3p0_V1 \\
  sbatch slurm/submit_shadow_dag.slurm
```

The DAG refuses a reference DM, reference FDF, pseudopotential, source
campaign metadata, or non-magnetic reference state that does not match the
provenance manifest. It uses only `module load siesta/5.4.2`.
'''


DEPLOYMENT = '''# Deployment on Yoltla

This package must live beside, not inside, the completed source campaign. The
source campaign is read-only during this validation.

```bash
ROOT=/absolute/path/containing/both/campaigns
cd "$ROOT"

unzip -q CU3N_PBE_LRU_SC222_RC3p0_SYMMETRY_SHADOW_V1.zip
cd "$ROOT/CU3N_PBE_LRU_SC222_RC3p0_SYMMETRY_SHADOW_V1"

module load python/3.12
python verify_package.py
bash -n slurm/submit_shadow_dag.slurm

test -s "$ROOT/CU3N_PBE_LRU_SC222_RC3p0_V1/runs/00_REFERENCE/00_REFERENCE.DM"

JOB=$(sbatch --parsable \\
  --export=ALL,SOURCE_CAMPAIGN_DIR="$ROOT/CU3N_PBE_LRU_SC222_RC3p0_V1" \\
  slurm/submit_shadow_dag.slurm)
echo "CU3N_SYMMETRY_SHADOW_JOB=$JOB"
squeue -j "$JOB"
```

The DAG requires the normal institutional module `siesta/5.4.2`; do not pass a
custom executable. On completion, inspect `slurm/dag_<job>.out` for
`DAG_COMPLETE` and read `results/final/symmetry_shadow_result.json`. A `FAIL`
is scientific evidence that the tested translation subgroup must not be used
automatically for this input family.
'''


def verify_package() -> str:
    return '''#!/usr/bin/env python3
import hashlib, json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
required=("campaign.json","source_provenance.json","README.md","DEPLOYMENT.md","slurm/submit_shadow_dag.slurm","scripts/analyze_shadow.py","scripts/run_field.py","scripts/validate_run.py","scripts/verify_source_campaign.py","reference_evidence/chi0.csv","reference_evidence/chi.csv","reference_evidence/occupations.json","runs/manifest.json")
missing=[item for item in required if not (ROOT/item).is_file()]
if missing: raise SystemExit("missing: "+", ".join(missing))
runs=json.loads((ROOT/"runs/manifest.json").read_text())
if len(runs)!=12: raise SystemExit("expected exactly twelve shadow runs")
for run in runs:
    if not (ROOT/"runs"/run["id"] / "siesta.fdf").is_file(): raise SystemExit("missing FDF: "+run["id"])
if {r["target"] for r in runs}!={"CuLR03","CuLR04","CuLR05"}: raise SystemExit("unexpected shadow sites")
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
expected=json.loads((ROOT/"source_provenance.json").read_text())["archived_matrix_evidence"]["files_sha256"]
for name,digest in expected.items():
    if sha(ROOT/"reference_evidence"/name)!=digest: raise SystemExit("archived evidence checksum mismatch: "+name)
print("PACKAGE_VERIFIED: "+ROOT.name)
'''


def build() -> Path:
    if not SOURCE.is_dir():
        raise SystemExit(f"source campaign missing: {SOURCE}")
    if not (EVIDENCE / "results/matrices/chi0.csv").is_file() or not (EVIDENCE / "results/matrices/chi.csv").is_file() or not (EVIDENCE / "results/raw_occupations/occupations.json").is_file():
        raise SystemExit(f"archived Cu3N matrix evidence missing: {EVIDENCE}")
    package = ROOT / NAME
    if package.exists():
        raise SystemExit(f"refusing to overwrite existing package: {package}")
    for directory in ("pseudopotentials", "reference_evidence", "runs", "results/final", "results/raw_occupations", "scripts", "slurm"):
        (package / directory).mkdir(parents=True, exist_ok=True)
    for name in ("Cu.psml", "N.psml"):
        shutil.copy2(SOURCE / "pseudopotentials" / name, package / "pseudopotentials" / name)
    for name in ("chi0.csv", "chi.csv"):
        shutil.copy2(EVIDENCE / "results/matrices" / name, package / "reference_evidence" / name)
    shutil.copy2(EVIDENCE / "results/raw_occupations/occupations.json", package / "reference_evidence" / "occupations.json")
    runs = shadow_runs()
    for record in runs:
        source_template = SOURCE / "runs" / f"10_X_{record['mode']}_{'PLUS' if record['alpha_ev'] > 0 else 'MINUS'}" / "siesta.fdf"
        write(package / "runs" / str(record["id"]) / "siesta.fdf", shadow_fdf(source_template, str(record["id"]), str(record["target"]), float(record["alpha_ev"]), str(record["mode"])))
        write(package / "runs" / str(record["id"]) / "run.json", json.dumps(record, indent=2))
    write(package / "runs/manifest.json", json.dumps(runs, indent=2))
    source_files = ("campaign.json", "runs/00_REFERENCE/siesta.fdf", "pseudopotentials/Cu.psml", "pseudopotentials/N.psml")
    evidence_files = {"chi0.csv": EVIDENCE / "results/matrices/chi0.csv", "chi.csv": EVIDENCE / "results/matrices/chi.csv", "occupations.json": EVIDENCE / "results/raw_occupations/occupations.json"}
    provenance = {"source_campaign_id": "CU3N_PBE_LRU_SC222_RC3p0_V1", "required_sha256": {rel: sha256(SOURCE / rel) for rel in source_files}, "reference_dm_requirement": "runs/00_REFERENCE/00_REFERENCE.DM must be nonempty; its bytes remain at source and are never packaged", "archived_matrix_evidence": {"archive_sha256": "76f5effd3d124d1723725a9f30d4ac17056b4d892f73b4c14c6028f96a87f11f", "files_sha256": {name: sha256(path) for name, path in evidence_files.items()}}}
    write(package / "campaign.json", json.dumps({"campaign_id": NAME, "purpose": "direct translation-only shadow validation for the Cu3N SC222 rc=3.0 family", "alpha_ev": ALPHA, "n_hubbard_sites": 24, "translation_fractional": [0.0, 0.0, 0.5], "shadows": [{"orbit": orbit, "representative": representative, "shadow": shadow, "representative_index": ri, "shadow_index": si} for orbit, representative, shadow, ri, si in SHADOWS]}, indent=2))
    write(package / "source_provenance.json", json.dumps(provenance, indent=2))
    write(package / "README.md", README)
    write(package / "DEPLOYMENT.md", DEPLOYMENT)
    write(package / "verify_package.py", verify_package())
    write(package / "scripts/run_field.py", RUN_FIELD)
    write(package / "scripts/validate_run.py", VALIDATE_RUN)
    write(package / "scripts/verify_source_campaign.py", VERIFY_SOURCE)
    write(package / "scripts/analyze_shadow.py", ANALYZE)
    shutil.copy2(ROOT / "tools" / "siesta542_bare_contract.py", package / "scripts" / "siesta542_bare_contract.py")
    write(package / "slurm/submit_shadow_dag.slurm", dag([str(record["id"]) for record in runs]))
    archive = ROOT / f"{NAME}.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as handle:
        for path in sorted(package.rglob("*")):
            if path.is_file():
                handle.write(path, path.relative_to(ROOT).as_posix())
    write(ROOT / f"{NAME}.zip.sha256", f"{sha256(archive)}  {archive.name}")
    print(archive)
    return package


if __name__ == "__main__":
    build()
