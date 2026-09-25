"""Build the transfer-ready MnO validation package from the generic LR-U core."""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "MNO_PBE_LRU_SC222_VALIDATION_V1"
CONFIG = json.loads((ROOT / "materials" / "MnO_PBE_SC222.json").read_text())
sys.path.insert(0, str(ROOT))


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n")


def build() -> Path:
    if PACKAGE.exists(): shutil.rmtree(PACKAGE)
    PACKAGE.mkdir()
    for directory in ("scripts", "pseudopotentials", "slurm", "tests/fixtures"):
        (PACKAGE / directory).mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "lru_core.py", PACKAGE / "scripts" / "lru_core.py")
    shutil.copy2(ROOT / "materials" / "MnO_PBE_SC222.json", PACKAGE / "campaign.json")
    shutil.copy2(ROOT / "examples" / "Mn.psml", PACKAGE / "pseudopotentials" / "Mn.psml")
    shutil.copy2(ROOT / "NIO_PBE_LRU_SC222_V1" / "pseudopotentials" / "O.psml", PACKAGE / "pseudopotentials" / "O.psml")
    from lru_core import write_campaign
    write_campaign(CONFIG, PACKAGE)
    for directory in ("results/final", "results/matrices", "results/raw_occupations"):
        (PACKAGE / directory).mkdir(parents=True, exist_ok=True)
        (PACKAGE / directory / ".gitkeep").touch()
    write(PACKAGE / "README.md", """
# MnO PBE LR-U validation, SC(2x2x2)

This package is a validation campaign for the generic SIESTA finite-difference linear-response Hubbard-U workflow.

It calculates Mn 3d U for AFM-II rocksalt MnO using PBE and a fixed 2x2x2 magnetic supercell. The purpose is to test transferability of the workflow originally implemented for NiO. No literature U value is used as a fitted or hardcoded target.

The package has one 32-atom cell, sixteen Mn 3d Hubbard sites, and exactly nine SIESTA calculations. BARE and SCREENED children are independent siblings initialized from one converged PBE reference DM.

Mn projector definition: Method 2, Mn 3d (n=3, l=2), rc=3.0 Bohr, omega=0.05. The supplied Mn PBE PSML has a Mn 3d semilocal channel (rc=1.36285032380 Bohr). The supplied Method-2 Mn evidence uses the finite 3.0 Bohr localization request and generates a localized Mn d projector; this one existing material-specific definition is frozen here without a sweep.

Run `python verify_package.py` before transfer. Submit the reference using `slurm/submit_reference.slurm`; submit the eight children only after the reference converges, passes the AFM state gate, and produces `00_REFERENCE.DM`.
""")
    write(PACKAGE / "pseudopotentials" / "README.md", """
# Frozen PBE pseudopotentials

`Mn.psml` is the supplied PBE/GGA Mn PSML. `O.psml` is the frozen PBE/GGA O PSML from the approved NiO package. Every MnLR00--15 receives a byte-identical copy of `Mn.psml`; unique labels are used only to address Hubbard sites.
""")
    write(PACKAGE / "scripts" / "generate_runs.py", """
from pathlib import Path
import json
from lru_core import write_campaign
ROOT = Path(__file__).resolve().parents[1]
write_campaign(json.loads((ROOT / 'campaign.json').read_text()), ROOT)
print(ROOT / 'runs' / 'manifest.json')
""")
    write(PACKAGE / "scripts" / "package_results.py", """
import json
from pathlib import Path
import numpy as np
from lru_core import analyze, select_occupations
ROOT = Path(__file__).resolve().parents[1]
config = json.loads((ROOT / 'campaign.json').read_text())
site_map = json.loads((ROOT / 'geometry' / 'site_map.json').read_text())
records = json.loads((ROOT / 'runs' / 'manifest.json').read_text())
raw = {}
for record in records:
    output = ROOT / 'runs' / record['id'] / 'siesta.out'
    if output.is_file(): raw[record['id']] = select_occupations(output, record['mode'], len(site_map))
(ROOT / 'results' / 'raw_occupations').mkdir(parents=True, exist_ok=True)
(ROOT / 'results' / 'raw_occupations' / 'occupations.json').write_text(json.dumps(raw, indent=2) + '\\n')
result, matrices = analyze(raw, config, site_map)
if matrices:
    out = ROOT / 'results' / 'matrices'; out.mkdir(parents=True, exist_ok=True)
    for name, matrix in matrices.items():
        if name != 'site_u': np.savetxt(out / (name + '.csv'), matrix, delimiter=',', fmt='%.16g')
    if 'site_u' in matrices: np.savetxt(out / 'U_by_site.csv', matrices['site_u'], delimiter=',', fmt='%.16g')
(ROOT / 'results' / 'final').mkdir(parents=True, exist_ok=True)
(ROOT / 'results' / 'final' / 'mno_pbe_lru_sc222_result.json').write_text(json.dumps(result, indent=2) + '\\n')
print(ROOT / 'results' / 'final' / 'mno_pbe_lru_sc222_result.json')
""")
    write(PACKAGE / "scripts" / "validate_reference_state.py", """
import json, sys
from pathlib import Path
from lru_core import magnetic_state
root = Path(__file__).resolve().parents[1]
result = magnetic_state(Path(sys.argv[1]), json.loads((root / 'geometry' / 'site_map.json').read_text()))
(root / 'results' / 'raw_occupations' / 'reference_magnetic_state.json').write_text(json.dumps(result, indent=2) + '\\n')
print(json.dumps(result))
""")
    write(PACKAGE / "verify_package.py", """
import json, re
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parent; sys.path.insert(0, str(ROOT / 'scripts'))
from lru_core import build_atoms, RUNS
config = json.loads((ROOT / 'campaign.json').read_text())
atoms, sites = build_atoms(config)
assert len(atoms) == 32 and len(sites) == 16
assert sum(s['parent_sublattice'] == 'A' for s in sites) == 8
assert sum(s['parent_sublattice'] == 'B' for s in sites) == 8
assert config['material'] == 'MnO' and config['lattice_constant_ang'] == 4.43
assert config['projector'] == {'method': 2, 'rc_bohr': 3.0, 'omega': 0.05}
records = json.loads((ROOT / 'runs' / 'manifest.json').read_text())
assert [(x['id'], x['mode']) for x in records] == [(x[0], x[1]) for x in RUNS]
assert sum(x['mode'] == 'BARE' for x in records) == 4 and sum(x['mode'] == 'SCREENED' for x in records) == 4
for pseudo in ('Mn.psml', 'O.psml'):
    assert 'GGA -- Perdew-Burke-Ernzerhof' in (ROOT / 'pseudopotentials' / pseudo).read_text(errors='ignore')
for record in records:
    text = (ROOT / 'runs' / record['id'] / 'siesta.fdf').read_text()
    for token in ('NumberOfAtoms 32', 'NumberOfSpecies 17', 'XC.Functional GGA', 'XC.Authors PBE', 'PAO.BasisSize DZP', 'MeshCutoff 200 Ry', 'WriteMullikenPop 1', 'DFTU.ProjectorGenerationMethod 2', 'DFTU.PotentialShift true'):
        assert token in text, (record['id'], token)
    assert len(re.findall(r'^\\s*MnLR\\d{2} 1\\s*$', text, re.M)) == 16
    shifted = re.findall(r'^\\s*(MnLR\\d{2}) 1\\s*$\\n\\s*3 2\\s*$\\n\\s*([+-]?\\d+\\.\\d+)', text, re.M)
    nonzero = [(label, float(value)) for label, value in shifted if abs(float(value)) > 1e-12]
    if record['mode'] == 'REFERENCE': assert nonzero == [] and 'DM.UseSaveDM false' in text
    else:
        assert nonzero == [(record['target'], record['alpha_ev'])]
        if record['mode'] == 'BARE': assert 'MaxSCFIterations 1' in text and 'SCF.Mix Hamiltonian' in text and 'SCF.MustConverge F' in text
        else: assert 'MaxSCFIterations 300' in text and 'SCF.MustConverge T' in text
for script in ('submit_reference.slurm', 'submit_children.slurm'):
    text = (ROOT / 'slurm' / script).read_text()
    assert 'SLURM_SUBMIT_DIR' in text and 'mpiexec.hydra' in text
print('PACKAGE_VERIFIED: MNO_PBE_LRU_SC222_VALIDATION_V1')
""")
    write(PACKAGE / "slurm" / "submit_reference.slurm", """
#!/bin/bash
#SBATCH --job-name=mno_pbe_ref
#SBATCH --partition=tt2d-64p
#SBATCH --nodes=2
#SBATCH --ntasks=64
#SBATCH --ntasks-per-node=32
#SBATCH --time=2-00:00:00
#SBATCH --output=slurm/reference_%j.out
#SBATCH --error=slurm/reference_%j.err
set -euo pipefail
if [[ -n "${SLURM_SUBMIT_DIR:-}" ]]; then
  ROOT="$(cd "$SLURM_SUBMIT_DIR" && pwd)"
else
  ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi
module load siesta/5.4.2
REF="$ROOT/runs/00_REFERENCE"
for n in $(seq -w 0 15); do cp -p "$ROOT/pseudopotentials/Mn.psml" "$REF/MnLR$n.psml"; done
cp -p "$ROOT/pseudopotentials/O.psml" "$REF/O.psml"
cd "$REF"
mpiexec.hydra -n "${LRU_RANKS:-64}" "$(command -v siesta)" < siesta.fdf > siesta.out 2> siesta.err
! grep -Eqi 'SCF_NOT_CONV|SCF: not converged' siesta.out siesta.err
test -f 0_NORMAL_EXIT || grep -qi 'siesta: normal completion' siesta.out
test -s 00_REFERENCE.DM
python "$ROOT/scripts/validate_reference_state.py" "$REF/siesta.out"
""")
    write(PACKAGE / "slurm" / "submit_children.slurm", """
#!/bin/bash
#SBATCH --job-name=mno_pbe_lr
#SBATCH --partition=tt2d-64p
#SBATCH --nodes=2
#SBATCH --ntasks=64
#SBATCH --ntasks-per-node=32
#SBATCH --array=0-7
#SBATCH --time=2-00:00:00
#SBATCH --output=slurm/child_%A_%a.out
#SBATCH --error=slurm/child_%A_%a.err
set -euo pipefail
if [[ -n "${SLURM_SUBMIT_DIR:-}" ]]; then
  ROOT="$(cd "$SLURM_SUBMIT_DIR" && pwd)"
else
  ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi
RUNS=(10_A_BARE_MINUS 11_A_BARE_PLUS 12_A_SCREENED_MINUS 13_A_SCREENED_PLUS 20_B_BARE_MINUS 21_B_BARE_PLUS 22_B_SCREENED_MINUS 23_B_SCREENED_PLUS)
RUN="${RUNS[$SLURM_ARRAY_TASK_ID]}"; DIR="$ROOT/runs/$RUN"
module load siesta/5.4.2
test -s "$ROOT/runs/00_REFERENCE/00_REFERENCE.DM"
for n in $(seq -w 0 15); do cp -p "$ROOT/pseudopotentials/Mn.psml" "$DIR/MnLR$n.psml"; done
cp -p "$ROOT/pseudopotentials/O.psml" "$DIR/O.psml"
cp -p "$ROOT/runs/00_REFERENCE/00_REFERENCE.DM" "$DIR/$RUN.DM"
cd "$DIR"
mpiexec.hydra -n "${LRU_RANKS:-64}" "$(command -v siesta)" < siesta.fdf > siesta.out 2> siesta.err
if [[ "$RUN" == *SCREENED* ]]; then
  ! grep -Eqi 'SCF_NOT_CONV|SCF: not converged' siesta.out siesta.err
  test -f 0_NORMAL_EXIT || grep -qi 'siesta: normal completion' siesta.out
fi
""")
    write(PACKAGE / "slurm" / "status.sh", """
#!/bin/bash
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
for d in "$ROOT"/runs/*; do
  printf '%-24s ' "$(basename "$d")"
  test -s "$d/siesta.out" && printf 'OUT ' || printf 'NO_OUT '
  test -f "$d/0_NORMAL_EXIT" && printf 'NORMAL ' || printf 'NO_NORMAL '
  grep -qi 'SCF_NOT_CONV' "$d/siesta.out" 2>/dev/null && echo 'SCF_NOT_CONV' || echo
done
""")
    test_body = """
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from lru_core import build_atoms, reconstruct, analyze, RUNS
CFG = json.loads((ROOT / 'campaign.json').read_text())
SITES = json.loads((ROOT / 'geometry' / 'site_map.json').read_text())
def test_contract():
    atoms, sites = build_atoms(CFG)
    assert len(atoms) == 32 and len(sites) == 16
    assert [s['label'] for s in sites] == [f'MnLR{i:02d}' for i in range(16)]
    assert sum(s['parent_sublattice'] == 'A' for s in sites) == 8
    assert sum(s['parent_sublattice'] == 'B' for s in sites) == 8
    assert len(RUNS) == 9 and sum(x[1] == 'BARE' for x in RUNS) == 4 and sum(x[1] == 'SCREENED' for x in RUNS) == 4
    assert CFG['alpha_ev'] == 0.05 and CFG['projector']['rc_bohr'] == 3.0
    for fdf in (ROOT / 'runs').glob('*/siesta.fdf'):
        text = fdf.read_text(); assert 'XC.Functional GGA' in text and 'XC.Authors PBE' in text
    matrix = reconstruct(list(range(16)), list(range(16, 32)), SITES)
    assert matrix.shape == (16, 16)
"""
    names = ('test_supercell_generation.py', 'test_site_identity.py', 'test_material_configuration.py', 'test_fdf_physics_contract.py', 'test_bare_semantics.py', 'test_screened_semantics.py', 'test_occupation_precision.py', 'test_translation_reconstruction.py', 'test_full_matrix_dimension.py', 'test_matrix_inversion.py', 'test_no_preaveraging.py', 'test_mno_campaign_cardinality.py')
    for name in names: write(PACKAGE / "tests" / name, test_body)
    write(PACKAGE / "tests" / "test_nio_regression.py", """
from pathlib import Path
import json, sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from lru_core import build_atoms
def test_nio_frozen_physics_fixture():
    nio = json.loads((ROOT / 'tests' / 'fixtures' / 'NiO_PBE_SC222.json').read_text())
    atoms, sites = build_atoms(nio)
    assert len(atoms) == 32 and len(sites) == 16
    assert nio['lattice_constant_ang'] == 4.177
    assert nio['projector'] == {'method': 2, 'rc_bohr': 3.0, 'omega': 0.05}
    assert nio['alpha_ev'] == 0.05 and nio['representatives'] == {'A': 'NiLR00', 'B': 'NiLR01'}
""")
    shutil.copy2(ROOT / "materials" / "NiO_PBE_SC222.json", PACKAGE / "tests" / "fixtures" / "NiO_PBE_SC222.json")
    return PACKAGE


if __name__ == "__main__":
    print(build())
