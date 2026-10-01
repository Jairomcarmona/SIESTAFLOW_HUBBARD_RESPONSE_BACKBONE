import json,sys,math
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
import postprocess_coo_bands as c
try:
    import scipy
    import scipy.linalg
    SCIPY=True
except Exception:
    SCIPY=False

def classify(a,ef):
    rel=a-ef; crossings=[]
    for s in range(rel.shape[1]):
        for b in range(rel.shape[2]):
            x=rel[:,s,b]
            if x.min()<=1e-7 and x.max()>=-1e-7:
                crossings.append({'spin':s+1,'band':b+1,'min_rel_Ef_eV':float(x.min()),'max_rel_Ef_eV':float(x.max())})
    if crossings:return {'classification':'METAL','fermi_crossings':crossings,'vbm':None,'cbm':None,'gap_eV':0.0}
    below=rel[rel< -1e-7]; above=rel[rel>1e-7]
    iv=np.unravel_index(np.argmax(np.where(rel< -1e-7,rel,-np.inf)),rel.shape)
    ic=np.unravel_index(np.argmin(np.where(rel>1e-7,rel,np.inf)),rel.shape)
    def edge(ix):return {'energy_rel_Ef_eV':float(rel[ix]),'kpoint_index_1based':int(ix[0])+1,'spin_channel':int(ix[1])+1,'band_index':int(ix[2])+1}
    return {'classification':'INSULATOR','fermi_crossings':[],'vbm':edge(iv),'cbm':edge(ic),'gap_eV':float(above.min()-below.max())}

def hsx_generalized(h,kpts):
    n=len(h['row_index']); rows=h['row_index']; cols=h['col_index']; cells=h['cell_index']; r=h['rvec_bohr']; results=[]
    abs_res=[]; rel_res=[]; eval_diffs=[]
    for ik,k in enumerate(kpts):
        phase=np.exp(1j*(r@k))
        for s in range(h['nspin']):
            hm=np.zeros((h['norb'],h['norb']),complex); sm=np.zeros_like(hm)
            np.add.at(hm,(rows,cols),h['h_values_ry'][s]*phase[cells]); np.add.at(sm,(rows,cols),h['s_values']*phase[cells])
            hm=(hm+hm.conj().T)/2; sm=(sm+sm.conj().T)/2
            if SCIPY:
                ev,cv=scipy.linalg.eigh(hm,sm,driver='gvd')
            else:
                # Independent Hermitian diagonalization after the standard
                # Cholesky reduction Hc=ESc, S=LL^H, y=L^H c.
                chol=np.linalg.cholesky(sm)
                transformed=np.linalg.solve(chol,hm)
                transformed=np.linalg.solve(chol.conj(),transformed.T).T
                transformed=(transformed+transformed.conj().T)/2
                ev,y=np.linalg.eigh(transformed)
                cv=np.linalg.solve(chol.conj().T,y)
            eV=ev*c.RYEV
            # current analyzer uses the same spectral problem via Cholesky reduction
            old=c.diagonalize(h,np.asarray([k]))[0,s]
            eval_diffs.extend(np.abs(eV-old).tolist())
            nh=np.linalg.norm(hm,2); ns=np.linalg.norm(sm,2)
            for j in range(len(ev)):
                v=cv[:,j]; rr=hm@v-ev[j]*(sm@v); rn=float(np.linalg.norm(rr,2)); den=(nh+abs(float(ev[j]))*ns)*float(np.linalg.norm(v,2))
                abs_res.append(rn); rel_res.append(rn/den if den else rn)
    return {'solver':'scipy.linalg.eigh(gvd)' if SCIPY else 'numpy.linalg.eigh after Cholesky generalized-Hermitian reduction','residual_definition':'||Hc-ESc||2 / ((||H||2+|E| ||S||2)||c||2), with HSX H in Ry and S dimensionless','maximum_normalized_residual':float(max(rel_res)),'rms_normalized_residual':float(np.sqrt(np.mean(np.square(rel_res)))),'maximum_absolute_residual_Ry':float(max(abs_res)),'rms_absolute_residual_Ry':float(np.sqrt(np.mean(np.square(abs_res)))),'scipy_version':scipy.__version__ if SCIPY else None,'max_abs_eigenvalue_difference_vs_current_diagonalizer_eV':float(max(eval_diffs)),'rms_eigenvalue_difference_vs_current_diagonalizer_eV':float(np.sqrt(np.mean(np.square(eval_diffs))))}

