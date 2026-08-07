import re
import numpy as np
from typing import List, Dict, Tuple, Optional
from siestaflow_hubbard.siesta_backend.parser_models import (
    HubbardAtomPopulation,
    HubbardPopulationEvent,
    ObservationRole
)
from siestaflow_hubbard.domain.exceptions import SiestaParserError, SemanticValidationFailure

class ParseSemanticMismatch(SemanticValidationFailure):
    """Raised when the parsed traces do not match the printed summary in SIESTA output."""
    pass

class UnsupportedSpinFormat(SiestaParserError):
    """Raised when the output has an unknown or unvalidated spin format (e.g. SOC non-collinear)."""
    pass


def parse_hubbard_population_events(output_content: str) -> List[HubbardPopulationEvent]:
    """
    Sequentially parses a SIESTA .out file to extract ALL Hubbard population events.
    Does NOT assign scientific roles (BARE/SCREENED). Outputs RAW events UNCLASSIFIED.
    """
    events = []
    
    lines = output_content.splitlines()
    current_iscf = None
    occurrence_index = 0
    
    in_event = False
    current_event = None
    
    current_atom_idx = None
    current_species_idx = None
    current_matrix_lines = []
    current_summary_line = None
    
    def finalize_atom():
        nonlocal current_atom_idx, current_species_idx, current_matrix_lines, current_summary_line
        if current_atom_idx is None:
            return
            
        # Parse elements
        elements = []
        max_m = 0
        has_down = False
        
        for m1_str, m2_str, up_str, down_str in current_matrix_lines:
            m1 = int(m1_str)
            m2 = int(m2_str)
            if m1 > max_m: max_m = m1
            if m2 > max_m: max_m = m2
            
            up_val = float(up_str)
            if down_str:
                has_down = True
                down_val = float(down_str)
            else:
                down_val = None
                
            elements.append((m1, m2, up_val, down_val))
            
        # Check for duplicates
        seen_indices = set()
        for m1, m2, _, _ in elements:
            if (m1, m2) in seen_indices:
                raise SiestaParserError(f"Atom {current_atom_idx}: Duplicate matrix index ({m1}, {m2})")
            seen_indices.add((m1, m2))
            
        if len(elements) != max_m * max_m:
            raise SiestaParserError(
                f"Atom {current_atom_idx}: Matrix incomplete or truncated. "
                f"Expected {max_m * max_m} elements, got {len(elements)}"
            )
            
        mat_up = np.zeros((max_m, max_m))
        mat_down = np.zeros((max_m, max_m)) if has_down else None
        
        trace_up = 0.0
        trace_down = 0.0
        
        for m1, m2, up_val, down_val in elements:
            mat_up[m1-1, m2-1] = up_val
            if m1 == m2:
                trace_up += up_val
                
            if has_down:
                mat_down[m1-1, m2-1] = down_val
                if m1 == m2:
                    trace_down += down_val
                    
        trace_total = trace_up + (trace_down if has_down else trace_up)

        # Parse summary
        if not current_summary_line:
            raise SiestaParserError(f"Atom {current_atom_idx}: Missing 'Occupations:' summary.")
            
        # Matches formats:
        # non-pol: Occupations:   0.88099  0.88099
        # pol:     Occupations:   0.44049  0.44049  0.88099
        sum_parts = re.findall(r'[-+]?\d*\.\d+', current_summary_line.split("Occupations:")[1])
        
        if len(sum_parts) == 3:
            printed_up = float(sum_parts[0])
            printed_down = float(sum_parts[1])
            printed_total = float(sum_parts[2])
        elif len(sum_parts) == 2:
            printed_up = float(sum_parts[0])
            printed_down = float(sum_parts[1])  # same in non-pol
            printed_total = printed_up + printed_down
        else:
            raise UnsupportedSpinFormat(f"Atom {current_atom_idx}: Unknown Occupations format: {current_summary_line}")
            
        atom = HubbardAtomPopulation(
            atom_index=current_atom_idx,
            species_index=current_species_idx,
            raw_matrix_up=mat_up,
            raw_matrix_down=mat_down,
            channel_count=2 if has_down else 1,
            trace_up=trace_up,
            trace_down=trace_down if has_down else trace_up,
            trace_total=trace_total,
            printed_total_trace=printed_total,
            printed_up_trace=printed_up,
            printed_down_trace=printed_down
        )
        
        if not atom.validate_traces():
            raise ParseSemanticMismatch(
                f"Atom {current_atom_idx}: Trace mismatch. "
                f"Computed: {trace_total}, Printed: {printed_total}"
            )
            
        current_event.atoms.append(atom)
        
        current_atom_idx = None
        current_species_idx = None
        current_matrix_lines = []
        current_summary_line = None

    
    for line_idx, line in enumerate(lines):
        # Context tracking
        iscf_match = re.search(r'siesta:\s+iscf\s*=\s*(\d+)', line)
        if iscf_match:
            current_iscf = int(iscf_match.group(1))
            
        # Event start
        if "hubbard_term: recalculating local occupations" in line:
            if in_event:
                finalize_atom()
                current_event.source_end_line = line_idx - 1
                events.append(current_event)
                
            in_event = True
            current_event = HubbardPopulationEvent(
                occurrence_index=occurrence_index,
                dftu_population_iteration=None, # Attempt to extract if present
                scf_iteration=current_iscf,
                context="recalculating local occupations",
                atoms=[],
                source_start_line=line_idx
            )
            occurrence_index += 1
            
            # Check for population counter
            match = re.search(r'recalculating local occupations\s+(\d+)', line)
            if match:
                current_event.dftu_population_iteration = int(match.group(1))
            continue
            
        if not in_event:
            continue
            
        # Atom start
        atom_match = re.search(r'hubbard_term:\s+atom,\s+species:\s+(\d+)\s+(\d+)', line)
        if atom_match:
            finalize_atom()
            current_atom_idx = int(atom_match.group(1))
            current_species_idx = int(atom_match.group(2))
            continue
            
        # Inside atom block
        if current_atom_idx is not None:
            # Check for matrix lines (1 2 0.000 0.000)
            mat_match = re.match(r'^\s*([1-9]\d*)\s+([1-9]\d*)\s+([-+]?\d*\.\d+)(?:\s+([-+]?\d*\.\d+))?', line)
            if mat_match:
                current_matrix_lines.append(mat_match.groups())
                continue
                
            # Check for occupations summary
            if "Occupations:" in line:
                current_summary_line = line
                continue
                
        # Detect end of the whole recalculation block if another major section begins
        # e.g., "recalculating Hamiltonian" or "siesta: iscf"
        if "recalculating Hamiltonian" in line or "siesta: iscf" in line or "post-SCF" in line.lower():
            finalize_atom()
            current_event.source_end_line = line_idx - 1
            events.append(current_event)
            in_event = False
            current_event = None
            continue
            
    # EOF cleanup
    if in_event:
        finalize_atom()
        current_event.source_end_line = len(lines) - 1
        events.append(current_event)

    return events
