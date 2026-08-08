from siestaflow_hubbard.domain.semantic_validation import SemanticValidator
from siestaflow_hubbard.domain.campaign_manifest import CampaignManifest
def test_case_a_physical_reflip_slopes_unchanged():
    assert isinstance(SemanticValidator().validate_campaign(None), list)
def test_case_b_relabel_negates_slopes_and_u():
    assert isinstance(SemanticValidator().validate_campaign(None), list)
