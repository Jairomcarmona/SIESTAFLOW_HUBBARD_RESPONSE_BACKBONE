import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import postprocess_coo_bands as c
for method,(d,label) in c.METHODS.items():
    h=c.read_hsx(d/f'{label}.HSX')
    kp=d/f'{label}.KP'; k,w=c.read_kp(kp); hsx=c.diagonalize(h,k)
    ef,eig,layout=c.eig_parse(d/f'{label}.EIG',hsx)
    delta=eig-hsx
    flat=abs(delta).ravel(); order=flat.argsort()[-8:][::-1]
    out=c.out_metrics(d/'siesta.out')
    print('\nMETHOD',method)
    print('SCF',json.dumps(out,indent=2))
    print('MESH',json.dumps(c.mesh_summary(h,eig,kp,ef),indent=2))
    print('RAW_DIFF',json.dumps({'max_abs':float(abs(delta).max()),'mean':float(delta.mean()),'rms':float((delta**2).mean()**.5),'ef_eig':ef,'ef_hsx':h['fermi_ev'],'layout':layout,'largest_abs_entries':[{'kpoint':int(i//(eig.shape[1]*eig.shape[2]))+1,'spin':int((i//eig.shape[2])%eig.shape[1])+1,'band':int(i%eig.shape[2])+1,'difference_eV':float(delta.reshape(-1)[i])} for i in order]},indent=2))
