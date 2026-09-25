#!/usr/bin/env python3
"""Build a direct 6x6 LR-U campaign for the validated ordered K-birnessite seed."""
from __future__ import annotations

import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NAME = "K_BIRNESSITE_PBE_LRU_ORDERED_CELL_V1"
OUT = ROOT / NAME
PSEUDO_SOURCE = Path(r"C:\Users\Jairo\Downloads\PSEUDOPOTENCIALES_pseudojo_pbe_stringent\nc-sr-05_pbe_stringent_psml")
GEOMETRY_SOURCE = Path(r"C:\Users\Jairo\Downloads\SIESTAFLOW_CONTEXT\references\k_birnessite\seed_K2Mn6O12_4H2O_v01\K2Mn6O12_4H2O_geometry_fractional.fdf")
CIF_SOURCE = Path(r"C:\Users\Jairo\Downloads\SIESTAFLOW_CONTEXT\references\k_birnessite\seed_K2Mn6O12_4H2O_v01\K2Mn6O12_4H2O_seed_v01.cif")

LATTICE = [[8.691, 0.0, 0.0], [0.0, 4.98, 0.0], [0.0, 0.0, 7.06]]
MN = [
    ("MnLR00", "MnIII", [0.0, 0.5, 0.0], +4.0),
    ("MnLR01", "MnIII", [1 / 6, 0.0, 0.0], -4.0),
    ("MnLR02", "MnIV", [1 / 3, 0.5, 0.0], +3.0),
    ("MnLR03", "MnIV", [0.5, 0.0, 0.0], -3.0),
    ("MnLR04", "MnIV", [2 / 3, 0.5, 0.0], +3.0),
    ("MnLR05", "MnIV", [5 / 6, 0.0, 0.0], -3.0),
]
OTHER = [
    ("O", [1 / 6, .667, .8622]), ("O", [0, .167, .8622]), ("O", [1 / 6, .333, .1378]), ("O", [0, .833, .1378]),
    ("O", [.5, .667, .8622]), ("O", [1 / 3, .167, .8622]), ("O", [.5, .333, .1378]), ("O", [1 / 3, .833, .1378]),
    ("O", [5 / 6, .667, .8622]), ("O", [2 / 3, .167, .8622]), ("O", [5 / 6, .333, .1378]), ("O", [2 / 3, .833, .1378]),
    ("K", [.25, .5, .48]), ("K", [.75, .5, .52]),
    ("O", [0, .229273, .5]), ("H", [.0891584147128025, .229273, .584982002044442]), ("H", [.9108415852871974, .229273, .584982002044442]),
    ("O", [.5, .229273, .5]), ("H", [.5891584147128025, .229273, .415017997955558]), ("H", [.4108415852871974, .229273, .415017997955558]),
    ("O", [0, .770727, .5]), ("H", [.0891584147128025, .770727, .584982002044442]), ("H", [.9108415852871974, .770727, .584982002044442]),
    ("O", [.5, .770727, .5]), ("H", [.5891584147128025, .770727, .415017997955558]), ("H", [.4108415852871974, .770727, .415017997955558]),
]


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.replace("\r\n", "\n").replace("\r", "\n").encode())


def run_id(site: str, mode: str, sign: str) -> str:
    return f"{int(site[-2:]) + 10:02d}_{site}_{mode}_{sign}"


def runs() -> list[dict]:
    items = [{"id": "00_REFERENCE", "mode": "REFERENCE", "target": None, "alpha_ev": 0.0, "parent_dm": None}]
    for label, valence, _, _ in MN:
        for mode in ("BARE", "SCREENED"):
            for sign, alpha in (("MINUS", -0.05), ("PLUS", 0.05)):
                items.append({"id": run_id(label, mode, sign), "mode": mode, "target": label, "alpha_ev": alpha,
                              "parent_dm": "00_REFERENCE/00_REFERENCE.DM", "declared_valence": valence})
    return items


