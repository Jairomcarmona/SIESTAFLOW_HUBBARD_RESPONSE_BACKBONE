#!/usr/bin/env python3
"""CoO V6 observable post-processing from existing converged HSX/EIG/KP only."""
from __future__ import annotations
import csv, hashlib, importlib.metadata, importlib.util, json, math, re, sys
from pathlib import Path
import numpy as np
import seekpath

BASE=Path(__file__).resolve().parents[2]
OUT=BASE/'coo'/'bands'
ROOT=BASE.parents[0]
HELPER=ROOT/'FEO_SCF_DIAGNOSTIC_EXPORT_20261001'/'analyze_feo_seekpath_bands.py'
spec=importlib.util.spec_from_file_location('hsx_tools',HELPER)
hsx_tools=importlib.util.module_from_spec(spec); spec.loader.exec_module(hsx_tools)
read_hsx=hsx_tools.read_hsx; diagonalize=hsx_tools.diagonalize; read_kp=hsx_tools.read_kp; classify=hsx_tools.classify_spectrum
RYEV=13.605693122994; BOHRANG=0.529177210903; KB=8.617333262145e-5
INTERVALS=40; FERMI_TOL=1e-7; WINDOW=(-8.,8.)
METHODS={'PBE':(BASE/'coo'/'pbe','COOPBE'),'PBE+LR-U':(BASE/'coo'/'pbe_lru','COOLRU')}
CELL=np.array([[0.,1.,1.],[.5,0.,.5],[.5,.5,0.]])*4.254
POS=np.array([[0.,0.,0.],[.5,0.,0.],[.25,.5,.5],[.75,.5,.5]])
# Distinct labels encode the opposite AFM-II magnetic sublattices; these are
# identity tags for symmetry detection, not a forced space group.
NUMBERS=[27,28,8,8]


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def route_make():
    result=seekpath.get_path_orig_cell((CELL,POS,NUMBERS),symprec=1e-5,angle_tolerance=-1.0)
    coords={k:list(map(float,v)) for k,v in result['point_coords'].items()}
    path=[list(x) for x in result['path']]
    rec=2*math.pi*np.linalg.inv(CELL).T
    points=[]; segs=[]; ticks=[]; cum=0.; prev=None
    for si,(a,b) in enumerate(path):
        p0=np.array(coords[a]); p1=np.array(coords[b]); ks=np.linspace(p0,p1,INTERVALS+1)
        ds=np.linalg.norm(np.diff(ks,axis=0)@rec,axis=1)
        connected=prev==a
        begin=1 if connected else 0
        if not connected: ticks.append({'labels':[a],'x_inv_ang':cum,'k_frac':p0.tolist()})
        ids=[]
        if connected: ids.append(len(points)-1)
        for j in range(begin,INTERVALS+1):
            if j>0: cum+=float(ds[j-1])
            idx=len(points); ids.append(idx)
            points.append({'k_frac':ks[j].tolist(),'x_inv_ang':cum,'segment_index':si,'segment':[a,b],'t':j/INTERVALS})
        ticks.append({'labels':[b],'x_inv_ang':cum,'k_frac':p1.tolist()})
        segs.append({'index':si,'start':a,'end':b,'indices':ids})
        prev=b
    return result,coords,path,points,segs,ticks

def route_from_saved_file():
    """Consume the already approved route verbatim; do not regenerate it."""
    obj=json.loads((OUT/'seekpath_route.json').read_text(encoding='utf-8'))
    points=obj['sampled_points']; ticks=[{'labels':[t['label']],'x_inv_ang':t['x_inv_ang'],'k_frac':t['k_frac']} for t in obj['ticks']]
    segs=[]; prev_end=None
    for s in obj['segments']:
        ids=[i for i,p in enumerate(points) if p['segment_index']==s['index']]
        if s['connected_to_previous']:
            if prev_end is None: raise ValueError('saved route marks first segment connected')
            ids.insert(0,prev_end)
        if not ids: raise ValueError(f"saved route segment {s['index']} has no points")
        segs.append({'index':s['index'],'start':s['start'],'end':s['end'],'indices':ids})
        prev_end=ids[-1]
    if len(points)!=283: raise ValueError(f"expected saved Seekpath route of 283 points, got {len(points)}")
    coords=obj['special_point_coordinates_reciprocal_original_cell']; path=obj['complete_ordered_path']
    sd={'spacegroup_international':obj['detected_spacegroup_international'],'spacegroup_number':obj['detected_spacegroup_number'],'spacegroup_hall':None,'bravais_lattice':obj['detected_bravais_lattice'],'bravais_lattice_extended':obj['bravais_lattice_extended']}
    return obj,sd,coords,path,points,segs,ticks

