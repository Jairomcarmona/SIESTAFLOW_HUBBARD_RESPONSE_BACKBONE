"""Build the FeO transfer-validation package from the approved MnO layout."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "FEO_PBE_LRU_SC222_VALIDATION_V1"
SOURCE = ROOT / "MNO_PBE_LRU_SC222_VALIDATION_V1_1"

CONFIG = {
    "campaign_id": "FEO_PBE_LRU_SC222_VALIDATION_V1",
    "material": "FeO",
    "lattice_constant_ang": 4.334,
    "lattice_vectors_parent": [[0.0, 1.0, 1.0], [0.5, 0.0, 0.5], [0.5, 0.5, 0.0]],
    "lattice_vectors_supercell": [[0.0, 2.0, 2.0], [1.0, 0.0, 1.0], [1.0, 1.0, 0.0]],
    "correlated": {"element": "Fe", "atomic_number": 26, "label_prefix": "FeLR"},
    "oxygen": {"label": "O", "atomic_number": 8},
    "parent_atoms": [
        {"role": "Fe_A", "sublattice": "A", "fractional": [0.0, 0.0, 0.0]},
        {"role": "Fe_B", "sublattice": "B", "fractional": [0.5, 0.0, 0.0]},
        {"role": "O_0", "sublattice": "O", "fractional": [0.25, 0.5, 0.5]},
        {"role": "O_1", "sublattice": "O", "fractional": [0.75, 0.5, 0.5]},
    ],
    "initial_moments": {"A": 4.0, "B": -4.0, "O": 0.0},
    "output_controls": {"write_dm": True, "write_mulliken": True},
    "projector": {"method": 2, "rc_bohr": 3.0, "omega": 0.05, "cutoff_policy": "explicit_rc"},
    "alpha_ev": 0.05,
    "kgrid": [3, 3, 3],
    "representatives": {"A": "FeLR00", "B": "FeLR01"},
    "scientific_purpose": "independent 3d/spin-polarized transfer validation; not a fitted literature benchmark",
    "literature_context": {
        "reference": "Cococcioni & de Gironcoli, Phys. Rev. B 71, 035105 (2005)",
        "reported_u_ev": 4.3,
        "method": "DFPT linear response", "code": "Quantum ESPRESSO", "xc": "LDA",
        "comparability": "context only; XC, projector and cell differ",
    },
}


DAG = r'''#!/bin/bash
# One Slurm allocation, one SIESTA FDF at a time: five nodes x twenty ranks = 100 MPI ranks.
# No arrays, no background MPI, and no release/reacquire between response runs.
#SBATCH --job-name=feo_pbe_lru_sc222_v1
#SBATCH --partition=tt2d-100p
#SBATCH --nodes=5
#SBATCH --ntasks=100
#SBATCH --ntasks-per-node=20
#SBATCH --cpus-per-task=1
#SBATCH --time=2-00:00:00
#SBATCH --output=slurm/dag_%j.out
#SBATCH --error=slurm/dag_%j.err
set -euo pipefail
ROOT="$(cd "${SLURM_SUBMIT_DIR:-$PWD}" && pwd)"; NODES=5; RANKS=100; PPN=20
RUNS=(00_REFERENCE 10_A_BARE_MINUS 11_A_BARE_PLUS 12_A_SCREENED_MINUS 13_A_SCREENED_PLUS 20_B_BARE_MINUS 21_B_BARE_PLUS 22_B_SCREENED_MINUS 23_B_SCREENED_PLUS)
fail(){ echo "DAG_ERROR: $*" >&2; exit 1; }
[[ "${SLURM_JOB_NUM_NODES:-}" == "$NODES" && "${SLURM_NTASKS:-}" == "$RANKS" ]] || fail "incorrect Slurm allocation"
mapfile -t HOSTS_A < <(scontrol show hostnames "$SLURM_JOB_NODELIST"); [[ "${#HOSTS_A[@]}" == "$NODES" ]] || fail "host resolution"
HOSTS="$(IFS=,; echo "${HOSTS_A[*]}")"; module purge; module load siesta/5.4.2; module load python/3.12
SIESTA="$(command -v siesta)"; MPI="$(command -v mpiexec.hydra)"; [[ -x "$SIESTA" && -x "$MPI" ]] || fail "runtime unavailable"
mpi(){ "$MPI" -bootstrap ssh -hosts "$HOSTS" -ppn "$PPN" -n "$RANKS" "$@"; }
PROBE="$(mktemp "$ROOT/slurm/placement_${SLURM_JOB_ID}.XXXX")"; trap 'rm -f "$PROBE"' EXIT; mpi /bin/hostname -s > "$PROBE"
for h in "${HOSTS_A[@]}"; do [[ "$(grep -Fxc "$h" "$PROBE" || true)" == "$PPN" ]] || fail "MPI placement for $h"; done
echo "DAG_MPI_PLACEMENT_OK: hosts=$HOSTS ranks=$RANKS ppn=$PPN"
normal(){ [[ -f "$1/0_NORMAL_EXIT" ]] || grep -qiE 'siesta: normal completion|job completed' "$1/siesta.out"; }
valid(){ local r="$1" d="$ROOT/runs/$1" mode; [[ -s "$d/siesta.out" ]] && normal "$d" || return 1; if [[ "$r" == 00_REFERENCE ]]; then mode=REFERENCE; elif [[ "$r" == *BARE* ]]; then mode=BARE; else mode=SCREENED; fi; if [[ "$mode" != BARE ]]; then ! grep -Eqi 'SCF_NOT_CONV|SCF: not converged|ABNORMAL_TERMINATION|MPI_Abort' "$d/siesta.out" "$d/siesta.err" 2>/dev/null || return 1; fi; python "$ROOT/scripts/validate_run.py" "$d/siesta.out" "$mode" >/dev/null; if [[ "$mode" == REFERENCE ]]; then python "$ROOT/scripts/validate_reference_state.py" "$d/siesta.out" >/dev/null; fi; [[ "$r" != 00_REFERENCE || -s "$d/00_REFERENCE.DM" ]]; }
stage(){ local r="$1" d="$ROOT/runs/$1"; for n in $(seq -w 0 15); do cp -fp "$ROOT/pseudopotentials/Fe.psml" "$d/FeLR$n.psml"; done; cp -fp "$ROOT/pseudopotentials/O.psml" "$d/O.psml"; [[ "$r" == 00_REFERENCE ]] || cp -fp "$ROOT/runs/00_REFERENCE/00_REFERENCE.DM" "$d/$r.DM"; }
for r in "${RUNS[@]}"; do d="$ROOT/runs/$r"; if [[ -e "$d/siesta.out" || -e "$d/siesta.err" ]]; then valid "$r" || fail "existing run failed scientific validation: $r"; echo "DAG_SKIP_VALID: $r"; continue; fi; [[ "$r" == 00_REFERENCE || -s "$ROOT/runs/00_REFERENCE/00_REFERENCE.DM" ]] || fail "reference DM missing"; echo "DAG_RUN: $r hosts=$HOSTS ranks=$RANKS ppn=$PPN"; stage "$r"; (cd "$d"; mpi "$SIESTA" < siesta.fdf > siesta.out 2> siesta.err); valid "$r" || fail "scientific validation failed: $r"; echo "DAG_DONE: $r"; done
python "$ROOT/scripts/package_results.py"; echo "DAG_COMPLETE: $ROOT/results/final/feo_pbe_lru_sc222_result.json"
'''


def replace_tree(root: Path) -> None:
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix in {".psml", ".ion", ".nc", ".xml", ".DM"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        text = (text.replace("MNO_PBE_LRU_SC222_VALIDATION_V1_1", "FEO_PBE_LRU_SC222_VALIDATION_V1")
                    .replace("mno_pbe_lru_sc222", "feo_pbe_lru_sc222")
                    .replace("MnO", "FeO").replace("MnLR", "FeLR").replace("Mn.psml", "Fe.psml")
                    .replace("Mn", "Fe").replace("MNO", "FEO").replace("25", "26")
                    .replace("4.43", "4.334").replace("+5.0", "+4.0").replace("-5.0", "-4.0"))
        path.write_text(text, encoding="utf-8")


def build() -> Path:
    if PACKAGE.exists():
        shutil.rmtree(PACKAGE)
    shutil.copytree(
        SOURCE,
        PACKAGE,
        ignore=shutil.ignore_patterns(".pytest_tmp", ".pytest_cache", "__pycache__", "*.pyc"),
    )
    replace_tree(PACKAGE)
    (PACKAGE / "campaign.json").write_text(json.dumps(CONFIG, indent=2) + "\n", encoding="utf-8")
    (ROOT / "materials").mkdir(exist_ok=True)
    (ROOT / "materials" / "FeO_PBE_SC222.json").write_text(json.dumps(CONFIG, indent=2) + "\n", encoding="utf-8")
    shutil.copy2(ROOT / "examples" / "tmo_campaigns" / "Fe.psml", PACKAGE / "pseudopotentials" / "Fe.psml")
    shutil.copy2(ROOT / "NIO_PBE_LRU_SC222_V1" / "pseudopotentials" / "O.psml", PACKAGE / "pseudopotentials" / "O.psml")
    for stale in (
        PACKAGE / "pseudopotentials" / "Mn.psml",
        PACKAGE / "DAG_RESUME_DEPLOYMENT.md",
        PACKAGE / "slurm" / "submit_dag_resume.slurm",
    ):
        if stale.exists(): stale.unlink()
    for stale in (PACKAGE / "results" / "final").glob("*.json"):
        stale.unlink()
    import sys
    sys.path.insert(0, str(ROOT))
    from lru_core import write_campaign
    write_campaign(CONFIG, PACKAGE)
    verify = """import json, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'scripts'))
