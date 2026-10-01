import os
import json
import hashlib
import io
import sys
from pathlib import Path
import pytest
from unittest.mock import patch
from subprocess import CompletedProcess

from hubbardflow.domain.campaign_manifest import CampaignManifest, CampaignState
from hubbardflow.execution.checkpoint_manager import CheckpointManager, CheckpointScientificAcceptanceDisabledError
from hubbardflow.reporting.evidence_exporter import EvidenceExporter
import hubbardflow.cli as cli
from hubbardflow.execution import wsl_supervisor


def test_wsl_command_decodes_utf8_report_output(monkeypatch):
    calls = []

    def fake_run(*args, **kwargs):
        calls.append(kwargs)
        return CompletedProcess(args[0], 0, stdout="U de carga — revisión α", stderr="")

    monkeypatch.setattr(wsl_supervisor.subprocess, "run", fake_run)

    assert wsl_supervisor.wsl_command("Ubuntu", ["python", "-m", "report"]) == "U de carga — revisión α"
    assert calls[0]["encoding"] == "utf-8"
    assert calls[0]["errors"] == "replace"


def test_cli_report_text_is_safe_for_legacy_windows_console(monkeypatch):
    class Cp1252Console(io.StringIO):
        encoding = "cp1252"

        def write(self, text):
            text.encode(self.encoding)
            return super().write(text)

    console = Cp1252Console()
    monkeypatch.setattr(sys, "stdout", console)

    cli._write_console_text("U de carga — respuesta α")

    assert "U de carga — respuesta \\u03b1" in console.getvalue()

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
    with pytest.raises(CheckpointScientificAcceptanceDisabledError):
        manager.is_step_completed("step1", [file1_path, file2_path])

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

def test_cli_audit_fdf_reports_repository_nio_pbe_spin_and_dftu(capsys):
    repo_root = Path(__file__).resolve().parents[1]
    fdf_path = repo_root / "campaigns/nio_afmii_pbe_restart_v3_20260927/inputs/reference_pbe.fdf"
    original_hash = hashlib.sha256(fdf_path.read_bytes()).hexdigest()

    assert cli.main(["audit-fdf", str(fdf_path)]) == 0

    report = json.loads(capsys.readouterr().out)
    assert report["validation"] == "passed"
    assert report["xc_functional"] == "GGA"
    assert report["xc_authors"] == "PBE"
    assert report["spin_mode"] == "spin-polarized"
    assert report["lattice_constant"] == pytest.approx(4.17)
    assert report["lattice_constant_units"] == "Ang"
    assert report["dftu_projector_block"] is True
    assert report["dftu_projector_l_values"] == [2]
    assert report["orbital_dimension"] == 25
    assert report["orbital_dimension_status"] == "inferred"
    assert hashlib.sha256(fdf_path.read_bytes()).hexdigest() == original_hash


def test_cli_audit_fdf_does_not_pass_an_unreadable_dftu_projector(monkeypatch, capsys):
    invalid_fdf = """SystemLabel test
Spin polarized
%block ChemicalSpeciesLabel
1 28 Ni
%endblock ChemicalSpeciesLabel
%block DFTU.Proj
NiLR0 one
%endblock DFTU.Proj
"""

    class SyntheticPath:
        def __init__(self, value):
            self.value = str(value)

        def read_text(self, encoding="utf-8"):
            return invalid_fdf

        def resolve(self):
            return self

        def __str__(self):
            return self.value

    monkeypatch.setattr(cli, "Path", SyntheticPath)

    assert cli.main(["audit-fdf", "invalid-projector.fdf"]) == 2
    assert capsys.readouterr().out == ""

def test_cli_init_dispatches_to_wsl_without_running_scientific_work(monkeypatch, capsys):
    profile = {
        "target": "local_wsl", "evidence": "VALIDATED_RUNTIME",
        "wsl": {"distribution": "Ubuntu", "python_executable": "/usr/bin/python3", "workspace_root": "/home/test/campaigns"},
        "allocation": {"nodes": 1, "total_cpus": 4, "memory": "8G", "walltime": "01:00:00", "max_parallel_steps": 1, "shutdown_margin_seconds": 60, "termination_grace_seconds": 30},
        "runtime": {"module_commands": [], "siesta_executable": "/opt/siesta", "exclusive": True, "environment": {}, "launcher": {"kind": "openmpi", "command": ["/usr/bin/mpiexec.openmpi"], "bootstrap": "local", "processes_per_node": 4}},
        "task_policy": {"max_attempts": 1, "require_scf_converged": True},
    }
    profile_path = "/inputs/profile.json"
    dispatched = {}

    class SyntheticPath:
        def __init__(self, value):
            self.value = str(value)
            self.name = self.value.rsplit("/", 1)[-1]
        def read_text(self, encoding="utf-8"):
            return json.dumps(profile)
        def resolve(self):
            return self
        def __str__(self):
            return self.value
    monkeypatch.setattr(cli, "Path", SyntheticPath)

    def fake_wsl_command(distribution, argv):
        dispatched["distribution"] = distribution
        dispatched["argv"] = argv
        return '{"campaign_id":"synthetic"}'

    with patch("hubbardflow.cli.windows_to_wsl_path", side_effect=lambda _d, p: f"/mnt/c/{cli.Path(p).name}"), \
         patch("hubbardflow.cli.wsl_command", side_effect=fake_wsl_command):
        assert cli.main([
            "init", "/inputs/input.fdf", "--lr-config", "/inputs/lr.json",
            "--profile", profile_path, "--name", "my_campaign", "--pointer", "/win/my_campaign.json",
        ]) == 0
    assert dispatched["distribution"] == "Ubuntu"
    assert dispatched["argv"][1:3] == ["-m", "hubbardflow.cli"]
    assert '"campaign_id":"synthetic"' in capsys.readouterr().out


