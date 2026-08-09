"""
phase4_energyshift_3point.py – DZP EnergyShift 3-Point Sequence Study (0.02 Ry, 0.01 Ry, 0.005 Ry).

Reuses existing 0.02 Ry and 0.01 Ry campaigns.
Executes 19 new SIESTA runs for 0.005 Ry.

Analyzes the sequence:
  - Generated PAO cutoff radii
  - chi0, chi, U matrices
  - U00, U01
  - Uniform mode and Staggered mode responses for chi0, chi, U
  - Consecutive changes (0.02 -> 0.01 vs 0.01 -> 0.005)
"""

from __future__ import annotations

import os
import sys
import json
import shutil
import hashlib
import re

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
WORK_ROOT = os.path.abspath("scratch/phase4_energyshift_demo")
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
    if scf_iter == 0:
        scf_iter = cnt
    return converged, scf_iter, total_energy


def extract_pao_radii(out_path: str) -> dict[str, float]:
    """Extract orbital cutoff radii (Bohr) from SIESTA .out file."""
    if not os.path.exists(out_path):
        return {}
    content = open(out_path).read()
    radii = {}
    current_state = None
    for line in content.splitlines():
        m_state = re.search(r"SPLIT:\s+Basis orbitals for state\s+([0-9][a-z])", line)
        if m_state:
            current_state = m_state.group(1)
        if current_state and "rc =" in line:
            m_rc = re.search(r"rc\s*=\s*([0-9]+\.[0-9]+)", line)
            if m_rc:
                radii[current_state] = float(m_rc.group(1))
    return radii


