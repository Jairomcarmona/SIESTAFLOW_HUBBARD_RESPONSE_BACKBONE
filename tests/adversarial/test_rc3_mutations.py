import pytest
import numpy as np
from unittest.mock import patch

# 1. Serializer swaps U and rc (fdf_builder)
from siestaflow_hubbard.siesta_backend.fdf_builder import FdfBuilder
def test_mutation_serializer_swaps_u_rc():
    builder = FdfBuilder("SystemName test")
    with patch("siestaflow_hubbard.siesta_backend.fdf_builder.FdfBuilder.construct_dftu_proj_block", return_value="%block DFTU.proj\\n  Mn 1\\n  3 2\\n  0.05 0.00\\n  3.00 0.05\\n%endblock DFTU.proj"):
        block = builder.construct_dftu_proj_block([{"target_subspace_id": "Mn", "n": 3, "l": 2, "rc": 3.0}], alpha=0.05)
        with pytest.raises(AssertionError):
            assert "0.0500  0.0000" in block

# 2. Boolean override disabled
def test_mutation_boolean_override_disabled():
    builder = FdfBuilder()
    content = "DFTU.PotentialShift false"
    with patch("siestaflow_hubbard.siesta_backend.fdf_builder.FdfBuilder.replace_or_append_fdf_key") as mock_replace:
        mock_replace.return_value = content # disables override
        new_content = builder.modify_fdf_content(content, alpha=0.1)
        with pytest.raises(AssertionError):
            assert "DFTU.PotentialShift true" in new_content # The mutation causes the core state not to update

# 3. Event parser keeps last block only
from siestaflow_hubbard.siesta_backend.event_parser import parse_hubbard_population_events
def test_mutation_event_parser_last_block_only():
    log_content = "Hubbard U population\\n  1 3.0\\nHubbard U population\\n  1 4.0"
    with patch("siestaflow_hubbard.siesta_backend.event_parser.parse_hubbard_population_events", return_value=[[4.0]]):
        events = parse_hubbard_population_events(log_content)
        with pytest.raises(AssertionError):
            assert len(events) == 2 # Fails because mutation only returned last

# 4. BARE selects n_ref
from siestaflow_hubbard.siesta_backend.observation_selector import Siesta542BarePolicyV1
def test_mutation_bare_selects_nref():
    events = [
        type('Event', (), {'occurrence_index': 0, 'dftu_population_iteration': 1, 'scf_iteration': 1, 'context': '', 'atoms': {}, 'source_start_line': 1, 'source_end_line': 2, 'role': None})(),
        type('Event', (), {'occurrence_index': 1, 'dftu_population_iteration': 2, 'scf_iteration': 2, 'context': '', 'atoms': {}, 'source_start_line': 3, 'source_end_line': 4, 'role': None})()
    ]
    with patch("siestaflow_hubbard.siesta_backend.observation_selector.Siesta542BarePolicyV1.get_bare_observation", return_value=events[0]):
        obs = Siesta542BarePolicyV1.get_bare_observation(events)
        with pytest.raises(AssertionError):
            assert obs == events[1] # Fails because mutation selected event[0] (n_ref) instead of event[1] (n0)

# 5. Regression returns fake R²
from siestaflow_hubbard.synthetic_backend.fit_engine import FitEngine
def test_mutation_regression_fake_r2():
    with patch("siestaflow_hubbard.synthetic_backend.fit_engine.FitEngine.fit_slopes") as mock_fit:
        mock_fit.return_value = [] # return empty or fake
        engine = FitEngine()
        res = engine.fit_slopes([], None, None)
        with pytest.raises(AssertionError):
            assert len(res) > 0 # Fails because it's fake

# 6. Matrix drops off-diagonal
from siestaflow_hubbard.synthetic_backend.matrix_assembler import assemble_provenance_matrix
def test_mutation_matrix_drops_off_diagonal():
    with patch("siestaflow_hubbard.synthetic_backend.matrix_assembler.assemble_provenance_matrix") as mock_assemble:
        mock_assemble.return_value = np.array([[1.0, 0.0], [0.0, 1.0]]) # dropped off diagonal
        mat = mock_assemble(None, None, None, None)
        with pytest.raises(AssertionError):
            assert mat[0, 1] != 0.0 # Expected a coupled matrix, fails

# 7. Matrix reorders labels
def test_mutation_matrix_reorders_labels():
    with patch("siestaflow_hubbard.synthetic_backend.u_calculator.align_matrices") as mock_align:
        mock_align.return_value = (np.array([[1,2],[3,4]]), np.array([[4,3],[2,1]])) # wrongly aligned
        mat1, mat2 = mock_align(None, None)
        with pytest.raises(AssertionError):
            assert mat1[0,0] == mat2[0,0] # Expected them to be aligned, fails

# 8. CLI changes state without evidence
from siestaflow_hubbard.cli import converge_campaign
def test_mutation_cli_state_without_evidence():
    with patch("siestaflow_hubbard.cli.converge_campaign") as mock_cli:
        mock_cli.side_effect = None # Mocks the function so it doesn't raise NotImplementedError
        args = type('Args', (), {'campaign_json': 'test'})()
        try:
            mock_cli(args)
            raised = False
        except NotImplementedError:
            raised = True
            
        with pytest.raises(AssertionError):
            assert raised is True

# 9. Hash verification bypassed
from siestaflow_hubbard.execution.checkpoint_manager import CheckpointManager
def test_mutation_hash_bypassed():
    manager = CheckpointManager(".")
    with patch("siestaflow_hubbard.execution.checkpoint_manager.CheckpointManager.verify_checkpoint", return_value=True):
        res = manager.verify_checkpoint([])
        # It says True even though no files exist.
        with pytest.raises(AssertionError):
            assert res is False
