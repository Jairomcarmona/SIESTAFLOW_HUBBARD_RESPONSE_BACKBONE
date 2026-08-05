import os
import sys
import shutil
import numpy as np
from typing import List, Dict

# Agregar src/ al PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from siesta_adapter import SiestaAdapter
from siestaflow_hubbard.synthetic_backend.fit_engine import fit_slopes, assemble_slope_matrix
from siestaflow_hubbard.synthetic_backend.population_generator import OccupationRecord
from siestaflow_hubbard.domain.cardinals import Cardinals
from siestaflow_hubbard.domain.alpha_grid import AlphaGrid
from siestaflow_hubbard.domain.matrix_pipeline import assemble_raw, invert_chi

def prepare_fdf_bare(base_fdf: str, alpha: float, target_fdf: str, run_name: str):
    """
    Prepara un FDF en modo BARE (1 iteración SCF, usa DM de referencia)
    """
    with open(base_fdf, 'r') as f:
        content = f.read()

    # Reemplazar SystemLabel
    content = content.replace("SystemLabel         MnO_smoke", f"SystemLabel         {run_name}")

    alpha_block = f"""
%block DFTU.proj
  Mn   1
  3  2
  {alpha:.4f}  0.0000
  0.0000
%endblock DFTU.proj
"""
    content += alpha_block

    # Forzar BARE Response (Frozen potential / 1st iteration)
    # Reemplazar iteraciones y peso de mezcla para que imprima el resultado de la 1ra iteración en la 2da
    content = content.replace("MaxSCFIterations    50", "MaxSCFIterations    2")
    content = content.replace("DM.MixingWeight     0.1", "DM.MixingWeight     1.0")
    
    content += "\n# --- BARE RESPONSE OVERRIDES ---\n"
    content += "DM.UseSaveDM true\n"

    with open(target_fdf, 'w') as f:
        f.write(content)

def prepare_fdf_screened(base_fdf: str, alpha: float, target_fdf: str, run_name: str):
    """
    Prepara un FDF en modo SCREENED (SCF completo, usa DM de referencia como guess)
    """
    with open(base_fdf, 'r') as f:
        content = f.read()

    # Reemplazar SystemLabel
    content = content.replace("SystemLabel         MnO_smoke", f"SystemLabel         {run_name}")

    alpha_block = f"""
%block DFTU.proj
  Mn   1
  3  2
  {alpha:.4f}  0.0000
  0.0000
%endblock DFTU.proj
"""
    content += alpha_block

    # Usar DM de referencia como guess (no-chaining policy)
    content += "\n# --- SCREENED RESPONSE OVERRIDES ---\n"
    content += "DM.UseSaveDM true\n"

    with open(target_fdf, 'w') as f:
        f.write(content)

def extract_occupations(adapter: SiestaAdapter, out_path: str, response_mode: str, alpha: float) -> List[OccupationRecord]:
    parsed = adapter.parse_converged_hubbard_occupations(out_path)
    
    # Filtrar solo átomos que sean del target (Mn, especie 1).
    # Como el adaptador devuelve atoms por indice 1..N
    records = []
    # Usaremos el "trace_total" como observable por ahora, o la matriz. 
    # Para ser simples, el observable es la ocupación D total del átomo.
    # En MnO (celda primitiva) solo hay 1 átomo de Mn (indice 1).
    atom_idx = 1
    
    if atom_idx not in parsed:
        print(f"  WARNING: Atom {atom_idx} not found in parsed occupations for {out_path}")
        return []
        
    trace_total = parsed[atom_idx]['trace_total']
    
    # Asumimos que channel_index = 0, observable_index = 0 (P=1, O=1)
    record = OccupationRecord(
        response_mode=response_mode,
        channel_index=0,
        alpha_ev=alpha,
        observable_index=0,
        occupation=trace_total
    )
    records.append(record)
    return records


