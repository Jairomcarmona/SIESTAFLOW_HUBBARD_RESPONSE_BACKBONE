import pytest
from siestaflow_hubbard.siesta_backend.parser_models import HubbardPopulationEvent, ObservationRole, ObservationContext, ObservationSelection
from siestaflow_hubbard.siesta_backend.observation_selector import (
    Siesta542BarePolicyV1,
    ObservationPolicyError
)

def create_mock_event(occurrence, scf, context=""):
    return HubbardPopulationEvent(
        occurrence_index=occurrence,
        dftu_population_iteration=occurrence,
        scf_iteration=scf,
        context=context,
        atoms=[],
        source_start_line=1,
        source_end_line=2
    )

@pytest.fixture
def base_context():
    return ObservationContext(
        siesta_version="5.4.2",
        calculation_mode="BARE",
        reference_dm_sha256="mock_sha256",
        projector_fingerprint="mock_proj",
        scf_mix_target="density",
        scf_mixer_method="Linear",
        scf_mixer_weight=1.0,
        max_scf_iterations=2,
        convergence_confirmed=True,
        final_scf_iteration=10,
        post_scf_population_occurrence=3
    )

def test_OBS_A_fake_event_before_bare(base_context):
    events = [
        create_mock_event(0, 1),
        create_mock_event(1, 99, "fake event"),
        create_mock_event(2, 2)
    ]
    bare = Siesta542BarePolicyV1.get_bare_observation(events, base_context)
    assert bare.event.scf_iteration == 2
    assert bare.event.occurrence_index == 2
    assert bare.role == ObservationRole.CANDIDATE_BARE

def test_OBS_B_extra_event_after_screened(base_context):
    events = [
        create_mock_event(0, 1),
        create_mock_event(1, 2),
        create_mock_event(2, 10),
        create_mock_event(3, 10), # the post_scf match according to context
        create_mock_event(4, 3, "unrelated appended event")
    ]
    
    screened = Siesta542BarePolicyV1.get_screened_observation(events, base_context)
    assert screened.event.scf_iteration == 10
    assert screened.event.occurrence_index == 3 

def test_OBS_C_wrong_scf_iteration_for_bare(base_context):
    events = [
        create_mock_event(0, 1),
        create_mock_event(1, 3)
    ]
    with pytest.raises(ObservationPolicyError, match="No BARE observation found"):
        Siesta542BarePolicyV1.get_bare_observation(events, base_context)

def test_OBS_D_unconverged_screened(base_context):
    events = [
        create_mock_event(0, 1),
        create_mock_event(1, 15)
    ]
    import copy
    unconverged_context = copy.copy(base_context)
    # Using python dataclasses, they are frozen. we must use replace
    from dataclasses import replace
    unconverged_context = replace(base_context, convergence_confirmed=False)

    with pytest.raises(ObservationPolicyError, match="SCREENED observation rejected"):
        Siesta542BarePolicyV1.get_screened_observation(events, unconverged_context)

def test_OBS_E_shuffle_event_list(base_context):
    events = [
        create_mock_event(3, 10),
        create_mock_event(0, 1),
        create_mock_event(1, 2)
    ]
    
    ref = Siesta542BarePolicyV1.get_reference_observation(events, base_context)
    assert ref.event.scf_iteration == 1
    
    bare = Siesta542BarePolicyV1.get_bare_observation(events, base_context)
    assert bare.event.scf_iteration == 2
    
    screened = Siesta542BarePolicyV1.get_screened_observation(events, base_context)
    assert screened.event.scf_iteration == 10

def test_reject_ambiguous_bare(base_context):
    events = [
        create_mock_event(1, 2),
        create_mock_event(2, 2)
    ]
    with pytest.raises(ObservationPolicyError, match="AMBIGUOUS"):
        Siesta542BarePolicyV1.get_bare_observation(events, base_context)

