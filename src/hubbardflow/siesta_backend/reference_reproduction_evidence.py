"""Fail closed parsing of D16 state reproduction evidence from reference outputs."""

from __future__ import annotations

from hubbardflow.domain.reference_reproduction import (
    OccupationEquivalence,
    ParentReproduction,
    ReferenceReproduction,
    ReproductionReason,
    ToleranceSource,
    compare_reference_states,
)
from hubbardflow.siesta_backend.event_parser import parse_hubbard_population_events
from hubbardflow.siesta_backend.point_state_evidence import build_point_state
from hubbardflow.siesta_backend.reference_state_evidence import require_converged_reference_output
from hubbardflow.siesta_backend.siesta542_screened_selection import select_converged_screened_event


class ReferenceIdentityMismatch(ValueError):
    """Parsed atom/projector inventory is incomplete or inconsistent."""


def reference_reproduction_evidence(
    planning_output: str,
    campaign_output: str,
    planning_dm_sha256: str | None,
    campaign_dm_sha256: str | None,
    criterion: ParentReproduction,
    expected_projectors: tuple[tuple[int, int], ...] | None = None,
    scf_dm_tolerance: float | None = None,
    tolerance_factor: float | None = None,
    tol_fermi_ev: float | None = None,
    fermi_tolerance_source: ToleranceSource | None = None,
) -> ReferenceReproduction:
    """Use final populations and stdout Fermi; DM digests are provenance only.

    Missing or malformed state evidence is recorded as not assessed. Matching
    digests never substitute for parsed, converged physical state evidence.
    Current point-state parsing supports collinear d projectors only; unsupported
    output remains an explicit rejection instead of an inferred equivalence.
    """
    side = "planning"
    try:
        states = []
        identities = []
        for side, output in (("planning", planning_output), ("campaign", campaign_output)):
            require_converged_reference_output(output)
            events = parse_hubbard_population_events(output)
            if not events or not events[-1].atoms:
                raise ValueError("last population event is missing or empty")
            event = events[-1]
            selected = select_converged_screened_event(output)
            if selected.source_start_line != event.source_start_line:
                raise ValueError("last population event is not the converged DM_out event")
            if expected_projectors is not None:
                observed = tuple(sorted((atom.atom_index, len(atom.raw_matrix_up)) for atom in event.atoms))
                if observed != tuple(sorted(expected_projectors)):
                    raise ReferenceIdentityMismatch(
                        f"atom/projector inventory incomplete: expected={expected_projectors}, observed={observed}"
                    )
            identities.append(
                tuple((atom.atom_index, atom.species_index, atom.channel_count) for atom in event.atoms)
            )
            states.append(build_point_state(event, output))
        if identities[0] != identities[1]:
            raise ReferenceIdentityMismatch(
                f"atom/projector identities differ: planning={identities[0]}, campaign={identities[1]}"
            )
        return compare_reference_states(
            states[0],
            states[1],
            planning_dm_sha256,
            campaign_dm_sha256,
            scf_dm_tolerance,
            tolerance_factor,
            criterion,
            tol_fermi_ev,
            fermi_tolerance_source,
        )
    except ReferenceIdentityMismatch as exc:
        return ReferenceReproduction(
            criterion,
            ReproductionReason.PARENT_IDENTITY_NOT_ESTABLISHED,
            planning_dm_sha256,
            campaign_dm_sha256,
            str(exc),
            all_reduced_classes_affected=True,
            occupation_equivalence=OccupationEquivalence.NOT_EQUIVALENT,
            declared_fermi_tolerance_ev=tol_fermi_ev,
            fermi_tolerance_source=fermi_tolerance_source,
        )
    except Exception as exc:  # noqa: BLE001 - unsupported or malformed state evidence remains unassessed.
        return ReferenceReproduction(
            criterion,
            ReproductionReason.EQUIVALENCE_NOT_ASSESSED,
            planning_dm_sha256,
            campaign_dm_sha256,
            f"{side} reference state unparseable or invalid: {type(exc).__name__}: {exc}",
            declared_fermi_tolerance_ev=tol_fermi_ev,
            fermi_tolerance_source=fermi_tolerance_source,
        )
