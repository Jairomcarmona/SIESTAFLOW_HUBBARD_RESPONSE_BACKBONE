"""Source-audited BARE profile for SIESTA 5.4.2 PotentialShift runs.

This module deliberately does not alter the historical two-step, density-mixed
BARE materialisation.  Its contract is narrower: it materialises and audits a
version-specific trace in which the response occupation is printed after the
first diagonalisation of ``H_ref + alpha P`` and before the first SCF summary.

The ordering was audited against upstream SIESTA 5.4.2 source revision
``e486d12067b96ff688179f0496d0ec21b6fae0ab``.  Any other SIESTA version,
mixing target, or output layout must use another explicit profile.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import ClassVar, Dict, Iterable, List

from siestaflow_hubbard.siesta_backend.event_parser import parse_hubbard_population_events
from siestaflow_hubbard.siesta_backend.parser_models import HubbardPopulationEvent


class Siesta542BareProfileError(ValueError):
    """Raised when an input or output cannot satisfy this audited profile."""


@dataclass(frozen=True)
class BareResponseSelection:
    """The two population blocks that establish the source-audited ordering."""

    pre_perturbation_event: HubbardPopulationEvent
    response_event: HubbardPopulationEvent
    stepf_line: int
    first_scf_line: int


@dataclass(frozen=True)
class Siesta542PotentialShiftHamiltonianProfile:
    """Fail-closed SIESTA 5.4.2 profile for a candidate \u03c7\u2070 observation.

    ``MaxSCFIterations 1`` is intentional: the profile keeps the run to the
    first diagonalisation under the perturbed Hamiltonian.  ``SCF.MustConverge
    false`` is only a termination policy; it is not evidence about BARE
    semantics.  The evidence is the source-audited ordering selected from the
    native output.
    """

    profile_id: str = "siesta-5.4.2-potential-shift-hamiltonian-v1"
    profile_version: str = "1"
    source_revision: str = "e486d12067b96ff688179f0496d0ec21b6fae0ab"

    _REQUIRED: ClassVar[None] = None  # reserved: required values are generated below

    @property
    def required_fdf_values(self) -> Dict[str, str]:
        return {
            "DFTU.PotentialShift": "true",
            "DFTU.FirstIteration": "true",
            "DM.UseSaveDM": "true",
            "SCF.Mix": "hamiltonian",
            "MaxSCFIterations": "1",
            "SCF.MustConverge": "false",
        }

    def materialize(self, fdf_text: str) -> str:
        """Return a profile-specific FDF without changing unrelated content."""
        result = fdf_text
        for key, value in self.required_fdf_values.items():
            result = _replace_or_append_key(result, key, value)
        self.validate_fdf(result)
        return result

    def validate_fdf(self, fdf_text: str) -> None:
        """Reject missing, duplicate-conflicting, or non-profile FDF values."""
        for key, expected in self.required_fdf_values.items():
            values = _fdf_values(fdf_text, key)
            if not values:
                raise Siesta542BareProfileError("Missing required FDF key: {0}".format(key))
            if len(values) != 1:
                raise Siesta542BareProfileError(
                    "Duplicate definitions for critical FDF key {0}: {1}".format(key, values)
                )
            normalised = {_normalise_fdf_value(value) for value in values}
            if len(normalised) != 1:
                raise Siesta542BareProfileError(
                    "Conflicting values for {0}: {1}".format(key, values)
                )
            actual = normalised.pop()
            if actual != expected:
                raise Siesta542BareProfileError(
                    "{0} must be {1!r}, got {2!r}".format(key, expected, actual)
                )

    def select_response(self, output_text: str) -> BareResponseSelection:
        """Select the first-iteration response from a native 5.4.2 output.

        SIESTA 5.4.2 Hamiltonian mixing prints the parent DFT+U occupations
        during ``setup_hamiltonian(0)``, then prints ``stepf`` after the first
        diagonalisation, then prints the candidate perturbed occupations during
        ``setup_hamiltonian(1)``, before ``scf: 1``.  The selected region is
        therefore a structural assertion, not an ordinal event guess.
        """
        lines = output_text.splitlines()
        self._validate_output_signature(lines)
        stepf_lines = [
            index for index, line in enumerate(lines)
            if re.match(r"^\s*stepf:\s+Fermi-Dirac step function\s*$", line)
        ]
        if len(stepf_lines) != 1:
            raise Siesta542BareProfileError(
                "Expected exactly one first-diagonalisation stepf marker, found {0}".format(
                    len(stepf_lines)
                )
            )
        first_scf_lines = [
            index for index, line in enumerate(lines)
            if re.match(r"^\s*scf:\s+1\b", line)
        ]
        if len(first_scf_lines) != 1:
            raise Siesta542BareProfileError(
                "Expected exactly one 'scf: 1' marker, found {0}".format(len(first_scf_lines))
            )

        stepf_line = stepf_lines[0]
        first_scf_line = first_scf_lines[0]
        if stepf_line >= first_scf_line:
            raise Siesta542BareProfileError("Invalid output ordering: stepf is not before scf: 1")

        events = parse_hubbard_population_events(output_text)
        if not events:
            raise Siesta542BareProfileError("No Hubbard population events were parsed")

        candidates = [
            event for event in events
            if _within(event.source_start_line, stepf_line, first_scf_line)
            and _within(event.source_end_line, stepf_line, first_scf_line)
        ]
        if len(candidates) != 1:
            raise Siesta542BareProfileError(
                "Expected one response population block between stepf and scf: 1, found {0}".format(
                    len(candidates)
                )
            )
        response = candidates[0]
        if response.dftu_population_iteration != 1 or not response.atoms:
            raise Siesta542BareProfileError(
                "Response block is not a populated DFTU first-iteration block"
            )

        parent = [
            event for event in events
            if event.source_end_line is not None and event.source_end_line < stepf_line
        ]
        if len(parent) != 1 or parent[0].dftu_population_iteration != 1 or not parent[0].atoms:
            raise Siesta542BareProfileError(
                "Expected one populated parent DFTU first-iteration block before stepf"
            )
        return BareResponseSelection(parent[0], response, stepf_line, first_scf_line)

    @staticmethod
    def _validate_output_signature(lines: Iterable[str]) -> None:
        if not any(
            re.match(r"^\s*redata:\s+SCF mix quantity\s*=\s*Hamiltonian\s*$", line, re.I)
            for line in lines
        ):
            raise Siesta542BareProfileError(
                "Output does not attest 'SCF mix quantity = Hamiltonian'"
            )


def _within(value: int, lower: int, upper: int) -> bool:
    return value is not None and lower < value < upper


def _normalise_fdf_value(value: str) -> str:
    return " ".join(value.strip().split()).lower()


def _fdf_values(fdf_text: str, key: str) -> List[str]:
    expression = re.compile(r"^\s*" + re.escape(key) + r"\s+(.+?)\s*(?:#.*)?$", re.I)
    values = []
    for line in fdf_text.splitlines():
        match = expression.match(line)
        if match:
            values.append(match.group(1))
    return values


def _replace_or_append_key(fdf_text: str, key: str, value: str) -> str:
    expression = re.compile(r"^(\s*)" + re.escape(key) + r"\s+.*$", re.I)
    lines = fdf_text.splitlines()
    replacement = "{0} {1}".format(key, value)
    found = False
    result = []
    for line in lines:
        if expression.match(line):
            if not found:
                result.append(replacement)
                found = True
            # Drop duplicate definitions rather than allowing silent FDF ambiguity.
            continue
        result.append(line)
    if not found:
        result.append(replacement)
    return "\n".join(result) + "\n"
