#!/usr/bin/env python3
"""Nonscf MnO Seekpath bands from validated converged method-specific HSX."""
from __future__ import annotations
import csv,hashlib,json,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent.parent
BANDS=HERE.parents[0]/'coo'/'bands'; sys.path.insert(0,str(BANDS))
import postprocess_coo_bands as p

OUT=HERE/'bands'; BOHRANG=0.529177210903; FERMI_TOL=1e-7; WINDOW=(-8.,8.)
CELL=np.array([[0.,1.,1.],[.5,0.,.5],[.5,.5,0.]])*4.4455
METHODS={'PBE':('pbe','MNO_PBE_REFERENCE'),'PBE+LR-U':('lru_central','MNCL')}

def sha(path:Path)->str:return hashlib.sha256(path.read_bytes()).hexdigest()
def spectrum_hash(a:np.ndarray)->str:return hashlib.sha256(np.asarray(a,dtype='<f8').tobytes()).hexdigest()
def json_default(value):
    if isinstance(value,np.generic):return value.item()
    raise TypeError(f'not JSON serializable: {type(value).__name__}')

def classify_route(rel:np.ndarray,segments:list[dict])->dict:
    crossings=[]
    for seg in segments:
        ids=seg['indices']
        for s in range(rel.shape[1]):
            for b in range(rel.shape[2]):
                x=rel[ids,s,b]
                if x.min()<=FERMI_TOL and x.max()>=-FERMI_TOL:
                    crossings.append({'spin_channel':s+1,'band_index':b+1,'segment_index':seg['index'],'segment':[seg['start'],seg['end']]})
    below=np.argwhere(rel < -FERMI_TOL); above=np.argwhere(rel > FERMI_TOL)
    if not below.size or not above.size:raise ValueError('route has no sampled states on both sides of EF')
    iv=tuple(np.unravel_index(np.argmax(np.where(rel < -FERMI_TOL,rel,-np.inf)),rel.shape))
    ic=tuple(np.unravel_index(np.argmin(np.where(rel > FERMI_TOL,rel,np.inf)),rel.shape))
    state='METAL' if crossings else 'INSULATOR'
    out={'classification':state,'fermi_crossings':crossings,'crossing_band_spin_pairs':sorted({(x['spin_channel'],x['band_index']) for x in crossings}),'vbm_rel_Ef_eV':float(rel[iv]) if state=='INSULATOR' else None,'cbm_rel_Ef_eV':float(rel[ic]) if state=='INSULATOR' else None,'indirect_gap_eV':float(rel[ic]-rel[iv]) if state=='INSULATOR' else None,
         'vbm_index_0based':iv if state=='INSULATOR' else None,'cbm_index_0based':ic if state=='INSULATOR' else None}
    return out

def route_segments(route:dict)->list[dict]:
    points=route['sampled_points']; segments=[]; previous=None
    for s in route['segments']:
        ids=[i for i,q in enumerate(points) if q['segment_index']==s['index']]
        if s['connected_to_previous']:
            if previous is None:raise ValueError('first route segment cannot be connected')
            ids.insert(0,previous)
        segments.append({'index':s['index'],'start':s['start'],'end':s['end'],'indices':ids})
        previous=ids[-1]
    return segments

def svg(path:Path,rel:np.ndarray,points:list[dict],segments:list[dict],ticks:list[dict],title:str,metadata:dict)->None:
    W,H=1100,680; L,R,T,B=90,30,40,88; pw,ph=W-L-R,H-T-B
    xs=np.array([q['x_inv_ang'] for q in points]); xmin,xmax=xs.min(),xs.max(); ymin,ymax=WINDOW
    xm=lambda x:L+(x-xmin)/(xmax-xmin)*pw; ym=lambda y:T+(ymax-y)/(ymax-ymin)*ph
    colors=['#2166ac','#b2182b']; esc=lambda s:s.replace('&','&amp;').replace('<','&lt;')
    lab={'GAMMA':'Γ'}
    chunks=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" data-material="MnO" data-energy-reference="E-EF" data-ef-line="0" data-spectrum-sha256="{metadata["spectrum_sha256"]}" data-source-hsx-sha256="{metadata["hsx_sha256"]}" data-route-points="{len(points)}">','<rect width="100%" height="100%" fill="white"/>','<g font-family="Arial,sans-serif" fill="#111">',f'<text x="{L}" y="24" font-size="18" font-weight="bold">MnO {esc(title)} Seekpath bands</text>']
    for y in range(-8,9,2):
        yy=ym(y); chunks += [f'<line x1="{L}" y1="{yy:.2f}" x2="{W-R}" y2="{yy:.2f}" stroke="#ddd"/>',f'<text x="{L-10}" y="{yy+4:.2f}" text-anchor="end" font-size="12">{y}</text>']
    yy=ym(0); chunks += [f'<line x1="{L}" y1="{yy:.2f}" x2="{W-R}" y2="{yy:.2f}" stroke="#222" stroke-dasharray="6,5" data-ef-line="0"/>']
    for t in ticks:
        xx=xm(t['x_inv_ang']); chunks += [f'<line x1="{xx:.2f}" y1="{T}" x2="{xx:.2f}" y2="{H-B}" stroke="#555" stroke-width="0.8"/>',f'<text x="{xx:.2f}" y="{H-B+22}" text-anchor="middle" font-size="13">{esc(lab.get(t["label"],t["label"]))}</text>']
    for seg in segments:
        for s in range(rel.shape[1]):
            for b in range(rel.shape[2]):
                vals=[]
                for ik in seg['indices']:
                    e=float(rel[ik,s,b]); vals.append((xm(points[ik]['x_inv_ang']),ym(e)) if ymin-.1<=e<=ymax+.1 else None)
                run=[]
                for q in vals+[None]:
                    if q is None:
                        if len(run)>1:chunks.append('<polyline points="'+' '.join(f'{x:.2f},{y:.2f}' for x,y in run)+f'" fill="none" stroke="{colors[s]}" stroke-width="0.75" opacity="0.72"/>')
                        run=[]
                    else:run.append(q)
    chunks += [f'<text x="{W-245}" y="32" font-size="12" fill="{colors[0]}">spin channel 1 (up)</text>',f'<text x="{W-120}" y="32" font-size="12" fill="{colors[1]}">spin channel 2 (down)</text>','</g></svg>']
    path.write_text('\n'.join(chunks),encoding='utf-8')

