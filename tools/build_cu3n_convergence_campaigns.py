#!/usr/bin/env python3
"""Build Cu3N LR-U convergence campaigns using the validated 5 x 20-rank DAG.

Three independent packages isolate the next physical checks after the completed
SC(2x2x2), DZP, 2x2x2-k, rc=3.0 Bohr calculation:
  * denser k sampling at fixed SC(2x2x2)/DZP;
  * a larger NAO basis at fixed SC(2x2x2)/k mesh;
  * a larger SC(3x3x3) at a denser practical k mesh.
"""
from __future__ import annotations

import json
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ALPHA = 0.05
RC_BOHR = 3.0
OMEGA_BOHR = 0.05


@dataclass(frozen=True)
class Case:
    name: str
    supercell: int
    kgrid: int
    basis: str
    purpose: str


CASES = (
    Case("CU3N_PBE_LRU_SC222_K333_RC3p0_V1", 2, 3, "DZP", "k-point response convergence from SC222 2x2x2 to 3x3x3"),
    Case("CU3N_PBE_LRU_SC222_TZP_RC3p0_V1", 2, 2, "TZP", "NAO-basis response convergence from DZP to TZP"),
    Case("CU3N_PBE_LRU_SC333_K222_RC3p0_V1", 3, 2, "DZP", "supercell response convergence from SC222 to SC333; k mesh is 2x2x2"),
)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8", newline="\n")


def parent_sites():
    return (("X", (0.5, 0.0, 0.0)), ("Y", (0.0, 0.5, 0.0)), ("Z", (0.0, 0.0, 0.5)))


def translations(size: int):
    return [(i, j, k) for i in range(size) for j in range(size) for k in range(size)]


def sites(size: int):
    out = []
    for ti, translation in enumerate(translations(size)):
        for pi, (orientation, frac) in enumerate(parent_sites()):
            index = 3 * ti + pi
            out.append({"index": index, "label": f"CuLR{index:02d}", "orientation": orientation,
                        "translation": list(translation),
                        "fractional_supercell": [(frac[d] + translation[d]) / size for d in range(3)]})
    return out


def run_records():
    records = [{"id": "00_REFERENCE", "mode": "REFERENCE", "target": None, "alpha_ev": 0.0}]
    for number, rep, target in ((10, "X", "CuLR00"), (20, "Y", "CuLR01"), (30, "Z", "CuLR02")):
        for mode in ("BARE", "SCREENED"):
            records.extend((
                {"id": f"{number}_{rep}_{mode}_MINUS", "mode": mode, "target": target, "alpha_ev": -ALPHA},
                {"id": f"{number}_{rep}_{mode}_PLUS", "mode": mode, "target": target, "alpha_ev": ALPHA},
            ))
    return records


