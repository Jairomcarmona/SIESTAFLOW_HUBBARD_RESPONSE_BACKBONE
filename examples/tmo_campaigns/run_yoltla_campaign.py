import os
import sys
import shutil
import numpy as np

# Ensure sys.path includes src and repo root
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.abspath(os.path.join(current_dir, "..", "..", "src"))
repo_dir = os.path.abspath(os.path.join(current_dir, "..", ".."))

if src_dir not in sys.path:
    sys.path.insert(0, src_dir)
if repo_dir not in sys.path:
    sys.path.insert(0, repo_dir)

from siestaflow_hubbard.siesta_backend.adapter import SiestaLRAdapter
from siestaflow_hubbard.siesta_backend.fdf_builder import FdfBuilder
from siestaflow_hubbard.synthetic_backend.fit_engine import FitEngine, assemble_slope_matrix
from siestaflow_hubbard.domain.cardinals import Cardinals
from siestaflow_hubbard.domain.alpha_grid import AlphaGrid
from siestaflow_hubbard.domain.matrix_pipeline import assemble_raw, invert_chi


def prepare_yoltla_cu3n_workspace(siesta_bin: str = "siesta"):
    """Prepares the Cu3N production workspace for Yoltla cluster execution."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Generate FDF with Production Grid (8x8x8) and 500 Ry Cutoff
    fdf_content = """SystemName          Cu3N_Yoltla_Production
SystemLabel         cu3n_yoltla

NumberOfAtoms       4
NumberOfSpecies     3

%block ChemicalSpeciesLabel
 1  29  Cu1
 2  29  Cu2
 3   7  N
%endblock ChemicalSpeciesLabel

LatticeConstant     3.81 Ang
%block LatticeVectors
 1.0  0.0  0.0
 0.0  1.0  0.0
 0.0  0.0  1.0
%endblock LatticeVectors

AtomicCoordinatesFormat Fractional
%block AtomicCoordinatesAndAtomicSpecies
 0.0  0.0  0.0  3
 0.5  0.0  0.0  1
 0.0  0.5  0.0  2
 0.0  0.0  0.5  2
%endblock AtomicCoordinatesAndAtomicSpecies

PAO.BasisSize       DZP
MeshCutoff          500.0 Ry

%block kgrid_Monkhorst_Pack
 8 0 0 0.0
 0 8 0 0.0
 0 0 8 0.0
%endblock kgrid_Monkhorst_Pack

MaxSCFIterations    150
DM.MixingWeight     0.05
DM.Tolerance        1.d-6
DM.NumberPulay      5

Spin                non-polarized

