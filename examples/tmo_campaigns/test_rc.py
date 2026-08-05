import os
import subprocess

template = """SystemName          Cu Test
SystemLabel         cu_test
NumberOfAtoms       1
NumberOfSpecies     1
%block ChemicalSpeciesLabel
 1  29  Cu1
%endblock ChemicalSpeciesLabel
LatticeConstant     3.81 Ang
%block LatticeVectors
 1.0  0.0  0.0
 0.0  1.0  0.0
 0.0  0.0  1.0
%endblock LatticeVectors
AtomicCoordinatesFormat Fractional
%block AtomicCoordinatesAndAtomicSpecies
 0.0  0.0  0.0  1
%endblock AtomicCoordinatesAndAtomicSpecies
PAO.BasisSize       DZP
MeshCutoff          300.0 Ry
MaxSCFIterations    1

%block DFTU.proj
  Cu1 1
  3 2 {rc_str}
  0.0 0.0
  0.0
%endblock DFTU.proj
"""

variants = ['0.0', '1.0', '1.0 0.1', '1.5 0.2', '']
for v in variants:
    print(f'Testing rc_str = "{v}"')
    fdf = template.format(rc_str=v)
    with open('test_rc.fdf', 'w') as f:
        f.write(fdf)
    res = subprocess.run('wsl -e /home/jmc/.local/siesta-5.4.2-openmpi/bin/siesta < test_rc.fdf > test_rc.out', shell=True, capture_output=True, text=True)
    with open('test_rc.out') as f:
        out = f.read()
    if 'Insert one value' in out:
        print('  Failed with rc/width error')
    elif 'SCF_NOT_CONV' in out or 'Job completed' in out:
        print('  SUCCESS!')
        break
    else:
        print('  Failed with other error')
