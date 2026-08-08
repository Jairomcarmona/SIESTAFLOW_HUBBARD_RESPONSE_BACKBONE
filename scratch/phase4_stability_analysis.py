import sys
import os
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
from siestaflow_hubbard.siesta_backend.event_parser import parse_hubbard_population_events
from siestaflow_hubbard.siesta_backend.observation_selector import Siesta542BarePolicyV1, ObservationContext

def get_trace(filepath, mode, alpha):
    with open(filepath, 'r', encoding='utf-8') as f:
        log = f.read()
    events = parse_hubbard_population_events(log)
    
    # We must provide context, let's mock a valid context
    context = ObservationContext(
        siesta_version="5.4.2",
        calculation_mode="BARE" if mode == "BARE" else "SCREENED",
        reference_dm_sha256="mock",
        projector_fingerprint="mock",
        scf_mix_target="density",
        scf_mixer_method="Linear",
        scf_mixer_weight=1.0,
        max_scf_iterations=2 if mode == "BARE" else 50,
        convergence_confirmed=True,
        final_scf_iteration=max([e.scf_iteration for e in events if e.scf_iteration is not None], default=1) if events else 1,
        post_scf_population_occurrence=None
    )
    
    if mode == 'BARE':
        try:
            sel = Siesta542BarePolicyV1.get_bare_observation(events, context)
            val = sel.event.atoms[0].trace_total
        except Exception as e:
            print(f"BARE exception: {e}")
            val = np.nan
        
        try:
            ref = Siesta542BarePolicyV1.get_reference_observation(events, context)
            ref_val = ref.event.atoms[0].trace_total
        except Exception as e:
            print(f"REF exception: {e}")
            ref_val = np.nan
            
        return val, ref_val
    else:
        try:
            sel = Siesta542BarePolicyV1.get_screened_observation(events, context)
            val = sel.event.atoms[0].trace_total
        except Exception as e:
            print(f"SCREENED exception: {e}")
            val = np.nan
        return val, np.nan

def analyze_window(alphas, pops):
    x = np.array(alphas)
    y = np.array(pops)
    mask = ~np.isnan(y)
    x = x[mask]
    y = y[mask]
    if len(x) < 2:
        return np.nan, np.nan
    A = np.vstack([x, np.ones(len(x))]).T
    m, c = np.linalg.lstsq(A, y, rcond=None)[0]
    return m, c

def main():
    alphas = [-0.02, -0.01, 0.00, 0.01, 0.02]
    work_dir = os.path.join(os.path.dirname(__file__), 'phase4_val')
    
    bare_pops = []
    bare_refs = []
    scr_pops = []
    
    for a in alphas:
        bare_file = os.path.join(work_dir, f"MnO_val_{a:+.2f}_BARE.out")
        scr_file = os.path.join(work_dir, f"MnO_val_{a:+.2f}_SCR.out")
        
        b_val, ref_val = get_trace(bare_file, 'BARE', a)
        s_val, _ = get_trace(scr_file, 'SCREENED', a)
        
        bare_pops.append(b_val)
        bare_refs.append(ref_val)
        scr_pops.append(s_val)
        
    print("ALPHAS:", alphas)
    print("BARE:", bare_pops)
    print("SCREENED:", scr_pops)
    
    # Inner window: [-0.01, 0, 0.01]
    inner_indices = [1, 2, 3]
    inner_alphas = [alphas[i] for i in inner_indices]
    inner_bare_pops = [bare_pops[i] for i in inner_indices]
    inner_scr_pops = [scr_pops[i] for i in inner_indices]
    
    bare_full_m, bare_full_c = analyze_window(alphas, bare_pops)
    bare_in_m, bare_in_c = analyze_window(inner_alphas, inner_bare_pops)
    
    scr_full_m, scr_full_c = analyze_window(alphas, scr_pops)
    scr_in_m, scr_in_c = analyze_window(inner_alphas, inner_scr_pops)
    
    # Left and right secants
    left_sec_bare = (bare_pops[2] - bare_pops[0]) / (alphas[2] - alphas[0])
    right_sec_bare = (bare_pops[4] - bare_pops[2]) / (alphas[4] - alphas[2])
    asym_bare = abs(right_sec_bare - left_sec_bare)
    
    left_sec_scr = (scr_pops[2] - scr_pops[0]) / (alphas[2] - alphas[0])
    right_sec_scr = (scr_pops[4] - scr_pops[2]) / (alphas[4] - alphas[2])
    asym_scr = abs(right_sec_scr - left_sec_scr)
    
    print("\n--- BARE ---")
    print(f"Full OLS slope: {bare_full_m:.4f}, intercept: {bare_full_c:.6f}")
    print(f"Inner OLS slope: {bare_in_m:.4f}, intercept: {bare_in_c:.6f}")
    print(f"Slope diff: {abs(bare_full_m - bare_in_m):.4f}")
    print(f"Rel diff: {abs(bare_full_m - bare_in_m)/abs(bare_full_m)*100:.2f}%")
    print(f"Left secant: {left_sec_bare:.4f}")
    print(f"Right secant: {right_sec_bare:.4f}")
    print(f"Asymmetry: {asym_bare:.4f}")
    
    print("\n--- SCREENED ---")
    print(f"Full OLS slope: {scr_full_m:.4f}, intercept: {scr_full_c:.6f}")
    print(f"Inner OLS slope: {scr_in_m:.4f}, intercept: {scr_in_c:.6f}")
    print(f"Slope diff: {abs(scr_full_m - scr_in_m):.4f}")
    print(f"Rel diff: {abs(scr_full_m - scr_in_m)/abs(scr_full_m)*100:.2f}%")
    print(f"Left secant: {left_sec_scr:.4f}")
    print(f"Right secant: {right_sec_scr:.4f}")
    print(f"Asymmetry: {asym_scr:.4f}")
    
    print("\n--- RESTART DRIFT ---")
    # from previous outputs or phase4 json, n_ref was about 5.380190
    n_ref = bare_refs[2]
    n0_0 = bare_pops[2]
    n_0 = scr_pops[2]
    print(f"n_ref(alpha=0) = {n_ref:.6f}")
    print(f"BARE n0(alpha=0) = {n0_0:.6f}")
    print(f"SCR n(alpha=0) = {n_0:.6f}")
    print(f"Restart drift (BARE) = {abs(n_ref - n0_0):.6f}")
    
if __name__ == "__main__":
    main()