def eig_parse(p,hsx_eigs):
    lines=p.read_text().splitlines(); ef=float(lines[0]); nb,ns,nk=map(int,lines[1].split())
    blocks=[]; current=None; vals=[]
    def close():
        if current is not None: blocks.append((current,vals.copy()))
    for line in lines[2:]:
        ss=line.split()
        if not ss: continue
        is_start=False
        try:
            ki=int(ss[0]); is_start=(1<=ki<=nk and len(ss)>1 and ('e' in ss[1].lower() or '.' in ss[1]))
        except ValueError: pass
        if is_start:
            close(); current=ki; vals=[float(v) for v in ss[1:]]
        elif current is not None:
            vals.extend(float(v) for v in ss)
    close()
    if len(blocks)!=nk or [k for k,_ in blocks]!=list(range(1,nk+1)): raise ValueError(f'EIG k blocks malformed: {len(blocks)} vs {nk}')
    raw=np.array([v for _,v in blocks],float)
    if raw.shape!=(nk,nb*ns): raise ValueError(f'EIG data shape {raw.shape}, expected {(nk,nb*ns)}')
    candidates=[raw.reshape(nk,ns,nb),raw.reshape(nk,nb,ns).transpose(0,2,1)]
    errs=[np.abs(x-hsx_eigs) for x in candidates]
    j=min(range(2),key=lambda q:float(np.max(errs[q])))
    return ef,candidates[j],{'format':'kpoint-index + eigenvalues, spin-major' if j==0 else 'kpoint-index + eigenvalues, band-interleaved spin','max_abs_candidate_error_ev':float(np.max(errs[j]))}

def out_metrics(path):
    s=path.read_text(errors='replace')
    def last(pattern,group=1,default=None):
        ms=list(re.finditer(pattern,s,re.I|re.M)); return float(ms[-1].group(group)) if ms else default
    it=re.search(r'SCF cycle converged after\s+(\d+) iterations',s)
    dD=last(r'max \|DM_out - DM_in\|\s*:\s*([0-9.eE+-]+)')
    dH=last(r'max \|H_out - H_in\|\s*\(eV\)\s*:\s*([0-9.eE+-]+)')
    pop=last(r'max \|pop\(DFT\+U\)_i - pop\(DFT\+U\)_j\|:\s*([0-9.eE+-]+)')
    et=last(r'siesta:\s+Etot\s*=\s*([+-]?[0-9.eE+-]+)')
    free=last(r'siesta:\s+FreeEng\s*=\s*([+-]?[0-9.eE+-]+)')
    ef=last(r'siesta:\s+Fermi\s*=\s*([+-]?[0-9.eE+-]+)')
    moments=[]; lines=s.splitlines()
    for i,line in enumerate(lines):
        if 'Mulliken Atomic Populations:' in line:
            j=i+2; block=[]
            while j<len(lines) and lines[j].strip().startswith(tuple(str(x) for x in range(10))):
                q=lines[j].split()
                if len(q)>=5:
                    try: block.append({'atom':int(q[0]),'charge_e':float(q[1]),'valence_e':float(q[2]),'moment_muB':float(q[3]),'species':q[4]})
                    except ValueError: pass
                j+=1
            if block: moments=block
    return {'scf_converged':it is not None,'iterations':int(it.group(1)) if it else None,'dDmax':dD,'dHmax_eV':dH,'DFTU_population_change':pop,'total_energy_eV':et,'free_energy_eV':free,'fermi_energy_eV':ef,'mulliken_atoms':moments,'total_moment_muB':sum(x['moment_muB'] for x in moments)}

