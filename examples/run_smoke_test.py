import os
from siesta_adapter import SiestaAdapter

def main():
    base_fdf = "MnO_smoke_test.fdf"
    alpha_grid = [-0.1, 0.0, 0.1]
    
    adapter = SiestaAdapter(wsl_siesta_path="/home/jmc/.local/siesta-5.4.2-serial/bin/siesta")
    cwd = os.getcwd()
    
    print("Starting SIESTAFLOW SiestaAdapter Smoke Test...")
    print(f"Base FDF: {base_fdf}")
    print(f"Alpha grid: {alpha_grid}")
    
    results = {}
    
    for alpha in alpha_grid:
        print(f"\n--- Running alpha = {alpha} ---")
        run_name = f"MnO_smoke_{alpha:.2f}"
        fdf_path = f"{run_name}.fdf"
        out_path = f"{run_name}.out"
        
        # 1. Prepare FDF
        print(f"Preparing {fdf_path}...")
        adapter.prepare_fdf(base_fdf, alpha, fdf_path)
        
        # 2. Run SIESTA using SLURM
        print(f"Submitting job to local SLURM (4 processors) -> {out_path} ...")
        adapter.run_siesta_slurm(fdf_path, out_path, cwd, n_procs=4)
        
        # 3. Parse output
        print("Parsing output with adversarial checks...")
        try:
            parsed = adapter.parse_converged_hubbard_occupations(out_path)
            results[alpha] = parsed
            print("  [SUCCESS] Extraction passed all adversarial checksums!")
            print(f"  Total Traces -> UP: {parsed['trace_up']:.4f}, DOWN: {parsed['trace_down']:.4f}")
        except Exception as e:
            print(f"  [FAILED] {type(e).__name__}: {str(e)}")
            return
            
    print("\nSmoke test complete. The SiestaAdapter is successfully integrated with SIESTA 5.4.2 in WSL.")
    
if __name__ == "__main__":
    main()
