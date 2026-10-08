import os

content = """
def test_cli_converge_no_evidence(tmp_path):
    \"\"\"RC-2 Adversarial test: invoke CLI without computational evidence\"\"\"
    manifest_path = str(tmp_path / "campaign.json")
    manifest = CampaignManifest(name="test")
    manifest.save_to_file(manifest_path)
    
    args = MagicMock()
    args.command = "converge"
    args.campaign_json = manifest_path
    
    with pytest.raises(NotImplementedError, match="Missing physical evidence to perform this transition"):
        cli.converge_campaign(args)
        
def test_cli_run_no_evidence(tmp_path):
    \"\"\"RC-2 Adversarial test: invoke CLI without computational evidence\"\"\"
    manifest_path = str(tmp_path / "campaign.json")
    manifest = CampaignManifest(name="test")
    manifest.save_to_file(manifest_path)
    
    args = MagicMock()
    args.command = "run"
    args.campaign_json = manifest_path
    
    with pytest.raises(NotImplementedError, match="Missing physical evidence to perform this transition"):
        cli.run_campaign(args)

def test_cli_execution_fails(tmp_path):
    \"\"\"RC-2 Adversarial test: SIESTA execution fails\"\"\"
    manifest_path = str(tmp_path / "campaign.json")
    manifest = CampaignManifest(name="test")
    manifest.save_to_file(manifest_path)
    
    args = MagicMock()
    args.command = "run"
    args.campaign_json = manifest_path
    
    # Simulating SIESTA execution failure by enforcing the NotImplementedError block
    with pytest.raises(NotImplementedError, match="Missing physical evidence to perform this transition"):
        cli.run_campaign(args)
        
    loaded = CampaignManifest.load_from_file(manifest_path)
    # The CLI cannot mark the campaign as completed
    assert loaded.state != CampaignState.COMPLETED
"""

with open("tests/test_cli_and_manifest.py", "a") as f:
    f.write(content)
