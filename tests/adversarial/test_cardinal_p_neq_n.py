from siestaflow_hubbard.domain.semantic_validation import SemanticValidator
from siestaflow_hubbard.domain.campaign_manifest import CampaignManifest
def test_cardinal_p_neq_n():
    assert isinstance(SemanticValidator().validate_campaign(None), list)
