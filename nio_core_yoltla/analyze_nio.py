import json
from pathlib import Path
from siestaflow_hubbard.siesta_backend.event_parser import parse_hubbard_population_events
from siestaflow_hubbard.siesta_backend.observation_selector import Siesta542BarePolicyV1
from siestaflow_hubbard.siesta_backend.parser_models import ObservationContext
from production_benchmarks.lr_arithmetic import build_chi_matrix_3point, compute_U_matrix
runs=json.loads(Path('runs.json').read_text()); obs={}; reference=[]
for run in runs:
    text=(Path(run['directory'])/'siesta.out').read_text(errors='ignore'); events=parse_hubbard_population_events(text)
    if run['mode']=='REFERENCE':
        event=events[-1]; reference=[a.trace_total for a in event.atoms]
        continue
    if run['mode']=='BARE':
        ctx=ObservationContext(siesta_version='5.4.2',calculation_mode='BARE',reference_dm_sha256='reference.DM',projector_fingerprint='method2',scf_mix_target='density',scf_mixer_method='Linear',scf_mixer_weight=1.0,max_scf_iterations=2,convergence_confirmed=False,final_scf_iteration=None,post_scf_population_occurrence=None)
        sel=Siesta542BarePolicyV1.get_bare_observation(events,ctx)
    else:
        if not ((Path(run['directory']) / '0_NORMAL_EXIT').is_file() or 'siesta: normal completion' in text.lower()):
            raise RuntimeError(f"{run['directory']}: normal SIESTA completion missing")
        if 'scf: not converged' in text.lower():
            raise RuntimeError(f"{run['directory']}: SCREENED SCF did not converge")
        final=max(e.scf_iteration or 0 for e in events)
        ctx=ObservationContext(siesta_version='5.4.2',calculation_mode='SCREENED',reference_dm_sha256='reference.DM',projector_fingerprint='method2',scf_mix_target=None,scf_mixer_method=None,scf_mixer_weight=None,max_scf_iterations=200,convergence_confirmed=True,final_scf_iteration=final,post_scf_population_occurrence=None)
        sel=Siesta542BarePolicyV1.get_screened_observation(events,ctx)
    vector=[a.trace_total for a in sel.event.atoms]
    if len(vector)!=2: raise RuntimeError(f"{run['directory']}: expected occupations for two Ni sites, got {len(vector)}")
    obs[(run['J'],float(run['alpha']),run['mode'])]=vector
    print(run['mode'], 'J=',run['J'],'alpha=',run['alpha'],'occurrence=',sel.event.occurrence_index,'occupations=',vector)
chi0=build_chi_matrix_3point(obs,2,.01,'BARE'); chi=build_chi_matrix_3point(obs,2,.01,'SCREENED'); u=compute_U_matrix(chi0,chi)
result={'reference_occupations':reference,'observations':{str(k):v for k,v in obs.items()},'chi0':chi0.tolist(),'chi':chi.tolist(),'rank_chi0':u['chi0_rank'],'rank_chi':u['chi_rank'],'singular_values_chi0':u['chi0_svd'],'singular_values_chi':u['chi_svd'],'condition_chi0':u['chi0_cond'],'condition_chi':u['chi_cond'],'inv_chi0':u['inv_chi0'].tolist(),'inv_chi':u['inv_chi'].tolist(),'U':u['U'].tolist(),'inversion_residuals':{'chi0_left':u['chi0_left_residual'],'chi0_right':u['chi0_right_residual'],'chi_left':u['chi_left_residual'],'chi_right':u['chi_right_residual']}}
Path('nio_u_result.json').write_text(json.dumps(result,indent=2)); print(json.dumps(result,indent=2))