def fdf(case: Case, record: dict) -> str:
    cu_sites = sites(case.supercell)
    labels = [site["label"] for site in cu_sites]
    species = [f"  {index:3d} 29 {label}" for index, label in enumerate(labels, 1)]
    n_species = len(labels) + 1
    species.append(f"  {n_species:3d}  7 N")
    atom_lines = ["  {:.8f} {:.8f} {:.8f} {:3d} # {}".format(*site["fractional_supercell"], site["index"] + 1, site["label"]) for site in cu_sites]
    atom_lines.extend(f"  {i / case.supercell:.8f} {j / case.supercell:.8f} {k / case.supercell:.8f} {n_species:3d} # N" for i, j, k in translations(case.supercell))
    projector_lines = []
    for label in labels:
        shift = record["alpha_ev"] if label == record["target"] else 0.0
        projector_lines.extend((f"  {label} 1", "  3 2", f"  {shift:+.4f} 0.0000", f"  {RC_BOHR:.4f} {OMEGA_BOHR:.4f}"))
    if record["mode"] == "REFERENCE":
        controls = ("DFTU.FirstIteration false", "SCF.MustConverge T", "SCF.Mix Hamiltonian", "SCF.Mixer.Method Pulay", "SCF.Mixer.Weight 0.05", "SCF.Mixer.History 8", "SCF.DM.Converge T", "SCF.H.Converge T", "SCF.DM.Tolerance 1.0e-5", "SCF.H.Tolerance 1.0e-4 eV", "MaxSCFIterations 300", "DM.UseSaveDM false")
    elif record["mode"] == "BARE":
        controls = ("DFTU.FirstIteration true", "MaxSCFIterations 1", "SCF.MustConverge F", "SCF.Mix Hamiltonian", "SCF.Mixer.Method Pulay", "SCF.Mixer.Weight 0.05", "SCF.Mixer.History 8", "DM.UseSaveDM true")
    else:
        controls = ("DFTU.FirstIteration true", "SCF.MustConverge T", "SCF.Mix Hamiltonian", "SCF.Mixer.Method Pulay", "SCF.Mixer.Weight 0.05", "SCF.Mixer.History 8", "SCF.DM.Converge T", "SCF.H.Converge T", "SCF.DM.Tolerance 1.0e-5", "SCF.H.Tolerance 1.0e-4 eV", "MaxSCFIterations 300", "DM.UseSaveDM true")
    return "\n".join((
        "SystemName Cu3N PBE LR-U convergence campaign", f"SystemLabel {record['id']}",
        f"NumberOfAtoms {len(cu_sites) + case.supercell ** 3}", f"NumberOfSpecies {n_species}",
        "%block ChemicalSpeciesLabel", *species, "%endblock ChemicalSpeciesLabel", "",
        "LatticeConstant 3.8400 Ang", "%block LatticeVectors",
        f"  {case.supercell:.6f} 0.000000 0.000000", f"  0.000000 {case.supercell:.6f} 0.000000", f"  0.000000 0.000000 {case.supercell:.6f}",
        "%endblock LatticeVectors", "AtomicCoordinatesFormat Fractional", "%block AtomicCoordinatesAndAtomicSpecies", *atom_lines, "%endblock AtomicCoordinatesAndAtomicSpecies", "",
        "XC.Functional GGA", "XC.Authors PBE", "Spin non-polarized", f"PAO.BasisSize {case.basis}", "PAO.EnergyShift 0.005 Ry", "PAO.SplitNorm 0.15", "PAO.BasisType split", "MeshCutoff 200 Ry",
        "%block kgrid_Monkhorst_Pack", f"  {case.kgrid} 0 0 0.0", f"  0 {case.kgrid} 0 0.0", f"  0 0 {case.kgrid} 0.0", "%endblock kgrid_Monkhorst_Pack",
        "OccupationFunction FD", "ElectronicTemperature 300 K", "MD.NumCGsteps 0", "%block DFTU.Proj", *projector_lines, "%endblock DFTU.Proj",
        "DFTU.ProjectorGenerationMethod 2", "DFTU.PotentialShift true", *controls,
    ))


