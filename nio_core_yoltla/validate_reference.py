import sys
from pathlib import Path
from siestaflow_hubbard.siesta_backend.event_parser import parse_hubbard_population_events

text = Path(sys.argv[1]).read_text(errors='ignore')
if not (Path(sys.argv[1]).parent / '0_NORMAL_EXIT').is_file() and 'siesta: normal completion' not in text.lower():
    raise RuntimeError('reference: normal SIESTA completion missing')
if 'scf: not converged' in text.lower():
    raise RuntimeError('reference: SCF did not converge')
events = parse_hubbard_population_events(text)
if not events:
    raise RuntimeError('reference: Hubbard occupations missing')
event = events[-1]
if len(event.atoms) != 2 or not all(atom.validate_traces() for atom in event.atoms):
    raise RuntimeError('reference: invalid Hubbard occupations for the two Ni sites')
