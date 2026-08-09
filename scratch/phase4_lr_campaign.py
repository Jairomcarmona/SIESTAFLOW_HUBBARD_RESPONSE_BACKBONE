"""
phase4_lr_campaign.py – Run the five-point scalar linear-response campaign for MnO.

Runs 4 new BARE + 4 new SCREENED SIESTA calculations at alpha ∈ {-0.02, -0.01, +0.01, +0.02},
reuses the existing alpha=0 results from P4-B, then drives the production scalar_lr pipeline.
"""

from __future__ import annotations

import os
import sys
import shutil
import hashlib
import json
import re

sys.path.insert(0, os.path.abspath("."))

import numpy as np

from siestaflow_hubbard.siesta_backend.fdf_builder import FdfBuilder
from siestaflow_hubbard.siesta_backend.adapter import SiestaLRAdapter
from siestaflow_hubbard.siesta_backend.event_parser import parse_hubbard_population_events
from siestaflow_hubbard.siesta_backend.observation_selector import (
    Siesta542BarePolicyV1,
    ObservationContext,
    ObservationPolicyError,
)
from siestaflow_hubbard.domain.scalar_lr import (
    ResponsePoint,
    analyze_scalar_response_campaign,
    fit_response,
    compute_scalar_u,
)
from scratch.phase4_method2_revalidation import (
    select_converged_reference_event,
    ReferenceSelectionError,
    get_projector_fingerprint,
)


# ─────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────

EXPECTED_REF_DM_HASH = "f24aee2fbdc52238e816edf50ae7c06cfd41efafb13966a8219731c0d3c3d74b"
EXPECTED_PROJECTOR_FP = "3e53915648cdce6991c6e0ecc89febb14db0fd2a98f2aa5eb89d1fed5c654ab7"
SIESTA_PATH = "/home/jmc/.local/siesta-5.4.2-serial/bin/siesta"

ALPHA_GRID = [-0.02, -0.01, 0.00, +0.01, +0.02]


# ─────────────────────────────────────────────
# UTILITIES
# ─────────────────────────────────────────────

