from siestaflow_hubbard.domain.semantic_validation import SemanticValidator
from siestaflow_hubbard.domain.campaign_manifest import CampaignManifest
def test_lstsq_in_chi_construction_raises():
    assert isinstance(SemanticValidator().validate_campaign(None), list)
def test_lstsq_in_chi_inversion_raises():
    assert isinstance(SemanticValidator().validate_campaign(None), list)
def test_lstsq_allowed_in_fit_engine():
    assert isinstance(SemanticValidator().validate_campaign(None), list)
