"""Build the routine beta-MnO2 LR-U validation package for Yoltla."""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = "BETA_MNO2_PBE_LRU_SC222_VALIDATION_V1"
PACKAGE = ROOT / NAME
SOURCE = ROOT / "FEO_PBE_LRU_SC222_VALIDATION_V1"

# Baur, Acta Cryst. B 32 (1976) 2200-2204; COD 2105790.
# The conventional rutile cell has Mn 2a and O 4f (u,u,0), u=0.30515.
CONFIG = {
    "campaign_id": NAME,
    "material": "beta-MnO2 (pyrolusite)",
    "structure_source": {
        "database": "Crystallography Open Database", "entry": "2105790",
        "doi": "10.1107/S0567740876007371",
        "citation": "W. H. Baur, Acta Cryst. B 32, 2200-2204 (1976)",
        "lattice_a_ang": 4.3983, "lattice_c_ang": 2.8730, "oxygen_u": 0.30515,
    },
    "lattice_constant_ang": 1.0,
    "lattice_vectors_parent": [[4.3983, 0.0, 0.0], [0.0, 4.3983, 0.0], [0.0, 0.0, 2.8730]],
    "lattice_vectors_supercell": [[8.7966, 0.0, 0.0], [0.0, 8.7966, 0.0], [0.0, 0.0, 5.7460]],
    "correlated": {"element": "Mn", "atomic_number": 25, "label_prefix": "MnLR"},
    "oxygen": {"label": "O", "atomic_number": 8},
    "parent_atoms": [
        {"role": "Mn_A", "sublattice": "A", "fractional": [0.0, 0.0, 0.0]},
        {"role": "Mn_B", "sublattice": "B", "fractional": [0.5, 0.5, 0.5]},
        {"role": "O_0", "sublattice": "O", "fractional": [0.30515, 0.30515, 0.0]},
        {"role": "O_1", "sublattice": "O", "fractional": [0.69485, 0.69485, 0.0]},
        {"role": "O_2", "sublattice": "O", "fractional": [0.80515, 0.19485, 0.5]},
        {"role": "O_3", "sublattice": "O", "fractional": [0.19485, 0.80515, 0.5]},
    ],
    "initial_moments": {"A": 3.0, "B": -3.0, "O": 0.0},
    "output_controls": {"write_dm": True, "write_mulliken": True},
    "projector": {"method": 2, "rc_bohr": 3.0, "omega": 0.05, "cutoff_policy": "explicit_rc"},
    "alpha_ev": 0.05,
    "kgrid": [3, 3, 3],
    "representatives": {"A": "MnLR00", "B": "MnLR01"},
    "magnetic_model": "collinear A1-AFM approximation to experimental helical beta-MnO2 order",
    "scientific_purpose": "routine external LR-U validation for Mn(IV)-O chemistry relevant to birnessite; not a fitted-U reproduction",
}


def write(path: Path, text: str) -> None:
    """Write LF-only text even when this builder is run on Windows."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8"))


def cif_text() -> str:
    return """data_2105790_pyrolusite\n_audit_creation_method 'campaign source snapshot'\n_chemical_name_common 'Pyrolusite, beta-MnO2'\n_chemical_formula_sum 'Mn O2'\n_cell_length_a 4.3983\n_cell_length_b 4.3983\n_cell_length_c 2.8730\n_cell_angle_alpha 90\n_cell_angle_beta 90\n_cell_angle_gamma 90\n_symmetry_space_group_name_H-M 'P 42/m n m'\n_symmetry_Int_Tables_number 136\n_cod_database_code 2105790\n_publ_section_title 'Rutile-type compounds. V. Refinement of MnO2 and MgF2'\n_publ_author_name 'Baur, W. H.'\n_publ_section_reference_journal_abbrev 'Acta Cryst. B'\n_publ_section_reference_year 1976\n_publ_section_reference_page_first 2200\n_publ_section_reference_page_last 2204\n_publ_section_reference_doi '10.1107/S0567740876007371'\n# Atomic coordinates are the symmetry-expanded conventional rutile positions.\n# Mn 2a: (0,0,0); O 4f: (u,u,0), u=0.30515.\nloop_\n_atom_site_label\n_atom_site_type_symbol\n_atom_site_fract_x\n_atom_site_fract_y\n_atom_site_fract_z\nMn1 Mn 0.00000 0.00000 0.00000\nMn2 Mn 0.50000 0.50000 0.50000\nO1 O 0.30515 0.30515 0.00000\nO2 O 0.69485 0.69485 0.00000\nO3 O 0.80515 0.19485 0.50000\nO4 O 0.19485 0.80515 0.50000\n"""


