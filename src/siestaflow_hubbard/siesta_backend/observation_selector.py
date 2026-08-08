from typing import List, Optional
import hashlib
import json
from siestaflow_hubbard.siesta_backend.parser_models import (
    HubbardPopulationEvent,
    ObservationRole,
    ObservationContext,
    ObservationSelection
)

class ObservationPolicyError(Exception):
    pass

class Siesta542BarePolicyV1:
    """
    Implements the 'siesta-5.4.2-lr-bare-v1' policy.
    Maps raw Hubbard population events to their scientific roles in a Linear Response calculation.
    """
    POLICY_ID = "siesta-5.4.2-lr-bare-v1"
    
    @staticmethod
    def _generate_run_context_id(context: ObservationContext) -> str:
        payload = {
            "siesta_version": context.siesta_version,
            "calculation_mode": context.calculation_mode,
            "reference_dm_sha256": context.reference_dm_sha256,
            "projector_fingerprint": context.projector_fingerprint,
            "scf_mix_target": context.scf_mix_target,
            "scf_mixer_method": context.scf_mixer_method,
            "scf_mixer_weight": context.scf_mixer_weight,
            "max_scf_iterations": context.max_scf_iterations,
        }
        json_str = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(json_str.encode("utf-8")).hexdigest()

    @staticmethod
    def _generate_event_id(event: HubbardPopulationEvent) -> str:
        payload = {
            "occurrence_index": event.occurrence_index,
            "scf_iteration": event.scf_iteration,
            "context": event.context
        }
        json_str = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(json_str.encode("utf-8")).hexdigest()

    @staticmethod
    def get_reference_observation(events: List[HubbardPopulationEvent], context: ObservationContext) -> ObservationSelection:
        if not events:
            raise ObservationPolicyError("No events found. Cannot extract reference observation.")
            
        candidates = [e for e in events if e.scf_iteration == 1]
        if not candidates:
            raise ObservationPolicyError("No reference observation found (requires scf_iteration == 1).")
        if len(candidates) > 1:
            raise ObservationPolicyError("AMBIGUOUS: Multiple events found for scf_iteration == 1.")
            
        candidate = candidates[0]
        
        # Validation
        if not context.reference_dm_sha256:
            raise ObservationPolicyError("REFERENCE extraction requires validated reference-DM context.")
            
        return ObservationSelection(
            role=ObservationRole.REFERENCE,
            policy_id=Siesta542BarePolicyV1.POLICY_ID,
            evidence="Matched scf_iteration == 1 with validated reference-DM context",
            event=candidate
        )

    @staticmethod
    def get_bare_observation(events: List[HubbardPopulationEvent], context: ObservationContext) -> ObservationSelection:
        if len(events) < 2:
            raise ObservationPolicyError("Insufficient events to extract BARE observation. Need at least 2.")
            
        candidates = [e for e in events if e.scf_iteration == 2]
        if not candidates:
            raise ObservationPolicyError("No BARE observation found (requires scf_iteration == 2).")
        if len(candidates) > 1:
            raise ObservationPolicyError("AMBIGUOUS: Multiple events found for scf_iteration == 2.")
            
        candidate = candidates[0]
        
        # Validation
        if context.calculation_mode != "BARE":
            raise ObservationPolicyError("BARE extraction requires calculation_mode == BARE.")
        if context.scf_mix_target != "density":
            raise ObservationPolicyError("BARE extraction requires SCF.Mix == density.")
        if context.scf_mixer_method != "Linear":
            raise ObservationPolicyError("BARE extraction requires SCF.Mixer.Method == Linear.")
        if context.scf_mixer_weight != 1.0:
            raise ObservationPolicyError("BARE extraction requires SCF.Mixer.Weight == 1.0.")
        if not context.reference_dm_sha256:
            raise ObservationPolicyError("BARE extraction requires same reference DM context.")
            
        return ObservationSelection(
            role=ObservationRole.CANDIDATE_BARE,
            policy_id=Siesta542BarePolicyV1.POLICY_ID,
            evidence="Matched scf_iteration == 2 under strictly validated BARE calculation mode",
            event=candidate
        )

    @staticmethod
    def get_screened_observation(events: List[HubbardPopulationEvent], context: ObservationContext) -> ObservationSelection:
        if not events:
            raise ObservationPolicyError("No events found. Cannot extract screened observation.")
            
        if not context.convergence_confirmed:
            raise ObservationPolicyError("SCREENED observation rejected: run-level convergence_confirmed == False.")
        if not context.final_scf_iteration:
            raise ObservationPolicyError("SCREENED observation rejected: final_scf_iteration not established.")
            
        candidates = [e for e in events if e.scf_iteration == context.final_scf_iteration]
        if not candidates:
            raise ObservationPolicyError("No SCREENED observation found matching final_scf_iteration.")
        if len(candidates) > 1:
            # Pick the final post-SCF event
            if context.post_scf_population_occurrence:
                c_matches = [e for e in candidates if e.occurrence_index == context.post_scf_population_occurrence]
                if len(c_matches) == 1:
                    candidates = c_matches
                else:
                    raise ObservationPolicyError("AMBIGUOUS: Multiple post-SCF events match final scf_iteration.")
            else:
                 raise ObservationPolicyError("AMBIGUOUS: Multiple events found for final scf_iteration.")
                 
        candidate = candidates[0]
        
        return ObservationSelection(
            role=ObservationRole.CANDIDATE_SCREENED,
            policy_id=Siesta542BarePolicyV1.POLICY_ID,
            evidence="Matched final_scf_iteration with convergence_confirmed == True",
            event=candidate
        )
