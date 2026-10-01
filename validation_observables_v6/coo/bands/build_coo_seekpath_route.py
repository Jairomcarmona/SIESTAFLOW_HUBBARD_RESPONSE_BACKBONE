import importlib.metadata,json,math
from pathlib import Path
import numpy as np, seekpath
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
cell=np.array([[0.,1.,1.],[.5,0.,.5],[.5,.5,0.]])*4.254
pos=np.array([[0,0,0],[.5,0,0],[.25,.5,.5],[.75,.5,.5]],float)
# Magnetic sublattices receive distinct identity tags; no space group is forced.
r=seekpath.get_path_orig_cell((cell,pos,[27,28,8,8]),symprec=1e-5,angle_tolerance=-1.0)
coords={k:list(map(float,v)) for k,v in r['point_coords'].items()}; path=[list(x) for x in r['path']]
rec=2*math.pi*np.linalg.inv(cell).T; points=[]; x=0.; prev=None; ticks=[]; spans=[]
for si,(a,b) in enumerate(path):
    q0=np.array(coords[a]); q1=np.array(coords[b]); arr=np.linspace(q0,q1,41); ds=np.linalg.norm(np.diff(arr,axis=0)@rec,axis=1); connected=prev==a; start=1 if connected else 0
    if not connected: ticks.append({'label':a,'x_inv_ang':x,'k_frac':q0.tolist()})
    for j in range(start,41):
        if j>0: x+=float(ds[j-1])
        points.append({'segment_index':si,'segment':[a,b],'t':j/40,'k_frac':arr[j].tolist(),'x_inv_ang':x})
    ticks.append({'label':b,'x_inv_ang':x,'k_frac':q1.tolist()}); spans.append({'index':si,'start':a,'end':b,'connected_to_previous':connected}); prev=b
obj={'material':'CoO','source_structure':'benchmarks/lr_u/CoO/reference.fdf','seekpath_version':importlib.metadata.version('seekpath'),'method':'seekpath.get_path_orig_cell','symprec_A':1e-5,'angle_tolerance_deg':-1.0,'detected_spacegroup_international':r['spacegroup_international'],'detected_spacegroup_number':int(r['spacegroup_number']),'detected_bravais_lattice':r['bravais_lattice'],'bravais_lattice_extended':r['bravais_lattice_extended'],'no_spacegroup_forced':True,'magnetic_sublattice_identity_tags':{'CoLR0':27,'CoLR1':28,'O':8},'lattice_vectors_ang':cell.tolist(),'fractional_positions':pos.tolist(),'special_point_coordinates_reciprocal_original_cell':coords,'complete_ordered_path':path,'segments':spans,'intervals_per_segment':40,'sampled_kpoint_count':len(points),'ticks':ticks,'sampled_points':points,'band_evaluation_status':'STOPPED_BEFORE_BAND_EVALUATION_PENDING_HSX_EIG_REVIEW'}
(OUT/'seekpath_route.json').write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print(json.dumps({k:obj[k] for k in ['seekpath_version','symprec_A','detected_spacegroup_international','detected_spacegroup_number','complete_ordered_path','special_point_coordinates_reciprocal_original_cell','sampled_kpoint_count','band_evaluation_status']},indent=2,ensure_ascii=False))