def fdf(record: dict) -> str:
    mode, target, alpha = record["mode"], record["target"], record["alpha_ev"]
    lines = ["SystemName K2Mn6O12_4H2O ordered-cell PBE LR-U", f"SystemLabel {record['id']}",
             "NumberOfAtoms 32", "NumberOfSpecies 9", "%block ChemicalSpeciesLabel"]
    lines += [f"  {i + 1} 25 {label}" for i, (label, *_rest) in enumerate(MN)]
    lines += ["  7 19 K", "  8 8 O", "  9 1 H", "%endblock ChemicalSpeciesLabel", "", "LatticeConstant 1.0000 Ang", "%block LatticeVectors"]
    lines += ["  " + " ".join(f"{x:.8f}" for x in row) for row in LATTICE]
    lines += ["%endblock LatticeVectors", "AtomicCoordinatesFormat Fractional", "%block AtomicCoordinatesAndAtomicSpecies"]
    for index, (label, _valence, frac, _spin) in enumerate(MN, 1):
        lines.append("  " + " ".join(f"{x:.12f}" for x in frac) + f" {index} # {label}")
    species = {"K": 7, "O": 8, "H": 9}
    for element, frac in OTHER:
        lines.append("  " + " ".join(f"{x:.12f}" for x in frac) + f" {species[element]} # {element}")
    lines += ["%endblock AtomicCoordinatesAndAtomicSpecies", "", "XC.Functional GGA", "XC.Authors PBE", "Spin polarized",
              "PAO.BasisSize DZP", "PAO.EnergyShift 0.005 Ry", "PAO.SplitNorm 0.15", "PAO.BasisType split", "MeshCutoff 200 Ry",
              "%block kgrid_Monkhorst_Pack", "  3 0 0 0.0", "  0 5 0 0.0", "  0 0 4 0.0", "%endblock kgrid_Monkhorst_Pack",
              "OccupationFunction FD", "ElectronicTemperature 300 K", "MD.NumCGsteps 0", "Write.DM true", "WriteMullikenPop 1", "%block DM.InitSpin"]
    for atom_index, (_label, _valence, _frac, spin) in enumerate(MN, 1): lines.append(f"  {atom_index} {spin:+.1f}")
    for atom_index in range(7, 33): lines.append(f"  {atom_index} +0.0")
    lines += ["%endblock DM.InitSpin", "%block DFTU.Proj"]
    for label, *_ in MN:
        shift = alpha if label == target else 0.0
        lines += [f"  {label} 1", "  3 2", f"  {shift:+.4f} 0.0000", "  3.0000 0.0500"]
    lines += ["%endblock DFTU.Proj", "DFTU.ProjectorGenerationMethod 2", "DFTU.PotentialShift true"]
    if mode == "REFERENCE":
        lines += ["DFTU.FirstIteration false", "SCF.MustConverge T", "SCF.Mix Hamiltonian", "SCF.Mixer.Method Pulay", "SCF.Mixer.Weight 0.05", "SCF.Mixer.History 8", "SCF.DM.Converge T", "SCF.H.Converge T", "SCF.DM.Tolerance 1.0e-5", "SCF.H.Tolerance 1.0e-4 eV", "MaxSCFIterations 300", "DM.UseSaveDM false"]
    elif mode == "BARE":
        lines += ["DFTU.FirstIteration true", "MaxSCFIterations 1", "SCF.MustConverge F", "SCF.Mix Hamiltonian", "SCF.Mixer.Method Pulay", "SCF.Mixer.Weight 0.05", "SCF.Mixer.History 8", "DM.UseSaveDM true"]
    else:
        lines += ["DFTU.FirstIteration true", "SCF.MustConverge T", "SCF.Mix Hamiltonian", "SCF.Mixer.Method Pulay", "SCF.Mixer.Weight 0.05", "SCF.Mixer.History 8", "SCF.DM.Converge T", "SCF.H.Converge T", "SCF.DM.Tolerance 1.0e-5", "SCF.H.Tolerance 1.0e-4 eV", "MaxSCFIterations 300", "DM.UseSaveDM true"]
    return "\n".join(lines) + "\n"


