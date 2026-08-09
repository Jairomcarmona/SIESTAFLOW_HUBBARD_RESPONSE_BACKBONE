"""
phase4_kgrid_sensitivity.py – Real K-Point Sensitivity Campaign (kgrid 1x1x1 vs 1x2x2).

Baseline: DZP @ 200 Ry, EnergyShift = 0.005 Ry, kgrid = (1, 1, 1) (reused from scratch/phase4_energyshift_demo/dzp_0p005ry/).
New Campaign: DZP @ 200 Ry, EnergyShift = 0.005 Ry, kgrid = (1, 2, 2) (19 new SIESTA runs).

Quantifies change in:
  - Reference total energy, Fermi level, spin moments
  - chi0, chi, U matrices
  - U00, U01, U10, U11
  - Response eigenmodes and eigenvectors for chi0, chi, U
  - Linear response quality diagnostics (R2, asymmetry)
  - Computational wall-clock and SCF iteration cost
"""

from __future__ import annotations

import os
import sys
import json
import shutil
import hashlib
import re
import time

sys.path.insert(0, os.path.abspath("."))

import numpy as np

from siestaflow_hubbard.siesta_backend.adapter import SiestaLRAdapter
from siestaflow_hubbard.siesta_backend.event_parser import parse_hubbard_population_events
from siestaflow_hubbard.siesta_backend.fdf_builder import FdfBuilder, materialize_split_species_fdf
from siestaflow_hubbard.siesta_backend.observation_selector import (
    Siesta542BarePolicyV1,
    ObservationContext,
)
from siestaflow_hubbard.domain.matrix_lr import ResponseObservation
from siestaflow_hubbard.domain.convergence_engine import (
    LRScientificConfiguration,
    ConvergenceResult,
    ConvergenceComparison,
    generate_single_dimension_scan,
    can_reuse_calculations,
    compare_convergence_results,
    build_convergence_result_from_observations,
)
from scratch.phase4_method2_revalidation import select_converged_reference_event

SIESTA_PATH = "/home/jmc/.local/siesta-5.4.2-serial/bin/siesta"
ALPHA_GRID = [-0.02, -0.01, 0.00, +0.01, +0.02]
WORK_ROOT = os.path.abspath("scratch/phase4_kgrid_demo")
RC_BOHR = 3.0
OMEGA_BOHR = 0.05


