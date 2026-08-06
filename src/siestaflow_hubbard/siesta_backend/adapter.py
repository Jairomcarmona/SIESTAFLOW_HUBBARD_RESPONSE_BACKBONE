import os
import re
import subprocess
from typing import Dict, Any, List, Optional
import numpy as np

from siestaflow_hubbard.domain.exceptions import (
    SiestaParserError,
    SemanticValidationFailure,
    ChecksumFailure,
    ExecutionError,
)
from siestaflow_hubbard.synthetic_backend.population_generator import OccupationRecord
from siestaflow_hubbard.domain.interfaces import BaseBackendAdapter


class SiestaLRAdapter(BaseBackendAdapter):
    """Formal backend adapter for SIESTA 5.4.2 Linear Response calculations."""

    def __init__(self, wsl_siesta_path: str = "/home/jmc/.local/siesta-5.4.2-openmpi/bin/siesta"):
        self.wsl_siesta_path = wsl_siesta_path

    def run_siesta_wsl(self, fdf_filename: str, out_filename: str, cwd: str) -> None:
        """Runs SIESTA inside WSL directly (serial)."""
        wsl_cwd = "/mnt/c" + cwd[2:].replace("\\", "/")
        cmd = f'wsl bash -c "cd {wsl_cwd} && {self.wsl_siesta_path} < {fdf_filename} > {out_filename}"'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            raise ExecutionError(f"SIESTA execution failed with return code {result.returncode}:\n{result.stderr}")

    def run_siesta_slurm(self, fdf_filename: str, out_filename: str, cwd: str = ".", n_procs: int = 4) -> None:
        """
        Runs SIESTA via SLURM or MPI, supporting both native Linux HPC clusters (like Yoltla)
        and WSL development environments. Automatically detects active SLURM job allocations.
        """
        job_name = fdf_filename.replace('.fdf', '')
        abs_cwd = os.path.abspath(cwd)

        # Detect OS & path format (Windows/WSL vs Native Linux HPC like Yoltla)
        is_windows = os.name == 'nt' or '\\' in abs_cwd
        if is_windows:
            linux_cwd = "/mnt/c" + abs_cwd[2:].replace("\\", "/")
            siesta_cmd = self.wsl_siesta_path
        else:
            linux_cwd = abs_cwd
            siesta_cmd = self.wsl_siesta_path if self.wsl_siesta_path != "/home/jmc/.local/siesta-5.4.2-openmpi/bin/siesta" else "siesta"

        # Check if already inside an active SLURM allocation (e.g. on Yoltla node)
        in_slurm_allocation = "SLURM_JOB_ID" in os.environ

        if in_slurm_allocation:
            # Direct execution inside active Slurm allocation
            # Yoltla system mandate: mpiexec.hydra -bootstrap ssh
            import shutil
            if shutil.which("mpiexec.hydra"):
                launcher = "mpiexec.hydra -bootstrap ssh"
            elif shutil.which("srun"):
                launcher = "srun"
            else:
                launcher = f"mpirun -np {n_procs}"

            cmd = f"cd {linux_cwd} && {launcher} {siesta_cmd} < {fdf_filename} > {out_filename}"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.returncode != 0:
                raise ExecutionError(f"SIESTA execution failed in Slurm allocation:\n{result.stderr}")
        else:
            # Submit standalone job via sbatch --wait or bash fallback
            wsl_workdir = f"/tmp/siesta_run_{job_name}"
            bash_script = f"""#!/bin/bash
rm -rf {wsl_workdir}
mkdir -p {wsl_workdir}
cp {linux_cwd}/*.fdf {linux_cwd}/*.psml {linux_cwd}/*.DM {wsl_workdir}/ 2>/dev/null || true

cat << 'EOF' > {wsl_workdir}/submit.sh
#!/bin/bash
#SBATCH --job-name={job_name}
#SBATCH --ntasks={n_procs}
#SBATCH --output=slurm_{job_name}.out
#SBATCH --partition=batch

cd {wsl_workdir}
mpirun -np {n_procs} {siesta_cmd} < {fdf_filename} > {out_filename}
EOF

chmod +x {wsl_workdir}/submit.sh
if command -v sbatch >/dev/null 2>&1; then
    cd {wsl_workdir} && sbatch --wait {wsl_workdir}/submit.sh
else
    cd {wsl_workdir} && bash {wsl_workdir}/submit.sh
fi
cp {wsl_workdir}/{out_filename} {linux_cwd}/ 2>/dev/null || true
cp {wsl_workdir}/*.DM {linux_cwd}/ 2>/dev/null || true
"""
            runner_file = os.path.join(abs_cwd, f"run_slurm_{job_name}.sh")
            with open(runner_file, 'w', newline='\n') as f:
                f.write(bash_script)

            if is_windows:
                linux_runner_path = "/mnt/c" + runner_file[2:].replace("\\", "/")
                cmd = f"wsl bash {linux_runner_path}"
            else:
                cmd = f"bash {runner_file}"

            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.returncode != 0:
                raise ExecutionError(f"SLURM/MPI execution failed with return code {result.returncode}:\n{result.stderr}")

    def prepare_input(self, fdf_template: str, alpha: float, mode: str) -> str:
        from siestaflow_hubbard.siesta_backend.fdf_builder import FdfBuilder
        builder = FdfBuilder(fdf_template)
        target = fdf_template.replace('.fdf', f'_{mode}_{alpha}.fdf')
        return builder.prepare_fdf(fdf_template, target, alpha, response_mode=mode)

    def run_simulation(self, fdf_filename: str, out_filename: str, n_procs: int) -> None:
        return self.run_siesta_slurm(fdf_filename, out_filename, cwd='.', n_procs=n_procs)

    def parse_converged_hubbard_occupations(self, out_file_or_content: str) -> Dict[Any, Any]:
        """
        Adversarial parser for SIESTA 5.4 Hubbard output.
        Accepts either a file path or raw text output content.
        - Validates geometry didn't relax
        - Extracts the LAST hubbard occupations block
        - Extracts 5x5 occupation matrices and summary traces for ALL atoms
        - Computes trace checksum and compares with SIESTA's printed total for each atom
        - Extracts maximum change in local occupations
        """
        if os.path.exists(out_file_or_content):
            with open(out_file_or_content, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
        else:
            content = out_file_or_content

        # 1. Geometry Check
        cg_moves = len(re.findall(r'Begin CG move', content))
        if cg_moves > 1:
            raise SemanticValidationFailure(f"Geometry relaxation detected ({cg_moves} CG moves). Fixed geometry required.")

        # 2. Extract Hubbard Blocks
        if 'hubbard_term: recalculating local occupations' in content:
            blocks = content.split('hubbard_term: recalculating local occupations')
            last_block = blocks[-1]
        elif 'hubbard_term: projector occupations' in content:
            blocks = content.split('hubbard_term: projector occupations')
            last_block = blocks[-1]
        else:
            raise SiestaParserError("No hubbard_term blocks found in output. Did DFTU run?")

        # Extract maximum change in local occup if present
        max_change = None
        max_change_match = re.search(
            r'hubbard_term:\s+maximum change in local occup\.\s+([-+]?\d*\.\d+|\d+)',
            last_block
        )
        if max_change_match:
            max_change = float(max_change_match.group(1))

        # Look for atom species sub-blocks
        atom_blocks = last_block.split('hubbard_term: atom, species:')
        if len(atom_blocks) < 2:
            raise SiestaParserError("No atom species found in the last hubbard block.")

        results = {}
        if max_change is not None:
            results["max_change"] = max_change

        for atom_block in atom_blocks[1:]:
            header_match = re.match(r'^\s*(\d+)\s+(\d+)', atom_block.strip())
            if not header_match:
                raise SiestaParserError("Could not parse atom index and species index from hubbard block.")

            atom_idx = int(header_match.group(1))
            species_idx = int(header_match.group(2))

            # Extract the 5x5 matrix
            matrix_lines = re.findall(
                r'^\s*([1-5])\s+([1-5])\s+([-+]?\d*\.\d+)(?:\s+([-+]?\d*\.\d+))?',
                atom_block,
                re.MULTILINE
            )
            if len(matrix_lines) != 25:
                raise SemanticValidationFailure(
                    f"Atom {atom_idx}: Expected 25 matrix elements for d-orbital, found {len(matrix_lines)}"
                )

            up_trace = 0.0
            down_trace = 0.0
            matrix_up = np.zeros((5, 5))
            matrix_down = np.zeros((5, 5))

            for m1_str, m2_str, up_str, down_str in matrix_lines:
                m1, m2 = int(m1_str) - 1, int(m2_str) - 1
                up_val = float(up_str)
                down_val = float(down_str) if down_str else up_val
                matrix_up[m1, m2] = up_val
                matrix_down[m1, m2] = down_val
                if m1 == m2:
                    up_trace += up_val
                    down_trace += down_val

            # 3. Checksum verification
            occ_match_pol = re.search(
                r'Occupations:\s+([-+]?\d*\.\d+)\s+([-+]?\d*\.\d+)\s+([-+]?\d*\.\d+)',
                atom_block
            )
            occ_match_nonpol = re.search(
                r'Occupations:\s+([-+]?\d*\.\d+)\s+([-+]?\d*\.\d+)',
                atom_block
            )
            
            if occ_match_pol:
                siesta_up = float(occ_match_pol.group(1))
                siesta_down = float(occ_match_pol.group(2))
                siesta_total = float(occ_match_pol.group(3))
            elif occ_match_nonpol:
                siesta_up = float(occ_match_nonpol.group(1))
                siesta_down = float(occ_match_nonpol.group(2))
                siesta_total = siesta_up + siesta_down
            else:
                raise SiestaParserError(f"Could not find 'Occupations:' summary line for atom {atom_idx}.")

            if abs(up_trace - siesta_up) > 1e-4:
                raise ChecksumFailure(
                    f"Atom {atom_idx} Spin-UP trace mismatch: computed {up_trace:.5f}, printed {siesta_up:.5f}"
                )
            if abs(down_trace - siesta_down) > 1e-4:
                raise ChecksumFailure(
                    f"Atom {atom_idx} Spin-DOWN trace mismatch: computed {down_trace:.5f}, printed {siesta_down:.5f}"
                )

            total_trace = up_trace + down_trace
            if abs(total_trace - siesta_total) > 1e-4:
                raise ChecksumFailure(
                    f"Atom {atom_idx} Total trace mismatch: computed {total_trace:.5f}, printed {siesta_total:.5f}"
                )

            results[atom_idx] = {
                "species": species_idx,
                "matrix_up": matrix_up,
                "matrix_down": matrix_down,
                "trace_up": up_trace,
                "trace_down": down_trace,
                "trace_total": total_trace,
            }

        return results

    def extract_occupations(
        self,
        out_filename: str,
        response_mode: str,
        alpha: float,
        target_atom_idx: int = 1,
        channel_index: int = 0,
        observable_index: int = 0,
    ) -> List[OccupationRecord]:
        """
        Extracts OccupationRecords for a given output file/content, response_mode, and alpha.
        Matches prototype occupation extraction logic.
        """
        parsed = self.parse_converged_hubbard_occupations(out_filename)
        if target_atom_idx not in parsed:
            return []

        trace_total = parsed[target_atom_idx]["trace_total"]
        record = OccupationRecord(
            response_mode=response_mode,
            channel_index=channel_index,
            alpha_ev=alpha,
            observable_index=observable_index,
            occupation=trace_total,
        )
        return [record]
