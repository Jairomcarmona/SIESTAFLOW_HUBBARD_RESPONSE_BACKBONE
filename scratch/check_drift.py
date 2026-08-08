import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'src'))
from siestaflow_hubbard.siesta_backend.event_parser import parse_population_events
from siestaflow_hubbard.siesta_backend.observation_selector import Siesta542BarePolicyV1

def check_drift(file_path):
    events = parse_population_events(file_path)
    ref = Siesta542BarePolicyV1.get_reference_observation(events)
    bare = Siesta542BarePolicyV1.get_bare_observation(events)
    
    n_ref = float(ref.context.split()[3]) # naive extraction just for this script if needed, wait no, we need to extract from atoms or just the whole trace.
    
    # Actually, event_parser yields HubbardPopulationEvent. We can find the population of atom 1.
    def get_pop(event, atom_idx=1):
        for a in event.atoms:
            if a.atom_index == atom_idx:
                return a.trace_total
        return 0.0
        
    n_ref_val = get_pop(ref)
    n_bare_val = get_pop(bare)
    
    print(f"File: {os.path.basename(file_path)}")
    print(f"n_ref: {n_ref_val:.6f}")
    print(f"n_bare: {n_bare_val:.6f}")
    print(f"Drift: {abs(n_ref_val - n_bare_val):.6f}")

check_drift("scratch/phase4_val/MnO_val_+0.00_BARE.out")
check_drift("scratch/phase4_val/MnO_val_+0.01_BARE.out")
check_drift("scratch/phase4_val/MnO_val_-0.01_BARE.out")
check_drift("scratch/phase4_val/MnO_val_+0.02_BARE.out")
check_drift("scratch/phase4_val/MnO_val_-0.02_BARE.out")