VALIDATE = r'''import re, sys
from pathlib import Path
from siesta542_bare_contract import select_bare_occupations
path=Path(sys.argv[1]); mode=sys.argv[2]; text=path.read_text(errors="ignore"); err=(path.parent/"siesta.err").read_text(errors="ignore") if (path.parent/"siesta.err").exists() else ""; status=text+"\n"+err
if not ((path.parent/"0_NORMAL_EXIT").exists() or re.search(r"siesta:\s+normal completion",status,re.I)): raise RuntimeError("normal completion missing")
if mode != "BARE" and re.search(r"SCF_NOT_CONV|SCF: not converged|ABNORMAL_TERMINATION|MPI_Abort",status,re.I): raise RuntimeError("required SCF convergence missing")
if mode == "BARE": select_bare_occupations(text, 6)
events=[]; cur=None
for line in text.splitlines():
 if "hubbard_term: recalculating local occupations" in line:
  if cur is not None: events.append(cur)
  cur=[]
 elif cur is not None and "Occupations:" in line:
  nums=re.findall(r"[-+]?(?:\d*\.\d+|\d+)(?:[Ee][-+]?\d+)?",line.split("Occupations:",1)[1])
  if len(nums)>=3: cur.append(float(nums[-1]))
if cur is not None: events.append(cur)
events=[x for x in events if len(x)==6]
if mode!="BARE":
 if not events: raise RuntimeError("final semantic event missing")
print("SEMANTIC_OCCUPATION_VALID")
'''

ANALYZE = r'''import json,re,sys
from pathlib import Path
import numpy as np
from siesta542_bare_contract import select_bare_occupations
root=Path(__file__).resolve().parents[1]; records=json.loads((root/'runs/manifest.json').read_text()); n=6
def select(p,mode):
 text=p.read_text(errors='ignore'); events=[]; cur=None
 if mode=='BARE': return np.asarray(select_bare_occupations(text,n))
 for line in text.splitlines():
  if 'hubbard_term: recalculating local occupations' in line:
   if cur is not None: events.append(cur)
   cur=[]
  elif cur is not None and 'Occupations:' in line:
   q=re.findall(r'[-+]?(?:\d*\.\d+|\d+)(?:[Ee][-+]?\d+)?',line.split('Occupations:',1)[1]);
   if len(q)>=3: cur.append(float(q[-1]))
 if cur is not None: events.append(cur)
 events=[e for e in events if len(e)==n]
 return np.array(events[-1])
raw={r['id']:select(root/'runs'/r['id']/'siesta.out',r['mode']) for r in records}
(root/'results/raw_occupations').mkdir(parents=True,exist_ok=True); (root/'results/raw_occupations/occupations.json').write_text(json.dumps({k:v.tolist() for k,v in raw.items()},indent=2)+'\n')
chi0=np.empty((n,n)); chi=np.empty((n,n)); labels=[f'MnLR{i:02d}' for i in range(n)]
for j,label in enumerate(labels):
 bminus=raw[f'{j+10:02d}_{label}_BARE_MINUS']; bplus=raw[f'{j+10:02d}_{label}_BARE_PLUS']; sminus=raw[f'{j+10:02d}_{label}_SCREENED_MINUS']; splus=raw[f'{j+10:02d}_{label}_SCREENED_PLUS']
 chi0[:,j]=(bplus-bminus)/.1; chi[:,j]=(splus-sminus)/.1
chi0_raw,chi_raw=chi0.copy(),chi.copy(); chi0=(chi0+chi0.T)/2; chi=(chi+chi.T)/2
rank0,rank=np.linalg.matrix_rank(chi0),np.linalg.matrix_rank(chi)
if rank0!=n or rank!=n: raise RuntimeError(f'SCIENTIFIC_ANALYSIS_FAILED: rank chi0={rank0}, chi={rank}')
inv0,inv=np.linalg.inv(chi0),np.linalg.inv(chi); K=inv0-inv; U=np.diag(K); idx3=[0,1]; idx4=[2,3,4,5]
out=root/'results/matrices'; out.mkdir(parents=True,exist_ok=True)
for name,a in {'chi0_raw':chi0_raw,'chi_raw':chi_raw,'chi0':chi0,'chi':chi,'inv_chi0':inv0,'inv_chi':inv,'K_hubbard':K,'U_by_site':U}.items(): np.savetxt(out/(name+'.csv'),a,delimiter=',',fmt='%.16g')
result={'campaign_id':'K_BIRNESSITE_PBE_LRU_ORDERED_CELL_V1','material':'K2Mn6O12_4H2O ordered birnessite seed','status':'PASS','matrix_dimension':n,'rank_chi0':int(rank0),'rank_chi':int(rank),'condition_chi0':float(np.linalg.cond(chi0)),'condition_chi':float(np.linalg.cond(chi)),'antisymmetry_chi0':float(np.linalg.norm(chi0_raw-chi0_raw.T)/max(np.linalg.norm(chi0_raw),1e-16)),'antisymmetry_chi':float(np.linalg.norm(chi_raw-chi_raw.T)/max(np.linalg.norm(chi_raw),1e-16)),'U_Mn_mean_eV':float(U.mean()),'U_MnIII_mean_eV':float(U[idx3].mean()),'U_MnIV_mean_eV':float(U[idx4].mean()),'U_by_site_eV':{label:float(U[i]) for i,label in enumerate(labels)},'inversion_residuals':{'chi0':float(np.linalg.norm(inv0@chi0-np.eye(n))),'chi':float(np.linalg.norm(inv@chi-np.eye(n))),'notes':['INITIAL_ORDERED_CELL: no crystallographic symmetry reduction applied; physical convergence remains to be assessed.']}}
(root/'results/final').mkdir(parents=True,exist_ok=True); (root/'results/final/campaign_result.json').write_text(json.dumps(result,indent=2)+'\n'); print(root/'results/final/campaign_result.json')
'''


