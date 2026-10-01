#!/usr/bin/env python3
"""Generate and freeze the standard Seekpath route for the exact MnO cell."""
from __future__ import annotations
import importlib.metadata,json,math
from pathlib import Path
import numpy as np,seekpath
HERE=Path(__file__).resolve().parent
CELL=np.array([[0.,1.,1.],[.5,0.,.5],[.5,.5,0.]])*4.4455
POS=np.array([[0,0,0],[.5,0,0],[.25,.5,.5],[.75,.5,.5]],float)
# Distinct labels identify AFM-II spin sublattices; the space group is not forced.
NUMBERS=[25,26,8,8]
SYMPREC=1e-5; INTERVALS=40
r=seekpath.get_path_orig_cell((CELL,POS,NUMBERS),symprec=SYMPREC,angle_tolerance=-1.0)
coords={k:list(map(float,v)) for k,v in r['point_coords'].items()}; path=[list(x) for x in r['path']]
rec=2*math.pi*np.linalg.inv(CELL).T; points=[]; x=0.; prev=None; ticks=[]; spans=[]
for si,(a,b) in enumerate(path):
    q0=np.array(coords[a]); q1=np.array(coords[b]); arr=np.linspace(q0,q1,INTERVALS+1)
    ds=np.linalg.norm(np.diff(arr,axis=0)@rec,axis=1); connected=prev==a; start=1 if connected else 0
    if not connected:ticks.append({'label':a,'x_inv_ang':x,'k_frac':q0.tolist()})
    for j in range(start,INTERVALS+1):
        if j>0:x+=float(ds[j-1])
        points.append({'segment_index':si,'segment':[a,b],'t':j/INTERVALS,'k_frac':arr[j].tolist(),'x_inv_ang':x})
    ticks.append({'label':b,'x_inv_ang':x,'k_frac':q1.tolist()}); spans.append({'index':si,'start':a,'end':b,'connected_to_previous':connected}); prev=b
obj={'material':'MnO','source_structure':'benchmarks/lr_u/MnO/reference.fdf','seekpath_version':importlib.metadata.version('seekpath'),'method':'seekpath.get_path_orig_cell','symprec_A':SYMPREC,'angle_tolerance_deg':-1.0,'detected_spacegroup_international':r['spacegroup_international'],'detected_spacegroup_number':int(r['spacegroup_number']),'detected_spacegroup_hall':r.get('spacegroup_hall'),'detected_bravais_lattice':r['bravais_lattice'],'detected_bravais_lattice_extended':r['bravais_lattice_extended'],'no_spacegroup_forced':True,'magnetic_sublattice_identity_tags':{'MnLR0':25,'MnLR1':26,'O':8},'lattice_vectors_ang':CELL.tolist(),'fractional_positions':POS.tolist(),'special_point_coordinates_reciprocal_original_cell':coords,'complete_ordered_path':path,'intervals_per_segment':INTERVALS,'sampled_kpoint_count':len(points),'segments':spans,'ticks':ticks,'sampled_points':points,'band_evaluation_status':'ROUTE_GENERATED'}
(HERE/'bands').mkdir(parents=True,exist_ok=True)
(HERE/'bands'/'seekpath_route.json').write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print(json.dumps({k:obj[k] for k in ['seekpath_version','symprec_A','detected_spacegroup_international','detected_spacegroup_number','complete_ordered_path','special_point_coordinates_reciprocal_original_cell','sampled_kpoint_count','no_spacegroup_forced']},indent=2,ensure_ascii=False))