def test_cli_init_help_documents_adaptive_policy_without_running_work(capsys):
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["--help"])
    assert exit_info.value.code == 0
    help_text = capsys.readouterr().out
    assert "fixed-grid or policy-driven adaptive v2" in help_text


def test_cli_rejects_legacy_campaign_without_v2_evidence(tmp_path, capsys):
    """Legacy metadata cannot be mistaken for a v2 WSL campaign pointer."""
    manifest_path = str(tmp_path / "campaign.json")
    manifest = CampaignManifest(name="test")
    manifest.save_to_file(manifest_path)
    assert cli.main(["run", manifest_path]) == 2
    assert "campaign pointer must use schema" in capsys.readouterr().err
    loaded = CampaignManifest.load_from_file(manifest_path)
    assert loaded.state != CampaignState.COMPLETED


def test_public_direct_manifest_commands_route_to_shared_runner_and_report_is_non_executing(monkeypatch, capsys):
    from hubbardflow.execution import campaign_runner

    manifest = "campaign.v2.json"
    class SyntheticPath:
        def __init__(self, value):
            self.value = value
        def read_text(self, encoding="utf-8"):
            return json.dumps({"schema": "siestaflow.campaign.v2"})
    monkeypatch.setattr(cli, "Path", SyntheticPath)
    calls = []
    monkeypatch.setattr(campaign_runner, "render_campaign_report", lambda path: calls.append(("report", path)) or "saved report")
    monkeypatch.setattr(campaign_runner, "run_campaign_worker", lambda path, mode: calls.append((mode, path)) or 0)
    monkeypatch.setattr(campaign_runner, "campaign_status", lambda path: {"status": "NOT_STARTED"})
    monkeypatch.setattr(campaign_runner, "request_campaign_stop", lambda path: {"stop_requested": True})

    assert cli.main(["report", str(manifest)]) == 0
    assert capsys.readouterr().out == "saved report\n"
    assert cli.main(["status", str(manifest)]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "NOT_STARTED"
    assert cli.main(["stop", str(manifest)]) == 0
    assert json.loads(capsys.readouterr().out)["stop_requested"] is True
    assert cli.main(["resume", str(manifest)]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "NOT_STARTED"
    assert calls == [("report", str(manifest)), ("resume", str(manifest))]


def test_cli_init_accepts_slurm_profile_for_direct_linux_manifest(monkeypatch, capsys):
    profile = {
        "target": "slurm", "evidence": "VALIDATED_RUNTIME",
        "slurm": {"partition": "compute", "account": None, "qos": None},
        "allocation": {"nodes": 1, "total_cpus": 4, "memory": "8G", "walltime": "01:00:00", "max_parallel_steps": 1, "shutdown_margin_seconds": 60, "termination_grace_seconds": 30},
        "runtime": {"module_commands": [], "siesta_executable": "/opt/siesta", "exclusive": True, "environment": {}, "launcher": {"kind": "hydra", "command": ["mpiexec.hydra"], "bootstrap": "ssh", "processes_per_node": 4}},
        "task_policy": {"max_attempts": 1, "require_scf_converged": True},
    }
    profile_path = "slurm-profile.json"
    dispatched = {}

    class SyntheticPath:
        def __init__(self, value):
            self.value = value
        def read_text(self, encoding="utf-8"):
            return json.dumps(profile) if self.value == profile_path else "{}"
    monkeypatch.setattr(cli, "Path", SyntheticPath)

    def fake_initialize(**kwargs):
        dispatched.update(kwargs)
        return {"campaign_id": "direct", "manifest_path": "/campaigns/direct/campaign.v2.json"}

    monkeypatch.setattr("hubbardflow.execution.wsl_campaign_init.initialize_campaign", fake_initialize)
    monkeypatch.setattr("hubbardflow.cli.sys.platform", "linux")
    assert cli.main([
        "init", "/inputs/reference.fdf", "--lr-config", "/inputs/lr.json",
        "--profile", profile_path, "--name", "direct", "--campaign-root", "/campaigns",
    ]) == 0
    assert dispatched["campaign_root"] == "/campaigns"
    assert "pointer_path" not in dispatched
    assert json.loads(capsys.readouterr().out)["campaign_id"] == "direct"
