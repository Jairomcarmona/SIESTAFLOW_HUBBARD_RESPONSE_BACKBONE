#!/usr/bin/env python3
"""Build two self-contained Cu3N SC(2x2x2) LR-U projector-sensitivity packages.

Each package uses one 5x20 Slurm allocation and launches one 100-rank SIESTA
calculation at a time.  The two packages differ only in the declared Cu-3d
Method-2 projector cutoff radius.
"""
from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALPHA = 0.05
TRANSLATIONS = [(i, j, k) for i in range(2) for j in range(2) for k in range(2)]
PARENT = (("X", (0.5, 0.0, 0.0)), ("Y", (0.0, 0.5, 0.0)), ("Z", (0.0, 0.0, 0.5)))


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8", newline="\n")


def run_records():
    records = [{"id": "00_REFERENCE", "mode": "REFERENCE", "target": None, "alpha_ev": 0.0}]
    for number, rep in ((10, "X"), (20, "Y"), (30, "Z")):
        for mode, suffix in (("BARE", "BARE"), ("SCREENED", "SCREENED")):
            for sign, value in (("MINUS", -ALPHA), ("PLUS", ALPHA)):
                records.append({"id": f"{number}_{rep}_{suffix}_{sign}", "mode": mode, "target": f"CuLR{(number//10-1):02d}", "alpha_ev": value})
    return records


def sites():
    out = []
    for tindex, translation in enumerate(TRANSLATIONS):
        for parent_index, (orientation, frac) in enumerate(PARENT):
            index = 3 * tindex + parent_index
            out.append({"index": index, "label": f"CuLR{index:02d}", "orientation": orientation,
                        "translation": list(translation),
                        "fractional_supercell": [(frac[d] + translation[d]) / 2 for d in range(3)]})
    return out


def fdf(record: dict, rc: float) -> str:
    labels = [f"CuLR{i:02d}" for i in range(24)]
    atom_lines, species = [], []
    for i, label in enumerate(labels, 1): species.append(f"  {i} 29 {label}")
    species.append("  25 7 N")
    for site in sites():
        x, y, z = site["fractional_supercell"]; atom_lines.append(f"  {x:.8f} {y:.8f} {z:.8f} {site['index']+1} # {site['label']}")
    for i, j, k in TRANSLATIONS:
        atom_lines.append(f"  {i/2:.8f} {j/2:.8f} {k/2:.8f} 25 # N")
    projectors = []
    for label in labels:
        shift = record["alpha_ev"] if label == record["target"] else 0.0
        projectors += [f"  {label} 1", "  3 2", f"  {shift:+.4f} 0.0000", f"  {rc:.4f} 0.0500"]
    common = [
        "XC.Functional GGA", "XC.Authors PBE", "Spin non-polarized", "PAO.BasisSize DZP",
        "PAO.EnergyShift 0.005 Ry", "PAO.SplitNorm 0.15", "PAO.BasisType split", "MeshCutoff 200 Ry",
        "%block kgrid_Monkhorst_Pack", "  2 0 0 0.0", "  0 2 0 0.0", "  0 0 2 0.0", "%endblock kgrid_Monkhorst_Pack",
        "OccupationFunction FD", "ElectronicTemperature 300 K", "MD.NumCGsteps 0", "%block DFTU.Proj", *projectors,
        "%endblock DFTU.Proj", "DFTU.ProjectorGenerationMethod 2", "DFTU.PotentialShift true",
    ]
    if record["mode"] == "REFERENCE":
        controls = ["DFTU.FirstIteration false", "SCF.MustConverge T", "SCF.Mix Hamiltonian", "SCF.Mixer.Method Pulay", "SCF.Mixer.Weight 0.05", "SCF.Mixer.History 8", "SCF.DM.Converge T", "SCF.H.Converge T", "SCF.DM.Tolerance 1.0e-5", "SCF.H.Tolerance 1.0e-4 eV", "MaxSCFIterations 300", "DM.UseSaveDM false"]
    elif record["mode"] == "BARE":
        controls = ["DFTU.FirstIteration true", "MaxSCFIterations 1", "SCF.MustConverge F", "SCF.Mix Hamiltonian", "SCF.Mixer.Method Pulay", "SCF.Mixer.Weight 0.05", "SCF.Mixer.History 8", "DM.UseSaveDM true"]
    else:
        controls = ["DFTU.FirstIteration true", "SCF.MustConverge T", "SCF.Mix Hamiltonian", "SCF.Mixer.Method Pulay", "SCF.Mixer.Weight 0.05", "SCF.Mixer.History 8", "SCF.DM.Converge T", "SCF.H.Converge T", "SCF.DM.Tolerance 1.0e-5", "SCF.H.Tolerance 1.0e-4 eV", "MaxSCFIterations 300", "DM.UseSaveDM true"]
    return "\n".join(["SystemName Cu3N PBE LR-U SC222 projector sensitivity", f"SystemLabel {record['id']}", "NumberOfAtoms 32", "NumberOfSpecies 25", "%block ChemicalSpeciesLabel", *species, "%endblock ChemicalSpeciesLabel", "", "LatticeConstant 3.8400 Ang", "%block LatticeVectors", "  2.000000 0.000000 0.000000", "  0.000000 2.000000 0.000000", "  0.000000 0.000000 2.000000", "%endblock LatticeVectors", "AtomicCoordinatesFormat Fractional", "%block AtomicCoordinatesAndAtomicSpecies", *atom_lines, "%endblock AtomicCoordinatesAndAtomicSpecies", "", *common, *controls, ""])


