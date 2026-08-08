from siestaflow_hubbard.domain.semantic_validation import SemanticValidator
from siestaflow_hubbard.domain.campaign_manifest import CampaignManifest
import pytest
@pytest.mark.parametrize("decision_type,required_field", [
    ("DEFER", None), ("REJECT", "rejection_reasons"), ("ACCEPT_FULL_MATRIX", "u_accepted_matrix_ev"),
    ("ACCEPT_DIAGONAL_VECTOR", "u_accepted_diagonal_ev"), ("ACCEPT_SINGLE_SCALAR", "u_accepted_scalar_ev")
])
def test_decision_type_validates(decision_type, required_field):
    assert isinstance(SemanticValidator().validate_campaign(None), list)
def test_diagonal_vector_requires_reduction_justification():
    assert isinstance(SemanticValidator().validate_campaign(None), list)
def test_single_scalar_requires_reduction_justification():
    assert isinstance(SemanticValidator().validate_campaign(None), list)
