import os
import sys
import shutil
import numpy as np

# Ensure sys.path includes ../../src and repository root
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.abspath(os.path.join(current_dir, "..", "..", "src"))
repo_dir = os.path.abspath(os.path.join(current_dir, "..", ".."))

if src_dir not in sys.path:
    sys.path.insert(0, src_dir)
if repo_dir not in sys.path:
    sys.path.insert(0, repo_dir)

from src.siestaflow_hubbard.siesta_backend.adapter import SiestaLRAdapter
from src.siestaflow_hubbard.siesta_backend.fdf_builder import FdfBuilder
from siestaflow_hubbard.synthetic_backend.fit_engine import FitEngine, assemble_slope_matrix
from siestaflow_hubbard.domain.cardinals import Cardinals
from siestaflow_hubbard.domain.alpha_grid import AlphaGrid
from siestaflow_hubbard.domain.matrix_pipeline import assemble_raw, invert_chi


def prepare_cu3n_workspace():
    # We must split Cu into Cu1 (perturbed) and Cu2 (spectator) to get the intra-site U.
    # The pseudo-potentials must be named Cu1.psml and Cu2.psml
    psml_dir = os.path.expanduser("~\\Downloads\\nc-sr-05_pbe_standard_psml\\nc-sr-05_pbe_standard_psml")
    
    if os.path.exists(os.path.join(psml_dir, "Cu.psml")):
        shutil.copy(os.path.join(psml_dir, "Cu.psml"), os.path.join(current_dir, "Cu1.psml"))
        shutil.copy(os.path.join(psml_dir, "Cu.psml"), os.path.join(current_dir, "Cu2.psml"))
    
    if os.path.exists(os.path.join(psml_dir, "N.psml")):
        shutil.copy(os.path.join(psml_dir, "N.psml"), os.path.join(current_dir, "N.psml"))

    fdf_content = """SystemName          Cu3N
SystemLabel         cu3n

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
MeshCutoff          300.0 Ry

%block kgrid_Monkhorst_Pack
 2 0 0 0.0
 0 2 0 0.0
 0 0 2 0.0
%endblock kgrid_Monkhorst_Pack

MaxSCFIterations    100
DM.MixingWeight     0.10
DM.Tolerance        1.d-4
DM.NumberPulay      4

Spin                non-polarized

SaveRho             F
SaveDeltaRho        F
SaveHS              F
"""
    with open(os.path.join(current_dir, "Cu3N_ref.fdf"), "w") as f:
        f.write(fdf_content)


def run_cu3n_campaign():
    print("=" * 70)
    print("SIESTAFLOW HUBBARD RESPONSE - Cu3N (Anti-ReO3) CAMPAIGN")
    print("Goal: Extract intra-site U for Cu(I) d^10 configuration")
    print("=" * 70)

    os.chdir(current_dir)
    cwd = current_dir

    prepare_cu3n_workspace()

    system = "Cu3N"
    tm_symbol = "Cu1"  # Perturbed species
    # Cu1 is atom index 2 in the coordinates block (1-indexed: 1=N, 2=Cu1, 3=Cu2, 4=Cu2)
    target_atom_idx = 2

    alpha_grid_vals = [-0.02, -0.01, 0.00, 0.01, 0.02]
    n_procs = 4

    adapter = SiestaLRAdapter()
    fdf_builder = FdfBuilder()

    ref_template = f"{system}_ref.fdf"
    ref_fdf = f"{system}_ref_run.fdf"
    ref_out = f"{system}_ref.out"

    # 1. Reference Calculation
    print(f"\n[{system} - FASE 1] Running Reference State (alpha=0.00 eV)...")
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

    if not os.path.exists(f"{system}_ref.DM"):
        if os.path.exists(f"{system}_ref_run.DM"):
            shutil.copy(f"{system}_ref_run.DM", f"{system}_ref.DM")
        else:
            raise RuntimeError(f"Reference DM file {system}_ref.DM was not generated!")

    print(f"  -> {system} Reference State successfully calculated.")

    system_records = []

    # 2. SCREENED Perturbations
    print(f"\n[{system} - FASE 2] Running SCREENED Perturbations...")
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

        shutil.copy(f"{system}_ref.DM", f"{run_name}.DM")

        print(f"  -> {system} SCREENED alpha = {alpha:+.2f} eV...")
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
    print(f"\n[{system} - FASE 3] Running BARE Perturbations...")
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

        shutil.copy(f"{system}_ref.DM", f"{run_name}.DM")

        print(f"  -> {system} BARE alpha = {alpha:+.2f} eV...")
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

    # 4. Results
    print(f"\n[{system} - FASE 4] OLS Linear Regression...")
    alpha_grid = AlphaGrid(
        alpha_values_ev=alpha_grid_vals,
        K_p=5,
        symmetric_pairs=True,
        k_negative=2,
        k_zero=1,
        k_positive=2
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
    print("Cu3N HUBBARD U LINEAR RESPONSE - FINAL VERDICT")
    print("=" * 80)
    print(f"  SCREENED fit: dn/dalpha = {R_scr[0, 0]:.6f} 1/eV, R^2 = {scr_recs[0].r_squared:.6f}")
    print(f"  BARE     fit: dn0/dalpha = {R_bare[0, 0]:.6f} 1/eV, R^2 = {bare_recs[0].r_squared:.6f}")
    print(f"  chi_0 (BARE)     = {chi_bare[0, 0]:.6f} 1/eV")
    print(f"  chi   (SCREENED) = {chi_scr[0, 0]:.6f} 1/eV")
    print(f"  U_effective      = {u_val:.4f} eV")
    print("=" * 80)

if __name__ == "__main__":
    run_cu3n_campaign()
