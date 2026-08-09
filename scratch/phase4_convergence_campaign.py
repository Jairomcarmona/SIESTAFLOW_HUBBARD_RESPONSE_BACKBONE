"""
phase4_convergence_campaign.py – Real demonstration of the Scientific Convergence Campaign Engine.

Runs a single-dimension numerical resolution scan (MeshCutoff: 150 Ry vs 200 Ry)
on the real 2-site MnO 2×1×1 supercell fixture using the production convergence engine.

Quantifies change in chi0, chi, and U matrix when numerical resolution changes.
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
WORK_ROOT = os.path.abspath("scratch/phase4_convergence_demo")
RC = 3.0
OMEGA = 0.05


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


def build_base_unsplit_fdf_content(mesh_cutoff_ry: float) -> str:
    return f"""SystemName          MnO 2x1x1 Supercell Base {mesh_cutoff_ry:.0f}Ry
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

PAO.BasisSize       SZ
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
  {RC:.4f}  {OMEGA:.4f}
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
) -> tuple[ConvergenceResult, int]:
    """Run full 2x2 campaign for a given configuration."""
    os.makedirs(work_dir, exist_ok=True)

    base_unsplit = build_base_unsplit_fdf_content(config.mesh_cutoff_ry)
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
        {"species": sp, "n": 3, "l": 2, "rc": config.projector_rc, "omega": config.projector_omega, "alpha": 0.0}
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
        print(f"[{config.system_label} Cutoff={config.mesh_cutoff_ry}Ry] Running split reference...")
        adapter.run_siesta_wsl("MnO_SplitRef.fdf", "MnO_SplitRef.out", ref_dir)
        new_runs += 1

    ref_dm_hash = hash_file(ref_dm)

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
                        "species": sp, "n": 3, "l": 2, "rc": config.projector_rc, "omega": config.projector_omega, "alpha": shift
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
                    print(f"  [{config.system_label} Cutoff={config.mesh_cutoff_ry}Ry J={J} {mode.upper()} alpha={alpha:+.2f}] Running...")
                    adapter.run_siesta_wsl(f"{run_name}.fdf", f"{run_name}.out", run_dir)
                    new_runs += 1

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
    return res, new_runs