def dag(run_names: list[str]) -> str:
    joined = " ".join(run_names)
    return f'''#!/bin/bash
# Validated Yoltla DAG: retain five nodes; execute one complete FDF on all 100 ranks.
# Direct 6x6 response: no symmetry reduction is used.
#SBATCH --job-name=kbir_lru_ordered_v1
#SBATCH --partition=tt2d-100p
#SBATCH --nodes=5
#SBATCH --ntasks=100
#SBATCH --ntasks-per-node=20
#SBATCH --cpus-per-task=1
#SBATCH --time=2-00:00:00
#SBATCH --output=slurm/dag_%j.out
#SBATCH --error=slurm/dag_%j.err
set -euo pipefail
ROOT="$(cd "${{SLURM_SUBMIT_DIR:-$PWD}}" && pwd)"; RANKS=100; PPN=20; NODES=5
RUNS=({joined})
fail(){{ echo "DAG_ERROR: $*" >&2; exit 1; }}
[[ "${{SLURM_JOB_NUM_NODES:-}}" == "$NODES" && "${{SLURM_NTASKS:-}}" == "$RANKS" ]] || fail "incorrect Slurm allocation"
mapfile -t H < <(scontrol show hostnames "$SLURM_JOB_NODELIST"); [[ "${{#H[@]}}" == "$NODES" ]] || fail "host resolution"
HOSTS="$(IFS=,; echo "${{H[*]}}")"; module purge; module load siesta/5.4.2; module load python/3.12
SIESTA="$(command -v siesta)"; MPI="$(command -v mpiexec.hydra)"; [[ -x "$SIESTA" && -x "$MPI" ]] || fail "runtime unavailable"
mpi(){{ "$MPI" -bootstrap ssh -hosts "$HOSTS" -ppn "$PPN" -n "$RANKS" "$@"; }}
P="$(mktemp "$ROOT/slurm/placement_${{SLURM_JOB_ID}}.XXXX")"; trap 'rm -f "$P"' EXIT; mpi /bin/hostname -s > "$P"
for h in "${{H[@]}}"; do [[ "$(grep -Fxc "$h" "$P" || true)" == "$PPN" ]] || fail "MPI placement $h"; done; echo "DAG_MPI_PLACEMENT_OK: hosts=$HOSTS ranks=$RANKS ppn=$PPN"
normal(){{ [[ -f "$1/0_NORMAL_EXIT" ]] || grep -qi 'siesta: normal completion' "$1/siesta.out"; }}
mode(){{ [[ "$1" == 00_REFERENCE ]] && echo REFERENCE || ([[ "$1" == *BARE* ]] && echo BARE || echo SCREENED); }}
valid(){{ local r="$1" d="$ROOT/runs/$1" m; m="$(mode "$r")"; [[ -s "$d/siesta.out" ]] && normal "$d" || return 1; if [[ "$m" != BARE ]]; then ! grep -Eqi 'SCF_NOT_CONV|SCF: not converged|ABNORMAL_TERMINATION|MPI_Abort' "$d/siesta.out" "$d/siesta.err" 2>/dev/null || return 1; fi; python "$ROOT/scripts/validate_run.py" "$d/siesta.out" "$m" >/dev/null; [[ "$r" != 00_REFERENCE || -s "$d/00_REFERENCE.DM" ]]; }}
stage(){{ local r="$1" d="$ROOT/runs/$1"; for n in 00 01 02 03 04 05; do cp -fp "$ROOT/pseudopotentials/Mn.psml" "$d/MnLR$n.psml"; done; for e in K O H; do cp -fp "$ROOT/pseudopotentials/$e.psml" "$d/$e.psml"; done; [[ "$r" == 00_REFERENCE ]] || cp -fp "$ROOT/runs/00_REFERENCE/00_REFERENCE.DM" "$d/$r.DM"; }}
for r in "${{RUNS[@]}}"; do d="$ROOT/runs/$r"; if [[ -e "$d/siesta.out" || -e "$d/siesta.err" ]]; then valid "$r" || fail "existing run failed scientific validation: $r"; echo "DAG_SKIP_VALID: $r"; continue; fi; [[ "$r" == 00_REFERENCE || -s "$ROOT/runs/00_REFERENCE/00_REFERENCE.DM" ]] || fail "reference DM missing"; echo "DAG_RUN: $r hosts=$HOSTS ranks=$RANKS ppn=$PPN"; stage "$r"; (cd "$d"; mpi "$SIESTA" < siesta.fdf > siesta.out 2> siesta.err); valid "$r" || fail "scientific validation failed: $r"; echo "DAG_DONE: $r"; done
python "$ROOT/scripts/analyze.py"; echo "DAG_COMPLETE: $ROOT/results/final/campaign_result.json"
'''


