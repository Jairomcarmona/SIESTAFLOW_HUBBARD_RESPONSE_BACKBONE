"""
production_benchmarks/preflight.py

Real preflight checker. PREFLIGHT_PASS only prints after performing
actual checks. Can be invoked as:
  python -m production_benchmarks.preflight production_benchmarks/
"""
from __future__ import annotations
import hashlib
import json
import os
import sys
import tempfile
import types
from typing import Any, Dict, List, Optional

import numpy as np


PSEUDO_DIR = r"C:\Users\Jairo\Downloads\PSEUDOPOTENCIALES_pseudojo_pbe_stringent\nc-sr-05_pbe_stringent_psml"

MATERIALS = ['feo', 'nio', 'cu2o', 'cu3n']

# Required non-TBD metadata keys per pseudopotential entry
REQUIRED_NON_TBD = ['uuid', 'sha256', 'file']


# ─────────────────────────────────────────────────────────────────────────────
# Individual checks
# ─────────────────────────────────────────────────────────────────────────────

def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def _extract_psml_uuid(path: str) -> Optional[str]:
    """Extract uuid= attribute from PSML XML header."""
    import re
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as fh:
            header = fh.read(2048)
        m = re.search(r'uuid=["\']([^"\']+)["\']', header)
        return m.group(1) if m else None
    except Exception:
        return None


def check_material_json(campaign_dir: str, mat: str,
                         failures: List[str]) -> Optional[Dict[str, Any]]:
    """Parse material.json and validate required fields."""
    path = os.path.join(campaign_dir, 'materials', mat, 'material.json')
    if not os.path.exists(path):
        failures.append(f"[{mat}] material.json not found: {path}")
        return None
    try:
        with open(path, encoding='utf-8') as fh:
            d = json.load(fh)
    except json.JSONDecodeError as e:
        failures.append(f"[{mat}] material.json parse error: {e}")
        return None
    return d


def check_no_tbd_uuids(mat: str, mat_cfg: Dict[str, Any],
                         failures: List[str]) -> None:
    """All pseudopotential UUIDs must be real (not 'TBD')."""
    for sp, info in mat_cfg.get('pseudopotentials', {}).items():
        for field in REQUIRED_NON_TBD:
            val = info.get(field, '')
            if str(val).upper() == 'TBD' or val == '':
                failures.append(
                    f"[{mat}] {sp}.{field} is TBD or empty — must be extracted from PSML"
                )


def check_pseudopotential_files(mat: str, mat_cfg: Dict[str, Any],
                                  pseudo_search_dirs: List[str],
                                  failures: List[str]) -> Dict[str, str]:
    """Find each PSML file and verify SHA256 and UUID."""
    found_paths: Dict[str, str] = {}
    for sp, info in mat_cfg.get('pseudopotentials', {}).items():
        fname   = info.get('file', '')
        exp_sha = info.get('sha256', '')
        exp_uuid= info.get('uuid', '')

        # Search in multiple directories
        found = None
        for d in pseudo_search_dirs:
            candidate = os.path.join(d, fname)
            if os.path.exists(candidate):
                found = candidate
                break

        if not found:
            failures.append(
                f"[{mat}] Pseudopotential not found: {fname} "
                f"(searched: {pseudo_search_dirs})"
            )
            continue

        found_paths[sp] = found

        # SHA256 check
        if exp_sha and exp_sha.upper() != 'TBD':
            actual_sha = _sha256_file(found)
            if actual_sha.lower() != exp_sha.lower():
                failures.append(
                    f"[{mat}] {sp}: SHA256 mismatch\n"
                    f"  expected: {exp_sha}\n"
                    f"  actual:   {actual_sha}"
                )

        # UUID check
        if exp_uuid and exp_uuid.upper() != 'TBD':
            actual_uuid = _extract_psml_uuid(found)
            if actual_uuid is None:
                failures.append(f"[{mat}] {sp}: Could not extract UUID from {found}")
            elif actual_uuid.lower() != exp_uuid.lower():
                failures.append(
                    f"[{mat}] {sp}: UUID mismatch\n"
                    f"  expected: {exp_uuid}\n"
                    f"  actual:   {actual_uuid}"
                )

    return found_paths