CORE = r'''#!/usr/bin/env python3
import json, re, sys
from pathlib import Path
import numpy as np
from siesta542_bare_contract import select_bare_occupations
ROOT=Path(__file__).resolve().parents[1]; N=24
def event_vectors(text):
    out=[]; current=None
    for line in text.splitlines():
        if 'hubbard_term: recalculating local occupations' in line:
            if current is not None: out.append(current)
            current=[]
        elif current is not None and 'Occupations:' in line:
            nums=re.findall(r'[-+]?(?:\d*\.\d+|\d+)(?:[Ee][-+]?\d+)?',line.split('Occupations:',1)[1])
            if len(nums)==3: current.append(float(nums[2]))
            elif len(nums)==2: current.append(float(nums[0])+float(nums[1]))
            else: raise RuntimeError(f'unrecognized Occupations line: {line}')
    if current is not None: out.append(current)
    return [x for x in out if len(x)==N]
def selected(path, mode):
    text=Path(path).read_text(errors='ignore'); err=(Path(path).parent/'siesta.err').read_text(errors='ignore') if (Path(path).parent/'siesta.err').exists() else ''
    status=(text+'\n'+err).lower()
    if not ((Path(path).parent/'0_NORMAL_EXIT').is_file() or 'siesta: normal completion' in status or 'job completed' in status): raise RuntimeError(f'normal completion missing: {path}')
    if mode in {'REFERENCE','SCREENED'} and re.search(r'scf_not_conv|scf: not converged|abnormal_termination',status): raise RuntimeError(f'SCF convergence missing: {path}')
    if mode=='BARE': return select_bare_occupations(text,N)
    ev=event_vectors(text)
    if not ev: raise RuntimeError(f'no complete 24-site Hubbard event: {path}')
    return ev[-1]
def translate(v,t):
    o=np.empty(N)
    for ti in range(8):
        i,j,k=ti//4,(ti//2)%2,ti%2; d=((i+t[0])%2)*4+((j+t[1])%2)*2+(k+t[2])%2
        for p in range(3): o[3*d+p]=v[3*ti+p]
    return o
def reconstruct(cols):
    m=np.empty((N,N)); trans=[(i,j,k) for i in range(2) for j in range(2) for k in range(2)]
    for ti,t in enumerate(trans):
        for p in range(3): m[:,3*ti+p]=translate(cols[p],t)
    return m
def main():
    cfg=json.loads((ROOT/'campaign.json').read_text()); runs=json.loads((ROOT/'runs/manifest.json').read_text()); raw={}
    for r in runs: raw[r['id']]=selected(ROOT/'runs'/r['id']/'siesta.out',r['mode'])
    (ROOT/'results/raw_occupations').mkdir(parents=True,exist_ok=True); (ROOT/'results/raw_occupations/occupations.json').write_text(json.dumps(raw,indent=2)+'\n')
    cols0=[]; cols=[]
    for number,rep in ((10,'X'),(20,'Y'),(30,'Z')):
        d=lambda a,b:(np.asarray(raw[a])-np.asarray(raw[b]))/(2*cfg['alpha_ev'])
        cols0.append(d(f'{number}_{rep}_BARE_PLUS',f'{number}_{rep}_BARE_MINUS')); cols.append(d(f'{number}_{rep}_SCREENED_PLUS',f'{number}_{rep}_SCREENED_MINUS'))
    chi0raw,reduced=reconstruct(cols0),reconstruct(cols); chi0=(chi0raw+chi0raw.T)/2; chi=(reduced+reduced.T)/2
    rank0,rank=int(np.linalg.matrix_rank(chi0)),int(np.linalg.matrix_rank(chi)); result={'campaign_id':cfg['campaign_id'],'status':'FAIL','n_hubbard_sites':N,'matrix_dimension':N,'alpha_ev':cfg['alpha_ev'],'projector':cfg['projector'],'rank_chi0':rank0,'rank_chi':rank,'condition_chi0':float(np.linalg.cond(chi0)),'condition_chi':float(np.linalg.cond(chi)),'notes':[]}
    out=ROOT/'results/matrices'; out.mkdir(parents=True,exist_ok=True)
    for name,a in [('chi0_raw',chi0raw),('chi_raw',reduced),('chi0',chi0),('chi',chi)]: np.savetxt(out/(name+'.csv'),a,delimiter=',',fmt='%.16g')
    if rank0!=N or rank!=N: result['notes']=['SCIENTIFIC_ANALYSIS_FAILED: SINGULAR_RESPONSE_MATRIX']
    else:
        i0,i=np.linalg.inv(chi0),np.linalg.inv(chi); K=i0-i; u=np.diag(K)
        for name,a in [('chi0_inverse',i0),('chi_inverse',i),('K_hubbard_kernel_ev',K),('U_by_site',u)]: np.savetxt(out/(name+'.csv'),a,delimiter=',',fmt='%.16g')
        result.update(status='PASS',U_Cu_eV=float(u.mean()),U_by_site_eV={f'CuLR{x:02d}':float(v) for x,v in enumerate(u)},inversion_residuals={'chi0':float(np.linalg.norm(i0@chi0-np.eye(N))),'chi':float(np.linalg.norm(i@chi-np.eye(N)))})
    (ROOT/'results/final').mkdir(parents=True,exist_ok=True); target=ROOT/'results/final/campaign_result.json'; target.write_text(json.dumps(result,indent=2)+'\n'); print(target)
if __name__=='__main__': main()
'''