SaveRho             F
SaveDeltaRho        F
SaveHS              F
"""
    ref_path = os.path.join(current_dir, "Cu3N_yoltla_ref.fdf")
    with open(ref_path, "w", newline="\n") as f:
        f.write(fdf_content)
    return ref_path


def run_yoltla_cu3n_campaign(siesta_bin: str = "siesta", n_procs: int = 16):
    print("=" * 80)
    print("SIESTAFLOW HUBBARD RESPONSE — YOLTLA HPC CLUSTER PRODUCTION CAMPAIGN")
    print("Target: Cu3N (Anti-ReO3) | K-grid: 8x8x8 | MeshCutoff: 500 Ry | Basis: DZP")
    print("=" * 80)

    cwd = current_dir
    ref_template = prepare_yoltla_cu3n_workspace(siesta_bin)

    system = "Cu3N_Yoltla"
    tm_symbol = "Cu1"
    target_atom_idx = 2

    # Positive-only alpha grid for d^10 filled shell linear response
    alpha_grid_vals = [0.00, 0.01, 0.02, 0.03, 0.04]

    adapter = SiestaLRAdapter(wsl_siesta_path=siesta_bin)
    fdf_builder = FdfBuilder()

    ref_fdf = f"{system}_ref_run.fdf"
    ref_out = f"{system}_ref.out"

    # 1. Reference State
    print(f"\n[{system}] 1. Calculating Reference State (alpha = 0.00 eV)...")
    base_proj = {
        "species": tm_symbol,
        "num_shells": 1,
        "n": 3,
        "l": 2,
        "rc": 1.76,
        "width": 0.1,
        "u_val": 0.0,
        "j_val": 0.0
    }
    
    ref_proj = [dict(base_proj, alpha=0.0000)]
    fdf_builder.prepare_fdf_screened(
        base_fdf_path=ref_template,
        target_fdf_path=ref_fdf,
        alpha=0.0000,
        run_name=f"{system}_ref",
        projections=ref_proj
    )

    adapter.run_siesta_slurm(ref_fdf, ref_out, cwd, n_procs=n_procs)

    if os.path.exists(f"{system}_ref_run.DM") and not os.path.exists(f"{system}_ref.DM"):
        shutil.copy(f"{system}_ref_run.DM", f"{system}_ref.DM")

    print(f"  -> Reference State successfully calculated on Yoltla.")

    system_records = []

    # 2. SCREENED Perturbations
    print(f"\n[{system}] 2. Running SCREENED Perturbations...")
    for alpha in alpha_grid_vals:
        run_name = f"{system}_SCR_{alpha:+.2f}"
        fdf_path = f"{run_name}.fdf"
        out_path = f"{run_name}.out"

        proj = [dict(base_proj, alpha=alpha)]
        fdf_builder.prepare_fdf_screened(
            base_fdf_path=ref_template,
            target_fdf_path=fdf_path,
            alpha=alpha,
            run_name=run_name,
            projections=proj
        )

        if os.path.exists(f"{system}_ref.DM"):
            shutil.copy(f"{system}_ref.DM", f"{run_name}.DM")

        print(f"  -> SCREENED alpha = {alpha:+.2f} eV...")
        adapter.run_siesta_slurm(fdf_path, out_path, cwd, n_procs=n_procs)

        recs = adapter.extract_occupations(
            out_path,
            response_mode="SCREENED",
            alpha=alpha,
            target_atom_idx=target_atom_idx
        )
        system_records.extend(recs)
        if recs:
            print(f"     Occup (Cu1 3d) = {recs[0].occupation:.6f}")

    # 3. BARE Perturbations
    print(f"\n[{system}] 3. Running BARE Perturbations...")
    for alpha in alpha_grid_vals:
        run_name = f"{system}_BARE_{alpha:+.2f}"
        fdf_path = f"{run_name}.fdf"
        out_path = f"{run_name}.out"

        proj = [dict(base_proj, alpha=alpha)]
        fdf_builder.prepare_fdf_bare(
            base_fdf_path=ref_template,
            target_fdf_path=fdf_path,
            alpha=alpha,
            run_name=run_name,
            projections=proj
        )

        if os.path.exists(f"{system}_ref.DM"):
            shutil.copy(f"{system}_ref.DM", f"{run_name}.DM")

        print(f"  -> BARE alpha = {alpha:+.2f} eV...")
        adapter.run_siesta_slurm(fdf_path, out_path, cwd, n_procs=n_procs)

        recs = adapter.extract_occupations(
            out_path,
            response_mode="BARE",
            alpha=alpha,
            target_atom_idx=target_atom_idx
        )
        system_records.extend(recs)
        if recs:
            print(f"     Occup (Cu1 3d) = {recs[0].occupation:.6f}")

    # 4. Results Processing
    print(f"\n[{system}] 4. OLS Linear Regression & U Extraction...")
    alpha_grid = AlphaGrid(
        alpha_values_ev=alpha_grid_vals,
        K_p=5,
        symmetric_pairs=False,
        k_negative=0,
        k_zero=1,
        k_positive=4
    )
    cardinals = Cardinals(
        P=1, O=1, N=1,
        alpha_grids={f"{tm_symbol}_site_{target_atom_idx}": alpha_grid},
        A=np.array([[1.0]])
    )

    engine = FitEngine()
    scr_recs = engine.fit_slopes(system_records, cardinals, response_mode='SCREENED')
    R_scr = assemble_slope_matrix(scr_recs, cardinals)
    chi_scr = assemble_raw(R_scr, cardinals.A)

    bare_recs = engine.fit_slopes(system_records, cardinals, response_mode='BARE')
    R_bare = assemble_slope_matrix(bare_recs, cardinals)
    chi_bare = assemble_raw(R_bare, cardinals.A)

    inv_chi_scr = invert_chi(chi_scr)
    inv_chi_bare = invert_chi(chi_bare)

    U_eff = inv_chi_bare - inv_chi_scr
    u_val = float(U_eff[0, 0])

    print("\n" + "=" * 80)
    print("YOLTLA CLUSTER — Cu3N HUBBARD U PRODUCTION VERDICT")
    print("=" * 80)
    print(f"  SCREENED fit: dn/dalpha = {R_scr[0, 0]:.6f} 1/eV, R^2 = {scr_recs[0].r_squared:.6f}")
    print(f"  BARE     fit: dn0/dalpha = {R_bare[0, 0]:.6f} 1/eV, R^2 = {bare_recs[0].r_squared:.6f}")
    print(f"  chi_0 (BARE)     = {chi_bare[0, 0]:.6f} 1/eV")
    print(f"  chi   (SCREENED) = {chi_scr[0, 0]:.6f} 1/eV")
    print(f"  U_effective      = {u_val:.4f} eV")
    print("=" * 80)


if __name__ == "__main__":
    siesta_bin = sys.argv[1] if len(sys.argv) > 1 else "siesta"
    n_procs = int(sys.argv[2]) if len(sys.argv) > 2 else int(os.environ.get("SLURM_NTASKS", 64))
    run_yoltla_cu3n_campaign(siesta_bin=siesta_bin, n_procs=n_procs)