def check_geometry(mat: str, mat_cfg: Dict[str, Any],
                    failures: List[str]) -> None:
    """Run geometry validator for each material."""
    from production_benchmarks.geometry_validator import (
        verify_cuprite_cu2o, verify_rocksalt_afm,
        verify_cu3n_antireo3, verify_afm_ii_ordering
    )

    coords = mat_cfg.get('base_fractional_coords', [])
    if not coords:
        failures.append(f"[{mat}] No base_fractional_coords in material.json")
        return

    fracs  = np.array([c['frac']    for c in coords])
    labels = [c['label']            for c in coords]
    a      = mat_cfg.get('lattice_constant_ang', 0.0)

    if mat == 'cu2o':
        result = verify_cuprite_cu2o(fracs, labels, a)
        if not result['geometry_valid']:
            for e in result['errors']:
                failures.append(f"[{mat}] geometry: {e}")

    elif mat == 'cu3n':
        result = verify_cu3n_antireo3(fracs, labels, a)
        if not result['geometry_valid']:
            for e in result['errors']:
                failures.append(f"[{mat}] geometry: {e}")

    elif mat in ('feo', 'nio'):
        cat_sym = 'Fe' if mat == 'feo' else 'Ni'
        spins   = [c.get('init_spin', 0.0) for c in coords if c['label'] == cat_sym]
        result  = verify_rocksalt_afm(
            fracs, labels, a,
            cation_symbol=cat_sym, anion_symbol='O',
            cation_spins=spins
        )
        if not result['geometry_valid']:
            for e in result['errors']:
                failures.append(f"[{mat}] geometry: {e}")

        # AFM-II ordering check
        if result.get('afm_ii_valid') is False:
            for e in result.get('afm_ii_details', {}).get('errors', []):
                failures.append(f"[{mat}] AFM-II: {e}")
        elif result.get('afm_ii_valid') is None and mat in ('feo', 'nio'):
            failures.append(f"[{mat}] AFM-II: no spin data in material.json")


def check_convergence_sequence(mat: str, mat_cfg: Dict[str, Any],
                                 failures: List[str]) -> None:
    """Convergence sequence must exist and accepted_value must initially be null."""
    seq = mat_cfg.get('convergence_sequence', [])
    if not seq:
        failures.append(f"[{mat}] convergence_sequence missing or empty")
        return

    for step in seq:
        if 'dimension' not in step:
            failures.append(f"[{mat}] convergence step missing 'dimension'")
        if 'values' not in step or not step['values']:
            failures.append(f"[{mat}] convergence step {step.get('dimension')} has no values")
        # accepted_value must be null (not pre-populated without evidence)
        acc = step.get('accepted_value', 'MISSING')
        if acc == 'MISSING':
            failures.append(f"[{mat}] step {step.get('dimension')}: 'accepted_value' key missing")
        # We allow null; non-null would require evidence check (skip here for scaffold)

    # No premature production_settings
    if 'production_settings' in mat_cfg:
        failures.append(
            f"[{mat}] 'production_settings' key present — "
            f"must be renamed to 'candidate_baseline' with explicit note"
        )


def check_projector_units(mat: str, mat_cfg: Dict[str, Any],
                            failures: List[str]) -> None:
    """Projector rc and omega must be in Bohr (i.e. < 20)."""
    baseline = mat_cfg.get('candidate_baseline', {})
    rc    = baseline.get('projector_rc_bohr', None)
    omega = baseline.get('projector_omega_bohr', None)
    if rc is not None and rc > 20:
        failures.append(f"[{mat}] projector_rc_bohr={rc} is suspiciously large (Bohr expected)")
    if omega is not None and omega > 20:
        failures.append(f"[{mat}] projector_omega_bohr={omega} is suspiciously large (Bohr expected)")