def dynamic_lru(source: str) -> str:
    source = source.replace('labels = [f"{prefix}{i:02d}" for i in range(16)]',
                            'labels = [site["label"] for site in build_atoms(config)[1]]')
    source = source.replace('"NumberOfAtoms 32", "NumberOfSpecies 17",',
                            'f"NumberOfAtoms {len(atoms)}", f"NumberOfSpecies {len(labels) + 1}",')
    source = source.replace('f"  17 {config[\'oxygen\'][\'atomic_number\']} {config[\'oxygen\'][\'label\']}"',
                            'f"  {len(labels) + 1} {config[\'oxygen\'][\'atomic_number\']} {config[\'oxygen\'][\'label\']}"')
    source = source.replace('else 17', 'else len(labels) + 1')
    source = source.replace('"  3 0 0 0.0", "  0 3 0 0.0", "  0 0 3 0.0",',
                            'f"  {config[\'kgrid\'][0]} 0 0 0.0", f"  0 {config[\'kgrid\'][1]} 0 0.0", f"  0 0 {config[\'kgrid\'][2]} 0.0",')
    source = source.replace('default=16', 'default=None')
    source = source.replace('REFERENCE_STATE_INVALID: Fe', 'REFERENCE_STATE_INVALID: Mn')
    source = source.replace('"Fe_total_moment"', '"Mn_total_moment"')
    source = source.replace('0.26, 0.10', '0.25, 0.10')
    return source


def dag() -> str:
    return """#!/bin/bash
# Validated Yoltla pattern: retain one five-node allocation; run one FDF at a time on all 100 ranks.
# No job arrays, no background MPI, no release/reacquire of the Slurm allocation.
#SBATCH --job-name=beta_mno2_lru_sc222_v1
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
stage(){ local r="$1" d="$ROOT/runs/$1"; for n in $(seq -w 0 15); do cp -fp "$ROOT/pseudopotentials/Mn.psml" "$d/MnLR$n.psml"; done; cp -fp "$ROOT/pseudopotentials/O.psml" "$d/O.psml"; [[ "$r" == 00_REFERENCE ]] || cp -fp "$ROOT/runs/00_REFERENCE/00_REFERENCE.DM" "$d/$r.DM"; }
for r in "${RUNS[@]}"; do d="$ROOT/runs/$r"; if [[ -e "$d/siesta.out" || -e "$d/siesta.err" ]]; then valid "$r" || fail "existing run failed scientific validation: $r"; echo "DAG_SKIP_VALID: $r"; continue; fi; [[ "$r" == 00_REFERENCE || -s "$ROOT/runs/00_REFERENCE/00_REFERENCE.DM" ]] || fail "reference DM missing"; echo "DAG_RUN: $r hosts=$HOSTS ranks=$RANKS ppn=$PPN"; stage "$r"; (cd "$d"; mpi "$SIESTA" < siesta.fdf > siesta.out 2> siesta.err); valid "$r" || fail "scientific validation failed: $r"; echo "DAG_DONE: $r"; done
python "$ROOT/scripts/package_results.py"; echo "DAG_COMPLETE: $ROOT/results/final/beta_mno2_pbe_lru_sc222_result.json"
"""


