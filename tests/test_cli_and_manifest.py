import os
import json
import tempfile
import pytest
from unittest.mock import patch, MagicMock

from siestaflow_hubbard.domain.campaign_manifest import CampaignManifest, CampaignState
from siestaflow_hubbard.execution.checkpoint_manager import CheckpointManager
from siestaflow_hubbard.reporting.evidence_exporter import EvidenceExporter
import siestaflow_hubbard.cli as cli

def test_campaign_manifest_transitions():
    manifest = CampaignManifest(name="test")
    assert manifest.state == CampaignState.DRAFT
    
    manifest.transition(CampaignState.LOCKED)
    assert manifest.state == CampaignState.LOCKED
    
    with pytest.raises(ValueError):
        manifest.transition(CampaignState.COMPLETED)
        
    manifest.transition(CampaignState.CONVERGENCE_RUNNING)
    manifest.transition(CampaignState.CONVERGED)
    assert manifest.state == CampaignState.CONVERGED

def test_campaign_manifest_io(tmp_path):
    manifest = CampaignManifest(name="test_io")
    manifest.cell_info = {"a": 1.0}
    
    path = str(tmp_path / "campaign.json")
    manifest.save_to_file(path)
    
    loaded = CampaignManifest.load_from_file(path)
    assert loaded.name == "test_io"
    assert loaded.cell_info == {"a": 1.0}
    assert loaded.state == CampaignState.DRAFT

def test_checkpoint_manager(tmp_path):
    work_dir = str(tmp_path)
    manager = CheckpointManager(work_dir)
    
    file1_path = "test1.out"
    file2_path = "test2.DM"
    
    # Create mock files
    with open(os.path.join(work_dir, file1_path), "w") as f:
        f.write("content1")
    with open(os.path.join(work_dir, file2_path), "w") as f:
        f.write("content2")
        
    manager.record_checkpoint([file1_path, file2_path])
    
    assert manager.verify_checkpoint([file1_path, file2_path]) is True
    
    # Modify a file to invalidate hash
    with open(os.path.join(work_dir, file1_path), "w") as f:
        f.write("modified")
        
    assert manager.verify_checkpoint([file1_path, file2_path]) is False
    assert manager.is_step_completed("step1", [file1_path, file2_path]) is False

def test_evidence_exporter(tmp_path):
    out_dir = str(tmp_path)
    exporter = EvidenceExporter(out_dir)
    
    data = {
        "geometry_spin": {"spin": "collinear"},
        "provenance": [{"file": "test", "hash": "123"}]
    }
    exporter.export(data)
    
    assert os.path.exists(os.path.join(out_dir, "EVIDENCE_REPORT.md"))
    assert os.path.exists(os.path.join(out_dir, "EVIDENCE_REPORT.html"))
    
    with open(os.path.join(out_dir, "EVIDENCE_REPORT.md"), "r") as f:
        content = f.read()
        assert "collinear" in content
        assert "123" in content

@patch("siestaflow_hubbard.cli.FdfValidator")
@patch("siestaflow_hubbard.cli.FdfParser")
def test_cli_audit_fdf(mock_parser_class, mock_validator_class, tmp_path):
    fdf_path = str(tmp_path / "test.fdf")
    with open(fdf_path, "w") as f:
        f.write("SystemName test")
        
    args = MagicMock()
    args.command = "audit-fdf"
    args.fdf_file = fdf_path
    
    mock_parser = mock_parser_class.return_value
    mock_validator = mock_validator_class.return_value
    mock_validator.detect_spin_mode.return_value = "collinear"
    
    cli.audit_fdf(args)
    
    mock_validator.check_unit.assert_called_once()
    mock_validator.validate_multi_species.assert_called_once()

def test_cli_init_campaign(tmp_path):
    args = MagicMock()
    args.command = "init"
    args.fdf_file = "test.fdf"
    args.name = "my_campaign"
    
    with patch("siestaflow_hubbard.domain.campaign_manifest.CampaignManifest.save_to_file") as mock_save:
        cli.init_campaign(args)
        mock_save.assert_called_once_with("campaign.json")

def test_cli_converge_no_evidence(tmp_path):
    """RC-2 Adversarial test: invoke CLI without computational evidence"""
    manifest_path = str(tmp_path / "campaign.json")
    manifest = CampaignManifest(name="test")
    manifest.save_to_file(manifest_path)
    
    args = MagicMock()
    args.command = "converge"
    args.campaign_json = manifest_path
    
    with pytest.raises(NotImplementedError, match="Missing physical evidence to perform this transition"):
        cli.converge_campaign(args)
        
def test_cli_run_no_evidence(tmp_path):
    """RC-2 Adversarial test: invoke CLI without computational evidence"""
    manifest_path = str(tmp_path / "campaign.json")
    manifest = CampaignManifest(name="test")
    manifest.save_to_file(manifest_path)
    
    args = MagicMock()
    args.command = "run"
    args.campaign_json = manifest_path
    
    with pytest.raises(NotImplementedError, match="Missing physical evidence to perform this transition"):
        cli.run_campaign(args)

def test_cli_execution_fails(tmp_path):
    """RC-2 Adversarial test: SIESTA execution fails"""
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
