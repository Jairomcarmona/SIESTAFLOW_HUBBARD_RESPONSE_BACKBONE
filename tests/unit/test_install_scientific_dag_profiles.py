import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).parents[2]
INSTALLER = ROOT / "tools" / "install_scientific_dag.py"


def _campaign(root: Path) -> Path:
    campaign = root / "campaign"
    (campaign / "runs" / "00_REFERENCE").mkdir(parents=True)
    (campaign / "pseudopotentials").mkdir()
    (campaign / "scripts").mkdir()
    (campaign / "runs" / "manifest.json").write_text(
        json.dumps([
            {"id": "00_REFERENCE", "mode": "REFERENCE"},
            {"id": "10_A_BARE_MINUS", "mode": "BARE", "target": "Mn"},
        ]),
        encoding="utf-8",
    )
    (campaign / "runs" / "00_REFERENCE" / "siesta.fdf").write_text(
        "%block ChemicalSpeciesLabel\n1 25 Mn\n%endblock ChemicalSpeciesLabel\n",
        encoding="utf-8",
    )
    (campaign / "pseudopotentials" / "Mn.psml").write_text(
        '<psml><pseudo-atom-spec atomic-number="25"/></psml>\n',
        encoding="utf-8",
    )
    (campaign / "scripts" / "validate_run.py").write_text("print('VALID')\n", encoding="utf-8")
    (campaign / "scripts" / "analyze.py").write_text("print('ANALYZED')\n", encoding="utf-8")
    return campaign


def test_clean_generic_campaign_installs_portable_profiles_without_running_them(tmp_path):
    campaign = _campaign(tmp_path)
    completed = subprocess.run(
        [sys.executable, str(INSTALLER), "--campaign-root", str(campaign)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["status"] == "SCIENTIFIC_DAG_INSTALLED"
    installed = campaign / "scripts" / "siestaflow_dag"
    assert (installed / "psml_selection.py").is_file()
    assert (installed / "siesta_dftu_fdf.py").is_file()
    assert (installed / "scientific_dag_analysis.py").is_file()
    config = json.loads((campaign / "scripts" / "scientific_dag.json").read_text())
    assert config["central_label"] == "Mn"
    assert config["analysis_script"] == "scripts/analyze.py"
    assert config["analysis_acceptance"] == {"schema_version": 1, "kind": "generic_full_rank"}
    template = (campaign / "slurm" / "submit_scientific_lru_dag.slurm").read_text()
    assert 'local_openmpi)' in template
    assert 'slurm_hydra_5x20)' in template
    assert "mpiexec.hydra" in template
    assert "--map-by \"ppr:$PPN:node\"" in template
    assert not (campaign / "results").exists()


def test_explicit_campaign_validator_is_hash_pinned_in_config(tmp_path):
    campaign = _campaign(tmp_path)
    validator = campaign / "scripts" / "validate_analysis.py"
    validator.write_text("print('{}')\n", encoding="utf-8")
    completed = subprocess.run(
        [
            sys.executable,
            str(INSTALLER),
            "--campaign-root",
            str(campaign),
            "--analysis-validator",
            "scripts/validate_analysis.py",
            "--campaign-id",
            "fixture-campaign-v1",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    acceptance = json.loads((campaign / "scripts" / "scientific_dag.json").read_text())["analysis_acceptance"]
    assert acceptance["kind"] == "campaign_hook"
    assert acceptance["campaign_id"] == "fixture-campaign-v1"
    assert acceptance["validator_script"] == "scripts/validate_analysis.py"
    import hashlib

    assert acceptance["validator_sha256"] == hashlib.sha256(validator.read_bytes()).hexdigest()