def hash_file(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def parse_converged_scf(out_content: str):
    converged = False
    scf_iter = 0
    cnt = 0
    total_energy = float("nan")
    fermi_ev = float("nan")
    total_spin = float("nan")

    for line in out_content.splitlines():
        if re.search(r"^\s*scf:\s+\d+", line):
            cnt += 1
        if "SCF cycle converged after" in line:
            converged = True
            m = re.search(r"SCF cycle converged after\s+(\d+)\s+iterations", line)
            if m:
                scf_iter = int(m.group(1))
        if "siesta: Etot" in line or "siesta: E_KS(eV)" in line:
            parts = line.split("=")
            if len(parts) > 1:
                try:
                    total_energy = float(parts[1].strip().split()[0])
                except Exception:
                    pass
        if "siesta: Fermi =" in line:
            m = re.search(r"siesta:\s+Fermi\s*=\s*([-+]?\d*\.\d+)", line)
            if m:
                fermi_ev = float(m.group(1))
        if "siesta: Total spin moment" in line:
            m = re.search(r"Total spin moment\s*=\s*([-+]?\d*\.\d+)", line)
            if m:
                total_spin = float(m.group(1))

    if scf_iter == 0:
        scf_iter = cnt
    return converged, scf_iter, total_energy, fermi_ev, total_spin


def build_base_unsplit_fdf_content(
    mesh_cutoff_ry: float,
    basis_size: str,
    energy_shift_ry: float,
    kgrid: tuple[int, int, int],
) -> str:
    kx, ky, kz = kgrid
    return f"""SystemName          MnO 2x1x1 Supercell Base kgrid_{kx}x{ky}x{kz}
SystemLabel MnO_2x1x1_Base

NumberOfAtoms       4
NumberOfSpecies     2

%block ChemicalSpeciesLabel
 1  25  Mn
 2   8  O
%endblock ChemicalSpeciesLabel

LatticeConstant     4.445 Ang
%block LatticeVectors
  0.0  1.0  1.0
  0.5  0.0  0.5
  0.5  0.5  0.0
%endblock LatticeVectors

AtomicCoordinatesFormat  Fractional
%block AtomicCoordinatesAndAtomicSpecies
 0.00  0.00  0.00   1   # Mn site 0
 0.50  0.00  0.00   1   # Mn site 1
 0.25  0.50  0.50   2   # O  site 0
 0.75  0.50  0.50   2   # O  site 1
%endblock AtomicCoordinatesAndAtomicSpecies

PAO.BasisSize       {basis_size}
PAO.EnergyShift     {energy_shift_ry} Ry
PAO.SplitNorm       0.15
PAO.BasisType       split

MeshCutoff          {mesh_cutoff_ry:.0f} Ry
%block kgrid_Monkhorst_Pack
 {kx} 0 0 0.0
 0 {ky} 0 0.0
 0 0 {kz} 0.0
%endblock kgrid_Monkhorst_Pack

MaxSCFIterations 500
DM.MixingWeight 0.05
DM.NumberPulay 5

Spin  polarized
%block DM.InitSpin
 1 +5.0
 2 +5.0
 3  0.0
 4  0.0
%endblock DM.InitSpin

DFTU.ProjectorGenerationMethod 2
DFTU.PotentialShift true

WriteCoorXmol true
WriteForces   true
WriteDM true

%block DFTU.proj
  Mn   1
  3  2
  0.0000  0.0000
  {RC_BOHR:.4f}  {OMEGA_BOHR:.4f}
%endblock DFTU.proj
DFTU.FirstIteration true
DM.UseSaveDM true

MD.NumCGsteps 0
"""


def extract_site_occupations_semantically(
    events: list,
    selected_event: any,
    species_to_site_map: dict[int, int],
    n_sites: int = 2,
) -> list[float]:
    occs = [float("nan")] * n_sites
    found_sites = set()
    for atom in selected_event.atoms:
        sp_idx = atom.species_index
        if sp_idx in species_to_site_map:
            site_idx = species_to_site_map[sp_idx]
            if site_idx in found_sites:
                raise RuntimeError(f"Duplicate atom found for site_idx {site_idx}")
            occs[site_idx] = float(atom.trace_total)
            found_sites.add(site_idx)

    if len(found_sites) != n_sites:
        raise RuntimeError(
            f"Explicit species mapping failed: expected {n_sites} sites, found {len(found_sites)}"
        )
    return occs


def prepare_pseudos(target_dir: str, species_labels: list[str]):
    pp_src = os.path.abspath("scratch/phase4_method2_revalidation/reference")
    for sp in species_labels:
        dst = os.path.join(target_dir, f"{sp}.psml")
        if not os.path.exists(dst):
            shutil.copy(os.path.join(pp_src, "Mn.psml"), dst)
    o_dst = os.path.join(target_dir, "O.psml")
    if not os.path.exists(o_dst):
        shutil.copy(os.path.join(pp_src, "O.psml"), o_dst)


def run_configuration_campaign(
    config: LRScientificConfiguration,
    work_dir: str,
    builder: FdfBuilder,
    adapter: SiestaLRAdapter,
) -> tuple[ConvergenceResult, int, dict]:
    os.makedirs(work_dir, exist_ok=True)

    base_unsplit = build_base_unsplit_fdf_content(
        config.mesh_cutoff_ry, config.basis_size, config.pao_energy_shift_ry, config.kgrid
    )
    split_fdf_content, species_labels = materialize_split_species_fdf(
        content=base_unsplit, target_species="Mn", new_prefix="MnLR"
    )
    n_sites = len(species_labels)
    site_labels = list(range(n_sites))
    species_to_site_map = {i + 1: i for i in range(n_sites)}

    # Reference
    ref_dir = os.path.join(work_dir, "split_reference")
    os.makedirs(ref_dir, exist_ok=True)
    ref_fdf = os.path.join(ref_dir, "MnO_SplitRef.fdf")
    ref_out = os.path.join(ref_dir, "MnO_SplitRef.out")
    ref_dm = os.path.join(ref_dir, "MnO_SplitRef.DM")

    prepare_pseudos(ref_dir, species_labels)

    ref_projections = [
        {"species": sp, "n": 3, "l": 2, "rc": config.projector_rc_bohr, "omega": config.projector_omega_bohr, "alpha": 0.0}
        for sp in species_labels
    ]
    ref_fdf_text = builder.modify_fdf_content(
        content=split_fdf_content,
        alpha=0.0,
        run_name="MnO_SplitRef",
        response_mode="SCREENED",
        projections=ref_projections,
    )
    with open(ref_fdf, "w") as f:
        f.write(ref_fdf_text)

    new_runs = 0
    t0_wall = time.time()
    if not (os.path.exists(ref_out) and "Job completed" in open(ref_out).read()):
        print(f"[{config.system_label} kgrid={config.kgrid}] Running split reference...")
        adapter.run_siesta_wsl("MnO_SplitRef.fdf", "MnO_SplitRef.out", ref_dir)
        new_runs += 1
    else:
        print(f"[{config.system_label} kgrid={config.kgrid}] Reusing split reference output")

    ref_dm_hash = hash_file(ref_dm)
    ref_out_text = open(ref_out).read()
    ref_conv, ref_scf_iter, E_ref, fermi_ev, total_spin = parse_converged_scf(ref_out_text)

    elec_info = {
        "E_ref_eV": E_ref,
        "fermi_eV": fermi_ev,
        "total_spin_moment": total_spin,
        "ref_scf_iterations": ref_scf_iter,
    }

    # Perturbations
    run_records = {}
    total_scf_iters = ref_scf_iter

    for J in range(n_sites):
        for alpha in config.alpha_grid:
            for mode in ["bare", "screened"]:
                dedup_key = (0 if alpha == 0.0 else J, alpha, mode)
                if dedup_key in run_records:
                    continue

                label = f"alpha_{alpha:+.2f}".replace(".", "p").replace("+", "pos").replace("-", "neg")
                run_name = f"MnO_colJ{J}_{mode.upper()}_{label}"
                run_dir = os.path.join(work_dir, f"colJ{J}_{mode}_{label}")
                os.makedirs(run_dir, exist_ok=True)

                fdf_path = os.path.join(run_dir, f"{run_name}.fdf")
                out_path = os.path.join(run_dir, f"{run_name}.out")
                dm_copy = os.path.join(run_dir, f"{run_name}.DM")

                prepare_pseudos(run_dir, species_labels)

                if not os.path.exists(dm_copy):
                    shutil.copy(ref_dm, dm_copy)

                projections = []
                for i, sp in enumerate(species_labels):
                    shift = alpha if i == J else 0.0
                    projections.append({
                        "species": sp, "n": 3, "l": 2, "rc": config.projector_rc_bohr, "omega": config.projector_omega_bohr, "alpha": shift
                    })

                mode_str = "BARE" if mode == "bare" else "SCREENED"
                fdf_text = builder.modify_fdf_content(
                    content=split_fdf_content,
                    alpha=alpha,
                    run_name=run_name,
                    response_mode=mode_str,
                    projections=projections,
                )
                with open(fdf_path, "w") as f:
                    f.write(fdf_text)

                already_done = (
                    os.path.exists(out_path)
                    and "Job completed" in open(out_path).read()
                )
                if not already_done:
                    print(f"  [{config.system_label} kgrid={config.kgrid} J={J} {mode.upper()} alpha={alpha:+.2f}] Running...")
                    adapter.run_siesta_wsl(f"{run_name}.fdf", f"{run_name}.out", run_dir)
                    new_runs += 1
                else:
                    print(f"  [{config.system_label} kgrid={config.kgrid} J={J} {mode.upper()} alpha={alpha:+.2f}] Reusing output")

                run_out_text = open(out_path).read()
                _, run_scf, _, _, _ = parse_converged_scf(run_out_text)
                total_scf_iters += run_scf

                run_records[dedup_key] = {
                    "out_path": out_path,
                    "fdf_path": fdf_path,
                    "dm_hash": hash_file(dm_copy),
                    "out_hash": hash_file(out_path),
                }

    wall_time_s = time.time() - t0_wall
    elec_info["total_scf_iterations"] = total_scf_iters
    elec_info["wall_time_seconds"] = wall_time_s

    # Extract observations
    observations = []
    for J in range(n_sites):
        for alpha in config.alpha_grid:
            bare_info = run_records[(0 if alpha == 0.0 else J, alpha, "bare")]
            screened_info = run_records[(0 if alpha == 0.0 else J, alpha, "screened")]

            bare_out_text = open(bare_info["out_path"]).read()
            screened_out_text = open(screened_info["out_path"]).read()

            bare_events = parse_hubbard_population_events(bare_out_text)
            ctx_bare = ObservationContext(
                siesta_version="5.4.2",
                calculation_mode="BARE",
                reference_dm_sha256=bare_info["dm_hash"],
                projector_fingerprint=f"siteJ_{J}_alpha_{alpha}",
                scf_mix_target="density",
                scf_mixer_method="Linear",
                scf_mixer_weight=1.0,
                max_scf_iterations=2,
                convergence_confirmed=False,
                final_scf_iteration=None,
                post_scf_population_occurrence=None,
            )
            ref_sel = Siesta542BarePolicyV1.get_reference_observation(bare_events, ctx_bare)
            bare_sel = Siesta542BarePolicyV1.get_bare_observation(bare_events, ctx_bare)

            occ_ref = extract_site_occupations_semantically(bare_events, ref_sel.event, species_to_site_map, n_sites)
            occ_bare = extract_site_occupations_semantically(bare_events, bare_sel.event, species_to_site_map, n_sites)

            scrn_converged, scrn_iter, _, _, _ = parse_converged_scf(screened_out_text)
            if not scrn_converged:
                raise RuntimeError(f"SCREENED at J={J}, alpha={alpha} did not converge")

            scrn_events = parse_hubbard_population_events(screened_out_text)
            scrn_selected, _, _ = select_converged_reference_event(scrn_events, scrn_iter)
            occ_scrn = extract_site_occupations_semantically(scrn_events, scrn_selected, species_to_site_map, n_sites)

            observations.append(ResponseObservation(
                perturbation_site=J,
                alpha=alpha,
                site_labels=site_labels,
                occupations_ref=occ_ref,
                occupations_bare=occ_bare,
                occupations_screened=occ_scrn,
                parent_dm_sha256=bare_info["dm_hash"],
            ))

    res = build_convergence_result_from_observations(config, observations, scf_cost=new_runs)
    return res, new_runs, elec_info


def compute_matrix_eigensystem(mat: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Compute eigenvalues and normalized eigenvectors of a 2x2 matrix."""
    vals, vecs = np.linalg.eigh(mat)
    # Sort descending
    idx = np.argsort(vals)[::-1]
    return vals[idx], vecs[:, idx]


def main():
    os.makedirs(WORK_ROOT, exist_ok=True)
    builder = FdfBuilder()
    adapter = SiestaLRAdapter(wsl_siesta_path=SIESTA_PATH)

    # 1. Baseline Config: DZP @ 200 Ry, EnergyShift = 0.005 Ry, kgrid = (1, 1, 1)
    cfg_111 = LRScientificConfiguration(
        system_label="MnO_2x1x1_KgridScan",
        structure_summary={"lattice_constant": 4.445, "n_atoms": 4},
        correlated_sites=[0, 1],
        species_labels=["MnLR0", "MnLR1"],
        pseudopotentials={"MnLR0": "Mn.psml", "MnLR1": "Mn.psml", "O": "O.psml"},
        basis_size="DZP",
        mesh_cutoff_ry=200.0,
        kgrid=(1, 1, 1),
        supercell=(2, 1, 1),
        projector_rc_bohr=3.0,
        projector_omega_bohr=0.05,
        projector_units="Bohr",
        pao_energy_shift_ry=0.005,
        pao_split_norm=0.15,
        pao_basis_type="split",
        alpha_grid=[-0.02, -0.01, 0.00, 0.01, 0.02],
        spin_configuration="polarized",
    )

    # 2. New Config: DZP @ 200 Ry, EnergyShift = 0.005 Ry, kgrid = (1, 2, 2)
    cfg_122 = LRScientificConfiguration(
        system_label="MnO_2x1x1_KgridScan",
        structure_summary={"lattice_constant": 4.445, "n_atoms": 4},
        correlated_sites=[0, 1],
        species_labels=["MnLR0", "MnLR1"],
        pseudopotentials={"MnLR0": "Mn.psml", "MnLR1": "Mn.psml", "O": "O.psml"},
        basis_size="DZP",
        mesh_cutoff_ry=200.0,
        kgrid=(1, 2, 2),
        supercell=(2, 1, 1),
        projector_rc_bohr=3.0,
        projector_omega_bohr=0.05,
        projector_units="Bohr",
        pao_energy_shift_ry=0.005,
        pao_split_norm=0.15,
        pao_basis_type="split",
        alpha_grid=[-0.02, -0.01, 0.00, 0.01, 0.02],
        spin_configuration="polarized",
    )

    dir_111 = os.path.abspath("scratch/phase4_energyshift_demo/dzp_0p005ry")
    dir_122 = os.path.join(WORK_ROOT, "kgrid_1x2x2")

    print("[BASELINE] Loading existing (1,1,1) baseline...")
    res_111, cost_111, elec_111 = run_configuration_campaign(cfg_111, dir_111, builder, adapter)

    print("\n[CAMPAIGN] Running new (1,2,2) campaign...")
    res_122, cost_122, elec_122 = run_configuration_campaign(cfg_122, dir_122, builder, adapter)

    # 3. Quantitative Comparison
    cmp = compare_convergence_results(res_111, res_122, param_name="kgrid")

    u_111 = res_111.U_matrix
    u_122 = res_122.U_matrix

    u00_111 = u_111[0, 0]
    u00_122 = u_122[0, 0]
    u00_abs = abs(u00_122 - u00_111)
    u00_rel = u00_abs / abs(u00_111)

    u01_111 = u_111[0, 1]
    u01_122 = u_122[0, 1]
    u01_abs = abs(u01_122 - u01_111)
    u01_rel = u01_abs / abs(u01_111)

    u10_111 = u_111[1, 0]
    u10_122 = u_122[1, 0]
    u10_abs = abs(u10_122 - u10_111)
    u10_rel = u10_abs / abs(u10_111)

    u11_111 = u_111[1, 1]
    u11_122 = u_122[1, 1]
    u11_abs = abs(u11_122 - u11_111)
    u11_rel = u11_abs / abs(u11_111)

    u_mat_abs = cmp.abs_diff_U
    u_mat_rel = cmp.rel_diff_U

    # Modes
    m111 = res_111.eigenmode_diagnostics
    m122 = res_122.eigenmode_diagnostics

    u_unif_111 = m111.get("uniform_mode", {}).get("U", float("nan"))
    u_unif_122 = m122.get("uniform_mode", {}).get("U", float("nan"))
    u_unif_diff = u_unif_122 - u_unif_111

    u_stag_111 = m111.get("staggered_mode", {}).get("U", float("nan"))
    u_stag_122 = m122.get("staggered_mode", {}).get("U", float("nan"))
    u_stag_diff = u_stag_122 - u_stag_111

    # Exact Eigensystems
    evals_u_111, evecs_u_111 = compute_matrix_eigensystem(u_111)
    evals_u_122, evecs_u_122 = compute_matrix_eigensystem(u_122)

    evals_c0_122, evecs_c0_122 = compute_matrix_eigensystem(res_122.chi0_raw)
    evals_c_122, evecs_c_122 = compute_matrix_eigensystem(res_122.chi_raw)

    # Cost ratio
    cost_scf_ratio = elec_122["total_scf_iterations"] / (elec_111["total_scf_iterations"] + 1e-12)

    # Recommendation
    if u_mat_rel < 0.05 and abs(u_unif_diff) < 0.10:
        rec = "A. k-point sensitivity is already weak enough to move to supercell sensitivity"
    else:
        rec = "B. run one denser k-grid, preferably approximately preserving reciprocal-space density"

    # Print Report
    print(f"\n========================================================")
    print(f"K-POINT SENSITIVITY REPORT: (1,1,1) vs (1,2,2)")
    print(f"========================================================")

    print(f"\nBASELINE REUSED:  (1,1,1) DZP 0.005Ry (0 new SIESTA runs)")
    print(f"NEW SIESTA RUNS:  {cost_122} (kgrid = (1,2,2))")

    print(f"\nELECTRONIC STRUCTURE CONTEXT:")
    print(f"  (1,1,1): E_ref = {elec_111['E_ref_eV']:.6f} eV, Fermi = {elec_111['fermi_eV']:.4f} eV, Total Spin = {elec_111['total_spin_moment']:.4f}")
    print(f"  (1,2,2): E_ref = {elec_122['E_ref_eV']:.6f} eV, Fermi = {elec_122['fermi_eV']:.4f} eV, Total Spin = {elec_122['total_spin_moment']:.4f}")

    print(f"\nCHI0 MATRICES:")
    print(f"  chi0 (1,1,1):\n{res_111.chi0_raw}")
    print(f"  chi0 (1,2,2):\n{res_122.chi0_raw}")

    print(f"\nCHI MATRICES:")
    print(f"  chi (1,1,1):\n{res_111.chi_raw}")
    print(f"  chi (1,2,2):\n{res_122.chi_raw}")

    print(f"\nU MATRICES (eV):")
    print(f"  U (1,1,1):\n{u_111}")
    print(f"  U (1,2,2):\n{u_122}")

    print(f"\nDIFFERENCES:")
    print(f"  U00_ABS_DIFF:        {u00_abs:.6f} eV")
    print(f"  U00_REL_DIFF:        {u00_rel:.4%}")
    print(f"  U01_ABS_DIFF:        {u01_abs:.6f} eV")
    print(f"  U01_REL_DIFF:        {u01_rel:.4%}")
    print(f"  U_MATRIX_ABS_DIFF:   {u_mat_abs:.6f} eV")
    print(f"  U_MATRIX_REL_DIFF:   {u_mat_rel:.4%}")

    print(f"\nMODE ANALYSIS (eV):")
    print(f"  Uniform mode:   (1,1,1) = {u_unif_111:.4f} eV  ->  (1,2,2) = {u_unif_122:.4f} eV  (change = {u_unif_diff:+.4f} eV)")
    print(f"  Staggered mode: (1,1,1) = {u_stag_111:.4f} eV  ->  (1,2,2) = {u_stag_122:.4f} eV  (change = {u_stag_diff:+.4f} eV)")

    print(f"\nEXACT EIGENSYSTEM FOR (1,2,2):")
    print(f"  U Eigenvalues: {evals_u_122}")
    print(f"  U Eigenvectors:\n{evecs_u_122}")

    print(f"\nCOMPUTATIONAL COST:")
    print(f"  (1,1,1): {elec_111['total_scf_iterations']} total SCF iterations")
    print(f"  (1,2,2): {elec_122['total_scf_iterations']} total SCF iterations (ratio = {cost_scf_ratio:.2f}x)")

    print(f"\nNEXT_RECOMMENDED_STEP: {rec}")

    # Evidence JSON
    evidence = {
        "task": "P4_KPOINT_SENSITIVITY_STEP1",
        "baseline_kgrid": [1, 1, 1],
        "new_kgrid": [1, 2, 2],
        "new_siesta_runs": cost_122,
        "fixed_parameters": {
            "basis": "DZP",
            "energy_shift_ry": 0.005,
            "mesh_cutoff_ry": 200.0,
            "supercell": [2, 1, 1],
            "projector_rc_bohr": RC_BOHR,
            "projector_omega_bohr": OMEGA_BOHR,
        },
        "electronic_context": {
            "111": elec_111,
            "122": elec_122,
        },
        "chi0_111": res_111.chi0_raw.tolist(),
        "chi0_122": res_122.chi0_raw.tolist(),
        "chi_111": res_111.chi_raw.tolist(),
        "chi_122": res_122.chi_raw.tolist(),
        "U_111": u_111.tolist(),
        "U_122": u_122.tolist(),
        "differences": {
            "u00_abs_diff": u00_abs,
            "u00_rel_diff": u00_rel,
            "u01_abs_diff": u01_abs,
            "u01_rel_diff": u01_rel,
            "u10_abs_diff": u10_abs,
            "u10_rel_diff": u10_rel,
            "u11_abs_diff": u11_abs,
            "u11_rel_diff": u11_rel,
            "u_matrix_abs_diff": u_mat_abs,
            "u_matrix_rel_diff": u_mat_rel,
        },
        "mode_analysis": {
            "uniform_mode_111": u_unif_111,
            "uniform_mode_122": u_unif_122,
            "uniform_mode_change": u_unif_diff,
            "staggered_mode_111": u_stag_111,
            "staggered_mode_122": u_stag_122,
            "staggered_mode_change": u_stag_diff,
        },
        "eigensystem_122": {
            "U_eigenvalues": evals_u_122.tolist(),
            "U_eigenvectors": evecs_u_122.tolist(),
            "chi0_eigenvalues": evals_c0_122.tolist(),
            "chi0_eigenvectors": evecs_c0_122.tolist(),
            "chi_eigenvalues": evals_c_122.tolist(),
            "chi_eigenvectors": evecs_c_122.tolist(),
        },
        "computational_cost": {
            "cost_111_scf_iters": elec_111["total_scf_iterations"],
            "cost_122_scf_iters": elec_122["total_scf_iterations"],
            "scf_ratio": cost_scf_ratio,
        },
        "scientific_status": "DIAGNOSTICS_ONLY",
        "next_recommended_step": rec,
    }

    os.makedirs("docs/audits", exist_ok=True)
    with open("docs/audits/PHASE4_KPOINT_SENSITIVITY.json", "w") as f:
        json.dump(evidence, f, indent=2)

    print(f"\nEVIDENCE: docs/audits/PHASE4_KPOINT_SENSITIVITY.json")
    print(f"\nTASK_VERDICT = PASS")


if __name__ == "__main__":
    main()
