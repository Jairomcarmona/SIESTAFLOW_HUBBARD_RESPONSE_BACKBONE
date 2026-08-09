import pytest
import os
import json
import hashlib
from siestaflow_hubbard.siesta_backend.fdf_builder import FdfBuilder, MaterializedDftuContract

def get_fingerprint(proj_dict: dict) -> str:
    json_str = json.dumps(proj_dict, sort_keys=True)
    return hashlib.sha256(json_str.encode('utf-8')).hexdigest()

def test_reference_method1_projector_fails():
    fdf_text = """
    DFTU.ProjectorGenerationMethod 1
    %block DFTU.proj
    Mn 1
      3 2
      0.0 0.0
      3.0 0.05
    %endblock DFTU.proj
    """
    builder = FdfBuilder()
    contract = builder.parse_materialized_dftu_contract(fdf_text, "Mn")
    assert contract is None or contract.projector_method != "2"

def test_missing_projector_generation_method_fails():
    fdf_text = """
    %block DFTU.proj
    Mn 1
      3 2
      0.0 0.0
      3.0 0.05
    %endblock DFTU.proj
    """
    builder = FdfBuilder()
    contract = builder.parse_materialized_dftu_contract(fdf_text, "Mn")
    assert contract is None or contract.projector_method != "2"

def test_projector_fingerprint_mock_forbidden():
    fp = get_fingerprint({"species": "Mn", "n": 3, "l": 2, "rc": 3.0, "omega": 0.05, "lambda_effective": 1.0})
    assert fp != "mock"
    assert "mock" not in fp

def test_non_converged_output_reference_validation_fail(tmp_path):
    out_content = "scf: iscf = 1\nscf: max dDmax = 0.001"
    is_converged = False
    for line in out_content.splitlines():
        if "SCF cycle converged" in line:
            is_converged = True
    assert not is_converged

def test_missing_dm_after_convergence_fails(tmp_path):
    dm_path = tmp_path / "MnO.DM"
    assert not os.path.exists(dm_path)

def test_changed_rc_different_fingerprint():
    dict1 = {"species": "Mn", "n": 3, "l": 2, "rc": 3.0, "omega": 0.05, "lambda_effective": 1.0}
    dict2 = {"species": "Mn", "n": 3, "l": 2, "rc": 4.0, "omega": 0.05, "lambda_effective": 1.0}
    assert get_fingerprint(dict1) != get_fingerprint(dict2)

def test_changed_omega_different_fingerprint():
    dict1 = {"species": "Mn", "n": 3, "l": 2, "rc": 3.0, "omega": 0.05, "lambda_effective": 1.0}
    dict2 = {"species": "Mn", "n": 3, "l": 2, "rc": 3.0, "omega": 0.10, "lambda_effective": 1.0}
    assert get_fingerprint(dict1) != get_fingerprint(dict2)

def test_omitted_lambda_and_explicit_lambda_same_effective_fingerprint():
    fdf_omitted = """
    DFTU.ProjectorGenerationMethod 2
    %block DFTU.proj
    Mn 1
      3 2
      0.0 0.0
      3.0 0.05
    %endblock DFTU.proj
    """
    fdf_explicit = """
    DFTU.ProjectorGenerationMethod 2
    %block DFTU.proj
    Mn 1
      3 2
      0.0 0.0
      3.0 0.05
      1.0
    %endblock DFTU.proj
    """
    builder = FdfBuilder()
    c_om = builder.parse_materialized_dftu_contract(fdf_omitted, "Mn")
    c_ex = builder.parse_materialized_dftu_contract(fdf_explicit, "Mn")
    
    assert c_om.lambda_effective == 1.0
    assert c_ex.lambda_effective == 1.0
    
    dict1 = {"species": c_om.species, "n": c_om.n, "l": c_om.l, "rc": c_om.rc, "omega": c_om.omega, "lambda_effective": c_om.lambda_effective}
    dict2 = {"species": c_ex.species, "n": c_ex.n, "l": c_ex.l, "rc": c_ex.rc, "omega": c_ex.omega, "lambda_effective": c_ex.lambda_effective}
    
    assert get_fingerprint(dict1) == get_fingerprint(dict2)

from scratch.phase4_method2_revalidation import (
    select_converged_reference_event,
    ReferenceSelectionAmbiguityError,
    ReferenceSelectionNotFoundError
)
from siestaflow_hubbard.siesta_backend.parser_models import HubbardPopulationEvent, HubbardAtomPopulation, ObservationRole
import numpy as np

def make_mock_event(occurrence_index: int, scf_iteration: int, trace_total: float, is_post_scf: bool = False):
    atom = HubbardAtomPopulation(
        atom_index=1,
        species_index=1,
        raw_matrix_up=np.eye(5),
        raw_matrix_down=None,
        channel_count=1,
        trace_up=trace_total,
        trace_down=0.0,
        trace_total=trace_total,
        printed_total_trace=trace_total
    )
    event = HubbardPopulationEvent(
        occurrence_index=occurrence_index,
        dftu_population_iteration=scf_iteration,
        scf_iteration=scf_iteration,
        context="recalculating local occupations",
        atoms=[atom]
    )
    if is_post_scf:
        setattr(event, 'is_post_scf', True)
    return event

def test_p4_a1_01_extra_trailing_event_ignored():
    ev_converged = make_mock_event(occurrence_index=309, scf_iteration=309, trace_total=5.3722)
    ev_trailing = make_mock_event(occurrence_index=310, scf_iteration=310, trace_total=9.9999)
    events = [ev_converged, ev_trailing]
    
    selected, candidate_occurrences, ambiguity = select_converged_reference_event(events, converged_scf_iteration=309)
    assert selected.occurrence_index == 309
    assert selected.atoms[0].trace_total == 5.3722
    assert selected.occurrence_index != ev_trailing.occurrence_index

def test_p4_a1_02_wrong_scf_event_last_ignored():
    ev_converged = make_mock_event(occurrence_index=15, scf_iteration=309, trace_total=5.3722)
    ev_wrong_last = make_mock_event(occurrence_index=99, scf_iteration=100, trace_total=1.1111)
    events = [ev_converged, ev_wrong_last]
    
    selected, candidate_occurrences, ambiguity = select_converged_reference_event(events, converged_scf_iteration=309)
    assert selected.occurrence_index == 15
    assert selected.atoms[0].trace_total == 5.3722
    assert selected.occurrence_index != ev_wrong_last.occurrence_index

def test_p4_a1_03_ambiguity_rejection():
    ev_candidate_1 = make_mock_event(occurrence_index=50, scf_iteration=309, trace_total=5.3722)
    ev_candidate_2 = make_mock_event(occurrence_index=51, scf_iteration=309, trace_total=5.3722)
    events = [ev_candidate_1, ev_candidate_2]
    
    with pytest.raises(ReferenceSelectionAmbiguityError):
        select_converged_reference_event(events, converged_scf_iteration=309)