def dag(package: str) -> str:
    return f'''#!/bin/bash
# Validated single-allocation LR-U DAG: five nodes x twenty ranks = 100 ranks.
# One SIESTA FDF runs at a time with all 100 ranks; no arrays or background MPI.
#SBATCH --job-name={package.lower()}
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
NODES=5; RANKS=100; PPN=20
RUNS=(00_REFERENCE 10_X_BARE_MINUS 10_X_BARE_PLUS 10_X_SCREENED_MINUS 10_X_SCREENED_PLUS 20_Y_BARE_MINUS 20_Y_BARE_PLUS 20_Y_SCREENED_MINUS 20_Y_SCREENED_PLUS 30_Z_BARE_MINUS 30_Z_BARE_PLUS 30_Z_SCREENED_MINUS 30_Z_SCREENED_PLUS)
fail() {{ echo "DAG_ERROR: $*" >&2; exit 1; }}
[[ "${{SLURM_JOB_NUM_NODES:-}}" == "$NODES" && "${{SLURM_NTASKS:-}}" == "$RANKS" ]] || fail "incorrect Slurm allocation"
mapfile -t HOSTS_A < <(scontrol show hostnames "$SLURM_JOB_NODELIST"); [[ "${{#HOSTS_A[@]}}" == "$NODES" ]] || fail "host resolution"
HOSTS="$(IFS=,; echo "${{HOSTS_A[*]}}")"
module purge; module load siesta/5.4.2; module load python/3.12
SIESTA="$(command -v siesta)"; MPI="$(command -v mpiexec.hydra)"; [[ -x "$SIESTA" && -x "$MPI" ]] || fail "runtime unavailable"
mpi() {{ "$MPI" -bootstrap ssh -hosts "$HOSTS" -ppn "$PPN" -n "$RANKS" "$@"; }}
PROBE="$(mktemp "$ROOT/slurm/placement_${{SLURM_JOB_ID}}.XXXX")"; trap 'rm -f "$PROBE"' EXIT; mpi /bin/hostname -s > "$PROBE"
for h in "${{HOSTS_A[@]}}"; do [[ "$(grep -Fxc "$h" "$PROBE" || true)" == "$PPN" ]] || fail "MPI placement for $h"; done
echo "DAG_MPI_PLACEMENT_OK: hosts=$HOSTS ranks=$RANKS ppn=$PPN"
normal() {{ [[ -f "$1/0_NORMAL_EXIT" ]] || grep -qiE 'siesta: normal completion|job completed' "$1/siesta.out"; }}
valid() {{ local r="$1" d="$ROOT/runs/$1" mode; [[ -s "$d/siesta.out" ]] && normal "$d" || return 1; if [[ "$r" == 00_REFERENCE ]]; then mode=REFERENCE; elif [[ "$r" == *BARE* ]]; then mode=BARE; else mode=SCREENED; fi; if [[ "$mode" != BARE ]]; then ! grep -Eqi 'SCF_NOT_CONV|SCF: not converged|ABNORMAL_TERMINATION' "$d/siesta.out" "$d/siesta.err" 2>/dev/null || return 1; fi; python "$ROOT/scripts/validate_run.py" "$d/siesta.out" "$mode" >/dev/null; [[ "$r" != 00_REFERENCE || -s "$d/00_REFERENCE.DM" ]]; }}
stage() {{ local r="$1" d="$ROOT/runs/$1"; for n in $(seq -w 0 23); do cp -fp "$ROOT/pseudopotentials/Cu.psml" "$d/CuLR$n.psml"; done; cp -fp "$ROOT/pseudopotentials/N.psml" "$d/N.psml"; [[ "$r" == 00_REFERENCE ]] || cp -fp "$ROOT/runs/00_REFERENCE/00_REFERENCE.DM" "$d/$r.DM"; }}
for r in "${{RUNS[@]}}"; do d="$ROOT/runs/$r"; if [[ -e "$d/siesta.out" || -e "$d/siesta.err" ]]; then valid "$r" || fail "existing run failed scientific validation: $r"; echo "DAG_SKIP_VALID: $r"; continue; fi; [[ "$r" == 00_REFERENCE || -s "$ROOT/runs/00_REFERENCE/00_REFERENCE.DM" ]] || fail "reference DM missing"; echo "DAG_RUN: $r hosts=$HOSTS ranks=$RANKS ppn=$PPN"; stage "$r"; (cd "$ROOT/runs/$r"; mpi "$SIESTA" < siesta.fdf > siesta.out 2> siesta.err); valid "$r" || fail "scientific validation failed: $r"; echo "DAG_DONE: $r"; done
python "$ROOT/scripts/analyze.py"; echo "DAG_COMPLETE: $ROOT/results/final/campaign_result.json"
'''