from lru_core import RUNS, build_atoms
cfg = json.loads((ROOT / 'campaign.json').read_text())
atoms, sites = build_atoms(cfg)
assert cfg['material'] == 'FeO' and cfg['lattice_constant_ang'] == 4.334
assert len(atoms) == 32 and len(sites) == 16
assert cfg['projector'] == {'method': 2, 'rc_bohr': 3.0, 'omega': 0.05, 'cutoff_policy': 'explicit_rc'}
assert cfg['alpha_ev'] == 0.05
records = json.loads((ROOT / 'runs' / 'manifest.json').read_text())
assert [(x['id'], x['mode']) for x in records] == [(x[0], x[1]) for x in RUNS]
assert len(records) == 9 and sum(x['mode'] == 'BARE' for x in records) == 4 and sum(x['mode'] == 'SCREENED' for x in records) == 4
for pseudo in ('Fe.psml', 'O.psml'):
    assert 'Perdew-Burke-Ernzerhof' in (ROOT / 'pseudopotentials' / pseudo).read_text(errors='ignore')
for record in records:
    text = (ROOT / 'runs' / record['id'] / 'siesta.fdf').read_text()
    for token in ('NumberOfAtoms 32', 'NumberOfSpecies 17', 'XC.Functional GGA', 'XC.Authors PBE', 'PAO.BasisSize DZP', 'PAO.EnergyShift 0.005 Ry', 'MeshCutoff 200 Ry', 'DFTU.ProjectorGenerationMethod 2', 'DFTU.PotentialShift true'):
        assert token in text, (record['id'], token)
    assert len(re.findall(r'^\\s*FeLR\\d{2} 1\\s*$', text, re.M)) == 16
    shifted = re.findall(r'^\\s*(FeLR\\d{2}) 1\\s*$\\n\\s*3 2\\s*$\\n\\s*([+-]?\\d+\\.\\d+)', text, re.M)
    nonzero = [(label, float(value)) for label, value in shifted if abs(float(value)) > 1e-12]
    if record['mode'] == 'REFERENCE':
        assert nonzero == [] and 'DM.UseSaveDM false' in text
    else:
        assert len(nonzero) == 1 and nonzero[0][0] == record['target'] and abs(nonzero[0][1] - record['alpha_ev']) < 1e-8
        if record['mode'] == 'BARE': assert 'MaxSCFIterations 1' in text and 'SCF.Mix Hamiltonian' in text and 'SCF.MustConverge F' in text
        else: assert 'MaxSCFIterations 300' in text and 'SCF.MustConverge T' in text