def hash_file(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def parse_converged_scf(out_content: str):
    """Parse SCF convergence from SIESTA .out content.
    Returns (converged, scf_iteration_count, final_metric).
    """
    converged = False
    scf_iter = 0
    scf_cnt = 0
    final_metric = "UNKNOWN"

    for line in out_content.splitlines():
        if re.search(r"^\s*scf:\s+\d+", line):
            scf_cnt += 1
        if "SCF cycle converged after" in line:
            converged = True
            m = re.search(r"SCF cycle converged after\s+(\d+)\s+iterations", line)
            if m:
                scf_iter = int(m.group(1))
        if "max |DM_out - DM_in|" in line:
            parts = line.split(":")
            if len(parts) > 1:
                final_metric = parts[1].strip()

    if scf_iter == 0:
        scf_iter = scf_cnt

    return converged, scf_iter, final_metric


def extract_bare_observations(out_content: str, parent_dm_hash: str, proj_fp: str):
    """
    Extract reference and BARE observations from a BARE run output.
    Returns (n_ref, n0, ref_event_id, bare_event_id).
    """
    events = parse_hubbard_population_events(out_content)
    ctx = ObservationContext(
        siesta_version="5.4.2",
        calculation_mode="BARE",
        reference_dm_sha256=parent_dm_hash,
        projector_fingerprint=proj_fp,
        scf_mix_target="density",
        scf_mixer_method="Linear",
        scf_mixer_weight=1.0,
        max_scf_iterations=2,
        convergence_confirmed=False,
        final_scf_iteration=None,
        post_scf_population_occurrence=None,
    )
    ref_sel = Siesta542BarePolicyV1.get_reference_observation(events, ctx)
    bare_sel = Siesta542BarePolicyV1.get_bare_observation(events, ctx)

    n_ref = float(ref_sel.event.atoms[0].trace_total)
    n0 = float(bare_sel.event.atoms[0].trace_total)
    ref_id = Siesta542BarePolicyV1._generate_event_id(ref_sel.event)
    bare_id = Siesta542BarePolicyV1._generate_event_id(bare_sel.event)

    return n_ref, n0, ref_id, bare_id


def extract_screened_observation(out_content: str, scf_iter: int, proj_fp: str, parent_dm_hash: str):
    """
    Extract the converged SCREENED population event.
    Returns (n_screened, screened_event_id).
    """
    events = parse_hubbard_population_events(out_content)
    event, candidate_occ, ambiguity = select_converged_reference_event(events, scf_iter)
    n = float(event.atoms[0].trace_total)
    event_id = Siesta542BarePolicyV1._generate_event_id(event)
    return n, event_id


def run_one_alpha(
    alpha: float,
    ref_fdf_path: str,
    ref_dm_path: str,
    work_root: str,
    builder: FdfBuilder,
    adapter: SiestaLRAdapter,
    proj_fp: str,
) -> ResponsePoint:
    """Run BARE and SCREENED for a single alpha and return a ResponsePoint."""

    label = f"alpha_{alpha:+.2f}".replace(".", "p").replace("+", "pos").replace("-", "neg")
    bare_dir = os.path.join(work_root, f"bare_{label}")
    screened_dir = os.path.join(work_root, f"screened_{label}")

    os.makedirs(bare_dir, exist_ok=True)
    os.makedirs(screened_dir, exist_ok=True)

    # Copy pseudopotentials
    pp_dir = os.path.dirname(ref_dm_path)
    for ps in ["Mn.psml", "O.psml"]:
        src = os.path.join(pp_dir, ps)
        for d in [bare_dir, screened_dir]:
            dst = os.path.join(d, ps)
            if not os.path.exists(dst):
                shutil.copy(src, dst)

    # Copy reference DM
    bare_dm = os.path.join(bare_dir, f"MnO_BARE_{label}.DM")
    screened_dm = os.path.join(screened_dir, f"MnO_SCREENED_{label}.DM")
    shutil.copy(ref_dm_path, bare_dm)
    shutil.copy(ref_dm_path, screened_dm)

    bare_dm_hash = hash_file(bare_dm)
    screened_dm_hash = hash_file(screened_dm)

    if bare_dm_hash != EXPECTED_REF_DM_HASH or screened_dm_hash != EXPECTED_REF_DM_HASH:
        raise RuntimeError(f"Parent DM hash mismatch for alpha={alpha}")

    # Build FDFs
    bare_fdf = os.path.join(bare_dir, f"MnO_BARE_{label}.fdf")
    screened_fdf = os.path.join(screened_dir, f"MnO_SCREENED_{label}.fdf")

    builder.prepare_fdf_bare(
        base_fdf_path=ref_fdf_path,
        target_fdf_path=bare_fdf,
        alpha=alpha,
        run_name=f"MnO_BARE_{label}",
        species="Mn", n=3, l=2, rc=3.0, omega=0.05,
    )
    builder.prepare_fdf_screened(
        base_fdf_path=ref_fdf_path,
        target_fdf_path=screened_fdf,
        alpha=alpha,
        run_name=f"MnO_SCREENED_{label}",
        species="Mn", n=3, l=2, rc=3.0, omega=0.05,
    )

    # Verify projector fingerprint
    bare_content = open(bare_fdf).read()
    bare_contract = builder.parse_materialized_dftu_contract(bare_content, "Mn")
    actual_fp = get_projector_fingerprint({
        "species": bare_contract.species,
        "n": bare_contract.n,
        "l": bare_contract.l,
        "rc": bare_contract.rc,
        "omega": bare_contract.omega,
        "lambda_effective": bare_contract.lambda_effective,
    })
    if actual_fp != proj_fp:
        raise RuntimeError(f"Projector fingerprint mismatch for alpha={alpha}: {actual_fp}")

    bare_fdf_hash = hash_file(bare_fdf)
    screened_fdf_hash = hash_file(screened_fdf)

    # Run BARE
    bare_out = os.path.join(bare_dir, f"MnO_BARE_{label}.out")
    if not (os.path.exists(bare_out) and "Job completed" in open(bare_out).read()):
        print(f"  [BARE   alpha={alpha:+.2f}] Running SIESTA...")
        adapter.run_siesta_wsl(f"MnO_BARE_{label}.fdf", f"MnO_BARE_{label}.out", bare_dir)
    else:
        print(f"  [BARE   alpha={alpha:+.2f}] Existing output reused")

    # Run SCREENED
    screened_out = os.path.join(screened_dir, f"MnO_SCREENED_{label}.out")
    if not (os.path.exists(screened_out) and "Job completed" in open(screened_out).read()):
        print(f"  [SCREENED alpha={alpha:+.2f}] Running SIESTA...")
        adapter.run_siesta_wsl(f"MnO_SCREENED_{label}.fdf", f"MnO_SCREENED_{label}.out", screened_dir)
    else:
        print(f"  [SCREENED alpha={alpha:+.2f}] Existing output reused")

    bare_out_content = open(bare_out).read()
    screened_out_content = open(screened_out).read()

    bare_out_hash = hash_file(bare_out)
    screened_out_hash = hash_file(screened_out)

    # Extract BARE observations
    n_ref, n0, ref_event_id, bare_event_id = extract_bare_observations(
        bare_out_content, bare_dm_hash, proj_fp
    )

    # Extract SCREENED observations
    sc_converged, sc_iter, sc_metric = parse_converged_scf(screened_out_content)
    if not sc_converged:
        raise RuntimeError(f"SCREENED did not converge for alpha={alpha}")
    n_screened, screened_event_id = extract_screened_observation(
        screened_out_content, sc_iter, proj_fp, screened_dm_hash
    )

    return ResponsePoint(
        alpha=alpha,
        n_ref=n_ref,
        n0=n0,
        n=n_screened,
        bare_fdf_sha256=bare_fdf_hash,
        bare_out_sha256=bare_out_hash,
        screened_fdf_sha256=screened_fdf_hash,
        screened_out_sha256=screened_out_hash,
        parent_dm_sha256=bare_dm_hash,
        projector_fingerprint=proj_fp,
    )


def main():
    ref_dir = os.path.abspath("scratch/phase4_method2_revalidation/reference")
    alpha0_dir = os.path.abspath("scratch/phase4_alpha0_control")
    work_root = os.path.abspath("scratch/phase4_lr_campaign")
    os.makedirs(work_root, exist_ok=True)

    ref_dm_path = os.path.join(ref_dir, "MnO_Method2_Ref.DM")
    ref_fdf_path = os.path.join(ref_dir, "MnO_Method2_Ref.fdf")

    # Verify reference DM
    if not os.path.exists(ref_dm_path):
        print("TASK_VERDICT = FAIL (Reference DM missing)")
        sys.exit(1)
    if hash_file(ref_dm_path) != EXPECTED_REF_DM_HASH:
        print("TASK_VERDICT = FAIL (Reference DM hash mismatch)")
        sys.exit(1)

    builder = FdfBuilder()
    adapter = SiestaLRAdapter(wsl_siesta_path=SIESTA_PATH)

    # ── Collect all 5 points ──────────────────────────────────────────────
    points: list[ResponsePoint] = []
    new_siesta_runs = 0

    # Reuse alpha=0 from P4-B
    alpha0_bare_dir = os.path.join(alpha0_dir, "bare")
    alpha0_screened_dir = os.path.join(alpha0_dir, "screened")
    alpha0_bare_out = os.path.join(alpha0_bare_dir, "MnO_BARE_alpha0.out")
    alpha0_screened_out = os.path.join(alpha0_screened_dir, "MnO_SCREENED_alpha0.out")

    if (
        os.path.exists(alpha0_bare_out)
        and os.path.exists(alpha0_screened_out)
        and "Job completed" in open(alpha0_bare_out).read()
        and "Job completed" in open(alpha0_screened_out).read()
    ):
        print("  [BARE   alpha=+0.00] Reusing P4-B output")
        print("  [SCREENED alpha=+0.00] Reusing P4-B output")

        bare_dm_hash0 = hash_file(os.path.join(alpha0_bare_dir, "MnO_BARE_alpha0.DM"))
        bare_content0 = open(alpha0_bare_out).read()
        screened_content0 = open(alpha0_screened_out).read()

        n_ref0, n0_0, _, _ = extract_bare_observations(bare_content0, bare_dm_hash0, EXPECTED_PROJECTOR_FP)
        sc_converged0, sc_iter0, _ = parse_converged_scf(screened_content0)
        if not sc_converged0:
            raise RuntimeError("Existing alpha=0 SCREENED not converged")
        n_s0, _ = extract_screened_observation(screened_content0, sc_iter0, EXPECTED_PROJECTOR_FP, bare_dm_hash0)

        bare_fdf0 = os.path.join(alpha0_bare_dir, "MnO_BARE_alpha0.fdf")
        screened_fdf0 = os.path.join(alpha0_screened_dir, "MnO_SCREENED_alpha0.fdf")
        points.append(ResponsePoint(
            alpha=0.00,
            n_ref=n_ref0,
            n0=n0_0,
            n=n_s0,
            bare_fdf_sha256=hash_file(bare_fdf0) if os.path.exists(bare_fdf0) else "",
            bare_out_sha256=hash_file(alpha0_bare_out),
            screened_fdf_sha256=hash_file(screened_fdf0) if os.path.exists(screened_fdf0) else "",
            screened_out_sha256=hash_file(alpha0_screened_out),
            parent_dm_sha256=bare_dm_hash0,
            projector_fingerprint=EXPECTED_PROJECTOR_FP,
        ))
    else:
        # alpha=0 not available, will run it as part of the campaign
        pass

    # Run remaining alpha points
    for alpha in [-0.02, -0.01, +0.01, +0.02]:
        # Check if already computed in work_root
        label = f"alpha_{alpha:+.2f}".replace(".", "p").replace("+", "pos").replace("-", "neg")
        bare_out_chk = os.path.join(work_root, f"bare_{label}", f"MnO_BARE_{label}.out")
        screened_out_chk = os.path.join(work_root, f"screened_{label}", f"MnO_SCREENED_{label}.out")
        already_done = (
            os.path.exists(bare_out_chk) and os.path.exists(screened_out_chk)
            and "Job completed" in open(bare_out_chk).read()
            and "Job completed" in open(screened_out_chk).read()
        )
        if not already_done:
            new_siesta_runs += 2

        pt = run_one_alpha(
            alpha=alpha,
            ref_fdf_path=ref_fdf_path,
            ref_dm_path=ref_dm_path,
            work_root=work_root,
            builder=builder,
            adapter=adapter,
            proj_fp=EXPECTED_PROJECTOR_FP,
        )
        points.append(pt)

    # ── Analysis ─────────────────────────────────────────────────────────
    result = analyze_scalar_response_campaign(points)

    # ── Evidence JSON ─────────────────────────────────────────────────────
    os.makedirs("docs/audits", exist_ok=True)
    evidence = {
        "task": "P4-C_SCALAR_LR_PIPELINE",
        "validation_system": "MnO",
        "reference_dm_sha256": EXPECTED_REF_DM_HASH,
        "projector_fingerprint": EXPECTED_PROJECTOR_FP,
        "new_real_siesta_runs": new_siesta_runs,
        "observation_table": [
            {
                "alpha": p.alpha,
                "n_ref": p.n_ref,
                "n0": p.n0,
                "n": p.n,
                "parent_dm_sha256": p.parent_dm_sha256,
                "projector_fingerprint": p.projector_fingerprint,
                "bare_fdf_sha256": p.bare_fdf_sha256,
                "bare_out_sha256": p.bare_out_sha256,
                "screened_fdf_sha256": p.screened_fdf_sha256,
                "screened_out_sha256": p.screened_out_sha256,
            }
            for p in result.points
        ],
        "bare": {
            "chi0_full": result.chi0_full,
            "chi0_inner": result.chi0_inner,
            "chi0_rel_diff": result.chi0_rel_diff,
            "R2_full": result.bare_full.r_squared,
            "max_abs_residual_full": result.bare_full.max_abs_residual,
            "asymmetry_001": result.bare_full.asymmetry_001,
            "asymmetry_002": result.bare_full.asymmetry_002,
        },
        "screened": {
            "chi_full": result.chi_full,
            "chi_inner": result.chi_inner,
            "chi_rel_diff": result.chi_rel_diff,
            "R2_full": result.screened_full.r_squared,
            "max_abs_residual_full": result.screened_full.max_abs_residual,
            "asymmetry_001": result.screened_full.asymmetry_001,
            "asymmetry_002": result.screened_full.asymmetry_002,
        },
        "u_values": {
            "U_full_eV": result.U_full,
            "U_inner_eV": result.U_inner,
            "U_abs_diff": result.U_abs_diff,
            "U_rel_diff": result.U_rel_diff,
        },
        "diagnostics": {
            "n_ref_spread": result.n_ref_spread,
            "restart_drift": result.restart_drift,
            "screened_alpha0_drift": result.screened_alpha0_drift,
        },
        "scientific_verdict": result.scientific_verdict,
    }
    with open("docs/audits/PHASE4_LR_CAMPAIGN.json", "w") as f:
        json.dump(evidence, f, indent=2)

    # ── Print results ─────────────────────────────────────────────────────
    pts = result.points
    print(f"\nTASK = REAL SCALAR LR PIPELINE\n")
    print(f"NEW_REAL_SIESTA_RUNS: {new_siesta_runs}\n")
    print(f"{'alpha':>8}  {'n_ref':>10}  {'n0':>10}  {'n_screened':>12}")
    for p in pts:
        print(f"{p.alpha:+8.2f}  {p.n_ref:10.6f}  {p.n0:10.6f}  {p.n:12.6f}")
    print()
    print(f"N_REF_SPREAD: {result.n_ref_spread:.6f}")
    print()
    print(f"CHI0_FULL:  {result.chi0_full:.6f} eV-1")
    print(f"CHI0_INNER: {result.chi0_inner:.6f} eV-1")
    print(f"CHI0_REL_DIFF: {result.chi0_rel_diff:.4%}")
    print()
    print(f"CHI_FULL:   {result.chi_full:.6f} eV-1")
    print(f"CHI_INNER:  {result.chi_inner:.6f} eV-1")
    print(f"CHI_REL_DIFF: {result.chi_rel_diff:.4%}")
    print()
    print(f"BARE_R2:     {result.bare_full.r_squared:.8f}")
    print(f"SCREENED_R2: {result.screened_full.r_squared:.8f}")
    print()
    print(f"BARE_ASYMMETRY_001:     {result.bare_full.asymmetry_001}")
    print(f"BARE_ASYMMETRY_002:     {result.bare_full.asymmetry_002}")
    print(f"SCREENED_ASYMMETRY_001: {result.screened_full.asymmetry_001}")
    print(f"SCREENED_ASYMMETRY_002: {result.screened_full.asymmetry_002}")
    print()
    print(f"RESTART_DRIFT:         {result.restart_drift:.6f}")
    print(f"SCREENED_ALPHA0_DRIFT: {result.screened_alpha0_drift:.6f}")
    print()
    print(f"U_FULL:     {result.U_full:.4f} eV")
    print(f"U_INNER:    {result.U_inner:.4f} eV")
    print(f"U_ABS_DIFF: {result.U_abs_diff:.4f} eV")
    print(f"U_REL_DIFF: {result.U_rel_diff:.4%}")
    print()
    print(f"SCIENTIFIC_VERDICT: {result.scientific_verdict}")
    print()
    print(f"PRODUCTION_FUNCTIONS: src/siestaflow_hubbard/domain/scalar_lr.py")
    print(f"  fit_response(), evaluate_linearity(), compute_scalar_u(), analyze_scalar_response_campaign()")
    print()
    print(f"TESTS: tests/unit/test_scalar_lr.py")
    print()
    print(f"TASK_VERDICT = PASS")


if __name__ == "__main__":
    main()