def build(rc: float) -> Path:
    key = str(rc).replace(".", "p")
    name = f"CU3N_PBE_LRU_SC222_RC{key}_V1"
    package = ROOT / name
    if package.exists(): shutil.rmtree(package)
    for d in ("geometry", "pseudopotentials", "runs", "results/final", "results/matrices", "results/raw_occupations", "scripts", "slurm"):
        (package / d).mkdir(parents=True, exist_ok=True)
    config = {"campaign_id": name, "material": "Cu3N", "functional": "PBE", "supercell": [2, 2, 2], "n_hubbard_sites": 24, "alpha_ev": ALPHA, "projector": {"shell": [3, 2], "method": 2, "rc_bohr": rc, "omega_bohr": 0.05}, "purpose": "projector-sensitivity baseline; not a converged physical U claim"}
    write(package / "campaign.json", json.dumps(config, indent=2))
    write(package / "geometry/site_map.json", json.dumps(sites(), indent=2))
    records = run_records(); write(package / "runs/manifest.json", json.dumps(records, indent=2))
    for record in records:
        write(package / f"runs/{record['id']}/run.json", json.dumps(record, indent=2)); write(package / f"runs/{record['id']}/siesta.fdf", fdf(record, rc))
    write(package / "geometry/supercell_222.fdf", fdf(records[0], rc))
    shutil.copy2(ROOT / "production_benchmarks/pseudos/Cu.psml", package / "pseudopotentials/Cu.psml")
    shutil.copy2(ROOT / "production_benchmarks/pseudos/N.psml", package / "pseudopotentials/N.psml")
    write(package / "scripts/analyze.py", CORE)
    shutil.copy2(ROOT / "tools" / "siesta542_bare_contract.py", package / "scripts" / "siesta542_bare_contract.py")
    write(package / "scripts/validate_run.py", "from pathlib import Path\nimport sys\nsys.path.insert(0,str(Path(__file__).parent))\nfrom analyze import selected\nselected(Path(sys.argv[1]),sys.argv[2])\nprint('SEMANTIC_OCCUPATION_VALID')")
    write(package / "slurm/submit_dag.slurm", dag(name))
    write(package / "verify_package.py", f'''import json, re\nfrom pathlib import Path\nr=Path(__file__).resolve().parent; c=json.loads((r/'campaign.json').read_text()); assert c['n_hubbard_sites']==24 and c['projector']['rc_bohr']=={rc}\nrs=json.loads((r/'runs/manifest.json').read_text()); assert len(rs)==13 and sum(x['mode']=='BARE' for x in rs)==6 and sum(x['mode']=='SCREENED' for x in rs)==6\nfor x in rs:\n t=(r/'runs'/x['id']/'siesta.fdf').read_text(); assert 'NumberOfAtoms 32' in t and 'NumberOfSpecies 25' in t and len(re.findall(r'^\\s*CuLR\\d{{2}} 1\\s*$',t,re.M))==24\nprint('PACKAGE_VERIFIED: {name}')''')
    write(package / "README.md", f'''# {name}\n\nCu3N PBE finite-difference LR-U projector-sensitivity baseline. This package is one member of a paired, predeclared `rc=2.5`/`3.0` Bohr test; it is not a claim of a final physical U.\n\n- SC(2x2x2): 32 atoms, 24 explicit Cu 3d Hubbard sites.\n- Three crystallographic Cu representatives (X/Y/Z); 13 SIESTA calculations: reference + 6 BARE + 6 SCREENED.\n- `alpha=+/-0.05 eV`, Method 2, `omega=0.05 Bohr`, `rc={rc} Bohr`.\n- One validated DAG allocation: 5 nodes x 20 ranks, then one 100-rank FDF at a time.\n\nRun `python verify_package.py`, then `sbatch slurm/submit_dag.slurm`.\n''')
    archive = ROOT / f"{name}.zip"
    if archive.exists(): archive.unlink()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for path in package.rglob("*"):
            if path.is_file(): z.write(path, path.relative_to(ROOT).as_posix())
    return archive


if __name__ == "__main__":
    for radius in (2.5, 3.0): print(build(radius))
