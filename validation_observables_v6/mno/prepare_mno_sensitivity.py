#!/usr/bin/env python3
"""Prepare MnO interval endpoint single points from the converged central DM."""
from __future__ import annotations
import hashlib,json,shutil
from decimal import Decimal,localcontext
from fractions import Fraction
from pathlib import Path
HERE=Path(__file__).resolve().parent
CENTRAL=HERE/'lru_central'
authority=json.loads((HERE/'authoritative_u_inputs.json').read_text(encoding='utf-8'))
site_bounds=authority['u_interval_by_site']
for variant,label,key in [('low','MNLO','lower_eV'),('high','MNHI','upper_eV')]:
    out=HERE/f'lru_{variant}'; out.mkdir(parents=True,exist_ok=True)
    fdf=(CENTRAL/'input.fdf').read_text(encoding='utf-8')
    fdf=fdf.replace('SystemName MnO AFM-II PBE+LR-U central V6',f'SystemName MnO AFM-II PBE+LR-U {variant.upper()} endpoint V6')
    fdf=fdf.replace('SystemLabel MNCL',f'SystemLabel {label}')
    for site in ('MnLR0','MnLR1'):
        start=fdf.index(f'  {site} 1')
        after_header=fdf.index('\n',start)+1
        line_start=fdf.index('\n',after_header)+1
        line_end=fdf.index('\n',line_start)
        fraction_key='lower_fraction' if key=='lower_eV' else 'upper_fraction'
        exact=Fraction(site_bounds[site][fraction_key])
        with localcontext() as ctx:
            ctx.prec=45
            decimal_value=Decimal(exact.numerator)/Decimal(exact.denominator)
        value_text=f'{decimal_value:.18f}'
        fdf=fdf[:line_start]+f'  {value_text} 0.000000000000000'+fdf[line_end:]
    (out/'input.fdf').write_text(fdf,encoding='utf-8')
    for name in ['MnLR0.psml','MnLR1.psml','O.psml','MnLR0.dftu_proj','MnLR1.dftu_proj','MnLR0.ion','MnLR1.ion','O.ion','MnLR0.ion.xml','MnLR1.ion.xml','O.ion.xml']:
        if (CENTRAL/name).exists():shutil.copy2(CENTRAL/name,out/name)
    shutil.copy2(CENTRAL/'MNCL.DM',out/f'{label}.DM')
    def sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
    fraction_key='lower_fraction' if key=='lower_eV' else 'upper_fraction'
    manifest={'variant':variant.upper(),'source_certificate_summary':'../authoritative_u_inputs.json','parent_dm':'../lru_central/MNCL.DM','parent_dm_sha256':sha(out/f'{label}.DM'),'input_fdf_sha256':sha(out/'input.fdf'),'u_site_eV':{s:site_bounds[s][key] for s in ('MnLR0','MnLR1')},'u_site_fraction':{s:site_bounds[s][fraction_key] for s in ('MnLR0','MnLR1')},'changes_from_central':['SystemName','SystemLabel','certified site-specific U endpoints']}
    (out/'input_provenance.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(f'{variant.upper()}: {json.dumps(manifest)}')