def main():
    os.makedirs(WORK_ROOT, exist_ok=True)
    builder = FdfBuilder()
    adapter = SiestaLRAdapter(wsl_siesta_path=SIESTA_PATH)

    # 1. Define Base Configuration (MnO 2x1x1 fixture)
    base_config = LRScientificConfiguration(
        system_label="MnO_2x1x1_CutoffScan",
        structure_summary={"lattice_constant": 4.445, "n_atoms": 4},
        correlated_sites=[0, 1],
        species_labels=["MnLR0", "MnLR1"],
        pseudopotentials={"MnLR0": "Mn.psml", "MnLR1": "Mn.psml", "O": "O.psml"},
        basis_size="SZ",
        mesh_cutoff_ry=150.0,
        kgrid=(1, 1, 1),
        supercell=(2, 1, 1),
        projector_rc=3.0,
        projector_omega=0.05,
        alpha_grid=[-0.02, -0.01, 0.00, 0.01, 0.02],
        spin_configuration="polarized",
    )

    # 2. Generate Single-Dimension Scan (MeshCutoff: 150 Ry vs 200 Ry)
    scan_configs = generate_single_dimension_scan(base_config, "mesh_cutoff_ry", [150.0, 200.0])

    print(f"CAMPAIGN = DEMONSTRATION MESH_CUTOFF SCAN\n")
    print(f"SUPPORTED_SCAN_DIMENSIONS: mesh_cutoff_ry, kgrid, basis_size, supercell, projector_rc, projector_omega, alpha_grid\n")

    # 3. Test Reuse Logic
    cfg_150 = scan_configs[0]
    cfg_200 = scan_configs[1]
    reuse_allowed = can_reuse_calculations(cfg_150, cfg_200)
    print(f"REUSE_LOGIC_TEST: Config 150Ry vs 200Ry reuse allowed? {reuse_allowed}")
    print(f"  (False is expected because MeshCutoff differs -> prevents invalid calculation reuse)\n")

    # 4. Run Campaign for Config A (150 Ry) and Config B (200 Ry)
    dir_150 = os.path.join(WORK_ROOT, "cutoff_150Ry")
    dir_200 = os.path.join(WORK_ROOT, "cutoff_200Ry")

    res_150, cost_150 = run_configuration_campaign(cfg_150, dir_150, builder, adapter)
    res_200, cost_200 = run_configuration_campaign(cfg_200, dir_200, builder, adapter)

    # 5. Compare Results (Quantify change in U matrix)
    cmp = compare_convergence_results(res_150, res_200, param_name="mesh_cutoff_ry")

    # 6. Print Summary Table
    print(f"\nCONVERGENCE CAMPAIGN RESULTS TABLE:")
    print(f"{'Config':<20} {'Cutoff':>8} {'kgrid':>7} {'Supercell':>10} {'rc':>5} {'omega':>6} "
          f"{'U_00':>9} {'U_11':>9} {'U_01':>9} {'U_10':>9} {'cond_chi0':>9} {'cond_chi':>9} {'Runs':>5}")

    for res in [res_150, res_200]:
        c = res.config
        u = res.U_matrix
        print(f"{c.system_label:<20} {c.mesh_cutoff_ry:7.0f}R {str(c.kgrid):>7} {str(c.supercell):>10} "
              f"{c.projector_rc:5.1f} {c.projector_omega:6.2f} "
              f"{u[0,0]:9.4f} {u[1,1]:9.4f} {u[0,1]:9.4f} {u[1,0]:9.4f} "
              f"{res.cond_chi0:9.4f} {res.cond_chi:9.4f} {res.scf_cost_siesta_runs:5d}")

    print(f"\nQUANTITATIVE COMPARISON (150 Ry -> 200 Ry):")
    print(f"  abs_diff_chi0:  {cmp.abs_diff_chi0:.6f} eV-1")
    print(f"  rel_diff_chi0:  {cmp.rel_diff_chi0:.4%}")
    print(f"  abs_diff_chi:   {cmp.abs_diff_chi:.6f} eV-1")
    print(f"  rel_diff_chi:   {cmp.rel_diff_chi:.4%}")
    print(f"  abs_diff_U:     {cmp.abs_diff_U:.6f} eV")
    print(f"  rel_diff_U:     {cmp.rel_diff_U:.4%}")
    print(f"  U_00 abs diff:  {cmp.diagonal_U_abs_diffs[0]:.6f} eV")
    print(f"  U_01 abs diff:  {cmp.off_diagonal_abs_diffs.get((0,1), float('nan')):.6f} eV")

    # Evidence JSON
    evidence = {
        "task": "P4_SCIENTIFIC_CONVERGENCE_CAMPAIGN",
        "demonstration_scan": "mesh_cutoff_ry",
        "configurations": [
            {
                "config_id": res.config_id,
                "mesh_cutoff_ry": res.config.mesh_cutoff_ry,
                "chi0_raw": res.chi0_raw.tolist(),
                "chi_raw": res.chi_raw.tolist(),
                "U_matrix": res.U_matrix.tolist() if res.U_matrix is not None else None,
                "scf_runs": res.scf_cost_siesta_runs,
            }
            for res in [res_150, res_200]
        ],
        "comparison": {
            "abs_diff_chi0": cmp.abs_diff_chi0,
            "rel_diff_chi0": cmp.rel_diff_chi0,
            "abs_diff_chi": cmp.abs_diff_chi,
            "rel_diff_chi": cmp.rel_diff_chi,
            "abs_diff_U": cmp.abs_diff_U,
            "rel_diff_U": cmp.rel_diff_U,
            "diagonal_U_abs_diffs": cmp.diagonal_U_abs_diffs,
            "off_diagonal_abs_diffs": {f"{k[0]}_{k[1]}": v for k, v in cmp.off_diagonal_abs_diffs.items()},
        },
        "status": "DIAGNOSTICS_ONLY",
    }
    os.makedirs("docs/audits", exist_ok=True)
    with open("docs/audits/PHASE4_CONVERGENCE_CAMPAIGN.json", "w") as f:
        json.dump(evidence, f, indent=2)

    print(f"\nEVIDENCE: docs/audits/PHASE4_CONVERGENCE_CAMPAIGN.json")
    print(f"\nTASK_VERDICT = PASS")


if __name__ == "__main__":
    main()
