#!/usr/bin/env python3
"""Build the minimum targeted validation suite for the ordered K-birnessite LR-U point.

The suite deliberately varies one physical/numerical assumption per campaign.
Every DAG retains five Yoltla nodes and runs one SIESTA calculation at a time
with all 100 MPI ranks.  No output from an existing calculation is packaged.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "K_BIRNESSITE_PBE_LRU_ORDERED_CELL_V1"
SUITE = ROOT / "K_BIRNESSITE_PBE_LRU_MINIMUM_VALIDATION_V1"
ARCHIVE = ROOT / f"{SUITE.name}.zip"


def load_seed_builder():
    spec = importlib.util.spec_from_file_location("kbir_seed", ROOT / "tools" / "build_k_birnessite_initial_lru.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load K-birnessite seed builder")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def norm_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8"))


def tag(alpha: float) -> str:
    return f"{'p' if alpha >= 0 else 'm'}{abs(alpha):.3f}".replace(".", "p")


def records(levels: list[float], classes: dict[str, str]) -> list[dict]:
    result = [{"id": "00_REFERENCE", "mode": "REFERENCE", "target": None, "alpha_ev": 0.0, "parent_dm": None}]
    for idx in range(6):
        label = f"MnLR{idx:02d}"
        for alpha in levels:
            for mode in ("BARE", "SCREENED"):
                result.append({
                    "id": f"{idx + 10:02d}_{label}_{mode}_a{tag(alpha)}",
                    "mode": mode,
                    "target": label,
                    "alpha_ev": alpha,
                    "parent_dm": "00_REFERENCE/00_REFERENCE.DM",
                    "declared_valence": classes[label],
                })
    return result


VALIDATE = (SEED / "scripts" / "validate_run.py").read_text(encoding="utf-8")

ANALYZE = r'''import json, re
from pathlib import Path
import numpy as np
from siesta542_bare_contract import select_bare_occupations

root=Path(__file__).resolve().parents[1]
cfg=json.loads((root/'campaign.json').read_text())
records=json.loads((root/'runs/manifest.json').read_text())
n=6
labels=[f'MnLR{i:02d}' for i in range(n)]

def select(path, mode):
    text=path.read_text(errors='ignore')
    if mode=='BARE': return np.asarray(select_bare_occupations(text,n))
    events=[]; cur=None
    for line in text.splitlines():
        if 'hubbard_term: recalculating local occupations' in line:
            if cur is not None: events.append(cur)
            cur=[]
        elif cur is not None and 'Occupations:' in line:
            nums=re.findall(r'[-+]?(?:\d*\.\d+|\d+)(?:[Ee][-+]?\d+)?', line.split('Occupations:',1)[1])
            if len(nums)>=3: cur.append(float(nums[-1]))
    if cur is not None: events.append(cur)
    events=[e for e in events if len(e)==n]
    if not events: raise RuntimeError(f'final semantic event missing: {path}')
    return np.asarray(events[-1])

raw={r['id']:select(root/'runs'/r['id']/'siesta.out',r['mode']) for r in records}
(root/'results/raw_occupations').mkdir(parents=True,exist_ok=True)
(root/'results/raw_occupations/occupations.json').write_text(json.dumps({k:v.tolist() for k,v in raw.items()},indent=2)+'\n')

def row(record): return raw[record['id']]
def solve(a):
    chi0=np.empty((n,n)); chi=np.empty((n,n))
    for j,label in enumerate(labels):
        def get(mode, sign):
            q=[r for r in records if r['target']==label and r['mode']==mode and abs(r['alpha_ev']-sign*a)<1e-12]
            if len(q)!=1: raise RuntimeError(f'missing {label} {mode} {sign*a}')
            return row(q[0])
        chi0[:,j]=(get('BARE',+1)-get('BARE',-1))/(2*a)
        chi[:,j]=(get('SCREENED',+1)-get('SCREENED',-1))/(2*a)
    raw0,rawx=chi0.copy(),chi.copy(); chi0=(chi0+chi0.T)/2; chi=(chi+chi.T)/2
    rank0=int(np.linalg.matrix_rank(chi0)); rank=int(np.linalg.matrix_rank(chi))
    if rank0 != n or rank != n: raise RuntimeError(f'SCIENTIFIC_ANALYSIS_FAILED alpha={a}: rank chi0={rank0}, chi={rank}')
    inv0=np.linalg.inv(chi0); inv=np.linalg.inv(chi); k=inv0-inv; u=np.diag(k)
    return raw0,rawx,chi0,chi,inv0,inv,k,u,rank0,rank

levels=sorted({abs(float(r['alpha_ev'])) for r in records if r['mode']!='REFERENCE'})
summary={}
for a in levels:
    raw0,rawx,chi0,chi,inv0,inv,k,u,rank0,rank=solve(a)
    dest=root/'results'/'by_alpha'/f'{a:.3f}'; dest.mkdir(parents=True,exist_ok=True)
    for name,matrix in {'chi0_raw':raw0,'chi_raw':rawx,'chi0':chi0,'chi':chi,'inv_chi0':inv0,'inv_chi':inv,'K_hubbard':k,'U_by_site':u}.items():
        np.savetxt(dest/(name+'.csv'),matrix,delimiter=',',fmt='%.16g')
    summary[f'{a:.3f}']={
        'U_Mn_mean_eV':float(u.mean()), 'U_by_site_eV':{labels[i]:float(u[i]) for i in range(n)},
        'rank_chi0':rank0,'rank_chi':rank,'condition_chi0':float(np.linalg.cond(chi0)), 'condition_chi':float(np.linalg.cond(chi)),
        'antisymmetry_chi0':float(np.linalg.norm(raw0-raw0.T)/max(np.linalg.norm(raw0),1e-16)),
        'antisymmetry_chi':float(np.linalg.norm(rawx-rawx.T)/max(np.linalg.norm(rawx),1e-16)),
        'inversion_residuals':{'chi0':float(np.linalg.norm(inv0@chi0-np.eye(n))), 'chi':float(np.linalg.norm(inv@chi-np.eye(n)))},
    }

means=np.array([summary[f'{a:.3f}']['U_Mn_mean_eV'] for a in levels])
result={'campaign_id':cfg['campaign_id'],'status':'PASS','matrix_dimension':n,'alpha_levels_ev':levels,'by_alpha':summary,
        'U_mean_span_eV':float(means.max()-means.min()),'U_mean_relative_span':float((means.max()-means.min())/abs(means.mean())) if means.mean() else None,
        'acceptance':cfg['acceptance_criteria'],'notes':['All values are direct central finite differences. Acceptance is assessed only after comparison with the baseline campaign.']}
(root/'results/final').mkdir(parents=True,exist_ok=True)
name='alpha_linearity_result.json' if len(levels)>1 else 'campaign_result.json'
(root/'results/final'/name).write_text(json.dumps(result,indent=2)+'\n')
print(root/'results/final'/name)
'''


def make_dag(campaign_name: str, run_ids: list[str], final_name: str) -> str:
    seed = (SEED / "slurm" / "submit_dag.slurm").read_text(encoding="utf-8")
    begin = seed.index("RUNS=(")
    end = seed.index(")\nfail()", begin)
    run_line = "RUNS=(" + " ".join(run_ids) + ")"
    seed = seed[:begin] + run_line + seed[end + 1:]
    seed = seed.replace("#SBATCH --job-name=kbir_lru_ordered_v1", f"#SBATCH --job-name={campaign_name.lower()[:28]}")
    seed = seed.replace("python \"$ROOT/scripts/analyze.py\"; echo \"DAG_COMPLETE: $ROOT/results/final/campaign_result.json\"",
                        f"python \"$ROOT/scripts/analyze.py\"; echo \"DAG_COMPLETE: $ROOT/results/final/{final_name}\"")
    return seed


def fdf_for(seed_mod, rec: dict, *, kgrid: tuple[int,int,int], basis: str, rc: float, magnetic: list[tuple]) -> str:
    original = seed_mod.MN
    seed_mod.MN = magnetic
    try:
        text = seed_mod.fdf(rec)
    finally:
        seed_mod.MN = original
    text = text.replace("PAO.BasisSize DZP", f"PAO.BasisSize {basis}")
    text = text.replace("  3 0 0 0.0\n  0 5 0 0.0\n  0 0 4 0.0", f"  {kgrid[0]} 0 0 0.0\n  0 {kgrid[1]} 0 0.0\n  0 0 {kgrid[2]} 0.0")
    text = text.replace("  3.0000 0.0500", f"  {rc:.4f} 0.0500")
    return text


def build_campaign(seed_mod, name: str, purpose: str, levels: list[float], *, kgrid=(3,5,4), basis="DZP", rc=3.0, magnetic=None, classes=None, acceptance=None) -> None:
    dest=SUITE/name
    if dest.exists(): shutil.rmtree(dest)
    magnetic=magnetic or seed_mod.MN
    classes=classes or {x[0]:x[1] for x in magnetic}
    acceptance=acceptance or {}
    recs=records(levels,classes)
    for d in ("geometry","pseudopotentials","runs","scripts","slurm","results/raw_occupations","results/by_alpha","results/final"):
        (dest/d).mkdir(parents=True,exist_ok=True)
    shutil.copy2(SEED/"geometry"/"K2Mn6O12_4H2O_geometry_fractional.fdf",dest/"geometry"/"K2Mn6O12_4H2O_geometry_fractional.fdf")
    shutil.copy2(SEED/"geometry"/"site_map.json",dest/"geometry"/"site_map_source.json")
    for p in (SEED/"pseudopotentials").glob("*.psml"): shutil.copy2(p,dest/"pseudopotentials"/p.name)
    cfg={
        "campaign_id":name,"parent_baseline":"K_BIRNESSITE_PBE_LRU_ORDERED_CELL_V1","classification":"TARGETED_MINIMUM_VALIDATION",
        "purpose":purpose,"material":"K2Mn6O12_4H2O ordered birnessite seed","formula":"K2Mn6O16H8","atom_count":32,
        "alpha_levels_ev":levels,"kgrid":list(kgrid),"basis":basis,
        "correlated_subspace":{"element":"Mn","shell":"3d","method":2,"rc_bohr":rc,"omega_bohr":0.05},
        "magnetic_initialization_muB":{x[0]:x[3] for x in magnetic},"site_classes":classes,"no_symmetry_reduction":True,
        "acceptance_criteria":acceptance,"run_count":len(recs),"execution":"five nodes, 100 ranks, 20 ranks/node; one FDF at a time"
    }
    norm_write(dest/"campaign.json",json.dumps(cfg,indent=2)+"\n")
    norm_write(dest/"runs/manifest.json",json.dumps(recs,indent=2)+"\n")
    for rec in recs:
        norm_write(dest/"runs"/rec["id"]/'run.json',json.dumps(rec,indent=2)+"\n")
        norm_write(dest/"runs"/rec["id"]/'siesta.fdf',fdf_for(seed_mod,rec,kgrid=kgrid,basis=basis,rc=rc,magnetic=magnetic))
    norm_write(dest/"scripts/validate_run.py",VALIDATE)
    norm_write(dest/"scripts/analyze.py",ANALYZE)
    shutil.copy2(ROOT / "tools" / "siesta542_bare_contract.py", dest / "scripts" / "siesta542_bare_contract.py")
    result='alpha_linearity_result.json' if len({abs(x) for x in levels})>1 else 'campaign_result.json'
    norm_write(dest/"slurm/submit_dag.slurm",make_dag(name,[x['id'] for x in recs],result))
    readme=f"# {name}\n\n{purpose}\n\nThis is one independent 100-rank sequential DAG. It must not overwrite the baseline directory. Run `python verify_package.py` and then `sbatch slurm/submit_dag.slurm`. Outputs are written only below this campaign directory.\n"
    norm_write(dest/"README.md",readme)
    verifier=f'''import json,re\nfrom pathlib import Path\nr=Path(__file__).resolve().parent; c=json.loads((r/'campaign.json').read_text()); m=json.loads((r/'runs/manifest.json').read_text())\nassert len(m)==c['run_count'] and c['no_symmetry_reduction']\nassert sum(x['mode']=='REFERENCE' for x in m)==1\nfor x in m:\n t=(r/'runs'/x['id']/'siesta.fdf').read_text()\n assert 'NumberOfAtoms 32' in t and 'NumberOfSpecies 9' in t and 'DFTU.ProjectorGenerationMethod 2' in t\n assert len(re.findall(r'^  MnLR\\d{{2}} 1$',t,re.M))==6\n if x['mode']=='REFERENCE': assert 'SCF.MustConverge T' in t\n elif x['mode']=='BARE': assert 'MaxSCFIterations 1' in t and 'SCF.Mix Hamiltonian' in t and 'SCF.MustConverge F' in t\n else: assert 'MaxSCFIterations 300' in t and 'SCF.MustConverge T' in t\ns=(r/'slurm/submit_dag.slurm').read_bytes(); assert b'\\r\\n' not in s and b'--nodes=5' in s and b'--ntasks=100' in s and b'--array' not in s\nprint('PACKAGE_VERIFIED: {name}')\n'''
    norm_write(dest/"verify_package.py",verifier)


def build_suite_readme() -> None:
    text='''# K-birnessite minimum-validation suite

This suite tests the first ordered-cell LR-U result without changing several assumptions at once. Each folder is independent and has a validated five-node, 100-rank sequential DAG.

| Campaign | Runs | Isolated question | Predeclared acceptance |
|---|---:|---|---|
| `01_ALPHA_LINEARITY` | 73 | Is the finite-difference response stable across ±0.025, ±0.050, ±0.100 eV? | Full rank at every alpha; compare mean U span against the 0.05-eV baseline. |
| `02_KGRID_4x6x5` | 25 | Is 3x5x4 k sampling sufficient? | Full rank; mean U differs from baseline by <=0.30 eV. |
| `03_TZP` | 25 | Is the DZP basis adequate for this response? | Full rank; mean U differs from baseline by <=0.30 eV. |
| `04_PROJECTOR_RC2p5` | 25 | Is the Mn-3d subspace robust against a smaller projector radius? | Full rank; mean U differs from baseline by <=0.50 eV. |
| `05_ALT_MN_ORDER` | 25 | Is the result stable to an alternative ordered MnIII/MnIV AFM seed? | Full rank, converged reference/SCREENED; compare energy, moments and U with baseline. |

The alpha campaign is the primary scientific test. A pass does not mean that the U is universal: it establishes a reproducible response for this explicit ordered K2Mn6O12·4H2O model and its declared projectors.

## Yoltla deployment

Run each folder independently. The DAG uses 5 nodes × 20 ranks = 100 ranks and executes each FDF sequentially without releasing the allocation. Do not use an array or launch child runs independently.
'''
    norm_write(SUITE/'README.md',text)


def main() -> None:
    if not SEED.is_dir(): raise FileNotFoundError(SEED)
    if SUITE.exists(): shutil.rmtree(SUITE)
    seed_mod=load_seed_builder()
    base_classes={x[0]:x[1] for x in seed_mod.MN}
    common={"full_rank":"rank(chi0)=rank(chi)=6","screened":"normal SIESTA completion and converged SCF required"}
    build_campaign(seed_mod,"01_ALPHA_LINEARITY","Five-point finite-difference linearity test around zero; all other inputs equal to baseline.",[-.1,-.05,-.025,.025,.05,.1],classes=base_classes,acceptance={**common,"U_mean_relative_span_max":0.10,"linearity":"compare U(0.025), U(0.050), U(0.100)"})
    build_campaign(seed_mod,"02_KGRID_4x6x5","Single-variable Brillouin-zone sampling control relative to the 3x5x4 baseline.",[-.05,.05],kgrid=(4,6,5),classes=base_classes,acceptance={**common,"absolute_U_mean_difference_from_baseline_eV_max":0.30})
    build_campaign(seed_mod,"03_TZP","Single-variable basis control: TZP replaces DZP; geometry, k-grid, projectors and alpha remain baseline values.",[-.05,.05],basis="TZP",classes=base_classes,acceptance={**common,"absolute_U_mean_difference_from_baseline_eV_max":0.30})
    build_campaign(seed_mod,"04_PROJECTOR_RC2p5","Single-variable correlated-subspace control: Mn 3d radius 2.5 Bohr replaces 3.0 Bohr.",[-.05,.05],rc=2.5,classes=base_classes,acceptance={**common,"absolute_U_mean_difference_from_baseline_eV_max":0.50})
    alternative=[("MnLR00","MnIV",[0.0,.5,0.0],+3.0),("MnLR01","MnIII",[1/6,0,0],-4.0),("MnLR02","MnIII",[1/3,.5,0],+4.0),("MnLR03","MnIV",[.5,0,0],-3.0),("MnLR04","MnIV",[2/3,.5,0],+3.0),("MnLR05","MnIV",[5/6,0,0],-3.0)]
    alt_classes={x[0]:x[1] for x in alternative}
    build_campaign(seed_mod,"05_ALT_MN_ORDER","Alternative AFM ordered MnIII/MnIV seed: MnIII labels are MnLR01 and MnLR02 rather than MnLR00 and MnLR01.",[-.05,.05],magnetic=alternative,classes=alt_classes,acceptance={**common,"comparison":"reference energy, local moments and U must be evaluated against baseline; no automatic energy threshold"})
    build_suite_readme()
    if ARCHIVE.exists(): ARCHIVE.unlink()
    shutil.make_archive(str(ARCHIVE.with_suffix("")),"zip",ROOT,SUITE.name)
    print(ARCHIVE)


if __name__ == '__main__': main()