def build() -> None:
    if OUT.exists(): shutil.rmtree(OUT)
    for directory in (OUT / "geometry/source", OUT / "pseudopotentials", OUT / "runs", OUT / "scripts", OUT / "slurm", OUT / "results/raw_occupations", OUT / "results/matrices", OUT / "results/final"):
        directory.mkdir(parents=True, exist_ok=True)
    for name in ("Mn.psml", "K.psml", "O.psml", "H.psml"):
        source = PSEUDO_SOURCE / name
        if not source.is_file(): raise FileNotFoundError(source)
        shutil.copy2(source, OUT / "pseudopotentials" / name)
    shutil.copy2(GEOMETRY_SOURCE, OUT / "geometry/source/K2Mn6O12_4H2O_geometry_fractional.fdf")
    shutil.copy2(GEOMETRY_SOURCE, OUT / "geometry/K2Mn6O12_4H2O_geometry_fractional.fdf")
    shutil.copy2(CIF_SOURCE, OUT / "geometry/source/K2Mn6O12_4H2O_seed_v01.cif")
    config = {"campaign_id": NAME, "classification": "INITIAL_ORDERED_CELL", "material": "K2Mn6O12_4H2O ordered birnessite seed", "formula": "K2Mn6O16H8", "geometry_validation": {"status": "PASS_EXACT_WITHIN_NUMERICAL_TOLERANCE", "atom_count": 32, "tolerance_A": 1e-10}, "correlated_subspace": {"element": "Mn", "shell": "3d", "method": 2, "rc_bohr": 3.0, "omega_bohr": 0.05}, "alpha_ev": 0.05, "kgrid": [3, 5, 4], "lattice_vectors_A": LATTICE, "magnetic_initialization_muB": {label: spin for label, _, _, spin in MN}, "site_classes": {label: valence for label, valence, _, _ in MN}, "no_symmetry_reduction": True, "pseudopotentials": {name: "ONCVPSP scalar-relativistic PBE, pseudojo nc-sr-05 stringent" for name in ("Mn", "K", "O", "H")}}
    write(OUT / "campaign.json", json.dumps(config, indent=2) + "\n")
    site_map = [{"index": i, "label": label, "declared_valence": valence, "fractional": frac, "initial_spin_muB": spin} for i, (label, valence, frac, spin) in enumerate(MN)]
    write(OUT / "geometry/site_map.json", json.dumps(site_map, indent=2) + "\n")
    records = runs(); write(OUT / "runs/manifest.json", json.dumps(records, indent=2) + "\n")
    for record in records:
        write(OUT / "runs" / record["id"] / "run.json", json.dumps(record, indent=2) + "\n")
        write(OUT / "runs" / record["id"] / "siesta.fdf", fdf(record))
    write(OUT / "scripts/validate_run.py", VALIDATE)
    write(OUT / "scripts/analyze.py", ANALYZE)
    shutil.copy2(ROOT / "tools" / "siesta542_bare_contract.py", OUT / "scripts" / "siesta542_bare_contract.py")
    write(OUT / "slurm/submit_dag.slurm", dag([r["id"] for r in records]))
    write(OUT / "README.md", "# K-birnessite PBE LR-U initial ordered-cell campaign\n\nThis is a direct 6x6 finite-difference LR-U calculation on the validated 32-atom K2Mn6O12·4H2O seed. It executes 25 SIESTA calculations: one reference plus BARE/SCREENED ±0.05 eV perturbations for each of six inequivalent Mn sites. No crystallographic symmetry reduction is applied. Report Mn(III) and Mn(IV) values separately; this initial ordered-cell result is not a converged bulk-birnessite U.\n")
    write(OUT / "SCIENTIFIC_CONTRACT.md", "# Scientific contract\n\nThe geometry is preserved from the supplied validated seed. PBE ONCVPSP PSML H/K/O/Mn pseudopotentials are from one pseudojo nc-sr-05 stringent family. The Mn 3d Method-2 projector is explicit: rc=3.0 Bohr, omega=0.05 Bohr. The response is direct 6x6, with no P1 symmetry reduction. REFERENCE and SCREENED require normal completion, converged SCF, and complete six-site occupations; BARE nonconvergence is intentional.\n")
    verify = """import json,re\nfrom pathlib import Path\nr=Path(__file__).resolve().parent; c=json.loads((r/'campaign.json').read_text()); m=json.loads((r/'runs/manifest.json').read_text())\nassert c['classification']=='INITIAL_ORDERED_CELL' and c['no_symmetry_reduction'] and len(m)==25\nassert sum(x['mode']=='BARE' for x in m)==12 and sum(x['mode']=='SCREENED' for x in m)==12\nfor p in ('Mn.psml','K.psml','O.psml','H.psml'): assert (r/'pseudopotentials'/p).is_file()\nfor x in m:\n t=(r/'runs'/x['id']/'siesta.fdf').read_text(); assert 'NumberOfAtoms 32' in t and 'NumberOfSpecies 9' in t and 'DFTU.ProjectorGenerationMethod 2' in t and '  3.0000 0.0500' in t\n assert len(re.findall(r'^  MnLR\\d{{2}} 1$',t,re.M))==6\n if x['mode']=='REFERENCE': assert 'SCF.MustConverge T' in t\n elif x['mode']=='BARE': assert 'MaxSCFIterations 1' in t and 'SCF.Mix Hamiltonian' in t and 'SCF.MustConverge F' in t\n else: assert 'MaxSCFIterations 300' in t and 'SCF.MustConverge T' in t\ns=(r/'slurm/submit_dag.slurm').read_bytes(); assert b'\\r\\n' not in s and b'--nodes=5' in s and b'--ntasks=100' in s and b'--array' not in s\nprint('PACKAGE_VERIFIED: K_BIRNESSITE_PBE_LRU_ORDERED_CELL_V1')\n"""
    # `verify` is a plain template (not an f-string); preserve the regex quantifier
    # expected in the generated verifier rather than an escaped literal brace.
    verify = verify.replace("d{{2}}", "d{2}")
    write(OUT / "verify_package.py", verify)
    archive = ROOT / f"{NAME}.zip"
    if archive.exists(): archive.unlink()
    shutil.make_archive(str(archive.with_suffix("")), "zip", ROOT, NAME)
    print(archive)


if __name__ == "__main__": build()