dag = (ROOT / 'slurm' / 'submit_dag.slurm').read_text()
assert '--nodes=5' in dag and '--ntasks=100' in dag and '--ntasks-per-node=20' in dag
assert '--array' not in dag and 'DAG_MPI_PLACEMENT_OK' in dag and 'mpiexec.hydra' in dag
assert 'validate_reference_state.py' in dag
print('PACKAGE_VERIFIED: FEO_PBE_LRU_SC222_VALIDATION_V1')
"""
    (PACKAGE / 'verify_package.py').write_text(verify, encoding='utf-8')
    for stale in ('submit_reference.slurm', 'submit_children.slurm'):
        stale_path = PACKAGE / 'slurm' / stale
        if stale_path.exists(): stale_path.unlink()
    (PACKAGE / "slurm" / "submit_dag.slurm").write_text(DAG.strip() + "\n", encoding="utf-8")
    readme = """# FeO PBE LR-U validation campaign, SC(2x2x2)

This package is an independent transfer test for the finite-difference SIESTA Hubbard-U workflow. It keeps the rocksalt AFM-II cell family but changes the correlated 3d species and magnetic moments relative to NiO and MnO, exercising Fe 3d occupation parsing and site reconstruction.

Frozen input contract: lattice constant 4.334 Ang, 32 atoms, 16 Fe 3d Hubbard sites, PBE, DZP, PAO energy shift 0.005 Ry, mesh cutoff 200 Ry, 3x3x3 k-grid, Method-2 Fe 3d projector with explicit rc=3.0 Bohr and omega=0.05 Bohr, AFM-II initial moments +4/-4, and alpha=+/-0.05 eV. The campaign contains exactly nine calculations: one REFERENCE, four BARE and four SCREENED.