def mesh_summary(hsx,eig_abs,kp,ef_eig):
    k,w=read_kp(kp); rel=eig_abs-ef_eig
    # Thermal occupations are reconstructed from actual EIG, actual Ef and 300 K.
    temp=hsx['temperature_k']; occ=1/(1+np.exp(np.clip(rel/(KB*temp),-700,700)))
    cross=[]; partial=[]
    for sp in range(rel.shape[1]):
        for b in range(rel.shape[2]):
            curve=rel[:,sp,b]
            if curve.min()<=FERMI_TOL and curve.max()>=-FERMI_TOL: cross.append({'spin_channel':sp+1,'band_index':b+1,'min_rel_Ef_eV':float(curve.min()),'max_rel_Ef_eV':float(curve.max())})
            if np.any((occ[:,sp,b]>1e-6)&(occ[:,sp,b]<1-1e-6)): partial.append({'spin_channel':sp+1,'band_index':b+1})
    below=rel[rel< -FERMI_TOL]; above=rel[rel>FERMI_TOL]
    state='METAL' if cross else 'INSULATOR'
    ret={'classification':state,'kpoint_count':int(len(k)),'number_of_bands':int(rel.shape[2]),'fermi_crossing_bands':cross,'partially_occupied_bands_at_300K':partial,'max_occupied_energy_rel_Ef_eV':float(below.max()) if below.size else None,'min_unoccupied_energy_rel_Ef_eV':float(above.min()) if above.size else None,'occupation_weighted_electron_count':float(np.sum(occ*w[:,None,None])),'temperature_K':temp,'fermi_energy_EIG_eV':ef_eig}
    ret['occupation_aware_gap_eV']=(float(above.min()-below.max()) if state=='INSULATOR' and below.size and above.size else 0.0 if state=='METAL' else None)
    return ret

def sample_route(route_data,hsx,eig,eigef):
    spres,coords,path,points,segs,ticks=route_data
    reciprocal=(2*math.pi*np.linalg.inv(CELL).T)*BOHRANG
    kcart=np.array([np.array(p['k_frac'])@reciprocal for p in points])
    energy={}; result={}
    for method,(d,label) in METHODS.items():
        h=hsx[method]; observed=h['cell_bohr'].T*BOHRANG
        if not np.allclose(observed,CELL,atol=2e-7,rtol=0): raise RuntimeError(f'{method} HSX cell mismatch')
        ef=h['fermi_ev']; absE=diagonalize(h,kcart); rel=absE-ef
        cls=classify(rel,segments=segs)
        md=(None,None,None)
        if cls['classification']=='INSULATOR':
            direct=[]
            for ik in range(len(points)):
                for s in range(rel.shape[1]):
                    below=np.flatnonzero(rel[ik,s]<-FERMI_TOL); above=np.flatnonzero(rel[ik,s]>FERMI_TOL)
                    if above.size and below.size:
                        vb=int(below[np.argmax(rel[ik,s,below])]); cb=int(above[np.argmin(rel[ik,s,above])])
                        direct.append((float(rel[ik,s,cb]-rel[ik,s,vb]),ik,s,vb,cb))
            md=min(direct) if direct else (None,None,None)
        energy[method]=rel
        result[method]={'route_classification':cls['classification'],'fermi_crossing_bands':cls['crossing_bands'],'fermi_crossing_channels':cls['crossing_channels'],'fermi_crossings':cls['crossings'],'fermi_energy_HSX_eV':ef,'number_of_bands':int(h['norb']),'route_kpoints':len(points)}
        if cls['classification']=='INSULATOR':
            iv=cls['vbm_index']; ic=cls['cbm_index']; result[method].update({'vbm':{'relative_to_Ef_eV':cls['vbm_rel_ev'],'band':iv[2]+1,'spin_channel':iv[1]+1,'k_fractional':points[iv[0]]['k_frac']},'cbm':{'relative_to_Ef_eV':cls['cbm_rel_ev'],'band':ic[2]+1,'spin_channel':ic[1]+1,'k_fractional':points[ic[0]]['k_frac'],'indirect_gap_eV':cls['indirect_gap_ev']},'minimum_direct_gap':{'gap_eV':md[0],'kpoint_index':md[1],'spin_channel':md[2]+1 if md[2] is not None else None,'vbm_band':md[3]+1 if len(md)>3 and md[3] is not None else None,'cbm_band':md[4]+1 if len(md)>4 and md[4] is not None else None,'k_fractional':points[md[1]]['k_frac'] if md[1] is not None else None}})
        result[method]['scf_mesh']=mesh_summary(h,eig[method],METHODS[method][0]/f'{label}.KP',eigef[method])
        result[method]['scf_convergence']=out_metrics(METHODS[method][0]/'siesta.out')
    return result,energy,points,segs,ticks,coords,path

