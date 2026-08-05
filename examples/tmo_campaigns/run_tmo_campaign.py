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

# Imports from backbone
from src.siestaflow_hubbard.siesta_backend.adapter import SiestaLRAdapter
from src.siestaflow_hubbard.siesta_backend.fdf_builder import FdfBuilder
from siestaflow_hubbard.synthetic_backend.fit_engine import fit_slopes, assemble_slope_matrix
from siestaflow_hubbard.synthetic_backend.population_generator import OccupationRecord
from siestaflow_hubbard.domain.cardinals import Cardinals
from siestaflow_hubbard.domain.alpha_grid import AlphaGrid
from siestaflow_hubbard.domain.matrix_pipeline import assemble_raw, invert_chi


def run_tmo_campaign():
    print("=" * 70)
    print("SIESTAFLOW HUBBARD RESPONSE - TRANSITION METAL OXIDES (TMO) CAMPAIGN")
    print("Systems: FeO, CoO, NiO")
    print("=" * 70)

    # Change directory to campaign workspace
    os.chdir(current_dir)
    cwd = current_dir

    tmo_systems = {
        'FeO': {'species': 'Fe'},
        'CoO': {'species': 'Co'},
        'NiO': {'species': 'Ni'}
    }

    alpha_grid_vals = [-0.02, -0.01, 0.00, 0.01, 0.02]
    n_procs = 4

    adapter = SiestaLRAdapter()
    fdf_builder = FdfBuilder()

    campaign_summary = {}

    for system, config in tmo_systems.items():
        tm_symbol = config['species']
        print("\n" + "#" * 70)
        print(f"  STARTING CAMPAIGN FOR SYSTEM: {system} (Species: {tm_symbol})")
        print("#" * 70)

        ref_template = f"{system}_ref.fdf"
        ref_fdf = f"{system}_ref_run.fdf"
        ref_out = f"{system}_ref.out"

        # 1. Reference Calculation (alpha = 0.0)
        print(f"\n[{system} - FASE 1] Running Reference State (alpha=0.00 eV)...")
        fdf_builder.prepare_fdf_screened(
            base_fdf_path=ref_template,
            target_fdf_path=ref_fdf,
            alpha=0.0000,
            run_name=f"{system}_ref",
            species=tm_symbol
        )

        adapter.run_siesta_slurm(ref_fdf, ref_out, cwd, n_procs=n_procs)

        # Ensure reference DM exists
        if not os.path.exists(f"{system}_ref.DM"):
            if os.path.exists(f"{system}_ref_run.DM"):
                shutil.copy(f"{system}_ref_run.DM", f"{system}_ref.DM")
            else:
                raise RuntimeError(f"Reference DM file {system}_ref.DM was not generated!")

        print(f"  -> {system} Reference State successfully calculated.")

        system_records = []

        # 2. SCREENED Perturbations
        print(f"\n[{system} - FASE 2] Running SCREENED Perturbations (alpha grid: {alpha_grid_vals})...")
        for alpha in alpha_grid_vals:
            run_name = f"{system}_SCR_{alpha:+.2f}"
            fdf_path = f"{run_name}.fdf"
            out_path = f"{run_name}.out"

            fdf_builder.prepare_fdf_screened(
                base_fdf_path=ref_template,
                target_fdf_path=fdf_path,
                alpha=alpha,
                run_name=run_name,
                species=tm_symbol
            )

            # Copy reference DM for no-chaining policy
            shutil.copy(f"{system}_ref.DM", f"{run_name}.DM")

            print(f"  -> {system} SCREENED alpha = {alpha:+.2f} eV...")
            adapter.run_siesta_slurm(fdf_path, out_path, cwd, n_procs=n_procs)

            recs = adapter.extract_occupations(
                out_path,
                response_mode="SCREENED",
                alpha=alpha,
                target_atom_idx=1
            )
            system_records.extend(recs)
            if recs:
                print(f"     Occup (d-total) = {recs[0].occupation:.6f}")

        # 3. BARE Perturbations
        print(f"\n[{system} - FASE 3] Running BARE Perturbations (alpha grid: {alpha_grid_vals})...")
        for alpha in alpha_grid_vals:
            run_name = f"{system}_BARE_{alpha:+.2f}"
            fdf_path = f"{run_name}.fdf"
            out_path = f"{run_name}.out"

            fdf_builder.prepare_fdf_bare(
                base_fdf_path=ref_template,
                target_fdf_path=fdf_path,
                alpha=alpha,
                run_name=run_name,
                species=tm_symbol
            )

            # Copy reference DM for no-chaining policy
            shutil.copy(f"{system}_ref.DM", f"{run_name}.DM")

            print(f"  -> {system} BARE alpha = {alpha:+.2f} eV...")
            adapter.run_siesta_slurm(fdf_path, out_path, cwd, n_procs=n_procs)

            recs = adapter.extract_occupations(
                out_path,
                response_mode="BARE",
                alpha=alpha,
                target_atom_idx=1
            )
            system_records.extend(recs)
            if recs:
                print(f"     Occup (d-total) = {recs[0].occupation:.6f}")

        # 4. OLS Fit & Response Matrix Assembly
        print(f"\n[{system} - FASE 4] OLS Linear Regression & Response Matrix Inversion...")
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
            alpha_grids={f"{tm_symbol}_site_1": alpha_grid},
            A=np.array([[1.0]])
        )

        scr_recs = fit_slopes(system_records, cardinals, response_mode='SCREENED')
        R_scr = assemble_slope_matrix(scr_recs, cardinals)
        chi_scr = assemble_raw(R_scr, cardinals.A)

        bare_recs = fit_slopes(system_records, cardinals, response_mode='BARE')
        R_bare = assemble_slope_matrix(bare_recs, cardinals)
        chi_bare = assemble_raw(R_bare, cardinals.A)

        inv_chi_scr = invert_chi(chi_scr)
        inv_chi_bare = invert_chi(chi_bare)

        U_eff = inv_chi_bare - inv_chi_scr
        u_val = float(U_eff[0, 0])

        r2_scr = scr_recs[0].r_squared
        r2_bare = bare_recs[0].r_squared

        slope_scr = R_scr[0, 0]
        slope_bare = R_bare[0, 0]

        campaign_summary[system] = {
            'tm_symbol': tm_symbol,
            'slope_scr': slope_scr,
            'slope_bare': slope_bare,
            'chi_scr': float(chi_scr[0, 0]),
            'chi_bare': float(chi_bare[0, 0]),
            'r2_scr': r2_scr,
            'r2_bare': r2_bare,
            'U_eff': u_val,
            'gate_u': "PASSED" if u_val > 0 else "REJECTED",
            'gate_r2': "PASSED" if (r2_scr >= 0.95 and r2_bare >= 0.95) else "WARNING"
        }

        print(f"  SCREENED fit: dn/dalpha = {slope_scr:.6f} 1/eV, R^2 = {r2_scr:.6f}")
        print(f"  BARE     fit: dn0/dalpha = {slope_bare:.6f} 1/eV, R^2 = {r2_bare:.6f}")
        print(f"  chi_0 (BARE)     = {chi_bare[0, 0]:.6f} 1/eV")
        print(f"  chi   (SCREENED) = {chi_scr[0, 0]:.6f} 1/eV")
        print(f"  U_effective      = {u_val:.4f} eV")

    # Overall Summary Table
    print("\n" + "=" * 80)
    print("TMO HUBBARD U LINEAR RESPONSE CAMPAIGN - FINAL VERDICT")
    print("=" * 80)
    print(f"{'System':<8} | {'TM':<4} | {'chi_bare (1/eV)':<15} | {'chi_scr (1/eV)':<15} | {'R^2 (SCR)':<10} | {'R^2 (BARE)':<10} | {'U_eff (eV)':<10} | {'Gate':<8}")
    print("-" * 80)
    for sys_name, res in campaign_summary.items():
        print(f"{sys_name:<8} | {res['tm_symbol']:<4} | {res['chi_bare']:<15.6f} | {res['chi_scr']:<15.6f} | {res['r2_scr']:<10.6f} | {res['r2_bare']:<10.6f} | {res['U_eff']:<10.4f} | {res['gate_u']:<8}")
    print("=" * 80)


if __name__ == "__main__":
    run_tmo_campaign()
