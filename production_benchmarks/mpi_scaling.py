"""
production_benchmarks/mpi_scaling.py

Real MPI scaling benchmark support.
generate_scaling_fdf: produces a proper bounded-SCF FDF.
parse_scaling_result: extracts timing from real SIESTA output.
recommend_mpi_config: derives optimal config from measured throughput.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class MPIScalingConfig:
    ranks_to_test:    List[int]
    n_scf_iterations: int
    material_label:   str
    results:          List[Dict[str, Any]] = field(default_factory=list)


def generate_scaling_fdf(base_fdf_content: str, n_scf_iters: int,
                          label: str) -> str:
    """
    Produce a benchmark FDF from base_fdf_content by:
    1. Clamping MaxSCFIterations to n_scf_iters
    2. Disabling DM write (no writeDM for benchmarking)
    3. Setting SystemLabel to label
    4. Disabling geometry optimization (MD.NumCGsteps 0)
    """
    if not base_fdf_content:
        raise ValueError("base_fdf_content must not be empty")
    if n_scf_iters < 1:
        raise ValueError(f"n_scf_iters must be >= 1, got {n_scf_iters}")

    content = base_fdf_content

    # Replace/set MaxSCFIterations
    if re.search(r'(?i)MaxSCFIterations', content):
        content = re.sub(r'(?i)(MaxSCFIterations\s+)\d+', f'MaxSCFIterations {n_scf_iters}', content)
    else:
        content += f'\nMaxSCFIterations {n_scf_iters}\n'

    # Replace/set SystemLabel
    if re.search(r'(?i)SystemLabel', content):
        content = re.sub(r'(?i)(SystemLabel\s+)\S+', f'SystemLabel {label}', content)
    else:
        content += f'\nSystemLabel {label}\n'

    # Disable DM write for benchmarking
    if re.search(r'(?i)WriteDM', content):
        content = re.sub(r'(?i)(WriteDM\s+)(true|yes|\.true\.|T)', 'WriteDM false', content)
    else:
        content += '\nWriteDM false\n'

    # Ensure no geometry optimization
    if re.search(r'(?i)MD\.NumCGsteps', content):
        content = re.sub(r'(?i)(MD\.NumCGsteps\s+)\d+', 'MD.NumCGsteps 0', content)
    else:
        content += '\nMD.NumCGsteps 0\n'

    header = (f'# MPI SCALING BENCHMARK FDF\n'
              f'# label: {label}\n'
              f'# MaxSCFIterations: {n_scf_iters}\n')

    return header + content


def parse_scaling_result(out_text: str) -> dict:
    """
    Extract timing information from a SIESTA output.
    """
    if not out_text:
        return {'parse_success': False, 'error': 'empty output'}

    result: Dict[str, Any] = {'parse_success': False}

    # Count SCF iterations: accepts "iscf =", "scf:", "scf_iter" etc.
    scf_matches = re.findall(r'(?i)(?:iscf\s*=\s*|scf:\s+)(\d+)', out_text)
    n_scf = len(scf_matches)
    result['n_scf_completed'] = n_scf

    # Per-SCF times
    scf_times = []
    for m in re.finditer(r'siesta:\s+iscf\s*=\s*\d+.*?Time\s*=\s*([\d.]+)', out_text):
        scf_times.append(float(m.group(1)))
    result['scf_times'] = scf_times

    # Total CPU time
    total_cpu = None
    m = re.search(r'siesta:\s+Total\s+cpu\s+time\s*[=:]\s*([\d.]+)', out_text, re.IGNORECASE)
    if m:
        total_cpu = float(m.group(1))

    # Total Wall time
    total_wall = None
    for pat in [
        r'(?i)elapsed.*?time\s*[=:]\s*([\d.]+)',
        r'(?i)wall.*?time\s*[=:]\s*([\d.]+)',
        r'(?i)real\s+time\s*[=:]\s*([\d.]+)',
    ]:
        m = re.search(pat, out_text)
        if m:
            total_wall = float(m.group(1))
            break

    result['total_walltime_s']  = total_wall
    result['total_cpu_s']       = total_cpu

    if scf_times:
        result['walltime_per_scf_s'] = float(sum(scf_times) / len(scf_times))
    elif total_wall is not None and n_scf > 0:
        result['walltime_per_scf_s'] = total_wall / n_scf
    else:
        result['walltime_per_scf_s'] = None

    # Memory
    m = re.search(r'(?i)memory\s+used\s*[=:]\s*([\d.]+)\s*(MB|GB|KB)', out_text)
    if m:
        val, unit = float(m.group(1)), m.group(2).upper()
        mem_mb = val * {'MB': 1, 'GB': 1024, 'KB': 1/1024}[unit]
        result['memory_mb'] = mem_mb
    else:
        result['memory_mb'] = None

    result['parse_success'] = True
    return result


def recommend_mpi_config(scaling_results: List[Dict[str, Any]]) -> dict:
    """
    Recommend MPI configuration based on measured scaling data.
    """
    if not scaling_results:
        return {
            'recommended_ranks_per_run': None,
            'max_concurrent_runs':       None,
            'efficiency_table':          [],
            'recommendation_basis':      'no_data',
            'status':                    'PENDING_MEASUREMENT',
            'MPI_RECOMMENDATION_STATUS': 'PENDING_MEASUREMENT',
        }

    usable = [r for r in scaling_results
              if r.get('walltime_per_scf_s') and r['walltime_per_scf_s'] > 0
              and r.get('n_ranks')]

    if not usable:
        return {
            'recommended_ranks_per_run': None,
            'max_concurrent_runs':       None,
            'efficiency_table':          [],
            'recommendation_basis':      'no_valid_measurements',
            'status':                    'PENDING_MEASUREMENT',
            'MPI_RECOMMENDATION_STATUS': 'PENDING_MEASUREMENT',
        }

    usable_sorted = sorted(usable, key=lambda r: r['n_ranks'])
    baseline_time = usable_sorted[0]['walltime_per_scf_s']
    baseline_ranks = usable_sorted[0]['n_ranks']

    table = []
    for r in usable_sorted:
        n = r['n_ranks']
        t = r['walltime_per_scf_s']
        ideal_speedup = n / baseline_ranks
        actual_speedup = baseline_time / t if t > 0 else 0
        efficiency = actual_speedup / ideal_speedup if ideal_speedup > 0 else 0
        throughput = 1.0 / t
        table.append({
            'n_ranks':          n,
            'walltime_per_scf': t,
            'speedup':          round(actual_speedup, 3),
            'parallel_efficiency': round(efficiency, 3),
            'throughput_scf_per_s': round(throughput, 6),
        })

    n_total = max(r['n_ranks'] for r in usable)
    best_entry = max(table, key=lambda e: e['throughput_scf_per_s'] * (n_total / e['n_ranks']))

    best_ranks = best_entry['n_ranks']
    max_concurrent = max(1, n_total // best_ranks)

    return {
        'recommended_ranks_per_run': int(best_ranks),
        'max_concurrent_runs':       int(max_concurrent),
        'efficiency_table':          table,
        'recommendation_basis':      'measured_throughput_maximization',
        'status':                    'MEASURED',
        'MPI_RECOMMENDATION_STATUS': 'MEASURED',
    }