def svg(path,rel,points,segs,ticks,title,metadata):
    W,H=1100,680; L,R,T,B=90,30,40,88; pw,ph=W-L-R,H-T-B; xs=np.array([p['x_inv_ang'] for p in points]); xmin,xmax=xs.min(),xs.max(); ymin,ymax=WINDOW
    xm=lambda x:L+(x-xmin)/(xmax-xmin)*pw; ym=lambda y:T+(ymax-y)/(ymax-ymin)*ph
    colors=['#2166ac','#b2182b']; esc=lambda s:s.replace('&','&amp;').replace('<','&lt;')
    lab={'GAMMA':'Γ','GAMMA_1':'Γ₁'}
    chunks=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" data-material="CoO" data-energy-reference="E-EF" data-ef-line="0" data-spectrum-sha256="{metadata["spectrum_sha256"]}" data-source-hsx-sha256="{metadata["hsx_sha256"]}" data-route-points="{len(points)}">','<rect width="100%" height="100%" fill="white"/>','<g font-family="Arial,sans-serif" fill="#111">',f'<text x="{L}" y="24" font-size="18" font-weight="bold">CoO {esc(title)} Seekpath bands</text>']
    for y in range(-8,9,2):
        yy=ym(y); chunks += [f'<line x1="{L}" y1="{yy:.2f}" x2="{W-R}" y2="{yy:.2f}" stroke="#ddd"/>',f'<text x="{L-10}" y="{yy+4:.2f}" text-anchor="end" font-size="12">{y}</text>']
    yy=ym(0); chunks += [f'<line x1="{L}" y1="{yy:.2f}" x2="{W-R}" y2="{yy:.2f}" stroke="#222" stroke-dasharray="6,5" data-ef-line="0"/>']
    for t in ticks:
        xx=xm(t['x_inv_ang']); chunks += [f'<line x1="{xx:.2f}" y1="{T}" x2="{xx:.2f}" y2="{H-B}" stroke="#555" stroke-width="0.8"/>',f'<text x="{xx:.2f}" y="{H-B+22}" text-anchor="middle" font-size="13">{esc("|".join(lab.get(a,a) for a in t["labels"]))}</text>']
    for seg in segs:
        for s in range(rel.shape[1]):
            for b in range(rel.shape[2]):
                pts=[]
                for ik in seg['indices']:
                    val=float(rel[ik,s,b]); pts.append((xm(points[ik]['x_inv_ang']),ym(val)) if ymin-.1<=val<=ymax+.1 else None)
                run=[]
                for p in pts+[None]:
                    if p is None:
                        if len(run)>1: chunks.append('<polyline points="'+' '.join(f'{x:.2f},{y:.2f}' for x,y in run)+f'" fill="none" stroke="{colors[s]}" stroke-width="0.75" opacity="0.72"/>')
                        run=[]
                    else: run.append(p)
    chunks += [f'<text x="{W-245}" y="32" font-size="12" fill="{colors[0]}">spin channel 1 (up)</text>',f'<text x="{W-120}" y="32" font-size="12" fill="{colors[1]}">spin channel 2 (down)</text>','</g></svg>']
    path.write_text('\n'.join(chunks),encoding='utf-8')