def main():
    print("=" * 60)
    print("SIESTAFLOW HUBBARD RESPONSE - BENCHMARK CAMPAIGN (MnO)")
    print("=" * 60)
    
    # 1. Configuración de la campaña
    base_fdf = "MnO_smoke_test.fdf"
    alpha_grid_vals = [-0.10, -0.05, 0.00, 0.05, 0.10]
    
    # P=1 (1 canal de perturbación: el átomo Mn), O=1 (1 observable: su ocupación total)
    # K_p=5 puntos. N=1 subespacio. A=[[1.0]]
    alpha_grid = AlphaGrid(alpha_grid_vals, 5, True, 2, 1, 2)
    cardinals = Cardinals(
        P=1, O=1, N=1,
        alpha_grids={"Mn_site_1": alpha_grid},
        A=np.array([[1.0]])
    )
    
    adapter = SiestaAdapter(wsl_siesta_path="/home/jmc/.local/siesta-5.4.2-serial/bin/siesta")
    cwd = os.getcwd()
    all_records = []
    
    print("\n[FASE 1] Ejecución del Estado de Referencia (alpha=0.0)")
    ref_fdf = "MnO_ref.fdf"
    ref_out = "MnO_ref.out"
    
    # Preparar el FDF de Referencia reemplazando el SystemLabel
    with open(base_fdf, 'r') as f:
        ref_content = f.read()
    ref_content = ref_content.replace("SystemLabel         MnO_smoke", "SystemLabel         MnO_ref")
    ref_content += "\nWriteDM true\n" # Para estar hiperseguros de que escribe el DM
    
    with open(ref_fdf, 'w') as f:
        f.write(ref_content)
        
    print("  -> Corriendo SIESTA Referencia...")
    adapter.run_siesta_slurm(ref_fdf, ref_out, cwd, n_procs=1)
    print("  -> Referencia completada.")
    
    # 2. Ejecución SCREENED
    print("\n[FASE 2] Perturbaciones SCREENED (Autoconsistentes)")
    for alpha in alpha_grid_vals:
        run_name = f"MnO_SCR_{alpha:+.2f}"
        fdf_path = f"{run_name}.fdf"
        out_path = f"{run_name}.out"
        
        prepare_fdf_screened(base_fdf, alpha, fdf_path, run_name)
        
        # Copiar DM de referencia (No-Chaining)
        shutil.copy("MnO_ref.DM", f"{run_name}.DM")
        
        print(f"  -> Corriendo alpha = {alpha:+.2f}...")
        adapter.run_siesta_slurm(fdf_path, out_path, cwd, n_procs=1)
        
        recs = extract_occupations(adapter, out_path, 'SCREENED', alpha)
        all_records.extend(recs)
        if recs: print(f"     n = {recs[0].occupation:.6f}")

    # 3. Ejecución BARE
    print("\n[FASE 3] Perturbaciones BARE (Primera Iteración / Frozen Potential)")
    for alpha in alpha_grid_vals:
        run_name = f"MnO_BARE_{alpha:+.2f}"
        fdf_path = f"{run_name}.fdf"
        out_path = f"{run_name}.out"
        
        prepare_fdf_bare(base_fdf, alpha, fdf_path, run_name)
        
        # Copiar DM de referencia (No-Chaining)
        shutil.copy("MnO_ref.DM", f"{run_name}.DM")
        
        print(f"  -> Corriendo alpha = {alpha:+.2f}...")
        adapter.run_siesta_slurm(fdf_path, out_path, cwd, n_procs=1)
        
        recs = extract_occupations(adapter, out_path, 'BARE', alpha)
        all_records.extend(recs)
        if recs: print(f"     n = {recs[0].occupation:.6f}")

    # 4. Ajuste de Regresión y Cálculo de U
    print("\n[FASE 4] Regresión Lineal y Ensamblaje de Susceptibilidad")
    
    # SCREENED
    scr_recs = fit_slopes(all_records, cardinals, 'SCREENED')
    R_scr = assemble_slope_matrix(scr_recs, cardinals)
    chi_scr = assemble_raw(R_scr, cardinals.A)
    
    # BARE
    bare_recs = fit_slopes(all_records, cardinals, 'BARE')
    R_bare = assemble_slope_matrix(bare_recs, cardinals)
    chi_bare = assemble_raw(R_bare, cardinals.A)
    
    print(f"\nResultados de Regresión Lineal:")
    print(f"  SCREENED: pendiente = {R_scr[0,0]:.4f} 1/eV, R^2 = {scr_recs[0].r_squared:.4f}")
    print(f"  BARE:     pendiente = {R_bare[0,0]:.4f} 1/eV, R^2 = {bare_recs[0].r_squared:.4f}")
    
    # Construcción de U
    inv_chi_scr = invert_chi(chi_scr)
    inv_chi_bare = invert_chi(chi_bare)
    
    U = inv_chi_bare - inv_chi_scr
    
    print("\n[VEREDICTO FINAL]")
    print("=" * 60)
    print(f"  chi_0 (BARE)     = {chi_bare[0,0]:.4f} 1/eV")
    print(f"  chi   (SCREENED) = {chi_scr[0,0]:.4f} 1/eV")
    print(f"  U_efectivo       = {U[0,0]:.4f} eV")
    print("=" * 60)
    
    if U[0,0] > 0:
        print("  GATE: U Diagonal > 0 -> [PASSED] (Físicamente Sensato)")
    else:
        print("  GATE: U Diagonal > 0 -> [REJECTED] (Física Negativa)")

if __name__ == "__main__":
    main()