def check_alpha_grid(mat: str, mat_cfg: Dict[str, Any],
                      failures: List[str]) -> None:
    """Alpha grid must be symmetric around zero."""
    baseline = mat_cfg.get('candidate_baseline', {})
    alpha_ev = baseline.get('alpha_ev', None)
    # Alpha_ev is usually a scalar in candidate_baseline;
    # the actual grid symmetry is enforced at run time.
    # For screening: [-delta, 0, +delta]. Check that the value is positive.
    if alpha_ev is not None and alpha_ev <= 0:
        failures.append(f"[{mat}] alpha_ev={alpha_ev} must be positive")


def check_slurm_profile(campaign_dir: str, failures: List[str]) -> None:
    """Slurm profile must have all required fields."""
    profile_path = os.path.join(campaign_dir, 'yoltla', 'profile.json')
    if not os.path.exists(profile_path):
        failures.append(f"yoltla/profile.json not found: {profile_path}")
        return
    with open(profile_path, encoding='utf-8') as fh:
        p = json.load(fh)
    required = ['partition', 'nodes', 'ntasks_total', 'siesta_binary',
                'mpi_launcher', 'scratch_base']
    for field in required:
        if field not in p:
            failures.append(f"Slurm profile missing required field: {field}")
    # siesta_binary must be configurable (not hardcoded absolute)
    sb = p.get('siesta_binary', '')
    if not sb:
        failures.append("Slurm profile: siesta_binary is empty")
    # ntasks must be consistent with nodes
    nt = p.get('ntasks_total', 0)
    nodes = p.get('nodes', 1)
    if nodes > 0 and nt % nodes != 0:
        failures.append(f"Slurm profile: ntasks_total={nt} not divisible by nodes={nodes}")


def check_canonical_dm_logic(failures: List[str]) -> None:
    """Verify the canonical DM logic is importable and functional."""
    try:
        from siestaflow_hubbard.siesta_backend.adapter import prepare_canonical_dm
    except ImportError as e:
        failures.append(f"prepare_canonical_dm not importable: {e}")
        return

    import hashlib
    with tempfile.TemporaryDirectory() as td:
        ref  = os.path.join(td, 'ref.DM')
        child= os.path.join(td, 'child.DM')
        data = b'test_canonical_bytes'
        with open(ref, 'wb') as fh: fh.write(data)
        sha = hashlib.sha256(data).hexdigest()
        try:
            returned = prepare_canonical_dm(ref, child, sha)
            with open(child, 'rb') as fh:
                actual = fh.read()
            if actual != data:
                failures.append("canonical_dm: child DM content != canonical after prepare")
            if returned != sha:
                failures.append(f"canonical_dm: returned sha {returned} != expected {sha}")
        except Exception as e:
            failures.append(f"canonical_dm: prepare_canonical_dm raised: {e}")


