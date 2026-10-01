#!/usr/bin/env python3
"""Summarize existing MnO SCF EIG/HSX/OUT using Ef and actual k sampling."""
from __future__ import annotations
import hashlib,json,sys
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parent
BANDS=HERE.parents[0]/'coo'/'bands'
sys.path.insert(0,str(BANDS))
import postprocess_coo_bands as p
read_hsx=p.read_hsx; diagonalize=p.diagonalize

def sha(path:Path)->str:return hashlib.sha256(path.read_bytes()).hexdigest()

def analyze(name:str,label:str)->dict:
    d=HERE/name; h=read_hsx(d/f'{label}.HSX'); kp,w=p.read_kp(d/f'{label}.KP')
    hsx=diagonalize(h,kp); ef,eig,layout=p.eig_parse(d/f'{label}.EIG',hsx)
    out=p.out_metrics(d/'siesta.out'); mesh=p.mesh_summary(h,eig,d/f'{label}.KP',ef)
    return {'directory':name,'system_label':label,'convergence':out,'scf_mesh':mesh,
            'EIG_HSX_max_abs_diff_eV':float(np.max(np.abs(eig-hsx))),
            'EIG_HSX_rms_diff_eV':float(np.sqrt(np.mean((eig-hsx)**2))),
            'EIG_spin_layout':layout,'fermi_energy_EIG_eV':ef,'fermi_energy_HSX_eV':h['fermi_ev'],
            'files_sha256':{f'{label}.DM':sha(d/f'{label}.DM'),f'{label}.HSX':sha(d/f'{label}.HSX'),
                            f'{label}.EIG':sha(d/f'{label}.EIG'),f'{label}.KP':sha(d/f'{label}.KP'),
                            'input.fdf':sha(d/'input.fdf') if (d/'input.fdf').exists() else sha(d/'siesta.fdf')}}

def main()->None:
    report={'material':'MnO','xc':'PBE','runs':{'PBE':analyze('pbe','MNO_PBE_REFERENCE'),
                                                'PBE+LR-U central':analyze('lru_central','MNCL'),
                                                'PBE+LR-U low':analyze('lru_low','MNLO'),
                                                'PBE+LR-U high':analyze('lru_high','MNHI')}}
    (HERE/'scf_observables.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