def main()->None:
    route=json.loads((OUT/'seekpath_route.json').read_text(encoding='utf-8'))
    diagnostic=json.loads((HERE/'hsx_eig_spectral_diagnostic.json').read_text(encoding='utf-8'))
    if diagnostic['compatibility_gate']['status']!='HSX_EIG_SPECTRALLY_COMPATIBLE':raise RuntimeError('HSX_EIG_REQUIRES_REVIEW')
    points=route['sampled_points']; segments=route_segments(route); ticks=route['ticks']
    reciprocal=(2*np.pi*np.linalg.inv(CELL).T)*BOHRANG
    kcart=np.array([np.array(q['k_frac'])@reciprocal for q in points])
    scf=json.loads((HERE/'scf_observables.json').read_text(encoding='utf-8'))
    methods={}; spectra={}
    for method,(folder,label) in METHODS.items():
        d=HERE/folder; h=p.read_hsx(d/f'{label}.HSX')
        if not np.allclose(h['cell_bohr'].T*BOHRANG,CELL,atol=2e-7,rtol=0):raise ValueError(f'{method} HSX cell differs from exact MnO cell')
        abs_e=p.diagonalize(h,kcart); ef=h['fermi_ev']; rel=abs_e-ef
        cls=classify_route(rel,segments)
        dh=diagnostic['methods'][method]
        state={'method':method,'route_classification':cls['classification'],'fermi_crossing_bands_spin':cls['crossing_band_spin_pairs'],'fermi_crossings':cls['fermi_crossings'],'fermi_energy_HSX_eV':ef,'route_kpoints':len(points),'number_of_bands':int(rel.shape[2]),'number_of_spin_channels':int(rel.shape[1]),'scf_mesh':scf['runs']['PBE' if method=='PBE' else 'PBE+LR-U central']['scf_mesh'],'scf_convergence':scf['runs']['PBE' if method=='PBE' else 'PBE+LR-U central']['convergence'],'source_dm':f'{label}.DM','source_dm_sha256':sha(d/f'{label}.DM'),'source_hsx':f'{label}.HSX','source_hsx_sha256':sha(d/f'{label}.HSX'),'source_eig':f'{label}.EIG','source_eig_sha256':sha(d/f'{label}.EIG'),'hsx_eig_consistency':{'max_abs_raw_diff_eV':dh['max_abs_raw_diff_eV'],'mean_EIG_minus_HSX_eV':dh['mean_EIG_minus_HSX_eV'],'max_abs_residual_after_offset_eV':dh['max_abs_residual_after_constant_offset_eV']}}
        if cls['classification']=='INSULATOR':
            iv=cls['vbm_index_0based']; ic=cls['cbm_index_0based']; direct=[]
            for ik in range(len(points)):
                for s in range(rel.shape[1]):
                    occupied=np.flatnonzero(rel[ik,s]<-FERMI_TOL); unoccupied=np.flatnonzero(rel[ik,s]>FERMI_TOL)
                    if occupied.size and unoccupied.size:
                        vb=int(occupied[np.argmax(rel[ik,s,occupied])]); cb=int(unoccupied[np.argmin(rel[ik,s,unoccupied])])
                        direct.append((float(rel[ik,s,cb]-rel[ik,s,vb]),ik,s,vb,cb))
            if not direct:raise ValueError(f'{method}: could not evaluate direct route gap')
            md=min(direct)
            state.update({'vbm':{'relative_to_Ef_eV':cls['vbm_rel_Ef_eV'],'band_index':iv[2]+1,'spin_channel':iv[1]+1,'route_kpoint_index':iv[0],'k_fractional':points[iv[0]]['k_frac']},'cbm':{'relative_to_Ef_eV':cls['cbm_rel_Ef_eV'],'band_index':ic[2]+1,'spin_channel':ic[1]+1,'route_kpoint_index':ic[0],'k_fractional':points[ic[0]]['k_frac']},'indirect_gap_eV':cls['indirect_gap_eV'],'minimum_direct_gap':{'gap_eV':md[0],'route_kpoint_index':md[1],'spin_channel':md[2]+1,'vbm_band':md[3]+1,'cbm_band':md[4]+1,'k_fractional':points[md[1]]['k_frac']}})
        arrhash=spectrum_hash(rel); csv_name=f"MnO_{'PBE' if method=='PBE' else 'PBE+LR-U'}_seekpath_bands.csv"
        with (OUT/csv_name).open('w',newline='',encoding='utf-8') as f:
            w=csv.writer(f); w.writerow(['path_index','segment_index','segment_start','segment_end','t','kx','ky','kz','k_distance_inv_ang','spin_channel','band_index','energy_ev','energy_minus_ef_ev'])
            for ik,q in enumerate(points):
                for s in range(rel.shape[1]):
                    for b in range(rel.shape[2]):
                        e=float(rel[ik,s,b]); w.writerow([ik,q['segment_index'],*q['segment'],f"{q['t']:.8f}",*[f'{x:.12f}' for x in q['k_frac']],f"{q['x_inv_ang']:.12f}",s+1,b+1,f'{abs_e[ik,s,b]:.10f}',f'{e:.10f}'])
        fig=f"MnO_{'PBE' if method=='PBE' else 'PBE+LR-U'}_SEEKPATH_BANDS.svg"; svg(OUT/fig,rel,points,segments,ticks,method,{'spectrum_sha256':arrhash,'hsx_sha256':state['source_hsx_sha256']})
        csv_rows=list(csv.DictReader((OUT/csv_name).open(encoding='utf-8')))
        csv_rel=np.array([float(x['energy_minus_ef_ev']) for x in csv_rows]).reshape(rel.shape)
        csv_abs=np.array([float(x['energy_ev']) for x in csv_rows]).reshape(abs_e.shape)
        n_inside=0
        if state['route_classification']=='INSULATOR':n_inside=int(np.count_nonzero((rel>cls['vbm_rel_Ef_eV'])&(rel<cls['cbm_rel_Ef_eV'])))
        svgtext=(OUT/fig).read_text(encoding='utf-8')
        svg_meta_ok=all(x in svgtext for x in [f'data-energy-reference="E-EF"',f'data-ef-line="0"',f'data-spectrum-sha256="{arrhash}"',f'data-source-hsx-sha256="{state["source_hsx_sha256"]}"',f'data-route-points="{len(points)}"'])
        val={'rows':len(csv_rows),'expected_rows':int(np.prod(rel.shape)),'max_csv_rel_array_abs_diff_eV':float(np.max(np.abs(csv_rel-rel))),'max_csv_abs_array_abs_diff_eV':float(np.max(np.abs(csv_abs-abs_e))),'route_gap_interval_eigenvalue_count':n_inside,'svg_energy_reference':'E-EF','svg_fermi_line_at_zero':True,'svg_metadata_matches_array_and_source':svg_meta_ok,'svg_spectrum_sha256':arrhash,'svg_source_hsx_sha256':state['source_hsx_sha256']}
        if val['rows']!=val['expected_rows'] or val['max_csv_rel_array_abs_diff_eV']>5.1e-11 or val['max_csv_abs_array_abs_diff_eV']>5.1e-11 or n_inside!=0 or not svg_meta_ok:raise RuntimeError(f'{method} derived-band artifact validation failed: {val}')
        state.update({'bands_csv':csv_name,'figure_svg':fig,'spectrum_sha256':arrhash,'artifact_validation':val})
        methods[method]=state; spectra[method]={'relative':rel,'absolute':abs_e}
    result={'status':'COMPLETE','material':'MnO','hsx_eig_compatibility':'HSX_EIG_SPECTRALLY_COMPATIBLE','seekpath_route_file':'seekpath_route.json','seekpath_version':route['seekpath_version'],'symprec_A':route['symprec_A'],'spacegroup':route['detected_spacegroup_international'],'spacegroup_number':route['detected_spacegroup_number'],'ordered_path':route['complete_ordered_path'],'special_point_coordinates':route['special_point_coordinates_reciprocal_original_cell'],'route_kpoint_count':len(points),'energy_window_relative_to_Ef_eV':list(WINDOW),'methods':methods,'gap_scope':'SCF-mesh and Seekpath-route values are sampled; neither proves the continuous global Brillouin-zone gap.'}
    (OUT/'results.json').write_text(json.dumps(result,indent=2,ensure_ascii=False,default=json_default)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2,ensure_ascii=False,default=json_default))

if __name__=='__main__':main()