ANALYZE = r'''#!/usr/bin/env python3
import json
import re
from pathlib import Path
import numpy as np
from siesta542_bare_contract import select_bare_occupations

ROOT = Path(__file__).resolve().parents[1]


def event_vectors(text, n):
    events, current = [], None
    for line in text.splitlines():
        if "hubbard_term: recalculating local occupations" in line:
            if current is not None: events.append(current)
            current = []
        elif current is not None and "Occupations:" in line:
            numbers = re.findall(r"[-+]?(?:\d*\.\d+|\d+)(?:[Ee][-+]?\d+)?", line.split("Occupations:", 1)[1])
            if len(numbers) == 3: current.append(float(numbers[2]))
            elif len(numbers) == 2: current.append(float(numbers[0]) + float(numbers[1]))
            else: raise RuntimeError(f"unrecognized Occupations line: {line}")
    if current is not None: events.append(current)
    return [event for event in events if len(event) == n]


def selected(path, mode, n):
    path = Path(path); text = path.read_text(errors="ignore")
    err = (path.parent / "siesta.err").read_text(errors="ignore") if (path.parent / "siesta.err").is_file() else ""
    status = (text + "\n" + err).lower()
    if not ((path.parent / "0_NORMAL_EXIT").is_file() or "siesta: normal completion" in status or "job completed" in status): raise RuntimeError(f"normal completion missing: {path}")
    if mode in {"REFERENCE", "SCREENED"} and re.search(r"scf_not_conv|scf: not converged|abnormal_termination", status): raise RuntimeError(f"SCF convergence missing: {path}")
    if mode == "BARE": return np.asarray(select_bare_occupations(text, n))
    events = event_vectors(text, n)
    if not events: raise RuntimeError(f"no complete {n}-site Hubbard event: {path}")
    return events[-1]


def translate(vector, shift, side):
    n = 3 * side ** 3; output = np.empty(n)
    for ti in range(side ** 3):
        i, j, k = ti // (side * side), (ti // side) % side, ti % side
        dst = ((i + shift[0]) % side) * side * side + ((j + shift[1]) % side) * side + ((k + shift[2]) % side)
        for parent in range(3): output[3 * dst + parent] = vector[3 * ti + parent]
    return output


def reconstruct(columns, side):
    n = 3 * side ** 3; matrix = np.empty((n, n)); shifts = [(i, j, k) for i in range(side) for j in range(side) for k in range(side)]
    for ti, shift in enumerate(shifts):
        for parent in range(3): matrix[:, 3 * ti + parent] = translate(columns[parent], shift, side)
    return matrix


def main():
    cfg = json.loads((ROOT / "campaign.json").read_text()); runs = json.loads((ROOT / "runs/manifest.json").read_text()); n = cfg["n_hubbard_sites"]; side = cfg["supercell"][0]
    raw = {run["id"]: selected(ROOT / "runs" / run["id"] / "siesta.out", run["mode"], n) for run in runs}
    (ROOT / "results/raw_occupations").mkdir(parents=True, exist_ok=True)
    (ROOT / "results/raw_occupations/occupations.json").write_text(json.dumps(raw, indent=2) + "\n")
    bare, screened = [], []
    for number, representative in ((10, "X"), (20, "Y"), (30, "Z")):
        derivative = lambda mode: (np.asarray(raw[f"{number}_{representative}_{mode}_PLUS"]) - np.asarray(raw[f"{number}_{representative}_{mode}_MINUS"])) / (2 * cfg["alpha_ev"])
        bare.append(derivative("BARE")); screened.append(derivative("SCREENED"))
    chi0_raw, chi_raw = reconstruct(bare, side), reconstruct(screened, side); chi0, chi = (chi0_raw + chi0_raw.T) / 2, (chi_raw + chi_raw.T) / 2
    out = ROOT / "results/matrices"; out.mkdir(parents=True, exist_ok=True)
    for name, matrix in (("chi0_raw", chi0_raw), ("chi_raw", chi_raw), ("chi0", chi0), ("chi", chi)):
        np.savetxt(out / f"{name}.csv", matrix, delimiter=",", fmt="%.16g")
    rank0, rank = int(np.linalg.matrix_rank(chi0)), int(np.linalg.matrix_rank(chi))
    result = {"campaign_id": cfg["campaign_id"], "status": "FAIL", "n_hubbard_sites": n, "matrix_dimension": n, "alpha_ev": cfg["alpha_ev"], "supercell": cfg["supercell"], "kgrid": cfg["kgrid"], "basis": cfg["basis"], "projector": cfg["projector"], "rank_chi0": rank0, "rank_chi": rank, "condition_chi0": float(np.linalg.cond(chi0)), "condition_chi": float(np.linalg.cond(chi)), "notes": []}
    if rank0 != n or rank != n:
        result["notes"] = ["SCIENTIFIC_ANALYSIS_FAILED: SINGULAR_RESPONSE_MATRIX"]
    else:
        inverse0, inverse = np.linalg.inv(chi0), np.linalg.inv(chi); kernel = inverse0 - inverse; u = np.diag(kernel)
        for name, matrix in (("chi0_inverse", inverse0), ("chi_inverse", inverse), ("K_hubbard_kernel_ev", kernel), ("U_by_site", u)):
            np.savetxt(out / f"{name}.csv", matrix, delimiter=",", fmt="%.16g")
        result.update(status="PASS", U_Cu_eV=float(u.mean()), U_A_mean_eV=float(u[0::3].mean()), U_B_mean_eV=float(u[1::3].mean()), U_C_mean_eV=float(u[2::3].mean()), max_site_deviation_from_mean_eV=float(np.max(np.abs(u - u.mean()))), inversion_residuals={"chi0": float(np.linalg.norm(inverse0 @ chi0 - np.eye(n))), "chi": float(np.linalg.norm(inverse @ chi - np.eye(n)))})
    target = ROOT / "results/final/campaign_result.json"; target.parent.mkdir(parents=True, exist_ok=True); target.write_text(json.dumps(result, indent=2) + "\n"); print(target)


if __name__ == "__main__": main()
'''


