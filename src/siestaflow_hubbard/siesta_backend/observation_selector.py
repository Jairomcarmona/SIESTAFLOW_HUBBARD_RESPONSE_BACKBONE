from typing import List, Optional
from siestaflow_hubbard.siesta_backend.parser_models import HubbardPopulationEvent, ObservationRole

class ObservationPolicyError(Exception):
    pass

class Siesta542BarePolicyV1:
    """
    Implements the 'siesta-5.4.2-lr-bare-v1' policy.
    Maps raw Hubbard population events to their scientific roles in a Linear Response calculation.
    """
    
    @staticmethod
    def get_reference_observation(events: List[HubbardPopulationEvent]) -> HubbardPopulationEvent:
        """
        Extracts n_ref: The population evaluated on the unperturbed reference DM
        before the first perturbed diagonalization.
        In SIESTA 5.4.2, this is always the first event printed during SCF iteration 1.
        """
        if not events:
            raise ObservationPolicyError("No events found. Cannot extract reference observation.")
            
        candidate = events[0]
        # In a well-formed log, the first event is n_ref.
        # We assign it a copy with the new role.
        event_copy = HubbardPopulationEvent(
            occurrence_index=candidate.occurrence_index,
            dftu_population_iteration=candidate.dftu_population_iteration,
            scf_iteration=candidate.scf_iteration,
            context=candidate.context,
            atoms=candidate.atoms,
            source_start_line=candidate.source_start_line,
            source_end_line=candidate.source_end_line,
            role=ObservationRole.REFERENCE
        )
        return event_copy

    @staticmethod
    def get_bare_observation(events: List[HubbardPopulationEvent]) -> HubbardPopulationEvent:
        """
        Extracts n0(alpha): The population evaluated on the density matrix immediately 
        following the first perturbed diagonalization.
        With the strict BARE SCF protocol (Linear mix, weight 1.0), the D_in of SCF iteration 2
        is exactly D_out of SCF iteration 1. Therefore, the first event of SCF iteration 2
        is the BARE response.
        If the output does not have a second event, it failed.
        """
        if len(events) < 2:
            raise ObservationPolicyError("Insufficient events to extract BARE observation. Need at least 2.")
            
        # The BARE observation is the second event (first of SCF step 2)
        candidate = events[1]
        
        event_copy = HubbardPopulationEvent(
            occurrence_index=candidate.occurrence_index,
            dftu_population_iteration=candidate.dftu_population_iteration,
            scf_iteration=candidate.scf_iteration,
            context=candidate.context,
            atoms=candidate.atoms,
            source_start_line=candidate.source_start_line,
            source_end_line=candidate.source_end_line,
            role=ObservationRole.CANDIDATE_BARE
        )
        return event_copy

    @staticmethod
    def get_screened_observation(events: List[HubbardPopulationEvent], is_converged: bool = True) -> HubbardPopulationEvent:
        """
        Extracts n(alpha): The population corresponding to the final self-consistent density.
        """
        if not events:
            raise ObservationPolicyError("No events found. Cannot extract screened observation.")
            
        if not is_converged:
            raise ObservationPolicyError("SCREENED observation rejected: SCF did not converge.")
            
        candidate = events[-1]
        
        event_copy = HubbardPopulationEvent(
            occurrence_index=candidate.occurrence_index,
            dftu_population_iteration=candidate.dftu_population_iteration,
            scf_iteration=candidate.scf_iteration,
            context=candidate.context,
            atoms=candidate.atoms,
            source_start_line=candidate.source_start_line,
            source_end_line=candidate.source_end_line,
            role=ObservationRole.CANDIDATE_SCREENED
        )
        return event_copy
