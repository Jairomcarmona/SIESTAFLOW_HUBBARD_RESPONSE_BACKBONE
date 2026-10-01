from hubbardflow.domain.semantic_validation import SemanticValidator
from hubbardflow.domain.campaign_manifest import CampaignManifest
def test_bare_unresolved():
    assert isinstance(SemanticValidator().validate_campaign(None), list)