def dag(case: Case) -> str:
    run_ids = " ".join(record["id"] for record in run_records())
    site_count = 3 * case.supercell ** 3
    return f'''#!/bin/bash
# Validated single-allocation Cu3N LR-U DAG: 5 nodes x 20 ranks = 100 ranks.
# One 100-rank SIESTA calculation at a time. No arrays or background MPI.
#SBATCH --job-name={case.name.lower()}
#SBATCH --partition=tt2d-100p
#SBATCH --nodes=5
#SBATCH --ntasks=100
#SBATCH --ntasks-per-node=20
#SBATCH --cpus-per-task=1
#SBATCH --time=2-00:00:00
#SBATCH --output=slurm/dag_%j.out
#SBATCH --error=slurm/dag_%j.err
set -euo pipefail
ROOT="$(cd "${{SLURM_SUBMIT_DIR:-$PWD}}" && pwd)"
NODES=5; RANKS=100; PPN=20
RUNS=({run_ids})
fail() {{ echo "DAG_ERROR: $*" >&2; exit 1; }}
[[ "${{SLURM_JOB_NUM_NODES:-}}" == "$NODES" && "${{SLURM_NTASKS:-}}" == "$RANKS" ]] || fail "incorrect Slurm allocation"
mapfile -t HOSTS_A < <(scontrol show hostnames "$SLURM_JOB_NODELIST")
[[ "${{#HOSTS_A[@]}}" == "$NODES" ]] || fail "host resolution"
HOSTS="$(IFS=,; echo "${{HOSTS_A[*]}}")"
module purge; module load siesta/5.4.2; module load python/3.12
SIESTA="$(command -v siesta)"; MPI="$(command -v mpiexec.hydra)"
[[ -x "$SIESTA" && -x "$MPI" ]] || fail "runtime unavailable"
mpi() {{ "$MPI" -bootstrap ssh -hosts "$HOSTS" -ppn "$PPN" -n "$RANKS" "$@"; }}
PROBE="$(mktemp "$ROOT/slurm/placement_${{SLURM_JOB_ID}}.XXXX")"; trap 'rm -f "$PROBE"' EXIT
mpi /bin/hostname -s > "$PROBE"
for host in "${{HOSTS_A[@]}}"; do [[ "$(grep -Fxc "$host" "$PROBE" || true)" == "$PPN" ]] || fail "MPI placement for $host"; done
echo "DAG_MPI_PLACEMENT_OK: hosts=$HOSTS ranks=$RANKS ppn=$PPN"
normal() {{ [[ -f "$1/0_NORMAL_EXIT" ]] || grep -qiE 'siesta: normal completion|job completed' "$1/siesta.out"; }}
mode_for() {{ [[ "$1" == 00_REFERENCE ]] && echo REFERENCE || ([[ "$1" == *BARE* ]] && echo BARE || echo SCREENED); }}
valid() {{
  local run="$1" directory="$ROOT/runs/$1" mode
  mode="$(mode_for "$run")"
  [[ -s "$directory/siesta.out" ]] && normal "$directory" || return 1
  if [[ "$mode" != BARE ]]; then ! grep -Eqi 'SCF_NOT_CONV|SCF: not converged|ABNORMAL_TERMINATION' "$directory/siesta.out" "$directory/siesta.err" 2>/dev/null || return 1; fi
  python "$ROOT/scripts/validate_run.py" "$directory/siesta.out" "$mode" >/dev/null
  [[ "$run" != 00_REFERENCE || -s "$directory/00_REFERENCE.DM" ]]
}}
stage() {{
  local run="$1" directory="$ROOT/runs/$1"
  for index in $(seq -w 0 {site_count - 1}); do cp -fp "$ROOT/pseudopotentials/Cu.psml" "$directory/CuLR$index.psml"; done
  cp -fp "$ROOT/pseudopotentials/N.psml" "$directory/N.psml"
  [[ "$run" == 00_REFERENCE ]] || cp -fp "$ROOT/runs/00_REFERENCE/00_REFERENCE.DM" "$directory/$run.DM"
}}
for run in "${{RUNS[@]}}"; do
  directory="$ROOT/runs/$run"
  if [[ -e "$directory/siesta.out" || -e "$directory/siesta.err" ]]; then valid "$run" || fail "existing run failed scientific validation: $run"; echo "DAG_SKIP_VALID: $run"; continue; fi
  [[ "$run" == 00_REFERENCE || -s "$ROOT/runs/00_REFERENCE/00_REFERENCE.DM" ]] || fail "reference DM missing"
  echo "DAG_RUN: $run hosts=$HOSTS ranks=$RANKS ppn=$PPN"
  stage "$run"
  (cd "$directory"; mpi "$SIESTA" < siesta.fdf > siesta.out 2> siesta.err)
  valid "$run" || fail "scientific validation failed: $run"
  echo "DAG_DONE: $run"
done
python "$ROOT/scripts/analyze.py"
echo "DAG_COMPLETE: $ROOT/results/final/campaign_result.json"
'''


