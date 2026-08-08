import os

code = """
def test_cli_converge_campaign(tmp_path):
    args = MagicMock()
    args.command = "converge"
    args.campaign_json = str(tmp_path / "campaign.json")
    
    manifest = CampaignManifest(name="test")
    manifest.save_to_file(args.campaign_json)
    
    cli.converge_campaign(args)
    
    loaded = CampaignManifest.load_from_file(args.campaign_json)
    assert loaded.state == CampaignState.CONVERGED

def test_cli_run_campaign(tmp_path):
    args = MagicMock()
    args.command = "run"
    args.campaign_json = str(tmp_path / "campaign.json")
    
    manifest = CampaignManifest(name="test", state=CampaignState.CONVERGED)
    manifest.save_to_file(args.campaign_json)
    
    cli.run_campaign(args)
    
    loaded = CampaignManifest.load_from_file(args.campaign_json)
    assert loaded.state == CampaignState.COMPLETED

def test_cli_resume_campaign(tmp_path):
    args = MagicMock()
    args.command = "resume"
    args.campaign_json = str(tmp_path / "campaign.json")
    
    manifest = CampaignManifest(name="test", state=CampaignState.SUSPENDED)
    manifest.save_to_file(args.campaign_json)
    
    cli.resume_campaign(args)
    
    loaded = CampaignManifest.load_from_file(args.campaign_json)
    assert loaded.state == CampaignState.SUSPENDED

@patch("siestaflow_hubbard.cli.EvidenceExporter")
def test_cli_report_campaign(mock_exporter_class, tmp_path):
    args = MagicMock()
    args.command = "report"
    args.campaign_json = str(tmp_path / "campaign.json")
    
    manifest = CampaignManifest(name="test", state=CampaignState.COMPLETED)
    manifest.save_to_file(args.campaign_json)
    
    mock_exporter = mock_exporter_class.return_value
    
    cli.report_campaign(args)
    
    mock_exporter.export.assert_called_once()
"""
with open("tests/test_cli_and_manifest.py", "a") as f:
    f.write(code)
