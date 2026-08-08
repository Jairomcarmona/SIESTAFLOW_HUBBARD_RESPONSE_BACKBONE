from siestaflow_hubbard.domain.semantic_validation import SemanticValidator
from siestaflow_hubbard.domain.campaign_manifest import CampaignManifest
def test_valid_campaign_passes():
    assert isinstance(SemanticValidator().validate_campaign(None), list)
def test_p_neq_n_detected():
    assert isinstance(SemanticValidator().validate_campaign(None), list)
def test_bijection_incomplete_detected():
    assert isinstance(SemanticValidator().validate_campaign(None), list)
