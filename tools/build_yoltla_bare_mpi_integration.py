#!/usr/bin/env python3
"""Build the isolated, non-scientific Yoltla BARE/MPI integration package."""
from __future__ import annotations
import argparse, shutil, zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
NAME="SIESTAFLOW_BARE_MPI_INTEGRATION_V1"
SLURM='''#!/bin/bash
#SBATCH --job-name=sf_bare_mpi_check
#SBATCH --partition=tt2d-100p
#SBATCH --nodes=5
#SBATCH --ntasks=100
#SBATCH --ntasks-per-node=20
#SBATCH --cpus-per-task=1
#SBATCH --time=02:00:00
#SBATCH --output=slurm/dag_%j.out
#SBATCH --error=slurm/dag_%j.err
set -euo pipefail
ROOT="$(cd "${SLURM_SUBMIT_DIR:-$PWD}" && pwd)"; N=5; R=100; P=20
fail(){ echo "DAG_ERROR: $*" >&2; exit 1; }
[[ "${SLURM_JOB_NUM_NODES:-}" == "$N" && "${SLURM_NTASKS:-}" == "$R" ]] || fail "allocation must be 5 nodes / 100 ranks"
mapfile -t H < <(scontrol show hostnames "$SLURM_JOB_NODELIST"); [[ ${#H[@]} == $N ]] || fail "host resolution"
HOSTS="$(IFS=,; echo "${H[*]}")"; module purge; module load siesta/5.4.2; module load python/3.12
MPI="$(command -v mpiexec.hydra || true)"; BIN="${SIESTA_BARE_AUDIT_BIN:-}"; REV="${SIESTA_BARE_AUDIT_SOURCE_REVISION:-}"
[[ -x "$MPI" && -n "$BIN" && -x "$BIN" && -n "$REV" ]] || fail "set SIESTA_BARE_AUDIT_BIN and SIESTA_BARE_AUDIT_SOURCE_REVISION; standard module binary is forbidden"
mpi(){ "$MPI" -bootstrap ssh -hosts "$HOSTS" -ppn "$P" -n "$R" "$@"; }
mapfile -t Q < <(mpi /bin/hostname -s); for h in "${H[@]}"; do [[ "$(printf '%s\\n' "${Q[@]}"|grep -Fxc "$h"||true)" == "$P" ]] || fail "bad MPI placement"; done
echo "DAG_MPI_PLACEMENT_OK: hosts=$HOSTS ranks=$R ppn=$P"
normal(){ grep -qiE '>> End of run|siesta: normal completion|job completed' "$1/siesta.out"; }
run(){ local x="$1" d="$ROOT/runs/$1"; [[ "$x" == 00_REFERENCE || -s "$ROOT/runs/00_REFERENCE/00_REFERENCE.DM" ]] || fail "parent DM missing"; cp -fp "$ROOT/pseudopotentials/"*.psml "$d/"; [[ "$x" == 00_REFERENCE ]] || cp -fp "$ROOT/runs/00_REFERENCE/00_REFERENCE.DM" "$d/$x.DM"; echo "DAG_RUN: $x"; (cd "$d"; mpi "$BIN" < siesta.fdf > siesta.out 2> siesta.err); normal "$d" || fail "non-normal termination: $x"; if [[ "$x" == 00_REFERENCE ]]; then ! grep -Eqi 'SCF_NOT_CONV|ABNORMAL_TERMINATION|MPI_Abort' "$d/siesta.out" "$d/siesta.err" || fail "reference not converged"; [[ -s "$d/00_REFERENCE.DM" ]] || fail "reference DM absent"; else PYTHONPATH="$ROOT/src" python "$ROOT/scripts/certify.py" "$d" "$ROOT/runs/00_REFERENCE/00_REFERENCE.DM" "$BIN" "$REV"; fi; echo "DAG_DONE: $x"; }
run 00_REFERENCE; run 10_BARE_MINUS; run 11_BARE_PLUS; echo "DAG_COMPLETE: semantic integration only; no U computed"
'''
CERT='''import sys
from pathlib import Path
from siestaflow_hubbard.siesta_backend.bare_semantics_evidence import write_bare_semantics_sidecar
d=Path(sys.argv[1]); lines=d.joinpath("siesta.out").read_text(errors="replace").splitlines(); marker="TRACE: LR_BARE population_evaluated iscf=2 population_cycle=2"; i=next(i for i,x in enumerate(lines) if marker in x); h=max(j for j in range(i) if "hubbard_term: recalculating local occupations" in lines[j].lower())
write_bare_semantics_sidecar(d/"bare_semantics.json",siesta_version="5.4.2",source_revision=sys.argv[4],executable_path=sys.argv[3],reference_dm_path=sys.argv[2],input_fdf_path=d/"siesta.fdf",output_path=d/"siesta.out",trace_path=d/"siesta.out",selected_event_lines=(h+1,h+1),selected_iscf=2,population_cycle=2)
'''
def fdf(src,label,must=False):
 s=(ROOT/'examples'/src).read_text().replace('SystemLabel         '+src[:-4], 'SystemLabel         '+label)
 return s+'\nSCF.MustConverge '+('F' if must else 'T')+'\n'
def main():
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--audit-source',type=Path,required=True);a=p.parse_args(); d=a.out/NAME; d.mkdir(parents=True)
 for run,src,m in [('00_REFERENCE','MnO_ref.fdf',False),('10_BARE_MINUS','MnO_BARE_-0.05.fdf',True),('11_BARE_PLUS','MnO_BARE_+0.05.fdf',True)]:
  q=d/'runs'/run;q.mkdir(parents=True);(q/'siesta.fdf').write_text(fdf(src,run,m),newline='\n')
 for x in ('Mn.psml','O.psml'): shutil.copy2(ROOT/'examples'/x,d/'pseudopotentials'/x) if (d/'pseudopotentials').exists() else None
 (d/'pseudopotentials').mkdir(exist_ok=True)
 for x in ('Mn.psml','O.psml'): shutil.copy2(ROOT/'examples'/x,d/'pseudopotentials'/x)
 (d/'slurm').mkdir();(d/'slurm'/'submit_dag.slurm').write_text(SLURM,newline='\n');(d/'scripts').mkdir();(d/'scripts'/'certify.py').write_text(CERT,newline='\n')
 shutil.copytree(ROOT/'src'/'siestaflow_hubbard',d/'src'/'siestaflow_hubbard'); (d/'siesta542_lr_bare_trace.patch').write_text(__import__('subprocess').check_output(['git','-C',str(a.audit_source),'diff','--','Src/m_new_dm.F90','Src/dftu.F','Src/setup_hamiltonian.F'],text=True))
 (d/'README.md').write_text('# BARE MPI integration\nRequires an instrumented SIESTA 5.4.2 binary. Set `SIESTA_BARE_AUDIT_BIN` and `SIESTA_BARE_AUDIT_SOURCE_REVISION`; then `sbatch slurm/submit_dag.slurm`. This validates semantics only and never computes U.\n',newline='\n')
 z=a.out/(NAME+'.zip');
 with zipfile.ZipFile(z,'w',zipfile.ZIP_DEFLATED) as h:
  for x in d.rglob('*'):
   if x.is_file(): h.write(x,x.relative_to(a.out).as_posix())
 print(z)
if __name__=='__main__': main()
