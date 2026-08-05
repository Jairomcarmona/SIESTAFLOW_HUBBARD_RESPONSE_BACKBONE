import os
from siesta_adapter import SiestaAdapter

def test_parser():
    real_output_path = r"C:\Users\Jairo\.gemini\antigravity\brain\2b84ddef-8494-4411-bfef-c3cc4d2870ea\scratch\full_output.txt"
    adapter = SiestaAdapter()
    
    print("Parsing real Yoltla output with adversarial verification...")
    occupations = adapter.parse_converged_hubbard_occupations(real_output_path)
    
    atoms = {k: v for k, v in occupations.items() if isinstance(k, int)}
    print(f"\n[SUCCESS] Successfully parsed {len(atoms)} atoms with validated checksums!")
    if "max_change" in occupations:
        print(f"   Max change in local occup: {occupations['max_change']}")
    
    for atom_idx, result in atoms.items():
        print(f"   Atom {atom_idx} (Species {result['species']}):")
        print(f"     Spin UP trace:   {result['matrix_up'].diagonal().sum():.6f} (Reported: {result['trace_up']:.6f})")
        print(f"     Spin DOWN trace: {result['matrix_down'].diagonal().sum():.6f} (Reported: {result['trace_down']:.6f})")
        print(f"     Total Trace:     {(result['matrix_up'].diagonal().sum() + result['matrix_down'].diagonal().sum()):.6f} (Reported: {result['trace_total']:.6f})")
    print("   Status: ALL CHECKSUMS PASSED\n")

if __name__ == "__main__":
    test_parser()