def build(case: Case) -> Path:
    package = ROOT / case.name
    if package.exists(): shutil.rmtree(package)
    for directory in ("geometry", "pseudopotentials", "runs", "results/final", "results/matrices", "results/raw_occupations", "scripts", "slurm"):
        (package / directory).mkdir(parents=True, exist_ok=True)
    n_sites = 3 * case.supercell ** 3
    config = {"campaign_id": case.name, "material": "Cu3N", "functional": "PBE", "supercell": [case.supercell] * 3, "n_hubbard_sites": n_sites, "alpha_ev": ALPHA, "kgrid": [case.kgrid] * 3, "basis": case.basis, "projector": {"shell": [3, 2], "method": 2, "rc_bohr": RC_BOHR, "omega_bohr": OMEGA_BOHR}, "purpose": case.purpose, "baseline": "CU3N_PBE_LRU_SC222_RC3p0_V1: SC222, DZP, 2x2x2 k-grid, rc=3.0 Bohr"}
    write(package / "campaign.json", json.dumps(config, indent=2))
    write(package / "geometry/site_map.json", json.dumps(sites(case.supercell), indent=2))
    records = run_records(); write(package / "runs/manifest.json", json.dumps(records, indent=2))
    for record in records:
        write(package / "runs" / record["id"] / "run.json", json.dumps(record, indent=2))
        write(package / "runs" / record["id"] / "siesta.fdf", fdf(case, record))
    write(package / "geometry/supercell.fdf", fdf(case, records[0]))
    shutil.copy2(ROOT / "production_benchmarks/pseudos/Cu.psml", package / "pseudopotentials/Cu.psml")
    shutil.copy2(ROOT / "production_benchmarks/pseudos/N.psml", package / "pseudopotentials/N.psml")
    write(package / "scripts/analyze.py", ANALYZE)
    shutil.copy2(ROOT / "tools" / "siesta542_bare_contract.py", package / "scripts/siesta542_bare_contract.py")
    write(package / "scripts/validate_run.py", "from pathlib import Path\nimport sys\nsys.path.insert(0, str(Path(__file__).parent))\nfrom analyze import selected\nselected(Path(sys.argv[1]), sys.argv[2], int(sys.argv[3]))\nprint('SEMANTIC_OCCUPATION_VALID')")
    script = (package / "slurm/submit_dag.slurm")
    text = dag(case).replace('python "$ROOT/scripts/validate_run.py" "$directory/siesta.out" "$mode" >/dev/null', f'python "$ROOT/scripts/validate_run.py" "$directory/siesta.out" "$mode" "{n_sites}" >/dev/null')
    write(script, text)
    write(package / "verify_package.py", f'''import json, re\nfrom pathlib import Path\nr=Path(__file__).resolve().parent; cfg=json.loads((r/'campaign.json').read_text()); runs=json.loads((r/'runs/manifest.json').read_text()); assert cfg['n_hubbard_sites']=={n_sites} and cfg['supercell']==[{case.supercell}]*3 and cfg['kgrid']==[{case.kgrid}]*3 and cfg['basis']=='{case.basis}' and len(runs)==13\nfor run in runs:\n text=(r/'runs'/run['id']/'siesta.fdf').read_text(); assert 'NumberOfAtoms {4 * case.supercell ** 3}' in text and 'NumberOfSpecies {n_sites + 1}' in text and len(re.findall(r'^\\s*CuLR\\d{{2}} 1\\s*$',text,re.M))=={n_sites}\nprint('PACKAGE_VERIFIED: {case.name}')''')
    write(package / "README.md", f'''# {case.name}\n\nScientific convergence campaign for the completed Cu3N PBE LR-U baseline `SC(2x2x2), DZP, k=2x2x2, rc=3.0 Bohr`.\n\n- Purpose: {case.purpose}.\n- Structure: SC({case.supercell}x{case.supercell}x{case.supercell}), {4 * case.supercell ** 3} atoms, {n_sites} explicit Cu-3d Hubbard sites.\n- Basis: {case.basis}; k-grid: {case.kgrid}x{case.kgrid}x{case.kgrid}; Method 2; rc=3.0 Bohr; omega=0.05 Bohr; alpha=+/-0.05 eV.\n- Topology: reference + 6 BARE + 6 SCREENED = 13 SIESTA calculations.\n- Slurm: one 5-node x 20-rank allocation, one 100-rank FDF at a time.\n\nThis campaign is a convergence test, not a parameter-tuning mechanism.\n''')
    archive = ROOT / f"{case.name}.zip"
    if archive.exists(): archive.unlink()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
        for path in package.rglob("*"):
            if path.is_file(): output.write(path, path.relative_to(ROOT).as_posix())
    return archive


if __name__ == "__main__":
    for item in CASES: print(build(item))