def main():
    OUT.mkdir(exist_ok=True,parents=True)
    route,sd,coords,path,points,segs,ticks=route_from_saved_file()
    diagnostic=json.loads((OUT/'hsx_eig_spectral_diagnostic.json').read_text(encoding='utf-8'))
    gates={}
    for method,m in diagnostic['methods'].items():
        gates[method]={
            'same_energy_zero':m['EIG_HSX_EF_difference_eV']<1e-8,
            'classification_matches':m['classification_EIG']['classification']==m['classification_HSX']['classification'],
            'same_fermi_crossing_band_spin_pairs':sorted((x['spin'],x['band']) for x in m['classification_EIG']['fermi_crossings'])==sorted((x['spin'],x['band']) for x in m['classification_HSX']['fermi_crossings']),
            'isolated_high_energy_maximum':m['maximum_location']['band_index']==62 and abs(m['maximum_location']['E_EIG_minus_EF_eV'])>5 and abs(m['maximum_location']['E_HSX_minus_EF_eV'])>5,
            'max_diff_within_1_eV_below_1_meV':m['energy_windows']['within_1_eV_of_EF']['MAX_ABS_DIFF_eV']<1e-3,
            'max_diff_within_5_eV_below_1_meV':m['energy_windows']['within_5_eV_of_EF']['MAX_ABS_DIFF_eV']<1e-3,
            'hsx_generalized_residual_sound':m['HSX_generalized_eigensystem_quality']['maximum_normalized_residual']<1e-12,
        }
        if method=='PBE+LR-U':
            gates[method]['edges_gap_invariant_sub_meV']=max(abs(m['delta_vbm_eig_minus_hsx_eV']),abs(m['delta_cbm_eig_minus_hsx_eV']),abs(m['delta_gap_eig_minus_hsx_eV']))<1e-3
    if not all(all(v for k,v in q.items() if k!='edges_gap_invariant_sub_meV') and q.get('edges_gap_invariant_sub_meV',True) for q in gates.values()):
        raise RuntimeError('HSX_EIG_REQUIRES_REVIEW: explicit spectral-compatibility gate failed: '+json.dumps(gates))
    hmap={}; eig={}; eigef={}; energy_ref={}
    for method,(d,label) in METHODS.items():
        h=read_hsx(d/f'{label}.HSX'); hmap[method]=h
        kp,w=read_kp(d/f'{label}.KP'); eh=diagonalize(h,kp)
        ef_e,eigarr,order=eig_parse(d/f'{label}.EIG',eh); eig[method]=eigarr; eigef[method]=ef_e
        delta=eigarr-eh; offset=float(delta.mean()); resid=delta-offset
        rel='SAME_ENERGY_ZERO_WITH_ISOLATED_HIGH_ENERGY_NUMERICAL_OUTLIER' if gates[method]['same_energy_zero'] else 'REVIEW'
        out=out_metrics(d/'siesta.out')
        energy_ref[method]={'relation':rel,'MAX_ABS_RAW_DIFFERENCE_eV':float(np.max(np.abs(delta))),'MEAN_RAW_DIFFERENCE_eV':float(delta.mean()),'BEST_CONSTANT_OFFSET_DELTA_eV':offset,'MAX_ABS_RESIDUAL_AFTER_OFFSET_eV':float(np.max(np.abs(resid))),'RMS_RESIDUAL_AFTER_OFFSET_eV':float(np.sqrt(np.mean(resid**2))),'EIG_Fermi_eV':ef_e,'HSX_Fermi_eV':h['fermi_ev'],'SIESTA_OUT_Fermi_eV':out['fermi_energy_eV'],'EIG_HSX_Fermi_abs_diff_eV':abs(ef_e-h['fermi_ev']),'EIG_spin_layout':order,'EIG_source':f'{label}.EIG','HSX_source':f'{label}.HSX','KP_source':f'{label}.KP','method':'PBE' if method=='PBE' else 'PBE+LR-U','source_DM':f'{label}.DM','source_DM_sha256':sha(d/f'{label}.DM'),'source_HSX_sha256':sha(d/f'{label}.HSX')}
    result,energies,points,segs,ticks,coords,path=sample_route((sd,coords,path,points,segs,ticks),hmap,eig,eigef)
    route['energy_reference_checks']=energy_ref
    route['hsx_eig_compatibility_gate']={'status':'HSX_EIG_SPECTRALLY_COMPATIBLE','criteria':gates,'diagnostic_file':'hsx_eig_spectral_diagnostic.json'}
    (OUT/'seekpath_route.json').write_text(json.dumps(route,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    methods={}
    for method in METHODS:
        rel=energies[method]; name='pbe' if method=='PBE' else 'pbe_lru'; fn=f'{name}_bands.csv'
        arrhash=hashlib.sha256(np.asarray(rel,dtype='<f8').tobytes()).hexdigest()
        with (OUT/fn).open('w',newline='',encoding='utf-8') as f:
            w=csv.writer(f); w.writerow(['path_index','segment_index','segment_start','segment_end','t','kx','ky','kz','k_distance_inv_ang','spin_channel','band_index','energy_ev','energy_minus_ef_ev'])
            for ik,p in enumerate(points):
                for s in range(rel.shape[1]):
                    for b in range(rel.shape[2]):
                        e=float(rel[ik,s,b]); w.writerow([ik,p['segment_index'],*p['segment'],f"{p['t']:.8f}",*[f'{x:.10f}' for x in p['k_frac']],f"{p['x_inv_ang']:.10f}",s+1,b+1,f"{e+hmap[method]['fermi_ev']:.10f}",f'{e:.10f}'])
        fig=f'CoO_{"PBE" if method=="PBE" else "PBE+LR-U"}_SEEKPATH_BANDS.svg'; svg(OUT/fig,rel,points,segs,ticks,method,{'spectrum_sha256':arrhash,'hsx_sha256':energy_ref[method]['source_HSX_sha256']})
        csv_rows=list(csv.DictReader((OUT/fn).open(encoding='utf-8')))
        csv_rel=np.array([float(x['energy_minus_ef_ev']) for x in csv_rows]).reshape(rel.shape)
        csv_abs=np.array([float(x['energy_ev']) for x in csv_rows]).reshape(rel.shape)
        cls=result[method]['route_classification']; n_inside=0
        if cls=='INSULATOR':
            low=result[method]['vbm']['relative_to_Ef_eV']; high=result[method]['cbm']['relative_to_Ef_eV']
            n_inside=int(np.count_nonzero((rel>low)&(rel<high)))
        svgtext=(OUT/fig).read_text(encoding='utf-8')
        svg_meta_ok=all(x in svgtext for x in [f'data-energy-reference="E-EF"',f'data-ef-line="0"',f'data-spectrum-sha256="{arrhash}"',f'data-source-hsx-sha256="{energy_ref[method]["source_HSX_sha256"]}"',f'data-route-points="{len(points)}"'])
        artifact_validation={'csv_rows':len(csv_rows),'expected_csv_rows':int(np.prod(rel.shape)),'max_csv_rel_array_abs_diff_eV':float(np.max(np.abs(csv_rel-rel))),'max_csv_abs_array_abs_diff_eV':float(np.max(np.abs(csv_abs-(rel+hmap[method]['fermi_ev'])))),'route_gap_interval_eigenvalue_count':n_inside,'svg_energy_reference':'E-EF','svg_fermi_line_at_zero':True,'svg_metadata_matches_array_and_source':svg_meta_ok,'svg_spectrum_sha256':arrhash,'svg_source_hsx_sha256':energy_ref[method]['source_HSX_sha256']}
        if artifact_validation['csv_rows']!=artifact_validation['expected_csv_rows'] or artifact_validation['max_csv_rel_array_abs_diff_eV']>5.1e-11 or artifact_validation['max_csv_abs_array_abs_diff_eV']>5.1e-11 or n_inside!=0 or not svg_meta_ok: raise RuntimeError(f'{method} SVG/CSV spectrum mismatch: {artifact_validation}')
        result[method]['bands_csv']=fn; result[method]['figure_svg']=fig; result[method]['spectrum_sha256']=arrhash; result[method]['artifact_validation']=artifact_validation; result[method]['energy_reference_check']=energy_ref[method]; methods[method]=result[method]
    report={'status':'COMPLETE','material':'CoO','hsx_eig_compatibility':'HSX_EIG_SPECTRALLY_COMPATIBLE','seekpath_route_file':'seekpath_route.json','seekpath_version':route['seekpath_version'],'spacegroup':route['detected_spacegroup_international'],'spacegroup_number':route['detected_spacegroup_number'],'symprec_A':route['symprec_A'],'ordered_path':path,'special_points':coords,'route_kpoint_count':len(points),'methods':methods,'distinction':'SCF-mesh and Seekpath gaps are sampled; neither proves a continuous global BZ gap.'}
    (OUT/'results.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2,ensure_ascii=False))
if __name__=='__main__': main()


