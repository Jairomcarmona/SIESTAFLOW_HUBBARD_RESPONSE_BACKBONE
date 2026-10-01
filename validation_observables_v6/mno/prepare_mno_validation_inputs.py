#!/usr/bin/env python3
"""Stage MnO observable-validation inputs from V6 originals and certificate."""
from __future__ import annotations
import hashlib, json, re, shutil
from fractions import Fraction
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
PBE=HERE/'pbe'
CENTRAL=HERE/'lru_central'
CERT=ROOT/'benchmarks/lr_u/forensic_audit/MnO_u_certificate.superseding.v2.json'

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main() -> None:
    c=json.loads(CERT.read_text(encoding='utf-8'))['certificate']
    u=c['nominal_u_by_site_eV']; bounds=c['u_interval_by_site']
    intervals=[{'lower_fraction':x['lower'],'upper_fraction':x['upper'],
                'lower_eV':float(Fraction(x['lower'])),'upper_eV':float(Fraction(x['upper']))}
               for x in bounds]
    authority={
        'artifact_path':str(CERT.relative_to(ROOT)).replace('\\','/'),
        'artifact_sha256':sha(CERT),
        'campaign_uuid':c['campaign_uuid'],
        'certificate_status':c['certificate_status'],
        'consistency_status':c['consistency_status'],
        'physical_acceptance':c['physical_acceptance'],
        'qualification_state':'PROTOCOL_REVIEW_REQUIRED',
        'site_labels':['MnLR0','MnLR1'],
        'central_u_eV':dict(zip(['MnLR0','MnLR1'],u)),
        'u_interval_by_site':dict(zip(['MnLR0','MnLR1'],intervals)),
        'certificate_half_width_field_eV':[float(Fraction(x)) for x in c['half_width_by_site']],
        'interval_geometric_half_width_eV':[(v['upper_eV']-v['lower_eV'])/2 for v in intervals],
        'estimator_sensitivity_eV':[0.02117671547611,0.03073848245487],
        'window_sensitivity_eV':[0.013125851,0.020275758],
        'source_analysis_sha256':c['analysis_artifact_sha256'],
        'source_evidence_manifest_sha256':c['source_evidence_manifest_sha256'],
    }
    HERE.mkdir(parents=True,exist_ok=True)
    (HERE/'authoritative_u_inputs.json').write_text(json.dumps(authority,indent=2)+'\n',encoding='utf-8')

    CENTRAL.mkdir(parents=True,exist_ok=True)
    source=(PBE/'siesta.fdf').read_text(encoding='utf-8')
    fdf=source.replace('SystemName MnO AFM-II PBE Stage U-A','SystemName MnO AFM-II PBE+LR-U central V6')
    fdf=fdf.replace('SystemLabel MNO_PBE_REFERENCE','SystemLabel MNCL')
    fdf='DFTU.PopTol 1.0e-5\n'+fdf
    fdf='\n'.join(line for line in fdf.splitlines() if not line.strip().startswith(('DM.MixingWeight','DM.NumberPulay')))+'\n'
    fdf=fdf.replace('DFTU.PotentialShift true','DFTU.PotentialShift false')
    fdf=fdf.replace('DFTU.FirstIteration false','DFTU.FirstIteration true')
    fdf=fdf.replace('DM.UseSaveDM false','DM.UseSaveDM true')
    for label,value in zip(['MnLR0','MnLR1'],u):
        pat=rf'({label} 1\s*\n\s*3 2\s*\n)\s*0\.0000\s+0\.0000'
        fdf,n=re.subn(pat,rf'\g<1>  {value:.15f} 0.000000000000000',fdf,count=1)
        if n!=1: raise RuntimeError(f'could not stage certified U for {label}')
    (CENTRAL/'input.fdf').write_text(fdf,encoding='utf-8')
    for name in ['MnLR0.psml','MnLR1.psml','O.psml','MnLR0.dftu_proj','MnLR1.dftu_proj',
                 'MnLR0.ion','MnLR1.ion','O.ion','MnLR0.ion.xml','MnLR1.ion.xml','O.ion.xml']:
        src=PBE/name
        if src.exists(): shutil.copy2(src,CENTRAL/name)
    shutil.copy2(PBE/'MNO_PBE_REFERENCE.DM',CENTRAL/'MNCL.DM')
    (CENTRAL/'input_provenance.json').write_text(json.dumps({
        'method':'PBE+LR-U central','parent_pbe_directory':'../pbe',
        'parent_dm':'../pbe/MNO_PBE_REFERENCE.DM','parent_dm_sha256':sha(PBE/'MNO_PBE_REFERENCE.DM'),
        'pbe_reference_input_sha256':sha(PBE/'siesta.fdf'),
        'u_certificate':'../authoritative_u_inputs.json',
        'input_fdf_sha256':sha(CENTRAL/'input.fdf'),
        'species_files':{n:sha(CENTRAL/n) for n in ['MnLR0.psml','MnLR1.psml','O.psml']},
    },indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'authority':authority,'central_fdf':str(CENTRAL/'input.fdf'),'seed_dm_sha256':sha(CENTRAL/'MNCL.DM')},indent=2))

if __name__=='__main__': main()
