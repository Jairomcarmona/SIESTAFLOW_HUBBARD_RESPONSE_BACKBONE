"""Small standalone selector for the audited SIESTA 5.4.2 BARE event.

Campaign packages may copy this module beside their analyzer so that their
BARE selection does not depend on event ordinal or an installed project wheel.
"""
from __future__ import annotations

import re


def select_bare_occupations(output_text: str, n_sites: int) -> list[float]:
    """Select the complete population block after ``stepf`` and before SCF 1."""
    lines = output_text.splitlines()
    if not re.search(
        r"^\s*redata:\s+SCF mix quantity\s*=\s*Hamiltonian\s*$",
        output_text,
        re.IGNORECASE | re.MULTILINE,
    ):
        raise ValueError("BARE output does not attest Hamiltonian mixing")
    if not re.search(r"^\s*Version\s*:\s*5\.4\.2\s*$", output_text,
                     re.IGNORECASE | re.MULTILINE):
        raise ValueError("BARE output does not attest the audited SIESTA 5.4.2 version")

    stepf = [i for i, line in enumerate(lines)
             if re.match(r"^\s*stepf:\s+Fermi-Dirac step function\s*$", line, re.IGNORECASE)]
    first_scf = [i for i, line in enumerate(lines)
                 if re.match(r"^\s*scf:\s+1\b", line, re.IGNORECASE)]
    if len(stepf) != 1 or len(first_scf) != 1 or stepf[0] >= first_scf[0]:
        raise ValueError("BARE output lacks unique ordered stepf and scf:1 markers")

    events: list[tuple[int, int, int | None, list[float]]] = []
    start: int | None = None
    event_end: int | None = None
    iteration: int | None = None
    current_atom: int | None = None
    atom_ids: set[int] = set()
    occupations: list[float] = []

    def finish_event() -> None:
        nonlocal start, event_end, iteration, current_atom, atom_ids, occupations
        if start is not None:
            events.append((start, event_end if event_end is not None else start,
                           iteration, occupations))
        start, event_end, iteration, current_atom = None, None, None, None
        atom_ids, occupations = set(), []

    for line_number, line in enumerate(lines):
        if "hubbard_term: recalculating local occupations" in line:
            finish_event()
            start = line_number
            match = re.search(r"recalculating local occupations\s+(\d+)", line, re.IGNORECASE)
            iteration = int(match.group(1)) if match else None
        elif start is not None:
            atom_match = re.search(r"hubbard_term:\s+atom,\s+species:\s+(\d+)\s+\d+", line, re.IGNORECASE)
            if atom_match:
                current_atom = int(atom_match.group(1))
            elif "Occupations:" in line:
                if current_atom is None or current_atom in atom_ids:
                    raise ValueError("BARE population block has a missing or duplicate atom summary")
                values = re.findall(
                    r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[Ee][-+]?\d+)?",
                    line.split("Occupations:", 1)[1],
                )
                if len(values) == 3:
                    occupations.append(float(values[2]))
                elif len(values) == 2:
                    occupations.append(float(values[0]) + float(values[1]))
                else:
                    raise ValueError(f"unrecognized SIESTA Occupations summary: {line}")
                atom_ids.add(current_atom)
                event_end = line_number
                current_atom = None
    finish_event()

    complete = [(begin, end, values) for begin, end, iteration, values in events
                if iteration == 1 and len(values) == n_sites]
    parent = [(begin, end, values) for begin, end, values in complete if end < stepf[0]]
    response = [(begin, end, values) for begin, end, values in complete
                if stepf[0] < begin and end < first_scf[0]]
    if len(parent) != 1 or len(response) != 1:
        raise ValueError(
            "BARE output must contain one complete parent event before stepf and "
            "one response event between stepf and scf:1"
        )
    return response[0][2]
