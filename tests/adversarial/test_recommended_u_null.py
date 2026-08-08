from siestaflow_hubbard.domain.semantic_validation import SemanticValidator
from siestaflow_hubbard.domain.campaign_manifest import CampaignManifest
import pytest

def test_candidate_evaluation_recommended_null():
    assert isinstance(SemanticValidator().validate_campaign(None), list)