The approximately 4.3 eV FeO value reported by Cococcioni and de Gironcoli is context only (different code, XC functional, projector and cell); it is not a hard-coded acceptance target. A PASS means that the declared runtime, convergence, semantic occupation, rank and direct-inversion gates pass.

Run `python verify_package.py` before transfer. Submit only `slurm/submit_dag.slurm`. The DAG reserves five nodes with twenty MPI ranks per node, keeps the allocation for the complete sequence, and runs one FDF at a time. BARE non-convergence is allowed by the LR contract; REFERENCE and SCREENED runs require normal SIESTA completion, SCF convergence and complete Fe occupation records.
"""
    (PACKAGE / "README.md").write_text(readme, encoding="utf-8")
    (PACKAGE / "SCIENTIFIC_CONTRACT.md").write_text(
        """# FeO PBE LR-U SC(2x2x2) scientific contract

Material: rocksalt AFM-II FeO; `a = 4.33400 Ang`; PBE (`XC.Functional GGA`, `XC.Authors PBE`); 32 atoms, 16 Fe and 16 O; sixteen Fe 3d Hubbard sites; DZP; `PAO.EnergyShift 0.005 Ry`; `MeshCutoff 200 Ry`; 3x3x3 k-grid; FD occupations at 300 K; alpha `+/-0.0500 eV`.

The Fe Hubbard subspace is an explicit Method-2 Fe 3d projector with `rc = 3.0 Bohr`, `omega = 0.05 Bohr`, and `DFTU.PotentialShift true`. This is a declared software-validation point, not a universal FeO convergence claim.

Exactly nine physical runs are required: one REFERENCE, four BARE (`MaxSCFIterations 1`, `SCF.Mix Hamiltonian`, `SCF.MustConverge F`) and four SCREENED (`SCF.MustConverge T`, maximum 300 iterations). The response remains 16x16. Raw reconstructed matrices are symmetrized, then `K = inv(chi0) - inv(chi)` is evaluated by direct inversion only; no pseudoinverse and no A/B pre-averaging. `U_I = K_II` and A/B averages are calculated only after the 16x16 inversion.
""",
        encoding="utf-8",
    )
    archive = ROOT / "FEO_PBE_LRU_SC222_VALIDATION_V1.zip"
    if archive.exists(): archive.unlink()
    shutil.make_archive(str(archive.with_suffix("")), "zip", ROOT, PACKAGE.name)
    return PACKAGE


if __name__ == "__main__":
    print(build())