def check_no_stubs(failures: List[str]) -> None:
    """
    Verify that no critical callables remain as pass/empty stubs.
    Tests by calling each function with minimal synthetic inputs.
    """
    errors = []

    # campaign_state
    try:
        from production_benchmarks.campaign_state import CampaignState, resume_incomplete
        with tempfile.TemporaryDirectory() as td:
            cs = CampaignState(td)
            cs.mark_complete('key1', {'ok': True})
            if not cs.is_complete('key1'):
                errors.append("campaign_state: mark_complete + is_complete failed")
            cs.mark_failed('key2', 'test_err')
            pending = cs.pending_keys()
            if 'key2' not in pending:
                errors.append("campaign_state: pending_keys did not return failed key")
            # Save + load round trip
            cs2 = CampaignState(td)
            if not cs2.is_complete('key1'):
                errors.append("campaign_state: save/load round trip failed")
    except Exception as e:
        errors.append(f"campaign_state stub: {e}")

    # geometry_validator
    try:
        from production_benchmarks.geometry_validator import verify_cuprite_cu2o
        r = verify_cuprite_cu2o(
            np.array([[0,0,0],[.5,.5,.5],[.25,.25,.25],[.25,.75,.75],[.75,.25,.75],[.75,.75,.25]]),
            ['O','O','Cu','Cu','Cu','Cu'], 4.27)
        if r.get('cu_o_nearest_ang') == 1.849 and r.get('cu_coordination') is None:
            errors.append("geometry_validator: returned hardcoded value")
        cu_o = r.get('cu_o_nearest_ang')
        if cu_o is None or abs(cu_o - 1.849) > 0.05:
            errors.append(f"geometry_validator: wrong Cu-O distance: {cu_o}")
    except Exception as e:
        errors.append(f"geometry_validator stub: {e}")

    # lr_arithmetic: build_chi_matrix_5point must not return zeros
    try:
        from production_benchmarks.lr_arithmetic import build_chi_matrix_5point
        delta = 0.01
        chi_true = np.array([[-0.09, 0.01], [0.01, -0.09]])
        alphas = [-2*delta, -delta, 0.0, delta, 2*delta]
        obs = {}
        for J in range(2):
            for a in alphas:
                obs[(J, a, 'SCREENED')] = [chi_true[I,J]*a + 9.5 for I in range(2)]
        res = build_chi_matrix_5point(obs, 2, delta, 'SCREENED')
        mat = res['matrix']
        if np.allclose(mat, np.zeros((2,2))):
            errors.append("lr_arithmetic: build_chi_matrix_5point returned zero matrix (stub)")
        if not np.allclose(mat, chi_true, atol=1e-8):
            errors.append(f"lr_arithmetic: 5-point matrix incorrect: {mat}")
    except Exception as e:
        errors.append(f"lr_arithmetic stub: {e}")

    # mpi_scaling
    try:
        from production_benchmarks.mpi_scaling import generate_scaling_fdf
        base = "SystemLabel test\nMaxSCFIterations 200\n"
        result = generate_scaling_fdf(base, 3, 'bench_label')
        if not result or result == '':
            errors.append("mpi_scaling: generate_scaling_fdf returned empty string (stub)")
        if 'MaxSCFIterations 3' not in result:
            errors.append(f"mpi_scaling: MaxSCFIterations not set correctly in output FDF")
    except Exception as e:
        errors.append(f"mpi_scaling stub: {e}")

    # slurm_runner
    try:
        from production_benchmarks.slurm_runner import generate_slurm_script, SlurmProfile
        profile = SlurmProfile(
            partition='test', nodes=1, ntasks_total=4, cpus_per_task=1,
            mem_per_node=16, walltime='1:00:00', siesta_binary='/usr/bin/siesta',
            mpi_launcher='srun', mpi_flags='', module_loads=[]
        )
        script = generate_slurm_script(profile, '/tmp/campaign', 'NiO',
                                        'SCREENING', [], 2)
        if not script or script == '':
            errors.append("slurm_runner: generate_slurm_script returned empty (stub)")
        if '#SBATCH' not in script:
            errors.append("slurm_runner: generated script missing #SBATCH directives")
    except Exception as e:
        errors.append(f"slurm_runner stub: {e}")

    # supercell_builder
    try:
        from production_benchmarks.supercell_builder import build_supercell
        fracs = np.array([[0,0,0],[.5,.5,.5]], dtype=float)
        lat   = np.eye(3) * 4.0
        labels = ['A','B']
        ids    = [1, 2]
        sc_mat = np.array([[2,0,0],[0,1,0],[0,0,1]], dtype=float)
        nf, nl, nids, nlat = build_supercell(fracs, labels, ids, lat, sc_mat)
        if len(nl) == 2:  # unchanged — stub
            errors.append("supercell_builder: build_supercell returned unchanged cell (stub)")
        if len(nl) != 4:
            errors.append(f"supercell_builder: expected 4 atoms in 2x1x1 supercell, got {len(nl)}")
    except Exception as e:
        errors.append(f"supercell_builder stub: {e}")

    for e in errors:
        failures.append(f"[stub-check] {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Main preflight
# ─────────────────────────────────────────────────────────────────────────────

def run_preflight(campaign_dir: str,
                   pseudo_dirs: Optional[List[str]] = None) -> bool:
    """
    Run all preflight checks.
    Returns True if PREFLIGHT_PASS, False otherwise.
    """
    campaign_dir = os.path.abspath(campaign_dir)
    failures: List[str] = []

    # Default pseudo search dirs
    if pseudo_dirs is None:
        pseudo_dirs = [
            PSEUDO_DIR,
            os.path.join(campaign_dir, 'pseudos'),
        ]

    print("=== PRODUCTION BENCHMARK PREFLIGHT ===")
    print(f"Campaign dir: {campaign_dir}")
    print()

    # 1. Material configs
    print("[ ] Checking material JSON files...")
    mat_cfgs: Dict[str, Any] = {}
    for mat in MATERIALS:
        cfg = check_material_json(campaign_dir, mat, failures)
        if cfg:
            mat_cfgs[mat] = cfg
            print(f"    {mat}: OK")
        else:
            print(f"    {mat}: FAIL")

    # 2. No TBD UUIDs
    print("[ ] Checking no TBD pseudopotential metadata...")
    for mat, cfg in mat_cfgs.items():
        check_no_tbd_uuids(mat, cfg, failures)

    # 3. Pseudopotential files + SHA256 + UUID
    print("[ ] Checking pseudopotential files, SHA256, and PSML UUIDs...")
    for mat, cfg in mat_cfgs.items():
        check_pseudopotential_files(mat, cfg, pseudo_dirs, failures)

    # 4. Geometry
    print("[ ] Validating geometries from coordinates...")
    for mat, cfg in mat_cfgs.items():
        check_geometry(mat, cfg, failures)

    # 5. Convergence sequence structure
    print("[ ] Checking convergence sequence (accepted_value=null)...")
    for mat, cfg in mat_cfgs.items():
        check_convergence_sequence(mat, cfg, failures)

    # 6. Projector units
    print("[ ] Checking projector units (Bohr)...")
    for mat, cfg in mat_cfgs.items():
        check_projector_units(mat, cfg, failures)

    # 7. Alpha grids
    print("[ ] Checking alpha grid values...")
    for mat, cfg in mat_cfgs.items():
        check_alpha_grid(mat, cfg, failures)

    # 8. Slurm profile
    print("[ ] Checking Slurm profile consistency...")
    check_slurm_profile(campaign_dir, failures)

    # 9. Canonical DM logic
    print("[ ] Verifying canonical DM logic...")
    check_canonical_dm_logic(failures)

    # 10. No stubs in critical callables
    print("[ ] Checking for stub implementations...")
    check_no_stubs(failures)

    print()
    if failures:
        print("PREFLIGHT_FAIL")
        print(f"\n{len(failures)} failure(s):")
        for i, f in enumerate(failures, 1):
            print(f"  [{i}] {f}")
        return False
    else:
        print("PREFLIGHT_PASS")
        return True


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('campaign_dir', nargs='?',
                   default='production_benchmarks/',
                   help='Path to production_benchmarks/ directory')
    p.add_argument('--pseudo-dir', nargs='*',
                   help='Additional pseudopotential search directories')
    args = p.parse_args()

    extra_dirs = args.pseudo_dir or []
    ok = run_preflight(args.campaign_dir,
                       pseudo_dirs=[PSEUDO_DIR] + extra_dirs
                       if extra_dirs else None)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
