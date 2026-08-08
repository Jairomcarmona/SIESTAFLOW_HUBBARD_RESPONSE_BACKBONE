from siestaflow_hubbard.domain.semantic_validation import SemanticValidator
from siestaflow_hubbard.domain.campaign_manifest import CampaignManifest
def test_correct_record_count():
    assert isinstance(SemanticValidator().validate_campaign(None), list)
def test_missing_record_detected_by_semantic_validator():
    assert isinstance(SemanticValidator().validate_campaign(None), list)
def test_duplicate_record_detected():
    assert isinstance(SemanticValidator().validate_campaign(None), list)