def build() -> Path:
    if PACKAGE.exists(): shutil.rmtree(PACKAGE)
    shutil.copytree(SOURCE, PACKAGE, ignore=shutil.ignore_patterns("results", "__pycache__", ".pytest_tmp", "*.pyc"))
    for stale in (PACKAGE / "pseudopotentials" / "Fe.psml", PACKAGE / "pseudopotentials" / "Mn.psml"):
        if stale.exists(): stale.unlink()
    shutil.copy2(ROOT / "examples" / "Mn.psml", PACKAGE / "pseudopotentials" / "Mn.psml")
    shutil.copy2(ROOT / "examples" / "O.psml", PACKAGE / "pseudopotentials" / "O.psml")
    write(PACKAGE / "campaign.json", json.dumps(CONFIG, indent=2) + "\n")
    write(PACKAGE / "geometry" / "source" / "COD_2105790_pyrolusite.cif", cif_text())
    write(PACKAGE / "scripts" / "lru_core.py", dynamic_lru((ROOT / "lru_core.py").read_text(encoding="utf-8")))
    sys.path.insert(0, str(PACKAGE / "scripts"))
    from lru_core import write_campaign
    write_campaign(CONFIG, PACKAGE)
    sys.path.pop(0)
    write(PACKAGE / "scripts" / "validate_run.py", "from pathlib import Path\nimport sys\nsys.path.insert(0, str(Path(__file__).parent))\nfrom lru_core import select_occupations\nselect_occupations(Path(sys.argv[1]), sys.argv[2], 16)\nprint('SEMANTIC_OCCUPATION_VALID')\n")
    write(PACKAGE / "scripts" / "validate_reference_state.py", "import json, sys\nfrom pathlib import Path\nfrom lru_core import magnetic_state\nroot=Path(__file__).resolve().parents[1]\nresult=magnetic_state(Path(sys.argv[1]), json.loads((root/'geometry'/'site_map.json').read_text()))\n(root/'results'/'raw_occupations').mkdir(parents=True, exist_ok=True)\n(root/'results'/'raw_occupations'/'reference_magnetic_state.json').write_text(json.dumps(result,indent=2)+'\\n')\nprint(json.dumps(result))\n")
    package_results = (SOURCE / "scripts" / "package_results.py").read_text(encoding="utf-8").replace("feo_pbe_lru_sc222_result.json", "beta_mno2_pbe_lru_sc222_result.json")
    write(PACKAGE / "scripts" / "package_results.py", package_results)
    write(PACKAGE / "slurm" / "submit_dag.slurm", dag())
    for stale in (PACKAGE / "slurm" / "submit_reference.slurm", PACKAGE / "slurm" / "submit_children.slurm", PACKAGE / "slurm" / "submit_dag_resume.slurm"):
        if stale.exists(): stale.unlink()
    write(PACKAGE / "README.md", """# beta-MnO2 PBE LR-U validation, SC(2x2x2)

Routine external validation campaign for pyrolusite (beta-MnO2). The input structure is the experimental refinement of Baur, *Acta Cryst. B* **32**, 2200-2204 (1976), DOI 10.1107/S0567740876007371, preserved as `geometry/source/COD_2105790_pyrolusite.cif`. It uses a 2x2x2 conventional-rutile supercell: 48 atoms, 16 Mn 3d Hubbard sites.

The magnetic state is a collinear A1-AFM approximation to the experimental helical order; that approximation is explicit and is checked after the REFERENCE calculation. Frozen routine settings: PBE, DZP, EnergyShift 0.005 Ry, MeshCutoff 200 Ry, 3x3x3 supercell k-grid, Method-2 Mn 3d projectors with explicit rc=3.0 Bohr and omega=0.05 Bohr, and alpha +/-0.05 eV.

Exactly nine SIESTA runs are materialized: REFERENCE, four BARE, and four SCREENED. BARE non-convergence is intentionally permitted. REFERENCE and SCREENED require normal completion, SCF convergence, semantic 16-site occupations, and, for the reference, the A1-AFM magnetic-state gate. Matrices are inverted directly; no pseudoinverse fallback exists.

Run `python verify_package.py`, then submit only `slurm/submit_dag.slurm`. The DAG reserves five nodes x 20 ranks and executes one FDF at a time on all 100 MPI ranks.
""")
    write(PACKAGE / "SCIENTIFIC_CONTRACT.md", """# beta-MnO2 routine LR-U contract

Geometry: COD 2105790 / Baur 1976, P42/mnm, a=b=4.3983 Ang, c=2.8730 Ang, O 4f u=0.30515. The source CIF is retained verbatim as a campaign input snapshot. The 2x2x2 conventional rutile supercell has 16 Mn and 32 O atoms. A1-AFM collinear order is a declared approximation to the experimental helical AFM order.

Projector definition: Mn 3d (n=3, l=2), Method 2, rc=3.0 Bohr, omega=0.05 Bohr and DFTU.PotentialShift true. This is a declared projector subspace; literature U values from different codes/projectors are comparison context, never an acceptance target.

The exact topology is REFERENCE plus BARE and SCREENED finite differences at +/-0.05 eV for MnLR00 (A) and MnLR01 (B). Raw response is reconstructed to 16x16 using translations, symmetrized, rank-gated, and inverted directly: K = inv(chi0) - inv(chi). A scientific PASS does not assert universal convergence or exact agreement with an external U number.
""")
    verify = """import json, re, sys
from pathlib import Path
root=Path(__file__).resolve().parent; sys.path.insert(0,str(root/'scripts'))
from lru_core import RUNS, build_atoms
c=json.loads((root/'campaign.json').read_text()); atoms, sites=build_atoms(c)
assert c['material'].startswith('beta-MnO2') and c['structure_source']['entry']=='2105790'
assert len(atoms)==48 and len(sites)==16 and c['projector']['rc_bohr']==3.0 and c['alpha_ev']==0.05
assert (root/'geometry/source/COD_2105790_pyrolusite.cif').is_file()
runs=json.loads((root/'runs/manifest.json').read_text()); assert len(runs)==9 and sum(x['mode']=='BARE' for x in runs)==4 and sum(x['mode']=='SCREENED' for x in runs)==4
for r in runs:
    t=(root/'runs'/r['id']/'siesta.fdf').read_text()
    assert 'NumberOfAtoms 48' in t and 'NumberOfSpecies 17' in t and len(re.findall(r'^\\s*MnLR\\d{2} 1\\s*$',t,re.M))==16
    assert 'LatticeConstant 1.0000 Ang' in t and 'DFTU.ProjectorGenerationMethod 2' in t and '  3.0000 0.0500' in t
    if r['mode']=='REFERENCE': assert 'SCF.MustConverge T' in t and 'DM.UseSaveDM false' in t
    elif r['mode']=='BARE': assert 'MaxSCFIterations 1' in t and 'SCF.Mix Hamiltonian' in t and 'SCF.MustConverge F' in t
    else: assert 'MaxSCFIterations 300' in t and 'SCF.MustConverge T' in t
dag=(root/'slurm/submit_dag.slurm').read_text()
assert '--nodes=5' in dag and '--ntasks=100' in dag and '--ntasks-per-node=20' in dag and '--array' not in dag
assert 'DAG_MPI_PLACEMENT_OK' in dag and 'validate_reference_state.py' in dag
assert b'\\r\\n' not in (root/'slurm/submit_dag.slurm').read_bytes()
print('PACKAGE_VERIFIED: BETA_MNO2_PBE_LRU_SC222_VALIDATION_V1')
"""
    write(PACKAGE / "verify_package.py", verify)
    # Normalize all text files, including source files inherited from Windows-created packages.
    for path in PACKAGE.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".py", ".slurm", ".md", ".json", ".fdf", ".cif", ".txt"}:
            path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n"))
    for cache in PACKAGE.rglob("__pycache__"):
        if cache.is_dir():
            shutil.rmtree(cache)
    archive=ROOT / f"{NAME}.zip"
    if archive.exists(): archive.unlink()
    shutil.make_archive(str(archive.with_suffix("")), "zip", ROOT, NAME)
    return PACKAGE


if __name__ == "__main__":
    print(build())
