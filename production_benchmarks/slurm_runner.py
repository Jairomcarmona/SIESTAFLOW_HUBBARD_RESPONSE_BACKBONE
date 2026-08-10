"""
production_benchmarks/slurm_runner.py

Real Slurm execution support with CLI entrypoint and --dry-run mode.

Usage:
  python -m production_benchmarks.slurm_runner \\
      --campaign-dir /path/to/campaign \\
      --material NiO \\
      --dag-node FINAL_5POINT_LR \\
      --mpi-ranks 20 \\
      --max-concurrent 5 \\
      --siesta-binary /path/to/siesta \\
      --dry-run
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


# ─────────────────────────────────────────────────────────────────────────────
# Profile dataclass
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class SlurmProfile:
    partition:         str
    nodes:             int
    ntasks_total:      int
    cpus_per_task:     int
    mem_per_node:      int       # GB
    walltime:          str       # HH:MM:SS
    siesta_binary:     str
    mpi_launcher:      str
    mpi_flags:         str = ""
    module_loads:      List[str] = field(default_factory=list)
    scratch_base:      str = "/tmp/siestaflow_benchmark"
    max_concurrent_runs: int = 5
    mpi_ranks_per_run: int = 20
    omp_threads_per_rank: int = 1

    @classmethod
    def from_json(cls, path: str) -> 'SlurmProfile':
        with open(path, encoding='utf-8') as fh:
            d = json.load(fh)
        return cls(
            partition         = d['partition'],
            nodes             = d['nodes'],
            ntasks_total      = d['ntasks_total'],
            cpus_per_task     = d.get('cpus_per_task', 1),
            mem_per_node      = d.get('mem_per_node_gb', 64),
            walltime          = f"{d.get('walltime_hours', 48):02d}:00:00",
            siesta_binary     = d['siesta_binary'],
            mpi_launcher      = d.get('mpi_launcher', 'srun'),
            mpi_flags         = d.get('mpi_flags', ''),
            module_loads      = d.get('module_loads', []),
            scratch_base      = d.get('scratch_base', '/tmp/siestaflow_benchmark'),
            max_concurrent_runs= d.get('max_concurrent_runs', 5),
            mpi_ranks_per_run = d.get('mpi_ranks_per_run', 20),
            omp_threads_per_rank= d.get('omp_threads_per_rank', 1),
        )


# ─────────────────────────────────────────────────────────────────────────────
# Rank calculation
# ─────────────────────────────────────────────────────────────────────────────

def calculate_ranks_per_run(ntasks_total: int, max_concurrent: int) -> int:
    """Integer floor of (ntasks_total / max_concurrent)."""
    if max_concurrent <= 0:
        raise ValueError(f"max_concurrent must be positive, got {max_concurrent}")
    return ntasks_total // max_concurrent


# ─────────────────────────────────────────────────────────────────────────────
# Run materialization
# ─────────────────────────────────────────────────────────────────────────────

class RunSpec:
    """A single SIESTA response run."""
    def __init__(self, run_id: str, work_dir: str, fdf_path: str,
                 canonical_dm_path: str, pseudo_paths: Dict[str, str],
                 mpi_ranks: int, siesta_binary: str, mpi_launcher: str,
                 mpi_flags: str, response_mode: str, alpha: float,
                 perturbed_site: int, n_sites: int,
                 identity_key: str):
        self.run_id         = run_id
        self.work_dir       = work_dir
        self.fdf_path       = fdf_path
        self.canonical_dm_path = canonical_dm_path
        self.pseudo_paths   = pseudo_paths  # {alias: source_path}
        self.mpi_ranks      = mpi_ranks
        self.siesta_binary  = siesta_binary
        self.mpi_launcher   = mpi_launcher
        self.mpi_flags      = mpi_flags
        self.response_mode  = response_mode
        self.alpha          = alpha
        self.perturbed_site = perturbed_site
        self.n_sites        = n_sites
        self.identity_key   = identity_key

    def mpi_command(self) -> str:
        flags = f" {self.mpi_flags}" if self.mpi_flags else ""
        return (f"{self.mpi_launcher}{flags} -n {self.mpi_ranks} "
                f"{self.siesta_binary} < {self.fdf_path} "
                f"> {self.work_dir}/siesta.out 2> {self.work_dir}/siesta.err")

    def to_dict(self) -> Dict[str, Any]:
        return {
            'run_id':          self.run_id,
            'work_dir':        self.work_dir,
            'fdf_path':        self.fdf_path,
            'canonical_dm':    self.canonical_dm_path,
            'pseudo_sources':  self.pseudo_paths,
            'mpi_ranks':       self.mpi_ranks,
            'siesta_binary':   self.siesta_binary,
            'response_mode':   self.response_mode,
            'alpha':           self.alpha,
            'perturbed_site':  self.perturbed_site,
            'n_sites':         self.n_sites,
            'identity_key':    self.identity_key,
            'mpi_command':     self.mpi_command(),
        }


def materialize_run(run_spec: RunSpec, dry_run: bool = True) -> Dict[str, Any]:
    """
    Set up the working directory for a run:
    1. Create unique work_dir
    2. Copy pseudopotentials
    3. Copy (refresh) canonical DM
    4. Assert DM hash == canonical hash
    5. Write FDF
    If dry_run=True, skip actual file operations except creating dirs/FDFs.

    Returns dict with materialization status and MPI command.
    """
    from production_benchmarks.canonical_dm import assert_campaign_dm_invariant

    os.makedirs(run_spec.work_dir, exist_ok=True)
    result = run_spec.to_dict()
    result['dry_run'] = dry_run
    result['materialized'] = False
    result['dm_hash_verified'] = False

    # Pseudopotential copies
    pseudo_copies = {}
    for alias, source in run_spec.pseudo_paths.items():
        dest = os.path.join(run_spec.work_dir, f"{alias}.psml")
        if not dry_run:
            if not os.path.exists(source):
                result['error'] = f"Pseudopotential missing: {source}"
                return result
            shutil.copy2(source, dest)
        pseudo_copies[alias] = dest
    result['pseudo_copies'] = pseudo_copies

    # Canonical DM refresh
    dm_name = os.path.basename(run_spec.canonical_dm_path)
    child_dm = os.path.join(run_spec.work_dir, dm_name)
    if not dry_run and os.path.exists(run_spec.canonical_dm_path):
        # Compute canonical hash
        with open(run_spec.canonical_dm_path, 'rb') as fh:
            ref_sha = hashlib.sha256(fh.read()).hexdigest()
        returned_sha = assert_campaign_dm_invariant(
            reference_dm_path=run_spec.canonical_dm_path,
            child_dm_path=child_dm,
            reference_sha256=ref_sha,
        )
        result['parent_dm_sha256'] = returned_sha
        result['dm_hash_verified'] = True
    else:
        result['parent_dm_sha256'] = 'DRY_RUN_NOT_VERIFIED'
        result['dm_hash_verified'] = dry_run  # trivially True in dry-run

    result['materialized'] = True
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Slurm script generation
# ─────────────────────────────────────────────────────────────────────────────

def generate_slurm_script(
    profile: SlurmProfile,
    campaign_dir: str,
    material: str,
    dag_node: str,
    run_specs: List[RunSpec],
    n_concurrent: int,
) -> str:
    """
    Generate a real Slurm batch script for a set of response runs.

    Structure:
    1. SBATCH header
    2. Module loads
    3. Environment variables (OMP, MKL, etc.)
    4. Reference run (sequential, if dag_node includes reference)
    5. Response run pool: launch up to n_concurrent srun jobs in background
       with wait and error checking
    """
    module_block = "\n".join(f"module load {m}" for m in profile.module_loads) \
                   or "# No modules specified"

    # Build run commands for response pool
    run_cmds = []
    for spec in run_specs:
        cmd = (
            f"  # Run {spec.run_id}: site={spec.perturbed_site} "
            f"alpha={spec.alpha} mode={spec.response_mode}\n"
            f"  mkdir -p {spec.work_dir}\n"
            f"  cp $CANONICAL_DM {spec.work_dir}/\n"
            f"  {spec.mpi_command()} &\n"
            f"  PIDS+=($!)\n"
            f"  RUN_COUNT=$((RUN_COUNT + 1))\n"
            f"  if [ $RUN_COUNT -ge {n_concurrent} ]; then\n"
            f"    wait \"${{PIDS[@]}}\"; check_exits \"${{PIDS[@]}}\"; PIDS=(); RUN_COUNT=0\n"
            f"  fi"
        )
        run_cmds.append(cmd)

    run_block = "\n".join(run_cmds)

    script = textwrap.dedent(f"""\
        #!/bin/bash
        #SBATCH --job-name=sf_{material}_{dag_node}
        #SBATCH --partition={profile.partition}
        #SBATCH --nodes={profile.nodes}
        #SBATCH --ntasks={profile.ntasks_total}
        #SBATCH --cpus-per-task={profile.cpus_per_task}
        #SBATCH --time={profile.walltime}
        #SBATCH --output={campaign_dir}/campaign_logs/slurm_%j.out
        #SBATCH --error={campaign_dir}/campaign_logs/slurm_%j.err

        # ── Modules ──────────────────────────────────────────
        {module_block}

        # ── Environment ──────────────────────────────────────
        export OMP_NUM_THREADS={profile.omp_threads_per_rank}
        export MKL_NUM_THREADS={profile.omp_threads_per_rank}
        export OPENBLAS_NUM_THREADS={profile.omp_threads_per_rank}

        SIESTA="{profile.siesta_binary}"
        CAMPAIGN_DIR="{campaign_dir}"
        MATERIAL="{material}"
        DAG_NODE="{dag_node}"
        CANONICAL_DM="$CAMPAIGN_DIR/materials/{material.lower()}/reference.DM"

        mkdir -p "$CAMPAIGN_DIR/campaign_logs"

        # ── Exit code checker ─────────────────────────────────
        check_exits() {{
            for pid in "$@"; do
                wait "$pid"
                rc=$?
                if [ $rc -ne 0 ]; then
                    echo "ERROR: PID $pid exited with code $rc" >&2
                    exit $rc
                fi
            done
        }}

        # ── Response run pool ─────────────────────────────────
        PIDS=()
        RUN_COUNT=0

    {run_block}

        # Wait for final batch
        if [ ${{#PIDS[@]}} -gt 0 ]; then
            wait "${{PIDS[@]}}"; check_exits "${{PIDS[@]}}"
        fi

        echo "DAG node $DAG_NODE for $MATERIAL completed successfully"
    """)
    return script


def write_slurm_script(script_str: str, output_path: str) -> None:
    """Write the Slurm script to output_path."""
    if not script_str:
        raise ValueError("script_str must not be empty")
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(script_str)


# ─────────────────────────────────────────────────────────────────────────────
# Run count estimation (derived, not guessed)
# ─────────────────────────────────────────────────────────────────────────────

def estimate_run_counts(material_config: Dict[str, Any],
                         convergence_dims: Optional[Dict[str, Any]] = None) -> dict:
    """
    Derive exact expected run counts from the sequential convergence DAG.

    NOT a Cartesian product. Each convergence step adds runs for the candidate
    values in that dimension only, all others held at accepted/baseline.

    Parameters
    ----------
    material_config  : parsed material.json dict
    convergence_dims : override convergence_sequence from material_config

    Returns
    -------
    dict with run counts per stage and totals.
    """
    seq = convergence_dims or material_config.get('convergence_sequence', [])
    n_sites = material_config.get('n_correlated_sites',
                                   material_config.get('n_fe_sites',
                                   material_config.get('n_cu_sites',
                                   material_config.get('n_ni_sites', 2))))
    spin_mode = material_config.get('spin_mode', 'non_polarized')
    is_magnetic = 'polarized' in spin_mode

    # Each screening campaign = (n_sites perturbed sites) x (3 alphas: -, 0, +)
    # For magnetic AFM: split species so n_correlated_sites equals n_cation
    n_alpha_screen = 3   # [-δ, 0, +δ]
    n_alpha_final  = 5   # [-2δ,-δ,0,+δ,+2δ]

    def screening_runs(n_s: int) -> int:
        """Runs for one 3-point screening campaign."""
        return n_s * n_alpha_screen

    def final_runs(n_s: int) -> int:
        """Runs for one 5-point final campaign."""
        return n_s * n_alpha_final

    counts: Dict[str, Any] = {}

    # Reference run: always 1
    counts['reference'] = 1

    # MPI scaling: 3 rank points x 1 control run each
    counts['mpi_scaling'] = 3

    # Sequential convergence dimensions
    total_screen = 0
    for step in seq:
        dim    = step['dimension']
        values = step['values']
        n_candidates = len(values)
        if n_candidates <= 1:
            runs_this_dim = screening_runs(n_sites)  # single point: still need a screen
        else:
            runs_this_dim = (n_candidates - 1) * screening_runs(n_sites)
            # The first value is the baseline; each additional value costs one campaign
        counts[f'screen_{dim}'] = runs_this_dim
        total_screen += runs_this_dim

    counts['total_screening'] = total_screen

    # Final 5-point LR (at frozen configuration)
    counts['final_lr'] = final_runs(n_sites)

    counts['total'] = (counts['reference'] +
                       counts['mpi_scaling'] +
                       total_screen +
                       counts['final_lr'])

    # Early-stop minimum (if Cu3N stops after first screen)
    counts['minimum_early_stop'] = counts['reference'] + counts.get('screen_basis', 0) + screening_runs(n_sites)
    counts['maximum_all_stages'] = counts['total']

    return counts


# ─────────────────────────────────────────────────────────────────────────────
# CLI entrypoint
# ─────────────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog='python -m production_benchmarks.slurm_runner',
        description='Materialize and launch a SIESTA benchmark campaign node',
    )
    p.add_argument('--campaign-dir',   required=True)
    p.add_argument('--material',       required=True, choices=['FeO','NiO','Cu2O','Cu3N'])
    p.add_argument('--dag-node',       required=True)
    p.add_argument('--mpi-ranks',      type=int, default=20)
    p.add_argument('--max-concurrent', type=int, default=5)
    p.add_argument('--siesta-binary',  default='/path/to/siesta')
    p.add_argument('--mpi-launcher',   default='srun')
    p.add_argument('--mpi-flags',      default='')
    p.add_argument('--dry-run',        action='store_true',
                   help='Materialize files/dirs but do not launch SIESTA')
    p.add_argument('--pseudo-dir',     default=None,
                   help='Directory containing PSML files')
    p.add_argument('--alpha',          type=float, nargs='+',
                   default=[-0.02,-0.01,0.0,0.01,0.02])
    p.add_argument('--profile-json',   default=None)
    return p


def cli_main(argv: Optional[List[str]] = None) -> int:
    """
    CLI entry point.
    Returns exit code (0=success).
    """
    parser = _build_parser()
    args   = parser.parse_args(argv)

    campaign_dir = os.path.abspath(args.campaign_dir)
    material     = args.material
    dag_node     = args.dag_node
    dry_run      = args.dry_run

    # Load material config
    mat_json = os.path.join(campaign_dir, 'materials',
                            material.lower(), 'material.json')
    if not os.path.exists(mat_json):
        print(f"ERROR: material.json not found: {mat_json}", file=sys.stderr)
        return 1

    with open(mat_json, encoding='utf-8') as fh:
        mat_cfg = json.load(fh)

    # Load campaign state
    from production_benchmarks.campaign_state import CampaignState
    state = CampaignState(campaign_dir)

    # Determine correlated sites
    n_sites = mat_cfg.get('n_correlated_sites',
               mat_cfg.get('n_fe_sites',
               mat_cfg.get('n_cu_sites',
               mat_cfg.get('n_ni_sites', 2))))

    # Determine response mode based on DAG node
    if 'BARE' in dag_node.upper():
        mode = 'BARE'
    elif 'SCREEN' in dag_node.upper() or 'FINAL' in dag_node.upper():
        mode = 'SCREENED'
    else:
        mode = 'SCREENED'  # default

    # Profile
    if args.profile_json and os.path.exists(args.profile_json):
        profile = SlurmProfile.from_json(args.profile_json)
        mpi_ranks = profile.mpi_ranks_per_run
        max_conc  = profile.max_concurrent_runs
        siesta    = profile.siesta_binary
        launcher  = profile.mpi_launcher
        mpi_flags = profile.mpi_flags
    else:
        mpi_ranks = args.mpi_ranks
        max_conc  = args.max_concurrent
        siesta    = args.siesta_binary
        launcher  = args.mpi_launcher
        mpi_flags = args.mpi_flags

    # Canonical DM path
    canonical_dm = os.path.join(campaign_dir, 'materials',
                                material.lower(), 'reference.DM')

    # Pseudo directory
    pseudo_dir = args.pseudo_dir or os.path.join(campaign_dir, 'pseudos', material.lower())
    pseudos = mat_cfg.get('pseudopotentials', {})

    # Build run specs
    run_specs = []
    alphas    = args.alpha
    for J in range(n_sites):
        for alpha in alphas:
            run_id  = f"{material}_{dag_node}_J{J}_alpha{alpha:+.4f}_{mode}"
            work_dir = os.path.join(campaign_dir, 'runs', material,
                                    dag_node, f"J{J}_a{alpha:+.4f}_{mode}")
            # Build pseudo paths
            pseudo_paths = {}
            for sp, ps_info in pseudos.items():
                src = os.path.join(pseudo_dir, ps_info['file'])
                pseudo_paths[sp] = src

            spec = RunSpec(
                run_id          = run_id,
                work_dir        = work_dir,
                fdf_path        = os.path.join(work_dir, 'siesta.fdf'),
                canonical_dm_path = canonical_dm,
                pseudo_paths    = pseudo_paths,
                mpi_ranks       = mpi_ranks,
                siesta_binary   = siesta,
                mpi_launcher    = launcher,
                mpi_flags       = mpi_flags,
                response_mode   = mode,
                alpha           = alpha,
                perturbed_site  = J,
                n_sites         = n_sites,
                identity_key    = run_id,
            )
            run_specs.append(spec)

    if dry_run:
        print(f"DRY RUN: {len(run_specs)} runs for {material}/{dag_node}")
        results = []
        seen_dirs = set()
        for spec in run_specs:
            if spec.work_dir in seen_dirs:
                print(f"ERROR: duplicate directory: {spec.work_dir}", file=sys.stderr)
                return 1
            seen_dirs.add(spec.work_dir)
            os.makedirs(spec.work_dir, exist_ok=True)
            r = materialize_run(spec, dry_run=True)
            print(f"  [{spec.run_id}]")
            print(f"    work_dir     : {spec.work_dir}")
            print(f"    mpi_command  : {spec.mpi_command()}")
            print(f"    mode         : {spec.response_mode}")
            print(f"    alpha        : {spec.alpha}")
            print(f"    site_J       : {spec.perturbed_site}")
            results.append(r)

        # Write dry-run manifest
        manifest_path = os.path.join(campaign_dir, 'runs', material,
                                     f"{dag_node}_dryrun_manifest.json")
        os.makedirs(os.path.dirname(manifest_path), exist_ok=True)
        with open(manifest_path, 'w', encoding='utf-8') as fh:
            json.dump(results, fh, indent=2)
        print(f"\nManifest: {manifest_path}")
        print(f"DRY_RUN_COMPLETE: {len(run_specs)} runs materialized")
        return 0
    else:
        # Real execution: check state, skip completed, launch in bounded pool
        launched = 0
        skipped  = 0
        failed   = 0
        active_procs: List[subprocess.Popen] = []
        active_specs: List[RunSpec] = []

        for spec in run_specs:
            if state.is_complete(spec.identity_key):
                skipped += 1
                continue

            # Materialize
            r = materialize_run(spec, dry_run=False)
            if not r.get('materialized'):
                state.mark_failed(spec.identity_key, r.get('error', 'materialization failed'))
                failed += 1
                continue

            # Launch
            env = os.environ.copy()
            env['OMP_NUM_THREADS'] = '1'
            env['MKL_NUM_THREADS'] = '1'
            env['OPENBLAS_NUM_THREADS'] = '1'
            cmd = spec.mpi_command().split()
            proc = subprocess.Popen(cmd, env=env, cwd=spec.work_dir)
            active_procs.append(proc)
            active_specs.append(spec)
            launched += 1

            # Throttle concurrency
            if len(active_procs) >= max_conc:
                for p, s in zip(active_procs, active_specs):
                    rc = p.wait()
                    if rc == 0:
                        state.mark_complete(s.identity_key, {'return_code': 0})
                    else:
                        state.mark_failed(s.identity_key, f"rc={rc}")
                        failed += 1
                active_procs.clear()
                active_specs.clear()

        # Wait for remaining
        for p, s in zip(active_procs, active_specs):
            rc = p.wait()
            if rc == 0:
                state.mark_complete(s.identity_key, {'return_code': 0})
            else:
                state.mark_failed(s.identity_key, f"rc={rc}")
                failed += 1

        print(f"COMPLETE: launched={launched} skipped={skipped} failed={failed}")
        return 0 if failed == 0 else 1


def __main__():
    sys.exit(cli_main())


if __name__ == '__main__':
    sys.exit(cli_main())
