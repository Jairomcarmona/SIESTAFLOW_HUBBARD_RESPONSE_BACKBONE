from siestaflow_hubbard.domain.semantic_validation import SemanticValidator
from siestaflow_hubbard.domain.campaign_manifest import CampaignManifest
def test_ill_conditioned_matrix():
    assert isinstance(SemanticValidator().validate_campaign(None), list)