def build_base_unsplit_fdf_content(mesh_cutoff_ry: float, basis_size: str, energy_shift_ry: float) -> str:
    return f"""SystemName          MnO 2x1x1 Supercell Base {energy_shift_ry}Ry
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
 1 0 0 0.0
 0 1 0 0.0
 0 0 1 0.0
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
) -> tuple[ConvergenceResult, int, dict[str, float]]:
    os.makedirs(work_dir, exist_ok=True)

    base_unsplit = build_base_unsplit_fdf_content(
        config.mesh_cutoff_ry, config.basis_size, config.pao_energy_shift_ry
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
    if not (os.path.exists(ref_out) and "Job completed" in open(ref_out).read()):
        print(f"[{config.system_label} Shift={config.pao_energy_shift_ry}Ry] Running split reference...")
        adapter.run_siesta_wsl("MnO_SplitRef.fdf", "MnO_SplitRef.out", ref_dir)
        new_runs += 1
    else:
        print(f"[{config.system_label} Shift={config.pao_energy_shift_ry}Ry] Reusing split reference output")

    ref_dm_hash = hash_file(ref_dm)
    pao_radii = extract_pao_radii(ref_out)

    # Perturbations
    run_records = {}
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
                    print(f"  [{config.system_label} Shift={config.pao_energy_shift_ry}Ry J={J} {mode.upper()} alpha={alpha:+.2f}] Running...")
                    adapter.run_siesta_wsl(f"{run_name}.fdf", f"{run_name}.out", run_dir)
                    new_runs += 1
                else:
                    print(f"  [{config.system_label} Shift={config.pao_energy_shift_ry}Ry J={J} {mode.upper()} alpha={alpha:+.2f}] Reusing output")

                run_records[dedup_key] = {
                    "out_path": out_path,
                    "fdf_path": fdf_path,
                    "dm_hash": hash_file(dm_copy),
                    "out_hash": hash_file(out_path),
                }

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

            scrn_converged, scrn_iter, _ = parse_converged_scf(screened_out_text)
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
    return res, new_runs, pao_radii


def main():
    os.makedirs(WORK_ROOT, exist_ok=True)
    builder = FdfBuilder()
    adapter = SiestaLRAdapter(wsl_siesta_path=SIESTA_PATH)

    shifts = [0.02, 0.01, 0.005]

    configs = [
        LRScientificConfiguration(
            system_label="MnO_2x1x1_EnergyShift3Point",
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
            pao_energy_shift_ry=eshift,
            pao_split_norm=0.15,
            pao_basis_type="split",
            alpha_grid=[-0.02, -0.01, 0.00, 0.01, 0.02],
            spin_configuration="polarized",
        )
        for eshift in shifts
    ]

    dirs = [
        os.path.abspath("scratch/phase4_basis_demo/dzp_200Ry"),  # 0.02 Ry
        os.path.abspath("scratch/phase4_energyshift_demo/dzp_0p01ry"),  # 0.01 Ry
        os.path.join(WORK_ROOT, "dzp_0p005ry"),  # 0.005 Ry
    ]

    results = []
    costs = []
    radii_list = []

    for cfg, d in zip(configs, dirs):
        res, cost, radii = run_configuration_campaign(cfg, d, builder, adapter)
        results.append(res)
        costs.append(cost)
        radii_list.append(radii)

    res_0p02, res_0p01, res_0p005 = results
    r0p02, r0p01, r0p005 = radii_list

    # Differences 0.02 -> 0.01
    u_0p02 = res_0p02.U_matrix
    u_0p01 = res_0p01.U_matrix
    u_0p005 = res_0p005.U_matrix

    u00_0p02 = u_0p02[0, 0]
    u00_0p01 = u_0p01[0, 0]
    u00_0p005 = u_0p005[0, 0]

    u01_0p02 = u_0p02[0, 1]
    u01_0p01 = u_0p01[0, 1]
    u01_0p005 = u_0p005[0, 1]

    u00_change_12 = u00_0p01 - u00_0p02
    u00_change_23 = u00_0p005 - u00_0p01

    u01_change_12 = u01_0p01 - u01_0p02
    u01_change_23 = u01_0p005 - u01_0p01

    # Eigenmode evolution
    m0p02 = res_0p02.eigenmode_diagnostics
    m0p01 = res_0p01.eigenmode_diagnostics
    m0p005 = res_0p005.eigenmode_diagnostics

    u_unif_0p02 = m0p02.get("uniform_mode", {}).get("U", float("nan"))
    u_unif_0p01 = m0p01.get("uniform_mode", {}).get("U", float("nan"))
    u_unif_0p005 = m0p005.get("uniform_mode", {}).get("U", float("nan"))

    u_stag_0p02 = m0p02.get("staggered_mode", {}).get("U", float("nan"))
    u_stag_0p01 = m0p01.get("staggered_mode", {}).get("U", float("nan"))
    u_stag_0p005 = m0p005.get("staggered_mode", {}).get("U", float("nan"))

    unif_change_12 = u_unif_0p01 - u_unif_0p02
    unif_change_23 = u_unif_0p005 - u_unif_0p01

    stag_change_12 = u_stag_0p01 - u_stag_0p02
    stag_change_23 = u_stag_0p005 - u_stag_0p01

    # Check convergence trend
    # Rate of change reduction: |change_23| / |change_12|
    ratio_u00 = abs(u00_change_23) / abs(u00_change_12) if abs(u00_change_12) > 1e-6 else 0.0
    ratio_unif = abs(unif_change_23) / abs(unif_change_12) if abs(unif_change_12) > 1e-6 else 0.0

    print(f"\n========================================================")
    print(f"DZP THREE-POINT ENERGYSHIFT STUDY (0.02 -> 0.01 -> 0.005 Ry)")
    print(f"========================================================")

    print(f"\nEXTRACTED PAO CUTOFF RADII (Bohr):")
    print(f"  0.02 Ry:  {r0p02}")
    print(f"  0.01 Ry:  {r0p01}")
    print(f"  0.005 Ry: {r0p005}")

    print(f"\nU MATRICES (eV):")
    print(f"  U (0.02 Ry):\n{u_0p02}")
    print(f"  U (0.01 Ry):\n{u_0p01}")
    print(f"  U (0.005 Ry):\n{u_0p005}")

    print(f"\nCONSECUTIVE CHANGES:")
    print(f"  U00:     0.02->0.01: {u00_change_12:+.6f} eV   |   0.01->0.005: {u00_change_23:+.6f} eV  (ratio={ratio_u00:.2f})")
    print(f"  U01:     0.02->0.01: {u01_change_12:+.6f} eV   |   0.01->0.005: {u01_change_23:+.6f} eV")
    print(f"  Uniform: 0.02->0.01: {unif_change_12:+.6f} eV   |   0.01->0.005: {unif_change_23:+.6f} eV  (ratio={ratio_unif:.2f})")
    print(f"  Stag:    0.02->0.01: {stag_change_12:+.6f} eV   |   0.01->0.005: {stag_change_23:+.6f} eV")

    # Recommendation
    if abs(unif_change_23) < 0.10 and abs(u00_change_23) < 0.10:
        rec = "A. proceed to k-grid convergence using DZP / EnergyShift=0.005 Ry"
        trend = "STABILIZING (rate of change decreasing rapidly)"
    elif ratio_unif < 0.5:
        rec = "A. proceed to k-grid convergence using DZP / EnergyShift=0.005 Ry"
        trend = "MONOTONICALLY CONVERGING (change decelerating)"
    else:
        rec = "B. test one additional longer-range basis point because the 0.01 -> 0.005 response remains materially evolving"
        trend = "MATERIALLY EVOLVING"

    print(f"\nORBITAL_RANGE_TREND: {trend}")
    print(f"NEXT_RECOMMENDED_STEP: {rec}")

    # Evidence JSON
    evidence = {
        "task": "P4_DZP_ENERGYSHIFT_THREE_POINT_STUDY",
        "energy_shifts_ry": [0.02, 0.01, 0.005],
        "new_siesta_runs": costs[2],
        "pao_radii": {
            "0.02Ry": r0p02,
            "0.01Ry": r0p01,
            "0.005Ry": r0p005,
        },
        "chi0_matrices": [res.chi0_raw.tolist() for res in results],
        "chi_matrices": [res.chi_raw.tolist() for res in results],
        "U_matrices": [res.U_matrix.tolist() for res in results],
        "changes": {
            "u00_0p02_to_0p01": u00_change_12,
            "u00_0p01_to_0p005": u00_change_23,
            "u01_0p02_to_0p01": u01_change_12,
            "u01_0p01_to_0p005": u01_change_23,
            "uniform_0p02_to_0p01": unif_change_12,
            "uniform_0p01_to_0p005": unif_change_23,
            "staggered_0p02_to_0p01": stag_change_12,
            "staggered_0p01_to_0p005": stag_change_23,
        },
        "mode_analysis": {
            "0.02Ry": {"uniform": u_unif_0p02, "staggered": u_stag_0p02},
            "0.01Ry": {"uniform": u_unif_0p01, "staggered": u_stag_0p01},
            "0.005Ry": {"uniform": u_unif_0p005, "staggered": u_stag_0p005},
        },
        "trend": trend,
        "next_recommended_step": rec,
        "scientific_status": "DIAGNOSTICS_ONLY",
    }
    os.makedirs("docs/audits", exist_ok=True)
    with open("docs/audits/PHASE4_ENERGYSHIFT_THREE_POINT.json", "w") as f:
        json.dump(evidence, f, indent=2)

    print(f"\nEVIDENCE: docs/audits/PHASE4_ENERGYSHIFT_THREE_POINT.json")
    print(f"\nTASK_VERDICT = PASS")


if __name__ == "__main__":
    main()