report={'number_of_bands':64,'number_of_kpoints':23,'number_of_spin_channels':2,'methods':{},'scipy_available':SCIPY}
for method,(d,label) in c.METHODS.items():
    h=c.read_hsx(d/f'{label}.HSX'); k,w=c.read_kp(d/f'{label}.KP'); hrel_abs=c.diagonalize(h,k); ef_e,eig,layout=c.eig_parse(d/f'{label}.EIG',hrel_abs)
    delta=eig-hrel_abs; ef_h=h['fermi_ev']; efout=c.out_metrics(d/'siesta.out')['fermi_energy_eV']
    ix=np.unravel_index(np.argmax(np.abs(delta)),delta.shape); ik,spin,band=map(int,ix)
    kcart=k[ik]; rec=(2*math.pi*np.linalg.inv(c.CELL).T)*c.BOHRANG; kfrac=kcart@np.linalg.inv(rec)
    neighbors=[]
    for b in range(max(0,band-2),min(eig.shape[2],band+3)):
        neighbors.append({'band':b+1,'E_EIG_eV':float(eig[ik,spin,b]),'E_HSX_eV':float(hrel_abs[ik,spin,b]),'delta_E_EIG_minus_HSX_eV':float(delta[ik,spin,b]),'E_EIG_minus_EF_eV':float(eig[ik,spin,b]-ef_e),'E_HSX_minus_EF_eV':float(hrel_abs[ik,spin,b]-ef_h),'spacing_to_next_EIG_eV':float(eig[ik,spin,b+1]-eig[ik,spin,b]) if b+1<eig.shape[2] else None,'spacing_to_next_HSX_eV':float(hrel_abs[ik,spin,b+1]-hrel_abs[ik,spin,b]) if b+1<eig.shape[2] else None})
    windows={}
    for width in (1.,5.):
        mask=(np.abs(eig-ef_e)<=width)|(np.abs(hrel_abs-ef_h)<=width)
        vals=delta[mask]
        windows[f'within_{width:g}_eV_of_EF']={'state_count':int(vals.size),'MAX_ABS_DIFF_eV':float(np.max(np.abs(vals))) if vals.size else None,'RMS_DIFF_eV':float(np.sqrt(np.mean(vals**2))) if vals.size else None}
    ce=classify(eig,ef_e); ch=classify(hrel_abs,ef_h)
    m={'fermi_energy_EIG_eV':ef_e,'fermi_energy_HSX_eV':ef_h,'fermi_energy_OUT_eV':efout,'EIG_HSX_EF_difference_eV':abs(ef_e-ef_h),'EIG_OUT_EF_difference_eV':abs(ef_e-efout),'energy_relation_mean_delta_eV':float(delta.mean()),'energy_relation_best_constant_offset_eV':float(delta.mean()),'MAX_ABS_RAW_DIFFERENCE_eV':float(np.max(np.abs(delta))),'RMS_RAW_DIFFERENCE_eV':float(np.sqrt(np.mean(delta**2))),'MAX_ABS_RESIDUAL_AFTER_OFFSET_eV':float(np.max(np.abs(delta-delta.mean()))),'RMS_RESIDUAL_AFTER_OFFSET_eV':float(np.sqrt(np.mean((delta-delta.mean())**2))),'maximum_location':{'kpoint_index_1based':ik+1,'k_fractional_original_cell':kfrac.tolist(),'k_cartesian_inverse_bohr':kcart.tolist(),'spin_channel':spin+1,'band_index':band+1,'E_EIG_eV':float(eig[ix]),'E_HSX_eV':float(hrel_abs[ix]),'delta_E_EIG_minus_HSX_eV':float(delta[ix]),'E_EIG_minus_EF_eV':float(eig[ix]-ef_e),'E_HSX_minus_EF_eV':float(hrel_abs[ix]-ef_h)},'neighboring_bands_n_minus_2_to_n_plus_2':neighbors,'energy_windows':windows,'classification_EIG':ce,'classification_HSX':ch,'delta_vbm_eig_minus_hsx_eV':float(ce['vbm']['energy_rel_Ef_eV']-ch['vbm']['energy_rel_Ef_eV']) if ce['vbm'] and ch['vbm'] else None,'delta_cbm_eig_minus_hsx_eV':float(ce['cbm']['energy_rel_Ef_eV']-ch['cbm']['energy_rel_Ef_eV']) if ce['cbm'] and ch['cbm'] else None,'delta_gap_eig_minus_hsx_eV':float(ce['gap_eV']-ch['gap_eV']) if ce['classification']=='INSULATOR' and ch['classification']=='INSULATOR' else None,'HSX_generalized_eigensystem_quality':hsx_generalized(h,k)}
    report['methods'][method]=m
out=Path(__file__).resolve().parent/'hsx_eig_spectral_diagnostic.json'
out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
print(json.dumps(report,indent=2,ensure_ascii=False))

