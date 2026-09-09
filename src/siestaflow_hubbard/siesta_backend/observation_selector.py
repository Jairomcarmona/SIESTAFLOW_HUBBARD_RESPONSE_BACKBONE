from dataclasses import replace
from pathlib import Path
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
            evidence=(
                "CANDIDATE only: matched scf_iteration == 2 under the configured "
                "BARE mode. This does not by itself prove that Hxc was not rebuilt."
            ),
            event=candidate
        )

    @staticmethod
    def get_verified_bare_observation(
        events: List[HubbardPopulationEvent], context: ObservationContext
    ) -> ObservationSelection:
        """Return chi0 evidence only after an explicit SIESTA semantic trace.

        The trace must be tied to the executable/version and show that the
        selected population event is evaluated before Hartree--XC rebuild from
        the perturbed density.  SCF iteration count is deliberately not used
        as a surrogate proof.
        """
        candidate = Siesta542BarePolicyV1.get_bare_observation(events, context)
        if not context.bare_hxc_rebuild_excluded:
            raise ObservationPolicyError(
                "BARE semantics are unverified: a native SIESTA trace excluding "
                "Hxc rebuild before the selected event is required for chi0."
            )
        if not context.bare_semantics_evidence_ref:
            raise ObservationPolicyError(
                "BARE semantics are unverified: missing version-specific evidence reference."
            )
        return ObservationSelection(
            role=ObservationRole.VERIFIED_BARE,
            policy_id=Siesta542BarePolicyV1.POLICY_ID,
            evidence=(
                "VERIFIED_BARE: Hxc rebuild excluded by native SIESTA semantic "
                f"trace {context.bare_semantics_evidence_ref}; {candidate.evidence}"
            ),
            event=candidate.event,
        )

    @staticmethod
    def context_from_verified_bare_sidecar(
        context: ObservationContext,
        *,
        sidecar_path: str | Path,
        executable_path: str | Path,
        reference_dm_path: str | Path,
        output_path: str | Path,
        selected_event_lines: tuple[int, int],
    ) -> ObservationContext:
        """Build a promotable BARE context only after artifact verification.

        This is the required bridge from a version-specific diagnostic trace
        to the selector.  Production orchestration must use this bridge;
        Python data objects alone are not a security boundary against code
        that intentionally fabricates a context.
        """
        from siestaflow_hubbard.siesta_backend.bare_semantics_evidence import (
            verify_bare_semantics_evidence,
        )

        evidence = verify_bare_semantics_evidence(
            sidecar_path,
            siesta_version=context.siesta_version,
            executable_path=executable_path,
            reference_dm_path=reference_dm_path,
            output_path=output_path,
            selected_event_lines=selected_event_lines,
        )
        if context.reference_dm_sha256 is None:
            raise ObservationPolicyError("BARE semantic evidence requires a reference-DM context hash")
        if context.reference_dm_sha256 != hashlib.sha256(Path(reference_dm_path).read_bytes()).hexdigest():
            raise ObservationPolicyError("BARE semantic evidence parent DM differs from the planned context")
        return replace(
            context,
            bare_hxc_rebuild_excluded=True,
            bare_semantics_evidence_ref=evidence.evidence_reference,
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
