#!/usr/bin/env python3
"""MnO HSX/EIG spectral consistency and generalized-eigenproblem audit."""
from __future__ import annotations
import json, math, sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
BANDS=HERE.parents[0]/'coo'/'bands'; sys.path.insert(0,str(BANDS))
import postprocess_coo_bands as p

RYEV=13.605693122994; BOHRANG=0.529177210903
CELL=np.array([[0.,1.,1.],[.5,0.,.5],[.5,.5,0.]])*4.4455
METHODS={'PBE':('pbe','MNO_PBE_REFERENCE'),'PBE+LR-U':('lru_central','MNCL')}

def classify(a:np.ndarray,ef:float)->dict:
    rel=a-ef; crosses=[]
    for s in range(rel.shape[1]):
        for b in range(rel.shape[2]):
            x=rel[:,s,b]
            if x.min()<=1e-7 and x.max()>=-1e-7:
                crosses.append({'spin':s+1,'band':b+1,'min_rel_Ef_eV':float(x.min()),'max_rel_Ef_eV':float(x.max())})
    if crosses:return {'classification':'METAL','fermi_crossings':crosses,'vbm':None,'cbm':None,'gap_eV':0.0}
    below=rel[rel < -1e-7]; above=rel[rel > 1e-7]
    if not below.size or not above.size: raise ValueError('cannot identify both occupied and unoccupied states')
    iv=np.unravel_index(np.argmax(np.where(rel < -1e-7,rel,-np.inf)),rel.shape)
    ic=np.unravel_index(np.argmin(np.where(rel > 1e-7,rel,np.inf)),rel.shape)
    def edge(ix):return {'energy_rel_Ef_eV':float(rel[ix]),'kpoint_index_1based':int(ix[0])+1,'spin_channel':int(ix[1])+1,'band_index':int(ix[2])+1}
    return {'classification':'INSULATOR','fermi_crossings':[],'vbm':edge(iv),'cbm':edge(ic),'gap_eV':float(above.min()-below.max())}

def generalized_quality(h:dict,kpts:np.ndarray)->dict:
    rows,cols,cells=h['row_index'],h['col_index'],h['cell_index']; r=h['rvec_bohr']
    abs_res=[]; rel_res=[]; eigdiff=[]
    for k in kpts:
        phase=np.exp(1j*(r@k))
        for s in range(h['nspin']):
            hm=np.zeros((h['norb'],h['norb']),complex); sm=np.zeros_like(hm)
            np.add.at(hm,(rows,cols),h['h_values_ry'][s]*phase[cells]); np.add.at(sm,(rows,cols),h['s_values']*phase[cells])
            hm=(hm+hm.conj().T)/2; sm=(sm+sm.conj().T)/2
            chol=np.linalg.cholesky(sm)
            a=np.linalg.solve(chol,hm); a=np.linalg.solve(chol.conj(),a.T).T; a=(a+a.conj().T)/2
            ev,y=np.linalg.eigh(a); cv=np.linalg.solve(chol.conj().T,y)
            ref=p.diagonalize(h,np.asarray([k]))[0,s]
            eigdiff.extend(np.abs(ev*RYEV-ref).tolist())
            hn=np.linalg.norm(hm,2); sn=np.linalg.norm(sm,2)
            for j in range(len(ev)):
                v=cv[:,j]; residual=float(np.linalg.norm(hm@v-ev[j]*(sm@v),2)); den=(hn+abs(float(ev[j]))*sn)*float(np.linalg.norm(v,2))
                abs_res.append(residual); rel_res.append(residual/den if den else residual)
    return {'method':'numpy.linalg.eigh after Cholesky generalized-Hermitian reduction','normalized_residual_definition':'||Hc-ESc||2 / ((||H||2+|E| ||S||2)||c||2)','maximum_normalized_residual':float(max(rel_res)),'rms_normalized_residual':float(np.sqrt(np.mean(np.square(rel_res)))),'maximum_absolute_residual_Ry':float(max(abs_res)),'rms_absolute_residual_Ry':float(np.sqrt(np.mean(np.square(abs_res)))),'max_eigenvalue_delta_vs_current_HSX_diagonalizer_eV':float(max(eigdiff)),'rms_eigenvalue_delta_vs_current_HSX_diagonalizer_eV':float(np.sqrt(np.mean(np.square(eigdiff))))}

