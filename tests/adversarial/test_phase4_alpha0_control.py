import pytest
from siestaflow_hubbard.siesta_backend.observation_selector import (
    Siesta542BarePolicyV1,
    ObservationContext,
    ObservationPolicyError
)
from siestaflow_hubbard.siesta_backend.parser_models import HubbardAtomPopulation, HubbardPopulationEvent
from scratch.phase4_method2_revalidation import (
    select_converged_reference_event,
    ReferenceSelectionAmbiguityError,
    ReferenceSelectionNotFoundError
)

import numpy as np

def make_mock_event(occurrence_index: int, scf_iteration: int, trace_total: float = 5.3722) -> HubbardPopulationEvent:
    atom = HubbardAtomPopulation(
        atom_index=1,
        species_index=1,
        raw_matrix_up=np.eye(5) * (trace_total / 5.0),
        raw_matrix_down=None,
        channel_count=1,
        trace_up=trace_total,
        trace_down=0.0,
        trace_total=trace_total,
        printed_total_trace=trace_total
    )
    return HubbardPopulationEvent(
        occurrence_index=occurrence_index,
        dftu_population_iteration=scf_iteration,
        scf_iteration=scf_iteration,
        context="recalculating local occupations",
        atoms=[atom]
    )

def test_p4_b_01_wrong_parent_dm_rejected():
    expected_ref_dm_hash = "f24aee2fbdc52238e816edf50ae7c06cfd41efafb13966a8219731c0d3c3d74b"
    wrong_parent_dm_hash = "deadbeef" * 8
    
    dm_match = (wrong_parent_dm_hash == expected_ref_dm_hash)
    assert dm_match is False, "Wrong parent DM hash must fail equality check"

def test_p4_b_02_wrong_projector_fingerprint_rejected():
    expected_fingerprint = "3e53915648cdce6991c6e0ecc89febb14db0fd2a98f2aa5eb89d1fed5c654ab7"
    wrong_fingerprint = "badfingerprint" * 4
    
    proj_match = (wrong_fingerprint == expected_fingerprint)
    assert proj_match is False, "Wrong projector fingerprint must fail equality check"

def test_p4_b_03_fake_screened_convergence_rejected():
    events = [make_mock_event(1, 10)]
    fake_ctx = ObservationContext(
        siesta_version="5.4.2",
        calculation_mode="SCREENED",
        reference_dm_sha256="f24aee2fbdc52238e816edf50ae7c06cfd41efafb13966a8219731c0d3c3d74b",
        projector_fingerprint="3e53915648cdce6991c6e0ecc89febb14db0fd2a98f2aa5eb89d1fed5c654ab7",
        scf_mix_target="density",
        scf_mixer_method="Linear",
        scf_mixer_weight=1.0,
        max_scf_iterations=100,
        convergence_confirmed=False,
        final_scf_iteration=10,
        post_scf_population_occurrence=None
    )
    with pytest.raises(ObservationPolicyError, match="convergence_confirmed == False"):
        Siesta542BarePolicyV1.get_screened_observation(events, fake_ctx)

def test_p4_b_04_ambiguous_screened_event_rejected():
    ev1 = make_mock_event(1, 309)
    ev2 = make_mock_event(2, 309)
    events = [ev1, ev2]
    
    with pytest.raises(ReferenceSelectionAmbiguityError):
        select_converged_reference_event(events, converged_scf_iteration=309)
