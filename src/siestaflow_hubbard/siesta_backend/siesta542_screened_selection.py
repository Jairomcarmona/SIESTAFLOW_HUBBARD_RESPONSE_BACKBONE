"""Fail-closed selection of a converged SCREENED population in SIESTA 5.4.2.

The SCREENED response is the projected population of the self-consistent
density matrix.  In the audited SIESTA 5.4.2 Hamiltonian-mixing trace, a
converged run prints ``SCF Convergence ...``, then ``Using DM_out to compute
the final energy and forces``, and then recomputes the Hubbard populations
from that ``DM_out``.  That last block is the observation.  Selecting "the
last printed block" without these markers would silently accept an
interrupted or non-converged SCF, whose last block is an intermediate
iterate rather than a response.

This module is separate from the BARE profile on purpose: that profile is
bound by hash in archived software locks and is not modified here.
"""
from __future__ import annotations

import re

from siestaflow_hubbard.siesta_backend.event_parser import parse_hubbard_population_events
from siestaflow_hubbard.siesta_backend.parser_models import HubbardPopulationEvent


class ScreenedSelectionError(ValueError):
    """Raised when an output does not prove a converged SCREENED population."""


_CONVERGED = re.compile(r"^\s*SCF Convergence by .*criterion\s*$")
_NOT_CONVERGED = re.compile(r"SCF_NOT_CONV|SCF:\s*NOT CONVERGED", re.IGNORECASE)
_DM_OUT = re.compile(r"^\s*Using DM_out to compute the final energy and forces\s*$")
_COMPLETED = re.compile(r"^\s*Job completed\s*$")


def select_converged_screened_event(output_text: str) -> HubbardPopulationEvent:
    """Return the population recomputed from the converged ``DM_out``.

    Requirements (all must hold):

    * no ``SCF_NOT_CONV`` marker and exactly one ``SCF Convergence`` line;
    * a ``Using DM_out`` marker after the convergence line;
    * normal completion (``Job completed``) after the final ``Using DM_out``;
    * exactly one populated Hubbard block after the last ``Using DM_out``,
      ending before ``Job completed``.
    """
    lines = output_text.splitlines()
    if any(_NOT_CONVERGED.search(line) for line in lines):
        raise ScreenedSelectionError("SCREENED output reports a non-converged SCF")
    converged = [index for index, line in enumerate(lines) if _CONVERGED.match(line)]
    if len(converged) != 1:
        raise ScreenedSelectionError(
            "SCREENED output must contain exactly one SCF convergence marker; found {0}".format(len(converged))
        )
    dm_out = [index for index, line in enumerate(lines) if _DM_OUT.match(line)]
    if not dm_out or dm_out[-1] < converged[0]:
        raise ScreenedSelectionError("SCREENED output lacks a 'Using DM_out' marker after convergence")
    completed = [
        index for index, line in enumerate(lines)
        if index > dm_out[-1] and _COMPLETED.match(line)
    ]
    if not completed:
        raise ScreenedSelectionError("SCREENED output lacks normal completion after the final DM_out")
    completion_line = completed[0]
    # The event parser reports 0-based line indices, like ``lines`` above.
    final_line = dm_out[-1]
    events = [
        event for event in parse_hubbard_population_events(output_text)
        if event.source_start_line > final_line and event.atoms
    ]
    if len(events) != 1:
        raise ScreenedSelectionError(
            "expected one populated Hubbard block after the final 'Using DM_out'; found {0}".format(len(events))
        )
    if events[0].source_end_line is None or events[0].source_end_line >= completion_line:
        raise ScreenedSelectionError(
            "SCREENED population block does not end before normal completion"
        )
    return events[0]