def main()->None:
    out={'material':'MnO','n_kpoints':23,'n_bands':64,'n_spin_channels':2,'methods':{}}
    for method,(folder,label) in METHODS.items():
        d=HERE/folder; h=p.read_hsx(d/f'{label}.HSX'); k,_=p.read_kp(d/f'{label}.KP')
        hsx=p.diagonalize(h,k); ef_e,eig,layout=p.eig_parse(d/f'{label}.EIG',hsx); ef_h=h['fermi_ev']; delta=eig-hsx
        ix=np.unravel_index(np.argmax(np.abs(delta)),delta.shape); ik,spin,band=map(int,ix)
        reciprocal=2*math.pi*np.linalg.inv((CELL/BOHRANG)).T
        kfrac=k[ik]@np.linalg.inv(reciprocal)
        neighbors=[]
        for b in range(max(0,band-2),min(eig.shape[2],band+3)):
            neighbors.append({'band':b+1,'E_EIG_eV':float(eig[ik,spin,b]),'E_HSX_eV':float(hsx[ik,spin,b]),'delta_eV':float(delta[ik,spin,b]),'E_EIG_minus_EF_eV':float(eig[ik,spin,b]-ef_e),'E_HSX_minus_EF_eV':float(hsx[ik,spin,b]-ef_h),'EIG_spacing_to_next_eV':float(eig[ik,spin,b+1]-eig[ik,spin,b]) if b+1<eig.shape[2] else None,'HSX_spacing_to_next_eV':float(hsx[ik,spin,b+1]-hsx[ik,spin,b]) if b+1<hsx.shape[2] else None})
        windows={}
        for width in (1.,5.):
            mask=(np.abs(eig-ef_e)<=width)|(np.abs(hsx-ef_h)<=width); vals=delta[mask]
            windows[f'within_{width:g}_eV_of_EF']={'state_count':int(vals.size),'max_abs_diff_eV':float(np.max(np.abs(vals))) if vals.size else None,'rms_diff_eV':float(np.sqrt(np.mean(vals**2))) if vals.size else None}
        ce=classify(eig,ef_e); ch=classify(hsx,ef_h); mean=float(delta.mean())
        report={'EF_EIG_eV':ef_e,'EF_HSX_eV':ef_h,'EF_OUT_eV':p.out_metrics(d/'siesta.out')['fermi_energy_eV'],'EF_EIG_HSX_abs_diff_eV':abs(ef_e-ef_h),'mean_EIG_minus_HSX_eV':mean,'max_abs_raw_diff_eV':float(np.max(np.abs(delta))),'rms_raw_diff_eV':float(np.sqrt(np.mean(delta**2))),'max_abs_residual_after_constant_offset_eV':float(np.max(np.abs(delta-mean))),'rms_residual_after_constant_offset_eV':float(np.sqrt(np.mean((delta-mean)**2))),'maximum_location':{'kpoint_index_1based':ik+1,'k_fractional_original_cell':kfrac.tolist(),'k_cartesian_inverse_bohr':k[ik].tolist(),'spin_channel':spin+1,'band_index':band+1,'E_EIG_eV':float(eig[ix]),'E_HSX_eV':float(hsx[ix]),'delta_eV':float(delta[ix]),'E_EIG_minus_EF_eV':float(eig[ix]-ef_e),'E_HSX_minus_EF_eV':float(hsx[ix]-ef_h)},'neighboring_bands_n_minus_2_to_n_plus_2':neighbors,'energy_windows':windows,'classification_EIG':ce,'classification_HSX':ch,'delta_vbm_EIG_minus_HSX_eV':float(ce['vbm']['energy_rel_Ef_eV']-ch['vbm']['energy_rel_Ef_eV']) if ce['vbm'] and ch['vbm'] else None,'delta_cbm_EIG_minus_HSX_eV':float(ce['cbm']['energy_rel_Ef_eV']-ch['cbm']['energy_rel_Ef_eV']) if ce['cbm'] and ch['cbm'] else None,'delta_gap_EIG_minus_HSX_eV':float(ce['gap_eV']-ch['gap_eV']) if ce['classification']==ch['classification']=='INSULATOR' else None,'HSX_generalized_eigensystem_quality':generalized_quality(h,k),'EIG_spin_layout':layout}
        out['methods'][method]=report
    m=out['methods']; lru=m['PBE+LR-U']
    out['compatibility_gate']={
        'same_energy_reference_for_each_method':all(x['EF_EIG_HSX_abs_diff_eV']<1e-8 for x in m.values()),
        'same_classification_each_method':all(x['classification_EIG']['classification']==x['classification_HSX']['classification'] for x in m.values()),
        'PBE_crossing_band_spin_pairs_match':sorted((x['spin'],x['band']) for x in m['PBE']['classification_EIG']['fermi_crossings'])==sorted((x['spin'],x['band']) for x in m['PBE']['classification_HSX']['fermi_crossings']),
        'LRU_edges_and_gap_invariant_sub_meV':max(abs(lru['delta_vbm_EIG_minus_HSX_eV']),abs(lru['delta_cbm_EIG_minus_HSX_eV']),abs(lru['delta_gap_EIG_minus_HSX_eV']))<1e-3,
        'maximum_discrepancy_isolated_high_energy_band':all(x['maximum_location']['band_index']>24 and abs(x['maximum_location']['E_EIG_minus_EF_eV'])>5 and abs(x['maximum_location']['E_HSX_minus_EF_eV'])>5 for x in m.values()),
        'near_fermi_windows_show_no_sub_meV_distortion':all(x['energy_windows']['within_5_eV_of_EF']['max_abs_diff_eV']<1e-3 for x in m.values()),
        'generalized_eigensolver_residuals_sound':all(x['HSX_generalized_eigensystem_quality']['maximum_normalized_residual']<1e-12 for x in m.values()),
    }
    out['compatibility_gate']['status']='HSX_EIG_SPECTRALLY_COMPATIBLE' if all(out['compatibility_gate'].values()) else 'HSX_EIG_REQUIRES_REVIEW'
    path=HERE/'hsx_eig_spectral_diagnostic.json'; path.write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(out,indent=2))

if __name__=='__main__':main()
